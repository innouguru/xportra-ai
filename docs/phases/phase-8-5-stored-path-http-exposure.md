# Phase 8.5 — Stored-Path HTTP Exposure

**Status:** Complete and verified (2026-09-24)
**Phase:** Phase 8 — API & Application Integration
**Type:** Thin FastAPI adapter over 8.4 stored use cases;
no domain logic in routes, no verdict

> This record describes what was actually implemented and verified.

## Objective

Expose the stored-path operations that became safe in
Phase 8.4 — finalize from the server-known latest,
stored package reads, stored report reads — through
the same thin adapter shape:

```text
HTTP request → auth → authorize → ApplicationContext
→ exactly one use case → DTO serialization → response
```

## Endpoint inventory (3 new, 16 total compliance)

- `POST /compliance/workflows/finalize` → 201
  `{workflow, package}`. Permission
  `PROGRESS_COMPLIANCE_WORKFLOW`. Body carries only
  the workflow record; the result is resolved
  server-side, never supplied.
- `POST /compliance/workflows/package` → 200
  `FinalPackageResponse`. Permission
  `READ_TENANT_RESOURCE`. Body carries the workflow
  record; linkage is server-resolved.
- `GET /compliance/reports/{report_id}` → 200
  `AnalysisReportResponse`. Permission
  `READ_TENANT_RESOURCE`. Identity in path; tenant
  from membership.

## Route → application mapping

`finalize_stored_package`, `get_stored_package`,
`describe_stored_report` — one use case per route.
The store reaches routes only through the
`get_result_store` dependency (503
`result_store_not_configured` when unwired); the
analyze route passes the optional store through for
persist-on-analysis with unchanged unwired behavior.
No container surgery beyond the additive store field.

## Authentication/authorization flow

Unchanged Phase 1 boundary plus 8.3 actor threading:
finalize is owner-only (workflow mutation);
package/report reads are member-readable. The
`actor_id` override path is covered to prove actor
propagation does not disturb tenant/role derivation.

## Tenant isolation

Tenant comes only from membership in every handler.
Record tenants are re-checked in the application
boundary (403 `tenant_mismatch`); server-looked-up
reports stay 404-non-leaking. Deliberate cross-tenant
attempts tested in both directions.

## Request/response schemas

Additive `FinalPackageResponse` (mirroring
`FinalPackageDTO`: identities, state, counts,
open requirements, full report, carried summary)
and `FinalizeWorkflowResponse` (record + package).
No domain objects cross the wire; no new verdict,
score, ranking, or interpretation fields exist.

## Error/status mapping

Reused unchanged from 8.2: 401 auth, 403
denied/tenant-mismatch, 400 app input, 404 not-found
(no stored result/package/report), 409
transition/not-ready (reasons in details)/
stale/terminal, 422 shape errors, 503 unwired store
or infrastructure, 500 unexpected. Stale covers both
forged round linkage and obsolete client records;
terminal covers both terminal records and
package-row-backed second finalization.

## OpenAPI contract

Auto-generated schema lists the three paths with
operation names and models (locked by test) alongside
the existing thirteen.

## Intentionally unexposed capabilities

`load_current_result` stays an application/orchestration
primitive (report reads cover the client need — no
dedicated endpoint justified). Result-attached history
needs no new endpoint or model: round→report
references already ride the existing history read.
Compound analyze-and-finalize remains rejected — the
lifecycle stays analyze → persist → retrieve/review →
explicit finalize.

## History integration decision

No change. The existing history endpoint already
projects round linkage including report identities;
stored results slot into those references without a
second history model.

## Verification

- Focused Phase 8.5: 25/25
  (`test_compliance_stored_api.py` — finalize happy/
  not-ready/stale/unstored/double/unwired/malformed;
  package read/missing/unwired; report read/missing/
  malformed/unwired; cross-tenant finalize/package/
  report; unauthenticated/member/actor; privacy and
  no-verdict scans; route-boundary AST scan; OpenAPI
  path lock).
- Phase 8.1 (31) + 8.2 + 8.3 (32) + 7.1–7.5 + Phase 6
  + Phase 2–5 regressions pass unmodified. Full suite:
  1740 passed + 44 skipped (gated), 0 failures. No live
  Qdrant/OpenRouter/database execution claimed.

## Deliberately outside Phase 8.5

UI, provider wiring, evaluation, production
hardening, audit logging, new permissions beyond the
two reused ones.

## Files created / modified

- Created: `tests/unit/test_compliance_stored_api.py`,
  `docs/phases/phase-8-5-stored-path-http-exposure.md`.
- Modified (additive): `xportra/api/dependencies.py`
  (store field + wiring + passthrough + 503
  dependency), `xportra/api/schemas.py`
  (`FinalPackageResponse`, `FinalizeWorkflowResponse`),
  `xportra/api/compliance.py` (3 endpoints + analyze
  store passthrough).
- No Phase 1–7 behavior change; no application-core
  change; no prior test touched.
