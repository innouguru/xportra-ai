# Xportra v1 — Staging Deployment Specification

> Status: **STAGING BLOCKED — no staging infrastructure exists.**
> This document specifies the staging environment to be
> provisioned and the verification to be executed once it
> exists. It authorizes no deployment by itself, records
> no credentials, and claims no verification results.
>
> Production procedure (unchanged baseline):
> `docs/deployment/XPORTA-V1-DEPLOYMENT.md`.

## 1. Staging isolation contract

Staging must be fully separate from any future
production: a different Supabase project, different
database, different Auth users, different Storage
bucket, different secrets, different API/frontend
origins. Production credentials and data must never
enter staging, and staging credentials must never be
reused for production.

## 2. Exact missing prerequisites (all absent 2026-10-07)

Verified against the execution environment — every
item below is missing, so staging stops here:

- [ ] Staging Supabase project (no `SUPABASE_URL`)
- [ ] Staging Postgres database (no staging `DATABASE_URL`)
- [ ] Staging Supabase Auth users + JWT secret
  (no `SUPABASE_JWT_SECRET`)
- [ ] Staging private Storage bucket + service-role key
  (no `SUPABASE_SERVICE_ROLE_KEY`)
- [ ] Staging API host/origin (no `APP_ENV` beyond
  default, no staging `CORS_ALLOWED_ORIGINS`)
- [ ] Staging frontend origin + build-time
  `VITE_API_BASE_URL` (no value configured)
- [ ] Qdrant endpoint/collection for analysis-path UAT
  (no `VECTOR_STORE_URL`) — without it, analysis
  UAT records NOT RUN / BLOCKED, never PASS
- [ ] OpenRouter key/model for analysis-path UAT
  (no `LLM_API_KEY`) — same BLOCKED treatment

## 3. Staging configuration (to apply once §2 exists)

- Backend: `APP_ENV=staging` is **not** a known
  environment (`development | test | production`
  only). Until a staging value is deliberately
  introduced, staging deployments run with
  `APP_ENV=test`: development-tenant pathway
  available for operator-driven UAT, production
  hardening (docs-off, debug-pin) engaged only under
  `production`. Do not invent a fourth environment
  without an ADR.
- `APP_DEBUG=false`, `DATABASE_URL=<staging DSN>`,
  `SUPABASE_JWT_SECRET=<staging secret>`,
  `SUPABASE_URL=<staging URL>`,
  `CORS_ALLOWED_ORIGINS=https://<staging frontend>`,
  storage/RAG variables per §2 availability.
- Migrations `001 → 013` via the deployment-guide
  `psql` procedure against the staging database only,
  then the §5 checklist of the deployment guide.
- Backend: `uvicorn xportra.api.app:app` on the
  staging host. Frontend: `npm run build` with
  staging `VITE_API_BASE_URL`, static hosting.

## 4. UAT record (all BLOCKED — no staging to run against)

| Area | Status |
|---|---|
| Migration verification | BLOCKED (§2) |
| Backend deployment | BLOCKED |
| Frontend deployment | BLOCKED |
| Authentication | BLOCKED |
| Shipment creation/listing | BLOCKED |
| Evidence workflow | BLOCKED |
| Analysis/report | BLOCKED (additionally needs Qdrant/OpenRouter) |
| Rehydration/fresh-session | BLOCKED |
| Finalization/locking | BLOCKED |
| History | BLOCKED |
| Tenant isolation | BLOCKED |
| Terminal-state protection | BLOCKED |
| Automated backend suite | PASS (2039 + 61 subtests, local, 2026-10-07) |
| Frontend suite | NOT RUN this task (standing 64 files / 439 tests; untouched) |

Defects discovered: none (nothing deployed; nothing
to reproduce against). Fixes made: none.

## 5. Production authorization

**Not authorized.** Production remains BLOCKED until
staging is provisioned per §2–§3, the UAT table above
reads PASS (analysis PASS only with RAG dependencies,
else recorded BLOCKED with justification), and the
deployed version is the tested commit. The next
action is operational: provision §2 and re-run this
task from §3.
