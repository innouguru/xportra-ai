# Xportra v1 — Production Deployment Guide

> Status: preparation only. No deployment has been performed and no
> production smoke test has been executed. This document records what
> must be provisioned, configured, migrated, deployed, and verified
> for the first real v1 deployment. Nothing here deploys anything.
>
> Authority: `REQUIREMENTS.md`, `INVARIANTS.md`,
> `docs/architecture/environment-schema.md` (canonical variable
> contract), `.env.example` (authoritative template),
> `tasks/completed/production-readiness-audit.md` (code verdict:
> no code-level production blocker),
> `tasks/completed/production-deployment-readiness-audit-render.md`
> (Render-target audit: blockers B1–B4), and
> `tasks/completed/render-production-wiring.md` (B1–B4 wiring:
> lifespan composition, `GET /health`, SUPABASE_URL gate,
> Render start command).

## 1. Prerequisites

- A Supabase project (free tier suffices for v1):
  Auth, Postgres database, one private Storage bucket.
- A static host for the frontend (any static host; no
  server-side rendering).
- A Python host for the backend (Python 3.13, no Docker
  required and none provided).
- Required iff RAG analysis is in v1 scope: a hosted Qdrant
  instance (see §14 for the exact specification, the free-first
  recommendation, and the verification procedure). Core shipment,
  workflow, evidence-register, listing, and report reads run
  without it (each dependent path fails closed; see §10
  and the lifespan paragraph in §7).
- Operator access to run `psql` against the production
  database for migrations (no migration runner ships
  with the project).

## 2. Architecture / services required

```text
Browser (static frontend)
  │  HTTPS, VITE_API_BASE_URL
  ▼
FastAPI backend (uvicorn, single process is enough for v1)
  ├── Supabase Postgres (authoritative persistence)
  ├── Supabase Auth (JWT verification, HS256)
  ├── Supabase Storage, private bucket (evidence objects)
  ├── Qdrant (optional; retrieval/analysis only)
  └── OpenRouter (optional; generation/analysis only)
```

At steady state the backend holds no session, no
in-memory registry, and no background workers. Each
request opens short-lived database connections; there
is no connection pool (accepted v1 limitation —
right-size the host before high concurrency).

## 3. Environment variables

Canonical contract: `docs/architecture/environment-schema.md`;
template: `.env.example` (placeholders only — never put
real secrets in repository files, and never commit `.env`).

Backend production values (all set in the host
environment, never in code):

| Variable | Required | Notes |
|---|---|---|
| `APP_ENV` | yes | Must be exactly `production`. Anything else is rejected as unknown; anything but `production` keeps development behavior. |
| `APP_DEBUG` | yes, as `false` | Unset counts as off. Any other value refuses production startup. |
| `DATABASE_URL` | yes | Supabase Postgres connection string (treated as a secret). Missing value refuses production startup. |
| `SUPABASE_JWT_SECRET` | yes | Supabase project JWT secret. Missing value refuses production startup and authentication setup. |
| `SUPABASE_URL` | yes | Supabase project URL. Required: pins token issuer verification (`<url>/auth/v1`); missing value refuses production startup. |
| `SUPABASE_JWT_AUDIENCE` | no | Defaults to `authenticated`. |
| `CORS_ALLOWED_ORIGINS` | yes in practice | Comma-separated explicit `https://` origins (e.g. the frontend domain). Empty means browsers get no access (fail closed). Wildcards are rejected at startup. |
| `SUPABASE_SERVICE_ROLE_KEY` | for uploads | Server-side Storage puts and signed URLs only; never exposed to clients. Without it, upload/download routes fail closed with 503. |
| `EVIDENCE_STORAGE_BUCKET` | no | Defaults to `tenant-evidence`; must name the provisioned private bucket. |
| `VECTOR_STORE_URL`, `VECTOR_STORE_COLLECTION` | for RAG | Qdrant REST endpoint + collection name. Constraints (§14): collection is operator-chosen (no repo default; the single variable feeds both retrieval and upload index-sync so they always agree); dimensions and distance are fixed by code (384 / cosine for the `all-MiniLM-L6-v2` baseline). |
| `QDRANT_API_KEY` | for Qdrant Cloud | Secret. Required by Qdrant Cloud; optional otherwise (absent = existing keyless behavior; never fails startup). Passed to `QdrantClient(api_key=...)` by both the RAG stack and the upload index-sync composers. |
| `LLM_API_KEY`, `LLM_MODEL` | for RAG | OpenRouter key + model id. |
| `LLM_BASE_URL` | no | Defaults to OpenRouter. |
| `LLM_TIMEOUT_SECONDS` | no | Defaults to 60. |
| `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` | for RAG | Baseline: `all-MiniLM-L6-v2` / `384`. Must match each other and the collection (mismatches fail closed at `ensure_collection`; never inferred). |
| `APP_NAME` | no | Instance label for diagnostics. |
| `LOG_LEVEL` | no | Documented verbosity; application code logs via stdlib only. |

Verified 2026-10-07: `.env.example` lists every variable
the code reads; no code path reads an undocumented
variable. Frontend: `VITE_API_BASE_URL` (build-time,
e.g. `https://api.example.com`; the `http://localhost:8000`
fallback is development-only).

## 4. Database migration procedure

Existing supported tooling is plain `psql`; no runner
ships with the project, and none was introduced (task
constraint). Apply in filename order against the
production database:

```text
001_initial_schema
002_add_supabase_auth_identity
003_regulatory_source_artifacts
004_regulatory_document_normalizations
005_regulatory_document_metadata
006_regulatory_requirements
007_regulatory_requirement_applicability
008_regulatory_requirement_assessments
009_evidence_documents
010_compliance_analysis_results
011_evidence_upload_processing
012_compliance_workflows
013_shipments
```

For each `NNN_name`:

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/NNN_name.sql
```

Notes and caveats:

- Run inside one operator session, in order, without
  skipping. Each file is its own transaction (`BEGIN;`
  … `COMMIT;`); a failure aborts that file only —
  fix the cause and rerun that file (all statements
  use `IF NOT EXISTS` guards except the initial 001
  base-schema creation, which must run once on an
  empty database).
- 001 seeds six Nigerian regulatory authorities and
  creates the `xportra` schema plus fourteen tables;
  002 adds `users.supabase_uid`; 011 adds upload/
  processing columns to `compliance_evidence`; 010/012/
  013 create the analysis, workflow, and shipment
  tables. No migration deletes production data; every
  file has a matching `.down.sql` rollback.
- Never edit an applied migration in place; future
  schema work means a new numbered migration plus ADR.

## 5. Post-migration verification checklist

Run these read-only checks (all must return rows/true;
none writes data):

- Schema `xportra` exists.
- Tables exist: `tenants`, `users`,
  `user_tenant_memberships`, `authorities` (six seeded
  rows), `exporters`, `products`, `destination_markets`,
  `requirements`, `requirement_applicability`,
  `compliance_evidence`, `evidence_requirements`,
  `compliance_analysis_reports`, `compliance_analyses`,
  `compliance_analysis_traces`,
  `compliance_workflow_rounds`,
  `final_assessment_packages`,
  `compliance_workflows` (012), `shipments` (013).
- 002 column present: `users.supabase_uid`.
- 011 columns present on `compliance_evidence`
  (processing/status/upload fields).
- Composite tenant keys present, e.g.
  `PRIMARY KEY (tenant_id, workflow_id)` on
  `compliance_workflows` and
  `PRIMARY KEY (tenant_id, shipment_id)` on `shipments`.
- Shipment status check admits
  `draft | bound | locked`; workflow state check admits
  the nine process states ending in
  `assessment_package_ready`.
- `updated_at` triggers present on the shipment,
  workflow, and result tables.

## 6. Supabase configuration

- Auth: create the project, note the JWT secret and
  project URL; set `SUPABASE_JWT_SECRET` and `SUPABASE_URL`
  on the backend host only (both are production boot gates;
  without the URL the issuer check cannot be pinned).
- Database: use the project connection string as
  `DATABASE_URL`; apply §4 migrations; create at least
  one tenant + owner membership for the first operator
  (via the application's own sign-up/membership flow
  once live, or `python -m xportra.dev.bootstrap`
  **only** against a non-production database — it
  refuses `APP_ENV=production`).
- Storage: create one **private** bucket (default name
  `tenant-evidence`; never public); grant the service
  role object access; set `SUPABASE_SERVICE_ROLE_KEY`
  backend-side only. Downloads are short-lived signed
  URLs issued per authorized request, never stored.

## 7. Backend deployment (Render-style Python web service)

- Runtime: Python 3.13 (`pyproject.toml`
  `requires-python = ">=3.13,<3.14"`), dependencies
  from `pyproject.toml` (`fastapi`, `uvicorn`,
  `psycopg[binary]`, `pyjwt`, plus `qdrant-client` and
  `sentence-transformers` where RAG paths are needed).
- Canonical Render start command (the application itself
  does NOT read `PORT`; Render supplies `$PORT` to the
  shell command, and the process must bind `0.0.0.0`):

  ```text
  uvicorn xportra.api.app:app --host 0.0.0.0 --port $PORT
  ```

  The start command invokes the `uvicorn` console script, so
  `uvicorn` must stay a declared runtime dependency in
  `pyproject.toml` (currently `uvicorn[standard]>=0.30,<1.0`;
  pinned by `tests/unit/test_production_runtime_dependencies.py`) —
  a build tree without it installs FastAPI but fails at startup
  with `uvicorn: command not found`. Deploy from a commit that
  contains the declaration, and clear the platform build cache if
  a cached environment predates it.
  Module import validates production configuration and
  fails fast on missing secrets (including `SUPABASE_URL`),
  missing `DATABASE_URL`, debug-on, unknown `APP_ENV`, or
  bad CORS origins; interactive docs are disabled in
  production; `debug=False` always.
- Lifespan composition: the database-backed base container
  is always built (`DATABASE_URL` stays a boot gate);
  the RAG chain, Supabase object storage, and evidence
  index sync are each composed independently through the
  existing Phase 5.14 / Phase 10.4 composition roots.
  Missing or unreachable optional services degrade to the
  existing per-route 503s (`rag_not_configured`,
  `evidence_upload_not_configured`) without failing boot
  and without affecting core routes. No external call is
  made at startup: Qdrant clients are constructed with
  compatibility probing disabled, the embedding model
  loads lazily on first use, and collection verification
  never runs at boot. Core-only boot (no Qdrant/OpenRouter
  variables) serves shipments, workflows, evidence
  reads, listings, stored reports/packages, and
  finalization; analysis, RAG queries, knowledge-mode
  chat, and uploads need their capability variables.
- Liveness probe: unauthenticated `GET /health` →
  `200 {"status": "ok"}` with no database, Supabase,
  Qdrant, or OpenRouter access. Point the platform health
  check at `/health` (never at `/docs`, which is disabled
  in production, and never at an authenticated route).
- No workers, schedulers, or filesystem state are
  required; each instance is stateless (scale by
  adding instances behind the platform's router,
  within the no-pooling limitation).

## 8. Frontend deployment

- Build: `npm run build` (`tsc --noEmit` then
  `vite build`) with `VITE_API_BASE_URL` set to the
  production API origin. Output: `dist/` (static).
- Host `dist/` on any static host over HTTPS; no SSR,
  no server code, no secrets in the bundle (the token
  lives in memory only; the dev-tenant header is sent
  only when no bearer token is configured, and the
  backend rejects it in production regardless).
- API expectations: JSON over GET/POST, bearer auth,
  structured `error.code` responses; the UI already
  maps 401/403/404/409/503 to plain-English states.

## 9. CORS configuration

Set `CORS_ALLOWED_ORIGINS` to the exact production
frontend origin(s) (`https://app.example.com`, comma-
separated, no paths, no wildcards). Development
loopback origins are never trusted in production.
Credentialed CORS stays off (header auth, no cookies).

## 10. Smoke-test procedure (first deployment)

Perform in order with a real operator account. Record
actual results at deployment time — this document
defines the procedure only; no production run has
occurred.

0. Health: `GET /health` → 200 (process alive;
   liveness only — proves nothing about downstream services).
1. Authenticate (Supabase sign-in → bearer token).
2. Call an authenticated read (e.g.
   `GET /compliance/shipments` → 200, possibly empty).
3. Start a shipment (`POST /compliance/workflows/start`
   with profile → 201; note `case_id`/`shipment_id`).
4. `GET /compliance/shipments` lists it; `GET
   /compliance/shipments/{id}` returns profile +
   workflow summary.
5. Reload/fresh session (no browser storage): repeat
   step 4 — identical results prove server authority.
6. Upload evidence (`POST /compliance-evidence/uploads`
   → 201) and supply it to the workflow.
7. Run analysis (`POST /compliance/workflows/analyze`
   → 200; requires Qdrant + OpenRouter provisioned).
8. Reload, then `GET /compliance/reports/{report_id}`
   → identical report (rehydration, no in-memory
   dependence).
9. Finalize (`POST /compliance/workflows/finalize` →
   201).
10. Confirm `shipment.status == locked`,
    workflow `state == assessment_package_ready`,
    and package linkage retrievable.
11. Fresh session: open the completed shipment and its
    historical report/package — all readable.
12. Negative: repeat a read with another tenant's
    identity → indistinguishable 404; retry finalize
    → terminal rejection (409), no duplicate package,
    shipment stays `locked`.

## 11. Production verification checklist (v1 completion gate)

- [ ] §5 migration checks all pass on the production database.
- [ ] Backend boots with production env (fails fast otherwise verified by startup validation).
- [ ] `GET /health` returns 200 from the deployed service (platform health check points at `/health`).
- [ ] Render start command is `uvicorn xportra.api.app:app --host 0.0.0.0 --port $PORT`.
- [ ] Frontend production build served over HTTPS against the production API origin.
- [ ] Smoke steps 1–12 pass with recorded evidence; negative step 12 confirmed.
- [ ] CORS allows only the production frontend origin.
- [ ] Storage bucket is private; uploads/downloads verified end-to-end (step 6).
- [ ] Hosted Qdrant verified per §14 (reachable, correct dims/metric, empty) — iff RAG analysis is in v1 scope.
- [ ] No `.env` or secret committed (`.env` ignored; secret-pattern scan clean as of 2026-10-07).
- [ ] Gated live integration tests executed against a non-production mirror where possible (still gated without `DATABASE_URL` in CI-less local runs).

## 12. Failure/recovery notes

- Migration file fails: that file's transaction aborts;
  fix the cause, rerun the same file (guards make
  reruns safe except re-running 001 on a populated
  schema — never do that); `.down.sql` files roll a
  single migration back for diagnosis, not for routine
  use.
- Backend fails at startup: it refuses to serve
  (missing secret/DSN, debug-on, unknown env, bad
  CORS, bad auth config) — fix environment, restart.
- Backend loses the database at runtime: requests fail
  closed (4xx/503 by path); no partial writes (every
  multi-write path is transactional or compensated);
  recovery is database recovery — the app holds no
  state to reconcile.
- Frontend deploy fails: static build is atomic per
  deploy on any standard static host; previous bundle
  stays live until replaced.
- Storage misconfigured: upload/download routes fail
  closed with 503 before mutation; fix bucket/keys,
  retry — no orphan state beyond compensated puts.
- Qdrant/OpenRouter unavailable: analysis,
  re-analysis, and conversational paths fail closed
  (503/502 by layer); shipment, workflow progression,
  evidence registration, listing, reports, and
  finalization of already-analyzed work are unaffected.
- Observability unavailable: stdlib logging degrades
  silently; requests never fail for logging reasons.

## 13. v1 completion gate

v1 is complete when §11 is fully checked with recorded
results. The code verdict stands (no code-level
blocker); remaining work is provisioning, migration,
deployment, and live verification — all operational,
none architectural.

## 14. Production Qdrant — hosted vector store specification

> Status: specified, NOT provisioned. This section derives
> every requirement from the repository (cited below) and
> defines a non-destructive verification procedure. No
> collection has been created, no document ingested, no
> embedding generated.
>
> Hard boundary: **provisioning ≠ ingestion.** At the end
> of this task Qdrant is expected to be EMPTY — no
> regulatory documents, no embeddings, no production
> corpus. The authoritative knowledge acquisition +
> ingestion pipeline is a subsequent phase.
>
> Authority: `xportra/infrastructure/rag_composition.py`
> (`RAGInfrastructureConfig`, `compose_rag_stack`),
> `xportra/infrastructure/evidence_upload.py`
> (`compose_evidence_index_sync_from_environment`),
> `xportra/infrastructure/vector_index.py`
> (`ensure_collection`, `_ensure_content_text_index`,
> `validate_qdrant_collection_config`),
> `xportra/domain/vector_index.py` (`VectorIndexConfig`),
> `REQUIREMENTS.md` TB-4/TB-6, and
> `tests/integration/test_rag_qdrant_smoke.py` (existing
> opt-in live-smoke pattern).

### 14.1 Existing RAG configuration discovered

| Item | Value / rule | Source |
|---|---|---|
| `VECTOR_STORE_URL` | required, no default; blank fails closed to per-route 503 (never localhost fallback) | `rag_composition.py` `_require_non_empty` |
| `VECTOR_STORE_COLLECTION` | required, no repo default; the single variable feeds BOTH retrieval and upload index-sync, so the two paths always agree | `rag_composition.py`, `evidence_upload.py` |
| `EMBEDDING_MODEL` | required, no default; approved baseline `all-MiniLM-L6-v2` | TB-6; `rag_composition.py` |
| `EMBEDDING_DIMENSIONS` | required positive int; must equal the model's output AND the collection size (checked, never inferred) | `rag_composition.py`, `vector_index.py` |
| Distance metric | **cosine** — the only configured value (`VectorIndexConfig.from_embedding_config` default; no env override exists) | `domain/vector_index.py` |
| Collection creation | automatic and idempotent: first `upsert` calls `ensure_collection()`, which creates a missing collection with the configured size/distance and validates (never destroys) an existing one; `find`/`get`/`count` never create | `vector_index.py` `ensure_collection`, `upsert` |
| Payload indexes | NOT required upfront: the `content` full-text index (WORD tokenizer, lowercase, no stop-words/stemmer) is provisioned automatically by the code on the first lexical query (`_ensure_content_text_index`); a manually created incompatible index fails closed — do NOT create payload indexes by hand | `vector_index.py` |
| Client authentication | wired (optional): `QDRANT_API_KEY` (blank/missing → keyless) is passed as `QdrantClient(url=..., api_key=..., check_compatibility=False)` by both the RAG stack and the upload index-sync composers through one shared parsing path (`qdrant_api_key_from_environment`); the key is excluded from reprs and logs and never appears in error messages | `rag_composition.py`, `evidence_upload.py` |
| TLS | supported transparently: the URL string passes straight to `QdrantClient`, which accepts `https://` endpoints (required by Qdrant Cloud; the client also skips its background version probe at composition since render-production-wiring) | `rag_composition.py`, installed client signature |
| App-level health check | none exists for Qdrant (process `/health` is downstream-free by design); `collection_exists` guards live inside each operation | grep over `xportra/` |

### 14.2 Production Qdrant configuration (Render env)

```text
VECTOR_STORE_URL=<provider REST endpoint, e.g. https://<cluster-host>[:6333]>
VECTOR_STORE_COLLECTION=<operator-chosen name; no repo default>
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384
QDRANT_API_KEY=<Qdrant Cloud API key — secret, backend host only>
```

(`384` is the `all-MiniLM-L6-v2` output size from the TB-6 baseline;
`ensure_collection` re-validates it against the live collection, so a
wrong value fails closed instead of corrupting anything. The collection
name is fixed at Render-configuration time and recorded there — never
in the repo. No production values exist yet; local `.env` vector
entries are empty.)

### 14.3 Collection specification

- Name: the `VECTOR_STORE_COLLECTION` value (operator-chosen).
- Vectors: single unnamed vector per point, `size: 384`,
  `distance: Cosine`.
- Payload: plain JSON per point (tenant/chunk/document ids, content,
  provenance); NO manual payload indexes — the code provisions the
  `content` text index itself on first lexical use.
- May be ABSENT at the end of this task: the application creates it
  on first ingestion (`ensure_collection`). Manually pre-creating it
  with the parameters above is allowed but not required; never
  delete or recreate a collection that already holds points.

### 14.4 Recommended free-first hosted option

**Qdrant Cloud Free Tier** (verified 2026-10-08: single node,
0.5 vCPU / 1 GB RAM / 4 GB disk, no credit card; roughly one million
768-dimension vectors — orders of magnitude above the v1 workload of
thousands of 384-dimension chunks).

Caveats, stated plainly:

1. Qdrant Cloud mandates API-key authentication, which the
   application supports via `QDRANT_API_KEY` (secret, backend host
   only; absent means keyless — required for Qdrant Cloud, optional
   for keyless deployments and development). Until the key is set,
   RAG paths keep their designed 503 degradation while core routes
   serve normally.
2. Free-tier clusters suspend after ~1 week of inactivity and are
   deleted after ~4 weeks if not reactivated — reactivation is an
   operator calendar item until traffic is steady.
3. This task provisions nothing: the user creates the cluster in the
   provider UI (cluster name + provider + region → note the REST
   endpoint; no corpus, no documents, no embeddings).

### 14.5 Safe verification procedure (non-destructive)

Run from an operator machine with `curl` (and, for step 6, the repo
venv). Stop on the first failure; create, ingest, and delete NOTHING
in the production collection. `<Q>` is the `VECTOR_STORE_URL` value,
`<C>` the collection name.

1. Reachability + TLS: `curl -sS "<Q>/"` → 200 with a version JSON
   body. Proves the endpoint is reachable over the required scheme.
2. Auth posture: `curl -sS -o /dev/null -w "%{http_code}" "<Q>/collections"`
   → 200 on a keyless host. On a key-mandated host (Qdrant Cloud)
   expect 401 here, then repeat with the key:
   `curl -sS -o /dev/null -w "%{http_code}" "<Q>/collections" -H
   "api-key: <QDRANT_API_KEY>"` → 200 (proves the key authenticates;
   use the key only in this header, never in URLs or logs). A 401
   WITH the key means the key is wrong or revoked — fix it before
   continuing. Do NOT work around auth.
3. Collection state: `curl -sS "<Q>/collections/<C>"` → **404 is the
   EXPECTED pass** (absent = nothing ingested yet). A 200 is also a
   pass ONLY if `result.config.params.vectors.size` is `384` and
   `result.config.params.vectors.distance` is `"Cosine"`; anything
   else is a hard failure (do not write to it).
4. Dimensions/metric match: covered by step 3 (or deferred to first
   ingestion, where `ensure_collection` enforces both and fails
   closed on mismatch).
5. Empty-corpus proof: if the collection exists,
   `curl -sS -X POST "<Q>/collections/<C>/points/count" -H
   "Content-Type: application/json" -d '{"exact":true}'` → count `0`.
   (Absent collection ⇒ vacuously empty — preferred end state.)
6. Repo live-smoke pattern (opt-in, throwaway collection only — never
   `<C>`): with `QDRANT_URL=<Q>` exported,
   `python -m pytest tests/integration/test_rag_qdrant_smoke.py -q`
   creates a `xportra-smoke-*` collection, asserts `count == 0`, and
   deletes it. Proves end-to-end client↔server operation without
   touching production state.

Record all six results (commands + status codes/bodies, secrets
redacted) before closing this task. Expected end state: steps 1–2
pass, step 3 returns 404, steps 4–5 pass vacuously, step 6 passes —
Qdrant reachable, correct, and EMPTY.
