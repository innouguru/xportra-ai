# Production-Readiness Audit — Complete

Implementation audit across sixteen production
concerns. **No code defects found; no code changed.**
Verdict: no code-level blocker remains; the version is
responsibly deployable once the operational
prerequisites below are completed.

## Production blockers

None. Every candidate blocker verified safe:

- Development tenant mechanism (`X-Development-Tenant-ID`,
  `xportra/dev/bootstrap.py`) is refused in production
  before any mutation or connection
  (`dependencies.py`, `runtime.py`, bootstrap guard;
  covered by production-security tests).
- No secrets tracked (`.env` ignored and absent from
  the index; secret-pattern scan clean).
- Auth pins HS256 with required exp/sub/audience and
  optional issuer; tenant selection restricted to the
  caller's active memberships; unknown roles denied;
  every boundary tested cross-tenant as
  indistinguishable 404.
- Error surface strips 5xx detail in production, never
  serves tracebacks or docs, and pins debug off at
  startup (missing secrets/DSN fail fast at import).
- CORS is explicit-origin only with wildcards rejected
  at startup, credentials never enabled, methods and
  headers allow-listed; production fails closed with no
  browser access when unconfigured.
- Evidence path validates type/size server-side with a
  schema-level base64 bound, composes storage keys
  server-side (no overwrite, no traversal, private
  bucket + signed URLs), compensates storage on DB
  failure, and enforces authoritative terminal state.
- Logging emits identifiers/latency only — no secrets,
  document contents, prompts, or chain-of-thought.

## Non-blocking limitations (accepted for v1)

- No CI workflow (`.github/` absent); no Dockerfile.
- No connection pooling (short-lived psycopg
  connections per operation — correct, not pooled).
- No structured-observability pipeline in app code
  (stdlib logging only; `LOG_LEVEL` documented but not
  consumed by application code).
- No JSON body cap beyond the upload base64 field
  bound (rely on reverse-proxy limits).
- Token lives in frontend memory only (reload signs
  out — secure default, no persistent login).
- Untracked local artifacts present
  (`xportra-ui-review.*`, `frontend/t5.txt`,
  `test-output.txt`, `.freebuff/`, `uv.lock`,
  CORS scratch test/task) — not committed; local
  cleanup recommended, not performed here.
- Frontend lockfile absent; backend `uv.lock` exists
  but untracked (pin ranges in `pyproject.toml` only).

## Deployment prerequisites (operational, no code changes)

- Backend: `uvicorn xportra.api.app:app` with
  `APP_ENV=production`, `APP_DEBUG=false`,
  `SUPABASE_JWT_SECRET`, `DATABASE_URL`,
  `CORS_ALLOWED_ORIGINS=https://<app-domain>`.
- Migrations: apply `migrations/001`–`013` in order via
  `psql` against Supabase Postgres (deterministic SQL;
  down-migrations exist; 001 is not re-runnable, later
  files are guarded).
- Frontend: `npm run build` with
  `VITE_API_BASE_URL=https://<api-domain>`; serve `dist/`
  statically (Node 20+ for build only).
- Supabase: Auth project (JWT secret/audience),
  Postgres database, one private Storage bucket
  (`tenant-evidence` default) with service-role key
  server-side only.
- Qdrant + OpenRouter + embeddings required only for
  analysis/conversational/RAG paths; shipment,
  workflow, evidence-register, listing, and report
  reads run without them (each dependency fails
  closed with 503/409/502 per path, never partial
  writes).
- Smoke verification: TCP/port check plus an
  authenticated `GET /compliance/shipments` (401
  without credentials proves routing/auth live; 200
  with a member token proves DB + tenancy).
- No `/health` endpoint exists; no Docker image;
  backups/retention are operator-owned.

## Recommended future work (outside v1)

CI workflow, connection pooling, structured logging
pipeline, request body caps, persistent login, health
endpoint, tracked lockfiles, backup/restore runbook,
load testing.

## Verification

- Focused production/security/auth suites: 77 passed
  + 24 subtests.
- Full backend: 2039 passed + 61 subtests, 0 failures.
- Frontend untouched (no run per task scope; last
  verified 64 files / 439 tests, `tsc` clean, build
  succeeds).
- Integration: 51 skipped (no `DATABASE_URL`; no live
  coverage claimed). No packages installed.
