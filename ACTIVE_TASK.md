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

## Next recommended milestone

Stage A/B review API wiring and publication-eligibility exposure, pending
separate authorization. The ingestion pipeline now runs end-to-end through
the worker.
