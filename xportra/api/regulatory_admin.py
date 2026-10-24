"""Regulatory source administration API (Phase 4D.10 Task 3).

Endpoints for source registration, artifact upload, and ingestion job
tracking. Every route requires an active global staff grant
(``GRANT_MANAGE``) — tenant membership or ownership alone is
insufficient.
"""
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from xportra.application.errors import ApplicationNotFoundError
from xportra.application.regulatory_candidate_extraction_service import (
    RegulatoryCandidateExtractionService,
)
from xportra.application.regulatory_governance_service import (
    RegulatoryGovernanceService,
)
from xportra.application.regulatory_source_intake_service import (
    RegulatorySourceIntakeService,
)
from xportra.application.regulatory_stage_a_review_service import (
    RegulatoryStageAReviewService,
)
from xportra.application.regulatory_publication_eligibility_service import (
    RegulatoryPublicationEligibilityService,
)
from xportra.application.regulatory_stage_b_review_service import (
    RegulatoryStageBReviewService,
)
from xportra.api.dependencies import (
    GlobalStaffDependency,
    StageADependency,
    StageBDependency,
    get_services,
)
from xportra.api.errors import APIError
from xportra.api.schemas import (
    RegulatoryArtifactListResponse,
    RegulatoryArtifactResponse,
    RegulatoryArtifactUploadRequest,
    RegulatoryCandidateListResponse,
    RegulatoryCandidateResponse,
    RegulatoryExtractRequest,
    RegulatoryExtractResponse,
    RegulatoryGovernanceFlagListResponse,
    RegulatoryGovernanceFlagResponse,
    RegulatoryIngestionJobListResponse,
    RegulatoryIngestionJobResponse,
    RegulatoryManualCandidateRequest,
    RegulatoryManualCandidateResponse,
    RegulatorySourceCreateRequest,
    RegulatorySourceListResponse,
    RegulatorySourceResponse,
    RegulatorySupersessionRequest,
    RegulatorySupersessionResponse,
    RegulatoryStageAReviewHistoryListResponse,
    RegulatoryStageAReviewHistoryResponse,
    RegulatoryStageAReviewRequest,
    RegulatoryStageAReviewResponse,
    RegulatoryStageBReviewHistoryListResponse,
    RegulatoryStageBReviewHistoryResponse,
    RegulatoryStageBReviewRequest,
    RegulatoryEligibleRequirementsResponse,
    RegulatoryEligibleRequirementResponse,
    RegulatoryStageBReviewResponse,
)

router = APIRouter(tags=["regulatory-admin"])


def _intake_service(services: Any = Depends(get_services)) -> RegulatorySourceIntakeService:
    database = getattr(services, "database", None)
    if database is None:
        raise APIError(
            503, "application_not_ready",
            "Application services are not initialized",
        )
    return RegulatorySourceIntakeService(database)


IntakeServiceDependency = Annotated[
    RegulatorySourceIntakeService, Depends(_intake_service)
]


def _extraction_service(services: Any = Depends(get_services)) -> RegulatoryCandidateExtractionService:
    database = getattr(services, "database", None)
    if database is None:
        raise APIError(
            503, "application_not_ready",
            "Application services are not initialized",
        )
    return RegulatoryCandidateExtractionService(database)


ExtractionServiceDependency = Annotated[
    RegulatoryCandidateExtractionService, Depends(_extraction_service)
]


def _stage_a_service(services: Any = Depends(get_services)) -> RegulatoryStageAReviewService:
    database = getattr(services, "database", None)
    if database is None:
        raise APIError(
            503, "application_not_ready",
            "Application services are not initialized",
        )
    return RegulatoryStageAReviewService(database)


StageAServiceDependency = Annotated[
    RegulatoryStageAReviewService, Depends(_stage_a_service)
]


def _stage_b_service(services: Any = Depends(get_services)) -> RegulatoryStageBReviewService:
    database = getattr(services, "database", None)
    if database is None:
        raise APIError(
            503, "application_not_ready",
            "Application services are not initialized",
        )
    return RegulatoryStageBReviewService(database)


StageBServiceDependency = Annotated[
    RegulatoryStageBReviewService, Depends(_stage_b_service)
]


def _supersession_service(services: Any = Depends(get_services)) -> RegulatorySourceIntakeService:
    database = getattr(services, "database", None)
    if database is None:
        raise APIError(
            503, "application_not_ready",
            "Application services are not initialized",
        )
    return RegulatorySourceIntakeService(database)


SupersessionServiceDependency = Annotated[
    RegulatorySourceIntakeService, Depends(_supersession_service)
]


def _governance_service(services: Any = Depends(get_services)) -> RegulatoryGovernanceService:
    database = getattr(services, "database", None)
    if database is None:
        raise APIError(
            503, "application_not_ready",
            "Application services are not initialized",
        )
    return RegulatoryGovernanceService(database)


GovernanceServiceDependency = Annotated[
    RegulatoryGovernanceService, Depends(_governance_service)
]


def _source_response(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": source["id"],
        "authority_id": source["authority_id"],
        "jurisdiction": source["jurisdiction"],
        "title": source["title"],
        "version": source.get("version"),
        "status": source["status"],
        "effective_date": source.get("effective_date"),
        "publication_date": source.get("publication_date"),
        "source_url": source.get("source_url"),
        "retrieval_timestamp": source.get("retrieval_timestamp"),
        "supersedes_source_id": source.get("supersedes_source_id"),
        "superseded_by_source_id": source.get("superseded_by_source_id"),
        "created_at": source["created_at"],
        "updated_at": source["updated_at"],
    }


def _artifact_response(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": artifact["id"],
        "source_id": artifact["source_id"],
        "content_hash": artifact["content_hash"],
        "content_length": artifact["content_length"],
        "content_type": artifact["content_type"],
        "acquisition_channel": artifact["acquisition_channel"],
        "acquired_at": artifact["acquired_at"],
        "status": artifact["status"],
        "source_version": artifact.get("source_version"),
        "created_at": artifact["created_at"],
        "updated_at": artifact["updated_at"],
    }


def _job_response(job: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": job["id"],
        "artifact_id": job["artifact_id"],
        "source_id": job["source_id"],
        "status": job["status"],
        "attempt_number": job["attempt_number"],
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "error_details": job.get("error_details"),
        "parser_version": job["parser_version"],
        "actor_user_id": job.get("actor_user_id"),
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
    }


def _candidate_response(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": candidate["id"],
        "source_id": candidate["source_id"],
        "artifact_id": candidate["artifact_id"],
        "normalized_document_id": candidate.get("normalized_document_id"),
        "requirement_text": candidate["requirement_text"],
        "requirement_type": candidate["requirement_type"],
        "source_location": candidate.get("source_location") or {},
        "position": candidate["position"],
        "actor": candidate.get("actor"),
        "status": candidate["status"],
        "extraction_outcome": candidate["extraction_outcome"],
        "parser_version": candidate.get("parser_version"),
        "manual_entry": candidate.get("manual_entry", False),
        "reviewer_user_id": candidate.get("reviewer_user_id"),
        "reviewed_at": candidate.get("reviewed_at"),
        "ingestion_job_id": candidate.get("ingestion_job_id"),
        "created_at": candidate["created_at"],
        "updated_at": candidate["updated_at"],
    }


@router.post(
    "/regulatory/sources",
    response_model=RegulatorySourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_source(
    payload: RegulatorySourceCreateRequest,
    service: IntakeServiceDependency,
    actor_id: GlobalStaffDependency,
):
    """Register a regulatory source.

    ``source_url`` is stored as metadata only; it is never fetched,
    crawled, or dereferenced by the server.
    """
    row = service.register_source(
        actor_user_id=actor_id,
        authority_id=payload.authority_id,
        jurisdiction=payload.jurisdiction,
        title=payload.title,
        version=payload.version,
        status=payload.status,
        effective_date=payload.effective_date,
        publication_date=payload.publication_date,
        source_url=payload.source_url,
    )
    return _source_response(row)


@router.get(
    "/regulatory/sources/{source_id}",
    response_model=RegulatorySourceResponse,
)
def get_source(
    source_id: UUID,
    service: IntakeServiceDependency,
    actor_id: GlobalStaffDependency,
):
    """Retrieve a regulatory source by ID."""
    row = service.get_source(source_id)
    if row is None:
        raise ApplicationNotFoundError("regulatory source not found")
    return _source_response(row)


def _flag_response(flag: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": flag["id"],
        "requirement_id": flag.get("requirement_id"),
        "trigger_source_id": flag.get("trigger_source_id"),
        "trigger_type": flag["trigger_type"],
        "status": flag["status"],
        "actor_user_id": flag.get("actor_user_id"),
        "rationale": flag.get("rationale", ""),
        "created_at": flag["created_at"],
        "updated_at": flag["updated_at"],
    }


@router.get(
    "/regulatory/sources",
    response_model=RegulatorySourceListResponse,
)
def list_sources(
    service: IntakeServiceDependency,
    actor_id: GlobalStaffDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """List all registered regulatory sources (administration view).

    Rows are displayed verbatim — supersession relationships are
    shown as recorded, never inferred.
    """
    items = service.list_sources()
    total = len(items)
    page = items[offset:offset + limit]
    return {
        "items": [_source_response(item) for item in page],
        "limit": limit,
        "offset": offset,
        "total": total,
    }


@router.get(
    "/regulatory/sources/{source_id}/governance-flags",
    response_model=RegulatoryGovernanceFlagListResponse,
)
def list_source_governance_flags(
    source_id: UUID,
    service: GovernanceServiceDependency,
    actor_id: GlobalStaffDependency,
):
    """List governance review flags recorded for a source.

    Shows pending and resolved flags verbatim with their recorded
    rationale. Pending flags read-only here: they cannot be cleared
    or bypassed from the administration view; completion follows
    the governance rules only (independent Stage A / Stage B).
    """
    items = service.get_flags_for_source(source_id)
    return {
        "items": [_flag_response(item) for item in items],
        "total": len(items),
    }


@router.get(
    "/regulatory/requirements/{requirement_id}/governance-flags",
    response_model=RegulatoryGovernanceFlagListResponse,
)
def list_requirement_governance_flags(
    requirement_id: UUID,
    service: GovernanceServiceDependency,
    actor_id: GlobalStaffDependency,
):
    """List governance review flags recorded for a requirement."""
    items = service.get_flags_for_requirement(requirement_id)
    return {
        "items": [_flag_response(item) for item in items],
        "total": len(items),
    }


@router.post(
    "/regulatory/sources/{source_id}/supersession",
    response_model=RegulatorySupersessionResponse,
    status_code=status.HTTP_200_OK,
)
def record_supersession(
    source_id: UUID,
    payload: RegulatorySupersessionRequest,
    service: SupersessionServiceDependency,
    actor_id: GlobalStaffDependency,
):
    """Record that this source supersedes another source.

    Requires an active ``GRANT_MANAGE`` global staff grant. Rejects
    self-supersession, cycles, and duplicate supersession links. Creates
    pending governance flags for all requirements linked to the
    superseded source.
    """
    result = service.record_supersession(
        actor_user_id=actor_id,
        source_id=source_id,
        supersedes_source_id=payload.supersedes_source_id,
        rationale=payload.rationale,
    )
    return {
        "id": result["id"],
        "source_id": result["source_id"],
        "supersedes_source_id": result.get("supersedes_source_id"),
        "superseded_by_source_id": result.get("superseded_by_source_id"),
        "status": result.get("status"),
        "updated_at": result.get("updated_at"),
    }


@router.post(
    "/regulatory/sources/{source_id}/artifacts",
    response_model=RegulatoryArtifactResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_artifact(
    source_id: UUID,
    payload: RegulatoryArtifactUploadRequest,
    service: IntakeServiceDependency,
    actor_id: GlobalStaffDependency,
):
    """Upload an original artifact and establish a durable ingestion job.

    Accepts ``text/plain``, ``text/markdown``, and ``application/json``
    only. ``application/pdf`` is explicitly rejected. Duplicate uploads
    of identical content are idempotent.
    """
    result = service.upload_artifact(
        actor_user_id=actor_id,
        source_id=source_id,
        content_base64=payload.content_base64,
        content_type=payload.content_type,
        source_version=payload.source_version,
    )
    return _artifact_response(result["artifact"])


@router.get(
    "/regulatory/sources/{source_id}/artifacts",
    response_model=RegulatoryArtifactListResponse,
)
def list_artifacts(
    source_id: UUID,
    service: IntakeServiceDependency,
    actor_id: GlobalStaffDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """List artifacts associated with a source."""
    items = service.list_artifacts(source_id)
    total = len(items)
    page = items[offset:offset + limit]
    return {
        "items": [_artifact_response(item) for item in page],
        "limit": limit,
        "offset": offset,
        "total": total,
    }


@router.get(
    "/regulatory/ingestion-jobs/{job_id}",
    response_model=RegulatoryIngestionJobResponse,
)
def get_job(
    job_id: UUID,
    service: IntakeServiceDependency,
    actor_id: GlobalStaffDependency,
):
    """Retrieve an ingestion job's status by ID."""
    row = service.get_job(job_id)
    if row is None:
        raise ApplicationNotFoundError("ingestion job not found")
    return _job_response(row)


@router.get(
    "/regulatory/sources/{source_id}/ingestion-jobs",
    response_model=RegulatoryIngestionJobListResponse,
)
def list_jobs(
    source_id: UUID,
    service: IntakeServiceDependency,
    actor_id: GlobalStaffDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """List ingestion jobs associated with a source."""
    items = service.list_jobs(source_id)
    total = len(items)
    page = items[offset:offset + limit]
    return {
        "items": [_job_response(item) for item in page],
        "limit": limit,
        "offset": offset,
        "total": total,
    }


@router.post(
    "/regulatory/ingestion-jobs/{job_id}/extract",
    response_model=RegulatoryExtractResponse,
    status_code=status.HTTP_200_OK,
)
def extract_candidates(
    job_id: UUID,
    service: ExtractionServiceDependency,
    actor_id: GlobalStaffDependency,
):
    """Extract candidate requirements from an ingested artifact.

    Runs the parsing/normalization/extraction pipeline against the
    artifact linked to the job. Records the extraction outcome
    (succeeded/partial/failed) and persists candidates with provenance.
    Candidates are unreviewed until Stage A verification and Stage B
    approval.
    """
    job = service.get_job(job_id)
    if job is None:
        raise ApplicationNotFoundError("ingestion job not found")
    result = service.extract_candidates(
        actor_user_id=actor_id,
        source_id=job["source_id"],
        artifact_id=job["artifact_id"],
        job_id=job_id,
    )
    return {
        "outcome": result["outcome"],
        "candidate_count": result["candidate_count"],
        "candidates": result.get("candidates", []),
        "job_id": job_id,
        "job_status": result["job"]["status"],
        "duplicate": result.get("duplicate", False),
        "normalization_id": result.get("normalization_id"),
        "error": result.get("error"),
    }


@router.post(
    "/regulatory/candidates",
    response_model=RegulatoryManualCandidateResponse,
    status_code=status.HTTP_201_CREATED,
)
def enter_manual_candidate(
    payload: RegulatoryManualCandidateRequest,
    service: ExtractionServiceDependency,
    actor_id: GlobalStaffDependency,
):
    """Manually enter a candidate requirement (recovery path).

    Requires reviewer attribution. Manual candidates pass the same Stage A
    and Stage B gates as extracted candidates; manual entry cannot make
    failed or partial extraction appear successful.
    """
    row = service.enter_manual_candidate(
        actor_user_id=actor_id,
        source_id=payload.source_id,
        artifact_id=payload.artifact_id,
        requirement_text=payload.requirement_text,
        requirement_type=payload.requirement_type,
        source_location=payload.source_location,
        position=payload.position,
        justification=payload.justification,
    )
    return _candidate_response(row)


@router.get(
    "/regulatory/sources/{source_id}/candidates",
    response_model=RegulatoryCandidateListResponse,
)
def list_candidates(
    source_id: UUID,
    service: ExtractionServiceDependency,
    actor_id: GlobalStaffDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """List candidate requirements for a source.

    Candidates are unreviewed; this endpoint does not imply approval or
    applicability.
    """
    items: list[dict[str, Any]] = []
    seen: set[UUID] = set()
    for artifact in service.list_artifacts_for_source(source_id):
        for candidate in service.list_candidates_for_artifact(artifact["id"]):
            if candidate["id"] not in seen:
                seen.add(candidate["id"])
                items.append(candidate)
    total = len(items)
    page = items[offset:offset + limit]
    return {
        "items": [_candidate_response(item) for item in page],
        "limit": limit,
        "offset": offset,
        "total": total,
    }


@router.get(
    "/regulatory/candidates/{candidate_id}",
    response_model=RegulatoryCandidateResponse,
)
def get_candidate(
    candidate_id: UUID,
    service: ExtractionServiceDependency,
    actor_id: GlobalStaffDependency,
):
    """Retrieve one candidate requirement by ID."""
    row = service.get_candidate(candidate_id)
    if row is None:
        raise ApplicationNotFoundError("candidate requirement not found")
    return _candidate_response(row)


def _stage_a_response(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": candidate["id"],
        "requirement_id": candidate["id"],
        "source_id": candidate.get("source_id"),
        "stage_a_status": candidate["stage_a_status"],
        "stage_a_reviewer_user_id": candidate.get("stage_a_reviewer_user_id"),
        "stage_a_reviewed_at": candidate.get("stage_a_reviewed_at"),
        "stage_a_rationale": candidate.get("stage_a_rationale"),
    }


def _stage_a_history_response(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": review["id"],
        "requirement_id": review["requirement_id"],
        "stage_a_status": review["stage_a_status"],
        "reviewer_user_id": review["reviewer_user_id"],
        "reviewed_at": review["reviewed_at"],
        "rationale": review["rationale"],
        "source_id": review.get("source_id"),
        "created_at": review["created_at"],
    }


@router.post(
    "/regulatory/candidates/{candidate_id}/stage-a",
    response_model=RegulatoryStageAReviewResponse,
    status_code=status.HTTP_200_OK,
)
def stage_a_verify(
    candidate_id: UUID,
    payload: RegulatoryStageAReviewRequest,
    service: StageAServiceDependency,
    actor_id: StageADependency,
):
    """Record a Stage A source/wording verification decision.

    Requires the ``STAGE_A_VERIFY`` global staff grant. Stage A verifies
    source traceability and requirement wording only — it does NOT
    approve pilot applicability (Stage B) or publish requirements.

    Valid decisions: verified, rejected, clarification_required.
    A candidate with failed extraction cannot be marked verified.
    """
    result = service.verify_stage_a(
        actor_user_id=actor_id,
        candidate_id=candidate_id,
        stage_a_status=payload.stage_a_status,
        rationale=payload.rationale,
    )
    return {
        "id": result["id"],
        "requirement_id": result["requirement_id"],
        "source_id": result.get("source_id"),
        "stage_a_status": result["stage_a_status"],
        "stage_a_reviewer_user_id": result.get("stage_a_reviewer_user_id"),
        "stage_a_reviewed_at": result.get("stage_a_reviewed_at"),
        "stage_a_rationale": result.get("stage_a_rationale"),
        "audit_id": result["audit_id"],
        "audit_created_at": result["audit_created_at"],
    }


@router.get(
    "/regulatory/candidates/{candidate_id}/stage-a",
    response_model=RegulatoryStageAReviewResponse,
)
def get_stage_a(
    candidate_id: UUID,
    service: StageAServiceDependency,
    actor_id: StageADependency,
):
    """Retrieve a candidate's current Stage A review state."""
    row = service.get_candidate_stage_a(candidate_id)
    if row is None:
        raise ApplicationNotFoundError("candidate requirement not found")
    return {
        "id": row["id"],
        "requirement_id": row["id"],
        "source_id": row.get("source_id"),
        "stage_a_status": row["stage_a_status"],
        "stage_a_reviewer_user_id": row.get("stage_a_reviewer_user_id"),
        "stage_a_reviewed_at": row.get("stage_a_reviewed_at"),
        "stage_a_rationale": row.get("stage_a_rationale"),
        "audit_id": None,
        "audit_created_at": None,
    }


@router.get(
    "/regulatory/candidates/{candidate_id}/stage-a/history",
    response_model=RegulatoryStageAReviewHistoryListResponse,
)
def list_stage_a_history(
    candidate_id: UUID,
    service: StageAServiceDependency,
    actor_id: StageADependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Return the append-only Stage A review decision history for a candidate.

    Prior decisions are never overwritten; each review is recorded as a
    new row in ``regulatory_stage_a_reviews``.
    """
    items = service.list_stage_a_decisions(candidate_id)
    total = len(items)
    page = items[offset:offset + limit]
    return {
        "items": [_stage_a_history_response(item) for item in page],
        "limit": limit,
        "offset": offset,
        "total": total,
    }


def _stage_b_response(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": candidate["id"],
        "requirement_id": candidate["id"],
        "source_id": candidate.get("source_id"),
        "stage_b_status": candidate["stage_b_status"],
        "stage_b_reviewer_user_id": candidate.get("stage_b_reviewer_user_id"),
        "stage_b_reviewed_at": candidate.get("stage_b_reviewed_at"),
        "stage_b_rationale": candidate.get("stage_b_rationale"),
        "stage_b_pilot_scope": candidate.get("stage_b_pilot_scope"),
    }


def _stage_b_history_response(review: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": review["id"],
        "requirement_id": review["requirement_id"],
        "stage_b_status": review["stage_b_status"],
        "reviewer_user_id": review["reviewer_user_id"],
        "reviewed_at": review["reviewed_at"],
        "rationale": review["rationale"],
        "pilot_scope": review["pilot_scope"],
        "evidence_references": review.get("evidence_references") or [],
        "same_person_exception": review.get("same_person_exception", False),
        "exception_authorizer_user_id": review.get("exception_authorizer_user_id"),
        "exception_authorization_ref": review.get("exception_authorization_ref"),
        "exception_justification": review.get("exception_justification"),
        "created_at": review["created_at"],
    }


@router.post(
    "/regulatory/candidates/{candidate_id}/stage-b",
    response_model=RegulatoryStageBReviewResponse,
    status_code=status.HTTP_200_OK,
)
def stage_b_approve(
    candidate_id: UUID,
    payload: RegulatoryStageBReviewRequest,
    service: StageBServiceDependency,
    actor_id: StageBDependency,
):
    """Record a Stage B pilot-applicability approval decision.

    Requires the ``STAGE_B_APPROVE`` global staff grant. Stage B determines
    applicability to the defined pilot scope only — it does NOT publish
    requirements or mark them exporter-ready.

    Valid decisions: approved, rejected, clarification_required.
    The candidate must have passed Stage A verification.
    Same-person Stage A/Stage B review is not permitted (fail-closed).
    """
    result = service.approve_stage_b(
        actor_user_id=actor_id,
        candidate_id=candidate_id,
        stage_b_status=payload.stage_b_status,
        rationale=payload.rationale,
        pilot_scope=payload.pilot_scope,
        evidence_references=payload.evidence_references,
        same_person_exception=payload.same_person_exception,
        exception_authorizer_user_id=payload.exception_authorizer_user_id,
        exception_authorization_ref=payload.exception_authorization_ref,
        exception_justification=payload.exception_justification,
    )
    return {
        "id": result["id"],
        "requirement_id": result["requirement_id"],
        "source_id": result.get("source_id"),
        "stage_b_status": result["stage_b_status"],
        "stage_b_reviewer_user_id": result.get("stage_b_reviewer_user_id"),
        "stage_b_reviewed_at": result.get("stage_b_reviewed_at"),
        "stage_b_rationale": result.get("stage_b_rationale"),
        "stage_b_pilot_scope": result.get("stage_b_pilot_scope"),
        "audit_id": result["audit_id"],
        "audit_created_at": result["audit_created_at"],
    }


@router.get(
    "/regulatory/candidates/{candidate_id}/stage-b",
    response_model=RegulatoryStageBReviewResponse,
)
def get_stage_b(
    candidate_id: UUID,
    service: StageBServiceDependency,
    actor_id: StageBDependency,
):
    """Retrieve a candidate's current Stage B review state."""
    row = service.get_candidate_stage_b(candidate_id)
    if row is None:
        raise ApplicationNotFoundError("candidate requirement not found")
    return {
        "id": row["id"],
        "requirement_id": row["id"],
        "source_id": row.get("source_id"),
        "stage_b_status": row["stage_b_status"],
        "stage_b_reviewer_user_id": row.get("stage_b_reviewer_user_id"),
        "stage_b_reviewed_at": row.get("stage_b_reviewed_at"),
        "stage_b_rationale": row.get("stage_b_rationale"),
        "stage_b_pilot_scope": row.get("stage_b_pilot_scope"),
    }


@router.get(
    "/regulatory/candidates/{candidate_id}/stage-b/history",
    response_model=RegulatoryStageBReviewHistoryListResponse,
)
def list_stage_b_history(
    candidate_id: UUID,
    service: StageBServiceDependency,
    actor_id: StageBDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Return the append-only Stage B review decision history for a candidate.

    Prior decisions are never overwritten; each review is recorded as a
    new row in ``regulatory_stage_b_reviews``.
    """
    items = service.list_stage_b_decisions(candidate_id)
    total = len(items)
    page = items[offset:offset + limit]
    return {
        "items": [_stage_b_history_response(item) for item in page],
        "limit": limit,
        "offset": offset,
        "total": total,
    }


def _eligibility_service(services: Any = Depends(get_services)) -> RegulatoryPublicationEligibilityService:
    database = getattr(services, "database", None)
    if database is None:
        raise APIError(
            503, "application_not_ready",
            "Application services are not initialized",
        )
    return RegulatoryPublicationEligibilityService(database)


EligibilityServiceDependency = Annotated[
    RegulatoryPublicationEligibilityService, Depends(_eligibility_service)
]


@router.get(
    "/regulatory/eligible-requirements",
    response_model=RegulatoryEligibleRequirementsResponse,
)
def list_eligible_requirements(
    service: EligibilityServiceDependency,
    actor_id: GlobalStaffDependency,
    source_filter: Annotated[UUID | None, Query()] = None,
    pilot_scope_filter: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Return regulatory requirements eligible for exporter-facing publication.

    Eligibility requires Stage A verification (``verified``), Stage B
    approval (``approved``), current active source (no supersession,
    withdrawal, or staleness), no pending governance flags, and
    successful extraction outcome (``succeeded``). Partial, failed,
    manual-only, or unverified requirements are excluded. Provenance
    and citation references are preserved only for eligible items.
    Caller-supplied approval claims are never accepted.
    """
    eligible = service.get_eligible_requirements(
        tenant=None,
        source_filter=source_filter,
        pilot_scope_filter=pilot_scope_filter,
    )
    total = len(eligible)
    page_items = eligible[offset:offset + limit]
    return {
        "items": [
            RegulatoryEligibleRequirementResponse(
                id=item.get("id"),
                requirement_text=item.get("requirement_text", ""),
                requirement_type=item.get("requirement_type", "unknown"),
                stage_a_status=item.get("stage_a_status", "pending"),
                stage_b_status=item.get("stage_b_status", "pending"),
                stage_b_pilot_scope=item.get("stage_b_pilot_scope"),
                citation_reference={
                    "normalized_document_id": item.get("normalized_document_id"),
                    "source_location": item.get("source_location"),
                    "position": item.get("position"),
                    "parser_version": item.get("parser_version"),
                    "ingestion_job_id": item.get("ingestion_job_id"),
                },
                source_reference={
                    "source_id": item.get("source_id"),
                    "source_version": item.get("document_version"),
                    "status": item.get("status"),
                },
                source_location=item.get("source_location"),
            ) for item in page_items
        ],
        "limit": limit,
        "offset": offset,
        "total": total,
    }
