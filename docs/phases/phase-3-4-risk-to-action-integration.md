# Phase 3.4 — Risk to Action Integration

> Status: Implemented and verified — 2026-09-21

## Objective

Phase 3.4 completes the deterministic domain integration pipeline by establishing
the boundary between risk classification (Phase 3.3) and action recommendation
(Phase 3.0). The integration path is:
Applicability → Risk → Action


`RiskToActionIntegration` connects risk-classified compliance cases to actionable
exporter recommendations while preserving all intermediate state information,
tenant isolation, and determinism guarantees.

## Why this belongs in Phase 3.4

The conceptual flow requires three stages:

1. **Applicability** (Phase 3.1) — Which requirements apply?
2. **Risk** (Phase 3.3) — What is the attention level?
3. **Action** (Phase 3.0) — What should the exporter do next?

Phase 3.0 provides action recommendations for cases that already have risk state.
Phase 3.3 provides risk classification for cases that already have applicability.
Phase 3.4 bridges these two stages into a single coherent pipeline.

## Implementation

`RiskToActionIntegration` is a read-only, in-memory, tenant-scoped service that:

1. Accepts risk-classified cases from `ApplicabilityToRiskIntegration` or
   `ComplianceRiskService.classify()`
2. Delegates all action recommendation logic to the existing
   `ComplianceActionRecommendationService`
3. Preserves unknown/insufficient states without silent conversion
4. Maintains tenant identity throughout the pipeline
5. Provides a convenience method for the full Applicability → Risk → Action flow

### Core methods

#### `recommend_from_risk(risk_classified_cases, tenant_id)`

Converts risk-classified results directly to action recommendations.

**Input:** List of risk-classified case dictionaries  
**Output:** List of action recommendation dictionaries  
**Delegation:** Forwards to `ComplianceActionRecommendationService.recommend()`

#### `full_pipeline(applicability_report, tenant_id)`

Executes the complete Applicability → Risk → Action flow in one call.

**Input:** Applicability report from `ComplianceApplicabilityService.determine()`  
**Output:** Dictionary containing:
- `risk_results` — From `ApplicabilityToRiskIntegration`
- `action_recommendations` — From `ComplianceActionRecommendationService`
- `pipeline_metadata` — Tenant ID, counts, status

### State preservation

- All risk state information is preserved in action recommendations
- Unknown/insufficient states are never silently converted to known states
- Assessment outcomes remain unchanged
- Applicability outcomes remain unchanged
- Recommendations are decision-support suggestions only
- No new compliance verdict or score is created

### Determinism

Output is deterministic:

- Identical input always produces identical output
- Actions are ordered by requirement ID
- Explanations are fixed strings derived from existing case state
- No LLMs, agents, retrieval, embeddings, vector DB, or RAG are used

### Tenant isolation

- Tenant ID is validated as required UUID
- Tenant identity is preserved through the entire pipeline
- Results from one tenant cannot leak to another tenant

### Explicit unknown-state handling

The integration preserves the existing unknown-state semantics:

| Risk state | Assessment | Evidence | Action |
|---|---|---|---|
| high | not_satisfied | any | address_requirement |
| medium | unknown | missing | provide_missing_evidence |
| low | satisfied | sufficient | no_action_required |
| unknown | unknown | insufficient | review_requirement |

Unknown states are never upgraded or silently resolved.

## Files modified

- `xportra/domain/ingestion.py` — add `RiskToActionIntegration`
- `xportra/domain/__init__.py` — export the new service
- `tests/unit/test_risk_to_action_integration.py` — focused Phase 3.4 tests
- `phase-3-4-risk-to-action-integration.md` — this document
- `ACTIVE_TASK.md` — updated after verification
- `CURRENT_STATE.md` — updated after verification

## Focused tests

The focused Phase 3.4 unit test file is:

- `tests/unit/test_risk_to_action_integration.py`

It covers:

1. High-risk (not_satisfied) → address_requirement
2. Medium-risk (unknown + missing evidence) → provide_missing_evidence
3. Low-risk (satisfied) → no_action_required
4. Unknown/insufficient state → review_requirement
5. Multiple conditions produce deterministic output
6. Tenant identity preserved throughout integration
7. Identical input produces identical actions (determinism)
8. Existing ActionRecommendationService behavior unchanged (delegation)
9. Full pipeline executes correctly end-to-end
10. Pipeline metadata includes correct counts
11. Invalid input validation (non-list cases)
12. Invalid tenant_id validation
13. Empty case list handling
14. Not-applicable cases excluded from actions
15. Pipeline preserves provenance chain

## Verification

Focused Phase 3.4 tests:

- Command: `python -m unittest tests/unit/test_risk_to_action_integration.py -v`
- Result: 15 passed, 0 failed, 0 skipped

Full unit suite:

- Command: `pytest tests/unit/ -v`
- Result: 186 passed, 0 failed, 0 skipped, 0 errors

## Regression status

All 171 pre-existing tests remain passing. Phase 2.x, Phase 3.0, 3.1, 3.2, and 3.3
behavior is intact. No existing services were modified.

## Deferred

The following functionality is intentionally left for later phases:

- Persistence of integration results or pipeline output
- Automatic triggering of downstream workflows
- RAG, LLM, embeddings, or vector search
- External regulatory API integration
- New risk classification rules
- New action recommendation types
- UI or notification layer
- Real-time monitoring or event-driven architecture

## Excluded work remained untouched

Phase 3.4 did not implement:

- LLM reasoning
- agents
- automated compliance decisions
- regulatory interpretation
- new applicability or evidence logic
- workflows
- notifications
- embeddings or vector DB
- retrieval or RAG
- UI
- crawling or monitoring
- unrelated refactoring
- modifications to existing risk or action services


