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

## Verification (initial milestone-1 state, historical)

- Focused unit tests: 44/44 pass (test_regulatory_source_intake.py).
- Broader regulatory + API regression: 192 passed.
- Full unit suite: 2325 passed; 3 pre-existing failures unrelated to this change
  (RAG domain IO audit, RAG cross-tenant matrix, worker event-loop flake — all
  pass in isolation or are untouched by this change).

## Completion (2026-10-31)

**Status:** Complete. Milestones M1–M8 (backend, repository-only) verified
and committed:

- `aaa6b9a` — M3/M6 manual recovery candidates through publication gates.
- `49629dc` — M4 bounded ingestion retries + staff retry endpoint
  (`POST /regulatory/ingestion-jobs/{job_id}/retry`), migration 031,
  worker lease-recovery SQL fix (bound-parameter `make_interval`).
- `4749488` — M5 Stage A wording correction (migration 032 append-only
  `regulatory_requirement_wording_corrections` + triggers; Stage A
  correction flow atomic with the decision; history endpoint;
  ADR-0021).
- `e137cd5` — M7 source withdrawal endpoint
  (`POST /regulatory/sources/{source_id}/withdrawal`) raising pending
  `withdrawal` governance flags that close Stage A, Stage B, and
  publication eligibility.
- `3131417` — M8 end-to-end PostgreSQL integration gate
  (`tests/integration/test_regulatory_full_workflow_postgresql.py`,
  3/3 pass on isolated `xportra_test`) plus ADR-0022 + migration 033
  fixing the real defect that made `register_source` fail on any real
  database (`artifact_id NOT NULL` vs the artifact-optional registration
  job).

Verification: 273 regulatory unit tests pass; E2E suite 3/3 pass;
migration 032 append-only triggers verified live on `xportra_test` (and
migration 030 applied there). Unrelated preserved working-tree changes
were left untouched. No push. Deferred: frontend wiring for retry /
wording-correction / withdrawal; exporter catalog backend (untracked
`xportra/api/catalog.py` remains uncommitted); production migrations
030–033 application at authorized deployment time.
