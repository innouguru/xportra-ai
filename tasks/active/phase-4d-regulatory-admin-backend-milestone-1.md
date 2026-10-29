# Phase 4D — Regulatory Administration Backend — Milestone 1

**Active task:** Implement the first usable staff-only backend milestone for
regulatory ingestion administration (source intake, job lifecycle, extraction
outcomes, safe retry).

**Status:** In progress.

## Scope (implemented)

- Staff-uploaded artifact ingestion: `POST /regulatory/sources/{source_id}/artifacts`
  accepts `text/plain`, `text/markdown`, `application/json`, and `application/pdf`.
- Staff-entered inline text: `POST /regulatory/sources/{source_id}/artifacts/text`
  accepts `text/plain` and `text/markdown` (no file upload).
- Source registration: `POST /regulatory/sources` (existing).
- List/inspect: `GET /regulatory/sources`, `GET /regulatory/sources/{source_id}`,
  `GET /regulatory/ingestion-jobs/{job_id}`,
  `GET /regulatory/sources/{source_id}/ingestion-jobs` (existing).
- Extraction outcomes: `POST /regulatory/ingestion-jobs/{job_id}/extract`,
  `GET /regulatory/sources/{source_id}/candidates`, `GET /regulatory/candidates/{candidate_id}`
  (existing).
- All mutating routes require `GRANT_MAME` via `require_global_staff`; read-only
  routes also require the grant. Fail-closed on missing/invalid identity or grant.
- Audit through existing `global_staff_audit` mechanism (service layer).

## What was NOT changed

- No migration added (existing 018–029 schema supports the requirement).
- No new queue service or external infrastructure.
- No Stage A/B approval, publication, or exporter-facing behavior.
- No production data or migration changes.
- Bootstrap (`XPA-GSA-INIT-001`) not executed; no grant created.

## Verification

- Focused unit tests: 44/44 pass (test_regulatory_source_intake.py).
- Broader regulatory + API regression: 192 passed.
- Full unit suite: 2325 passed; 3 pre-existing failures unrelated to this change
  (RAG domain IO audit, RAG cross-tenant matrix, worker event-loop flake — all
  pass in isolation or are untouched by this change).
