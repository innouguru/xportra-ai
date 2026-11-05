# Workstream 1: Repair Existing Ingestion Execution

**Status:** Completed and verified against local `xportra_test`.

## Scope

Correct the existing regulatory ingestion execution path without changing its
in-process worker architecture, PostgreSQL job model, retry mechanism, or
migration 034 stage schema.

## Acceptance criteria

- Job selection and claim are atomic and use `SKIP LOCKED`.
- Completion, failure, and stage updates are fenced by the current claim.
- Expired claims recover to retryable/queued without stale owners completing
  or failing the recovered job.
- Existing normalized documents and candidates are handled idempotently and
  end in a consistent completed state.
- Only the known candidate-document-position uniqueness conflict is treated
  as an idempotent duplicate; real persistence failures are recorded and
  surfaced.
- Unit tests cover lifecycle, ownership, contention, retries, recovery,
  accurate stages, and persistence failures. PostgreSQL integration tests run
  only against the isolated local `xportra_test` database.
- Preserve pre-existing worktree changes. Do not stage, commit, or push.

## Implementation completed

- The worker atomically selects and claims the oldest pending/retryable job
  with an artifact using `FOR UPDATE SKIP LOCKED`.
- Claim fencing uses a monotonically increasing `started_at` token. Job
  attribution in `actor_user_id` is preserved, and stage/completion/failure
  updates require the current token.
- The worker renews leases during extraction; recovery uses the heartbeat
  timestamp and resets expired jobs to retryable/queued.
- Existing normalizations and candidates are reused idempotently. Missing
  candidates are still persisted when retrying partial work; only the
  document-position uniqueness conflict is treated as a duplicate.
- Failure diagnostics remain sanitized, persistence failures are surfaced,
  and startup logs a sanitized configuration reason.
- No new migration or architecture change was introduced. The pre-existing
  local edit to migration 034 was left untouched.

## Verification

- Focused worker, candidate-extraction, ingestion-service, and source-intake
  unit tests: **116 passed**.
- Workstream 1 PostgreSQL integration suite against local PostgreSQL 18.6,
  `127.0.0.1:5432/xportra_test`: **12 passed, 0 skipped**.
- The test process received an explicit loopback `DATABASE_URL`; `.env` was
  not read or modified for the test connection.
- Repository migration check returned **0 missing objects**. Existing
  migrations 010, 012, 013, and 034 were missing and were applied to this
  local test database in order using `psql -v ON_ERROR_STOP=1 -f`.
- Existing table row counts matched their pre-test baseline after cleanup;
  test fixture rows were absent after the run. The added tables from 010,
  012, and 013 remain empty.
- Modified Python files compile successfully.
- Git status and diffs were inspected. No files were staged, committed, or
  pushed.
