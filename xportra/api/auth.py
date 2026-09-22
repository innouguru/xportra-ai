"""Supabase Auth verification and tenant-identity resolution.

This module lives at the API/application boundary. It verifies Supabase Auth
access tokens using the Supabase project JWT secret (HS256), represents the
authenticated identity, and resolves the tenant context from the authenticated
user's existing membership data. Raw JWTs, HTTP headers, and request objects
are never passed into domain services; only the immutable ``TenantContext``
crosses the boundary.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import jwt as pyjwt

from xportra.persistence.repositories import (
    UserRepository,
    UserTenantMembershipRepository,
)
from xportra.persistence.tenant import TenantContext

from .errors import APIError, AuthenticationError

DEVELOPMENT_TENANT_HEADER = "X-Development-Tenant-ID"
TENANT_SELECTION_HEADER = "X-Xportra-Tenant-ID"

ACCESS_TOKEN_ISSUER_SUFFIX = "/auth/v1"


class AuthConfigurationError(ValueError):
    """Supabase authentication configuration is missing or incomplete."""


@dataclass(frozen=True, slots=True)
class SupabaseAuthSettings:
    jwt_secret: str
    audience: str = "authenticated"
    supabase_url: str | None = None

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "SupabaseAuthSettings":
        values = os.environ if environment is None else environment
        secret = values.get("SUPABASE_JWT_SECRET", "").strip()
        if not secret:
            raise AuthConfigurationError("SUPABASE_JWT_SECRET is required")
        audience = values.get("SUPABASE_JWT_AUDIENCE", "").strip() or "authenticated"
        url = values.get("SUPABASE_URL", "").strip() or None
        return cls(jwt_secret=secret, audience=audience, supabase_url=url)


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    subject: UUID
    email: str | None = None


@dataclass(frozen=True, slots=True)
class MemberContext:
    """Authenticated tenant context plus the membership role resolved server-side."""

    tenant: TenantContext
    role: str

    def __post_init__(self) -> None:
        if not isinstance(self.tenant, TenantContext):
            raise TypeError("tenant must be a TenantContext")
        if not isinstance(self.role, str) or not self.role.strip():
            raise ValueError("role must be a non-empty string")


class SupabaseTokenVerifier:
    """Verify a Supabase Auth access token and extract the authenticated identity."""

    def __init__(self, settings: SupabaseAuthSettings) -> None:
        self._settings = settings

    def verify(self, token: str) -> AuthenticatedIdentity:
        try:
            payload = pyjwt.decode(
                token,
                key=self._settings.jwt_secret,
                algorithms=["HS256"],
                audience=self._settings.audience,
                options={"require": ["exp", "sub"]},
            )
        except pyjwt.ExpiredSignatureError as cause:
            raise AuthenticationError(
                "expired_token", "The access token has expired"
            ) from cause
        except pyjwt.InvalidTokenError as cause:
            raise AuthenticationError(
                "invalid_token", "The access token is invalid"
            ) from cause
        if self._settings.supabase_url is not None:
            expected_issuer = (
                self._settings.supabase_url.rstrip("/") + ACCESS_TOKEN_ISSUER_SUFFIX
            )
            if payload.get("iss") != expected_issuer:
                raise AuthenticationError(
                    "invalid_token", "The access token is invalid"
                )
        return AuthenticatedIdentity(
            subject=self._subject(payload),
            email=payload.get("email"),
        )

    @staticmethod
    def _subject(payload: dict[str, Any]) -> UUID:
        try:
            return UUID(str(payload.get("sub")))
        except (ValueError, TypeError) as cause:
            raise AuthenticationError(
                "invalid_token",
                "The access token does not carry a valid user subject",
            ) from cause


class TenantMembershipResolver:
    """Resolve the authenticated user's ``TenantContext`` from membership data."""

    def __init__(
        self,
        users: UserRepository,
        memberships: UserTenantMembershipRepository,
    ) -> None:
        self._users = users
        self._memberships = memberships

    def resolve(
        self,
        identity: AuthenticatedIdentity,
        requested_tenant_id: UUID | None = None,
    ) -> TenantContext:
        return self.resolve_member(identity, requested_tenant_id).tenant

    def resolve_member(
        self,
        identity: AuthenticatedIdentity,
        requested_tenant_id: UUID | None = None,
    ) -> MemberContext:
        user = self._users.get_by_supabase_uid(identity.subject)
        active = (
            self._memberships.list_active_for_user(user["id"])
            if user is not None
            else []
        )
        if not active:
            raise APIError(
                403,
                "tenant_membership_required",
                "The authenticated user has no active tenant membership",
            )
        selected = self._select_membership(active, requested_tenant_id)
        role = selected.get("role")
        if not isinstance(role, str) or not role.strip():
            raise APIError(
                403,
                "tenant_membership_required",
                "The authenticated user has no usable tenant membership role",
            )
        return MemberContext(TenantContext(selected["tenant_id"]), role)

    @staticmethod
    def _select_membership(
        memberships: list[dict[str, Any]],
        requested_tenant_id: UUID | None,
    ) -> dict[str, Any]:
        if requested_tenant_id is None:
            if len(memberships) == 1:
                return memberships[0]
            raise APIError(
                400,
                "tenant_selection_required",
                "The authenticated user belongs to multiple tenants; select one",
            )
        for membership in memberships:
            if membership["tenant_id"] == requested_tenant_id:
                return membership
        raise APIError(
            403,
            "tenant_not_member",
            "The authenticated user is not a member of the requested tenant",
        )