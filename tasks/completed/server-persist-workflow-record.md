# Server-Persist the Compliance Workflow Record — Complete

Implements the single Phase 8 integration-blocker fix:
the compliance workflow record (`state`, `shipment_id`,
`supplied_evidence_ids`, `open_requirements`) is now
server-owned in PostgreSQL (`xportra.compliance_workflows`,
migration 012) instead of client-echoed only.

Scope honored: no workflow redesign, no transition-rule
changes, no score/verdict, no ORM, no shipment table,
no frontend contract/visual changes, no result-architecture
rewrite. Tenant isolation server-side throughout.

## What changed

- `migrations/012_compliance_workflows.sql` (+ `.down.sql`):
  tenant-scoped table, state CHECK over the 9 domain
  states, UUID[] reference columns, standard
  created_at/updated_at + trigger. No secondary index:
  the composite PK covers the identity lookup.
- `xportra/persistence/repositories.py`:
  `ComplianceWorkflowRepository`
  (`create_in_transaction` / `get` / `save_in_transaction`
  update-only).
- `xportra/application/result_store.py`:
  optional `workflows` repo; `create_workflow_record`
  (idempotent adopt on retry), `resolve_authoritative_workflow`
  (snapshot compare → `StaleAnalysisError`), `save_workflow_record`
  (update-only, fails closed when missing); result/package/round
  writes carry the workflow update in the same transaction.
  Without the repo the previous client-held behavior holds.
- `xportra/application/workflows.py`: start persists the begun
  row; all mutations load + verify + save; `supply_evidence`
  additionally requires tenant-owned recorded evidence when
  both boundaries are wired; `finalize_stored_package`
  resolves first (existing round anchor kept).
- `xportra/application/analysis.py`: `run_analysis` resolves
  the authoritative workflow before RAG when wired.
- `xportra/api/compliance.py`: the 7 mutating handlers pass
  configured stores (request/response shapes unchanged).
- `xportra/api/dependencies.py`: production wiring adds the
  workflow repository to the result store.
- `tests/unit/test_application_boundary.py`: one assertion
  updated for the intended new `_evidence_service`
  collaborator (statelessness intent preserved).

## Verification

- New `tests/unit/test_workflow_record_persistence.py`:
  15/15 passing (persistence across service instances,
  stale state/references/rounds rejection, unknown workflow,
  cross-tenant rejection, repeat-start convergence,
  legacy path pin, evidence ownership, store validation,
  migration 012 static structure).
- New `tests/integration/test_workflow_record_postgresql.py`:
  DATABASE_URL-gated HTTP end-to-end (2 skipped here —
  no live database; same gating as all DB suites).
- Required groups
  (`test_compliance_workflow`, `test_workflow_closure`,
  `test_cross_request_state`, `test_compliance_api`,
  `test_compliance_stored_api`, `test_result_store`,
  `test_result_store_migration`, `test_application_boundary`,
  `test_assessment_readiness`): green.
- Full backend: 1954 passed + 46 skipped (gated
  Postgres/Qdrant/OpenRouter-live), 0 failures.
- Frontend untouched: no `tsc`/`build` run required.

## Deferred (reported, not implemented)

- `requirement_id` on supply is still unlinked (no
  validation against `evidence_requirements`).
- Read-only projections (`status`/`history`/`package`)
  still render the submitted record; only mutating and
  stored paths anchor to server state.
- Shipment profile still never reaches the server (no
  shipment table per task constraints); frontend
  sessionStorage registry unchanged.
