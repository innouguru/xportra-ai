"""Dependency wiring for the API boundary."""

from dataclasses import dataclass, field
import os
from typing import Annotated, Any
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
    #: Phase 5.13 RAG application service (or a test fake implementing
    #: ``RAGApplicationContract``). ``None`` until the retrieval/LLM
    #: infrastructure is wired for an environment — the RAG route then
    #: fails closed with 503 instead of serving an unwired chain.
    rag: Any = field(default=None)

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

    @classmethod
    def from_environment_with_rag(
        cls,
        *,
        llm_client=None,
        embedding_provider=None,
    ) -> "ApplicationServices":
        """Build the full container with the production RAG chain wired.

        Opt-in composition entry point used once per application
        lifecycle (e.g. ``create_app(cls.from_environment_with_rag())``).
        The default ``from_environment`` is unchanged (``rag=None`` →
        the RAG route fails closed with 503). With no explicit
        ``llm_client``, the production OpenRouter adapter is built
        from the canonical LLM settings; an injected client (e.g.
        ``ScriptedLLMClient``) always wins for deterministic use.
        The embedding provider defaults to the approved
        sentence-transformers baseline (lazy — no model download at
        startup). Missing/invalid RAG configuration raises at
        startup, never per request.
        """
        # Resolved lazily via importlib (stdlib) so that xportra.api
        # keeps no static dependency on xportra.infrastructure — the
        # Phase 5.13 boundary guarantee. The composition root itself
        # remains the single explicit wiring place.
        import importlib

        rag_composition = importlib.import_module(
            "xportra.infrastructure.rag_composition"
        )
        base = cls.from_environment()
        stack = rag_composition.compose_rag_stack_from_environment(
            embedding_provider=embedding_provider,
            llm_client=llm_client,
        )
        return cls(
            database=base.database,
            exporters=base.exporters,
            products=base.products,
            destinations=base.destinations,
            evidence=base.evidence,
            certifications=base.certifications,
            rag=stack.service,
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


def get_rag_service(request: Request):
    """Resolve the RAG application service for the request.

    The chain (context pipeline, LLM client, answer validator) is
    injected through the service container, so tests can replace it
    with deterministic fakes. No Qdrant/LLM SDK client is ever
    constructed inside a route handler. Fails closed when the chain
    is not wired for the environment.
    """
    services = get_services(request)
    rag = getattr(services, "rag", None)
    if rag is None:
        raise APIError(
            503,
            "rag_not_configured",
            "The RAG query service is not configured for this deployment",
        )
    return rag


RAGServiceDependency = Annotated[Any, Depends(get_rag_service)]


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
