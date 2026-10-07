# ACTIVE_TASK.md — Current Active Task

## Task: Lock Shipment on Finalization

**Status:** Complete (2026-10-07).

Terminal finalization atomically transitions the bound
shipment to locked in the same transaction as package
linkage + terminal workflow row; failures roll back
together; retry/idempotency preserved; completion
semantics unchanged (`assessment_package_ready` +
package linkage).

Verification: focused 14 passed; full backend 2033
passed + 61 subtests; frontend untouched; integration
gated (51 skipped, no `DATABASE_URL`). Task record:
`tasks/completed/shipment-lock-finalization.md`.
Committed; push not requested.
