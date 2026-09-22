# Phase 2.7 — Compliance Case Read Model

> Status: Complete for the approved boundary scope — 2026-09-21

## Implementation summary

Phase 2.7 adds `ComplianceCaseService`, a composition-only read model over the
existing Phase 2.5 applicability result, Phase 2.4 requirement, Phase 2.6
assessment, and tenant evidence references.

No new compliance reasoning or verdict is introduced.

## Case behavior

A case exposes:

- tenant identity
- applicability context/fingerprint and outcome/reason
- requirement identity, text, type, and source location
- assessment outcome/reason and evidence IDs
- linked tenant evidence references
- regulatory source reference
- normalized document metadata reference
- provenance IDs
- existing timestamp/status values where supplied

Existing states are preserved:

- applicable + satisfied -> satisfied assessment is exposed
- applicable + not_satisfied -> not_satisfied assessment is exposed
- applicable + unknown -> unknown assessment is exposed
- unknown applicability -> assessment is exposed as unknown
- not_applicable applicability -> it is not converted to satisfied
- missing assessment -> unknown assessment

The read model has no new compliance verdict or score.

## Provenance and tenant isolation

The composed chain is:

```text
case -> assessment -> applicability -> requirement -> normalized document -> artifact -> source
```

Evidence references remain tenant-owned and are included only when they belong to
the case tenant and are explicitly linked to the requirement. Mismatched tenant,
requirement, or applicability records are rejected.

## Persistence decision

No new table was required. Existing applicability, requirement, assessment, and
evidence persistence are composed in memory by the read service. This avoids
copying shared regulatory data or creating a duplicated compliance state store.

## Security and exclusions

- no cross-tenant evidence or assessment data is exposed
- no regulatory source content is duplicated
- no applicability is inferred
- no evidence is reassessed
- no compliance score, risk score, recommendation, workflow, notification, or
  action is generated
- no LLM, agent, retrieval, RAG, embedding, vector, or UI behavior is introduced

## Tests and limitations

Focused tests are in `tests/unit/test_compliance_case.py` and cover complete
aggregation, all relevant state combinations, missing evidence, tenant isolation,
provenance, deterministic output, and invalid input.

PostgreSQL integration tests require `DATABASE_URL` and are not run when it is
unavailable. The read model is unit validated against the existing contracts.

Phase 2.8 remains deferred.
