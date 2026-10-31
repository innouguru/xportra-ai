"""Exporter-facing regulatory catalog API (Phase 4D.10 Task 7).

One endpoint:

    GET /catalog/requirements

Handler shape (mirrors the established Phase 8.2 boundary):

1. ``require_permission(READ_TENANT_RESOURCE)`` resolves the authorized
   ``MemberContext`` — tenant identity comes from server-side membership,
   never the request body.
2. Exactly one application use case is invoked:
   ``RegulatoryCatalogService.list_catalog_requirements``.
3. The result is returned for Pydantic serialization.

The catalog exposes only published requirements that have a durable
applicability decision of ``applicable`` for the requesting tenant's
scope. Unknown, missing, unpublished, or out-of-scope requirements are
excluded. Staff-only, tenant-private, and audit information is never
exposed.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from xportra.application.regulatory_catalog_service import RegulatoryCatalogService
from xportra.api.auth import MemberContext
from xportra.api.authorization import READ_TENANT_RESOURCE
from xportra.api.dependencies import ServicesDependency, require_permission
from xportra.api.schemas import (
    CatalogRequirementsResponse,
    CatalogRequirementItem,
    CatalogSourceReference,
    CatalogCitationReference,
    CatalogApplicability,
)
from xportra.api.errors import APIError
from xportra.persistence.tenant import TenantContext

router = APIRouter(tags=["catalog"])


def _catalog_service(services: ServicesDependency) -> RegulatoryCatalogService:
    """Build the catalog service from the application container."""
    database = getattr(services, "database", None)
    if database is None:
        raise APIError(
            503,
            "application_not_ready",
            "Application services are not initialized",
        )
    return RegulatoryCatalogService(database)


CatalogServiceDependency = Annotated[
    RegulatoryCatalogService, Depends(_catalog_service)
]


@router.get(
    "/catalog/requirements",
    response_model=CatalogRequirementsResponse,
    status_code=status.HTTP_200_OK,
)
def list_catalog_requirements(
    service: CatalogServiceDependency,
    member: Annotated[
        MemberContext, Depends(require_permission(READ_TENANT_RESOURCE))
    ],
    product: Annotated[str | None, Query(description="Commodity or product code")] = None,
    origin_country: Annotated[
        str | None, Query(description="Origin country ISO code (e.g. NG)")
    ] = None,
    destination_country: Annotated[
        str | None, Query(description="Destination country ISO code (e.g. NL)")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CatalogRequirementsResponse:
    """List published regulatory requirements applicable to the organization's scope.

    Requires an authenticated user with an active tenant membership and the
    ``read_tenant_resource`` permission. Tenant identity is resolved
    server-side from membership; the caller cannot supply a tenant ID.

    Returns only requirements that:
    - have been deliberately published (status = 'published'),
    - passed Stage A verification and Stage B approval,
    - have an active source,
    - have a durable applicability decision of 'applicable' for this tenant
      under the requested scope (or any scope when no scope parameters are
      given),
    - have no pending review flags blocking publication.

    Unknown, missing, or unresolved applicability is never returned as
    applicable. Staff-only, tenant-private, and audit information is never
    exposed.
    """
    result = service.list_catalog_requirements(
        TenantContext(member.tenant.tenant_id),
        product=product,
        origin_country=origin_country,
        destination_country=destination_country,
        limit=limit,
        offset=offset,
    )

    return CatalogRequirementsResponse(
        items=[
            CatalogRequirementItem(
                requirement_id=item["requirement_id"],
                requirement_text=item["requirement_text"],
                requirement_type=item["requirement_type"],
                stage_a_status=item["stage_a_status"],
                stage_b_status=item["stage_b_status"],
                stage_b_pilot_scope=item["stage_b_pilot_scope"],
                published_at=item["published_at"],
                source=CatalogSourceReference(
                    source_id=item["source"]["source_id"],
                    source_title=item["source"]["source_title"],
                    source_jurisdiction=item["source"]["source_jurisdiction"],
                    source_version=item["source"]["source_version"],
                    source_status=item["source"]["source_status"],
                ),
                citation=CatalogCitationReference(
                    normalized_document_id=item["citation"][
                        "normalized_document_id"
                    ],
                    source_location=item["citation"]["source_location"],
                    position=item["citation"]["position"],
                    parser_version=item["citation"]["parser_version"],
                ),
                applicability=CatalogApplicability(
                    outcome=item["applicability"]["outcome"],
                    reason=item["applicability"]["reason"],
                    context_fingerprint=item["applicability"][
                        "context_fingerprint"
                    ],
                ),
            )
            for item in result["items"]
        ],
        limit=result["limit"],
        offset=result["offset"],
        total=result["total"],
    )
