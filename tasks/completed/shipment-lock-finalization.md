# Shipment Lock on Finalization — Complete

Narrow lifecycle-consistency task. No state machine
redesign, no versioning/snapshots/delete semantics, no
FKs, no lock-as-completion-signal, no frontend change.
ADR-0013 open questions unaltered.

## What changed

- `xportra/persistence/repositories.py`:
  `ShipmentRepository.get_in_transaction` — row read
  inside the caller's transaction.
- `xportra/application/result_store.py`:
  `store_package_linkage` locks the finalizing
  workflow's shipment in the same transaction as the
  package linkage + terminal workflow row (new
  `_lock_shipment_in_transaction`): tenant-scoped
  resolve, case match, `bound → locked` through
  `ShipmentService.mark_locked`; unknown/cross-tenant
  → not-found, case mismatch / non-bound status →
  invalid input, already-`locked` reads as consistent
  terminal state. No new error type.

## Tests

- `tests/unit/test_shipment_lock_finalize.py` (new,
  14 tests): domain matrix (bound→locked ok;
  draft→locked, locked→bound, locked→locked rejected);
  success persists locked + terminal workflow + package
  on one shared transaction connection; package and
  workflow-save failures roll everything back
  (transactional fake boundary); package-conflict retry
  keeps terminal state without reopening; service-level
  second finalize → `TerminalWorkflowError` before any
  store write; unknown/cross-tenant/case-mismatch/draft
  fail closed.

## Verification

- Focused: 14 passed; related finalization/shipment/
  listing/workflow suites: 124 passed.
- Full backend: 2033 passed + 61 subtests, 0 failures.
- Frontend untouched (no run per task scope).
- Integration: 51 skipped (no `DATABASE_URL`; live
  transaction coverage not claimed). No packages
  installed.
