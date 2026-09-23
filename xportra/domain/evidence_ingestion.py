"""Controlled evidence ingestion boundary for Phase 4.1."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from xportra.persistence.errors import PersistenceIntegrityError
from xportra.persistence.repositories import EvidenceDocumentRepository
from xportra.persistence.tenant import TenantContext

from .errors import (
    DomainPersistenceError,
    DomainValidationError,
    require_tenant_context,
)
from .evidence_corpus import (
    SOURCE_TYPES,
    EvidenceDocument,
)


def _strip(value: Any) -> str:
    """Deterministic loss-minimizing normalization: trim whitespace only."""
    return value.strip() if isinstance(value, str) else ""


class EvidenceDocumentIngestionService:
    """Validate, normalize, and persist source evidence records.

    Entry ``ingest(source_record, *, tenant_id)`` owns the ingestion
    contract; ``EvidenceDocumentRepository`` owns persistence mechanics.
    Normalization is loss-minimizing: surrounding whitespace is stripped
    from ``title``/``source_location`` only; stored ``content`` is
    preserved byte-for-byte so the content fingerprint always reflects
    source evidence. No fetching, no search, no retrieval, no RAG, no LLM.
    """

    def __init__(self, repository: EvidenceDocumentRepository) -> None:
        self._repository = repository

    def ingest(
        self, source_record: dict[str, Any], *, tenant_id: TenantContext
    ) -> dict[str, Any]:
        """Ingest one source record into the evidence corpus."""
        require_tenant_context(tenant_id)
        if not isinstance(source_record, dict):
            raise DomainValidationError("source record is required")
        record_tenant = source_record.get("tenant_id")
        if record_tenant is not None and record_tenant != tenant_id.tenant_id:
            raise DomainValidationError("conflicting tenant identity")
        source_id = _strip(source_record.get("source_id"))
        if not source_id:
            raise DomainValidationError("source_id is required")
        source_type = source_record.get("source_type")
        if source_type not in SOURCE_TYPES:
            raise DomainValidationError("unsupported source_type")
        location = _strip(source_record.get("source_location"))
        if not location:
            raise DomainValidationError("source_location is required")
        title = _strip(source_record.get("title"))
        if not title:
            raise DomainValidationError("title is required")
        content = source_record.get("content")
        if not isinstance(content, str) or not content.strip():
            raise DomainValidationError("content is required")
        metadata = source_record.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            raise DomainValidationError("metadata is malformed")
        for field in ("effective_date", "retrieved_at"):
            value = source_record.get(field)
            if value is not None and not hasattr(value, "isoformat"):
                raise DomainValidationError(f"{field} is malformed")
        version_raw = source_record.get("document_version")
        if version_raw is not None and not isinstance(version_raw, str):
            raise DomainValidationError("document_version is malformed")
        if isinstance(version_raw, str) and version_raw != version_raw.strip():
            raise DomainValidationError("document_version is malformed")
        document = EvidenceDocument.create(
            tenant_id,
            title=title,
            content=content,
            source_type=source_type,
            source_id=source_id,
            source_location=location,
            jurisdiction=source_record.get("jurisdiction"),
            document_version=version_raw,
            effective_date=source_record.get("effective_date"),
            retrieved_at=source_record.get("retrieved_at"),
            status=source_record.get("status", "active"),
            metadata=dict(metadata) if metadata is not None else {},
        )
        existing = self._repository.get_by_source_identity(
            tenant_id, document.source_id, document.document_version
        )
        if existing is not None:
            self._require_identical(existing, document, tenant_id)
            return existing
        try:
            row = self._repository.create(document.to_record())
        except PersistenceIntegrityError as cause:
            raise DomainPersistenceError(
                "evidence document ingestion", cause
            ) from cause
        if row.get("tenant_id") != tenant_id.tenant_id:
            raise DomainValidationError("cross-tenant document write")
        return row

    @staticmethod
    def _require_identical(
        existing: dict[str, Any],
        document: EvidenceDocument,
        tenant_id: TenantContext,
    ) -> None:
        if existing.get("tenant_id") != tenant_id.tenant_id:
            raise DomainValidationError("cross-tenant document write")
        expected = document.to_record()
        for field in (
            "title", "content", "source_type", "source_id",
            "source_location", "jurisdiction", "document_version",
            "status", "metadata",
        ):
            if (existing.get(field) or None) != (expected.get(field) or None):
                raise DomainValidationError(
                    "conflicting evidence document content"
                )
        if existing.get("content_fingerprint") != expected.get(
            "content_fingerprint"
        ):
            raise DomainValidationError(
                "conflicting evidence document content"
            )
        if str(existing.get("id")) != str(expected.get("id")):
            raise DomainValidationError("document identity mismatch")
