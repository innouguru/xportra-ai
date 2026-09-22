# Phase 3.0 — Compliance Action Recommendation Foundation

> Status: Implemented and verified — 2026-09-21

## Implementation summary

Phase 3.0 adds `ComplianceActionRecommendationService`, a deterministic advisory
layer over existing compliance cases. It translates existing applicability,
assessment, evidence, and risk state into a possible exporter next action
without changing any underlying compliance outcome.

The service is read-only, in-memory, tenant-scoped, and provenance-preserving.
It does not introduce new applicability rules, evidence logic, regulatory
interpretation, automated decisions, or persistence.

## Recommendation rules

The `recommend` method maps existing state to exporter next actions:

| Existing state | Action type | Explanation |
|---|---|---|
| `not_satisfied` | `address_requirement` | assessment not_satisfied; address requirement |
| `unknown` + missing required evidence | `provide_missing_evidence` | assessment unknown with missing required evidence; provide missing evidence |
| `unknown` without sufficient evidence | `review_requirement` | assessment unknown without sufficient evidence; review requirement |
| `satisfied` | `no_action_required` | assessment satisfied; no action required |
| `not_applicable` | excluded | no recommendation returned |

Where applicability itself is `unknown`, the recommendation remains advisory and
conservative: `review_requirement`.

## Output format

Each recommendation contains:

- `action_type`
- `explanation`
- `tenant_id`
- `context`
- `context_fingerprint`
- `requirement_id`
- `requirement_text`
- `risk_state` where deterministically available
- `regulatory_source`
- `document_metadata`
- `provenance`
- `status`

## State preservation

- Applicability outcomes remain unchanged.
- Assessment outcomes remain unchanged.
- Recommendations are decision-support suggestions only.
- No new compliance verdict or score is created.
- The service does not reinterpret regulatory wording.
- Full source/document/provenance links remain attached.
- Tenant isolation is enforced across the full case set.

## Determinism

Output is deterministic:

- cases are validated against a single `tenant_id`
- output is sorted by `requirement_id`
- explanations are fixed strings derived from existing case state
- `risk_state` is derived per case using the existing risk classification rules
- no LLMs, agents, retrieval, embeddings, vector DB, or RAG are used

## Focused tests

The focused Phase 3.0 unit test file is:

- `tests/unit/test_compliance_action_recommendation.py`

It covers:

1. `not_satisfied` → `address_requirement`
2. missing evidence → `provide_missing_evidence`
3. unknown → `review_requirement`
4. satisfied → `no_action_required`
5. not-applicable exclusion
6. deterministic explanation
7. provenance preservation
8. tenant isolation
9. deterministic repeated output
10. empty case set

## Files modified

- `xportra/domain/ingestion.py` — add `ComplianceActionRecommendationService`
- `xportra/domain/__init__.py` — export the new service
- `tests/unit/test_compliance_action_recommendation.py` — focused Phase 3.0 tests
- `phase-3-0-compliance-action-recommendation-foundation.md` — this document
- `ACTIVE_TASK.md` — updated after verification
- `CURRENT_STATE.md` — updated after verification

## Verification

Focused Phase 3.0 tests passed:

- `python -m pytest tests/unit/test_compliance_action_recommendation.py -q`

Full unit regression passed:

- `python -m pytest tests/unit -q`

PostgreSQL-backed integration verification was not run because `DATABASE_URL`
is not configured in the current environment.

## Excluded work remained untouched

Phase 3.0 did not implement:

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
