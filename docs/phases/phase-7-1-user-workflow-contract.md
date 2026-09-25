# Phase 7.1 — Compliance User Workflow Contract

**Status:** Complete and verified (2026-09-24)
**Phase:** Phase 7 — User Workflow
**Type:** First Phase 7 domain capability — pure workflow
coordinator over existing Phase 1–6 contracts; no API, no UI,
no persistence, no verdict

> This record describes what was actually implemented and verified.

## Objective

Define the domain-level workflow for moving through a
compliance case — shipment creation through evidence
submission, analysis, review, issue resolution, re-analysis,
and final assessment packaging — as a production domain
capability before any API or UI concerns:

```text
begin → provide_information → note_evidence_pending
    → record applicability outcome → run_analysis
    → submit_for_review → request_additional_evidence
    → supply_evidence → run_analysis (next round)
    → submit_for_review → finalize → assessment package
```

## Architecture decision

No suitable boundary existed: there is no Shipment domain
object (only shipment characteristics inside applicability
input), no workflow/application service, and no reusable
process-state model (existing statuses are record statuses,
not progression states). The smallest contract was therefore
created: `ComplianceWorkflowService` plus frozen
`ComplianceWorkflow` / `WorkflowAnalysisRound` /
`AssessmentPackage` in `xportra/domain/compliance_workflow.py`.

The service coordinates; it never determines applicability,
assessment, risk, action, authority, or verdicts; retrieves
nothing; calls no LLM; parses no model output; and builds no
second reasoning, evidence, citation, or audit system. Per
the project convention for additive domain boundaries (Phase
2+), the decision is recorded here rather than in an ADR —
no structural, storage, or cross-cutting change was made.

## Workflow states and transitions

Nine process-progression states (never regulatory truth —
`compliant`/`satisfied`/`applicable`/risk levels appear
nowhere in the state model):

- `created` → `information_provided` | `evidence_pending`
- `information_provided` → `evidence_pending` |
  `applicability_determined`
- `evidence_pending` → `applicability_determined`
- `applicability_determined` → `analysis_available` |
  `evidence_pending`
- `analysis_available` → `review_required` |
  `additional_evidence_requested`
- `review_required` → `additional_evidence_requested` |
  `assessment_package_ready`
- `additional_evidence_requested` → `reanalysis_required`
- `reanalysis_required` → `analysis_available`
- `assessment_package_ready` → (terminal)

Every mutating operation validates tenant, state membership,
and input shape; illegal transitions fail closed.

## Evidence / re-analysis loop

`request_additional_evidence` flags requirement IDs needing
action; `supply_evidence` records new evidence references and
requires re-analysis; each `run_analysis` appends a new round
(round index plus the existing deterministic report,
analysis, trace, and input-fingerprint IDs) and returns a new
workflow object — predecessors are never mutated, so every
pass is distinguishable through existing identities. No new
versioning system beyond the round counter. Shipment identity
is caller-supplied; evidence bytes live outside the contract
(recording stays persistence-backed); the workflow is pure
in-memory coordination for Phase 8 to expose.

## Phase 6 integration

`run_analysis` delegates to the completed
`ComplianceReasoningApplication.analyze_case` with
pass-through RAG controls — the Phase 6 result is preserved
by identity and recorded into the round. State and tenant
are validated before delegation, hence before any retrieval
or provider call. Phase 6 semantics untouched (no Phase 6
file modified).

## Final assessment package

`finalize` (from `review_required`, latest round only)
builds the `AssessmentPackage`: workflow/case/shipment
identity, the latest Phase 6 result and untouched Phase 3.5
summary by reference, round history, and a read-only
projection of requirements still carrying missing
information. Aggregation only — no verdict, score,
percentage, or reinterpretation.

## Invariants and failure semantics

Tenant/case isolation on every operation (cross-tenant and
cross-case results fail closed); deterministic-first
validation with zero-call proofs; provider/retrieval/
analysis failures propagate and never become compliance or
workflow-success states; no silent partial completion;
trace privacy preserved end to end.

## Verification

- Focused Phase 7.1: 32/32 (`test_compliance_workflow.py`
  — creation; full progression; invalid transitions;
  truth-separation; evidence loop incl. round
  distinguishability and frozen-predecessor proof; Phase 6
  delegation incl. identity preservation; isolation;
  deterministic-first and propagation failures; package
  authority/provenance/no-verdict proofs; framework-
  boundary AST checks incl. no-duplicate-logic scan).
- Phase 6 regression: 247/247 unmodified. Full suite: 1468
  passed + 37 skipped (gated), 0 failures. Live
  Qdrant/OpenRouter not executed, nothing claimed.

## Deliberately outside Phase 7.1

API endpoints, UI/notifications/frontend state, persistence
and migrations, ORM, Shipment object formalization, evidence
bytes handling, evaluation metrics, production hardening,
new providers/stores, package reopening after terminal
state (future work when scoped).

## Files created / modified

- Created: `xportra/domain/compliance_workflow.py`,
  `tests/unit/test_compliance_workflow.py`,
  `docs/phases/phase-7-1-user-workflow-contract.md`.
- Modified (additive only): `xportra/domain/__init__.py`
  (15 additive exports).
- No Phase 1–6 behavior file modified; no prior test touched.
