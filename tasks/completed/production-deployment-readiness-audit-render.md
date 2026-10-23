# Production Deployment Readiness Audit (Render-style Python web service) — Complete

Read-only audit, 2026-10-08. No application code changed, no dependencies
added, no deployment performed, no external service called, no secret values
read or printed. Supabase production state per task brief taken as given
(migrations 002–013 applied, `xportra-production` tenant, Auth user + mapping +
owner membership, RLS intentionally disabled, private `tenant-evidence` bucket
with 10 MB / MIME policy) and not re-verified here.

## 1. Deployment target assumptions

- Render-style Python web service: single long-lived web process, HTTP on a
  platform-assigned `$PORT`, config exclusively via environment variables,
  ephemeral local filesystem, HTTPS terminated by the platform, TCP/HTTP
  health check against one path, stateless instances (no shared disk).
- Backend: Python 3.13 (`pyproject.toml` `requires-python >=3.13,<3.14`),
  dependencies `fastapi`, `uvicorn[standard]`, `httpx`, `psycopg[binary]`,
  `pyjwt`, `qdrant-client`, `sentence-transformers` — all already declared.
- Frontend: static Vite build (`dist/`), no SSR, configured at build time.

## 2. Backend start command

- Import path: `xportra.api.app:app` (`xportra/api/app.py`, factory
  `create_app()`, module-level `app = create_app()`).
- Production ASGI command (no Procfile / render.yaml / Dockerfile exists —
  the platform start command must be supplied at deploy time):
  `uvicorn xportra.api.app:app --host 0.0.0.0 --port $PORT`
  (see §14 blockers: host/port are NOT handled in code today).
- Current development command (docs/deployment guides): plain
  `uvicorn xportra.api.app:app` (uvicorn default binds `127.0.0.1:8000`).
- Startup-time local-infrastructure dependencies: NONE. Module import only
  validates configuration (`validate_app_env`,
  `validate_production_environment`, `SupabaseAuthSettings.from_environment`);
  lifespan builds `ApplicationServices.from_environment()`, whose `Database`
  constructor only stores the DSN + `psycopg.connect` factory (first real
  connection opens per-request). Qdrant/LLM/embedding/Storage clients are
  never constructed at startup on the default path (all `None` → 503
  per-request, §6/§14).

## 3. Required production environment variables

(All names verified against `docs/architecture/environment-schema.md`,
`.env.example`, and grep over `xportra/`. `.env.example` lists every variable
the code reads; no code path reads an undocumented variable.)

| Variable | Classification | Notes |
|---|---|---|
| `APP_ENV=production` | required config | Anything else keeps dev behavior; unknown values rejected at import. |
| `APP_DEBUG=false` (or unset) | required config | Any other value refuses production startup. |
| `DATABASE_URL` | required secret | Supabase Postgres connection string; missing refuses startup. |
| `SUPABASE_JWT_SECRET` | required secret | Missing refuses startup AND per-request auth setup. |
| `SUPABASE_URL` | required config (recommended) | Enables `iss == <url>/auth/v1` check; without it issuer is not verified. |
| `CORS_ALLOWED_ORIGINS` | required config in practice | Empty = production serves zero browser origins (fail closed). Exact `https://` origins, no wildcards/paths. |
| `SUPABASE_SERVICE_ROLE_KEY` | required secret iff uploads used | Without it upload/download routes 503 before any mutation. |
| `EVIDENCE_STORAGE_BUCKET` | optional (default `tenant-evidence`) | Must name the provisioned private bucket. |
| `VECTOR_STORE_URL` | required iff RAG/analysis/uploads-indexed used | No default; missing → RAG veut 503, not localhost fallback. |
| `VECTOR_STORE_COLLECTION` | required iff RAG used | Same collection must back retrieval AND upload index-sync. |
| `LLM_API_KEY` | required secret iff RAG/analysis used | Only read when the RAG stack is composed. |
| `LLM_MODEL` | required config iff RAG used | e.g. an OpenRouter model id. |
| `EMBEDDING_MODEL` | required config iff RAG used | Must match indexed collection (fail-closed on mismatch). |
| `EMBEDDING_DIMENSIONS` | required config iff RAG used | Positive int; must equal model output AND collection size. |
| `SUPABASE_JWT_AUDIENCE` | optional (default `authenticated`) | — |
| `LLM_BASE_URL` | optional (default `https://openrouter.ai/api/v1`) | — |
| `LLM_TIMEOUT_SECONDS` | optional (default `60`) | Must be finite positive. |
| `APP_NAME` | obsolete/unused | Documented but NOT read by any application code. |
| `LOG_LEVEL` | obsolete/unused | Documented but NOT consumed (stdlib logging, no level wiring). |
| `PORT` | NOT read by code | Platform must inject into the start command (§14 blocker). |

## 4. Optional environment variables

`SUPABASE_JWT_AUDIENCE`, `EVIDENCE_STORAGE_BUCKET`, `LLM_BASE_URL`,
`LLM_TIMEOUT_SECONDS`. Everything else is either required (above) or unused
(`APP_NAME`, `LOG_LEVEL`). No development/test-only variables exist in the
schema (dev behavior is keyed off `APP_ENV != production`, not variables).

## 5. Database readiness

- `DatabaseSettings.from_environment()` requires `DATABASE_URL`, else
  `DatabaseConfigurationError` at import (production) — fail fast, correct.
- `Database` opens short-lived `psycopg.connect(dsn, row_factory=dict_row)`
  connections per operation, each wrapped in a transaction; no pool, no
  persistent connections, no startup connection — safe for a single Render
  instance, concurrency-limited by design (accepted v1 limitation).
- SSL: code passes the DSN straight through — no `sslmode` enforcement or
  defaulting. Readiness depends on `DATABASE_URL` carrying Supabase's SSL
  parameters (Supabase connection strings do); code neither helps nor
  hinders. Non-blocking: verify the provisioned DSN connects with SSL.
- Migrations 002–013 already applied per brief; 001–013 each ship `.down.sql`
  rollbacks; no startup migration runner exists (operator `psql`, never the
  app). Nothing in the app expects a local PostgreSQL server.
- No liveness/readiness DB probe endpoint exists (§12).

## 6. Qdrant readiness — CRITICAL

- Access is exclusively via `QdrantClient(url=config.qdrant_url)` built from
  `VECTOR_STORE_URL` in `rag_composition.py` / `evidence_upload.py`. There is
  NO localhost default in application code (missing/blank raises
  `RAGConfigurationError`); `localhost:6333` appears only in tests/docs.
- The deployed default (`uvicorn xportra.api.app:app`, lifespan →
  `from_environment()`) wires `rag=None`, `evidence_storage=None`,
  `evidence_index_sync=None`. The opt-in composers
  (`from_environment_with_rag`, `from_environment_with_evidence_upload`) are
  referenced ONLY in tests/docstrings — never by `app.py`. Consequences:
  - `POST /rag/query` → 503 `rag_not_configured`.
  - `POST /compliance/workflows/analyze` → 503 (RAG dependency missing).
  - `POST /conversations/messages` knowledge intents → 503; shipment-only
    intents still work without RAG.
  - `POST /compliance-evidence/uploads` and download → 503
    `evidence_upload_not_configured` (BOTH storage and index-sync must be
    wired; `with_evidence_upload` swallows each compose failure to `None`
    independently). Uploaded-evidence indexing additionally needs Qdrant even
    though Storage is Supabase.
- So a hosted Qdrant-compatible endpoint IS required for production IF
  analysis / knowledge-chat / file-upload flows are in scope; core flows
  (shipments, workflow progression, evidence registration reads, listings,
  stored reports/packages, finalize of already-analyzed work, shipment-only
  conversation) run WITHOUT Qdrant. No Qdrant I/O happens at startup on any
  path (embedding model loads lazily on first `embed()`; `ensure_collection`
  is a per-lifecycle call, never invoked by `app.py`).
- Endpoints/services requiring Qdrant: `/rag/query`, `/compliance/workflows/analyze`,
  knowledge-mode `/conversations/messages`, and the upload index-sync leg of
  `/compliance-evidence/uploads`. No replacement vector DB is introduced.

## 7. OpenRouter readiness

- Single adapter `OpenRouterLLMClient` (OpenAI-compatible chat completions
  over `httpx`, no vendor SDK) built ONLY inside `compose_rag_stack` from
  `LLMSettings` (`LLM_API_KEY` secret + `LLM_MODEL`); `LLM_BASE_URL` /
  `LLM_TIMEOUT_SECONDS` optional. Missing key/model raises at COMPOSITION
  time (`LLMConfigurationError` → `RAGConfigurationError`), never per
  request — but composition is never invoked by the deployed app (§6), so
  today missing LLM credentials do NOT prevent startup; RAG routes 503
  instead. `LLMSettings.api_key` is `repr=False` (never logged); generation
  logs carry model id + latency only. No LLM call is made during tests here.

## 8. Supabase readiness

- Auth/JWT: `SupabaseAuthSettings.from_environment()` REQUIRES
  `SUPABASE_JWT_SECRET` (HS256, requires `exp`+`sub`, audience default
  `authenticated`, optional issuer pin from `SUPABASE_URL`). `create_app()`
  calls it at import in production (fail fast) and every authenticated
  request re-derives it. `SUPABASE_URL` optional but recommended — without it
  any correctly-signed token with the right audience passes regardless of
  issuer.
- Storage: `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (+ optional bucket)
  required ONLY by the upload/download path at composition time; all other
  endpoints never touch them. Never exposed to clients (server-side puts +
  signed-URL issuance over `httpx`, no vendor SDK).
- All three variables are mandatory for a FULL production boot only in the
  sense: JWT secret + DATABASE_URL gate startup; URL + service-role key gate
  issuer verification and uploads respectively. No Supabase network I/O at
  startup on any path.

## 9. Storage readiness

- Bucket: `tenant-evidence` default (`EVIDENCE_STORAGE_BUCKET` override);
  matches the provisioned private bucket. Private-only: downloads are
  per-request short-lived signed URLs (TTL ≤ 3600 s), used immediately and
  never stored (response DTO carries the URL by purpose; audit log excludes
  it). Upload/download verify tenant + evidence ownership first;
  cross-tenant lookups fail closed as not-found.
- MIME: closed set PDF (`application/pdf`), DOCX
  (`application/vnd.openxmlformats-...wordprocessingml.document`), JPEG
  (`image/jpeg`), PNG (`image/png`) — declared content-type AND magic-byte
  inspection (`%PDF-`, ZIP+OOXML structure, `FFD8FF`, PNG signature);
  extension is consistency-check only. Matches the bucket MIME restriction.
- Size: 10 MB per file enforced on DECODED bytes in domain
  (`MAX_EVIDENCE_UPLOAD_BYTES`), transport bound
  `MAX_UPLOAD_BASE64_CHARACTERS = 20_000_000` in API schemas → 413
  `payload_too_large`; frontend mirrors the 10 MB message. No reverse-proxy
  body cap exists in code (platform limit applies).
- Everything is Supabase Storage; storage keys are server-composed
  (client filenames are display metadata only; traversal rejected); failed DB
  writes trigger compensating storage deletes. No local filesystem
  persistence is assumed (no `tempfile`, no volume writes —
  `base64 → bytes → httpx PUT` entirely in memory; 10 MB × request fits a
  web worker but bounds concurrency). In-memory store exists but is
  tests/dev-only and unreachable in production wiring.

## 10. CORS readiness

- `runtime.py` is the single home: methods GET+POST only, headers
  `Content-Type` / `Authorization` / `X-Development-Tenant-ID` only,
  `allow_credentials=False`, preflight cache 600 s, security headers
  (`nosniff`, `DENY`, `no-referrer`) on all responses.
- Development/test: local Vite origins (`http://localhost:5173`,
  `http://127.0.0.1:5173`) always allowed + `CORS_ALLOWED_ORIGINS` extras.
- Production: ONLY `CORS_ALLOWED_ORIGINS`; empty → zero browser origins
  (verified: returns `()`); wildcards/malformed origins rejected at startup
  in every environment. The frontend production origin IS configurable purely
  via `CORS_ALLOWED_ORIGINS=https://<frontend-domain>` — no code change
  needed. Nothing to change yet; just set the variable at deploy time.

## 11. Authentication/authorization readiness

- Production behavior verified (44/44 Phase 10.1 security tests passing):
  `X-Development-Tenant-ID` is rejected unconditionally in production
  (`503 development_tenant_context_disabled`) — even alongside a Bearer
  token — and `get_member_context` raises `401 authentication_required`
  for anonymous production requests. Dev header grants synthetic OWNER only
  outside production. `xportra/dev/bootstrap.py` refuses `APP_ENV=production`
  before opening any connection.
- No hard-coded development users, passwords, tokens, or tenant UUIDs in
  application source (grep-clean; secrets scan clean per prior audit).
  Tenant identity always resolves server-side from Supabase subject →
  `users.supabase_uid` → active memberships; `X-Xportra-Tenant-ID` may only
  SELECT among the caller's own active memberships, never arbitrary tenants.
- Do not weaken: production relies entirely on this boundary; RLS is
  intentionally disabled, so the application layer is the ONLY tenant
  isolation enforcement.

## 12. Health-check readiness

- NO `/health`, readiness, or liveness endpoint exists (verified against the
  live OpenAPI path list: 33 API paths, docs routes only otherwise). No DB
  health check exists anywhere.
- Recommended provider check until a dedicated endpoint is approved:
  unauthenticated `GET /compliance/shipments` → expect `401
  authentication_required`, which proves process boot, routing, and the auth
  boundary live WITHOUT touching the database (auth rejects before membership
  resolution in production… note: anonymous production requests raise before
  any DB use, so this is a liveness check, NOT a DB-readiness check).
  Authenticated `GET /compliance/shipments` (200) additionally proves
  DATABASE_URL + tenancy. Do NOT use `/docs`/`/openapi.json` (disabled in
  production) or any mutating/503-capable path as the health check.

## 13. Frontend API configuration

- Single mechanism: `VITE_API_BASE_URL` (build-time, `frontend/src/api/client.ts`
  `apiBaseUrl()`), default `http://localhost:8000` when unset. All API traffic
  flows through `apiFetch`; no raw `fetch()` elsewhere; Bearer preferred,
  dev-header only when no token is configured (backend rejects it in
  production regardless).
- Pointing at a hosted HTTPS API requires NO code change: build with
  `VITE_API_BASE_URL=https://<api-domain>` (`npm run build` → static `dist/`).
  Caveat: it is build-time, not runtime — each backend URL needs its own
  frontend build. Auth token lives in memory only (reload signs out; accepted).
  No `VITE_*` Supabase variables exist — the frontend holds no Supabase
  client; it only pastes the Supabase JWT into `Authorization`.

## 14. Blocking issues

B1. **No `$PORT`/bind handling — platform cannot route to the app.**
`xportra/` contains zero references to a `PORT` variable and no bind
configuration; docs only show bare `uvicorn xportra.api.app:app`
(localhost:8000). A Render-style host assigns a dynamic port and expects the
service to listen on `0.0.0.0:$PORT`. Smallest remediation (deploy config
only, no code): set the platform start command to
`uvicorn xportra.api.app:app --host 0.0.0.0 --port $PORT` (shell-expanded by
the host). No ADR/code change needed if the host supports command
interpolation; otherwise a one-line `start.sh` is the smallest artifact.

B2. **No health-check endpoint for the provider to probe.**
Nothing to probe except auth-guarded routes or disabled docs (§12).
Smallest remediation: add ONE unauthenticated `GET /health` (liveness only,
no DB/Supabase/Qdrant I/O — must stay dependency-free so deploys stay
routable during downstream outages) in a follow-on task WITH acceptance
tests; point the provider health check at it. Until then use the §12
401-probe as the interim check. (Requires a tiny code addition — an approved
micro-task, not part of this audit.)

B3. **Deployed composition serves a neutered API (analysis/RAG/uploads all 503).**
`app.py` lifespan hardcodes `ApplicationServices.from_environment()`; the
working composers (`from_environment_with_rag`,
`from_environment_with_evidence_upload`) are dead code in production and
there is no combined composer (each drops the other's piece). Deploying
today's image yields 503 on `/rag/query`, `/compliance/workflows/analyze`,
knowledge chat, and evidence uploads — i.e. the smoke procedure §§6–7 of
the deployment guide CANNOT pass. Smallest remediation: one follow-on task
to wire lifespan (or `create_app`) to compose upload + RAG stacks from the
environment with per-piece fail-closed-to-503 semantics preserved, so missing
Qdrant/LLM/Storage key degrades per-route rather than crashing boot; add an
ADR only if the chosen wiring alters boundaries (it shouldn't — composers
already exist). Scope decision needed first: full-product boot (needs hosted
Qdrant + OpenRouter) vs core-only boot (DATABASE_URL + Supabase secrets,
RAG/upload routes documented 503).

B4. **`SUPABASE_URL` should be treated as required.**
Issuer verification is skipped when it is unset (any correctly-signed token
accepted). Smallest remediation: set it in production env (no code change);
optionally promote to startup-required in the B3 task.

## 15. Non-blocking issues

- N1. `APP_NAME` / `LOG_LEVEL` documented but unread by code (log-level
  tuning via env silently does nothing). Harmless; either wire or document.
- N2. No connection pooling (short-lived psycopg connections per op).
  Correct for one instance; right-size before high concurrency.
- N3. No `sslmode` enforcement — relies on the DSN carrying Supabase SSL
  params. Verify the provisioned `DATABASE_URL` connects with SSL; no code
  change proposed.
- N4. No request-body cap beyond the 20 M-char upload field bound; rely on
  the platform's request-size limit.
- N5. `sentence-transformers` in default dependencies pulls torch-class
  weight — fine on Render (no Docker needed) but expect a slow first
  install/boot and lazy model download on first embedding; pre-warming is an
  ops nicety, not a blocker. Model download at request time needs egress —
  allowed on Render.
- N6. No CI workflow, no Dockerfile, no lockfile pinning beyond version
  ranges (`uv.lock` exists but untracked), frontend lockfile absent —
  reproducible-build hygiene for later.
- N7. `VITE_API_BASE_URL` is build-time: each backend URL needs a frontend
  rebuild; coordinate frontend/backend deploy order.
- N8. Frontend token in memory only (reload signs out) — secure default.
- N9. No background workers/schedulers/queues/WebSockets/cron of any kind
  (grep-clean); lifespan is boot-only with no teardown work; a single web
  service is sufficient, horizontal instances are safe (stateless, no
  in-memory registry, no sticky sessions).
- N10. Prior `tasks/completed/production-readiness-audit.md` verdict (no
  code-level blocker) still holds for CODE; the §14 blockers are
  wiring/operations gaps, not behavior defects.

## 16. Exact next deployment task

**`tasks/active/render-production-wiring.md` (single scoped task):**
"Render production wiring — composition + health + start command."

1. Wire `create_app`/lifespan to compose the RAG stack AND the evidence
   upload stack from the environment (reuse existing composers; add the
   missing combined path), preserving per-route 503 fail-closed when
   Qdrant/LLM/Storage pieces are absent and never failing boot for them;
   keep `DATABASE_URL` + `SUPABASE_JWT_SECRET` as the only boot gates.
2. Add dependency-free `GET /health` (liveness, no I/O) with focused tests.
3. Record the Render start command
   (`uvicorn xportra.api.app:app --host 0.0.0.0 --port $PORT`) and the
   production env set (§3 table) in `docs/deployment/`; set
   `CORS_ALLOWED_ORIGINS` to the real frontend origin and `SUPABASE_URL`.
4. Acceptance: boot with core-only env (RAG/upload routes 503, everything
   else live); boot with full env (all routes live against hosted Qdrant);
   `/health` 200 with backends down; `tsc`/pytest regressions green.
   Then: provision hosted Qdrant (collection sized to `EMBEDDING_DIMENSIONS`)
   iff analysis is in v1 scope, deploy, and run the §10 smoke procedure of
   `docs/deployment/XPORTA-V1-DEPLOYMENT.md`.

## Verification (this audit)

- Focused suites read-only: `test_phase_10_1_production_security.py` 44
  passed + 24 subtests; `test_rag_composition.py` 46 passed.
- Live import probes (no I/O): OpenAPI path enumeration (33 paths, no
  `/health`); `validate_production_environment` fails-closed/empty-CORS
  behavior; grep audits for `PORT` (absent), `sslmode` (absent),
  `LOG_LEVEL`/`APP_NAME` (unread), localhost defaults (tests/docs only),
  background-job primitives (absent), hard-coded dev identities (absent).
- No packages installed; no `.env`/secret values read or printed; no network
  calls made.
