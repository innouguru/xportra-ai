# Regulatory Artifact Deletion & Legal-Hold Design — Read-Only Design Document (2026-10-21)

Status: Design only; no implementation authorized; deletion remains disabled.
Source of truth: approved retention policy (`docs/phases/regulatory-artifact-retention-policy.md`), storage-boundary audit (`docs/phases/regulatory-storage-boundary-audit.md`), ADR-0017 §5/§8, technology baseline (`docs/architecture/technology-baseline.md`), ADR-0018.

## Verdict: PASS WITH CONDITIONS — design is internally consistent and respects approved policy; implementation requires separate authorization and product-owner approval for deletion mechanism, legal-hold schema, and deployment prerequisites.

---

## 1.5 Legal-hold concurrency and resolution protocol

A hold is not simply a boolean flag; it is a durable, independently authorized state change that must serialize against deletion. Repeated hold checks alone are insufficient because they do not serialize concurrent authorization/deletion transactions. The repository's current model supports advisory locks (`pg_advisory_xact_lock`) and atomic transactions (`database.transaction()`), which must be used explicitly.

### 1.5.1 Serialization mechanism

- Before authorization/eligibility computation, the service acquires an advisory lock on the artifact identity (e.g., `SELECT pg_advisory_xact_lock(hashtext(artifact_id::text)::bigint)`). This serializes authorization, eligibility, and deletion progress for the same artifact within the database transaction. Because PostgreSQL advisory locks are transaction-scoped and end when the transaction commits or rolls back, they do not extend across the separate Supabase Storage mutation (Step 2). The design explicitly accepts this limitation: the advisory lock prevents concurrent authorization/deletion authorization for the same artifact within PostgreSQL, but it does not prevent concurrent storage mutations outside the database. Safety relies on the deletion-intent state being the authoritative gate: once authorized, the service must verify deletion-intent state (`authorized`, `deleting`, etc.) before calling adapter `delete()`, and concurrent authorizations must observe the same state to prevent duplicate storage mutations.
- If the repository's current `database.transaction()` does not expose advisory locks directly, the minimum required schema/service change is a transaction-level advisory lock function or a row-level lock (`SELECT ... FOR UPDATE`) on `regulatory_artifact_deletion_intent`. The design documents this as a required change rather than assuming safety from existing patterns alone.
- Hold placement/release also uses the same advisory lock (or a separate advisory lock scope `artifact_hold`) so that hold mutations serialize against deletion authorization. A concurrent deletion authorization must observe an active hold before proceeding to storage mutation.

### 1.5.2 Exact point of irreversibility

Deletion becomes irreversible at Step 2 (storage mutation) — not at authorization or eligibility verification. Before Step 2, rollback of the authorization transaction (Step 1) fully prevents storage mutation. After Step 2 succeeds, the artifact is physically removed; only reconciliation (Step 3) can confirm or alert about unreconciled audit/state failure. There is no database rollback of storage deletion; reconciliation must handle unreconciled states explicitly.

### 1.5.3 Concurrent hold/deletion scenarios

| Timeline / Race | Hold state before authorization | Deletion authorization outcome | Required behavior |
|---|---|---|---|
| Hold active, deletion authorized | Active | Blocked before Step 2 | Authorization verifies hold; deny; no storage mutation |
| Deletion authorized, hold placed before Step 2 | Active (placed after Step 1 but before Step 2) | Blocked at Step 2 entry | Re-check hold within same transaction before storage mutation; deny; delete storage call skipped; deletion-intent moves to `hold_placed` (or remains `authorized` with failure note) |
| Deletion authorized and Step 2 completed, hold placed after Step 2 | N/A (deletion already executed) | Already deleted | Hold applies to future operations, not retroactively; existing `deleted` state preserved; reconciliation continues independently |
| Concurrent authorization for same artifact (different authorization references) | Active or released | Serialized by advisory lock; second authorization waits or is denied based on state machine rules | Only one authorization proceeds per artifact at a time; duplicate protection ensures no duplicate storage mutation |

### 1.5.5 Limitations and guarantees

- **Guarantee**: Within PostgreSQL, advisory locks (or row-level locks) serialize authorization, eligibility computation, and hold mutations for the same artifact. Concurrent database transactions cannot both proceed to authorization or storage mutation without observing the same state.
- **Limitation**: Advisory locks end with the PostgreSQL transaction (Step 1). They do not cover the Supabase Storage mutation (Step 2) directly. Safety relies on the deletion-intent state being the authoritative gate: once Step 1 completes and inserts an `authorized` or `deleting` intent, any concurrent authorization must observe that state (through the deletion-intent table, not just the hold table) and deny or wait accordingly. A hold placed after Step 1 but before Step 2 is effective because the service re-checks the hold table (and deletion-intent state) within the authorization/Step 2 entry transaction; if an active hold exists, Step 2 is blocked.
- **Guarantee**: A hold placed after Step 2 (storage mutation completed) does not retroactively undo deletion; it applies to future deletion attempts (e.g., duplicate authorization or retry attempts) and is preserved independently.
- **Limitation**: If the process crashes after Step 1 completes (authorization verified, deletion-intent inserted) but before Step 2 starts, the deletion-intent remains `authorized`. A concurrent authorization could observe the `authorized` state and deny (if state-machine rules require `pending` or no active intent) or proceed only after reconciliation verifies authorization remains valid. The design requires the reconciliation/retry job to re-verify authorization and hold status before retrying Step 2; it must not assume authorization remains valid indefinitely.
- **Guarantee**: The deletion-intent table is durable and append-only; unreconciled states (`reconciled = False`) are preserved and alerted, never silently removed. Audit events (`global_staff_audit`) linked via `authorization_ref` are preserved independently of artifact storage state.
- **Limitation**: Cross-system atomic rollback (database + storage) is impossible. The outbox/saga design accepts unreconciled states and relies on bounded retries and reconciliation rather than a single atomic transaction.

- If authorization succeeds and deletion-intent is inserted, but the process crashes before Step 2, the deletion-intent remains `authorized`. A reconciliation/retry job must re-verify authorization (re-check `authorization_ref` validity, grant status, and hold status), re-check eligibility, and retry Step 2 within bounded retries. It must not create a new storage mutation without re-authorizing.
- If Step 2 succeeds but the process crashes before Step 3 (final reconciliation), the deletion-intent remains `deleted` (if `deleted_at` was set) or `authorized` (if not). The reconciliation job detects unreconciled rows (`reconciled = False` or `deleted_at` set with `reconciled = False`) and retries Step 3 (audit/state recording) without retrying Step 2 unless storage state is unconfirmed.
- If storage state is uncertain (e.g., signed URL verification ambiguous), reconciliation must treat it as unreconciled and retry verification; it must not assume deletion or retention without evidence.

---

- This design covers the authorization, eligibility, audit, and cross-system consistency required before any regulatory source artifact can be physically removed from storage.
- Deletion is NOT implemented; no endpoint, route, adapter exposure, or automatic scheduling is added.
- The adapter (`RegulatorySourceStorageAdapter`) exposes `delete()` only for compensating deletes (existing contract); it is NOT exposed through `RegulatorySourceStorageApplicationService` (new authorized boundary) and must not become user-facing until all controls below are implemented, tested, and deployed.
- Postgres (`global_staff_audit`, `regulatory_ingestion_jobs`, artifact metadata) and Supabase Storage (`regulatory-source-artifacts` bucket) are separate systems; a single ACID transaction cannot roll back both.

---

## 2. State machine proposal (artifact-level deletion lifecycle)

We propose a durable, queryable deletion-intent record (not a mutation of the original artifact metadata) that tracks the multi-system deletion process. This avoids corrupting provenance records and supports recovery/reconciliation.

### 2.1 New table: `regulatory_artifact_deletion_intent`

Purpose: durable, append-only intent and outcome tracking for every deletion attempt. This is the audit source of truth; original artifact metadata (`regulatory_source_artifacts`) and ingestion history (`regulatory_ingestion_jobs`) are preserved unchanged.

Proposed columns:

| Column | Type | Constraint / Note |
|---|---|---|
| `id` | UUID, PK | Generated by application service |
| `artifact_id` | UUID, NOT NULL, FK → `regulatory_source_artifacts.id` | Immutable reference |
| `content_hash` | TEXT, NOT NULL | Verified against artifact at request time |
| `status` | TEXT, NOT NULL, CHECK (`pending`, `eligible`, `ineligible`, `authorized`, `hold_placed`, `deleting`, `deleted`, `failed`, `reconciled`) | Explicit state machine |
| `actor_user_id` | UUID, NOT NULL | Authorized actor (`GRANT_MANAGE` holder) |
| `authorization_ref` | TEXT, NOT NULL | Independent authorization reference (matches `global_staff_authorizations` pattern) |
| `reason` | TEXT, NOT NULL | Justification provided by actor |
| `retention_eligibility` | TEXT, NOT NULL, CHECK (`current_published`, `superseded_24mo`, `rejected_24mo`, `withdrawn_24mo`, `manual_recovery`, `ineligible`) | Derived from artifact status and retention rules |
| `legal_hold_active` | BOOLEAN, NOT NULL, DEFAULT FALSE | Set by hold mechanism; blocks deletion |
| `audit_event_ref` | TEXT | Link to `global_staff_audit` event for authorization/deletion audit |
| `requested_at` | TIMESTAMP WITH TIME ZONE, NOT NULL | Request time |
| `authorized_at` | TIMESTAMP WITH TIME ZONE | Authorization verification time |
| `deleted_at` | TIMESTAMP WITH TIME ZONE | Only set after confirmed storage deletion and final reconciliation |
| `reconciled` | BOOLEAN, NOT NULL, DEFAULT FALSE | Confirms storage deletion matches database state |
| `reconciliation_note` | TEXT | Explanation of reconciliation outcome |

### 2.2 New table: `regulatory_artifact_legal_hold`

Purpose: durable, append-only record of legal/compliance holds that suspend deletion for specific artifacts.

Proposed columns:

| Column | Type | Constraint / Note |
|---|---|---|
| `id` | UUID, PK | |
| `artifact_id` | UUID, NOT NULL, FK → `regulatory_source_artifacts.id` | Scope holds to one artifact |
| `status` | TEXT, NOT NULL, CHECK (`active`, `released`, `expired`) | Hold state |
| `actor_user_id` | UUID, NOT NULL | Authorized staff who placed/released hold |
| `authorization_ref` | TEXT, NOT NULL | Independent authorization reference |
| `reason` | TEXT, NOT NULL | Justification for hold |
| `placed_at` | TIMESTAMP WITH TIME ZONE, NOT NULL | |
| `released_at` | TIMESTAMP WITH TIME ZONE | Only set after release |
| `released_by` | UUID | Actor who released |
| `release_authorization_ref` | TEXT | Authorization reference for release |

Rules:
- A hold is placed independently of any deletion request. Once active (`status = 'active'`), any deletion eligibility check must return ineligible until the hold is released (`status = 'released'`).
- Hold release requires the same authorization boundary (`GRANT_MANAGE`) and records an independent authorization reference.
- Holds must never be silently overridden by a concurrent deletion request; deletion must query the hold table within the same authorization verification transaction and fail closed if an active hold exists.

---

## 3. Deletion eligibility rules (matching approved retention policy)

Eligibility is computed server-side at authorization time; it must never be inferred from a client-supplied status.

### 3.1 Eligibility derivation

Given an artifact row (`regulatory_source_artifacts`), the service must verify:

1. `artifact_id` exists and is immutable.
2. `content_hash` is verified and matches the artifact at request time (prevents deleting a superseded or altered artifact without awareness).
3. Artifact status and source linkage are read from authoritative database records, not from client input.
4. Retention duration is computed from the authoritative supersession/rejection/withdrawal timestamp (stored in `regulatory_sources` or derived from stage decisions).

Eligibility results:

- `current_published`: artifact linked to a published (Stage B applicable/current) requirement and source is current → **ineligible**.
- `superseded_24mo`: supersession date recorded and `now() - supersession_date >= 24 months` → eligible only if no active hold.
- `rejected_24mo`: rejection/review-completion date recorded and `now() - date >= 24 months` → eligible only if no active hold.
- `withdrawn_24mo`: withdrawal/rejection date recorded and `now() - date >= 24 months` → eligible only if no active hold.
- `manual_recovery`: artifact created through manual recovery (`failed`, `partial`, `zero_candidates`) → eligible only after 24 months from creation/recovery date and with same hold checks.
- Any missing timestamp, ambiguous status, missing provenance, or unverified retention calculation → **ineligible** (fail-closed).

### 3.2 Authorization before eligibility check

- Every deletion request must provide `actor_user_id` and `authorization_ref`.
- The authorized application service (`RegulatorySourceStorageApplicationService` pattern, extended) verifies `GlobalStaffGrantService.is_granted(actor_user_id, GRANT_MANAGE)` before any eligibility computation.
- If authorization fails, eligibility is never evaluated; the request fails with `PermissionDeniedError`.
- If authorization passes but eligibility computes to `ineligible`, the request fails with `ApplicationValidationError` (never a silent denial).
- No deletion endpoint is exposed to clients without this two-stage verification (authorization first, eligibility second, hold check third).

---

## 4. Audit and cross-system consistency

Because PostgreSQL and Supabase Storage are separate systems, we must accept that a single ACID transaction spanning both is impossible. Instead, we design a durable, recoverable state machine using an outbox/saga pattern with idempotent retries and reconciliation.

### 4.1 Deletion saga (ordered, idempotent steps)

Step 1 — Authorization and eligibility verification (PostgreSQL transaction):
- Lock artifact metadata (advisory lock or row-level lock on `regulatory_source_artifacts`).
- Verify authorization (`GRANT_MANAGE`).
- Verify no active legal hold (`regulatory_artifact_legal_hold`).
- Compute eligibility; if ineligible, rollback and raise error.
- Insert deletion-intent record (`regulatory_artifact_deletion_intent`) with `status = 'authorized'`, `actor_user_id`, `authorization_ref`, `reason`, `retention_eligibility`, and `audit_event_ref` linked to `global_staff_audit` event inserted atomically.
- If audit insertion fails, rollback deletion-intent and raise error (fail-closed).

Step 2 — Storage deletion (Supabase Storage):
- Call adapter `delete()` with the exact `artifact_uri` (object key) derived from the artifact record.
- If storage deletion fails (network, authorization, missing object), leave deletion-intent at `status = 'authorized'` or set to `failed`, and initiate retry/reconciliation. Never silently skip.
- If storage deletion succeeds, proceed to Step 3. If it fails after retries, set `status = 'failed'` with `reconciliation_note` describing storage state and retry schedule.

Step 3 — Final audit and reconciliation (PostgreSQL transaction):
- Update deletion-intent `status = 'deleted'` and set `deleted_at`.
- Verify storage state by attempting a signed URL or listing the object; if the object still exists, treat as unreconciled (`reconciled = False`) and schedule reconciliation retry.
- If storage deletion confirmed and audit event exists, update `reconciled = True` and `reconciliation_note`.
- If audit/state recording fails but storage deletion succeeded, the artifact is deleted but unreconciled (`reconciled = False`). A reconciliation job must retry audit/state recording; the artifact must never be falsely reported as not deleted. The unreconciled state must trigger an operational alert, not a silent omission.

### 4.2 Idempotency, duplicate-request safety, and retry exhaustion

The repository's existing authorization mechanism uses independent authorization references (`global_staff_authorizations`). A deletion operation must preserve the original authorization, actor, reason, and audit linkage exactly across retries. The current design uses `(artifact_id, authorization_ref, actor_user_id)` as the unique key on `regulatory_artifact_deletion_intent`. This is sufficient for duplicate prevention when authorization references are unique per operation, but a dedicated operation/request identifier (`operation_id`) would improve traceability if authorization references are reused or if the same actor requests the same deletion with a renewed authorization. Given the current authorization design (independent references per authorization event), the composite key is adequate, but the service must treat the authorization reference as immutable for the operation; any retry reuses the same `authorization_ref` and does not invent a new one.

**Duplicate rules:**
- Same `(artifact_id, authorization_ref, actor_user_id)`: read existing `regulatory_artifact_deletion_intent`; return current state; no new mutation; no new storage call.
- Different `authorization_ref` for same `artifact_id`: new authorization check. Verify authorization, eligibility, and hold status. If an active deletion-intent exists in `authorized`, `deleting`, or `deleted` state, deny (to prevent concurrent conflicting operations). If `failed`, allow a new authorization only after bounded retry exhaustion and reconciliation of previous failure.
- No duplicate storage mutation is permitted under any authorization reference combination.

**Retry exhaustion:**
- Retries are bounded (e.g., maximum 5 attempts, with exponential backoff starting at 30 seconds, capped at 5 minutes). After exhaustion, `status` moves to `failed`, `reconciled = False`, and `reconciliation_note` records the exhaustion reason.
- A manual reconciliation (not automatic) is required to either retry with a new authorization or confirm unrecoverable failure. The unreconciled state must trigger an operational alert.
- Retries must verify authorization (`GRANT_MANAGE`) and eligibility (including hold status) before each retry. If authorization or eligibility fails during retry, the retry stops and the state moves to `failed` or `ineligible` (depending on failure type) without continuing storage mutations.

**Storage success followed by database failure:**
- If Step 2 succeeds (storage deleted) but Step 3 fails (audit/state update fails), the deletion-intent must remain unreconciled (`reconciled = False`). The reconciliation job retries Step 3 only; it must not retry Step 2 unless storage absence is unconfirmed. If storage absence is unconfirmed, the reconciliation must verify storage state first (via signed URL attempt or storage list API); if the object is absent, proceed with Step 3; if present, treat as unreconciled and retry storage deletion with bounded retries (but only after confirming authorization remains valid).

**Database intent creation followed by process crash:**
- If Step 1 completes (authorization verified, deletion-intent inserted) but the process crashes before Step 2, the reconciliation/retry job detects `authorized` state, verifies authorization and eligibility (re-checking hold status), verifies storage state, and proceeds to Step 2 or Step 3 as appropriate. It does not create a new authorization reference or duplicate mutation.

### 4.3 Failure scenarios and expected outcomes

| Scenario | Database state | Storage state | Service behavior / reconciliation |
|---|---|---|---|
| Authorization fails | No deletion-intent inserted | Unchanged | Deny; no audit event |
| Eligibility ineligible | No deletion-intent inserted (or existing intent remains unchanged) | Unchanged | Deny with explicit ineligible reason; no storage call |
| Active legal hold | Intent not created; or if hold placed after authorization, delete blocked | Unchanged | Deny; hold must be released first |
| Audit insertion fails during authorization phase | Deletion-intent rolled back; no audit event inserted | Unchanged | Fail-closed; retry authorization/audit |
| Storage deletion fails (network/auth/missing key) | Deletion-intent remains `authorized` or `failed` | Unchanged (if never deleted) or partially deleted (if partial) | Retry with bounded retries; never claim deleted |
| Storage deletion succeeds, audit/state update fails | Deletion-intent `status` remains `authorized` or updated without final audit; storage deleted | Deleted | Reconciliation job retries audit/state; unreconciled state must alert; artifact must not be falsely reported as retained |
| Reconciliation confirms storage deleted and audit exists | `deleted`, `reconciled = True` | Deleted | Complete; audit preserved |
| Duplicate request with same authorization reference | Read existing intent; no new mutation | No new mutation | Return current state; no duplicate storage action |
| Duplicate request with different authorization reference, artifact already deleted (`reconciled = True`) | Read `deleted`; deny new authorization | Deleted | Deny; artifact remains deleted; previous audit preserved |
| Concurrent hold placed during authorization phase | Hold table has `active` row; delete blocked before storage mutation | Unchanged | Deny; authorization verified but hold prevents progression |

---

## 5. Security and exposure rules

- **Authorization**: Every deletion request requires an active `GRANT_MANAGE` grant verified through `GlobalStaffGrantService.is_granted()`. No other permission (including any future expanded permission set) authorizes deletion unless explicitly approved.
- **Application boundary**: Deletion is only reachable through `RegulatorySourceStorageApplicationService` (or an equivalent future authorized service). The adapter (`RegulatorySourceStorageAdapter`) must never be called directly by any API route, worker, or script. The adapter's `delete` method is not exposed through the application service at this time.
- **No public endpoint**: No public HTTP endpoint exposes deletion. Any future endpoint must reuse `require_global_staff` (`GRANT_MANAGE`) and must not accept arbitrary keys or artifact IDs from untrusted clients without server-side authorization and eligibility verification.
- **No tenant-membership substitute**: `GRANT_MANAGE` is the only authorization mechanism; tenant membership (`user_tenant_memberships`) never substitutes for it.
- **No service-role secret exposure**: The adapter uses `SUPABASE_SERVICE_ROLE_KEY` for storage access. This secret must not be logged, included in error responses, or exposed to clients. Any future endpoint that creates signed URLs must sanitize responses so URLs are not logged with secrets or embedded in error messages.
- **Audit reference independence**: The authorization reference (`authorization_ref`) is an independent, verifiable record (`global_staff_authorizations`). It is not fabricated by the caller and must match the target artifact scope.

---

## 6. Testing requirements (before any deletion is enabled)

These are design-level test requirements, not implemented tests. A separate authorized task must implement them.

### 6.1 Authorization and eligibility
- Deny deletion for missing/invalid `actor_user_id`, revoked/missing `GRANT_MANAGE`, or invalid `authorization_ref`.
- Deny deletion for `current_published` artifacts (indefinite retention).
- Deny deletion for artifacts missing supersession/rejection/withdrawal timestamps.
- Allow deletion only when retention duration (24 months for superseded/rejected/withdrawn; 24 months for manual recovery) is verified and no active legal hold exists.

### 6.2 Legal holds
- Place active hold with `authorization_ref` and justification.
- Release hold with independent authorization reference.
- Verify deletion is blocked when active hold exists; verify deletion proceeds (if eligible) after release.
- Verify concurrent hold placement during authorization phase blocks progression.

### 6.3 Concurrent and duplicate behavior
- Concurrent authorization + eligibility + hold check must not allow two deletions to proceed simultaneously for the same artifact with different authorization references (advisory lock or row-level lock on `regulatory_artifact_deletion_intent`).
- Duplicate requests with same authorization reference must not trigger duplicate storage mutations.
- Concurrent storage deletion attempts must be serialized; only one must succeed.

### 6.4 Audit durability, retention, and artifact-level evidence

`global_staff_audit` (existing append-only audit) is sufficient for authorization linkage (`authorization_ref`, `actor_user_id`, `permission`, `reason`, timestamp) but is **insufficient** for full durable artifact-level deletion evidence. The audit repository does not store `artifact_id`, `content_hash`, `retention_eligibility`, `reconciled` state, `reconciliation_note`, or retry history. Therefore, the design requires either:

- **Option A (recommended)**: Extend `global_staff_audit` with optional fields (`artifact_id`, `content_hash`, `operation_type`, `reconciliation_state`) only if a broader audit redesign is approved; or
- **Option B (current design)**: Use `global_staff_audit` for authorization/deletion authorization events, and rely on `regulatory_artifact_deletion_intent` as the durable artifact-level audit source for `artifact_id`, `content_hash`, eligibility, reconciliation, retry history, and final disposition. The `audit_event_ref` in `regulatory_artifact_deletion_intent` links the authorization event (in `global_staff_audit`) to the artifact-level outcome (in `regulatory_artifact_deletion_intent`).

Given the approved policy requires artifact-level audit (`actor_user_id`, `authorization_ref`, timestamp, justification, `artifact_id`, `content_hash`), Option B is sufficient and minimizes schema changes to the existing audit mechanism. The audit retention period (24 months provisional) applies to both authorization events and deletion-intent records; neither audit mechanism deletes its own historical records before the retention period.

Audit records must never be deleted merely because the source artifact has been removed. The retention policy and audit mechanism must preserve the authorization event (`global_staff_audit`), the deletion-intent record (`regulatory_artifact_deletion_intent`), and any retry/reconciliation notes independently of the artifact's storage state. Deletion of audit records requires the same authorization (`GRANT_MANAGE`), eligibility, and audit linkage as artifact deletion; the audit mechanism itself does not delete its own historical events before the retention period (24 months provisional, or indefinite for current audit retention as approved).

If audit insertion fails during authorization phase, the deletion-intent is rolled back (fail-closed). If audit/state recording fails after storage deletion succeeds, the unreconciled state (`reconciled = False`) is preserved, alerted, and retried; it is never silently removed or overwritten by a new authorization.

### 6.5 Failure and recovery
- Storage failure (missing object, authorization error, network timeout) must not corrupt database state or falsely claim deletion.
- Crash recovery must detect unreconciled deletion-intent rows (`deleted_at` set but `reconciled = False`) and retry reconciliation; it must not retry storage deletion unless storage state is confirmed unchanged (to avoid false deletion confirmation).
- Reconciliation must verify storage object absence (via signed URL attempt or storage list API) and database `reconciled` state.
- No deletion-intent row may be silently removed; unreconciled rows must trigger operational visibility (log/alert), not silent omission.

### 6.6 Security
- Adapter `delete` is not exposed through application service.
- No endpoint allows arbitrary object-key deletion without server-composed key verification.
- No endpoint allows retrieval or download of regulatory artifacts without `GRANT_MANAGE` authorization (existing authorized boundary preserved).
- No public bucket, anonymous download, or unsigned URL exists for regulatory artifacts.

---

## 7. Migration proposal (not implemented; requires authorization)

These are proposed schema changes for the future authorized implementation. They are not applied.

### 7.1 Migration: `019_regulatory_artifact_legal_hold`

Creates `xportra.regulatory_artifact_legal_hold` with columns: `id` (UUID PK), `artifact_id` (UUID NOT NULL, FK `regulatory_source_artifacts.id`), `status`, `actor_user_id`, `authorization_ref`, `reason`, `placed_at`, `released_at`, `released_by`, `release_authorization_ref`. Includes indexes on `artifact_id`, `status`, `actor_user_id`, `placed_at`.

### 7.2 Migration: `020_regulatory_artifact_deletion_intent`

Creates `xportra.regulatory_artifact_deletion_intent` with columns listed in §2.1. Includes composite index on `(artifact_id, authorization_ref, actor_user_id)` for duplicate detection; index on `status`; index on `artifact_id`; index on `reconciled` + `status` for reconciliation queries.

### 7.3 Migration: `021_regulatory_artifact_deletion_audit_link`

Optional but recommended: creates a foreign-key or linkage mechanism between `regulatory_artifact_deletion_intent.audit_event_ref` and `global_staff_audit.authorization_ref` if the audit mechanism is extended. If the existing audit mechanism remains sufficient, no additional migration is required; the linkage is maintained through the `authorization_ref` value and `audit_ref` fields.

### 7.4 Migration: `022_regulatory_artifact_retention_computation`

Optional but recommended: creates or updates a computed/enforced retention eligibility function/index that verifies artifact status and retention duration. If eligibility is computed at request time (not stored), this migration is unnecessary; eligibility is derived from authoritative records at authorization time.

---

## 8. Deployment prerequisites (not implemented; requires authorization)

Before any deletion mechanism is deployed or enabled:

1. Dedicated private bucket/access policy (`ADR-0018`) configured.
2. Service identity (`REGULATORY_WORKER_ACTOR_USER_ID`) configured and active `GRANT_MANAGE` grant provisioned through approved authorization procedure.
3. `RegulatorySourceStorageApplicationService` deployed and wired; adapter `delete` remains unexposed; no public endpoint exists.
4. `regulatory_artifact_legal_hold` table deployed with authorization and audit linkage.
5. `regulatory_artifact_deletion_intent` table deployed with state machine, duplicate protection, and reconciliation fields.
6. Deletion authorization endpoint (if any future endpoint is added) enforced by `require_global_staff` and eligibility verification.
7. Audit mechanism (`global_staff_audit`) verified and linked; audit insertion atomic with authorization phase.
8. Reconciliation mechanism (scheduled or triggered job) implemented and tested; unreconciled states trigger operational visibility.
9. Focused tests (§6) pass: authorization, eligibility, holds, concurrency, audit atomicity, storage failure, crash recovery, reconciliation, duplicate detection, security.
10. Integration tests against isolated database (`DATABASE_URL`) pass for authorization, state transitions, and reconciliation.
11. Product-owner approval obtained for deletion mechanism, retention durations, and deployment.

---

## 9. Decision status: approved vs. open

### Approved (per user directive for this refinement)
- Durable saga/outbox with bounded retries and reconciliation: approved.
- Existing retention durations (indefinite current/published; 24 months superseded/rejected/withdrawn/manual recovery): approved.
- `global_staff_audit` for authorization/deletion authorization events; `regulatory_artifact_deletion_intent` for durable artifact-level evidence linked by `audit_event_ref`: approved.
- Fail-closed handling of unreconciled outcomes (unreconciled state alerts, bounded retries, no silent omission): approved.
- No public deletion endpoint; adapter `delete` remains unexposed to ordinary application flows: approved.
- Deletion disabled until all prerequisites (§8) verified: approved.

### Open prerequisites (before any implementation)
- Dedicated private bucket/access policy (`ADR-0018`) configured.
- Service identity (`REGULATORY_WORKER_ACTOR_USER_ID`) configured and active `GRANT_MANAGE` grant provisioned.
- `RegulatorySourceStorageApplicationService` deployed and wired; adapter `delete` unexposed.
- `regulatory_artifact_legal_hold` table deployed with authorization and audit linkage.
- `regulatory_artifact_deletion_intent` table deployed with state machine, duplicate protection, reconciliation fields, and advisory-lock support.
- Deletion authorization endpoint (if any future endpoint added) enforced by `require_global_staff` and eligibility verification.
- Audit mechanism (`global_staff_audit`) verified and linked; audit insertion atomic with authorization phase.
- Reconciliation mechanism (scheduled or triggered job) implemented, tested, and producing operational visibility for unreconciled states.
- Focused tests (§6) pass: authorization, eligibility, holds, concurrency, audit atomicity, storage failure, crash recovery, reconciliation, duplicate detection, security.
- Integration tests against isolated database (`DATABASE_URL`) pass for authorization, state transitions, and reconciliation.
- Product-owner approval obtained for deployment of deletion mechanism.

---

## 10. Separate bounded implementation prompt (if design is approved)

If the design above is approved by the product owner and all prerequisites (§8) are met, the bounded implementation prompt would be:

> Implement migrations `019_regulatory_artifact_legal_hold`, `020_regulatory_artifact_deletion_intent`, `021_regulatory_artifact_deletion_audit_link` (optional), and `022_regulatory_artifact_retention_computation` (optional) in an isolated database. Implement `LegalHoldService` and `DeletionIntentService` following existing authorization (`GlobalStaffGrantService`), audit (`GlobalStaffAuditRepository`), and repository patterns. Implement reconciliation job. Add focused tests (§6). Ensure adapter `delete` remains unexposed; ensure `RegulatorySourceStorageApplicationService` does not expose deletion. Confirm no public endpoint exists. Confirm deletion remains disabled until all prerequisites verified.

This prompt is NOT authorized by this design document; it requires separate product-owner authorization.
