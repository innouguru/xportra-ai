# Phase 6.2 — Compliance Analysis Report Composition

**Status:** Complete and verified (2026-09-24)
**Phase:** Phase 6 — Compliance Reasoning & Decision Support
**Type:** Case-level composition of existing per-requirement
analyses plus existing deterministic decision state — no new
verdict, no prose inference, no API, no workflow

> This record describes what was actually implemented and verified.

## Objective

Compose multiple Phase 6.1 `ComplianceAnalysis` results into a
structured case-level report for later API/UI consumption:

```text
ComplianceAnalysis[]            (Phase 6.1)
    + decision_summary dict     (Phase 3.5, authoritative)
        ↓
ComplianceReportService.compose (deterministic)
        ↓
ComplianceAnalysisReport        (ordered analyses + aggregates
                                 + referenced decision state)
```

Composition, not a decision engine.

## Authoritative case-level state

The existing `ComplianceDecisionSummaryService` (Phase 3.5)
dict — applicability/risk/action sections as that service
computed them — is the authoritative case-level decision
state. Phase 6.2 references it by carrying the identical
object; it never recomputes risk, actions, or applicability
from explanations. No overall compliance status field exists
anywhere in the report — a new independent verdict algorithm
is structurally unrepresentable.

## Aggregate semantics (outcomes only, never prose)

Counts derive exclusively from `analysis.applicability` /
`analysis.assessment`:

- `applicable_count` — applicability `applicable` (any
  assessment).
- `satisfied_count` — applicable **and** satisfied
  (`not_applicable` can never satisfy).
- `not_satisfied_count` — applicable and not satisfied.
- `unknown_count` — applicable with unknown assessment, plus
  unknown applicability (position unknown for any
  deterministic reason; `unknown` stays `unknown`).
- `not_applicable_count` — applicability `not_applicable`.
- A defensive partition check fails closed if the four
  outcome buckets ever stop summing to the total.

Rollups preserve requirement association: missing-information
entries are `(requirement_id, items)` pairs;
`uncertain_requirement_ids` holds `uncertain` certainty only
(unknown-certainty requirements stay visible via
`unknown_count` + per-analysis entries — no collapse of
missing/unknown/uncertain/not-satisfied);
`requirements_with_conflicting_evidence` plus a total
conflicting-reference count.

## Ordering semantics

Analyses ordered by ascending stringified `requirement_id`
(the Phase 3.x convention) — deterministic, documented,
independent of insertion or database order. Report identity is
uuid5 over tenant + case + ordered requirement and analysis
IDs.

## Duplicate/inconsistency behavior (fail closed)

Duplicate requirement identity is rejected explicitly — never
silently merged or dropped. Cross-tenant analyses, cross-
tenant decision summaries, non-`ComplianceAnalysis` items,
non-sequence input, non-UUID case identity, and malformed
fingerprints/summaries all raise `ComplianceReportError`.
Empty input yields a valid empty report (zero counts,
`is_empty`, no verdict invented).

## Evidence/provenance preservation

Analysis objects are preserved by reference (`assertIs`-
proven): typed evidence/knowledge/source references intact,
requirement association intact, citation labels verbatim.
The 6.1 integrity guarantees are reused, not reimplemented.

## Verification

- Focused Phase 6.2: 39/39 (`test_compliance_analysis_report.py` —
  single/multiple/ordering; all statuses incl. mixed exact
  counts; no-inference proofs; missing/uncertainty rollups;
  reference preservation incl. cross-association;
  decision-summary reference + aggregate independence +
  real-service interop; duplicates; tenant/case identity;
  empty/all-not-applicable/all-unknown; malformed classes;
  framework-boundary AST checks).
- Phase 6.1 regression + Phase 2–5 regression: 592/592.
  Full suite: 1263 passed + 37 skipped (gated), 0 failures.
  No prior test touched. Live Qdrant/OpenRouter not executed,
  nothing claimed.

## Explicitly deferred

API endpoints, Phase 7 workflow, UI, verdict engines, score
calibration, multi-case rollups, agents, memory, retries.

## Files created / modified

- Created: `xportra/domain/compliance_report.py`,
  `tests/unit/test_compliance_analysis_report.py`,
  `docs/phases/phase-6-2-compliance-analysis-report-composition.md`.
- Modified (additive only): `xportra/domain/__init__.py`
  (imports + `__all__`).
- No Phase 1–6.1 behavior file modified; no prior test
  touched.
