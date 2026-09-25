# Phase 10.1 — Production Security & Configuration Hardening

> Scope record (2026-09-25). Implementation state is recorded in
> `CURRENT_STATE.md`; this document states the approved scope and the
> audit baseline. Hardening phase, not a feature phase.

## Approved scope (REQUIREMENTS.md R-10.1)

1. Production configuration boundary (R-10.1.1).
2. Authentication/authorization security audit (R-10.1.2).
3. Tenant-isolation security matrix (R-10.1.3).
4. Production error-surface hardening (R-10.1.4).
5. Logging/sensitive-data audit (R-10.1.5).
6. HTTP/API security configuration (R-10.1.6).
7. Secrets/configuration hygiene (R-10.1.7).
8. Security regression tests (R-10.1.8).

Explicitly out of scope (R-10.1.9): deployment, containers,
orchestration, cloud infra, CI/CD redesign, backups, DR, performance,
load testing, Qdrant hosting, provider migration, observability
redesign, dashboards, notifications, frontend features, product
workflows, compliance rules, LLM behavior, deterministic-authority
changes, reopening/versioning finalized assessments.

## Audit baseline (pre-implementation, 2026-09-25)

- Authenticated identity is authoritative: `get_member_context`
  resolves tenant/role from server-side membership
  (`TenantMembershipResolver`); `X-Xportra-Tenant-ID` is constrained to
  memberships (non-member → 403; multi-membership requires selection).
- Request bodies carry no trusted tenant identity: create/read request
  schemas exclude `tenant_id` (`extra="forbid"`); the workflow record's
  `tenant_id` is re-validated per call (`_owned_workflow` /
  `ensure_tenant_match`); stored reads are repository tenant-scoped.
- Every compliance and Phase 1 route enforces `require_permission`;
  member role is limited to reads + evidence recording/association;
  workflow progression and analysis are owner-only.
- Error handlers return generic messages (no tracebacks/secrets);
  unexpected exceptions log server-side and return `internal_error`.
- Logging carries model/collection names, latency, and error type names
  only; `LLMSettings.api_key` and `RAGInfrastructureConfig.llm_settings`
  are excluded from repr.
- `.env` is untracked and git-ignored; `.env.example` holds placeholders
  only.

## Hardening gaps accepted for implementation (ADR-0008)

G1 dev header silently ignored (not rejected) when `Authorization` is
also present in production. G2 interactive docs/OpenAPI served in
production. G3 no production startup validation (secrets, debug off).
G4 5xx response details can embed driver/provider internals. G5
exact-duplicate definitions in `dependencies.py` / `schemas.py`. G6
scattered inline `APP_ENV` predicates. G7 no baseline security headers.
G8 `.env.example` lacks production-safety notes.

## Verification

Per the task file: new focused tests, existing security/auth/tenant
tests, full backend regression suite. No live Postgres/Qdrant/OpenRouter
claims unless executed.

## Implementation record (2026-09-25)

Fixes (all confined to `xportra/api/` plus `.env.example` comments;
no domain/application/persistence/frontend change):

- New `xportra/api/runtime.py`: single `APP_ENV` predicate,
  unknown-value rejection, `APP_DEBUG` parsing, and production startup
  validation (`SUPABASE_JWT_SECRET` + `DATABASE_URL` required,
  `APP_DEBUG` must be off/unset) applied on the environment-composed
  path.
- `app.py`: docs/redoc/OpenAPI disabled in production, `debug=False`
  pinned, minimal security-headers middleware
  (`nosniff` / `DENY` / `no-referrer`), production validation wired.
- `dependencies.py`: dev header rejected unconditionally in production
  (G1 — including alongside `Authorization`) in `get_member_context`
  and `get_request_actor`; inline env checks centralized; exact
  duplicate `get_result_store` removed.
- `errors.py`: 5xx responses strip dynamic detail in production (G4);
  stable codes and all 4xx structured semantics preserved.
- `schemas.py`: exact duplicate `FinalPackageResponse` /
  `FinalizeWorkflowResponse` removed (behavior-neutral).
- `.env.example`: production-safety notes only; values unchanged.

Tests: `tests/unit/test_phase_10_1_production_security.py` — 44 tests
(+24 subtests) covering the R-10.1.1–R-10.1.8 matrix.

Results: focused 44/44 pass; related auth/API/compliance/stored/
boundary suites 217/217 pass; full suite 1784 passed + 44 skipped
(gated Postgres/Qdrant/OpenRouter-live, not executed), 0 failures.
Frontend untouched: no frontend tests or build required.
