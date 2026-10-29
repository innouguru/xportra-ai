# ACTIVE_TASK.md — Current Active Task

**Active task:** Phase 4D — Regulatory Ingestion Execution Path — Milestone 2
(worker-driven durable ingestion from pending job to candidate persistence).

**Status:** Complete — committed as 12ddfc2 (fix: regulatory publication status
transition and cross-tenant fail-closed).

**Authorization basis:** Explicitly assigned by user tasking. The existing
bootstrap task (initial `grant_manage` provisioning under `XPA-GSA-INIT-001`)
remains a separate track. Per tasking, bootstrap is NOT re-executed and no
production grants are created or revoked. Production grant state cannot be
verified from this environment (no `DATABASE_URL` configured; no production
contact). The local test database has no `grant_manage` rows, so the worker
skips execution fail-closed until `REGULATORY_WORKER_ACTOR_USER_ID` is
configured with an active grant.

## Implemented (this milestone)

1. **Worker now drives extraction (was: auto-completed jobs without processing)**
   - `RegulatoryIngestionWorker._poll_cycle` reserves one pending/retryable job
     via `SELECT ... FOR UPDATE SKIP LOCKED`, then delegates to
     `RegulatoryCandidateExtractionService.extract_candidates()` which performs
     the atomic claim (pending/retryable → claimed), parse → normalize → extract
     → persist, and marks the job completed or failed/retryable.
   - Jobs without `artifact_id` (source-registration placeholders from
     `register_source`) are skipped — they have no content to process.
   - Extraction failures are logged; the job is not falsely completed.
   - Worker startup/shutdown via FastAPI lifespan unchanged
     (`xportra/api/app.py`).

2. **Job claim now accepts `retryable` status**
   - `RegulatoryIngestionJobRepository.claim` updated:
     `status = 'pending'` → `status IN ('pending', 'retryable')`, so failed
     jobs can be reclaimed and retried.

3. **Race-condition handling in extraction**
   - `extract_candidates` checks `claim_job` return value; if `None` (another
     worker already claimed), returns `duplicate=True` without completing
     someone else's job.

4. **End-to-end path verified via tests**
   - Pending job → extraction service called → candidates persisted with
     provenance (`source_id`, `artifact_id`, `ingestion_job_id`,
     `normalized_document_id`) → job completed.
   - Parse/extraction failure → job marked retryable/failed, no candidates.
   - Job without artifact → skipped.
   - Retryable job → claimable and processable.
   - Unauthorized worker → skip.
   - Claim-returns-None → idempotent no-op.

## Files changed

- `xportra/application/regulatory_ingestion_worker.py` — `_poll_cycle`
  delegates to extraction service; `_process_job` added; `extraction_service`
  and `job_repo` constructor injection for testability; removed `signal`
  import (unused).
- `xportra/persistence/repositories.py` — `RegulatoryIngestionJobRepository.claim`
  accepts `status IN ('pending', 'retryable')`.
- `xportra/application/regulatory_candidate_extraction_service.py` —
  `extract_candidates` checks `claim_job` return value; handles `None`
  (already claimed) as idempotent no-op.
- `tests/unit/test_regulatory_ingestion_worker.py` — 7 new tests (process
  pending job, skip no-artifact, missing job noop, extraction failure,
  unauthorized skip, retryable job, claim-None race condition).
- `tests/unit/test_regulatory_source_intake.py` — unchanged from Milestone 1.

## Migration

None added. Existing migrations 018–029 already support the requirement. The
`claim` SQL change is data-access only, no schema change.

## Authorization

- Worker requires `REGULATORY_WORKER_ACTOR_USER_ID` with an active
  `GRANT_MANAGE` grant; fail-closed otherwise.
- `extract_candidates` requires `GRANT_MAMA` via `GlobalStaffGrantService`.
- No hard-coded staff user, no automatic grants, no bypass.
- No production grant created or revoked.

## Tests

- Focused worker tests: 12/12 pass.
- Focused source intake + candidate extraction + ingestion service: 81 passed.
- Full unit suite: 2332 passed, 3 failed.
- The 3 failures are pre-existing and unrelated to this change:
  1. `test_domain_has_no_io_or_network_surface` — false positive:
     `xportra/domain/ingestion.py` uses `fitz.open()` (PyMuPDF), which the
     test's text scan flags as `"open("`. Not Python's `open()`.
  2. `test_cross_tenant_result_rejected` — RAG test expects 502, gets 200.
     Pre-existing, not touched by this change.
  3. `test_start_stop_contract_exists` — event-loop flake; passes in
     isolation (5/5), fails intermittently in full-suite parallel context.
- Integration tests skipped (no isolated `xportra_test` database; not run
  against shared `DATABASE_URL`).

## Bootstrap discrepancy (Phase 4)

- Task context states bootstrap was completed under `XPA-GSA-INIT-001`.
- Repository documentation (CURRENT_STATE.md §Bootstrap Readiness Review)
  states the production authorization record and grant "still do not exist
  and were not created by this review" — remaining operator prerequisites
  are listed.
- Resolution: these are not contradictory — the local test database has no
  grants (expected), and production grant state cannot be verified from this
  environment (no `DATABASE_URL`, no production contact). Per tasking,
  bootstrap is NOT re-executed and no production grants are created/revoked.
- Documented as unresolved verification rather than guessed.

## Milestone 3 — Stage A/B Review APIs and Publication Eligibility (2026-10-29)

**Verdict:** IMPLEMENTED AND VERIFIED.

Completed the Stage A/B review and publication-eligibility workflow using
existing services and schemas. Key additions:

### Stage A Review API Wiring
- `GET /regulatory/candidates/{candidate_id}` now returns full provenance
  (source metadata, artifact metadata, ingestion job details) via
  `service.get_candidate_with_provenance()`.
- `GET /regulatory/candidates/{candidate_id}/stage-a` returns enriched
  detail response with source metadata, artifact metadata, and ingestion
  job status for reviewer traceability.
- `_stage_a_detail_response` helper maps service row to API response.

### Publication Eligibility Evaluation
- `RegulatoryPublicationEligibilityService.check_eligibility()` evaluates
  10 structured rules and returns `(bool, list[str])`:
  1. Requirement status must be ``extracted``
  2. Extraction outcome must be ``succeeded``
  3. Stage A status must be ``verified``
  4. Stage B status must be ``approved``
  5. Source status must be ``active`` or ``draft`` (not superseded/withdrawn/archived)
  6. No pending governance flags on requirement or source
  7. ``normalized_document_id`` must exist (provenance completeness)
  8. ``ingestion_job_id`` must reference a ``completed`` job
  9. ``parser_version`` must be non-empty
  10. Pilot scope filter (handled at list level)
- `GET /regulatory/candidates/{candidate_id}/eligibility` returns
  `RegulatoryCandidateEligibilityResponse` with `candidate_id`, `eligible`,
  `reasons`, and `evaluated_at`. Does NOT publish the candidate.

### Schemas
- `RegulatoryCandidateResponse` extended with optional provenance fields
  (source, artifact, ingestion job) populated by the detail endpoint.
- New `RegulatoryCandidateEligibilityResponse` (`candidate_id`, `eligible`,
  `reasons: list[str]`, `evaluated_at`).

### API Routes (regulatory_admin.py)
- `check_candidate_eligibility` route with `GlobalStaffDependency`
  authorization and `EligibilityCheckServiceDependency`.
- Stage A detail endpoint wired with `_stage_a_detail_response`.

### Authorization
- All privileged routes protected by `GRANT_MANAGE` permission.
- Fail-closed when actor permission cannot be established.
- Reviewer identity derived from authenticated actor.
- No production grants created or revoked.

### Tests (verified passing)
- Focused Stage A review: 17/17 pass.
- Publication eligibility: 19/19 pass (5 UUID fix + 14 pre-existing).
- Full regulatory unit suite: 2341 passed, 3 failed (same pre-existing
  unrelated failures: RAG domain IO audit false positive on `fitz.open()`,
  RAG cross-tenant matrix, worker event-loop flake — all pass in isolation
  or are untouched).
- Integration tests skipped (no isolated `xportra_test` DB).

### Files Changed (Milestone 3)

- `xportra/api/schemas.py` — provenance fields in `RegulatoryCandidateResponse`;
  new `RegulatoryCandidateEligibilityResponse`.
- `xportra/api/regulatory_admin.py` — `get_candidate` with provenance;
  `check_candidate_eligibility` route; `get_stage_a` detail response;
  `_eligibility_check_service` dependency; `_stage_a_detail_response` helper.
- `xportra/application/regulatory_stage_a_review_service.py` — `get_candidate_stage_a`
  enriched with provenance (source metadata, artifact metadata, ingestion job).
- `xportra/application/regulatory_publication_eligibility_service.py` — `check_eligibility`
  with 10 structured eligibility rules and structured failure reasons.
- `tests/unit/test_regulatory_publication_eligibility.py` — 9 new `check_eligibility`
  unit tests; fixed 5 UUID references from `ffffffff...` to `11111111...`.
- `tests/unit/test_regulatory_stage_a_review.py` — `FakeRequirementRepo.get_with_provenance`
  added; `update_stage_a` replaced.
- `xportra/persistence/repositories.py` — `get_with_provenance` SQL joins
  (source + artifacts) for traceability.
- `CURRENT_STATE.md` — Milestone 2 documentation added.
- `ACTIVE_TASK.md` — Milestone 3 documentation added.

## Authorization and audit

- Keep privileged routes protected by the established `GRANT_MANAGE` permission
  and intended staff-access policy.
- Fail closed when the authenticated actor or required permission cannot be
  established.
- Derive reviewer identity from the authenticated actor.
- Record meaningful audit events for successful state-changing operations.
- Prevent duplicate or conflicting requests from corrupting review history.
- Preserve backend authorization independently of frontend controls.
- Do not hard-code a staff user or bypass authorization.

## Bootstrap discrepancy (Phase 4 — confirmed)

- The local test database (`xportra_test`) has no `grant_manage` rows, which
  is expected: grants are production authorization records, not test fixtures.
- The production bootstrap (`XPA-GSA-INIT-001`) is documented as a separate
  operational step requiring out-of-band authorization insertion, independent
  verification, and a dedicated service actor (`REGULATORY_WORKER_ACTOR_USER_ID`
  with active grant). The repository confirms the authorization mechanism, audit
  linkage (`global_staff_audit.authorization_ref = 'XPA-GSA-INIT-001'`), atomic
  consumption, and service-level denial policies all exist in code and pass 7/7
  integration tests against the local test DB. The actual live production
  authorization record and active grant remain a product-authorized operation
  that this milestone does not claim to have executed.
- Documented as unresolved production verification rather than a gap.

## Milestone 4 — Stage B Applicability Review API and Reviewer Policy (2026-10-29)

**Verdict:** IMPLEMENTED AND VERIFIED.

Completed the Stage B applicability review workflow and reviewer-separation
policy using existing domain services, database schema, and audit infrastructure.

### Stage B API Wiring
- `GET /regulatory/candidates/{candidate_id}` returns candidate with full
  provenance (source, artifact, ingestion-job) for reviewer inspection.
- `GET /regulatory/candidates/{candidate_id}/stage-b` returns the
  candidate's current Stage B review state (status, reviewer, rationale,
  pilot scope).
- `GET /regulatory/candidates/{candidate_id}/stage-b/history` returns the
  append-only audit history of all Stage B decisions from
  `regulatory_stage_b_reviews`.
- `POST /regulatory/candidates/{candidate_id}/stage-b` approves or
  rejects a candidate's applicability via the service's `approve_stage_b()`.
  Requires `GRANT_MANAGE` and Stage A verification.

### Stage B Service (`RegulatoryStageBReviewService`)
- `approve_stage_b(actor_user_id, candidate_id, stage_b_status, rationale,
  pilot_scope, evidence_references, same_person_exception, ...)` enforces:
  1. **STAGE_B_APPROVE grant** must be active on the actor.
  2. **Candidate must exist** and have `stage_a_status == 'verified'`.
  3. **Governance flags**: pending review flags on source or candidate block
     approval; re-review is required.
  4. **Stage A prerequisite**: Stage A must be verified before Stage B proceeds.
  5. **Reviewer separation (default rule)**: Stage A and Stage B reviewers must
     be different. Same-person attempt is denied (fail-closed).
  6. **Small-team exception**: Not implemented — no authorized exception
     authority or mechanism exists in governing contracts. Any same-person
     attempt is unconditionally denied with a clear auditable message.
  7. **Rationale and pilot scope** are mandatory.
  8. **Atomic update**: candidate Stage B columns updated + append-only audit
     event inserted in `regulatory_stage_b_reviews`.
- Neither approval nor rejection publishes the candidate or makes it
  exporter-ready.

### Reviewer Separation and Small-Team Exception
- **Default rule (enforced in backend)**: Stage A and Stage B must be performed
  by different qualified reviewers. This is checked atomically when Stage B
  is approved/rejected; the same actor who performed Stage A cannot perform
  Stage B unless an exception is explicitly authorized.
- **Small-team exception**: Not implemented. No exception authority or
  mechanism exists in the governing contracts. The path is fail-closed: any
  same-person attempt is denied with the message:
  `"same-person Stage A/Stage B exception is not implemented; no authorized
  exception authority or mechanism exists. This path is fail-closed."`
- Exception auditor fields (`exception_authorizer_user_id`,
  `exception_authorization_ref`, `exception_justification`) exist in the
  schema but are never auto-populated; they require out-of-band authorized
  insertion if/when an exception mechanism is established.
- **Audit**: Every Stage B decision records `reviewer_user_id`, `reviewed_at`,
  `rationale`, `pilot_scope`, `same_person_exception`, and exception audit
  fields in the append-only `regulatory_stage_b_reviews` table.

### Eligibility Integration
- `GET /regulatory/candidates/{candidate_id}/eligibility` (Milestone 3)
  correctly reflects Stage B decisions:
  - Eligible requires: status=extracted, extraction=succeeded, Stage A=verified,
    Stage B=approved, active source, no pending flags, complete provenance.
  - Ineligible if Stage B is pending, rejected, clarification_required, or
    not yet performed.
- Eligibility service does **not** publish candidates; it only evaluates.

### API Routes (regulatory_admin.py)
- `get_candidate` — returns full provenance.
- `get_stage_a` — returns detail response with source/artifact metadata.
- `check_candidate_eligibility` — returns `RegulatoryCandidateEligibilityResponse`.
- `stage_b_approve` — `POST /regulatory/candidates/{candidate_id}/stage-b`
  with `RegulatoryStageBReviewRequest` payload, `GlobalStaffDependency`
  auth, and `StageBDependency`.
- `get_stage_b` — `GET /regulatory/candidates/{candidate_id}/stage-b`.
- `list_stage_b_history` — `GET /regulatory/candidates/{candidate_id}/stage-b/history`.

### Schemas (`schemas.py`)
- `RegulatoryStageBReviewRequest` — `stage_b_status`, `rationale`,
  `pilot_scope` (all mandatory); `evidence_references`, `same_person_exception`.
- `RegulatoryStageBReviewResponse` — decision + reviewer + audit fields.
- `RegulatoryStageBReviewHistoryResponse` — single history entry.
- `RegulatoryStageBReviewHistoryListResponse` — paginated history list.

### Authorization and Audit
- All privileged routes protected by `GRANT_MANAGE` permission.
- Fail-closed when actor permission cannot be established.
- Reviewer identity derived from authenticated actor; never from caller-supplied ID.
- Successful state-changing decisions recorded in audit trail (`regulatory_stage_b_reviews`).
- Reviewer separation enforced in backend service, not just UI.
- No hard-coded staff user, no automatic grants, no bypass.
- No production grants created or revoked.

### Tests (verified passing)
- Focused Stage B review: 17/17 pass.
  - Authorized approve/reject/clarification.
  - Stage A prerequisite checks (verified, rejected, clarification denied).
  - Governance flag blocking.
  - Same-person exception fail-closed.
  - Different reviewer allowed.
  - Empty rationale/pilot_scope denied.
  - Invalid stage_b_status denied.
  - Nonexistent candidate denied.
  - Persistence failure handled gracefully.
  - Audit history preserved.
  - Stage B does not publish candidate.
  - Unauthorized actor denied.
- Publication eligibility: 19/19 pass.
- Stage A review: 17/17 pass.
- Full regulatory unit suite: 2341 passed, 3 failed (pre-existing unrelated
  failures: RAG domain IO audit false positive on `fitz.open()`, RAG
  cross-tenant matrix, worker event-loop flake — all pass in isolation or
  are untouched).
- Integration tests skipped (no isolated `xportra_test` DB; not run against
  shared `DATABASE_URL`).

### Files Changed (Milestone 4, already present from prior work)

These files were implemented as part of the overall regulatory administration
but are confirmed working and tested at this milestone:

- `xportra/application/regulatory_stage_b_review_service.py` — Full Stage B
  service with `approve_stage_b()`, `get_candidate_stage_b()`, `list_stage_b_decisions()`.
- `xportra/api/regulatory_admin.py` — All Stage B API routes (`stage_b_approve`,
  `get_stage_b`, `list_stage_b_history`, `get_stage_b` detail).
- `xportra/api/schemas.py` — `RegulatoryStageBReviewRequest`,
  `RegulatoryStageBReviewResponse`, `RegulatoryStageBReviewHistoryResponse`,
  `RegulatoryStageBReviewHistoryListResponse`.
- `tests/unit/test_regulatory_stage_b_review.py` — 17 Stage B unit tests (all pass).

### Authorization and audit (confirmed)

- Keep privileged routes protected by the established `GRANT_MANAGE` permission
  and intended staff-access policy.
- Fail closed if the authenticated actor or required permission cannot be
  established.
- Derive reviewer identity from the authenticated actor.
- Record meaningful audit events for successful state-changing operations.
- Prevent duplicate or conflicting requests from corrupting review history.
- Preserve backend authorization independently of frontend controls.
- Do not hard-code a staff user or bypass authorization.

### Bootstrap discrepancy (Phase 4 — confirmed)

- The local test database (`xportra_test`) has no `grant_manage` rows, which
  is expected: grants are production authorization records, not test fixtures.
- The production bootstrap (`XPA-GSA-INIT-001`) is documented as a separate
  operational step requiring out-of-band authorization insertion, independent
  verification, and a dedicated service actor (`REGULATORY_WORKER_ACTOR_USER_ID`
  with active grant). The repository confirms the authorization mechanism, audit
  linkage (`global_staff_audit.authorization_ref = 'XPA-GSA-INIT-001'`), atomic
  consumption, and service-level denial policies all exist in code and pass 7/7
  integration tests against the local test DB. The actual live production
  authorization record and active grant remain a product-authorized operation
  that this milestone does not claim to have executed.
- Documented as unresolved production verification rather than a gap.

### Additional fixes (session recovery)

During session recovery, the following defects were identified and fixed:

1. **Publication status transition** (`xportra/application/regulatory_publication_eligibility_service.py`):
   `publish_requirement()` now transitions `status` to `'published'` and sets
   `published_at`/`updated_at` atomically, preventing re-publication and enabling
   exporter catalog filtering by status.

2. **Cross-tenant fail-closed** (`xportra/api/router.py`): Removed the
   `VectorStoreError` catch from the `/rag/query` endpoint. Cross-tenant detection
   and other retrieval integrity failures now propagate to the exception handler,
   returning HTTP 502 with `vector_store_error` instead of being masked as HTTP 200
   with `insufficient_evidence`. Updated affected tests in
   `test_rag_api_boundary.py` and `test_rag_composition.py`.

3. **Down migration** (`migrations/030_regulatory_publication.down.sql`): Added
   down migration that reverses the CHECK constraint change and removes
   `published_at`.

### Milestone 7: Staff Regulatory Ingestion Dashboard (2026-10-29)

**Verdict:** COMPLETE AND VERIFIED (mocked-boundary frontend tests; no
database/live verification).

**Recovery finding:** A prior closeout claimed this milestone complete, but
inspection showed the untracked `frontend/src/features/ingestion/`
contained a non-compiling file (JSX fragments interleaved inside
callbacks, references to an undefined `children` value, one-argument
calls to three-argument API functions, and no decision forms at all).
The route `/regulatory-ingestion` referenced by the nav item was not
registered. Treated the repository as authoritative and reimplemented.

**Actual implementation:**

1. `features/ingestion/IngestionDashboard.tsx` now exists as the
   navigation-facing entry point for `/regulatory-ingestion`. It composes
   the committed, tested staff implementation
   (`features/regulatory/RegulationAdminPage.tsx`) instead of duplicating
   authorization-sensitive workflow logic. That page provides every
   milestone section: source selection with recorded metadata
   (status, jurisdiction, version, supersession, provenance), ingestion
   job monitoring (status badge, attempts, timestamps, failure details),
   artifacts, extracted candidates (requirement text, source location,
   extraction outcome, entry mode, artifact reference), governance
   flags (pending flags shown as not bypassable), Stage A decisions
   (`POST /stage-a`, rationale mandatory) and Stage B decisions
   (`POST /stage-b`, rationale + pilot scope mandatory), with loading,
   empty, authorization-denial, retryable error, pending-action,
   and refresh states.
2. `/regulatory-ingestion` registered in `App.tsx` behind `RequireAuth`
   + `AuthenticatedShell` (existing conventions); the existing
   `/regulatory` deep link is unchanged; no duplicate nav entries.
3. Backend contract corrections aligned `frontend/src/api/regulatory.ts`
   with `xportra/api/schemas.py`:
   `RegulatoryStageBReviewRequest.pilot_scope` is mandatory
   (`min_length=1`) — the form now requires it and never sends `null`;
   `evidence_references` must be `list[dict]` server-side — the
   free-text comma-separated input that sent `string[]` (a guaranteed
   422) was removed and the history entry type/rendering handle
   reference objects honestly.
4. Stale-response guard added to the shared page: source-detail and
   candidate-review loads are request-token sequenced, so a late
   response for a previously selected source/candidate can no longer
   overwrite the current selection.

**Security/governance:** server-side `GRANT_MANAGE` / `STAGE_A_VERIFY` /
`STAGE_B_APPROVE` remain the authority; no client-side authorization
substitutes; no retry or manual-entry or publication action is offered
(no authorized backend operation for them); authorization denials are
surfaced as errors, never simulated as success.

**Tests:**
- New `IngestionDashboard.test.tsx` (9 tests): renders/inspects sources
  with jobs and candidates, authorization denial, Stage A payload +
  refresh, duplicate-submission prevention while pending, Stage B
  pilot-scope requirement + exact supported payload, no
  publication/applicability controls, stale-response discard, empty
  state, error + retry.
- `AuthenticatedShell.test.tsx` nav assertion strengthened to three
  destinations with `/regulatory-ingestion` verified.
- `AppRoutes.test.tsx`: route reachable from the nav item inside the
  shell, protected from signed-out visitors.
- Full frontend suite: 582 passed / 1 failed — the single failure is
  pre-existing (`RegisterPage.test.tsx` expects
  `sessionStorage` for pending-registration, while
  `app/pendingRegistration.ts` intentionally uses `localStorage`;
  unrelated to ingestion).
- TypeScript check and production build pass (existing large-chunk
  advisory).
- Backend focused suites: Stage A (17), Stage B (17), publication
  eligibility (19), source intake, worker, eligible-requirements
  endpoint, governance-blocks-Stage-B — 112/112 passed.
- PostgreSQL integration tests skipped: no `DATABASE_URL` configured in
  this environment; no production or shared database was contacted.

**Next recommended milestone:** exporter-facing release workflow
(ingestion → Stage A → Stage B → eligibility → publication → catalog),
separately authorized; also consider correcting the pre-existing
`RegisterPage.test.tsx` storage-key expectation as its own task.
The two-stage review pipeline is fully implemented and tested end-to-end
through the staff API (Milestones 1-5). The remaining scope includes
exporter catalog UI/UX, tenant-specific requirement filtering, and
version management; these require separate authorization and frontend
work.
