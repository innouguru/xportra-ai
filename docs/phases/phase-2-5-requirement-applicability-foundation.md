# Phase 2.5 — Requirement Applicability Foundation

> Status: Complete for the approved boundary scope — 2026-09-21

## Implementation

Phase 2.5 evaluates an extracted regulatory requirement against a minimal
business context:

```text
regulatory requirement + tenant-owned applicability context
    -> deterministic applicability outcome and explanation
```

The implementation does not decide compliance, generate recommendations, or
interpret applicability probabilistically.

## Applicability model

`ApplicabilityContext` contains only the minimum explicit tenant-owned facts:

- `tenant_id`
- exporter identity/name
- origin country
- destination country
- commodity
- product category
- optional business characteristics
- optional actor role

Unknown values remain null. A tenant ID is mandatory and is validated before
evaluation.

## Outcomes and rules

`RegulatoryRequirementApplicabilityService` returns:

- `applicable`
- `not_applicable`
- `unknown`

Rules are deterministic and conservative:

- explicit destination match -> applicable evidence
- known destination mismatch -> `not_applicable`
- missing destination -> `unknown`
- explicit commodity match/mismatch follows the same rule
- explicit exporter actor plus exporter context role -> actor match
- actor mismatch or missing actor facts remains `unknown`
- explicit numeric thresholds are evaluated only when the corresponding business
  characteristic is supplied
- missing threshold facts -> `unknown`
- threshold failure -> `not_applicable`
- no facts sufficient to decide -> `unknown`

Each result includes a concise deterministic reason such as matched destination,
destination mismatch, matched commodity, explicit actor match, threshold not met,
or insufficient context.

No applicability decision is interpreted as compliance status.

## Provenance and tenant isolation

Results retain the regulatory requirement ID. The requirement already links to the
normalized document, acquired artifact, and regulatory source:

```text
applicability result -> requirement -> normalized document -> artifact -> source
```

Applicability results and context are tenant-owned. The persistence identity is:

```text
(tenant_id, requirement_id, context_fingerprint)
```

This prevents one tenant's context or result from being reused as another tenant's
result.

## Persistence and idempotency

Created:

- `migrations/007_regulatory_requirement_applicability.sql`
- `migrations/007_regulatory_requirement_applicability.down.sql`

The table `xportra.regulatory_requirement_applicability` stores the tenant,
requirement, deterministic context fingerprint, outcome, explanation, context
JSONB, status, and timestamps. The repository uses parameterized SQL and enforces
unique evaluation identity at the database layer.

Repeated evaluation with the same requirement and context returns the existing
result.

## Security and exclusions

- shared regulatory requirements remain separate from tenant-owned contexts and
  results
- no cross-tenant result access path is introduced
- no secrets or credentials are logged or added
- no document content is executed
- no compliance status, score, recommendation, or action is generated
- no generalized rule engine is introduced

## Tests and limitations

Focused Phase 2.5 tests are in `tests/unit/test_regulatory_applicability.py`.
They cover outcomes, destination and commodity rules, actors, thresholds,
explanations, provenance, tenant validation, idempotency, and the absence of
applicability-to-compliance inference.

PostgreSQL integration tests require `DATABASE_URL` and are not run when it is
unavailable. The deterministic domain boundary and repository contract are unit
validated.

Deferred work includes richer approved business facts, broader jurisdiction
rules, compliance evaluation, recommendations, and Phase 2.6.
