# Phase 7.2 — Shipment & Evidence Intake Formalization

**Status:** Complete and verified (2026-09-24)
**Phase:** Phase 7 — User Workflow
**Type:** Domain reference + handoff contracts making the 7.1
workflow traceable; no API, no UI, no persistence, no verdict

> This record describes what was actually implemented and verified.

## Objective

Formalize workflow ↔ shipment ↔ evidence relationships so the
workflow can answer *which shipment does this concern?* and
*which recorded evidence is supplied for this case?*:

```text
ShipmentReference (tenant + shipment + case)
        ↓ bind once, early
ComplianceWorkflow (shipment association fixed)
        ↓
Document uploaded/recorded → ComplianceEvidenceService
    (authoritative; outside; never called here)
        ↓
SuppliedEvidenceReference (tenant + evidence + case [+ req])
        ↓ supply_to_workflow (validates, delegates)
ComplianceWorkflowService.supply_evidence (7.1, unchanged)
        ↓
re-analysis via ComplianceReasoningApplication (Phase 6)
```

## Architecture investigation outcome

Verified against the repository: no Shipment domain object
and no shipment table exist (only shipment characteristics
inside applicability input); tenant-owned exporters,
products, and destination markets do. Evidence recording and
evidence-to-requirement linking already exist and stay
authoritative (`ComplianceEvidenceService.record` /
`record_with_requirements` over `compliance_evidence` /
`evidence_requirements`). Hence identity/reference contracts
plus handoff validation only — no second shipment model, no
second evidence system, no assessment engine. Per the Phase
2+ convention the decision is recorded here, not in an ADR.

## Shipment reference decision

`ShipmentReference` is tenant + shipment + case UUIDs,
frozen, identity-only. Shipment commercial fields belong to
a future shipment-management subsystem outside this
traceability scope. Binding invariant: one workflow → one
tenant → one case → one shipment reference; once-early
(`created`, `information_provided`, `evidence_pending`);
identical re-bind idempotent; switching shipments, late
binding, and tenant/case mismatches fail closed. The 7.1
`shipment_id` field and file are untouched — binding fills
it via `replace`, never mutation.

## Evidence reference / handoff decision

`SuppliedEvidenceReference` carries the existing
`compliance_evidence` identity plus tenant/case scope and
the optional recording-time requirement link — never bytes
or contents. Upload/record (persistence, authoritative,
outside) stays separated from supply (workflow recognition
of a domain reference). `supply_to_workflow` re-checks
tenant/case and delegates the transition to 7.1
`supply_evidence`, inheriting its explicit duplicate
behavior; validation failures produce no new state.
Ownership is never inferred from user-supplied IDs.

## Workflow transitions (unchanged 7.1 machine)

Binding is permitted only before applicability processing;
supply flows through the established
`additional_evidence_requested`/`review_required` →
`reanalysis_required` path. No states added: states still
describe user/process progression only.

## Tenant / case isolation

Every handoff re-checks tenant and case against the
workflow under the caller context; cross-tenant shipment,
evidence, and workflow combinations, wrong-case references,
malformed and stale references, and non-reference supply
input all fail closed.

## Failure semantics

Deterministic-first: tenant/workflow/shipment/case/
evidence validated before any delegation (zero-call
proofs); recording-side failures cannot produce workflow
state (the intake layer performs no recording —
AST-verified); provider/retrieval failures propagate
through the unchanged 7.1/Phase 6 path.

## Verification

- Focused Phase 7.2: 32/32 (`test_shipment_intake.py` —
  shipment binding incl. idempotent rebind, switch/late/
  cross-tenant/cross-case/raw rejection; evidence
  references incl. case-level form and raw-bytes rejection;
  handoff incl. delegation, duplicates, wrong-state;
  Phase 6 loop integration; isolation; zero-call and
  snapshot failure proofs; determinism/serialization;
  framework-boundary AST checks).
- Phase 7.1 (32) + Phase 6 (247) + Phase 2–5 regressions
  pass unmodified. Full suite: 1500 passed + 37 skipped
  (gated), 0 failures. No live execution claimed.

## Deliberately outside Phase 7.2

API/UI, Shipment object commercial fields, evidence bytes
and recording implementation, persistence/migrations, ORM,
package reopening, evaluation, production hardening, new
providers/stores.

## Files created / modified

- Created: `xportra/domain/shipment_intake.py`,
  `tests/unit/test_shipment_intake.py`,
  `docs/phases/phase-7-2-shipment-evidence-intake-formalization.md`.
- Modified (additive only): `xportra/domain/__init__.py`
  (4 additive exports).
- `xportra/domain/compliance_workflow.py` untouched; no
  prior test touched.
