"""Shipment and evidence intake formalization for Phase 7.2.

The smallest reusable domain references plus the evidence-submission
handoff that make a Phase 7.1 compliance workflow traceable:

```text
ShipmentReference (tenant + shipment + case)
        ↓ bind once, early
ComplianceWorkflow (shipment association fixed)
        ↓
Document uploaded/recorded  →  ComplianceEvidenceService
    (authoritative recording + requirement linking; outside
     this contract, persistence-backed, never called here)
        ↓
SuppliedEvidenceReference (tenant + evidence + case [+ requirement])
        ↓ supply_to_workflow (validates, delegates)
ComplianceWorkflowService.supply_evidence (Phase 7.1, unchanged)
        ↓
re-analysis via ComplianceReasoningApplication (Phase 6, unchanged)
```

Investigation outcome (verified against the repository): no
Shipment domain object and no shipment table exist — only
shipment characteristics inside applicability input, plus
tenant-owned exporters, products, and destination markets.
Evidence recording and evidence-to-requirement linking already
exist and stay authoritative (`ComplianceEvidenceService.record`
/ `record_with_requirements` over `compliance_evidence` /
`evidence_requirements`). This module therefore introduces
only identity/reference contracts plus handoff validation —
no second shipment persistence model, no second evidence
persistence system, no assessment engine.

Upload/record vs supply stays separated: recording persists
or registers the artifact (outside); supply is the workflow
explicitly recognizing a domain evidence reference for this
case/shipment. The workflow receives references, never raw
file bytes — `supply_to_workflow` accepts only a
`SuppliedEvidenceReference`; bytes, strings, dicts, and raw
artifacts fail closed.

Association invariant: one workflow → one tenant → one case
→ one shipment reference. Binding is once-and-early
(`created`, `information_provided`, `evidence_pending`);
re-binding the same shipment is idempotent, switching to a
different shipment is an explicit invalid operation, and
binding after applicability processing has begun is
rejected. Cross-tenant shipment, evidence, and workflow
combinations fail closed, as do wrong-case and malformed
references. Ownership is never inferred from user-supplied
IDs alone — every handoff re-checks tenant and case against
the workflow under the caller's tenant context.

This module performs no document parsing, extraction,
chunking, embedding, indexing, persistence, retrieval, LLM
invocation, or reasoning of its own.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from .compliance_workflow import (
    WORKFLOW_STATE_CREATED,
    WORKFLOW_STATE_EVIDENCE_PENDING,
    WORKFLOW_STATE_INFORMATION_PROVIDED,
    ComplianceWorkflow,
    ComplianceWorkflowError,
    ComplianceWorkflowService,
)
from .errors import DomainValidationError, require_tenant_context

_BINDING_STATES = frozenset({
    WORKFLOW_STATE_CREATED,
    WORKFLOW_STATE_INFORMATION_PROVIDED,
    WORKFLOW_STATE_EVIDENCE_PENDING,
})


class ShipmentIntakeError(DomainValidationError):
    """A shipment/evidence intake integrity failure (fail closed).

    Raised for malformed references, tenant/case mismatches,
    shipment switches, late binding, and non-reference supply
    input — never converted into an associated workflow state.
    """


@dataclass(frozen=True, slots=True)
class ShipmentReference:
    """Immutable identity answering which shipment a workflow concerns.

    Identity only: tenant, shipment, and case. Shipment
    commercial fields (parties, goods, transport, dates)
    belong to a future shipment-management subsystem outside
    this contract's traceability scope.
    """

    tenant_id: UUID
    shipment_id: UUID
    case_id: UUID

    def __post_init__(self) -> None:
        for name in ("tenant_id", "shipment_id", "case_id"):
            if not isinstance(getattr(self, name), UUID):
                raise ShipmentIntakeError(
                    f"shipment {name} must be a UUID")

    def to_record(self) -> dict[str, Any]:
        return {
            "tenant_id": str(self.tenant_id),
            "shipment_id": str(self.shipment_id),
            "case_id": str(self.case_id),
        }


@dataclass(frozen=True, slots=True)
class SuppliedEvidenceReference:
    """Immutable domain evidence reference for workflow supply.

    Carries the existing evidence identity (`compliance_evidence`
    row) plus the tenant/case scope it is supplied under and the
    optional requirement association established at recording
    time. No bytes, no contents, no model-generated IDs.
    """

    tenant_id: UUID
    evidence_id: UUID
    case_id: UUID
    requirement_id: UUID | None = None

    def __post_init__(self) -> None:
        for name in ("tenant_id", "evidence_id", "case_id"):
            if not isinstance(getattr(self, name), UUID):
                raise ShipmentIntakeError(
                    f"evidence {name} must be a UUID")
        requirement_id = self.requirement_id
        if requirement_id is not None and not isinstance(
                requirement_id, UUID):
            raise ShipmentIntakeError(
                "evidence requirement_id must be a UUID")

    def to_record(self) -> dict[str, Any]:
        return {
            "tenant_id": str(self.tenant_id),
            "evidence_id": str(self.evidence_id),
            "case_id": str(self.case_id),
            "requirement_id": (
                str(self.requirement_id)
                if self.requirement_id is not None else None),
        }


class ShipmentIntakeService:
    """Pure handoff validation for shipment and evidence intake."""

    def __init__(
        self,
        *,
        workflow_service: ComplianceWorkflowService | None = None,
    ) -> None:
        self._workflow_service = (
            workflow_service or ComplianceWorkflowService())
        if not callable(getattr(
                self._workflow_service, "supply_evidence", None)):
            raise ShipmentIntakeError(
                "a compliance workflow service is required")

    def register_shipment(
        self,
        *,
        tenant_id: Any,
        shipment_id: UUID,
        case_id: UUID,
    ) -> ShipmentReference:
        """Build the shipment reference for a workflow's case."""
        require_tenant_context(tenant_id)
        return ShipmentReference(
            tenant_id=tenant_id.tenant_id,
            shipment_id=shipment_id,
            case_id=case_id,
        )

    def bind_shipment(
        self,
        workflow: ComplianceWorkflow,
        shipment: ShipmentReference,
        *,
        tenant_id: Any,
    ) -> ComplianceWorkflow:
        """Fix the workflow's shipment association (once, early).

        Re-binding the identical shipment is idempotent;
        switching shipments, binding after processing began,
        and any tenant/case mismatch fail closed.
        """
        require_tenant_context(tenant_id)
        tenant_uuid = tenant_id.tenant_id
        if not isinstance(workflow, ComplianceWorkflow):
            raise ShipmentIntakeError(
                "a compliance workflow is required")
        if not isinstance(shipment, ShipmentReference):
            raise ShipmentIntakeError(
                "a shipment reference is required; raw shipment "
                "data is never bound")
        if workflow.tenant_id != tenant_uuid:
            raise ShipmentIntakeError(
                "workflow belongs to a different tenant")
        if shipment.tenant_id != tenant_uuid:
            raise ShipmentIntakeError(
                "shipment belongs to a different tenant")
        if shipment.case_id != workflow.case_id:
            raise ShipmentIntakeError(
                "shipment belongs to a different case")
        if workflow.shipment_id is not None:
            if workflow.shipment_id != shipment.shipment_id:
                raise ShipmentIntakeError(
                    "workflow shipment identity cannot be "
                    "switched; this is an explicit invalid "
                    "operation")
            return workflow
        if workflow.state not in _BINDING_STATES:
            raise ShipmentIntakeError(
                f"shipment cannot be bound from workflow state "
                f"{workflow.state!r}")
        return replace(workflow, shipment_id=shipment.shipment_id)

    def reference_evidence(
        self,
        *,
        tenant_id: Any,
        evidence_id: UUID,
        case_id: UUID,
        requirement_id: UUID | None = None,
    ) -> SuppliedEvidenceReference:
        """Build the domain evidence reference for workflow supply."""
        require_tenant_context(tenant_id)
        return SuppliedEvidenceReference(
            tenant_id=tenant_id.tenant_id,
            evidence_id=evidence_id,
            case_id=case_id,
            requirement_id=requirement_id,
        )

    def supply_to_workflow(
        self,
        workflow: ComplianceWorkflow,
        evidence: SuppliedEvidenceReference,
        *,
        tenant_id: Any,
    ) -> ComplianceWorkflow:
        """Hand recorded evidence to the workflow (validates, delegates).

        Tenant and case are re-checked against the workflow;
        the actual state transition stays owned by
        `ComplianceWorkflowService.supply_evidence` (Phase 7.1,
        unchanged) — including its explicit duplicate
        behavior. Validation failures produce no new workflow
        state.
        """
        require_tenant_context(tenant_id)
        tenant_uuid = tenant_id.tenant_id
        if not isinstance(workflow, ComplianceWorkflow):
            raise ShipmentIntakeError(
                "a compliance workflow is required")
        if not isinstance(evidence, SuppliedEvidenceReference):
            raise ShipmentIntakeError(
                "a domain evidence reference is required; raw "
                "file content is never accepted as the evidence "
                "contract")
        if workflow.tenant_id != tenant_uuid:
            raise ShipmentIntakeError(
                "workflow belongs to a different tenant")
        if evidence.tenant_id != tenant_uuid:
            raise ShipmentIntakeError(
                "evidence belongs to a different tenant")
        if evidence.case_id != workflow.case_id:
            raise ShipmentIntakeError(
                "evidence belongs to a different case")
        return self._workflow_service.supply_evidence(
            workflow,
            tenant_id=tenant_id,
            evidence_ids=[evidence.evidence_id],
        )


__all__ = [
    "ShipmentIntakeError",
    "ShipmentIntakeService",
    "ShipmentReference",
    "SuppliedEvidenceReference",
]
