"""Read-only workflow history projection for Phase 7.4.

A deterministic view over what a Phase 7.1 compliance
workflow already retains — answering *what has happened to
this workflow, in what order, and what are its current
artifacts?* — without recording anything new:

```text
ComplianceWorkflow (+ optional latest result/package)
        ↓
WorkflowHistoryService.project (this module — pure)
        ↓
WorkflowHistoryView (frozen, serializable, read-only)
        ↓
Phase 8 can expose it through API
```

Underlying history sources (and only these):

- workflow identity (deterministic creation identity)
- bound shipment association (current association, not a
  binding event — binding order is architectural, not
  observed)
- ``supplied_evidence_ids`` in supply-append order (bare
  evidence identities; requirement linkage lives in the
  authoritative recording service, outside)
- ``rounds`` in ``round_index`` order, each carrying the
  recorded report/analysis/trace IDs and input
  fingerprints
- current ``state`` and ``open_requirements`` (current
  state, not events — intermediate states are not retained
  once left)
- optionally supplied latest Phase 6 result and final
  assessment package, each re-validated and shown by
  reference only

Deliberate limitations: no timestamps exist anywhere in
the workflow, so none are shown; entries are grouped by
kind in a fixed presentation order (creation → shipment →
supplies → rounds → final reference) and within each group
follow the recorded order — chronological interleaving
*across* groups (e.g. a supply relative to a later round)
is not recorded and therefore not claimed. Readiness is
computed on demand through the Phase 7.3 service when a
result is supplied — historical readiness checks were
never recorded and are never pretended. Phase 6.5 traces,
the Phase 3.5 summary, and Phase 7.3 readiness remain the
authorities for provenance, summary, and readiness; this
module copies no reasoning content, bytes, prompts, or
secrets.

This module performs no retrieval, no LLM invocation, no
persistence, no database access, no mutation, and no event
recording of any kind.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from .assessment_readiness import (
    AssessmentReadiness,
    AssessmentReadinessService,
)
from .compliance_workflow import (
    WORKFLOW_STATES,
    AssessmentPackage,
    ComplianceWorkflow,
)
from .errors import DomainValidationError, require_tenant_context
from .reasoning_application import ComplianceReasoningResult

HISTORY_WORKFLOW_CREATED = "workflow_created"
HISTORY_SHIPMENT_BOUND = "shipment_bound"
HISTORY_EVIDENCE_SUPPLIED = "evidence_supplied"
HISTORY_ANALYSIS_COMPLETED = "analysis_completed"
HISTORY_FINAL_PACKAGE_READY = "final_package_ready"


class WorkflowHistoryError(DomainValidationError):
    """A history-projection integrity failure (fail closed).

    Raised for malformed inputs and tenant/case/workflow
    mismatches across the workflow and its supplied
    artifacts — never converted into a partial or combined
    view.
    """


@dataclass(frozen=True, slots=True)
class WorkflowHistoryEntry:
    """One derived history item in presentation order.

    ``sequence`` is the position in the view's entry tuple
    (deterministic presentation order, not wall-clock
    time). ``references`` are ordered ``(label, value)``
    identifier pairs — never contents, prompts, or secrets.
    """

    sequence: int
    kind: str
    detail: str
    references: tuple[tuple[str, str], ...]

    def to_record(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "kind": self.kind,
            "detail": self.detail,
            "references": [
                {"label": label, "value": value}
                for label, value in self.references
            ],
        }


@dataclass(frozen=True, slots=True)
class FinalPackageReference:
    """Identity-only reference to a supplied final package."""

    workflow_id: UUID
    report_id: UUID
    round_count: int
    decision_summary_present: bool

    def to_record(self) -> dict[str, Any]:
        return {
            "workflow_id": str(self.workflow_id),
            "report_id": str(self.report_id),
            "round_count": self.round_count,
            "decision_summary_present": (
                self.decision_summary_present),
        }


@dataclass(frozen=True, slots=True)
class WorkflowHistoryView:
    """Immutable read-only projection of workflow history."""

    workflow_id: UUID
    tenant_id: UUID
    case_id: UUID
    shipment_id: UUID | None
    state: str
    entries: tuple[WorkflowHistoryEntry, ...]
    supplied_evidence_ids: tuple[UUID, ...]
    open_requirements: tuple[UUID, ...]
    round_count: int
    latest_report_id: UUID | None
    decision_summary_present: bool
    readiness: AssessmentReadiness | None
    final_package: FinalPackageReference | None

    def to_record(self) -> dict[str, Any]:
        return {
            "workflow_id": str(self.workflow_id),
            "tenant_id": str(self.tenant_id),
            "case_id": str(self.case_id),
            "shipment_id": (
                str(self.shipment_id)
                if self.shipment_id is not None else None),
            "state": self.state,
            "entries": [e.to_record() for e in self.entries],
            "supplied_evidence_ids": [
                str(v) for v in self.supplied_evidence_ids],
            "open_requirements": [
                str(v) for v in self.open_requirements],
            "round_count": self.round_count,
            "latest_report_id": (
                str(self.latest_report_id)
                if self.latest_report_id is not None else None),
            "decision_summary_present": (
                self.decision_summary_present),
            "readiness": (
                self.readiness.to_record()
                if self.readiness is not None else None),
            "final_package": (
                self.final_package.to_record()
                if self.final_package is not None else None),
        }


class WorkflowHistoryService:
    """Pure read-only projection over workflow artifacts."""

    def __init__(
        self,
        *,
        readiness_service: Any | None = None,
    ) -> None:
        self._readiness_service = (
            readiness_service or AssessmentReadinessService())
        if not callable(getattr(
                self._readiness_service, "check", None)):
            raise WorkflowHistoryError(
                "an assessment readiness service is required")

    def project(
        self,
        workflow: ComplianceWorkflow,
        *,
        tenant_id: Any,
        reasoning_result: ComplianceReasoningResult | None = None,
        assessment_package: AssessmentPackage | None = None,
    ) -> WorkflowHistoryView:
        """Derive the history view (no mutation, no calls).

        Supplied artifacts are re-validated against the
        workflow; any tenant/case/workflow/report mismatch
        fails closed. Readiness is computed on demand when
        a result is supplied, never stored.
        """
        require_tenant_context(tenant_id)
        tenant_uuid = tenant_id.tenant_id
        if not isinstance(workflow, ComplianceWorkflow):
            raise WorkflowHistoryError(
                "a compliance workflow is required")
        if workflow.state not in WORKFLOW_STATES:
            raise WorkflowHistoryError(
                "workflow state is malformed")
        if workflow.tenant_id != tenant_uuid:
            raise WorkflowHistoryError(
                "workflow belongs to a different tenant")
        if reasoning_result is not None:
            self._checked_result(
                workflow, reasoning_result, tenant_uuid)
        package_reference: FinalPackageReference | None = None
        if assessment_package is not None:
            package_reference = self._checked_package(
                workflow, assessment_package, tenant_uuid)

        entries = self._build_entries(
            workflow, package_reference)
        readiness: AssessmentReadiness | None = None
        if reasoning_result is not None:
            readiness = self._readiness_service.check(
                workflow, reasoning_result, tenant_id=tenant_id)
        latest_report_id = (
            workflow.rounds[-1].report_id if workflow.rounds
            else None)
        decision_summary_present = False
        if reasoning_result is not None:
            decision_summary_present = (
                reasoning_result.decision_summary is not None)
        elif assessment_package is not None:
            decision_summary_present = (
                assessment_package.decision_summary is not None)
        return WorkflowHistoryView(
            workflow_id=workflow.id,
            tenant_id=workflow.tenant_id,
            case_id=workflow.case_id,
            shipment_id=workflow.shipment_id,
            state=workflow.state,
            entries=tuple(entries),
            supplied_evidence_ids=tuple(
                workflow.supplied_evidence_ids),
            open_requirements=tuple(workflow.open_requirements),
            round_count=len(workflow.rounds),
            latest_report_id=latest_report_id,
            decision_summary_present=decision_summary_present,
            readiness=readiness,
            final_package=package_reference,
        )

    # ------------------------------------------------------------------
    # projection integrity (fail closed)
    # ------------------------------------------------------------------

    @staticmethod
    def _checked_result(
        workflow: ComplianceWorkflow,
        reasoning_result: ComplianceReasoningResult,
        tenant_uuid: UUID,
    ) -> None:
        if not isinstance(
                reasoning_result, ComplianceReasoningResult):
            raise WorkflowHistoryError(
                "a compliance reasoning result is required")
        if reasoning_result.tenant_id != tenant_uuid:
            raise WorkflowHistoryError(
                "reasoning result belongs to a different tenant")
        if reasoning_result.case_id != workflow.case_id:
            raise WorkflowHistoryError(
                "reasoning result belongs to a different case")
        if not workflow.rounds:
            raise WorkflowHistoryError(
                "reasoning result has no recorded round to "
                "attach to")
        if (reasoning_result.report.id
                != workflow.rounds[-1].report_id):
            raise WorkflowHistoryError(
                "reasoning result does not match the latest "
                "recorded round")

    @staticmethod
    def _checked_package(
        workflow: ComplianceWorkflow,
        assessment_package: AssessmentPackage,
        tenant_uuid: UUID,
    ) -> FinalPackageReference:
        if not isinstance(assessment_package, AssessmentPackage):
            raise WorkflowHistoryError(
                "a final assessment package is required")
        if assessment_package.workflow_id != workflow.id:
            raise WorkflowHistoryError(
                "assessment package belongs to a different "
                "workflow")
        if assessment_package.tenant_id != tenant_uuid:
            raise WorkflowHistoryError(
                "assessment package belongs to a different "
                "tenant")
        if assessment_package.case_id != workflow.case_id:
            raise WorkflowHistoryError(
                "assessment package belongs to a different case")
        return FinalPackageReference(
            workflow_id=assessment_package.workflow_id,
            report_id=assessment_package.reasoning_result.report.id,
            round_count=len(assessment_package.rounds),
            decision_summary_present=(
                assessment_package.decision_summary is not None),
        )

    @staticmethod
    def _build_entries(
        workflow: ComplianceWorkflow,
        package_reference: FinalPackageReference | None,
    ) -> list[WorkflowHistoryEntry]:
        entries: list[WorkflowHistoryEntry] = []
        entries.append(WorkflowHistoryEntry(
            sequence=len(entries),
            kind=HISTORY_WORKFLOW_CREATED,
            detail="workflow began",
            references=(
                ("workflow_id", str(workflow.id)),
                ("tenant_id", str(workflow.tenant_id)),
                ("case_id", str(workflow.case_id)),
            ),
        ))
        if workflow.shipment_id is not None:
            entries.append(WorkflowHistoryEntry(
                sequence=len(entries),
                kind=HISTORY_SHIPMENT_BOUND,
                detail="shipment reference bound",
                references=(
                    ("shipment_id", str(workflow.shipment_id)),
                    ("case_id", str(workflow.case_id)),
                    ("tenant_id", str(workflow.tenant_id)),
                ),
            ))
        for position, evidence_id in enumerate(
                workflow.supplied_evidence_ids):
            entries.append(WorkflowHistoryEntry(
                sequence=len(entries),
                kind=HISTORY_EVIDENCE_SUPPLIED,
                detail="evidence reference supplied",
                references=(
                    ("evidence_id", str(evidence_id)),
                    ("supply_position", str(position)),
                ),
            ))
        for round_record in workflow.rounds:
            references: list[tuple[str, str]] = [
                ("round_index", str(round_record.round_index)),
                ("report_id", str(round_record.report_id)),
            ]
            references.extend(
                ("analysis_id", str(value))
                for value in round_record.analysis_ids)
            references.extend(
                ("trace_id", str(value))
                for value in round_record.trace_ids)
            references.extend(
                ("input_fingerprint", value)
                for value in round_record.input_fingerprints)
            entries.append(WorkflowHistoryEntry(
                sequence=len(entries),
                kind=HISTORY_ANALYSIS_COMPLETED,
                detail="analysis round completed",
                references=tuple(references),
            ))
        if package_reference is not None:
            entries.append(WorkflowHistoryEntry(
                sequence=len(entries),
                kind=HISTORY_FINAL_PACKAGE_READY,
                detail="final assessment package available",
                references=(
                    ("workflow_id",
                     str(package_reference.workflow_id)),
                    ("report_id",
                     str(package_reference.report_id)),
                    ("round_count",
                     str(package_reference.round_count)),
                ),
            ))
        return entries


__all__ = [
    "HISTORY_ANALYSIS_COMPLETED",
    "HISTORY_EVIDENCE_SUPPLIED",
    "HISTORY_FINAL_PACKAGE_READY",
    "HISTORY_SHIPMENT_BOUND",
    "HISTORY_WORKFLOW_CREATED",
    "FinalPackageReference",
    "WorkflowHistoryEntry",
    "WorkflowHistoryError",
    "WorkflowHistoryService",
    "WorkflowHistoryView",
]
