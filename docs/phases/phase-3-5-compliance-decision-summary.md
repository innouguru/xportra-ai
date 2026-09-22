# Phase 3.5 — Compliance Decision Summary

**Status:** Complete and verified (2026-09-22)
**Phase:** Phase 3 — Applicability Engine
**Type:** Orchestration / representation boundary only — no new compliance rules

> This record describes what was actually implemented and verified in Phase 3.5.

## Objective

Introduce the next minimal deterministic domain boundary that condenses the
existing **Applicability → Risk → Action** outputs into a single structured
**Compliance Decision Summary** suitable for consumption by future
application/API layers.

The boundary adds representation, not policy. It decides nothing on its own:
applicability, risk, and action recommendation remain owned by the services
that already produce them. Retrieval, RAG, LLM reasoning, embeddings, vector
search, document retrieval, external regulatory APIs, persistence, UI work, and
new compliance rules are explicitly out of scope.

## Why this belongs in Phase 3.5

Phase 3.0 through Phase 3.4 completed the executable domain pipeline. Each
stage returns its own structure, so a caller must currently know how to call
three services and stitch three outputs together. Phase 3.5 closes that gap
with a single read-only join that preserves every existing outcome and every
existing uncertainty, without becoming a workflow engine.

## Implementation

### Abstraction created

`ComplianceDecisionSummaryService` in `xportra/domain/ingestion.py`.
It is deliberately small: two public entry points, both returning the same
summary shape, plus private helpers that only assemble and order
already-computed data.

### Constructor

```python
ComplianceDecisionSummaryService(
    risk_service: ComplianceRiskService | None = None,
    risk_to_action: RiskToActionIntegration | None = None,
)
```

Both collaborators are optional and default to the existing Phase 2.9 and
Phase 3.4 implementations. Injection exists only for testability; no behaviour
is configurable.

### Public methods

**`summarize(cases, *, tenant_id)`** — the primary boundary.

1. Delegates risk classification to `ComplianceRiskService.classify()`
   (the source of truth for risk).
2. Delegates action recommendation to
   `RiskToActionIntegration.recommend_from_risk()`, which delegates to
   `ComplianceActionRecommendationService.recommend()` (the source of truth for
   actions).
3. Reads applicability, assessment, and evidence directly from the supplied
   cases.
4. Joins the three views per requirement ID and composes the summary.

No rule is re-implemented at any step.

**`summarize_from_applicability(applicability_report, *, tenant_id)`** — the
pipeline convenience entry point. It runs the existing Phase 3.4
`full_pipeline()` for the risk and action sections and takes applicability from
the report itself. Because a report carries no assessment or evidence, those
fields remain `None` rather than being assumed.

### Data represented

One fixed, deterministic shape with no optional top-level keys:

| Key | Content |
| --- | --- |
| `tenant_id` | The validated tenant UUID, propagated unchanged |
| `context_fingerprint` | Existing fingerprint from the input, or `None` when the input carries none |
| `status` | Constant `"decision_summary"` (same convention as `"determined"` / `"complete"` / `"recommendation"`) |
| `applicability` | `total_requirements`, `applicable_count`, `not_applicable_count`, `unknown_count`, and the ordered per-requirement results |
| `risk` | `classified_count`, `by_state` counts, and the verbatim `ComplianceRiskService` results |
| `actions` | `recommendation_count`, `by_type` counts, and the verbatim `ComplianceActionRecommendationService` recommendations |
| `unknown_states` | Every uncertainty observable from the input, each as `{requirement_id, kind, reason}` |
| `requirements` | One row per requirement ID joining applicability, assessment, evidence, risk state, and action type |

The `requirements` rows are the join that did not previously exist:

```text
requirement_id | requirement_text | applicability_outcome | applicability_reason
               | assessment_outcome | assessment_reason | evidence_present
               | risk_state | action_type
```

`evidence_present` is `True`/`False` for a case that carries an evidence
collection, and `None` for input that does not carry evidence at all (a pure
applicability report). `risk_state` and `action_type` are `None` when the
existing services legitimately produce no row — most importantly for
`not_applicable`, which the existing risk and action rules exclude.
`risk.results` and `actions.results` are the existing service outputs verbatim,
only ordered; no value in them is recomputed or rewritten.

## Unknown / insufficient-state behavior

Uncertainty is preserved, never resolved. `unknown_states` is an explicit,
additive index of every uncertainty already present in the inputs, using four
descriptive kinds. Kinds are labels, never decisions:

| kind | Recorded when |
|---|---|
| `applicability_unknown` | the requirement's applicability outcome is `unknown` |
| `assessment_unknown` | an applicable requirement's assessment outcome is `unknown` |
| `missing_evidence` | an applicable, assessment-unknown case matches the existing services' `_is_missing_evidence` semantics (the `required evidence absent` assessment reason or an empty evidence list) |
| `risk_unknown` | the existing risk service itself classified the requirement's state as `unknown` |

Guarantees:

- applicability `unknown` stays `unknown`; it is never counted as applicable or
  not_applicable.
- assessment `unknown` stays `unknown` and is never upgraded to a verdict.
- `missing_evidence` mirrors the existing services' semantics exactly, matching
  the `medium` / `provide_missing_evidence` outcomes those services already
  produce for the same case, so the summary never contradicts its own risk and
  action sections. Evidence presence remains separately visible via
  `evidence_present`.
- A pure applicability report carries no assessment or evidence, so
  `assessment_outcome` and `evidence_present` stay `None` — nothing is invented
  to make the summary look complete.
- No new risk levels, action types, or outcome values are introduced anywhere.

## Determinism

Identical input always produces an identical summary. Every section is sorted
by requirement ID (`applicability.results`, `risk.results`, `actions.results`,
`requirements`, and `unknown_states` by requirement ID then kind), count
dictionaries use sorted keys, and explanations are only ever copied from the
existing services' fixed strings. No timestamps, random values, or
environment-dependent values enter the output. The service is read-only,
in-memory, performs no persistence, and makes no external calls.

## Tenant preservation

`tenant_id` must be a UUID and appears as the summary's top-level tenant
identity. Case- and report-level tenant checks are delegated to the existing
validation (`ComplianceRiskService._validate_case` via `classify()`, and the
Phase 3.3/3.4 tenant checks via the pipeline), so input belonging to another
tenant raises `ComplianceSummaryValidationError` and never contributes to a
summary. Summaries for different tenants are built independently and share no
state.

## Implementation notes

Two pre-existing shape-assumption defects in Phase 3.3/3.4 helper code were
found while verifying the real end-to-end flow and minimally fixed, because the
summary boundary could not run over genuine pipeline output otherwise:

- `RiskToActionIntegration._rebuild_cases_from_risk()` and
  `ApplicabilityToRiskIntegration._build_cases()` used
  `original.get("requirement", {})`, which returns `None` (not `{}`) when the
  key exists with a `None` value, crashing real applicability results.
- Real applicability results carry `requirement_id` at the top level of each
  result rather than nested under `requirement`; the readers now accept both
  shapes.

No rules, outcomes, or public behavior of the existing services changed; all
Phase 3.0–3.4 tests pass unmodified.

## Tests

Focused module: `tests/unit/test_compliance_decision_summary.py` — 16 tests,
following the existing Phase 3.x conventions (`unittest`, isolated per-test
fixtures, deterministic UUIDs).

| # | Required scenario | Test |
|---|---|---|
| 1 | complete applicable case | `test_complete_applicable_case` |
| 2 | mixed applicable/not-applicable | `test_mixed_applicable_and_not_applicable` |
| 3 | unknown applicability | `test_unknown_applicability_preserved` |
| 4 | unknown assessment | `test_unknown_assessment_preserved` |
| 5 | missing evidence | `test_missing_evidence_distinguishable` |
| 6 | high-risk case | `test_high_risk_case` |
| 7 | medium-risk case | `test_medium_risk_case` |
| 8 | low-risk case | `test_low_risk_case` |
| 9 | recommended actions preserved | `test_recommended_actions_preserved` |
| 10 | multiple requirements, deterministic ordering | `test_multiple_requirements_deterministic_ordering` |
| 11 | tenant identity preserved | `test_tenant_identity_preserved` |
| 12 | deterministic identical-input output | `test_deterministic_identical_input` |
| 13 | empty-input behavior | `test_empty_input_behavior` |
| 14 | existing risk/action services unchanged | `test_existing_services_remain_unchanged` |
| 15 | end-to-end Applicability → Risk → Action → Summary | `test_end_to_end_real_services_flow` |
| + | input validation | `test_input_validation` |

Notable assertions:

- Test 9 compares `summary["actions"]["results"]` byte-for-byte against both
  `ComplianceActionRecommendationService.recommend()` and
  `RiskToActionIntegration.recommend_from_risk()`, proving the summary copies
  rather than rewrites recommendations.
- Test 10 feeds the same cases in two different orders and asserts identical
  serialized summaries.
- Test 14 reads the module source and asserts the new service name is absent
  from `ComplianceRiskService` and `ComplianceActionRecommendationService`
  bodies, that every `state = "..."` literal is one of
  `{high, medium, low, unknown}`, and that the action-type literals are exactly
  `{address_requirement, no_action_required, provide_missing_evidence,
  review_requirement}` — i.e. no new risk levels or action types were invented.
- Test 15 runs the real `ComplianceApplicabilityService`,
  `ApplicabilityToRiskIntegration`, `RiskToActionIntegration`, and
  `ComplianceDecisionSummaryService` over a real applicability report and
  asserts the summary's counts agree with the report's counts.

## Verification results

| Run | Command | Result |
|---|---|---|
| Baseline before Phase 3.5 tests | `python -m pytest tests/unit` | **186 passed** |
| Focused Phase 3.5 | `python -m pytest tests/unit/test_compliance_decision_summary.py -v` | **16 passed**, 0 failures, 0 errors |
| Full unit regression | `python -m pytest tests/unit` | **202 passed**, 0 failures, 0 errors |

202 = 186 baseline + 16 new Phase 3.5 tests. No pre-existing test was changed
or skipped. PostgreSQL-backed integration tests were not run because
`DATABASE_URL` is not configured in the current environment (unchanged from
Phase 3.4).

## Files changed

| File | Change |
|---|---|
| `xportra/domain/ingestion.py` | Added `ComplianceDecisionSummaryService`; minimal robustness fixes in `ApplicabilityToRiskIntegration._build_cases()` and `RiskToActionIntegration._rebuild_cases_from_risk()` (see Implementation notes). No existing class, method signature, rule, or outcome was altered. |
| `tests/unit/test_compliance_decision_summary.py` | New — 16 focused tests |
| `docs/phases/phase-3-5-compliance-decision-summary.md` | New — this record |
| `ACTIVE_TASK.md` | Updated to Phase 3.5 |
| `CURRENT_STATE.md` | Updated through Phase 3.5 |

No database schema, migration, configuration, dependency, API, or
application-layer file changed.

## Deferred functionality

Deliberately not implemented in Phase 3.5:

- No API/HTTP exposure of the summary (no new endpoint or schema).
- No persistence of summaries; the boundary is read-only and in-memory.
- No regulatory scoring, verdict, or confidence value of any kind.
- No retrieval, RAG, embeddings, vector search, chunking, reranking, agents, or
  LLM reasoning.
- No external regulatory API integration.
- No UI.
- No generalized workflow engine or pluggable pipeline framework.

Phase 3.5 is complete. Phase 3.6 has **not** started.
