# ACTIVE_TASK.md — Current Active Task

## Task: Implement Shipment Persistence Boundary

**Status:** Complete (2026-10-07).

ADR-0013 v1 Shipment aggregate implemented: migration 013
tenant-scoped `shipments` table, domain Shipment +
lifecycle, repository + store boundary, workflow-start
persistence/binding with adopt-on-retry, applicability
shipment defaults, analysis bound-shipment verification,
frontend start-profile transport (no new UI).

Verification: backend unit 2001 passed + 61 subtests;
frontend 63 files / 427 tests, `tsc` clean, build
succeeds; integration gated (48 skipped, no
`DATABASE_URL`). Task record:
`tasks/completed/shipment-persistence-implementation.md`.
Committed; push not requested.
