"""Compliance-workflow use cases (Phase 7 journey orchestration).

``WorkflowApplicationService`` coordinates the existing
domain services — never reimplementing them:

- ``ComplianceWorkflowService`` owns every state
  transition, analysis delegation, finalization, and the
  terminal closure rule.
- ``ShipmentIntakeService`` owns shipment binding and
  the evidence-supply handoff.
- ``AssessmentReadinessService`` owns the readiness
  verdict behind ``check_readiness`` / ``finalize_package``.
- ``WorkflowHistoryService`` owns the history projection.

Use cases are stateless: callers pass the workflow's
``to_record()`` form in and receive the updated record
form back. No workflow persistence exists in the domain,
and this layer invents none — live result/package
objects travel in-session with the caller, while records
(and DTOs) are the wire-stable surface. A future Phase 8
store may persist records; the contract already supports
it without change.

Tenant safety is deterministic and never message-based:
record tenant is compared against the context tenant
before any domain call (``TenantMismatchError``);
terminal state is checked via the explicit 7.5 predicate
before mutating calls (``TerminalWorkflowError``); the
supply reference is built from context tenant plus
workflow case — never from client-supplied scope.
Remaining domain validation failures propagate as
``InvalidTransitionError`` with the domain detail and
cause preserved.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from xportra.domain.assessment_readiness import (
    READINESS_ANALYSIS_STALE,
    AssessmentReadinessService,
)
from xportra.domain.compliance_workflow import (
    WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY,
    AssessmentPackage,
    ComplianceWorkflow,
    ComplianceWorkflowError,
    ComplianceWorkflowService,
    WorkflowAnalysisRound,
)
from xportra.domain.reasoning_application import (
    ComplianceReasoningResult,
)
from xportra.domain.shipment_intake import (
    ShipmentIntakeError,
    ShipmentIntakeService,
    SuppliedEvidenceReference,
)
from xportra.domain.workflow_history import (
    WorkflowHistoryError,
    WorkflowHistoryService,
)

from ._guards import (
    checked_context,
    checked_uuid,
    checked_uuid_list,
    ensure_tenant_match,
    workflow_from_record,
)
from .context import ApplicationContext
from .dtos import (
    AnalysisReportDTO,
    FinalPackageDTO,
    HistoryDTO,
    ReadinessDTO,
    WorkflowDTO,
)
from .errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
    InvalidTransitionError,
    StaleAnalysisError,
    TerminalWorkflowError,
    WorkflowNotReadyError,
)


class WorkflowApplicationService:
    """Stateless use cases over the compliance-workflow journey."""

    def __init__(
        self,
        *,
        workflow_service: ComplianceWorkflowService | None = None,
        intake_service: ShipmentIntakeService | None = None,
        readiness_service: AssessmentReadinessService | None = None,
        history_service: WorkflowHistoryService | None = None,
        result_store: Any | None = None,
    ) -> None:
        self._workflows = (
            workflow_service or ComplianceWorkflowService())
        self._intake = intake_service or ShipmentIntakeService()
        self._readiness = (
            readiness_service or AssessmentReadinessService())
        self._history = history_service or WorkflowHistoryService()
        for name, service, method in (
            ("workflow", self._workflows, "begin"),
            ("intake", self._intake, "supply_to_workflow"),
            ("readiness", self._readiness, "check"),
            ("history", self._history, "project"),
        ):
            if not callable(getattr(service, method, None)):
                raise ApplicationValidationError(
                    f"a {name} service is required")
        if result_store is not None:
            for method in ("load_result", "store_package_linkage",
                           "load_package", "rounds_for_workflow",
                           "latest_round_for_workflow"):
                if not callable(getattr(result_store, method, None)):
                    raise ApplicationValidationError(
                        "a result store is required")
        self._result_store = result_store

    # ------------------------------------------------------------------
    # progression use cases (items 1, 2, 3, 8, 10)
    # ------------------------------------------------------------------

    def start_workflow(
        self,
        ctx: ApplicationContext,
        case_id: UUID,
        shipment_id: UUID | None = None,
    ) -> tuple[dict[str, Any], WorkflowDTO]:
        """Begin a workflow, binding the shipment when given."""
        ctx = checked_context(ctx)
        checked_uuid(case_id, "case")
        if shipment_id is not None:
            checked_uuid(shipment_id, "shipment")
        try:
            workflow = self._workflows.begin(
                tenant_id=ctx.tenant, case_id=case_id)
            if shipment_id is not None:
                reference = self._intake.register_shipment(
                    tenant_id=ctx.tenant,
                    shipment_id=shipment_id, case_id=case_id)
                workflow = self._intake.bind_shipment(
                    workflow, reference, tenant_id=ctx.tenant)
        except (ComplianceWorkflowError,
                ShipmentIntakeError) as cause:
            raise InvalidTransitionError(
                str(cause), cause=cause) from cause
        return workflow.to_record(), self._describe(ctx, workflow)

    def provide_information(
        self,
        ctx: ApplicationContext,
        workflow_record: dict[str, Any],
    ) -> tuple[dict[str, Any], WorkflowDTO]:
        """Record that shipment information was provided."""
        workflow = self._checked_open(ctx, workflow_record)
        return self._transition(
            workflow, ctx, "provide_information")

    def note_evidence_pending(
        self,
        ctx: ApplicationContext,
        workflow_record: dict[str, Any],
    ) -> tuple[dict[str, Any], WorkflowDTO]:
        """Record that evidence is awaited."""
        workflow = self._checked_open(ctx, workflow_record)
        return self._transition(
            workflow, ctx, "note_evidence_pending")

    def record_applicability(
        self,
        ctx: ApplicationContext,
        workflow_record: dict[str, Any],
    ) -> tuple[dict[str, Any], WorkflowDTO]:
        """Record the deterministic applicability outcome."""
        workflow = self._checked_open(ctx, workflow_record)
        return self._transition(
            workflow, ctx, "record_applicability_determined")

    def submit_for_review(
        self,
        ctx: ApplicationContext,
        workflow_record: dict[str, Any],
    ) -> tuple[dict[str, Any], WorkflowDTO]:
        """Hand the available analysis to user review."""
        workflow = self._checked_open(ctx, workflow_record)
        return self._transition(
            workflow, ctx, "submit_for_review")

    def supply_evidence(
        self,
        ctx: ApplicationContext,
        workflow_record: dict[str, Any],
        evidence_id: UUID,
        requirement_id: UUID | None = None,
    ) -> tuple[dict[str, Any], WorkflowDTO]:
        """Hand recorded evidence to the workflow for its case."""
        ctx = checked_context(ctx)
        workflow = self._owned_workflow(ctx, workflow_record)
        checked_uuid(evidence_id, "evidence")
        if requirement_id is not None:
            checked_uuid(requirement_id, "requirement")
        self._ensure_open(ctx, workflow)
        try:
            reference = SuppliedEvidenceReference(
                tenant_id=ctx.tenant_id,
                evidence_id=evidence_id,
                case_id=workflow.case_id,
                requirement_id=requirement_id,
            )
            advanced = self._intake.supply_to_workflow(
                workflow, reference, tenant_id=ctx.tenant)
        except (ComplianceWorkflowError,
                ShipmentIntakeError) as cause:
            raise InvalidTransitionError(
                str(cause), cause=cause) from cause
        return advanced.to_record(), self._describe(ctx, advanced)

    def request_additional_evidence(
        self,
        ctx: ApplicationContext,
        workflow_record: dict[str, Any],
        requirement_ids: list[UUID] | tuple[UUID, ...],
    ) -> tuple[dict[str, Any], WorkflowDTO]:
        """Flag requirements needing user action."""
        workflow = self._checked_open(ctx, workflow_record)
        checked_ids = checked_uuid_list(
            requirement_ids, "requirement")
        try:
            advanced = self._workflows.request_additional_evidence(
                workflow, tenant_id=ctx.tenant,
                requirement_ids=checked_ids)
        except ComplianceWorkflowError as cause:
            raise InvalidTransitionError(
                str(cause), cause=cause) from cause
        return advanced.to_record(), self._describe(ctx, advanced)

    def check_readiness(
        self,
        ctx: ApplicationContext,
        workflow_record: dict[str, Any],
        reasoning_result: ComplianceReasoningResult,
    ) -> ReadinessDTO:
        """Evaluate finalization readiness (read-only)."""
        ctx = checked_context(ctx)
        workflow = self._owned_workflow(ctx, workflow_record)
        if not isinstance(
                reasoning_result, ComplianceReasoningResult):
            raise ApplicationValidationError(
                "a compliance reasoning result is required")
        try:
            readiness = self._readiness.check(
                workflow, reasoning_result, tenant_id=ctx.tenant)
        except ComplianceWorkflowError as cause:
            raise InvalidTransitionError(
                str(cause), cause=cause) from cause
        return ReadinessDTO.from_record(readiness.to_record())

    def finalize_package(
        self,
        ctx: ApplicationContext,
        workflow_record: dict[str, Any],
        reasoning_result: ComplianceReasoningResult,
    ) -> tuple[dict[str, Any], FinalPackageDTO]:
        """Produce the final assessment package when ready."""
        ctx = checked_context(ctx)
        workflow = self._owned_workflow(ctx, workflow_record)
        if not isinstance(
                reasoning_result, ComplianceReasoningResult):
            raise ApplicationValidationError(
                "a compliance reasoning result is required")
        self._ensure_open(ctx, workflow)
        try:
            readiness = self._readiness.check(
                workflow, reasoning_result, tenant_id=ctx.tenant)
        except ComplianceWorkflowError as cause:
            raise InvalidTransitionError(
                str(cause), cause=cause) from cause
        if not readiness.ready:
            reasons = tuple(
                (issue.code, issue.detail)
                for issue in readiness.reasons)
            detail = "; ".join(
                f"{code}: {detail}"
                for code, detail in reasons)
            if any(code == READINESS_ANALYSIS_STALE
                   for code, _ in reasons):
                raise StaleAnalysisError(
                    f"workflow is not ready: {detail}",
                    reasons=reasons)
            raise WorkflowNotReadyError(
                f"workflow is not ready: {detail}",
                reasons=reasons)
        try:
            advanced, package = self._workflows.finalize(
                workflow, reasoning_result, tenant_id=ctx.tenant)
        except ComplianceWorkflowError as cause:
            raise InvalidTransitionError(
                str(cause), cause=cause) from cause
        return (advanced.to_record(),
                FinalPackageDTO.from_package(package))

    # ------------------------------------------------------------------
    # read use cases (items 7, 11, 12)
    # ------------------------------------------------------------------

    def get_workflow(
        self,
        ctx: ApplicationContext,
        workflow_record: dict[str, Any],
    ) -> WorkflowDTO:
        """Project the workflow record to its client DTO."""
        ctx = checked_context(ctx)
        workflow = self._owned_workflow(ctx, workflow_record)
        return self._describe(ctx, workflow)

    def is_closed(
        self,
        ctx: ApplicationContext,
        workflow_record: dict[str, Any],
    ) -> bool:
        """Report whether the workflow is permanently closed."""
        ctx = checked_context(ctx)
        workflow = self._owned_workflow(ctx, workflow_record)
        try:
            return self._workflows.is_closed(
                workflow, tenant_id=ctx.tenant)
        except ComplianceWorkflowError as cause:
            raise InvalidTransitionError(
                str(cause), cause=cause) from cause

    def get_history(
        self,
        ctx: ApplicationContext,
        workflow_record: dict[str, Any],
        reasoning_result: ComplianceReasoningResult | None = None,
        assessment_package: Any | None = None,
    ) -> HistoryDTO:
        """Project workflow history (identifiers only)."""
        ctx = checked_context(ctx)
        workflow = self._owned_workflow(ctx, workflow_record)
        if reasoning_result is not None:
            self._checked_artifact_scope(
                ctx, workflow, reasoning_result)
        if assessment_package is not None:
            self._checked_package_scope(
                ctx, workflow, assessment_package)
        try:
            view = self._history.project(
                workflow, tenant_id=ctx.tenant,
                reasoning_result=reasoning_result,
                assessment_package=assessment_package)
        except WorkflowHistoryError as cause:
            raise ApplicationValidationError(
                str(cause), cause=cause) from cause
        return HistoryDTO.from_record(view.to_record())

    def get_package(
        self,
        ctx: ApplicationContext,
        assessment_package: Any,
    ) -> FinalPackageDTO:
        """Project a final assessment package to its DTO."""
        ctx = checked_context(ctx)
        if not isinstance(assessment_package, AssessmentPackage):
            raise ApplicationValidationError(
                "a final assessment package is required")
        ensure_tenant_match(
            ctx, assessment_package.tenant_id,
            "assessment package")
        return FinalPackageDTO.from_package(assessment_package)

    # ------------------------------------------------------------------
    # stored-result use cases (require a configured result store)
    # ------------------------------------------------------------------

    def load_current_result(
        self,
        ctx: ApplicationContext,
        workflow_record: dict[str, Any],
    ) -> tuple[dict[str, Any], ComplianceReasoningResult]:
        """Resolve the server-known latest result for a workflow.

        The recorded round linkage — not the submitted
        record — decides what is current. No stored rounds
        means no result, never an implicit fallback.
        """
        store = self._require_store()
        ctx = checked_context(ctx)
        workflow = self._owned_workflow(ctx, workflow_record)
        latest = store.latest_round_for_workflow(
            ctx, workflow.id)
        if latest is None:
            raise ApplicationNotFoundError(
                "no stored result for workflow")
        if latest["case_id"] != workflow.case_id:
            raise ApplicationValidationError(
                "stored rounds belong to a different case")
        return latest, store.load_result(ctx, latest["report_id"])

    def finalize_stored_package(
        self,
        ctx: ApplicationContext,
        workflow_record: dict[str, Any],
    ) -> tuple[dict[str, Any], FinalPackageDTO]:
        """Finalize using the server-known latest result.

        The submitted record's round linkage must match the
        recorded linkage exactly — a forged or stale record
        fails closed instead of finalizing the wrong round.
        An already-finalized workflow fails as terminal,
        backed by the package row's uniqueness.
        """
        store = self._require_store()
        ctx = checked_context(ctx)
        workflow = self._owned_workflow(ctx, workflow_record)
        self._ensure_open(ctx, workflow)
        server_rounds = store.rounds_for_workflow(
            ctx, workflow.id)
        if not server_rounds:
            raise ApplicationNotFoundError(
                "no stored result for workflow")
        claimed = [(r.round_index, str(r.report_id))
                   for r in workflow.rounds]
        recorded = [(row["round_index"], str(row["report_id"]))
                    for row in server_rounds]
        if claimed != recorded:
            raise StaleAnalysisError(
                "stored rounds do not match the submitted "
                "workflow record",
                reasons=(("stale_round_linkage",
                          "stored rounds do not match"),))
        if server_rounds[-1]["case_id"] != workflow.case_id:
            raise ApplicationValidationError(
                "stored rounds belong to a different case")
        existing = store.load_package(ctx, workflow.id)
        if existing is not None:
            raise TerminalWorkflowError(
                "workflow is already finalized")
        result = store.load_result(
            ctx, server_rounds[-1]["report_id"])
        advanced_record, dto = self.finalize_package(
            ctx, workflow_record, result)
        advanced = workflow_from_record(advanced_record)
        store.store_package_linkage(
            ctx, advanced, result.report.id,
            server_rounds[-1]["round_index"],
            list(advanced.open_requirements))
        return advanced_record, dto

    def get_stored_package(
        self,
        ctx: ApplicationContext,
        workflow_record: dict[str, Any],
    ) -> FinalPackageDTO:
        """Read the stored final package for a workflow."""
        store = self._require_store()
        ctx = checked_context(ctx)
        workflow = self._owned_workflow(ctx, workflow_record)
        linkage = store.load_package(ctx, workflow.id)
        if linkage is None:
            raise ApplicationNotFoundError(
                "no final package stored for workflow")
        if linkage["case_id"] != workflow.case_id:
            raise ApplicationValidationError(
                "stored package belongs to a different case")
        result = store.load_result(ctx, linkage["report_id"])
        server_rounds = store.rounds_for_workflow(
            ctx, workflow.id)
        rounds = tuple(
            WorkflowAnalysisRound(
                round_index=row["round_index"],
                report_id=row["report_id"]
                if isinstance(row["report_id"], UUID)
                else UUID(str(row["report_id"])),
                analysis_ids=tuple(
                    a if isinstance(a, UUID) else UUID(str(a))
                    for a in row["analysis_ids"]),
                trace_ids=tuple(
                    t if isinstance(t, UUID) else UUID(str(t))
                    for t in row["trace_ids"]),
                input_fingerprints=tuple(
                    row["input_fingerprints"]),
            )
            for row in server_rounds
        )
        package = AssessmentPackage(
            workflow_id=workflow.id,
            tenant_id=ctx.tenant_id,
            case_id=workflow.case_id,
            shipment_id=workflow.shipment_id,
            state=WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY,
            reasoning_result=result,
            decision_summary=result.decision_summary,
            rounds=rounds,
            open_requirements=tuple(
                o if isinstance(o, UUID) else UUID(str(o))
                for o in linkage["open_requirements"]),
        )
        return FinalPackageDTO.from_package(package)

    def describe_stored_report(
        self,
        ctx: ApplicationContext,
        report_id: UUID,
    ) -> AnalysisReportDTO:
        """Read a stored report by identity (tenant-scoped)."""
        store = self._require_store()
        ctx = checked_context(ctx)
        if not isinstance(report_id, UUID):
            raise ApplicationValidationError(
                "a report identity UUID is required")
        return AnalysisReportDTO.from_result(
            store.load_result(ctx, report_id))

    def _require_store(self) -> Any:
        if self._result_store is None:
            raise ApplicationValidationError(
                "no result store is configured")
        return self._result_store

    # ------------------------------------------------------------------
    # ownership and transition guards (fail closed)
    # ------------------------------------------------------------------

    def _owned_workflow(
        self,
        ctx: ApplicationContext,
        workflow_record: dict[str, Any],
    ) -> ComplianceWorkflow:
        workflow = workflow_from_record(workflow_record)
        ensure_tenant_match(ctx, workflow.tenant_id, "workflow")
        return workflow

    def _checked_open(
        self,
        ctx: ApplicationContext,
        workflow_record: dict[str, Any],
    ) -> ComplianceWorkflow:
        ctx = checked_context(ctx)
        workflow = self._owned_workflow(ctx, workflow_record)
        self._ensure_open(ctx, workflow)
        return workflow

    def _ensure_open(
        self,
        ctx: ApplicationContext,
        workflow: ComplianceWorkflow,
    ) -> None:
        try:
            closed = self._workflows.is_closed(
                workflow, tenant_id=ctx.tenant)
        except ComplianceWorkflowError as cause:
            raise InvalidTransitionError(
                str(cause), cause=cause) from cause
        if closed:
            raise TerminalWorkflowError(
                "workflow is permanently closed; start a fresh "
                "progression for further work")

    def _transition(
        self,
        workflow: ComplianceWorkflow,
        ctx: ApplicationContext,
        operation: str,
    ) -> tuple[dict[str, Any], WorkflowDTO]:
        try:
            advanced = getattr(self._workflows, operation)(
                workflow, tenant_id=ctx.tenant)
        except ComplianceWorkflowError as cause:
            raise InvalidTransitionError(
                str(cause), cause=cause) from cause
        return advanced.to_record(), self._describe(ctx, advanced)

    def _describe(self, ctx: ApplicationContext,
                  workflow: ComplianceWorkflow) -> WorkflowDTO:
        try:
            closed = self._workflows.is_closed(
                workflow, tenant_id=ctx.tenant)
        except ComplianceWorkflowError as cause:
            raise InvalidTransitionError(
                str(cause), cause=cause) from cause
        return WorkflowDTO.from_record(
            workflow.to_record(), is_closed=closed)

    def _checked_artifact_scope(
        self,
        ctx: ApplicationContext,
        workflow: ComplianceWorkflow,
        reasoning_result: ComplianceReasoningResult,
    ) -> None:
        if not isinstance(
                reasoning_result, ComplianceReasoningResult):
            raise ApplicationValidationError(
                "a compliance reasoning result is required")
        ensure_tenant_match(
            ctx, reasoning_result.tenant_id, "reasoning result")
        if reasoning_result.case_id != workflow.case_id:
            raise ApplicationValidationError(
                "reasoning result belongs to a different case")

    def _checked_package_scope(
        self,
        ctx: ApplicationContext,
        workflow: ComplianceWorkflow,
        assessment_package: Any,
    ) -> None:
        if not isinstance(assessment_package, AssessmentPackage):
            raise ApplicationValidationError(
                "a final assessment package is required")
        ensure_tenant_match(
            ctx, assessment_package.tenant_id,
            "assessment package")
        if assessment_package.case_id != workflow.case_id:
            raise ApplicationValidationError(
                "assessment package belongs to a different case")
        if assessment_package.workflow_id != workflow.id:
            raise ApplicationValidationError(
                "assessment package belongs to a different "
                "workflow")


__all__ = [
    "WorkflowApplicationService",
]
