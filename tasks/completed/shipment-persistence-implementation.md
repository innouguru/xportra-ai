# Shipment Persistence Implementation — Complete

Implements the ADR-0013 v1 Shipment aggregate as
server-owned, durable, tenant-scoped persistence. No
architectural decision reopened; OQ-S1–OQ-S6 remain open.

## What changed (backend)

- `migrations/013_shipments.sql` (+ `.down.sql`): `xportra.shipments`
  with `PRIMARY KEY (tenant_id, shipment_id)`, profile facts,
  `draft | bound | locked` status, standard timestamps/trigger,
  tenant+case index. No FK from `compliance_workflows` (documented:
  would reject existing rows on real data); no profile columns there.
- `xportra/domain/shipment.py` (new): `Shipment`, `ShipmentService`
  (create/bind/lock, draft-only edits), `shipment_from_record`;
  exported via `xportra/domain/__init__.py`.
- `xportra/persistence/repositories.py`: `ShipmentRepository`
  (create/get/save, tenant-scoped, update-only save).
- `xportra/application/result_store.py`: shipment boundary on
  `ComplianceResultStore` (single-transaction
  `create_shipment_with_workflow_record`, adopt-on-retry with
  stale (409) on profile/case mismatch), `store_supports_shipment_records`.
- `xportra/application/workflows.py`: `start_workflow` accepts an
  optional profile mapping — persist-then-bind against the stored row;
  identity-only starts resolve the stored row (unknown → 404,
  locked → 409 terminal); legacy client-held path preserved where no
  shipment boundary is configured.
- `xportra/application/assessments.py`: `determine_applicability`
  accepts `shipment_id` — explicit facts win, stored shipment
  supplies omitted groups, unknown → 404.
- `xportra/application/analysis.py`: bound-shipment resolution
  verified before analysis (cases never rewritten).
- `xportra/api/schemas.py`: `ShipmentProfileSchema`,
  `StartWorkflowRequest.shipment`, `ApplicabilityRequest.shipment_id`.
- `xportra/api/compliance.py`: start/applicability handlers forward
  the new fields; `xportra/api/dependencies.py` wires
  `ShipmentRepository` into the result store.

## What changed (frontend)

- `frontend/src/api/workflows.ts`: `StartWorkflowInput.shipment`.
- `frontend/src/features/shipment/NewShipmentPage.tsx`: sends the
  already-collected profile on start. No new UI, routes, or concepts.

## Tests

- `tests/unit/test_shipment_persistence.py` (new, 47 tests): domain,
  start/retry/mismatch/tenant/lifecycle, applicability precedence,
  analysis guards, migration SQL structure, HTTP start/retry/forgery.
- `tests/integration/test_shipment_postgresql.py` (new, gated):
  live round-trip + rollback (skipped without `DATABASE_URL`).
- `tests/unit/test_application_boundary.py`: collaborator-set
  assertion extended with `_shipments` (intent unchanged).

## Verification

- Backend unit: 2001 passed + 61 subtests, 0 failures.
- Frontend: 63 files / 427 tests passing; `tsc --noEmit` clean;
  `npm run build` succeeds.
- Integration: 48 skipped (no `DATABASE_URL`; no live coverage
  claimed). No packages installed.
