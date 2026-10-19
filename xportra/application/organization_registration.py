"""Organization-level self-service registration use case (Phase 10.11).

A visitor who has authenticated with Supabase can independently
create an Xportra organization without an existing administrator
inviting them first. This use case owns the trusted provisioning
sequence::

    verified Supabase identity
        ↓
    Xportra user mapped to that identity
        ↓
    new organization (the existing tenant row)
        ↓
    active owner membership

Authorization model
-------------------

Authentication establishes identity; this use case establishes the
*only* membership an identity gets at registration time. It never
accepts a tenant id, user id, role, or membership status from the
client — those are derived here (identity from the validated
authentication context supplied by the API boundary, role from the
existing ``owner`` vocabulary, status ``active``). The API layer
requires only a *verified identity* (no prior membership), because
the membership does not exist yet.

This module depends on no HTTP, API, or frontend constructs and is
independently callable: the boundary passes the already-verified
``supabase_uid`` and account email as plain values.

Registration is idempotent and concurrency-safe at the persistence
boundary: a repeated or concurrent registration for an identity that
already holds an active membership returns a conflict instead of
creating duplicate tenants, users, or memberships. It never deletes
or transfers an existing organization, and it does not confer any
regulatory verification, approval, or compliance status — a
registered organization is simply an active workspace.
"""

from __future__ import annotations

import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from xportra.application.errors import (
    ApplicationError,
    ApplicationValidationError,
)

#: Supported registered organization categories (mirrors the
#: migration 014 check constraint). A category is a profile fact,
#: never a regulatory status.
ORGANIZATION_TYPES = (
    "farmer",
    "cooperative",
    "exporter",
    "service_provider",
    "other",
)

#: Initial organization-administrator role (existing vocabulary).
ORGANIZATION_ADMIN_ROLE = "owner"

MAX_ORGANIZATION_NAME_CHARACTERS = 200
MAX_DISPLAY_NAME_CHARACTERS = 200
MAX_REGION_CHARACTERS = 120
MAX_EMAIL_CHARACTERS = 320

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


class OrganizationRegistrationError(ApplicationError):
    """The organization could not be provisioned safely."""

    category = "organization_registration_failed"


class OrganizationAlreadyRegisteredError(OrganizationRegistrationError):
    """The authenticated identity already holds an active membership."""

    category = "organization_already_registered"


class RegistrationStore(Protocol):
    """Trusted provisioning boundary implemented by the persistence layer."""

    def provision(
        self,
        *,
        supabase_uid: UUID,
        email: str | None,
        display_name: str,
        legal_name: str,
        slug: str,
        organization_type: str | None = ...,
        country_code: str | None = ...,
        region: str | None = ...,
        role: str = ...,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class OrganizationRegistrationResult:
    """The outcome of one registration, safe for API serialization."""

    organization_id: UUID
    organization_slug: str
    organization_name: str
    user_id: UUID
    role: str
    membership_status: str


def default_slug_factory(organization_name: str) -> str:
    """Derive a unique-ish, non-identifying tenant slug server-side.

    The human-readable prefix aids operators; the random suffix keeps
    the slug unique without exposing sequential or internal
    identifiers and without requiring a uniqueness pre-check.
    """
    base = _SLUG_STRIP.sub("-", organization_name.strip().lower()).strip("-")
    base = base[:40].strip("-") or "organization"
    return f"{base}-{secrets.token_hex(4)}"


class OrganizationRegistrationService:
    """Provision an organization for a verified Supabase identity."""

    def __init__(
        self,
        store: RegistrationStore,
        *,
        slug_factory: Callable[[str], str] = default_slug_factory,
    ) -> None:
        self._store = store
        self._slug_factory = slug_factory

    def register(
        self,
        *,
        supabase_uid: UUID,
        identity_email: str | None,
        organization_name: str,
        organization_type: str,
        country_code: str | None,
        region: str | None = None,
        contact_name: str | None = None,
        contact_email: str | None = None,
    ) -> OrganizationRegistrationResult:
        if not isinstance(supabase_uid, UUID):
            raise TypeError("supabase_uid must be a UUID")

        name = self._require_text(
            organization_name,
            "organization_name",
            MAX_ORGANIZATION_NAME_CHARACTERS,
        )
        normalized_type = self._validate_type(organization_type)
        normalized_country = self._validate_country(country_code)
        normalized_region = self._optional_text(
            region, "region", MAX_REGION_CHARACTERS
        )
        display_name = self._optional_text(
            contact_name, "contact_name", MAX_DISPLAY_NAME_CHARACTERS
        ) or name

        email = self._resolve_email(identity_email, contact_email)

        slug = self._slug_factory(name)
        if not isinstance(slug, str) or not slug.strip():
            raise OrganizationRegistrationError(
                "The organization reference could not be generated"
            )

        outcome = self._store.provision(
            supabase_uid=supabase_uid,
            email=email,
            display_name=display_name,
            legal_name=name,
            slug=slug,
            organization_type=normalized_type,
            country_code=normalized_country,
            region=normalized_region,
            role=ORGANIZATION_ADMIN_ROLE,
        )
        status = getattr(outcome, "status", None)
        if status == "created":
            return OrganizationRegistrationResult(
                organization_id=outcome.tenant_id,
                organization_slug=outcome.tenant_slug,
                organization_name=outcome.tenant_name,
                user_id=outcome.user_id,
                role=outcome.role,
                membership_status=outcome.membership_status,
            )
        if status == "already_member":
            raise OrganizationAlreadyRegisteredError(
                "This account already belongs to an organization"
            )
        if status == "identity_conflict":
            raise OrganizationAlreadyRegisteredError(
                "This email address is already associated with an account"
            )
        raise OrganizationRegistrationError(
            "The organization could not be created"
        )

    @staticmethod
    def _require_text(value: object, field: str, limit: int) -> str:
        text = value.strip() if isinstance(value, str) else ""
        if not text:
            raise ApplicationValidationError(f"{field} is required")
        if len(text) > limit:
            raise ApplicationValidationError(f"{field} is too long")
        return text

    @classmethod
    def _optional_text(
        cls, value: object, field: str, limit: int
    ) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ApplicationValidationError(f"{field} must be text")
        text = value.strip()
        if not text:
            return None
        if len(text) > limit:
            raise ApplicationValidationError(f"{field} is too long")
        return text

    @staticmethod
    def _validate_type(value: object) -> str:
        text = value.strip().lower() if isinstance(value, str) else ""
        if text not in ORGANIZATION_TYPES:
            raise ApplicationValidationError(
                "organization_type is not a supported category"
            )
        return text

    @staticmethod
    def _validate_country(value: object) -> str:
        text = value.strip().upper() if isinstance(value, str) else ""
        if len(text) != 2 or not text.isascii() or not text.isalpha():
            raise ApplicationValidationError(
                "country_code must be a two-letter country code"
            )
        return text

    @staticmethod
    def _resolve_email(
        identity_email: str | None, contact_email: str | None
    ) -> str | None:
        supplied = (
            contact_email.strip()
            if isinstance(contact_email, str) and contact_email.strip()
            else None
        )
        if supplied is not None and len(supplied) > MAX_EMAIL_CHARACTERS:
            raise ApplicationValidationError("contact_email is too long")
        account_email = (
            identity_email.strip()
            if isinstance(identity_email, str) and identity_email.strip()
            else None
        )
        if account_email is None:
            return supplied
        if supplied is not None and supplied.lower() != account_email.lower():
            raise ApplicationValidationError(
                "contact_email must match the authenticated account email"
            )
        return account_email


__all__ = [
    "MAX_DISPLAY_NAME_CHARACTERS",
    "MAX_ORGANIZATION_NAME_CHARACTERS",
    "ORGANIZATION_ADMIN_ROLE",
    "ORGANIZATION_TYPES",
    "OrganizationAlreadyRegisteredError",
    "OrganizationRegistrationError",
    "OrganizationRegistrationResult",
    "OrganizationRegistrationService",
    "default_slug_factory",
]
