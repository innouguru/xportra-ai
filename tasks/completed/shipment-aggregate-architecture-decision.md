# Shipment Aggregate Architecture Decision — Complete

Design/documentation task only. Documents the decision to introduce a
tenant-scoped first-class `Shipment` aggregate owning commercial
shipment/profile facts independently from compliance workflow/process
state.

## What changed

- `docs/decisions/ADR-0013-shipment-aggregate-boundary.md` (new):
  accepted architecture decision — aggregate boundary, minimum
  persistence boundary (tenant_id, shipment_id, case_id, product,
  origin_country, destination_country, quantity, unit, shipment_date),
  identity model, tenant boundary, `draft → bound → locked` lifecycle,
  workflow binding, API direction, input-resolution precedence,
  mutation rules, historical integrity, security, migration 013
  expectations, alternatives A–D, open questions OQ-S1–OQ-S6.
- `docs/decisions/README.md`: status 13 decisions as of 2026-10-07,
  ADR-0013 listed.
- `CURRENT_STATE.md`: shipment aggregate decision section appended.
- `ACTIVE_TASK.md`: this task recorded complete.

## What did not change

No migration 013, no `shipments` table, no repository/service/schema/
frontend/transition/test change. No commit or push performed by this
task unless project conventions require it.
