"""HTTP request and response schemas for the Phase 1.8 API boundary."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


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
