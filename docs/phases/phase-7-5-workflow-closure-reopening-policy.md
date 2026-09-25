# Phase 7.5 — Workflow Closure/Reopening Policy

**Status:** Complete and verified (2026-09-24)
**Phase:** Phase 7 — User Workflow
**Type:** Explicit terminal-state rule; no API, no UI, no
new state, no verdict

> This record describes what was actually implemented and verified.

## Decision: permanent closure

`assessment_package_ready` is **permanently closed**.
There is no reopen transition, no second finalization,
and no package versioning. This resolves the ambiguity
left open in Phase 7.1 ("package reopening after terminal
state (future work when scoped)").

Why closure, not reopening:

- The canonical Phase 7 journey (`development_phases.md`)
  places iteration ("resolve issues / upload additional
  evidence") strictly *before* the final assessment
  package. No requirement authorizes post-finalization
  mutation.
- Reopening would demand a new transition plus package
  versioning/supersession the domain deliberately lacks;
  inventing either would violate the no-new-vocabulary
  constraint.
- Immutability already freezes finalized instances, so
  closure is declared, not bolted on: the terminal state
  has zero outgoing edges and every mutating operation
  already failed closed from it.
- Closure is finding-neutral: it applies identically
  whether findings are satisfied, unknown,
  not-satisfied, contradictory, or uncertain. Compliance
  findings never drive lifecycle policy.

Per the Phase 2+ convention the decision is recorded
here, not in an ADR — no structural, storage, or
cross-cutting change was made.

## Exact domain semantics

- New evidence after finalization: `supply_evidence`
  (and the 7.2 `supply_to_workflow` handoff) raise
  `ComplianceWorkflowError`; nothing is recorded.
- Re-analysis after finalization: `run_analysis` raises
  before any retrieval/provider call (zero-call locked).
- Return to `reanalysis_required`: impossible — no
  outgoing transition exists (machine-shape locked).
- Second `finalize()`: raises via the 7.3 readiness gate
  (`invalid_workflow_state`); no second package.
- Causing operation: none exists. Reopening is not
  automatic *or* explicit — it is absent.
- Previous package: remains valid and untouched; the
  finalized instance is immutable, so its package
  linkage cannot degrade. History projection is
  unchanged.
- Continuation path: a fresh `begin()` starts a new
  progression (same deterministic identity for the same
  scope, fresh empty rounds) while the finalized
  snapshot persists unaltered.

## Contract added

`WORKFLOW_TERMINAL_STATES = frozenset({
assessment_package_ready })` plus
`ComplianceWorkflowService.is_closed(workflow, *,
tenant_id) -> bool` (read-only, tenant-validated,
fail-closed like every operation). One additive export.
No transition, state, or message changed.

## Tenant isolation

Terminal rejections validate tenant first: cross-tenant
supply, analysis, finalization, and closure queries on
a finalized workflow raise before any state logic, with
zero provider calls.

## History implications

None — the 7.4 projection already represents terminal
state plus the package reference by identity. No 7.4
file, test, or doc required changes.

## Verification

- Focused Phase 7.5: 19/19 (`test_workflow_closure.py`
  — terminal rejection of all 7.1 ops, second
  finalize, 7.2 supply/switch handoff, zero-call
  re-analysis; no-mutation and package-preservation
  proofs; `is_closed`/constant/machine-shape locks;
  finding-neutrality; cross-tenant closure isolation;
  fresh-progression continuation).
- Phase 7.1 (32) + 7.2 (32) + 7.3 (33) + 7.4 (35) +
  Phase 6 (247) + Phase 2–5 regressions pass
  unmodified. Full suite: 1587 passed + 37 skipped
  (gated), 0 failures. No live execution claimed.

## Deliberately outside Phase 7.5

Reopen transitions, package versioning, API/UI,
persistence, events, timestamps, evaluation,
production hardening, verdicts/scores.

## Files created / modified

- Created: `tests/unit/test_workflow_closure.py`,
  `docs/phases/phase-7-5-workflow-closure-reopening-policy.md`.
- Modified (minimal): `xportra/domain/compliance_workflow.py`
  (terminal-states constant + `is_closed`; no behavior
  change), `xportra/domain/__init__.py` (1 additive
  export).
- No prior test touched; no other behavior file
  modified.
