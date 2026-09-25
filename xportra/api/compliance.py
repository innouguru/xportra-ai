"""Thin compliance-workflow HTTP adapter (Phase 8.2).

Every handler follows the same shape:

1. ``require_permission`` resolves the authorized
   ``MemberContext`` (existing Phase 1 boundary — tenant
   from server-side membership, never the request body).
2. The handler builds an ``ApplicationContext`` from that
   membership plus the ``get_request_actor`` subject
   (Phase 8.3: Bearer subject, else ``None``).
3. Exactly one application use case is invoked.
4. Its DTO/record result is returned for serialization.

Handlers own no transitions, readiness math, reasoning,
retrieval, or tenant-ownership logic beyond invoking the
boundaries that do. Workflow records travel in the body
because no workflow store exists — the server holds no
session and no process-global registry.

Result-dependent reads that the normalized result
store (Phase 8.4) makes safe — finalize from the
server-known latest, stored package reads, stored
report reads — are exposed below. Anything still
requiring live in-session objects stays absent.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, status

from xportra.application.analysis import AnalysisApplicationService
from xportra.application.assessments import AssessmentApplicationService
from xportra.application.context import ApplicationContext
from xportra.application.workflows import WorkflowApplicationService

from .auth import MemberContext
from .authorization import (
    PROGRESS_COMPLIANCE_WORKFLOW,
    READ_TENANT_RESOURCE,
    RUN_COMPLIANCE_ANALYSIS,
)
from .dependencies import (
    RAGServiceDependency,
    ResultStoreDependency,
    ServicesDependency,
    get_request_actor,
    require_permission,
)
from .schemas import (
    AnalysisReportResponse,
    AnalyzeWorkflowRequest,
    AnalyzeWorkflowResponse,
    ApplicabilityRequest,
    ApplicabilityResponse,
    CaseReadinessRequest,
    CaseReadinessResponse,
    ClosureResponse,
    FinalizeWorkflowResponse,
    FinalPackageResponse,
    HistoryResponse,
    RequestEvidenceRequest,
    StartWorkflowRequest,
    SupplyEvidenceRequest,
    WorkflowActionRequest,
    WorkflowActionResponse,
    WorkflowSummaryResponse,
)

router = APIRouter(tags=["compliance-workflows"])


def _context(
    member: MemberContext, actor_id: UUID | None
) -> ApplicationContext:
    return ApplicationContext(
        actor_id=actor_id, tenant=member.tenant, role=member.role
    )


def _workflow_response(record: dict[str, Any], summary: dict[str, Any]):
    return {"workflow": record, "summary": summary}


@router.post(
    "/compliance/workflows/start",
    response_model=WorkflowActionResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_workflow(
    payload: StartWorkflowRequest,
    member: Annotated[
        MemberContext, Depends(require_permission(PROGRESS_COMPLIANCE_WORKFLOW))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Begin a workflow, binding the shipment when given."""
    service = WorkflowApplicationService()
    record, dto = service.start_workflow(
        _context(member, actor_id),
        payload.case_id,
        shipment_id=payload.shipment_id,
    )
    return _workflow_response(record, dto.to_dict())


@router.post(
    "/compliance/workflows/provide-information",
    response_model=WorkflowActionResponse,
)
def provide_information(
    payload: WorkflowActionRequest,
    member: Annotated[
        MemberContext, Depends(require_permission(PROGRESS_COMPLIANCE_WORKFLOW))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Record that shipment information was provided."""
    service = WorkflowApplicationService()
    record, dto = service.provide_information(
        _context(member, actor_id), payload.workflow.model_dump())
    return _workflow_response(record, dto.to_dict())


@router.post(
    "/compliance/workflows/note-evidence-pending",
    response_model=WorkflowActionResponse,
)
def note_evidence_pending(
    payload: WorkflowActionRequest,
    member: Annotated[
        MemberContext, Depends(require_permission(PROGRESS_COMPLIANCE_WORKFLOW))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Record that evidence is awaited."""
    service = WorkflowApplicationService()
    record, dto = service.note_evidence_pending(
        _context(member, actor_id), payload.workflow.model_dump())
    return _workflow_response(record, dto.to_dict())


@router.post(
    "/compliance/workflows/record-applicability",
    response_model=WorkflowActionResponse,
)
def record_applicability(
    payload: WorkflowActionRequest,
    member: Annotated[
        MemberContext, Depends(require_permission(PROGRESS_COMPLIANCE_WORKFLOW))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Record the deterministic applicability outcome."""
    service = WorkflowApplicationService()
    record, dto = service.record_applicability(
        _context(member, actor_id), payload.workflow.model_dump())
    return _workflow_response(record, dto.to_dict())


@router.post(
    "/compliance/workflows/submit-for-review",
    response_model=WorkflowActionResponse,
)
def submit_for_review(
    payload: WorkflowActionRequest,
    member: Annotated[
        MemberContext, Depends(require_permission(PROGRESS_COMPLIANCE_WORKFLOW))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Hand the available analysis to user review."""
    service = WorkflowApplicationService()
    record, dto = service.submit_for_review(
        _context(member, actor_id), payload.workflow.model_dump())
    return _workflow_response(record, dto.to_dict())


@router.post(
    "/compliance/workflows/request-additional-evidence",
    response_model=WorkflowActionResponse,
)
def request_additional_evidence(
    payload: RequestEvidenceRequest,
    member: Annotated[
        MemberContext, Depends(require_permission(PROGRESS_COMPLIANCE_WORKFLOW))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Flag requirements needing user action."""
    service = WorkflowApplicationService()
    record, dto = service.request_additional_evidence(
        _context(member, actor_id),
        payload.workflow.model_dump(),
        payload.requirement_ids,
    )
    return _workflow_response(record, dto.to_dict())


@router.post(
    "/compliance/workflows/supply-evidence",
    response_model=WorkflowActionResponse,
)
def supply_evidence(
    payload: SupplyEvidenceRequest,
    member: Annotated[
        MemberContext, Depends(require_permission(PROGRESS_COMPLIANCE_WORKFLOW))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Hand recorded evidence to the workflow for its case."""
    service = WorkflowApplicationService()
    record, dto = service.supply_evidence(
        _context(member, actor_id),
        payload.workflow.model_dump(),
        payload.evidence_id,
        requirement_id=payload.requirement_id,
    )
    return _workflow_response(record, dto.to_dict())


@router.post(
    "/compliance/workflows/status",
    response_model=WorkflowSummaryResponse,
)
def workflow_status(
    payload: WorkflowActionRequest,
    member: Annotated[
        MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Project the client-held workflow record to its summary."""
    service = WorkflowApplicationService()
    dto = service.get_workflow(
        _context(member, actor_id), payload.workflow.model_dump())
    return dto.to_dict()


@router.post(
    "/compliance/workflows/history",
    response_model=HistoryResponse,
)
def workflow_history(
    payload: WorkflowActionRequest,
    member: Annotated[
        MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Project workflow history (identifiers only, no live result)."""
    service = WorkflowApplicationService()
    dto = service.get_history(
        _context(member, actor_id), payload.workflow.model_dump())
    return dto.to_dict()


@router.post(
    "/compliance/workflows/is-closed",
    response_model=ClosureResponse,
)
def workflow_closure(
    payload: WorkflowActionRequest,
    member: Annotated[
        MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Report whether the workflow is permanently closed."""
    service = WorkflowApplicationService()
    record = payload.workflow.model_dump()
    closed = service.is_closed(_context(member, actor_id), record)
    return {"workflow_id": record["id"], "is_closed": closed}


@router.post(
    "/compliance/workflows/analyze",
    response_model=AnalyzeWorkflowResponse,
)
def analyze_workflow(
    payload: AnalyzeWorkflowRequest,
    rag: RAGServiceDependency,
    services: ServicesDependency,
    member: Annotated[
        MemberContext, Depends(require_permission(RUN_COMPLIANCE_ANALYSIS))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Run (or re-run) compliance analysis for the workflow.

    The state machine routes first runs vs re-runs; the
    live reasoning result is used in-request for the
    report DTO and then released. When the deployment
    wires the result store, the result is also retained
    for later cross-request finalization and reads;
    unwired deployments keep the previous behavior.
    """
    service = AnalysisApplicationService(
        rag_service=rag,
        result_store=getattr(services, "result_store", None),
    )
    record, _result, report = service.run_analysis(
        _context(member, actor_id),
        payload.workflow.model_dump(),
        payload.cases,
        mode=payload.mode,
        max_context_chars=payload.max_context_characters,
        top_k=payload.top_k,
        candidate_pool=payload.candidate_pool,
        decision_summary=payload.decision_summary,
    )
    return {"workflow": record, "report": report.to_dict()}


@router.post(
    "/compliance/assessments/applicability",
    response_model=ApplicabilityResponse,
)
def determine_applicability(
    payload: ApplicabilityRequest,
    member: Annotated[
        MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Determine which requirements apply (deterministic)."""
    service = AssessmentApplicationService()
    dto = service.determine_applicability(
        _context(member, actor_id),
        payload.requirements,
        exporter=payload.exporter,
        product=payload.product,
        destination=payload.destination,
        actor_role=payload.actor_role,
        business_characteristics=payload.business_characteristics,
    )
    return dto.to_dict()


@router.post(
    "/compliance/assessments/case-readiness",
    response_model=CaseReadinessResponse,
)
def assess_case_readiness(
    payload: CaseReadinessRequest,
    member: Annotated[
        MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Assess evidence coverage (information, not verdict)."""
    service = AssessmentApplicationService()
    dto = service.assess_case_readiness(
        _context(member, actor_id), payload.cases)
    return dto.to_dict()


@router.post(
    "/compliance/workflows/finalize",
    response_model=FinalizeWorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
def finalize_workflow(
    payload: WorkflowActionRequest,
    store: ResultStoreDependency,
    member: Annotated[
        MemberContext, Depends(require_permission(PROGRESS_COMPLIANCE_WORKFLOW))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Finalize the server-known latest result into a package.

    Human-review-gated: the workflow must already be in
    ``review_required`` with round linkage matching the
    recorded linkage exactly. Readiness, staleness, and
    terminal rules all come from the application/domain
    boundary — this handler only forwards the record.
    """
    service = WorkflowApplicationService(result_store=store)
    record, dto = service.finalize_stored_package(
        _context(member, actor_id), payload.workflow.model_dump())
    return {"workflow": record, "package": dto.to_dict()}


@router.post(
    "/compliance/workflows/package",
    response_model=FinalPackageResponse,
)
def stored_package(
    payload: WorkflowActionRequest,
    store: ResultStoreDependency,
    member: Annotated[
        MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Read the stored final package for a workflow."""
    service = WorkflowApplicationService(result_store=store)
    dto = service.get_stored_package(
        _context(member, actor_id), payload.workflow.model_dump())
    return dto.to_dict()


@router.get(
    "/compliance/reports/{report_id}",
    response_model=AnalysisReportResponse,
)
def stored_report(
    report_id: UUID,
    store: ResultStoreDependency,
    member: Annotated[
        MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))
    ],
    actor_id: Annotated[UUID | None, Depends(get_request_actor)],
):
    """Read a stored compliance report by identity."""
    service = WorkflowApplicationService(result_store=store)
    dto = service.describe_stored_report(
        _context(member, actor_id), report_id)
    return dto.to_dict()
