"""Dependency wiring for the API boundary."""

from dataclasses import dataclass
import os
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request

from xportra.domain.services import (
    CertificationService,
    ComplianceEvidenceService,
    DestinationMarketService,
    ExporterService,
    ProductService,
)
from xportra.persistence.database import Database, DatabaseSettings
from xportra.persistence.repositories import (
    AuthorityRepository,
    CertificationPermitLicenseRepository,
    ComplianceEvidenceRepository,
    DestinationMarketRepository,
    EvidenceRequirementRepository,
    ExporterRepository,
    ProductRepository,
    RequirementRepository,
    UserRepository,
    UserTenantMembershipRepository,
)
from xportra.persistence.tenant import TenantContext

from .auth import (
    DEVELOPMENT_TENANT_HEADER,
    TENANT_SELECTION_HEADER,
    MemberContext,
    SupabaseAuthSettings,
    SupabaseTokenVerifier,
    TenantMembershipResolver,
)
from .authorization import OWNER_ROLE, authorize, require_permission
from .errors import APIError, AuthenticationError


@dataclass(frozen=True, slots=True)
class ApplicationServices:
    database: Database
    exporters: ExporterService
    products: ProductService
    destinations: DestinationMarketService
    evidence: ComplianceEvidenceService
    certifications: CertificationService

    @classmethod
    def from_environment(cls) -> "ApplicationServices":
        database = Database(DatabaseSettings.from_environment())
        exporter_repository = ExporterRepository(database)
        product_repository = ProductRepository(database)
        destination_repository = DestinationMarketRepository(database)
        requirement_repository = RequirementRepository(database)
        evidence_repository = ComplianceEvidenceRepository(database)
        evidence_requirement_repository = EvidenceRequirementRepository(database)
        return cls(
            database=database,
            exporters=ExporterService(exporter_repository),
            products=ProductService(exporter_repository, product_repository),
            destinations=DestinationMarketService(destination_repository),
            evidence=ComplianceEvidenceService(
                database,
                evidence_repository,
                evidence_requirement_repository,
                requirement_repository,
            ),
            certifications=CertificationService(
                exporter_repository,
                AuthorityRepository(database),
                CertificationPermitLicenseRepository(database),
            ),
        )


def get_services(request: Request) -> ApplicationServices:
    services = getattr(request.app.state, "services", None)
    if services is None:
        raise APIError(
            503,
            "application_not_ready",
            "Application services are not initialized",
        )
    return services


def get_development_tenant_context(
    x_development_tenant_id: Annotated[
        str | None,
        Header(alias=DEVELOPMENT_TENANT_HEADER),
    ] = None,
) -> TenantContext:
    """Translate the explicit development/test tenant header into TenantContext.

    This dependency is intentionally not authentication and is only reachable
    as an isolated development/test pathway that cannot be enabled in
    production. Production deployments must use authenticated identity.
    """
    if os.environ.get("APP_ENV", "development").lower() == "production":
        raise APIError(
            503,
            "development_tenant_context_disabled",
            "Development tenant context is disabled in production",
        )
    if not x_development_tenant_id or not x_development_tenant_id.strip():
        raise APIError(
            400,
            "tenant_context_required",
            "A development/test tenant ID is required for this unauthenticated API",
        )
    try:
        tenant_id = UUID(x_development_tenant_id.strip())
    except (ValueError, AttributeError) as cause:
        raise APIError(
            422,
            "invalid_tenant_context",
            "Development/test tenant ID must be a UUID",
        ) from cause
    return TenantContext(tenant_id)


def _is_production() -> bool:
    return os.environ.get("APP_ENV", "development").lower() == "production"


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise AuthenticationError(
            "invalid_token", "Bearer access token is required or malformed"
        )
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise AuthenticationError(
            "invalid_token", "Bearer access token is required or malformed"
        )
    return parts[1].strip()


def _requested_tenant_id(value: str | None) -> UUID | None:
    if value is None or not value.strip():
        return None
    try:
        return UUID(value.strip())
    except (ValueError, AttributeError) as cause:
        raise APIError(
            422,
            "invalid_tenant_context",
            "Tenant selection must be a UUID",
        ) from cause


def _authenticated_member_context(
    request: Request,
    authorization: str,
    tenant_selection: str | None,
) -> MemberContext:
    services = get_services(request)
    token = _bearer_token(authorization)
    settings = SupabaseAuthSettings.from_environment()
    identity = SupabaseTokenVerifier(settings).verify(token)
    resolver = TenantMembershipResolver(
        UserRepository(services.database),
        UserTenantMembershipRepository(services.database),
    )
    return resolver.resolve_member(identity, _requested_tenant_id(tenant_selection))


def get_member_context(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_xportra_tenant_id: Annotated[
        str | None, Header(alias=TENANT_SELECTION_HEADER)
    ] = None,
    x_development_tenant_id: Annotated[
        str | None, Header(alias=DEVELOPMENT_TENANT_HEADER)
    ] = None,
) -> MemberContext:
    """Resolve the authenticated member context from identity and membership."""
    if authorization is not None:
        return _authenticated_member_context(
            request, authorization, x_xportra_tenant_id
        )
    if _is_production():
        if x_development_tenant_id is not None:
            raise APIError(
                503,
                "development_tenant_context_disabled",
                "Development tenant context is disabled in production",
            )
        raise AuthenticationError("authentication_required", "Authentication is required")
    if x_development_tenant_id is not None:
        tenant = get_development_tenant_context(x_development_tenant_id)
        return MemberContext(tenant, OWNER_ROLE)
    raise AuthenticationError("authentication_required", "Authentication is required")


def get_tenant_context(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_xportra_tenant_id: Annotated[
        str | None, Header(alias=TENANT_SELECTION_HEADER)
    ] = None,
    x_development_tenant_id: Annotated[
        str | None, Header(alias=DEVELOPMENT_TENANT_HEADER)
    ] = None,
) -> TenantContext:
    """Resolve the request's TenantContext from verified identity and membership."""
    return get_member_context(
        request,
        authorization,
        x_xportra_tenant_id,
        x_development_tenant_id,
    ).tenant


ServicesDependency = Annotated[ApplicationServices, Depends(get_services)]
MemberContextDependency = Annotated[
    MemberContext,
    Depends(get_member_context),
]
TenantContextDependency = Annotated[
    TenantContext,
    Depends(get_tenant_context),
]


def require_permission(permission: str):
    def dependency(member: MemberContextDependency) -> MemberContext:
        return authorize(member, permission)

    return dependency
