# Phase 3.1 — Compliance Applicability Determination

> Status: Implemented and verified — 2026-09-21

## Objective

Phase 3.1 strengthens the **Applicability Determination** layer by introducing
`ComplianceApplicabilityService`, a deterministic batch applicability service
that evaluates a set of compliance requirements against a single
`ApplicabilityContext` and produces a structured report.

The existing `RegulatoryRequirementApplicabilityService.evaluate()` evaluates
one requirement at a time. Phase 3.1 adds the capability to evaluate **all
requirements for an export case** in one operation, producing a consolidated
applicability report that preserves the distinction between:

- `applicable` — the requirement clearly applies to this export case
- `not_applicable` — the requirement clearly does not apply (mismatch)
- `unknown` — insufficient information to determine applicability

## Why this belongs in Phase 3.1

The conceptual flow is:

```
Export Case
    ↓
Compliance Requirements
    ↓
Applicability Determination  ← Phase 3.1 strengthens this
    ↓
Compliance Risk Classification
    ↓
Action Recommendation
```

Phase 3.0 (action recommendation) operates on cases that already have
applicability, assessment, and evidence determined. Phase 3.1 provides the
missing batch-level applicability determination capability that feeds into
those downstream services.

## Implementation

`ComplianceApplicabilityService` is a read-only, in-memory, tenant-scoped
service that:

1. Accepts a list of requirements and an `ApplicabilityContext`
2. Delegates to `RegulatoryRequirementApplicabilityService.evaluate()` for each
   requirement independently
3. Aggregates results into a structured report with counts per outcome
4. Computes a deterministic context fingerprint
5. Preserves tenant isolation

### Output format

The `determine` method returns:

- `tenant_id`
- `context_fingerprint` — deterministic SHA-256 hash of the context
- `total_requirements` — total number of requirements evaluated
- `applicable_count` — requirements that clearly apply
- `not_applicable_count` — requirements that clearly do not apply
- `unknown_count` — requirements with insufficient information
- `results` — individual applicability results from the underlying service
- `status` — always `"determined"`

### Determinism

- Each requirement is evaluated independently using the existing
  `RegulatoryRequirementApplicabilityService` rules
- The context fingerprint is deterministic (SHA-256 of the serialized context)
- Repeated evaluation with the same inputs produces identical results
- No LLMs, agents, retrieval, embeddings, vector DB, or RAG are used

## Files modified

- `xportra/domain/ingestion.py` — add `ComplianceApplicabilityService` and
  `context_fingerprint` helper
- `xportra/domain/__init__.py` — export the new service and helper
- `tests/unit/test_compliance_applicability.py` — focused Phase 3.1 tests
- `phase-3-1-compliance-applicability-determination.md` — this document
- `ACTIVE_TASK.md` — updated after verification
- `CURRENT_STATE.md` — updated after verification

## Focused tests

The focused Phase 3.1 unit test file is:

- `tests/unit/test_compliance_applicability.py`

It covers:

1. Clearly applicable requirement
2. Clearly non-applicable requirement
3. Insufficient information / indeterminate applicability
4. Multiple requirements evaluated independently
5. Deterministic repeated evaluation
6. Context fingerprint consistency with underlying service
7. Empty requirements validation
8. Invalid context validation
9. Tenant isolation
10. Status field
11. Counts sum to total

## Verification

Focused Phase 3.1 tests:

- Command: `python -m unittest tests/unit/test_compliance_applicability.py -v`
- Result: 11 passed, 0 failed, 0 skipped

Full unit suite:

- Command: `pytest tests/unit/ -v`
- Result: 140 passed, 0 failed, 0 skipped, 0 errors

## Regression status

All 129 pre-existing tests remain passing. Phase 2.x behavior is intact.

## Deferred

The following functionality is intentionally left for later phases:

- Persistence of batch applicability results (no new repository method added)
- Integration with export case / product / destination entities at the service
  layer (the service operates on raw requirements and context only)
- RAG, LLM, embeddings, or vector search
- External regulatory API integration
- Applicability inference beyond the existing deterministic rules