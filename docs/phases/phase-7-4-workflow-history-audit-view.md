# Phase 7.4 — Workflow History & Audit View

**Status:** Complete and verified (2026-09-24)
**Phase:** Phase 7 — User Workflow
**Type:** Read-only deterministic projection over 7.1–7.3
artifacts; no API, no UI, no events, no persistence

> This record describes what was actually implemented and verified.

## Objective

Project what a compliance workflow already retains into a
traceable timeline Phase 8 can expose — *what has happened
to this workflow, in what order, and what are its current
artifacts?* — without recording anything new:

```text
ComplianceWorkflow (+ optional latest result/package)
        ↓
WorkflowHistoryService.project (pure, read-only)
        ↓
WorkflowHistoryView (frozen, serializable)
```

## Underlying history sources (and only these)

Verified against `ComplianceWorkflow`: deterministic
creation identity; the bound shipment association;
`supplied_evidence_ids` in supply-append order (bare
identities — requirement linkage stays with the
authoritative recording service); `rounds` in
`round_index` order with recorded report/analysis/trace
IDs and input fingerprints; current `state` and
`open_requirements`. No transition log, no timestamps,
and no readiness-check log exist — intermediate states
are not retained once left, and the final package is
returned by `finalize()`, never stored on the workflow.

## Projection contract

`WorkflowHistoryView` (frozen: identities, state,
entries, evidence/requirement copies, round count,
latest report, summary flag, computed readiness,
identity-only `FinalPackageReference`) plus
`WorkflowHistoryEntry` (`sequence`, `kind`, ordered
`(label, value)` reference pairs — never contents) and
five kinds: `workflow_created`, `shipment_bound`,
`evidence_supplied`, `analysis_completed`,
`final_package_ready`. `WorkflowHistoryError`
fail-closed on malformed or mismatched inputs.

## Ordering semantics

Fixed grouped presentation order — creation → shipment →
supplies (supply order) → rounds (round order) → final
reference — with contiguous sequences. Within-group
order is authoritative recorded order; chronological
interleaving *across* groups is not recorded and
explicitly not claimed. No timestamps exist or are
shown (locked by key-scan test).

## Represented vs derived

Represented: creation, shipment association, supplies,
rounds, current state/requirements, supplied result and
package (each re-validated, shown by reference).
Derived: on-demand readiness via the Phase 7.3 service
(computed, never stored — a finalized workflow honestly
reports not-ready-for-finalization); the package
reference (identity only, no content copied).

## Provenance and privacy

Round entries preserve report/analysis/trace/fingerprint
references; evidence, summary-presence, and package
identities preserved; reasoning content never copied
(locked by test). Output carries only UUIDs, state
names, flags, and stored fingerprints — no bytes,
prompts, model output, secrets, or provider internals
(locked by scan tests). Phase 6.5 traces, the Phase 3.5
summary, and Phase 7.3 readiness stay authoritative.

## Isolation and purity

Tenant/case/workflow re-checked on every call; foreign
or spliced results/packages fail closed. The service is
stateless, takes no RAG/persistence parameters, mutates
nothing, and calls nothing but the injected (default
Phase 7.3) readiness calculation — verified by AST
boundary tests.

## Why no event store

There is nothing to store events *in* that the domain
does not already retain: rounds are the recorded
history, supplies keep append order, and states are
current-only by 7.1 design. An event table would invent
chronology the domain never observed.

## Verification

- Focused Phase 7.4: 35/35 (`test_workflow_history.py`
  — construction incl. minimal/immutable/fixed-shape/
  non-mutating; content incl. 7.2-bind integration and
  honest terminal readiness; grouped ordering incl.
  no-timestamp proof; provenance incl. no-content-copy;
  isolation incl. spliced artifacts; purity incl.
  statelessness and AST boundary scans; privacy scans).
- Phase 7.1 (32) + 7.2 (32) + 7.3 (33) + Phase 6 (247)
  + Phase 2–5 regressions pass unmodified. Full suite:
  1568 passed + 37 skipped (gated), 0 failures. No live
  execution claimed.

## Deliberately outside Phase 7.4

API/UI, event sourcing, history/audit tables,
timestamps, audit logging, notifications, activity
tracking, generic history frameworks, persistence,
evaluation, production hardening.

## Files created / modified

- Created: `xportra/domain/workflow_history.py`,
  `tests/unit/test_workflow_history.py`,
  `docs/phases/phase-7-4-workflow-history-audit-view.md`.
- Modified (additive only): `xportra/domain/__init__.py`
  (11 additive exports).
- No Phase 1–7.3 behavior file modified; no prior test
  touched.
