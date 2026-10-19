"""Thin organization-registration HTTP adapter (Phase 10.11).

One endpoint over the organization-registration use case::

    POST /organizations

Handler shape (mirrors the established Phase 8.2 boundary):

1. ``get_authenticated_identity`` verifies the Supabase access
   token through the existing ES256/JWKS (or retained HS256)
   contract and returns only the authenticated subject + email.
   It resolves *no* membership — the membership does not exist
   yet, which is the whole point of registration.
2. The handler passes the verified identity plus the organization
   profile to exactly one application use case.
3. The use case derives the tenant, the Xportra user, and the
   initial ``owner`` membership server-side and returns
   identifiers only.

The request body can never supply a tenant id, user id, Supabase
subject, role, or membership status (``extra="forbid"``), so an
authenticated user cannot assign themselves a privileged role or an
arbitrary tenant. Registration confers no regulatory verification,
approval, or compliance status — only an active workspace.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from .auth import AuthenticatedIdentity
from .dependencies import (
    OrganizationRegistrationServiceDependency,
    get_authenticated_identity,
)
from .schemas import (
    OrganizationRegistrationRequest,
    OrganizationRegistrationResponse,
)

router = APIRouter(tags=["organizations"])


@router.post(
    "/organizations",
    response_model=OrganizationRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_organization(
    payload: OrganizationRegistrationRequest,
    identity: Annotated[
        AuthenticatedIdentity, Depends(get_authenticated_identity)
    ],
    service: OrganizationRegistrationServiceDependency,
):
    """Register a new organization for the authenticated identity.

    Idempotent and safe on retry: an identity that already holds an
    active membership receives a conflict instead of a duplicate
    organization. Tenant, user, and role are server-derived.
    """
    result = service.register(
        supabase_uid=identity.subject,
        identity_email=identity.email,
        organization_name=payload.organization_name,
        organization_type=payload.organization_type,
        country_code=payload.country_code,
        region=payload.region,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
    )
    return OrganizationRegistrationResponse(
        organization_id=result.organization_id,
        organization_slug=result.organization_slug,
        organization_name=result.organization_name,
        user_id=result.user_id,
        role=result.role,
        membership_status=result.membership_status,
    )
