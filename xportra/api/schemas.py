"""HTTP request and response schemas for the API boundary."""

from datetime import date, datetime
from typing import Literal
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
