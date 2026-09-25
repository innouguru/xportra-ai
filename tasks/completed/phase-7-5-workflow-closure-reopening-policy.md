# Phase 7.5 — Workflow Closure/Reopening Policy (Completed 2026-09-24)

Terminal rule made explicit: `assessment_package_ready`
is permanently closed — no reopen transition, no second
finalization, no package versioning. Declared via
`WORKFLOW_TERMINAL_STATES` + `is_closed`; behavior
already fail-closed, now locked. Mirrors `ACTIVE_TASK.md`;
full record in
`docs/phases/phase-7-5-workflow-closure-reopening-policy.md`.

## Scope delivered

- `compliance_workflow.py` (minimal): terminal-states
  constant + tenant-validated `is_closed` predicate; one
  additive export; zero behavior change.
- `tests/unit/test_workflow_closure.py`: 19 tests.
- Continuation after finalization is a fresh progression;
  prior packages stay valid; history model unchanged.

## Acceptance

Focused 19/19; Phase 7.1 (32) + 7.2 (32) + 7.3 (33) +
7.4 (35) + Phase 6 (247) + Phase 2–5 regressions pass;
full suite 1587 passed + 37 skipped (gated), 0 failures.
No prior test weakened. No API, UI, persistence, events,
or evaluation built. With 7.5 the workflow contract is
closed: **Phase 7 COMPLETE**, Phase 8 may proceed.
