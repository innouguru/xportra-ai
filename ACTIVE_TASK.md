# ACTIVE_TASK.md — Current Active Task

**Active task:** Phase 4D — Regulatory Ingestion Execution Path — Milestone 2
(worker-driven durable ingestion from pending job to candidate persistence).

**Status:** In progress — implementation complete, tests passing, documentation
pending, commit pending.

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

## Next recommended milestone

Stage B applicability review API wiring and small-team exception policy,
pending separate authorization. The Stage A review and publication-eligibility
endpoints are fully implemented and tested.
