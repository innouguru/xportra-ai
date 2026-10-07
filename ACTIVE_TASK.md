# ACTIVE_TASK.md — Current Active Task

## Task: Shipment Lifecycle Audit and Hardening

**Status:** Complete (2026-10-07).

End-to-end audit of the persisted shipment lifecycle
and API/frontend contract with three minimal fixes:
stored-path 503 for unwired listing reads, bounded
full-window discovery fetches, single-pass list
composition. All ten audit questions verified holding;
no migration, no redesign, no new features.

Verification: backend 2034 passed + 61 subtests;
frontend 64 files / 439 tests, `tsc` clean, build
succeeds; integration gated (51 skipped, no
`DATABASE_URL`). Task record:
`tasks/completed/shipment-lifecycle-audit-hardening.md`.
Committed; push not requested.
