"""FastAPI routes for the intentionally small Phase 1.8 resource API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from xportra.domain.errors import DomainNotFoundError

from .auth import MemberContext
from .dependencies import ServicesDependency, require_permission
from .authorization import (
    ASSOCIATE_EVIDENCE_REQUIREMENT,
    CREATE_CERTIFICATION,
    CREATE_COMPLIANCE_EVIDENCE,
    CREATE_DESTINATION_MARKET,
    CREATE_EXPORTER,
    CREATE_PRODUCT,
    READ_TENANT_RESOURCE,
)
from .schemas import (
    CertificationCreateRequest,
    CertificationResponse,
    ComplianceEvidenceCreateRequest,
    ComplianceEvidenceResponse,
    ComplianceEvidenceWithRequirementsRequest,
    DestinationMarketCreateRequest,
    DestinationMarketResponse,
    EvidenceRequirementAssociationRequest,
    EvidenceRequirementAssociationResponse,
    ExporterCreateRequest,
    ExporterResponse,
    ProductCreateRequest,
    ProductResponse,
)

router = APIRouter()


def _require_record(record, resource_name: str, record_id: UUID):
    if record is None:
        raise DomainNotFoundError(f"{resource_name} {record_id} was not found for tenant")
    return record


@router.post(
    "/exporters",
    response_model=ExporterResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_exporter(
    payload: ExporterCreateRequest,
    services: ServicesDependency,
    member: Annotated[MemberContext, Depends(require_permission(CREATE_EXPORTER))],
):
    return services.exporters.create(member.tenant, **payload.model_dump())


@router.get("/exporters/{exporter_id}", response_model=ExporterResponse)
def get_exporter(
    exporter_id: UUID,
    services: ServicesDependency,
    member: Annotated[MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))],
):
    record = services.exporters.get(member.tenant, exporter_id)
    return _require_record(record, "exporter", exporter_id)


@router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    payload: ProductCreateRequest,
    services: ServicesDependency,
    member: Annotated[MemberContext, Depends(require_permission(CREATE_PRODUCT))],
):
    return services.products.create(member.tenant, **payload.model_dump())


@router.get("/products/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: UUID,
    services: ServicesDependency,
    member: Annotated[MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))],
):
    record = services.products.get(member.tenant, product_id)
    return _require_record(record, "product", product_id)


@router.post(
    "/destination-markets",
    response_model=DestinationMarketResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_destination_market(
    payload: DestinationMarketCreateRequest,
    services: ServicesDependency,
    member: Annotated[MemberContext, Depends(require_permission(CREATE_DESTINATION_MARKET))],
):
    return services.destinations.register(member.tenant, **payload.model_dump())


@router.get(
    "/destination-markets/{destination_id}",
    response_model=DestinationMarketResponse,
)
def get_destination_market(
    destination_id: UUID,
    services: ServicesDependency,
    member: Annotated[MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))],
):
    record = services.destinations.get(member.tenant, destination_id)
    return _require_record(record, "destination market", destination_id)


@router.post(
    "/compliance-evidence/with-requirements",
    response_model=ComplianceEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_compliance_evidence_with_requirements(
    payload: ComplianceEvidenceWithRequirementsRequest,
    services: ServicesDependency,
    member: Annotated[MemberContext, Depends(require_permission(CREATE_COMPLIANCE_EVIDENCE))],
):
    values = payload.model_dump()
    requirement_ids = values.pop("requirement_ids")
    return services.evidence.record_with_requirements(
        member.tenant,
        requirement_ids=requirement_ids,
        **values,
    )


@router.post(
    "/compliance-evidence",
    response_model=ComplianceEvidenceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_compliance_evidence(
    payload: ComplianceEvidenceCreateRequest,
    services: ServicesDependency,
    member: Annotated[MemberContext, Depends(require_permission(CREATE_COMPLIANCE_EVIDENCE))],
):
    return services.evidence.record(member.tenant, **payload.model_dump())


@router.get(
    "/compliance-evidence/{evidence_id}",
    response_model=ComplianceEvidenceResponse,
)
def get_compliance_evidence(
    evidence_id: UUID,
    services: ServicesDependency,
    member: Annotated[MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))],
):
    record = services.evidence.get(member.tenant, evidence_id)
    return _require_record(record, "compliance evidence", evidence_id)


@router.post(
    "/compliance-evidence/{evidence_id}/requirements",
    response_model=EvidenceRequirementAssociationResponse,
    status_code=status.HTTP_201_CREATED,
)
def associate_compliance_evidence_requirement(
    evidence_id: UUID,
    payload: EvidenceRequirementAssociationRequest,
    services: ServicesDependency,
    member: Annotated[MemberContext, Depends(require_permission(ASSOCIATE_EVIDENCE_REQUIREMENT))],
):
    return services.evidence.associate_requirement(
        member.tenant,
        evidence_id,
        payload.requirement_id,
    )


@router.post(
    "/certifications-permits-licenses",
    response_model=CertificationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_certification_permit_license(
    payload: CertificationCreateRequest,
    services: ServicesDependency,
    member: Annotated[MemberContext, Depends(require_permission(CREATE_CERTIFICATION))],
):
    return services.certifications.record(member.tenant, **payload.model_dump())


@router.get(
    "/certifications-permits-licenses/{certificate_id}",
    response_model=CertificationResponse,
)
def get_certification_permit_license(
    certificate_id: UUID,
    services: ServicesDependency,
    member: Annotated[MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))],
):
    record = services.certifications.get(member.tenant, certificate_id)
    return _require_record(record, "certification", certificate_id)
