# Phase 8.2 — HTTP Endpoint Exposure (Completed 2026-09-24)

Thin FastAPI adapter (13 endpoints) over the
stateless-safe 8.1 use cases, with existing auth,
additive permissions, centralized type-based error
mapping, stable schemas, and a locked OpenAPI contract.
Mirrors `ACTIVE_TASK.md`; full record in
`docs/phases/phase-8-2-http-endpoint-exposure.md`.

## Scope delivered

- `xportra/api/compliance.py`: 13 thin handlers (one
  use case each); per-request service construction.
- `authorization.py`: 2 additive owner-only permissions.
- `errors.py`: centralized app-error → HTTP mapping.
- `schemas.py`: compliance request/response models.
- `app.py`: router include.
- Application wire translation: UUID coercion for
  JSON-transported case views, provenance, and summary
  scope (mechanical, in-session behavior unchanged).
- `tests/unit/test_compliance_api.py`: 29 tests.

## Acceptance

Focused 29/29; Phase 8.1 (31) + 7.1–7.5 (151) +
Phase 6 (247) + Phase 2–5 regressions pass; full suite
1647 passed + 37 skipped (gated), 0 failures. No prior
test weakened. Finalize/package/report endpoints
deliberately unexposed pending the reported
result-transfer/store gap (no fake persistence). No UI
or evaluation built.
