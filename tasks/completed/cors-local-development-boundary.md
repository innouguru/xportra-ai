# Task: Secure CORS Boundary for Local Frontend ↔ API Development

**Status:** Complete (2026-09-27). Verified per acceptance
criteria below; see `ACTIVE_TASK.md` (now closed) and
`CURRENT_STATE.md`.

## Objective

Unblock local frontend integration (`OPTIONS
/compliance/workflows/start` currently 405s) with a
secure, explicit CORS boundary: local Vite origins in
development/test, explicit `CORS_ALLOWED_ORIGINS`
configuration only in production, wildcards forbidden
everywhere.

## Scope

1. CORS origin/method/header resolution in
   `xportra/api/runtime.py` following existing
   environment conventions, with startup validation.
2. `CORSMiddleware` wiring in `xportra/api/app.py`
   (no credentials support; auth rides on headers).
3. `CORS_ALLOWED_ORIGINS` documented in `.env.example`
   and `docs/architecture/environment-schema.md`.
4. Focused tests in `tests/unit/test_cors_boundary.py`.
5. State updates (`ACTIVE_TASK.md`, `CURRENT_STATE.md`).

## Constraints

- No `allow_origins=["*"]`, no auth/tenant-isolation
  changes, no frontend changes, no workflow/compliance/
  evidence/conversation/LLM behavior changes, no new
  configuration framework, Phase 10.1 boundary preserved.

## Acceptance Criteria

- [x] Allowed local origin preflights successfully.
- [x] Disallowed origins receive no permissive headers.
- [x] Production requires explicit configuration;
      wildcards rejected at startup.
- [x] Focused, related, and full suites pass.
- [x] Manual preflight check no longer returns 405.
