# Phase 8.5 — Stored-Path HTTP Exposure (Completed 2026-09-24)

Thin FastAPI exposure of the 8.4 stored-path operations:
finalize-from-latest (201), stored package read, stored
report read — review-gated, tenant-safe, terminal-
enforcing, with the existing error/status mapping
reused unchanged. Mirrors `ACTIVE_TASK.md`; full record
in `docs/phases/phase-8-5-stored-path-http-exposure.md`.

## Scope delivered

- `POST /compliance/workflows/finalize`,
  `POST /compliance/workflows/package`,
  `GET /compliance/reports/{report_id}`.
- Container store field + wiring + passthrough +
  503 dependency; analyze passes the optional store.
- Additive schemas; no compound endpoint; history
  endpoint unchanged.
- `tests/unit/test_compliance_stored_api.py`: 25 tests.

## Acceptance

Focused 25/25; Phase 8.1–8.4 + 7.1–7.5 + Phase 6 +
Phase 2–5 regressions pass; full suite 1740 passed +
44 skipped (gated), 0 failures. No prior test weakened.
No UI or evaluation built. No live execution claimed.
