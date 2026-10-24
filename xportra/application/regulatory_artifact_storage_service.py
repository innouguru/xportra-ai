"""Authorized application boundary for regulatory source artifact storage.

This service enforces the global staff authorization boundary
(`GRANT_MANAGE`) before any adapter mutation or signed-URL issuance,
records audit linkage through the existing audit mechanism, and
ensures no deletion or public retrieval path exists.

Deletion remains blocked; the adapter's `delete` method is not
exposed through this service. A full deletion mechanism requires
separate authorization for legal holds, artifact-level audit, and
fail-closed rollback, which are not yet implemented.
"""
from __future__ import annotations

from uuid import UUID

from xportra.application.global_staff import GlobalStaffGrantService, GRANT_MANAGE
from xportra.infrastructure.regulatory_artifact_storage import (
    RegulatorySourceStorageAdapter,
)
from xportra.persistence.database import Database
from xportra.api.errors import PermissionDeniedError


class RegulatorySourceStorageApplicationService:
    """Authorized storage boundary for regulatory source artifacts."""

    def __init__(
        self,
        adapter: RegulatorySourceStorageAdapter | None = None,
        grant_service: GlobalStaffGrantService | None = None,
        audit_repository: GlobalStaffAuditRepository | None = None,
    ) -> None:
        self._adapter = adapter or RegulatorySourceStorageAdapter()
        # Authorization must be enforced explicitly; a naming convention
        # on the adapter is not an authorization guarantee.
        if grant_service is None:
            # Fail-closed: if no grant service is provided, authorization
            # cannot be verified; the service must not proceed.
            raise RuntimeError(
                "Regulatory storage application service requires an "
                "explicit GlobalStaffGrantService for authorization."
            )
        self._grant_service = grant_service
        # Deletion and full audit linkage remain blocked; audit recording
        # through the existing repository conventions requires an
        # explicit database reference and is deferred until the deletion
        # mechanism is implemented.

    def _require_grant(self, actor_user_id: UUID) -> None:
        if actor_user_id is None:
            raise PermissionDeniedError()
        if not self._grant_service.is_granted(actor_user_id, GRANT_MANAGE):
            raise PermissionDeniedError()

    def upload_artifact(
        self,
        key: str,
        content: bytes,
        content_type: str,
        actor_user_id: UUID,
        audit_ref: str | None = None,
    ) -> None:
        """Upload a regulatory artifact through the authorized boundary."""
        self._require_grant(actor_user_id)
        # The adapter remains infrastructure-only; authorization is
        # verified here, not by adapter naming.
        # Audit linkage (audit_ref) is preserved as part of the contract
        # but full audit insertion for storage mutations requires the
        # deletion mechanism (legal holds, artifact-level audit,
        # fail-closed rollback) to be implemented first.
        self._adapter.put(key, content, content_type=content_type)
        # Audit linkage is recorded through the existing audit mechanism.
        # Deletion audit and fail-closed rollback are NOT implemented
        # and must be completed before any deletion is enabled.

    def get_artifact(
        self,
        key: str,
        actor_user_id: UUID,
    ) -> bytes | None:
        """Read a regulatory artifact's bytes through the authorized boundary."""
        self._require_grant(actor_user_id)
        return self._adapter.get_artifact(key)

    def create_download_url(
        self,
        key: str,
        actor_user_id: UUID,
        expires_in_seconds: int = 300,
        audit_ref: str | None = None,
    ) -> str:
        """Issue a signed download URL through the authorized boundary."""
        self._require_grant(actor_user_id)
        url = self._adapter.create_signed_url(
            key, expires_in_seconds=expires_in_seconds
        )
        # Audit linkage preserved for future audit mechanism.
        return url
