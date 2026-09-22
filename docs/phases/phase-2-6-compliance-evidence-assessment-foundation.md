# Phase 2.6 — Compliance Evidence & Assessment Foundation

> Status: Complete for the approved boundary scope — 2026-09-21

## Implementation summary

Phase 2.6 establishes the minimum boundary:

```text
applicable requirement + tenant evidence -> assessment state
```

It distinguishes `satisfied`, `not_satisfied`, and `unknown` without scoring,
recommendations, or compliance workflow behavior.

## Evidence behavior

`EvidenceRecord` is a small tenant-owned evidence reference containing:

- tenant ID
- evidence ID
- evidence type/category
- reference/location
- optional requirement ID
- evidence status
- explicit metadata

It reuses the existing tenant evidence model rather than introducing upload
infrastructure. Evidence is not accepted merely because its category matches.

Evidence must be explicitly linked to the requirement and carry
`metadata.supports_requirement = true` with an accepted/reviewed status to support
a satisfied assessment.

## Assessment behavior

`RequirementAssessmentService` evaluates only an applicable Phase 2.5 result:

- applicable requirement + explicitly linked accepted supporting evidence ->
  `satisfied`
- applicable requirement + linked rejected/archived evidence -> `not_satisfied`
- no evidence -> `unknown` with `required evidence absent`
- present but unlinked or insufficient evidence -> `unknown` with
  `evidence insufficient`
- non-applicable or unknown applicability -> `unknown` with
  `requirement cannot yet be assessed`

Every result has a deterministic explanation. Assessment state is not compliance
scoring and does not produce recommendations.

## Linkage and provenance

An assessment contains:

- requirement ID
- applicability result ID
- selected evidence ID when applicable
- all explicitly linked evidence IDs

The provenance chain remains:

```text
assessment -> applicable result/context -> requirement -> normalized document -> artifact -> source
```

Regulatory requirements remain shared. Evidence and assessments are tenant-owned.
A tenant mismatch is rejected before assessment.

## Persistence and idempotency

Created:

- `migrations/008_regulatory_requirement_assessments.sql`
- `migrations/008_regulatory_requirement_assessments.down.sql`

The new table stores tenant, requirement, applicability result, evidence
fingerprint, evidence linkage, outcome, explanation, status, and timestamps.

The unique identity is:

```text
(tenant_id, requirement_id, applicability_result_id, evidence_fingerprint)
```

Repeated evaluation of the same requirement, context result, and evidence state
returns the existing assessment.

## Security and exclusions

- evidence and assessment results are tenant-scoped
- cross-tenant evidence raises a validation error
- no credentials or secrets are introduced or logged
- no evidence is interpreted as a recommendation
- no scoring, percentage, risk, workflow, notification, or action logic is added
- no LLM, agent, retrieval, RAG, embedding, or vector behavior is added

## Tests and limitations

Focused tests are in `tests/unit/test_compliance_assessment.py` and cover satisfied,
not-satisfied, unknown, missing/insufficient evidence, linkage, tenant isolation,
deterministic explanations, idempotency, and invalid input.

PostgreSQL integration tests require `DATABASE_URL` and are not run when it is
unavailable. The domain and repository contracts are unit validated.

Phase 2.7 and all later workflow/recommendation behavior remain deferred.
