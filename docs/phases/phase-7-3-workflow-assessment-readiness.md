# Phase 7.3 — Workflow-to-Assessment Readiness & Final Packaging Trigger

**Status:** Complete and verified (2026-09-24)
**Phase:** Phase 7 — User Workflow
**Type:** Deterministic readiness gate over the 7.1
finalization path; no API, no UI, no verdict, no score

> This record describes what was actually implemented and verified.

## Objective

Define the domain rule for when a compliance workflow is
sufficiently complete to produce its final assessment
package — *is this workflow ready to be finalized?* — as a
readiness gate, never a compliance decision engine:

```text
workflow + latest Phase 6 result
        ↓
AssessmentReadinessService.check (pure, deterministic)
        ↓
READY  →  existing final assessment package
NOT READY  →  structured readiness failure (no package)
```

## Architecture investigation outcome

`finalize()` (7.1) already required: `review_required`
state, a `ComplianceReasoningResult` of the matching
tenant/case, at least one round, and a report matching the
latest round. It did not require a bound shipment, did not
verify the round's analysis/trace linkage beyond the report
id, and accepted an absent decision summary. No duplicate
readiness rule existed — the gate extracts and extends that
validation rather than paralleling it. Per the Phase 2+
convention the decision is recorded here, not in an ADR.

## Readiness definition

`AssessmentReadiness` (`ready: bool` + `reasons:
tuple[ReadinessIssue, ...]`, frozen, serializable) with
seven deterministic issue codes: `tenant_mismatch`,
`case_mismatch`, `invalid_workflow_state`,
`missing_shipment_reference`, `no_analysis`,
`analysis_stale`, `analysis_integrity_failure`. None carries
verdict vocabulary (`compliant`/`pass`/`fail`/scores appear
nowhere — locked by test).

## Prerequisites (all required)

- caller tenant matches workflow and result tenants
- result case matches workflow case
- workflow state is `review_required`
- a shipment reference is bound (`shipment_id` present —
  value integrity comes from the 7.2 binding boundary)
- at least one completed analysis round
- result report equals the latest recorded round (freshness)
- latest-round linkage intact: result analysis ids, report
  analyses, and trace ids/fingerprints match the round;
  every trace references the result report and a result
  analysis; analyses and traces are tenant-scoped to the
  workflow

## Deliberately not prerequisites

- **Decision summary:** carried by reference and never
  recomputed; absence does not block (the 7.1 contract
  accepts `None`, locked by unmodified 7.1 tests).
- **Regulatory outcomes:** missing evidence, `unknown` /
  `not_satisfied` assessments, contradictions, and
  uncertainty never block — a package may be final as a
  process artifact while containing unresolved findings.

## Stale-analysis behavior

Evidence supplied after analysis moves the workflow to
`reanalysis_required` (wrong state → `invalid_workflow_state`);
a result whose report predates the latest round is
`analysis_stale`. Both fail readiness; a fresh
`run_analysis` plus review restores it. Freshness is a
workflow rule, not a compliance judgment.

## Finalization behavior

`finalize()` runs the gate first; NOT READY raises
`ComplianceWorkflowError` naming each `code: detail`
(no package, workflow state untouched). Package
construction is unchanged: latest Phase 6 result and
untouched Phase 3.5 summary by reference, round history,
read-only missing-information projection — no verdict,
score, percentage, ranking, or confidence.

## Failure semantics

Malformed inputs (bad tenant context, non-workflow,
malformed state, non-result) raise immediately — corrupt
state is never a readiness answer. Domain gaps return
`ready = False`. Provider/retrieval failures are
structurally impossible here (no calls exist on any path)
and continue to propagate as errors from `run_analysis`;
a failed analysis yields no result and therefore no
ready workflow.

## Isolation guarantees

Tenant/case/shipment/analysis/report/trace checks re-verify
ownership on every call; cross-tenant callers, foreign
results, spliced analyses/traces, and unbound shipments
fail closed. Trace `case_id` is intentionally *not*
compared to the workflow case: Phase 6.5 scopes traces to
requirement-level case views by design (verified against a
real pipeline result during implementation).

## Verification

- Focused Phase 7.3: 33/33 (`test_assessment_readiness.py`
  — ready + serializable + deterministic; each missing
  prerequisite; evidence iteration incl. duplicates;
  unresolved findings incl. field preservation; isolation;
  zero-call and no-partial-package proofs; package
  authority/provenance/no-verdict/determinism; seam and
  framework-boundary checks).
- Phase 7.1 (32) + 7.2 (32) + Phase 6 (247) + Phase 2–5
  regressions pass unmodified. Full suite: 1533 passed +
  37 skipped (gated), 0 failures. No live execution claimed.

## Deliberately outside Phase 7.3

API/UI, compliance decision/sufficiency/risk engines,
verdicts/scores, Phase 3.5/Phase 6 semantic changes,
persistence/migrations, ORM, generic workflow
infrastructure, evaluation, production hardening.

## Files created / modified

- Created: `xportra/domain/assessment_readiness.py`,
  `tests/unit/test_assessment_readiness.py`,
  `docs/phases/phase-7-3-workflow-assessment-readiness.md`.
- Modified (minimal): `xportra/domain/compliance_workflow.py`
  (`finalize` validates via the gate; optional
  `readiness_service` seam; package construction
  unchanged), `xportra/domain/__init__.py` (10 additive
  exports).
- No prior test touched; no Phase 1–7.2 behavior file
  modified beyond the `finalize` gate.
