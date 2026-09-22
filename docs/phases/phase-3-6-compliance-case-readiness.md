# Phase 3.6 — Compliance Case Readiness / Evidence Coverage Boundary

**Status:** Complete and verified (2026-09-22)
**Phase:** Phase 3 — Applicability Engine
**Type:** Domain representation / readiness boundary — no new compliance rules

> This record describes what was actually implemented and verified in Phase 3.6.

## Objective

Build a small deterministic domain boundary that evaluates whether a compliance
case carries **sufficient known information** to support the existing
Applicability → Risk → Action decision pipeline, and expose **evidence and
information gaps** explicitly so that future retrieval/RAG work can target
those gaps instead of guessing.

The boundary adds readiness representation, not compliance verdicts. It
performs no retrieval, web search, RAG, LLM reasoning, embeddings, vector
search, crawling, external API calls, or persistence, and introduces no new
compliance rules.

## Core semantic rule: readiness is not compliance

```text
READY           ≠  COMPLIANT
NOT_READY       ≠  NON_COMPLIANT
```

A case may have every required piece of information known while still
containing high-risk or `not_satisfied` requirements — that case is `ready`
*and* needs remediation. Likewise, a `not_ready` case is not non-compliant; the
available information is simply insufficient for a complete determination. The
service introduces no compliance verdict of any kind, and the report carries an
explicit `readiness_not_compliance` note stating this.

## Implementation

### Abstraction created

`ComplianceCaseReadinessService` in `xportra/domain/ingestion.py`.

Pipeline position:

```text
Applicability → Risk → Action → Summary → Readiness
```

### Constructor

```python
ComplianceCaseReadinessService(
    risk_service: ComplianceRiskService | None = None,
    risk_to_action: RiskToActionIntegration | None = None,
)
```

Collaborators default to the existing Phase 2.9 and Phase 3.4 implementations;
injection exists only for testability.

### Information accounting

For every requirement (any applicability outcome):

- **Applicability information is required** (+1 required).
- Known iff the outcome is `applicable` or `not_applicable` (+1 known); an
  `unknown` outcome produces an `applicability_unknown` gap.

For each **applicable** requirement only (matching existing pipeline scope):

- **Assessment information is required** (+3 required for the applicable
  triple). Known iff the assessment outcome is `satisfied` or `not_satisfied`;
  `unknown` produces an `assessment_unknown` gap.
- **Evidence coverage** is evaluated only when the assessment is `unknown`, by
  reusing `ComplianceRiskService._is_missing_evidence` directly (no new
  evidence rule): a gap `missing_evidence` is recorded when the reason flag or
  empty evidence indicates missing coverage, otherwise +1 known. This mirrors
  the exact scope in which the risk service, action service, and Phase 2.8
  summary consult missing evidence.
- **Risk information** is known iff the risk service returned a classification
  with state `high`, `medium`, or `low` (+1 known); otherwise a `risk_unknown`
  gap is recorded (reason taken from the risk explanation, or
  "no risk classification produced" if none was emitted).

`not_applicable` requirements contribute only their applicability information —
never assessment, evidence, or risk requirements — and their rows keep
`risk_state`/`action_type` as `None`.

### Gap kinds (evidence-gap behavior)

Four gap kinds, identical in name and meaning to the Phase 3.5
`unknown_states` vocabulary:

| Kind | Meaning | Never implies |
|---|---|---|
| `applicability_unknown` | The requirement's applicability could not be determined | applicable / not_applicable |
| `assessment_unknown` | An applicable requirement has no known assessment | satisfied / not_satisfied |
| `missing_evidence` | Known-required evidence is absent for an unknown assessment | assessment is satisfied/not_satisfied |
| `risk_unknown` | The risk service could not classify the requirement | high / medium / low |

Gaps are observations about *information availability* only. No missing fact is
invented, no unknown is inferred into a known value, and no action or outcome is
rewritten.

### Readiness states (minimal deterministic model)

```text
ready           — every required piece of information is known (zero gaps)
partially_ready — applicability is known for all requirements, but some
                  assessment, evidence, or risk information is missing
not_ready       — no cases at all (nothing to determine), or at least one
                  requirement with unknown applicability (the applicable
                  requirement set itself cannot be enumerated completely)
```

No additional states were introduced; `not_applicable`, `unknown`, and
`missing evidence` remain distinct concepts and are never merged into a state
name.

### Report shape (output)

```python
{
    "tenant_id": UUID,                          # preserved caller identity
    "context_fingerprint": str | None,          # reused from Phase 3.5 helper
    "status": "readiness_report",
    "readiness_state": "ready" | "partially_ready" | "not_ready",
    "required_information": int,                # applicability(1) + applicable(3 each)
    "known_information": int,
    "missing_information": int,                 # == len(gaps)
    "gaps": [                                   # sorted by (requirement_id, kind)
        {"requirement_id": ..., "kind": ..., "reason": ...},
    ],
    "unknown_applicability_requirements": [...],  # IDs per gap kind
    "unknown_assessment_requirements": [...],
    "missing_evidence_requirements": [...],
    "unknown_risk_requirements": [...],
    "actions_requiring_evidence": [             # from the existing action service
        {"requirement_id": ..., "action_type": ..., "explanation": ...},
    ],
    "requirements": [                           # one row per case, requirement-ID order
        {"requirement_id": ..., "requirement_text": ...,
         "applicability_outcome": ..., "assessment_outcome": ...,
         "evidence_present": bool, "risk_state": ...|None,
         "action_type": ...|None},
    ],
    "readiness_not_compliance": "...",          # explicit non-verdict note
}
```

**`actions_requiring_evidence`** lists the existing service's own
`provide_missing_evidence` and `review_requirement` recommendations — the two
action types the Phase 3.0 logic emits exactly when information is
insufficient. Actions are consumed as-is; no recommendation is rewritten into a
stronger or weaker conclusion, and no new action type exists.

### Input

The same case dictionaries the existing pipeline already consumes — no new
input format, no migration, no adaptation layer beyond reading existing fields.

### Tenant handling

- `tenant_id` must be a `UUID`; anything else raises
  `ComplianceSummaryValidationError` (same error type as the rest of Phase 3).
- Every case is validated against that tenant via
  `ComplianceRiskService._validate_case`, so a case from another tenant is
  rejected, never silently merged.
- The returned report carries the caller's `tenant_id`.

### Determinism

For identical inputs the report is identical:

- requirement order: sorted by `str(requirement.id)`;
- gap order: sorted by `(str(requirement_id), kind)`;
- `actions_requiring_evidence`: sorted by requirement ID;
- counts are pure functions of the ordered input;
- every explanation/reason string is passed through from the existing services
  or a fixed literal (e.g. "no risk classification produced").

## No duplicated business logic

The service re-uses, and does not re-implement:

- applicability outcomes — read from the cases produced by the Phase 2.5 /
  Phase 3.1 services;
- risk classification — delegated to `ComplianceRiskService.classify()`;
- action recommendation — delegated to `RiskToActionIntegration` →
  `ComplianceActionRecommendationService`;
- missing-evidence semantics — `ComplianceRiskService._is_missing_evidence`
  called directly;
- case validation — `ComplianceRiskService._validate_case` called directly.

No new risk level, action type, applicability outcome, assessment outcome, or
compliance verdict exists anywhere in this phase.

## Tests

`tests/unit/test_compliance_case_readiness.py` — 20 focused tests following the
existing `unittest` conventions (class-style, isolated `setUp`, UUID
identifiers, no I/O):

1. fully known case → `ready`
2. partially known case → `partially_ready`
3. insufficient/unknown case → `not_ready`
4. unknown applicability gap
5. unknown assessment gap
6. missing evidence gap
7. unknown risk gap
8. multiple simultaneous gaps
9. no false inference from missing facts
10. deterministic requirement ordering
11. deterministic gap ordering
12. identical input produces identical output
13. tenant identity preserved
14. invalid tenant rejected
15. empty input handled deterministically
16. ready case can still contain high risk
17. not-ready case is not labelled non-compliant
18. existing decision summary remains unchanged
19. existing risk/action semantics remain unchanged
20. end-to-end integration with the existing Phase 3.5 summary

Test 20 asserts the readiness report's gap kinds equal the Phase 3.5 summary's
`unknown_states` kinds on the same cases, and that both carry the same tenant
and context fingerprint — the two boundaries agree on uncertainty.

## Verification

- Baseline re-confirmed immediately before Phase 3.6 work: 202/202 passing.
- Focused Phase 3.5→3.6 tests: `pytest tests/unit/test_compliance_case_readiness.py -q`
  → **20 passed**.
- Full unit suite: `pytest tests/unit/ -q` → **222 passed, 0 failed, 0
  errors** (202 baseline + 20 new). The only warnings are pre-existing
  third-party `starlette` deprecation notices, unrelated to this change.
- PostgreSQL-backed integration tests were not run because `DATABASE_URL` is
  not configured in the current environment.

## Files changed

- `xportra/domain/ingestion.py` — added `ComplianceCaseReadinessService`
  (before `SourceAcquisitionService`); no existing class or rule modified.
- `tests/unit/test_compliance_case_readiness.py` — new, 20 tests.
- `docs/phases/phase-3-6-compliance-case-readiness.md` — this record.
- `ACTIVE_TASK.md`, `CURRENT_STATE.md` — state updates.

## Explicitly deferred (not implemented)

API endpoints; UI; persistence; document-ingestion changes; web crawling;
regulatory-source connectors; embeddings; vector databases; retrieval;
reranking; RAG; LLM reasoning; agents; automated compliance verdicts. The gap
list produced here is the intended target surface for future retrieval work;
the retrieval itself belongs to a later phase.

Phase 3.7 and any later phase have not been started.
