"""HTTP request and response schemas for the API boundary."""

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from xportra.domain.evidence_retrieval import DEFAULT_TOP_K

RAG_RETRIEVAL_MODES = ("semantic", "lexical", "hybrid")
RAGRetrievalMode = Literal["semantic", "lexical", "hybrid"]

#: API-layer guard on information-need length. The domain validates
#: presence/normalization only; this bound keeps a single request from
#: carrying unbounded text into retrieval/prompt/LLM stages. It is an
#: API choice, not a domain rule.
MAX_INFORMATION_NEED_CHARACTERS = 4000

#: API-layer default context budget (content characters). The domain
#: owns budget semantics (``EvidenceContextBudget``); this default
#: only applies when the caller supplies no explicit budget.
DEFAULT_RAG_CONTEXT_CHARACTERS = 4000


class APIRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExporterCreateRequest(APIRequest):
    legal_name: str = Field(min_length=1)
    trading_name: str | None = None
    registration_number: str | None = None
    country_of_registration: str | None = None
    status: str = "active"


class ExporterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    legal_name: str
    trading_name: str | None
    registration_number: str | None
    country_of_registration: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ProductCreateRequest(APIRequest):
    exporter_id: UUID
    product_name: str = Field(min_length=1)
    commodity_code: str | None = None
    description: str | None = None
    status: str | None = "active"


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    exporter_id: UUID
    product_name: str
    commodity_code: str | None
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class DestinationMarketCreateRequest(APIRequest):
    country_code: str = Field(min_length=1)
    market_name: str = Field(min_length=1)
    regulatory_context: str | None = None
    status: str | None = "active"


class DestinationMarketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    country_code: str
    market_name: str
    regulatory_context: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ComplianceEvidenceCreateRequest(APIRequest):
    document_title: str = Field(min_length=1)
    document_type: str = Field(min_length=1)
    file_reference_or_uri: str = Field(min_length=1)
    source_id: UUID | None = None
    content_hash: str | None = None
    status: str = "uploaded"


class ComplianceEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    source_id: UUID | None
    document_title: str
    document_type: str
    file_reference_or_uri: str
    content_hash: str | None
    status: str
    uploaded_at: datetime
    created_at: datetime
    updated_at: datetime
    #: Phase 10.4 processing lifecycle (migration 011).
    #: Optional so pre-migration rows and test doubles
    #: without the columns still serialize.
    processing_status: str | None = None
    processing_step: str | None = None
    processing_error: str | None = None
    processed_at: datetime | None = None
    original_filename: str | None = None
    mime_type: str | None = None


class ComplianceEvidenceWithRequirementsRequest(ComplianceEvidenceCreateRequest):
    requirement_ids: list[UUID] = Field(min_length=1)


class EvidenceRequirementAssociationRequest(APIRequest):
    requirement_id: UUID


class EvidenceRequirementAssociationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    evidence_id: UUID
    requirement_id: UUID
    created_at: datetime


class CertificationCreateRequest(APIRequest):
    exporter_id: UUID
    issuing_authority_id: UUID
    title: str = Field(min_length=1)
    issue_date: date | None = None
    expiry_date: date | None = None
    status: str = "issued"
    document_reference: str | None = None


class CertificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    exporter_id: UUID
    issuing_authority_id: UUID
    title: str
    issue_date: date | None
    expiry_date: date | None
    status: str
    document_reference: str | None
    created_at: datetime
    updated_at: datetime


class RAGQueryScopeRequest(APIRequest):
    """Optional conjunctive scope over the canonical indexed dimensions.

    Mirrors ``EvidenceRetrievalScope`` exactly: only the four
    established dimensions may be expressed. Tenant scoping is never
    part of the body — it comes from the authenticated context.
    """

    source_id: str | None = None
    source_type: str | None = None
    document_id: UUID | None = None
    document_version: str | None = None


class RAGQueryRequest(APIRequest):
    """Single coherent RAG query operation.

    Only the user's information need is required. The optional
    controls mirror already-validated domain values (retrieval mode,
    context budget, top-k, candidate pool, canonical scope). No
    tenant identity, no provider settings, no raw prompts, no
    embedding configuration, and no vector-store internals may be
    supplied — ``extra="forbid"`` (via ``APIRequest``) rejects them.
    """

    information_need: str = Field(
        min_length=1, max_length=MAX_INFORMATION_NEED_CHARACTERS
    )
    mode: RAGRetrievalMode = "hybrid"
    max_context_characters: StrictInt = Field(
        default=DEFAULT_RAG_CONTEXT_CHARACTERS, gt=0
    )
    top_k: StrictInt = Field(default=DEFAULT_TOP_K, gt=0)
    candidate_pool: StrictInt | None = Field(default=None, gt=0)
    scope: RAGQueryScopeRequest | None = None


class RAGCitationEvidenceResponse(BaseModel):
    """Authoritative provenance for one cited evidence item.

    Tenant identity, raw content, embedding contract, and scores are
    deliberately omitted: the client receives identifiers and source
    pointers sufficient to trace the evidence, never infrastructure
    internals.
    """

    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    source_id: str
    source_type: str
    source_location: str | None
    document_version: str | None
    content_fingerprint: str


class RAGCitationResponse(BaseModel):
    """One validated citation: prompt-local label plus its evidence."""

    label: str
    rank_position: int
    evidence: RAGCitationEvidenceResponse


class RAGQueryResponse(BaseModel):
    """Structured answer boundary.

    ``status`` preserves the Phase 5.11/5.12 distinction: ``valid``
    (validated answer), ``invalid_citations`` (structured non-raising
    validator path), ``empty`` (model produced no substantive output
    — distinct from provider failure and validation failure).
    Operational failures never surface here; they map to error
    responses instead.
    """

    answer_text: str
    status: str
    is_empty: bool
    extracted_references: list[str]
    invalid_references: list[str]
    citations: list[RAGCitationResponse]


#: Phase 8.2 compliance-workflow schemas. Request bodies carry
#: workflow records (the wire-stable surface — no workflow
#: store exists) plus operation primitives only. Tenant
#: identity is never part of any body; it comes from the
#: authenticated member context. Responses mirror the
#: application DTO contracts without exposing domain objects.


class WorkflowRoundSchema(BaseModel):
    """One recorded analysis round (references only)."""

    round_index: int
    report_id: UUID
    analysis_ids: list[UUID]
    trace_ids: list[UUID]
    input_fingerprints: list[str]


class WorkflowRoundResponse(BaseModel):
    """One recorded round for clients (no implementation fingerprints)."""

    round_index: int
    report_id: UUID
    analysis_ids: list[UUID]
    trace_ids: list[UUID]


class WorkflowRecordSchema(APIRequest):
    """Client-held workflow state passed per request.

    The server holds no workflow session: callers send the
    record returned by the previous call and receive the
    updated record back. Records are validated structurally
    here; all ownership and transition rules stay in the
    application/domain boundary.
    """

    id: UUID
    tenant_id: UUID
    case_id: UUID
    shipment_id: UUID | None = None
    state: str
    rounds: list[WorkflowRoundSchema] = Field(default_factory=list)
    supplied_evidence_ids: list[UUID] = Field(default_factory=list)
    open_requirements: list[UUID] = Field(default_factory=list)


class ShipmentProfileSchema(APIRequest):
    """Commercial shipment facts collected at intake (ADR-0013 v1).

    Transport for the already-collected New Shipment
    profile: required facts must be non-blank, optional
    facts accept null or blank (stored as absent). No
    workflow state, evidence, or compliance content
    travels here.
    """

    product: str
    origin_country: str
    destination_country: str
    quantity: str | None = None
    unit: str | None = None
    shipment_date: str | None = None


class StartWorkflowRequest(APIRequest):
    case_id: UUID
    shipment_id: UUID | None = None
    shipment: ShipmentProfileSchema | None = None


class WorkflowActionRequest(APIRequest):
    workflow: WorkflowRecordSchema


class SupplyEvidenceRequest(APIRequest):
    workflow: WorkflowRecordSchema
    evidence_id: UUID
    requirement_id: UUID | None = None

class RequestEvidenceRequest(APIRequest):
    workflow: WorkflowRecordSchema
    requirement_ids: list[UUID] = Field(min_length=1)


class AnalyzeWorkflowRequest(APIRequest):
    """Run (or re-run) analysis; the state machine routes passes."""

    workflow: WorkflowRecordSchema
    cases: list[dict] = Field(min_length=1)
    mode: RAGRetrievalMode = "hybrid"
    max_context_characters: StrictInt = Field(
        default=DEFAULT_RAG_CONTEXT_CHARACTERS, gt=0
    )
    top_k: StrictInt | None = Field(default=None, gt=0)
    candidate_pool: StrictInt | None = Field(default=None, gt=0)
    decision_summary: dict | None = None


class ApplicabilityRequest(APIRequest):
    """Determine applicability over caller-supplied records."""

    requirements: list[dict] = Field(min_length=1)
    exporter: dict | None = None
    product: dict | None = None
    destination: dict | None = None
    actor_role: str | None = None
    business_characteristics: dict | None = None
    shipment_id: UUID | None = None


class CaseReadinessRequest(APIRequest):
    cases: list[dict] = Field(min_length=1)


class WorkflowSummaryResponse(BaseModel):
    """Workflow progression state for clients."""

    workflow_id: UUID
    tenant_id: UUID
    case_id: UUID
    shipment_id: UUID | None = None
    state: str
    is_closed: bool
    round_count: int
    rounds: list[WorkflowRoundResponse]
    supplied_evidence_ids: list[UUID]
    open_requirements: list[UUID]


class WorkflowActionResponse(BaseModel):
    workflow: WorkflowRecordSchema
    summary: WorkflowSummaryResponse


class ShipmentWorkflowSummarySchema(BaseModel):
    """Workflow progress behind one listed shipment (counts only)."""

    workflow_id: UUID
    state: str
    is_closed: bool
    supplied_evidence_count: int
    open_requirements_count: int
    round_count: int
    latest_report_id: UUID | None = None


class ShipmentItemSchema(BaseModel):
    """One shipment with its workflow summary for discovery."""

    shipment_id: UUID
    case_id: UUID
    product: str
    origin_country: str
    destination_country: str
    quantity: str | None = None
    unit: str | None = None
    shipment_date: str | None = None
    status: str
    created_at: str
    updated_at: str
    workflow: ShipmentWorkflowSummarySchema | None = None
    workflow_count: int
    workflow_record: WorkflowRecordSchema | None = None


class ShipmentListResponse(BaseModel):
    """One page of tenant shipment discovery."""

    shipments: list[ShipmentItemSchema]
    limit: int
    offset: int
    total: int


class RequirementFindingResponse(BaseModel):
    analysis_id: UUID
    requirement_id: UUID
    requirement_text: str
    applicability: str
    assessment: str
    explanation: str
    uncertainty: str
    uncertainty_explanation: str
    evidence_sufficiency: str
    sufficiency_explanation: str
    contradiction_state: str
    missing_information: list[str]
    supporting_evidence: list[dict]
    conflicting_evidence: list[dict]
    knowledge_references: list[dict]
    sources: list[dict]
    missing_items: list[dict]


class AnalysisReportResponse(BaseModel):
    report_id: UUID
    case_id: UUID
    counts: dict[str, int]
    requirements_with_missing_information: list[UUID]
    uncertain_requirement_ids: list[UUID]
    requirements_with_conflicting_evidence: list[UUID]
    conflicting_evidence_count: int
    findings: list[RequirementFindingResponse]


class AnalyzeWorkflowResponse(BaseModel):
    workflow: WorkflowRecordSchema
    report: AnalysisReportResponse


class FinalPackageResponse(BaseModel):
    """Stored final assessment package (terminal, by reference)."""

    workflow_id: UUID
    tenant_id: UUID
    case_id: UUID
    shipment_id: UUID | None = None
    state: str
    round_count: int
    open_requirements: list[UUID]
    report: AnalysisReportResponse
    decision_summary: dict | None = None


class FinalizeWorkflowResponse(BaseModel):
    workflow: WorkflowRecordSchema
    package: FinalPackageResponse


class HistoryEntryResponse(BaseModel):
    sequence: int
    kind: str
    detail: str
    references: list[dict[str, str]]


class HistoryResponse(BaseModel):
    workflow_id: UUID
    tenant_id: UUID
    case_id: UUID
    shipment_id: UUID | None = None
    state: str
    entries: list[HistoryEntryResponse]
    round_count: int
    latest_report_id: UUID | None = None
    decision_summary_present: bool
    readiness: dict | None = None
    final_package: dict | None = None


class ClosureResponse(BaseModel):
    workflow_id: UUID
    is_closed: bool


class ApplicabilityResultResponse(BaseModel):
    requirement_id: UUID
    outcome: str
    reason: str


class ApplicabilityResponse(BaseModel):
    counts: dict[str, int]
    results: list[ApplicabilityResultResponse]


class ReadinessGapResponse(BaseModel):
    requirement_id: UUID
    kind: str
    reason: str


class CaseReadinessResponse(BaseModel):
    readiness_state: str
    required_information: int
    known_information: int
    missing_information_count: int
    gaps: list[ReadinessGapResponse]
    missing_evidence_requirements: list[UUID]
    unknown_applicability_requirements: list[UUID]
    unknown_assessment_requirements: list[UUID]


#: Phase 10.2 conversational schemas. The request carries one
#: allow-listed read-only intent plus the minimal context that
#: intent needs; the workflow record travels in the body
#: because no conversation/workflow store exists (the Phase 8.2
#: precedent — the server revalidates per request and holds no
#: session). Tenant identity is never part of any body; it
#: comes from the authenticated member context. Client-supplied
#: ``conversation_id`` is a correlation identifier only: it is
#: validated for shape, echoed in the response, and never
#: dereferenced. ``extra="forbid"`` (via ``APIRequest``)
#: rejects tenant IDs, prompts, provider settings, and raw
#: content fields.

ConversationMode = Literal["shipment_aware", "knowledge"]

ConversationIntent = Literal[
    "explain_requirement_state",
    "explain_evidence_gaps",
    "explain_finding",
    "summarize_shipment_state",
    "answer_regulatory_question",
]

#: API-layer bound on conversation user text. The domain owns
#: the contract bound (``MAX_USER_MESSAGE_CHARACTERS``); this
#: mirrors it so oversized bodies fail fast with 422.
MAX_CONVERSATION_MESSAGE_CHARACTERS = 2000


class ConversationMessageRequest(APIRequest):
    """One stateless, read-only conversation turn."""

    conversation_id: UUID
    mode: ConversationMode
    intent: ConversationIntent
    user_text: str = Field(
        min_length=1, max_length=MAX_CONVERSATION_MESSAGE_CHARACTERS
    )
    workflow: dict | None = None
    requirement_id: UUID | None = None
    evidence_id: UUID | None = None
    information_need: str | None = Field(default=None, min_length=1)
    retrieval_mode: RAGRetrievalMode = "hybrid"
    max_context_characters: StrictInt = Field(
        default=DEFAULT_RAG_CONTEXT_CHARACTERS, gt=0
    )
    top_k: StrictInt | None = Field(default=None, gt=0)


class ConversationShipmentCitationResponse(BaseModel):
    """Identifier citation for one shipment/compliance claim."""

    kind: str
    id: UUID


class ConversationMessageResponse(BaseModel):
    """Grounded assistant turn: quoted state or cited knowledge."""

    conversation_id: UUID
    mode: str
    intent: str
    status: str
    summary_text: str
    shipment_references: list[ConversationShipmentCitationResponse]
    citations: list[RAGCitationResponse]
    refusal_reason: str | None = None


#: Phase 10.4 evidence file-upload schemas. The transport
#: carries base64-encoded bytes (no multipart dependency):
#: the domain boundary validates the decoded bytes
#: (10 MB cap, MVP types, magic bytes) and never trusts
#: the declared content type or filename alone. Tenant
#: identity is never part of any body; it comes from the
#: authenticated member context. ``extra="forbid"`` (via
#: ``APIRequest``) rejects tenant IDs, object keys, and
#: storage internals.

#: Transport bound on the base64 payload. The domain owns
#: the exact 10 MB byte cap; this bound only rejects
#: absurd bodies before decoding (~15 MB decoded).
MAX_UPLOAD_BASE64_CHARACTERS = 20_000_000


class EvidenceUploadRequest(APIRequest):
    """One evidence file upload (JSON transport, base64 bytes)."""

    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=255)
    content_base64: str = Field(
        min_length=1, max_length=MAX_UPLOAD_BASE64_CHARACTERS
    )
    document_title: str | None = Field(default=None, min_length=1)
    document_type: str | None = Field(default=None, min_length=1)
    requirement_ids: list[UUID] = Field(default_factory=list)
    workflow: WorkflowRecordSchema | None = None


class EvidenceUploadResponse(BaseModel):
    """Uploaded evidence: identifiers + lifecycle state.

    Never carries file bytes, document text, storage
    keys, or signed URLs.
    """

    evidence_id: UUID
    tenant_id: UUID
    document_title: str | None = None
    document_type: str | None = None
    status: str | None = None
    processing_status: str | None = None
    processing_step: str | None = None
    processing_error: str | None = None
    content_hash: str | None = None
    original_filename: str | None = None
    mime_type: str | None = None
    duplicate: bool = False
    linked_requirement_ids: list[UUID] = Field(default_factory=list)


class EvidenceDownloadResponse(BaseModel):
    """Authorized download grant: one short-lived signed URL."""

    evidence_id: UUID
    tenant_id: UUID
    download_url: str
    expires_in_seconds: int


#: Organization self-service registration schemas (Phase 10.11).
#:
#: The request carries only organization/user *profile* input. It
#: deliberately has no tenant id, user id, Supabase subject, role,
#: or membership-status field, and ``extra="forbid"`` (via
#: ``APIRequest``) rejects any attempt to smuggle one: identity,
#: tenant, and the initial administrator role are derived entirely
#: server-side from the verified authentication context. The
#: response returns identifiers plus the initial role only — never
#: tokens, secrets, or storage/infrastructure details.
OrganizationType = Literal[
    "farmer", "cooperative", "exporter", "service_provider", "other"
]


class OrganizationRegistrationRequest(APIRequest):
    organization_name: str = Field(min_length=1, max_length=200)
    organization_type: OrganizationType
    country_code: str = Field(min_length=2, max_length=2)
    region: str | None = Field(default=None, max_length=120)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=320)


class OrganizationRegistrationResponse(BaseModel):
    organization_id: UUID
    organization_slug: str
    organization_name: str
    user_id: UUID
    role: str
    membership_status: str


#: Current-account identity returned by ``GET /me`` for the authenticated
#: shell. Only the fields the UI needs to display who is signed in and
#: which organization they are working under.
class IdentityResponse(BaseModel):
    user_id: UUID
    display_name: str
    email: str | None = None
    organization_id: UUID | None = None
    organization_name: str | None = None
    role: str | None = None
    #: Active global staff permission names held by the caller, resolved
    #: server-side from the grant store. Empty by default so the response
    #: fails closed: the frontend may surface staff navigation only when
    #: a recognized permission is present here. Tenant roles never imply
    #: global staff permissions.
    staff_permissions: list[str] = []


#: Regulatory source intake schemas (Phase 4D.10 Task 3).
#: Requests carry only metadata and base64-encoded artifact bytes;
#: global-staff identity comes from the authenticated context.
#: Responses carry identifiers and lifecycle state only — never
#: storage keys, file bytes, or infrastructure internals.

MAX_ARTIFACT_BASE64_CHARACTERS = 20_000_000

ACCEPTED_ARTIFACT_CONTENT_TYPES = frozenset({
    "text/plain", "text/markdown", "application/json",
})

VALID_SOURCE_STATUSES = frozenset({
    "draft", "active", "superseded", "withdrawn", "archived",
})


class RegulatorySourceCreateRequest(APIRequest):
    """Register a regulatory source. source_url is metadata only."""

    authority_id: UUID
    jurisdiction: str = Field(min_length=1)
    title: str = Field(min_length=1)
    version: str | None = Field(default=None, max_length=100)
    status: str = Field(default="draft")
    effective_date: date | None = None
    publication_date: date | None = None
    source_url: str | None = Field(default=None, max_length=2048)


class RegulatorySourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    authority_id: UUID
    jurisdiction: str
    title: str
    version: str | None
    status: str
    effective_date: date | None
    publication_date: date | None
    source_url: str | None
    retrieval_timestamp: datetime | None
    supersedes_source_id: UUID | None
    superseded_by_source_id: UUID | None
    created_at: datetime
    updated_at: datetime


class RegulatorySupersessionRequest(APIRequest):
    """Record that this source supersedes another source.

    ``supersedes_source_id`` identifies the source being superseded.
    ``rationale`` documents why the supersession is being recorded.
    """

    supersedes_source_id: UUID
    rationale: str = Field(min_length=1)


class RegulatorySupersessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    supersedes_source_id: UUID | None
    superseded_by_source_id: UUID | None
    status: str
    updated_at: datetime


class RegulatoryArtifactUploadRequest(APIRequest):
    """Upload an original regulatory artifact (JSON transport, base64 bytes)."""

    content_base64: str = Field(
        min_length=1, max_length=MAX_ARTIFACT_BASE64_CHARACTERS
    )
    content_type: str = Field(min_length=1, max_length=255)
    source_version: str | None = Field(default=None, max_length=100)


class RegulatoryTextEntryRequest(APIRequest):
    """Enter staff-typed text as a regulatory artifact (no file upload).

    The text is carried directly in the request body and stored in the
    private regulatory source-artifact storage alongside uploaded files.
    Only text media types are accepted.
    """

    content_text: str = Field(min_length=1)
    content_type: str = Field(min_length=1, max_length=255)
    source_version: str | None = Field(default=None, max_length=100)


class RegulatoryArtifactTextResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    content_hash: str
    content_length: int
    content_type: str
    acquisition_channel: str
    acquired_at: datetime
    status: str
    source_version: str | None
    created_at: datetime
    updated_at: datetime


class RegulatoryArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    content_hash: str
    content_length: int
    content_type: str
    acquisition_channel: str
    acquired_at: datetime
    status: str
    source_version: str | None
    created_at: datetime
    updated_at: datetime


class RegulatoryIngestionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    artifact_id: UUID
    source_id: UUID
    status: str
    attempt_number: int
    started_at: datetime | None
    completed_at: datetime | None
    error_details: str | None
    parser_version: str
    actor_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class RegulatoryArtifactListResponse(BaseModel):
    items: list[RegulatoryArtifactResponse]
    limit: int
    offset: int
    total: int


class RegulatoryIngestionJobListResponse(BaseModel):
    items: list[RegulatoryIngestionJobResponse]
    limit: int
    offset: int
    total: int


class RegulatorySourceListResponse(BaseModel):
    items: list[RegulatorySourceResponse]
    limit: int
    offset: int
    total: int


class RegulatoryGovernanceFlagResponse(BaseModel):
    """One governance review flag, displayed verbatim.

    Pending flags are surfaced with their recorded rationale;
    completion and dismissal remain governed exclusively by the
    backend governance rules — never from this view.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    requirement_id: UUID | None
    trigger_source_id: UUID | None
    trigger_type: str
    status: str
    actor_user_id: UUID | None
    rationale: str
    created_at: datetime
    updated_at: datetime


class RegulatoryGovernanceFlagListResponse(BaseModel):
    items: list[RegulatoryGovernanceFlagResponse]
    total: int


#: Regulatory candidate extraction schemas (Phase 4D.10 Task 4).
#: Candidates are unreviewed until Stage A verification and Stage B
#: applicability approval. Extraction records outcome and provenance
#; it does not publish or approve requirements.

EXTRACTION_OUTCOMES = frozenset({"succeeded", "partial", "failed", "manual"})


class RegulatoryExtractRequest(APIRequest):
    """Trigger candidate extraction for an ingestion job."""

    job_id: UUID


class RegulatoryExtractResponse(BaseModel):
    """Extraction result: outcome, candidate count, and job status.

    Never presents candidates as approved or applicable requirements.
    """

    outcome: str
    candidate_count: int
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    job_id: UUID
    job_status: str
    duplicate: bool = False
    normalization_id: UUID | None = None
    error: str | None = None


class RegulatoryManualCandidateRequest(APIRequest):
    """Manually enter a candidate requirement (recovery path).

    Requires reviewer attribution. Manual candidates pass the same Stage A
    and Stage B gates as extracted candidates; manual entry cannot make
    failed or partial extraction appear successful.
    """

    artifact_id: UUID
    requirement_text: str = Field(min_length=1)
    requirement_type: str = Field(default="unknown")
    source_location: dict[str, Any] | None = Field(default_factory=dict)
    position: int = Field(default=0, ge=0)
    justification: str | None = Field(default=None, max_length=2000)


class RegulatoryManualCandidateResponse(BaseModel):
    """Manually entered candidate requirement with reviewer attribution."""

    id: UUID
    source_id: UUID
    artifact_id: UUID
    requirement_text: str
    requirement_type: str
    source_location: dict[str, Any]
    position: int
    status: str
    extraction_outcome: str
    manual_entry: bool
    reviewer_user_id: UUID | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RegulatoryCandidateResponse(BaseModel):
    """One candidate requirement (unreviewed, not approved).

    Provenance fields (source, artifact, ingestion job) are populated
    by the detail endpoint to enable traceability from candidate text
    back to the source artifact and extraction run. The list endpoint
    omits these fields for brevity.
    """

    id: UUID
    source_id: UUID
    artifact_id: UUID
    normalized_document_id: UUID | None
    requirement_text: str
    requirement_type: str
    source_location: dict[str, Any]
    position: int
    actor: str | None
    status: str
    extraction_outcome: str
    parser_version: str | None
    manual_entry: bool
    reviewer_user_id: UUID | None
    reviewed_at: datetime | None
    ingestion_job_id: UUID | None
    created_at: datetime
    updated_at: datetime
    #: Source metadata for review traceability.
    source_title: str | None = None
    source_jurisdiction: str | None = None
    source_version: str | None = None
    source_status: str | None = None
    source_authority_id: UUID | None = None
    #: Artifact metadata for review traceability.
    artifact_uri: str | None = None
    artifact_content_hash: str | None = None
    artifact_content_length: int | None = None
    artifact_content_type: str | None = None
    artifact_acquisition_channel: str | None = None
    #: Ingestion job status for review traceability.
    ingestion_job_status: str | None = None
    ingestion_job_error_details: str | None = None
    ingestion_job_parser_version: str | None = None


class RegulatoryCandidateEligibilityResponse(BaseModel):
    """Publication eligibility for a single candidate, with structured reasons.

    Eligibility requires Stage A verification, Stage B approval, current
    active source, no pending governance flags, successful extraction, and
    complete provenance. Reasons explain why a candidate is not eligible;
    an empty reasons list means eligible. This endpoint evaluates only —
    it does not publish the candidate.
    """

    candidate_id: UUID
    eligible: bool
    reasons: list[str] = Field(default_factory=list)
    evaluated_at: datetime


class RegulatoryEligibleRequirementResponse(BaseModel):
    """An eligible regulatory requirement ready for exporter-facing publication.

    Only requirements passing Stage A verification, Stage B approval,
    current source, no pending governance flags, and successful
    extraction are included. Provenance references are preserved
    but raw content and internal scores are never exposed.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    requirement_text: str
    requirement_type: str
    stage_a_status: str
    stage_b_status: str
    stage_b_pilot_scope: str | None
    citation_reference: dict[str, Any]
    source_reference: dict[str, Any]
    source_location: dict[str, Any] | None = None


class RegulatoryEligibleRequirementsResponse(BaseModel):
    items: list[RegulatoryEligibleRequirementResponse]
    limit: int
    offset: int
    total: int


class RegulatoryCandidateListResponse(BaseModel):
    items: list[RegulatoryCandidateResponse]
    limit: int
    offset: int
    total: int


#: Regulatory Stage A review schemas (Phase 4D.10 Task 5).
#: Stage A verifies source traceability and requirement wording only.
#: It does NOT approve pilot applicability (Stage B) or publish
#: requirements for exporter-facing use.

STAGE_A_STATUSES = frozenset({"verified", "rejected", "clarification_required"})


class RegulatoryStageAReviewRequest(APIRequest):
    """Submit a Stage A review decision for a candidate requirement.

    Requires the ``STAGE_A_VERIFY`` global staff permission.
    ``stage_a_status`` must be one of: verified, rejected,
    clarification_required. Rationale is mandatory.
    """

    stage_a_status: str
    rationale: str = Field(min_length=1)


class RegulatoryStageAReviewResponse(BaseModel):
    """Stage A review decision: current state plus audit reference.

    Never presents the candidate as approved or applicable — Stage A
    verification is distinct from Stage B applicability approval.
    """

    id: UUID
    requirement_id: UUID
    stage_a_status: str
    stage_a_reviewer_user_id: UUID | None
    stage_a_reviewed_at: datetime | None
    stage_a_rationale: str | None
    audit_id: UUID
    audit_created_at: datetime


class RegulatoryStageAReviewHistoryResponse(BaseModel):
    """One append-only Stage A review decision from the audit history."""

    id: UUID
    requirement_id: UUID
    stage_a_status: str
    reviewer_user_id: UUID
    reviewed_at: datetime
    rationale: str
    source_id: UUID | None
    created_at: datetime


class RegulatoryStageAReviewHistoryListResponse(BaseModel):
    items: list[RegulatoryStageAReviewHistoryResponse]
    limit: int
    offset: int
    total: int


#: Regulatory Stage B review schemas (Phase 4D.10 Task 6).
#: Stage B determines pilot-applicability approval only.
#: It does NOT publish requirements or mark them exporter-ready.

STAGE_B_STATUSES = frozenset({"approved", "rejected", "clarification_required"})


class RegulatoryStageBReviewRequest(APIRequest):
    """Submit a Stage B pilot-applicability approval decision.

    Requires the ``STAGE_B_APPROVE`` global staff permission.
    The candidate must have passed Stage A verification.
    ``stage_b_status`` must be one of: approved, rejected,
    clarification_required. Rationale and pilot scope are mandatory.
    Same-person Stage A/Stage B review is not permitted (fail-closed).
    """

    stage_b_status: str
    rationale: str = Field(min_length=1)
    pilot_scope: str = Field(min_length=1)
    evidence_references: list[dict[str, Any]] | None = Field(default_factory=list)
    same_person_exception: bool = Field(default=False)
    exception_authorizer_user_id: UUID | None = None
    exception_authorization_ref: str | None = None
    exception_justification: str | None = None


class RegulatoryStageBReviewResponse(BaseModel):
    """Stage B pilot-applicability approval decision: current state plus
    audit reference.

    Never presents the candidate as published or exporter-ready — Stage B
    approval is distinct from publication and exporter-facing assessment.
    """

    id: UUID
    requirement_id: UUID
    stage_b_status: str
    stage_b_reviewer_user_id: UUID | None
    stage_b_reviewed_at: datetime | None
    stage_b_rationale: str | None
    stage_b_pilot_scope: str | None
    audit_id: UUID
    audit_created_at: datetime


class RegulatoryStageBReviewHistoryResponse(BaseModel):
    """One append-only Stage B review decision from the audit history."""

    id: UUID
    requirement_id: UUID
    stage_b_status: str
    reviewer_user_id: UUID
    reviewed_at: datetime
    rationale: str
    pilot_scope: str
    evidence_references: list[dict[str, Any]]
    same_person_exception: bool
    exception_authorizer_user_id: UUID | None
    exception_authorization_ref: str | None
    exception_justification: str | None
    created_at: datetime


class RegulatoryStageBReviewHistoryListResponse(BaseModel):
    items: list[RegulatoryStageBReviewHistoryResponse]
    limit: int
    offset: int
    total: int


#: Regulatory catalog schemas (exporter-facing, Phase 4D.10 Task 7).
#: The catalog exposes only published requirements that have been
#: evaluated as applicable to the requesting organization's scope.


class CatalogSourceReference(BaseModel):
    """Source metadata visible in the catalog (read-only, no internals)."""

    source_id: UUID | None
    source_title: str | None
    source_jurisdiction: str | None
    source_version: str | None
    source_status: str | None


class CatalogCitationReference(BaseModel):
    """Citation metadata for traceability to the source document."""

    normalized_document_id: UUID | None
    source_location: dict[str, Any] | None
    position: int | None
    parser_version: str | None


class CatalogApplicability(BaseModel):
    """Applicability determination for the requested scope."""

    outcome: str
    reason: str | None
    context_fingerprint: str | None


class CatalogRequirementItem(BaseModel):
    """One published, applicable requirement visible in the exporter catalog."""

    requirement_id: UUID
    requirement_text: str
    requirement_type: str
    stage_a_status: str
    stage_b_status: str
    stage_b_pilot_scope: str | None
    published_at: datetime | None
    source: CatalogSourceReference
    citation: CatalogCitationReference
    applicability: CatalogApplicability


class CatalogRequirementsResponse(BaseModel):
    """Paginated catalog response: published, applicable requirements."""

    items: list[CatalogRequirementItem]
    limit: int
    offset: int
    total: int
