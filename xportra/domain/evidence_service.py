"""Domain-facing corpus service above the evidence corpus repository."""

from typing import Any
from uuid import UUID

from xportra.persistence.errors import PersistenceIntegrityError
from xportra.persistence.repositories import EvidenceDocumentRepository
from xportra.persistence.tenant import TenantContext

from .errors import (
    DomainNotFoundError,
    DomainPersistenceError,
    DomainValidationError,
    require_tenant_context,
)
from .evidence_corpus import EvidenceDocument


def _norm_version(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


class EvidenceCorpusService:
    """Create and read tenant-scoped evidence corpus documents."""

    def __init__(self, repository: EvidenceDocumentRepository) -> None:
        self._repository = repository

    def create(self, tenant: TenantContext, **values: Any) -> dict[str, Any]:
        require_tenant_context(tenant)
        document = EvidenceDocument.create(tenant, **values)
        existing = self._repository.get_by_source_identity(
            tenant, document.source_id, document.document_version
        )
        if existing is not None:
            raise DomainValidationError(
                "evidence document already exists for source identity"
            )
        try:
            row = self._repository.create(document.to_record())
        except PersistenceIntegrityError as cause:
            raise DomainPersistenceError(
                "evidence document creation", cause
            ) from cause
        if row.get("tenant_id") != tenant.tenant_id:
            raise DomainValidationError("cross-tenant document write")
        return row

    def get(
        self, tenant: TenantContext, document_id: UUID
    ) -> dict[str, Any] | None:
        require_tenant_context(tenant)
        return self._repository.get_by_id(tenant, document_id)

    def get_by_source(
        self, tenant: TenantContext, source_id: str, version: Any = None
    ) -> dict[str, Any] | None:
        require_tenant_context(tenant)
        if not isinstance(source_id, str) or not source_id.strip():
            raise DomainValidationError("source_id is required")
        return self._repository.get_by_source_identity(
            tenant, source_id.strip(), _norm_version(version)
        )

    def list_for_tenant(self, tenant: TenantContext) -> list[dict[str, Any]]:
        require_tenant_context(tenant)
        return self._repository.list_for_tenant(tenant)

    def require_active(
        self, tenant: TenantContext, document_id: UUID
    ) -> dict[str, Any]:
        row = self.get(tenant, document_id)
        if row is None:
            raise DomainNotFoundError("evidence document was not found")
        if row.get("status") != "active":
            raise DomainValidationError("evidence document is not active")
        return row
