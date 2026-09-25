"""Authenticated execution context for application use cases.

Every application use case takes an ``ApplicationContext``
as its first argument and propagates its effective tenant
into the tenant-scoped domain services it orchestrates.

Trust model (mirrors the Phase 1 boundary, unchanged):

- The API layer verifies the caller's access token and
  resolves server-side membership into a ``MemberContext``
  (authenticated subject + effective tenant + role).
- The API layer then builds this context from those
  server-resolved values — never from client-supplied
  tenant IDs::

      ApplicationContext(
          actor_id=identity.subject,
          tenant=member.tenant,
          role=member.role,
      )

- Application use cases propagate ``context.tenant`` and
  never accept a tenant identity from any other source.
- Role enforcement stays owned by the existing API
  authorization policy (``authorize``); use cases declare
  which permission the API must require, and the role
  carried here is informational. The application layer
  performs no authorization redesign.

This module depends on no HTTP, API, or frontend
constructs and is independently callable.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from xportra.persistence.tenant import TenantContext


@dataclass(frozen=True, slots=True)
class ApplicationContext:
    """Who is acting, in which tenant, under which role.

    ``actor_id`` is the authenticated subject (``None``
    only where the API explicitly permits an unauthenticated
    development identity); ``tenant`` is the effective
    tenant resolved server-side; ``role`` is the membership
    role (``"owner"`` / ``"member"`` per the Phase 1 policy).
    """

    actor_id: UUID | None
    tenant: TenantContext
    role: str

    def __post_init__(self) -> None:
        if self.actor_id is not None and not isinstance(
                self.actor_id, UUID):
            raise TypeError("actor_id must be a UUID or None")
        if not isinstance(self.tenant, TenantContext):
            raise TypeError("tenant must be a TenantContext")
        if not isinstance(self.role, str) or not self.role.strip():
            raise ValueError("role must be a non-empty string")

    @property
    def tenant_id(self) -> UUID:
        """The effective tenant identity for domain calls."""
        return self.tenant.tenant_id


__all__ = [
    "ApplicationContext",
]
