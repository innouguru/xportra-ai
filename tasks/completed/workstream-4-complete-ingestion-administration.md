# Workstream 4 — Complete Existing Ingestion Administration

**Status:** Complete — acceptance verified 2026-11-05.

## Scope

Complete the existing authorized regulatory source ingestion dashboard,
including job progress, extraction outcomes, evidence inspection, safe
failure diagnostics, refresh, and eligible retries. Reuse existing APIs,
stored extraction history, and staff authorization.

## Focused decisions

- The user authorized a minimal read-only endpoint over existing
  Workstream 3 extraction-run records so empty and failed runs can be inspected
  by ingestion job without re-running extraction or adding storage.
- The user authorized a backward-compatible addition of the already-persisted
  processing stage and stage-update timestamp to the ingestion-job response
  schema. Worker behavior is unchanged.

## Boundaries

- No new storage or migration.
- No worker, extraction, retry-lifecycle, authorization-model, publication,
  or general dashboard redesign.
- Keep server-side `grant_manage` authorization authoritative.
- Preserve all unrelated pre-existing worktree changes; do not stage,
  commit, or push.

## Acceptance

- Show actual job/source/artifact identity, backend status/stage, recorded
  timestamps, honest progress, refresh failures, and retry eligibility.
- Expose persisted extraction outcome, candidate evidence, provenance, and
  safe diagnostics for each selected job, including runs with no candidates.
- Preserve staff authorization and avoid fabricated progress or evidence.
- Run focused backend/API and frontend regression tests; use only local
  `xportra_test` if PostgreSQL integration testing is required.

## Implementation and verification

- Added the staff-authorized read-only job extraction-history endpoint over
  existing extraction-run records, including runs with no candidate links.
- Exposed the existing processing-stage fields in the job response schema.
- Completed the source ingestion dashboard presentation for job state/stage,
  timestamps, artifact identity, extraction outcomes/evidence, failure
  diagnostics, stale refreshes, and guarded retry actions.
- Worker execution and database schema were not changed; no migration was
  added, and integration fixtures were cleaned up.

Verification results:

- `npm run test -- src/features/regulatory/RegulationAdminPage.test.tsx`
  (from `frontend`): 43 passed.
- `npm run lint` (from `frontend`): passed.
- `npm run build` (from `frontend`): passed; Vite reported the existing
  bundle-size warning for a chunk over 500 kB.
- `.venv\Scripts\python.exe -m pytest tests\unit\test_regulatory_job_response_contract.py tests\unit\test_regulatory_job_extraction_history_endpoint.py tests\unit\test_regulatory_job_retry_endpoint.py -q --tb=short`:
  10 passed; one Starlette/httpx deprecation warning.
- With process-scoped `DATABASE_URL=postgresql://postgres@127.0.0.1:5432/xportra_test`,
  `.venv\Scripts\python.exe -m pytest tests\integration\test_regulatory_candidate_extraction_postgresql.py -q --tb=short`:
  17 passed and 4 subtests passed.
- Verified the connection target was local PostgreSQL 18.6, database
  `xportra_test`, user `postgres`; required stage and extraction-history schema
  was present. Fixed test fixture identifiers were unused before the suite,
  and scoped fixture counts were zero after cleanup. No migration was needed.
- Nothing was staged, committed, or pushed. Unrelated pre-existing worktree
  modifications were preserved.
