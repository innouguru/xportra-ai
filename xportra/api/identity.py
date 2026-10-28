"""Current-account identity read for the authenticated shell.

``GET /me`` returns the authenticated person's display name, email, and
the organization they are working under, resolved server-side from the
verified Supabase session and the user's active tenant membership.

Every request is authenticated. The current user is resolved exclusively
from the trusted JWT subject (``users.supabase_uid`` -> ``users.id``);
the request never accepts a user id or tenant id as proof of access.
Tenant isolation is enforced because only memberships belonging to the
authenticated user are ever returned, and no arbitrary organization is
selected when the user holds multiple active memberships.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header

from .auth import SupabaseAuthSettings, SupabaseTokenVerifier, TENANT_SELECTION_HEADER
from .dependencies import ServicesDependency
from .errors import APIError, AuthenticationError
from .schemas import IdentityResponse
from xportra.persistence.repositories import (
    UserRepository,
    UserTenantMembershipRepository,
)

router = APIRouter(tags=["identity"])


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


@router.get("/me", response_model=IdentityResponse)
def current_identity(
    services: ServicesDependency,
    authorization: Annotated[str | None, Header()] = None,
    x_xportra_tenant_id: Annotated[
        str | None, Header(alias=TENANT_SELECTION_HEADER)
    ] = None,
) -> IdentityResponse:
    """Return the caller's identity and active organization context.

    Resolves the user from the verified Supabase subject (never from a
    client-supplied id) and returns only the identity fields the shell
    needs: display name, email, and the active organization name.
    """
    database = services.database
    token = _bearer_token(authorization)
    settings = SupabaseAuthSettings.from_environment()
    identity = SupabaseTokenVerifier(settings).verify(token)

    users = UserRepository(database)
    memberships = UserTenantMembershipRepository(database)

    user = users.get_by_supabase_uid(identity.subject)
    if user is None:
        raise APIError(
            403,
            "identity_not_provisioned",
            "The authenticated account is not provisioned in Xportra.",
        )

    requested_tenant_id: UUID | None = None
    if x_xportra_tenant_id is not None and x_xportra_tenant_id.strip():
        try:
            requested_tenant_id = UUID(x_xportra_tenant_id.strip())
        except (ValueError, AttributeError) as cause:
            raise APIError(
                422,
                "invalid_tenant_context",
                "Tenant selection must be a UUID",
            ) from cause

    active = memberships.list_active_for_user(user["id"])
    organization_id: UUID | None = None
    organization_name: str | None = None
    role: str | None = None

    if active:
        if requested_tenant_id is not None:
            selected = None
            for membership in active:
                if membership["tenant_id"] == requested_tenant_id:
                    selected = membership
                    break
            if selected is None:
                raise APIError(
                    403,
                    "tenant_not_member",
                    "The authenticated user is not a member of the requested tenant.",
                )
        elif len(active) == 1:
            selected = active[0]
        else:
            # Multiple active memberships without an explicit selection:
            # do not pick an arbitrary organization. The user identity is
            # still returned so the shell can show name and email.
            selected = None

        if selected is not None:
            organization_id = selected["tenant_id"]
            organization_name = selected.get("tenant_legal_name")
            role = selected.get("role")

    return IdentityResponse(
        user_id=user["id"],
        display_name=user.get("display_name") or "",
        email=user.get("email") or identity.email,
        organization_id=organization_id,
        organization_name=organization_name,
        role=role,
    )
