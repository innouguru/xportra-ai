# Xportra v1 — Production Deployment Guide

> Status: preparation only. No deployment has been performed and no
> production smoke test has been executed. This document records what
> must be provisioned, configured, migrated, deployed, and verified
> for the first real v1 deployment. Nothing here deploys anything.
>
> Authority: `REQUIREMENTS.md`, `INVARIANTS.md`,
> `docs/architecture/environment-schema.md` (canonical variable
> contract), `.env.example` (authoritative template), and
> `tasks/completed/production-readiness-audit.md` (code verdict:
> no code-level production blocker).

## 1. Prerequisites

- A Supabase project (free tier suffices for v1):
  Auth, Postgres database, one private Storage bucket.
- A static host for the frontend (any static host; no
  server-side rendering).
- A Python host for the backend (Python 3.13, no Docker
  required and none provided).
- Optional, only for analysis/conversational/RAG paths:
  a reachable Qdrant instance plus OpenRouter access
  with an embeddings-capable setup. Core shipment,
  workflow, evidence-register, listing, and report
  reads run without them (each dependent path fails
  closed; see §10).
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
| `SUPABASE_URL` | recommended | Enables token issuer verification (`<url>/auth/v1`). |
| `SUPABASE_JWT_AUDIENCE` | no | Defaults to `authenticated`. |
| `CORS_ALLOWED_ORIGINS` | yes in practice | Comma-separated explicit `https://` origins (e.g. the frontend domain). Empty means browsers get no access (fail closed). Wildcards are rejected at startup. |
| `SUPABASE_SERVICE_ROLE_KEY` | for uploads | Server-side Storage puts and signed URLs only; never exposed to clients. Without it, upload/download routes fail closed with 503. |
| `EVIDENCE_STORAGE_BUCKET` | no | Defaults to `tenant-evidence`; must name the provisioned private bucket. |
| `VECTOR_STORE_URL`, `VECTOR_STORE_COLLECTION` | for RAG | Qdrant endpoint + collection. |
| `LLM_API_KEY`, `LLM_MODEL` | for RAG | OpenRouter key + model id. |
| `LLM_BASE_URL` | no | Defaults to OpenRouter. |
| `LLM_TIMEOUT_SECONDS` | no | Defaults to 60. |
| `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` | for RAG | Must match each other and the collection. |
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
  project URL; set `SUPABASE_JWT_SECRET` (+ optional
  `SUPABASE_URL`) on the backend host only.
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

## 7. Backend deployment

- Runtime: Python 3.13 (`pyproject.toml`
  `requires-python = ">=3.13,<3.14"`), dependencies
  from `pyproject.toml` (`fastapi`, `uvicorn`,
  `psycopg[binary]`, `pyjwt`, plus `qdrant-client` and
  `sentence-transformers` where RAG paths are needed).
- Start: `uvicorn xportra.api.app:app` (module import
  validates production configuration and fails fast on
  missing secrets, debug-on, unknown `APP_ENV`, or bad
  CORS origins; interactive docs are disabled in
  production; `debug=False` always).
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
- [ ] Frontend production build served over HTTPS against the production API origin.
- [ ] Smoke steps 1–12 pass with recorded evidence; negative step 12 confirmed.
- [ ] CORS allows only the production frontend origin.
- [ ] Storage bucket is private; uploads/downloads verified end-to-end (step 6).
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
