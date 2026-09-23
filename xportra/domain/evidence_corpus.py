"""Evidence corpus foundation for Phase 4.0."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from xportra.domain.errors import DomainValidationError, require_tenant_context
from xportra.persistence.tenant import TenantContext

SOURCE_TYPES = frozenset({"regulation", "guidance", "certificate", "policy", "other"})
DOCUMENT_STATUSES = frozenset({"active", "inactive"})


def stable_document_id(tenant_id: UUID, source_id: str, version: str | None) -> UUID:
    """Stable uuid5 from tenant hex + source_id + version (no secrets)."""
    key = ":".join(["xportra:evidence-document", tenant_id.hex,
                    source_id, version or ""])
    return uuid5(NAMESPACE_URL, key)


def content_fingerprint(content: str) -> str:
    """sha256 hex of stripped content."""
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()

@dataclass(frozen=True)
class EvidenceDocument:
    """Persistent evidence source document allowed for future retrieval."""

    tenant_id: UUID
    document_id: UUID
    title: str
    content: str
    source_type: str
    source_id: str
    source_location: str | None = None
    jurisdiction: str | None = None
    document_version: str | None = None
    effective_date: date | None = None
    retrieved_at: datetime | None = None
    status: str = "active"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, UUID):
            raise DomainValidationError("tenant_id must be a UUID")
        if not isinstance(self.document_id, UUID):
            raise DomainValidationError("document_id must be a UUID")
        if not isinstance(self.title, str) or not self.title.strip():
            raise DomainValidationError("title is required")
        if not isinstance(self.content, str) or not self.content.strip():
            raise DomainValidationError("content is required")
        if self.source_type not in SOURCE_TYPES:
            raise DomainValidationError("unsupported source_type")
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise DomainValidationError("source_id is required")
        if self.status not in DOCUMENT_STATUSES:
            raise DomainValidationError("unsupported document status")
        if not isinstance(self.metadata, dict):
            raise DomainValidationError("metadata is malformed")
        version = (self.document_version or "").strip()
        expected = stable_document_id(
            self.tenant_id, self.source_id.strip(), version)
        if self.document_id != expected:
            raise DomainValidationError("document_id mismatch")

    @property
    def is_active(self) -> bool:
        return self.status == "active"

    def to_record(self) -> dict[str, Any]:
        version = (self.document_version or "").strip()
        return {
            "id": self.document_id,
            "tenant_id": self.tenant_id,
            "title": self.title.strip(),
            "content": self.content,
            "source_type": self.source_type,
            "source_id": self.source_id.strip(),
            "source_location": self.source_location,
            "jurisdiction": self.jurisdiction,
            "document_version": version or None,
            "effective_date": self.effective_date,
            "retrieved_at": self.retrieved_at,
            "status": self.status,
            "metadata": dict(self.metadata),
            "content_fingerprint": content_fingerprint(self.content),
        }

    @classmethod
    def create(cls, tenant: TenantContext, **kw) -> "EvidenceDocument":
        require_tenant_context(tenant)
        raw_source = kw.get("source_id", "")
        norm_source = raw_source.strip() if isinstance(raw_source, str) else ""
        if not norm_source:
            raise DomainValidationError("source_id is required")
        raw_version = kw.get("document_version")
        norm_version = ""
        if isinstance(raw_version, str) and raw_version.strip():
            norm_version = raw_version.strip()
        title = kw.get("title", "")
        content = kw.get("content", "")
        source_type = kw.get("source_type", "")
        status = kw.get("status", "active")
        metadata = kw.get("metadata")
        if not isinstance(title, str) or not title.strip():
            raise DomainValidationError("title is required")
        if not isinstance(content, str) or not content.strip():
            raise DomainValidationError("content is required")
        if source_type not in SOURCE_TYPES:
            raise DomainValidationError("unsupported source_type")
        if status not in DOCUMENT_STATUSES:
            raise DomainValidationError("unsupported document status")
        if metadata is not None and not isinstance(metadata, dict):
            raise DomainValidationError("metadata is malformed")
        return cls(
            tenant_id=tenant.tenant_id,
            document_id=stable_document_id(
                tenant.tenant_id, norm_source, norm_version),
            title=title.strip(),
            content=content,
            source_type=source_type,
            source_id=norm_source,
            source_location=kw.get("source_location"),
            jurisdiction=kw.get("jurisdiction"),
            document_version=norm_version or None,
            effective_date=kw.get("effective_date"),
            retrieved_at=kw.get("retrieved_at"),
            status=status,
            metadata=dict(metadata) if metadata is not None else {},
        )

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "EvidenceDocument":
        if not isinstance(record, dict):
            raise DomainValidationError("record malformed")
        try:
            return cls(
                tenant_id=record["tenant_id"],
                document_id=record["id"],
                title=record["title"],
                content=record["content"],
                source_type=record["source_type"],
                source_id=record["source_id"],
                source_location=record.get("source_location"),
                jurisdiction=record.get("jurisdiction"),
                document_version=record.get("document_version"),
                effective_date=record.get("effective_date"),
                retrieved_at=record.get("retrieved_at"),
                status=record.get("status", "active"),
                metadata=dict(record.get("metadata") or {}),
            )
        except DomainValidationError:
            raise
        except Exception as exc:
            raise DomainValidationError("record malformed") from exc


