# Phase 3.3 — Applicability to Risk Integration

> Status: Implemented and verified — 2026-09-21
> This document was recorded during the phase-documentation reorganization. It
> describes the actual Phase 3.3 implementation and test results, which were
> verified at implementation time and left unchanged.

## Objective

Phase 3.3 establishes the deterministic boundary between the applicability
layer (Phase 3.1 / Phase 3.2) and the risk/priority layer (Phase 2.9).

The conceptual flow is:

```
Applicability Determination (Phase 3.1 / 3.2)
        ↓
Applicability → Risk Integration            ← Phase 3.3
        ↓
Compliance Risk Classification (Phase 2.9)
        ↓
Action Recommendation (Phase 3.0)
```

Before this phase, applicability results produced by
`ComplianceApplicabilityService.determine()` could not be consumed directly by
`ComplianceRiskService.classify()`, because the risk service expects compliance
**case** dictionaries with `requirement`, `applicability`, `assessment`, and
`evidence` members. Phase 3.3 supplies that translation without duplicating or
changing any risk logic.

## Integration boundary introduced

`ApplicabilityToRiskIntegration` converts an applicability report into the case
format expected by `ComplianceRiskService` and delegates classification to the
existing service.

### Constructor

```python
ApplicabilityToRiskIntegration(risk_service: ComplianceRiskService | None = None)
```

- Accepts an optional injected `ComplianceRiskService`; when omitted, the
  existing service is constructed internally.
- Injection exists so tests can prove delegation rather than reimplementation.

### Core method

```python
classify_from_applicability(
    applicability_report: dict[str, Any],
    *,
    tenant_id: UUID,
) -> list[dict[str, Any]]
```

- **Input:** an applicability report produced by
  `ComplianceApplicabilityService.determine()` plus the caller's `tenant_id`.
- **Output:** the risk classification list produced by the existing
  `ComplianceRiskService.classify()` — no new output shape is invented.
- **Delegation:** all classification rules remain inside
  `ComplianceRiskService`; Phase 3.3 never re-implements risk logic.

### Report-to-case translation

`_build_cases()` maps each report result to a case dictionary:

| Case field | Source |
|---|---|
| `tenant_id` | the validated caller `tenant_id` |
| `requirement.id` / `text` / `type` | `result["requirement"]` |
| `applicability.outcome` | `result["outcome"]` |
| `applicability.reason` | `result["reason"]` (default `"determined"`) |
| `assessment.outcome` | fixed `"unknown"` |
| `assessment.reason` | fixed `"assessment not yet performed"` |
| `evidence` | fixed empty list |
| `context_fingerprint` | `report["context_fingerprint"]` |

Because Phase 3.3 performs no assessment of its own, every translated case
carries an explicit `unknown` assessment and no evidence. Phase 3.3 therefore
never invents an assessment outcome and never infers evidence.

Report entries are skipped only when their outcome is outside
`{applicable, not_applicable, unknown}` or when the requirement has no `id`.
Skipping never rewrites or guesses an outcome.

## Reuse of `ComplianceRiskService`

- Phase 3.3 wraps the existing risk service; it does not replace, subclass, or
  modify it.
- The delegated service remains the single source of truth for risk states
  (`high`, `medium`, `low`, `unknown`) and for explanation strings.
- Verified by a focused test that runs the integration path and a direct
  `ComplianceRiskService.classify()` call over the same built cases, then
  asserts the results are identical.
- With the Phase 2.9 rules and the translation above, a translated `applicable`
  case (unknown assessment, no evidence) classifies as `medium` with the
  explanation `unknown with missing required evidence`.


## State preservation

### `applicable`

- Translated into a case and classified by the existing risk service.
- The applicability outcome itself is never modified.

### `not_applicable`

- Preserved as `not_applicable` in the constructed case.
- Excluded from risk classification, matching existing risk-service semantics
  (`ComplianceRiskService` classifies only case dictionaries whose applicability
  outcome is `applicable`).
- Never silently converted into an applicable requirement.

### `unknown`

- Preserved as `unknown` in the constructed case.
- Never treated as `applicable` and never treated as `not_applicable`.
- Because the existing risk service classifies only `applicable` cases, an
  unknown applicability outcome produces no risk row rather than a guessed one.
- No state is upgraded, resolved, or inferred to make the pipeline appear
  complete.

## Unknown applicability handling

- Unknown applicability is carried across the boundary untouched; the
  integration introduces no defaulting, inference, or fallback rule that would
  resolve it.
- Focused tests assert that an all-`unknown` report and an
  all-`not_applicable` report each produce an empty risk list rather than
  fabricated risk states.
- A mixed report containing `applicable`, `not_applicable`, and `unknown`
  outcomes classifies only the `applicable` requirements.

## Tenant identity preservation

- `tenant_id` is required and must be a `UUID`; any other value raises
  `ComplianceSummaryValidationError("tenant_id is required")`.
- The report's own `tenant_id` must equal the caller's `tenant_id`; a mismatch
  raises `ComplianceSummaryValidationError` with
  `"applicability report belongs to a different tenant"`.
- The validated `tenant_id` is written into every constructed case, so risk
  results cannot cross tenant boundaries.
- A report that is not a dictionary raises
  `ComplianceSummaryValidationError("applicability_report is required")`.

## Deterministic behavior

- Identical input produces identical output; a focused test asserts that two
  successive calls return equal results.
- All classification rules, states, and explanation strings remain owned by the
  deterministic `ComplianceRiskService`.
- No ordering, grouping, aggregation, randomness, clock, or environment input
  is added by the integration.


## Explicit non-goals honored

- **No persistence.** No table, repository, migration, or write path was added;
  the integration is a pure in-memory translation plus delegation.
- **No external calls.** No network, HTTP, or third-party service is invoked.
- **No RAG / LLM / retrieval.** No LLM reasoning, embeddings, vector database,
  chunking, reranking, or retrieval of any kind is used.
- **No new applicability, assessment, risk, or action rules.**
- **No modifications to existing services or domain behavior.**

## Files modified

- `xportra/domain/ingestion.py` — add `ApplicabilityToRiskIntegration`
- `xportra/domain/__init__.py` — export the new integration service
- `tests/unit/test_applicability_to_risk_integration.py` — focused Phase 3.3
  tests
- `docs/phases/phase-3-3-applicability-to-risk-integration.md` — this document
- `ACTIVE_TASK.md` — updated after verification
- `CURRENT_STATE.md` — updated after verification

## Focused tests

The focused Phase 3.3 unit test file is:

- `tests/unit/test_applicability_to_risk_integration.py`

It covers:

1. Applicable requirements reach risk classification
2. Not-applicable requirements produce no compliance risk
3. Unknown applicability is preserved (not treated as applicable)
4. Multiple mixed outcomes are aggregated correctly
5. Tenant identity is enforced (report/caller tenant mismatch rejected)
6. Deterministic output for identical input
7. Existing `ComplianceRiskService` behavior is unchanged (delegation)
8. Existing action recommendation still consumes the integrated output
9. Empty applicability report returns an empty risk list
10. Invalid (non-dict) report raises a validation error
11. Invalid (non-UUID) `tenant_id` raises a validation error
12. All-`not_applicable` report returns an empty risk list
13. All-`unknown` report returns an empty risk list
14. Mixed real-world scenario (cocoa export to Nigeria) classifies only the
    applicable requirements


## Verification

Focused Phase 3.3 tests:

- Command: `python -m unittest tests/unit/test_applicability_to_risk_integration.py -v`
- Result: **14 passed**, 0 failed, 0 skipped

Full unit regression at completion:

- Command: `pytest tests/unit/ -v`
- Result: **171 passed**, 0 failed, 0 skipped, 0 errors

PostgreSQL-backed integration tests were not run because `DATABASE_URL` is not
configured in the current environment.

## Regression status

All 157 pre-existing tests from Phase 2.x and Phase 3.0/3.1/3.2 remained
passing. Existing `ComplianceRiskService` and
`ComplianceActionRecommendationService` behavior was unchanged; no existing
service was modified.

## Deferred

The following functionality is intentionally left for later phases:

- Persistence of integration or risk results (no repository method added)
- Automatic fetching of applicability reports or compliance cases from
  repositories (the integration accepts an already-built report)
- Evidence collection or assessment execution inside the integration
- RAG, LLM, embeddings, or vector search
- External regulatory API integration
- New applicability, assessment, risk, or action rules
- Workflow triggering, notifications, UI, or monitoring

## Excluded work remained untouched

Phase 3.3 did not implement:

- LLM reasoning
- agents
- automated compliance decisions
- regulatory interpretation
- new applicability or evidence logic
- workflows or notifications
- embeddings or vector DB
- retrieval or RAG
- UI
- crawling or monitoring
- unrelated refactoring
- modifications to existing risk or action services

