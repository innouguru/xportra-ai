# Shipment Listing and History Implementation — Complete

Read/discovery integration only. No new aggregate, migration,
state machine change, versioning, snapshots, FKs, delete
semantics, or lock-on-finalize. ADR-0013 unchanged.

## What changed (backend)

- `xportra/persistence/repositories.py`: `ShipmentRepository`
  gains tenant-scoped `list_for_tenant` (newest-first,
  limit/offset incl. unbounded) + `count_for_tenant`;
  `ComplianceWorkflowRepository` gains `list_for_shipment`
  (recency order; multiplicity across cases preserved).
- `xportra/application/result_store.py`: listing reads
  (`list_shipments` with timestamps, `count_shipments`,
  `get_shipment_entry`, `list_workflows_for_shipment`) +
  `store_supports_shipment_listing`.
- `xportra/application/shipments.py` (new):
  `ShipmentListingService` — paginated/filtered list and
  detail composition; completion = terminal workflow state
  with package linkage (never shipment `locked`); drafts
  surface with `workflow: null`.
- `xportra/application/dtos.py` (+ `__init__.py`):
  `ShipmentWorkflowSummaryDTO`, `ShipmentItemDTO`,
  `ShipmentListDTO`.
- `xportra/api/schemas.py` + `compliance.py`:
  `GET /compliance/shipments` (limit/offset/status,
  existing permission + error conventions) and
  `GET /compliance/shipments/{shipment_id}` (404 for
  unknown/cross-tenant).

## What changed (frontend)

- `frontend/src/api/shipments.ts` (new): list/detail fetch
  + `toShipmentEntry` adapter; server refreshes the device
  cache (server wins); 404 detail reads as null.
- `lib/shipments.ts`: entry record nullable (drafts honest);
  device-local forgotten-set; `forgetShipment` stays
  hide-only and now hides server rows too.
- Dashboard, archive, workspace reload, historical report
  resolve the durable list; workspace adopts the server
  record over stale snapshots and binds drafts through the
  existing start endpoint; report rehydration untouched.
  No redesign, no new screens, no route changes.

## Tests

- `tests/unit/test_shipment_listing.py` (new, 18 tests):
  ordering, tenant scope, pagination, status filter,
  terminal-without-package, bound-completed, multiplicity,
  detail/404/cross-tenant, unconfigured store, HTTP
  list/detail/pagination/filter.
- `tests/integration/test_shipment_listing_postgresql.py`
  (new, gated): live list/detail/isolation/rollback.
- Frontend: `api/shipments.test.ts` (new); dashboard,
  archive, workspace (+3 durable-resume tests), and
  historical report (+1 server-resolution test) suites
  migrated to the server source with empty-registry and
  server-wins coverage; nothing weakened.

## Verification

- Backend unit: 2019 passed + 61 subtests, 0 failures.
- Frontend: 64 files / 439 tests passing;
  `tsc --noEmit` clean; `npm run build` succeeds.
- Integration: 51 skipped (no `DATABASE_URL`; no live
  coverage claimed). No packages installed.
