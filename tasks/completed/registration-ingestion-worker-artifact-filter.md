# Registration Ingestion Worker Artifact Filter

**Status:** Complete (2026-11-04).

## Authorization and context

This narrow fix is explicitly assigned by the user and follows the
artifact-optional registration-job contract in ADR-0022. A registration
placeholder has no artifact and must remain pending until an artifact-bound
job is created.

## Scope and acceptance criteria

- Polling reserves only pending/retryable jobs with a non-null
  `artifact_id`, preserving oldest-first ordering, row locking, and
  `SKIP LOCKED`.
- Tests prove placeholders are skipped and remain pending, valid artifact
  jobs are selected without placeholder starvation, and retryable jobs
  remain selectable.
- Worker startup logs a useful diagnostic when worker identity configuration
  is missing or invalid, without logging configuration values or secrets.
- Focused tests pass; only files belonging to this fix are staged. No push.

## Verification

- `uv run --no-sync python -m pytest tests/unit/test_regulatory_ingestion_worker.py tests/unit/test_render_production_wiring.py -q`
  — 40 passed, including 2 startup-configuration subtests.
- The direct system Python test attempt could not collect tests because its
  installation lacks the declared `psycopg-binary` adapter; the project
  virtual environment passed the focused suite.
- No push was performed.
