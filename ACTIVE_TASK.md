# ACTIVE_TASK.md — Current Active Task

## Task: Implement Durable Shipment Listing and History

**Status:** Complete (2026-10-07).

Read/discovery integration: tenant-scoped shipment
listing/detail reads compose stored Shipment rows with
latest-workflow summaries (`GET /compliance/shipments`,
`GET /compliance/shipments/{shipment_id}`); dashboard,
archive, workspace reload, and historical report are
server-backed with server-wins semantics; completion
remains workflow/package based; lock-on-finalize stays
future work.

Verification: backend unit 2019 passed + 61 subtests;
frontend 64 files / 439 tests, `tsc` clean, build
succeeds; integration gated (51 skipped, no
`DATABASE_URL`). Task record:
`tasks/completed/shipment-listing-history-implementation.md`.
Committed; push not requested.
