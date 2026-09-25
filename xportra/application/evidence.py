"""Evidence recording use cases (upload/record boundary).

``EvidenceApplicationService`` wraps the authoritative,
persistence-backed ``ComplianceEvidenceService`` so the
workflow journey can record evidence artifacts before
handing references to the workflow (use case 3 in the
inventory). Recording registers the artifact and its
optional requirement links; it never interprets,
chunks, embeds, or assesses anything.

The evidence service is injected (production wiring
supplies the database-backed instance); this layer
holds no I/O of its own. Returned DTOs carry artifact
identity only — never document contents.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from xportra.domain.errors import (
    DomainNotFoundError,
    DomainPersistenceError,
    DomainValidationError,
)

from ._guards import (
    checked_context,
    checked_uuid,
    ensure_tenant_match,
)
from .context import ApplicationContext
from .dtos import EvidenceRecordDTO
from .errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
    InfrastructureError,
    sanitized_detail,
)


class EvidenceApplicationService:
    """Stateless evidence recording use cases."""

    def __init__(self, *, evidence_service: Any) -> None:
        if not callable(getattr(evidence_service, "record", None)):
            raise ApplicationValidationError(
                "an evidence service is required")
        if not callable(getattr(evidence_service, "get", None)):
            raise ApplicationValidationError(
                "an evidence service is required")
        self._evidence = evidence_service

    def record_evidence(
        self,
        ctx: ApplicationContext,
        *,
        document_title: str,
        document_type: str,
        file_reference_or_uri: str,
        requirement_ids: (
            list[UUID] | tuple[UUID, ...]) = (),
        source_id: UUID | None = None,
        content_hash: str | None = None,
        status: str = "uploaded",
    ) -> EvidenceRecordDTO:
        """Record an evidence artifact (and optional links)."""
        ctx = checked_context(ctx)
        for field, value in (
                ("document title", document_title),
                ("document type", document_type),
                ("file reference", file_reference_or_uri),
                ("status", status)):
            if not isinstance(value, str) or not value.strip():
                raise ApplicationValidationError(
                    f"a non-empty {field} is required")
        checked_requirements = _checked_optional_uuids(
            requirement_ids, "requirement")
        if source_id is not None:
            checked_uuid(source_id, "source")
        if content_hash is not None and not isinstance(
                content_hash, str):
            raise ApplicationValidationError(
                "malformed content hash")
        try:
            if checked_requirements:
                row = self._evidence.record_with_requirements(
                    ctx.tenant,
                    document_title.strip(),
                    document_type.strip(),
                    file_reference_or_uri.strip(),
                    checked_requirements,
                    source_id=source_id,
                    content_hash=content_hash,
                    status=status.strip(),
                )
            else:
                row = self._evidence.record(
                    ctx.tenant,
                    document_title.strip(),
                    document_type.strip(),
                    file_reference_or_uri.strip(),
                    source_id=source_id,
                    content_hash=content_hash,
                    status=status.strip(),
                )
        except DomainNotFoundError as cause:
            raise ApplicationNotFoundError(
                str(cause), cause=cause) from cause
        except DomainValidationError as cause:
            raise ApplicationValidationError(
                str(cause), cause=cause) from cause
        except DomainPersistenceError as cause:
            raise InfrastructureError(
                sanitized_detail(cause), cause=cause) from cause
        return EvidenceRecordDTO.from_record(_checked_row(row))

    def get_evidence(
        self,
        ctx: ApplicationContext,
        evidence_id: UUID,
    ) -> EvidenceRecordDTO:
        """Read a recorded evidence artifact by identity."""
        ctx = checked_context(ctx)
        checked_uuid(evidence_id, "evidence")
        try:
            row = self._evidence.get(ctx.tenant, evidence_id)
        except DomainValidationError as cause:
            raise ApplicationValidationError(
                str(cause), cause=cause) from cause
        except DomainPersistenceError as cause:
            raise InfrastructureError(
                sanitized_detail(cause), cause=cause) from cause
        if row is None:
            raise ApplicationNotFoundError(
                "evidence was not found")
        row = _checked_row(row)
        tenant_id = row.get("tenant_id")
        if not isinstance(tenant_id, UUID):
            raise ApplicationValidationError(
                "malformed evidence tenant identity")
        ensure_tenant_match(ctx, tenant_id, "evidence")
        return EvidenceRecordDTO.from_record(row)


def _checked_optional_uuids(values: Any,
                            field: str) -> list[UUID]:
    if values is None:
        return []
    if not isinstance(values, (list, tuple)):
        raise ApplicationValidationError(
            f"malformed {field} identities")
    for value in values:
        checked_uuid(value, field)
    return list(values)


def _checked_row(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ApplicationValidationError(
            "malformed evidence record")
    return row


__all__ = [
    "EvidenceApplicationService",
]
