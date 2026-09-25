# Phase 8.3 — Workflow/Result Transfer-or-Store Contract (Completed 2026-09-24)

Documented and testable cross-request answer: workflow
records transfer client-side today; deterministic inputs
reconstruct from authoritative records; live results are
in-session only with round-linkage stale protection;
terminal closure and tenant isolation hold across
transfers; concurrency is safe through server
statelessness. Result persistence specified but
deferred (only lawful form is normalized tables —
disproportionate and DB-untestable here). Actor subject
threaded end-to-end. Mirrors `ACTIVE_TASK.md`; full
record in
`docs/phases/phase-8-3-workflow-result-transfer-or-store-contract.md`.

## Scope delivered

- `get_request_actor` + actor threading across all 13
  compliance routes; tenant/role derivation unchanged.
- `tests/unit/test_cross_request_state.py`: 32 tests.
- Finalize/package/report endpoints remain blocked
  (reported with unblock condition); no fake
  persistence created.

## Acceptance

Focused 32/32; Phase 8.1 (31) + 8.2 (29) + 7.1–7.5
(151) + Phase 6 (247) + Phase 2–5 regressions pass;
full suite 1679 passed + 37 skipped (gated), 0
failures. No prior test weakened. No UI or evaluation
built.
