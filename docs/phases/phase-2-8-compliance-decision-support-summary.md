# Phase 2.8 — Compliance Decision-Support Summary

> Status: Complete for the approved boundary scope — 2026-09-21

## Implementation summary

Phase 2.8 adds `ComplianceSummaryService`, a thin deterministic summary layer over
the existing `ComplianceCaseService` and Phase 2.5/2.6 compliance case data.

No new compliance reasoning is introduced. The service only composes and counts
existing case states.

## Summary output

The `summarize` method returns a read-only dict with:

| Field | Description |
|---|---|
| `total_cases` | Total number of cases in the set |
| `total_applicable_requirements` | Cases with `applicable` outcome (excludes `not_applicable`) |
| `satisfied_requirements` | Applicable cases with `satisfied` assessment |
| `not_satisfied_requirements` | Applicable cases with `not_satisfied` assessment |
| `unknown_requirements` | Applicable cases with `unknown` assessment + unknown applicability cases |
| `requirements_missing_evidence` | Unknown assessment cases where evidence is absent or links are missing |
| `requirements_requiring_review` | Cases needing reviewer attention: unknown applicability + unknown assessment |
| `affected_requirements` | `not_satisfied` + `requiring_review` requirements, for prioritization UI |
| `missing_evidence_requirements` | `requirements_missing_evidence` with full provenance |
| `status` | Fixed to `"summary"` |

## State preservation

The following states are preserved exactly as-is, never converted:

- `not_applicable` — excluded from `total_applicable_requirements`, not in `affected_requirements`
- `unknown` — never converted to `satisfied` or `not_satisfied`; remains as `unknown`
- `satisfied` — retained when evidence is accepted
- `not_satisfied` — retained when evidence is rejected

`unknown` applicability does not become satisfied; `unknown` assessment does not become failure.

## Provenance and tenant isolation

- Each case is validated to belong to the requested `tenant_id`; cross-tenant cases raise `ComplianceSummaryValidationError`
- `affected_requirements` and `missing_evidence_requirements` include `regulatory_source`, `document_metadata`, and `provenance` references
- Shared regulatory data is referenced through existing IDs; no duplication

## Determinism

Output is deterministic: cases are sorted by `requirement_id` string, and the same input
always produces the same output. No LLM, agents, embeddings, vector DB, retrieval, RAG,
or ranking is used.

## What was NOT implemented

- Compliance scoring or risk scoring
- Recommendations or actions
- Prioritization or ranking
- LLMs, agents, embeddings, vector DB, retrieval, RAG
- UI, crawling, monitoring, or workflow logic
- Any new compliance reasoning or verdict generation

## Tests

Focused Phase 2.8 tests in `tests/unit/test_compliance_summary.py` cover:

1. Outcome counts (applicable, satisfied, not_satisfied, unknown)
2. Missing evidence detection and provenance
3. Unknown applicability requiring review
4. Non-applicable exclusion from applicable totals
5. Provenance preservation in missing evidence output
6. Tenant isolation (cross-tenant rejection)
7. Deterministic repeated output
8. Empty case set returns zero counts

Full unit regression complements the focused tests.

## Files modified

- `xportra/domain/ingestion.py` — `ComplianceSummaryService` class (already existed, verified complete)
- `tests/unit/test_compliance_summary.py` — Phase 2.8 focused unit tests
- `phase-2-8-compliance-decision-support-summary.md` — this documentation file

## PostgreSQL status

PostgreSQL integration tests require `DATABASE_URL` and were not run in this environment.
The summary service is a pure in-memory/read-service layer with no database dependency.

## Completion

Phase 2.8 is complete. Phase 2.9 must not begin.