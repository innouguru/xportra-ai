# Blocked — Bootstrap authorization policy (Phase 4D.10)

**Status:** Blocked — authorization mechanism implemented (migrations 015–017, authorization table, audit linkage, atomic transaction, fail-closed bootstrap); live owner authorization and independent verification remain deferred. Read-only operational procedure documented in `docs/phases/phase-4d-regulatory-knowledge-administration.md` (§Task 2 procedure) and this file.

## Operational authorization procedure (documented, not executed)

This procedure is the approved, auditable mechanism for independently verifying and recording the initial `grant_manage` bootstrap. It has not been executed; no authorization record exists; no live grant has been created.

### 1. Authorized parties (frozen by design)
- **Authorizer:** The product owner (or an independently designated authority explicitly named in writing). Only the product owner may authorize the initial `grant_manage` grant. The target user must never authorize their own bootstrap.
- **Target:** A single, explicitly named user (e.g., the intended initial trusted operator). The internal user UUID (`users.id`) is resolved at execution time through the verified identity-mapping contract (`supabase_uid` → `users.id`) and must never be hardcoded in documentation or code.
- **Independent verifier:** A separate operator (not the target user, not the same individual acting as both authorizer and verifier unless explicitly authorized with justification and audit). The verifier must confirm the authorizer's instruction through an explicitly identified, trusted out-of-band channel (e.g., a signed message, a recorded meeting reference, or a documented approval record retained in an independent location). The repository does not currently establish a single digital-signature mechanism or a fixed evidence-retention location; these remain unresolved operational details that must be specified before the live operation.
- **Operator (executor):** The independent operator who performs the bootstrap transaction. The operator uses the verified authorization reference (`global_staff_authorizations.authorization_ref`) to execute the bootstrap atomically.

### 2. Independent verification and evidence requirements
- The verifier records: (a) the authorizing party identity/reference; (b) the target user identity/reference; (c) the scope (`grant_manage` only); (d) the verification method (explicit trusted channel); (e) the authorization reference identifier (`authorization_ref`, not free text); (f) justification; (g) timestamps (`approved_at`, `verified_at`); (h) status (`approved`).
- Evidence must be sufficient for a later independent audit: an auditor must be able to reconstruct who authorized, who verified, through which channel, with what reference, and when — without relying solely on the database record.
- Unresolved operational detail: The repository does not specify a required trusted verification channel (e.g., signed document store, meeting log, external approval system) or the retention location for independent evidence. This must be resolved before live authorization. **Proposed resolution (not executed):** The product owner retains the independent verification evidence (e.g., signed authorization reference file, meeting/minutes reference, or secure message log) in an organization-controlled, access-controlled store separate from the repository (e.g., company document management or approved secret management), with access restricted to the product owner and a designated auditor. The authorization reference (`authorization_ref`) stored in `global_staff_authorizations` links to this evidence; the auditor verifies the link by comparing the reference in the database against the retained evidence record.
- Unresolved operational detail: The exact authority allowed to approve exceptions (e.g., same-person exception for Stage A/Stage B) is not defined in code or documentation; the procedure treats any exception as requiring the same independent verification and audit linkage.

### 3. Authorization record consumption (atomic, single-use)
- The authorization record is created in `global_staff_authorizations` (migration 016) with status `approved` and a non-empty `authorization_ref` (constraint enforced by database check).
- During bootstrap (migration 015 service logic), the authorization is verified: it must exist, match `(target_user_id, permission)`, have status `approved`, and not be `consumed` or `revoked`. The authorization is consumed (`status` updated to `consumed`, `consumed_at` set, `consumed_by` recorded) in the same database transaction as the grant creation.
- After consumption, the authorization cannot be reused for another target or grant. Duplicate attempts must reference a new, independently verified authorization record.
- If audit insertion (`global_staff_audit`, migration 015) fails, the transaction rolls back and neither the grant nor the authorization consumption takes effect (fail-closed).

### 4. What is NOT sufficient (confirmed by repository inspection)
- Verified Supabase login or active user record alone.
- Tenant `owner` status or membership (`user_tenant_memberships`) as a substitute for global staff authorization.
- Caller-supplied actor UUID without server-side identity resolution (`AuthenticatedIdentity.subject` → `users.supabase_uid` → `users.id`).
- Free-text `justification` without a verifiable `authorization_ref` and independent authorization process.
- A `postgres` database role observation (the `postgres` user is a superuser and does not represent the application role).

### 5. Audit and retention
- Every bootstrap event creates an append-only audit record (`global_staff_audit`, migration 015, trigger-protected against UPDATE/DELETE by ordinary roles; absolute immutability against privileged administrators is not claimed).
- The audit event retains: `event_type` (`bootstrap`), `actor_user_id`, `target_user_id`, `permission` (`grant_manage`), `reason`/`justification`, `authorization_ref` (from migration 017 linkage), and timestamp.
- Provisional audit retention: 24 months (not a verified statutory requirement; final retention/deletion controls remain unresolved and disabled).

### 6. Failure, duplicate, and retry behavior
- Self-bootstrap (`actor_user_id == target_user_id` with `permission == grant_manage`) is denied by the service (`_deny_self_managed`).
- If an active `grant_manage` row exists for any user, bootstrap fails with `AlreadyBootstrappedError`.
- If authorization is missing, revoked, expired, consumed, or does not match target/scope, bootstrap fails with `ApplicationValidationError`.
- Retries without a new authorization reference must fail; retries with the same consumed reference must fail.
- No manual database procedure may bypass the authorization reference verification or audit insertion.

### 7. Approved policy decisions (recorded under product-owner authorization for initial release)
- Single-operator exception approved (scope: `grant_manage`; justification: initial trusted operator `innouguru@gmail.com` identity verified externally 2026-10-21; unavailable second independent operator; never misrepresented as independent review).
- Self-bootstrap (`actor == target` with `grant_manage`) remains denied (service-level `_deny_self_managed` preserved).
- Verification mechanism / retention location: must be specified by product owner/operator before authorization insertion (approved prerequisite — must be established, not fabricated).
- Exception authority: must be fully defined before authorization execution (approved prerequisite — not yet fully defined; current partial definition: product owner approves exceptions with justification and audit linkage).
- Retention/deletion policy: provisional 24-month retention; automatic deletion disabled; must be finalized before broadening access (approved prerequisite — provisional policy approved for minimal release).
- Second operator / grant-manager: deferred for minimal release; single-operator exception applies (approved prerequisite — must be documented before broadening).
- Role choice (`postgres` superuser vs dedicated `xportra_app`): must be finalized before authorization/bootstrap (`xportra_app` verified locally; justification document required if `postgres` intended — approved prerequisite — must be finalized).
- Migration 029: reconstructed (`ADR-0020-reconstruction-note.md`); not applied to hosted/prod; provenance gap remains; requires separate authorization before application; includes note for explicit table grants if applied (`GRANT ... ON ALL TABLES IN SCHEMA xportra TO xportra_app;` applies only to existing tables).

### 8. Remaining operational prerequisites (must be confirmed by operator before live authorization/bootstrap insertion)
The following must be explicitly confirmed (not fabricated) before any authorization record is inserted or bootstrap executed:
- Verification mechanism / evidence retention location confirmed and established (exact trusted out-of-band channel specified; organization-controlled store location/access mechanism confirmed; authorization_ref linked to retained evidence).
- Exception authority fully defined (same-person exception rules for Stage A/Stage B, manual recovery; documented and approved).
- Database connection identity finalized (`postgres` justification with superuser acknowledgment documented, or dedicated `xportra_app` configured and verified against hosted DB with `SELECT current_user; SELECT * FROM pg_roles WHERE rolname = current_user;` showing `rolsuper = false`).
- Final retention/deletion policy finalized (period and deletion controls configured; provisional 24-month policy approved for minimal release but must be finalized before broadening).
- Second operator / grant-manager provision plan documented (even if deferred; must state mitigation for minimal release and plan for future broadening).
- Authorization reference (`authorization_ref`) generated (non-empty, unique, verifiable); authorization record (`global_staff_authorizations`) prepared with `status='approved'`, verified reference, target/permission scope (`grant_manage` only), justification (including single-operator exception justification), authorizer reference, and timestamps (`approved_at`, `verified_at`).

### 8. Prohibited actions (explicit confirmation)
This procedure and this task do NOT authorize:
- Creating the initial authorization record (`global_staff_authorizations`).
- Creating the initial live `grant_manage` grant (`global_staff_grants`).
- Wiring `require_global_staff` into admin routes (implemented as dependency only; not wired to any production route).
- Adding admin routes or admin UI.
- Deploying or altering production configuration.
- Running migrations against production/shared Supabase (migrations 015 applied only to isolated `xportra_test`; migrations 016 and 017 exist but are not applied to any verified environment).
- Changing role memberships, grants, passwords, connection strings, or database configuration.
- Inventing a real person's approval, completed verification event, timestamp, or evidence reference.

**Context:** ADR-0017 and the approved Phase 4D.10 Task 2 design document the bootstrap prerequisites (§L) but do not define a sufficient, independently verifiable authorization mechanism for the initial `grant_manage` grant. The approved contract requires:

- Independent product-owner authorization outside the ordinary permission workflow.
- Verifiable attribution (not a free-text justification string).
- Independent audit reference that can be verified later.
- Prevention of self-authorization and arbitrary caller grants.

**What is NOT sufficient (confirmed by inspection):**
- Verified Supabase login or active user record.
- Tenant `owner` status or membership.
- Caller-supplied actor UUID.
- Free-text `justification` / `reason` string without an authorization process.

**Decision required:**
1. Who independently authorizes the initial `grant_manage` grant?
2. How is that authorization verified outside the ordinary application permission workflow (e.g., signed authorization record, out-of-band operational procedure, separate authorization table)?
3. How is the authorization record referenced and independently verified during audit?
4. How is the authorized operation executed and attributed (actor, target, timestamp, reference)?
5. How are duplicate attempts, retries, and failed attempts recorded?
6. How does the procedure prevent self-authorization and arbitrary callers from creating the first global grant?

**Recommended option:**
- A separate `global_staff_authorizations` table (or equivalent external operational record) that records: authorizing party UUID/reference, authorization timestamp, scope (`grant_manage`), justification, authorization method/reference, and status (`approved`/`revoked`).
- The bootstrap operation must reference an approved authorization record by a verifiable identifier (not free text) and fail closed if the reference is missing, unverified, or does not match the actor/target/scope.
- Self-bootstrap remains denied; the authorization record must be created by an independent party, not the target.

**Alternatives:**
- External signed authorization token/file (operational record outside PostgreSQL) referenced by a secure hash; requires verification mechanism.
- Manual database/operations procedure only (no in-product authorization record); fails to provide verifiable audit reference.

**Trade-offs:**
- Separate authorization table increases schema complexity but provides verifiable audit linkage.
- External reference avoids schema change but requires a safe verification mechanism that does not expose secrets.

**Testable acceptance criteria (once approved):**
- Bootstrap without a verifiable authorization reference fails.
- Self-authorization (actor = target with authorization record created by target) fails.
- Duplicate authorization attempts are recorded safely.
- The authorization reference is preserved in audit history and can be independently verified.

**Next step:** Product-owner selects mechanism and approves schema/change before bootstrap authorization can be implemented.
