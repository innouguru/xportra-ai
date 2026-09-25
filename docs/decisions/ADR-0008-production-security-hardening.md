# ADR-0008: Production security & configuration hardening (Phase 10.1)

- Status: Accepted
- Date: 2026-09-25
- Scope: Phase 10.1 production security & configuration hardening

## Context

The Xportra AI API/application boundary (Phases 1.8–1.10, 8.x) already
enforces authenticated tenant identity, server-side membership
resolution, role checks, per-record tenant comparisons, and generic
error responses. Phase 10.1 audits that posture for production safety
without changing product behavior. The audit found the core design
sound and identified narrow hardening gaps:

1. The `APP_ENV == "production"` predicate is inlined in three places
   (`xportra/api/app.py`, twice in `xportra/api/dependencies.py`) with
   an implicit `development` default, and no startup validation pins
   down the production configuration.
2. The development tenant header is rejected in production on the
   unauthenticated path but silently ignored (rather than rejected)
   when `Authorization` is also present.
3. Interactive API documentation (`/docs`, `/redoc`, `/openapi.json`)
   is served unconditionally, including in production.
4. No baseline security response headers are set.
5. `InfrastructureError` response details derive from
   `sanitized_detail()`/stringified driver and provider exceptions,
   which can embed table/constraint names, SQL fragments, or endpoint
   URLs — acceptable for local diagnostics but not for production
   clients.
6. Exact-duplicate definitions exist in security-relevant files
   (`get_result_store` in `dependencies.py`; `FinalPackageResponse` /
   `FinalizeWorkflowResponse` in `schemas.py`).

## Decision

- Add `xportra/api/runtime.py`: the single `APP_ENV` predicate
  (`is_production_environment`), unknown-value rejection
  (`validate_app_env`, applied on every `create_app`), plus
  `validate_production_environment` (requires `SUPABASE_JWT_SECRET`
  and `DATABASE_URL`; rejects `APP_DEBUG=true`/unparseable), applied
  from `create_app` on the environment-composed path (no injected
  services) before serving in production. The existing
  `SupabaseAuthSettings.from_environment()` startup check is kept, so
  its exact error contract is unchanged.
- Reject `X-Development-Tenant-ID` unconditionally in production —
  including when `Authorization` is present — in both
  `get_member_context` and `get_request_actor`.
- Disable `docs_url`, `redoc_url`, and `openapi_url` in production.
- Add a minimal API-layer middleware setting `X-Content-Type-Options:
  nosniff`, `X-Frame-Options: DENY`, and `Referrer-Policy: no-referrer`.
- Strip 5xx response details in production (stable `code` preserved;
  4xx structured semantics, including readiness reasons, unchanged).
- Remove the exact-duplicate definitions (behavior-neutral).
- No authorization-architecture, persistence, domain, or frontend change.

## Alternatives considered

1. **Treat unset/unknown `APP_ENV` as production (fail closed by
   default).** Rejected: it would flip the local-development default
   and break existing dev/test behavior and tests; explicit production
   validation achieves the safety without changing the default.
2. **Redesign authorization or add a second tenant-isolation layer.**
   Rejected: the audit found the existing boundary sound; a second
   system would violate R-10.1.3.
3. **Full security-header suite (CSP, HSTS, TrustedHost).** Rejected as
   unjustified for the current architecture: no browser-served content
   policy to declare, TLS termination is deployment-owned (out of
   scope), and no host configuration exists to trust. The three minimal
   headers match the JSON-API surface.
4. **Strip all error details in every environment.** Rejected: local
   diagnostics rely on them; production-only stripping preserves both
   needs.

## Consequences

- Production boots fail fast on missing secrets or debug enabled.
- Production responses expose less surface; all behavior changes are
  confined to `APP_ENV=production` except the duplicate removal (exact)
  and the middleware headers (additive, environment-independent).
- Linked requirements: `REQUIREMENTS.md` R-10.1.
- Linked task: `tasks/active/phase-10-1-production-security-hardening.md`.
