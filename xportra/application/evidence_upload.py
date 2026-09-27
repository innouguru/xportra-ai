"""Evidence file-upload use cases (Phase 10.4, R-10.4).

``EvidenceUploadApplicationService`` owns the minimum
production-safe upload path:

```text
terminal-workflow pre-check (before any mutation)
    ↓ availability pre-checks (storage/indexing, before any mutation)
    ↓ file validation (10 MB, MVP types, magic bytes)
    ↓ content-hash idempotency (same tenant → same row)
    ↓ server-generated evidence identity + object key
    ↓ private Storage put
    ↓ database registration (compensating delete on failure)
    ↓ optional requirement association (link absent on failure)
    ↓ processing: parse → corpus ingest → index sync
    ↓ ready | failed (failed never reads as ready)
```

Reuse, never replacement: text extraction adapters are
new (stdlib-only, per U1), but normalization follows
the existing loss-minimizing convention, corpus
persistence goes through the existing
``EvidenceDocumentIngestionService`` (Phase 4.1),
chunking/embedding/indexing through the injected
index-sync boundary (Phases 4.2–4.5), and requirement
satisfaction still requires the Phase 2.6 rule —
uploads arrive with review status ``uploaded`` and can
never satisfy anything by themselves
(``uploaded ≠ ready ≠ sufficient ≠ satisfied``).

Tenant safety is deterministic comparison, never
message parsing: every row read is re-checked against
the context tenant, and content-hash idempotency is
scoped per tenant (cross-tenant identical hashes stay
independent). Terminal workflows (``is_closed``) are
rejected before any storage or database mutation, and
unwired storage/indexing fails closed with
``InfrastructureError`` before any mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from xportra.domain.compliance_workflow import WORKFLOW_TERMINAL_STATES
from xportra.domain.errors import (
    DomainError,
    DomainNotFoundError,
    DomainPersistenceError,
    DomainValidationError,
    VectorStoreError,
)
from xportra.domain.evidence_storage import (
    DEFAULT_DOWNLOAD_URL_TTL_SECONDS,
    EVIDENCE_STORAGE_BUCKET,
    EvidenceStorageError,
)
from xportra.domain.evidence_upload import (
    PROCESSING_FAILED,
    PROCESSING_PROCESSING,
    PROCESSING_READY,
    PROCESSING_UPLOADED,
    EvidenceFileTooLargeError as DomainFileTooLargeError,
    EvidenceFileValidationError as DomainFileValidationError,
    compose_object_key,
    extract_upload_text,
    validate_upload_file,
)

from ._guards import (
    checked_context,
    checked_uuid,
    ensure_tenant_match,
    workflow_from_record,
)
from .context import ApplicationContext
from .errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
    EvidenceUploadTooLargeError,
    InfrastructureError,
    TerminalWorkflowError,
    sanitized_detail,
)


@dataclass(frozen=True, slots=True)
class EvidenceUploadDTO:
    """One uploaded evidence file: identifiers + lifecycle state.

    Never carries file bytes, document text, storage
    internals beyond the owning bucket name, or signed
    URLs.
    """

    evidence_id: str
    tenant_id: str
    document_title: str | None
    document_type: str | None
    status: str | None
    processing_status: str | None
    processing_step: str | None
    processing_error: str | None
    content_hash: str | None
    original_filename: str | None
    mime_type: str | None
    duplicate: bool
    linked_requirement_ids: tuple[str, ...]

    @classmethod
    def from_row(
        cls,
        row: dict[str, Any],
        *,
        duplicate: bool,
        linked_requirement_ids: tuple[str, ...] = (),
    ) -> "EvidenceUploadDTO":
        if not isinstance(row, dict):
            raise ApplicationValidationError("malformed evidence record")
        try:
            evidence_id = str(UUID(str(row.get("id"))))
            tenant_id = str(UUID(str(row.get("tenant_id"))))
        except (ValueError, TypeError, AttributeError) as cause:
            raise ApplicationValidationError(
                "malformed evidence identity") from cause
        return cls(
            evidence_id=evidence_id,
            tenant_id=tenant_id,
            document_title=row.get("document_title"),
            document_type=row.get("document_type"),
            status=row.get("status"),
            processing_status=row.get("processing_status",
                                      PROCESSING_UPLOADED),
            processing_step=row.get("processing_step"),
            processing_error=row.get("processing_error"),
            content_hash=row.get("content_hash"),
            original_filename=row.get("original_filename"),
            mime_type=row.get("mime_type"),
            duplicate=bool(duplicate),
            linked_requirement_ids=tuple(linked_requirement_ids),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "tenant_id": self.tenant_id,
            "document_title": self.document_title,
            "document_type": self.document_type,
            "status": self.status,
            "processing_status": self.processing_status,
            "processing_step": self.processing_step,
            "processing_error": self.processing_error,
            "content_hash": self.content_hash,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "duplicate": self.duplicate,
            "linked_requirement_ids": list(self.linked_requirement_ids),
        }


@dataclass(frozen=True, slots=True)
class EvidenceDownloadDTO:
    """Authorized download grant: identifiers + one signed URL."""

    evidence_id: str
    tenant_id: str
    download_url: str
    expires_in_seconds: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "tenant_id": self.tenant_id,
            "download_url": self.download_url,
            "expires_in_seconds": self.expires_in_seconds,
        }


class EvidenceUploadApplicationService:
    """Stateless evidence file-upload use cases."""

    def __init__(
        self,
        *,
        evidence_service: Any,
        corpus_ingestion: Any,
        index_sync: Any,
        storage: Any,
        clock=None,
        evidence_ids=None,
    ) -> None:
        for name, service, methods in (
            ("evidence", evidence_service, (
                "register_upload", "find_by_content_hash",
                "set_processing_state", "get",
                "associate_requirement")),
            ("corpus ingestion", corpus_ingestion, ("ingest",)),
            ("index synchronization", index_sync, ("sync",)),
            ("object storage", storage, (
                "put", "delete", "create_signed_url")),
        ):
            if service is None or any(
                    not callable(getattr(service, m, None))
                    for m in methods):
                raise ApplicationValidationError(
                    f"an upload {name} service is required")
        self._evidence = evidence_service
        self._corpus = corpus_ingestion
        self._sync = index_sync
        self._storage = storage
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._evidence_ids = evidence_ids or uuid4

    def upload_evidence(
        self,
        ctx: ApplicationContext,
        *,
        filename: Any,
        content_type: Any,
        content: Any,
        document_title: Any = None,
        document_type: Any = None,
        requirement_ids: Any = (),
        workflow_record: Any = None,
    ) -> EvidenceUploadDTO:
        """Upload, register, and process one evidence file."""
        ctx = checked_context(ctx)
        checked_requirements = _checked_requirement_ids(requirement_ids)
        self._require_workflow_open(ctx, workflow_record)

        try:
            validated = validate_upload_file(
                filename=filename,
                content_type=content_type,
                content=content,
            )
        except DomainFileTooLargeError as cause:
            raise EvidenceUploadTooLargeError(
                str(cause), cause=cause) from cause
        except DomainFileValidationError as cause:
            raise ApplicationValidationError(
                str(cause), cause=cause) from cause

        title = _optional_text(document_title, "document title")
        kind_label = validated.detected_kind
        document_type_text = _optional_text(document_type, "document type")
        resolved_title = title or validated.original_filename
        resolved_type = document_type_text or kind_label

        existing = self._find_existing(ctx, validated.content_hash)
        if existing is not None:
            ensure_tenant_match(
                ctx, _row_tenant(existing), "evidence")
            linked = self._link_requirements(
                ctx, _row_id(existing), checked_requirements)
            if existing.get("processing_status") == PROCESSING_READY:
                return EvidenceUploadDTO.from_row(
                    existing, duplicate=True,
                    linked_requirement_ids=linked)
            row = self._run_processing(
                ctx, existing, bytes(content), validated)
            return EvidenceUploadDTO.from_row(
                row, duplicate=True,
                linked_requirement_ids=linked)

        evidence_id = self._evidence_ids()
        if not isinstance(evidence_id, UUID):
            raise ApplicationValidationError(
                "malformed evidence identity")
        try:
            object_key = compose_object_key(
                tenant_id=ctx.tenant_id,
                evidence_id=evidence_id,
                content_hash=validated.content_hash,
                extension=validated.extension,
            )
        except DomainValidationError as cause:
            raise ApplicationValidationError(
                str(cause), cause=cause) from cause

        try:
            self._storage.put(
                object_key, bytes(content),
                content_type=validated.content_type)
        except EvidenceStorageError as cause:
            raise InfrastructureError(
                sanitized_detail(cause), cause=cause) from cause

        try:
            row = self._evidence.register_upload(
                ctx.tenant,
                evidence_id=evidence_id,
                document_title=resolved_title,
                document_type=resolved_type,
                file_reference_or_uri=object_key,
                content_hash=validated.content_hash,
                original_filename=validated.original_filename,
                mime_type=validated.content_type,
                storage_bucket=EVIDENCE_STORAGE_BUCKET,
                uploaded_by=ctx.actor_id,
            )
        except DomainValidationError as cause:
            self._compensate_put(object_key)
            raise ApplicationValidationError(
                str(cause), cause=cause) from cause
        except (DomainPersistenceError, DomainNotFoundError) as cause:
            self._compensate_put(object_key)
            raise InfrastructureError(
                sanitized_detail(cause), cause=cause) from cause

        linked = self._link_requirements(
            ctx, evidence_id, checked_requirements)
        row = self._run_processing(
            ctx, row, bytes(content), validated)
        return EvidenceUploadDTO.from_row(
            row, duplicate=False,
            linked_requirement_ids=linked)

    def get_download(
        self,
        ctx: ApplicationContext,
        evidence_id: UUID,
    ) -> EvidenceDownloadDTO:
        """Issue a short-lived download URL after authorization.

        The requesting actor's tenant and the evidence
        ownership are verified first (U4); cross-tenant
        lookups fail closed without revealing existence.
        """
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
            raise ApplicationNotFoundError("evidence was not found")
        if not isinstance(row, dict):
            raise ApplicationValidationError("malformed evidence record")
        ensure_tenant_match(ctx, _row_tenant(row), "evidence")
        object_key = row.get("file_reference_or_uri")
        if not isinstance(object_key, str) or not object_key.strip():
            raise ApplicationNotFoundError(
                "evidence file is not available for download")
        try:
            url = self._storage.create_signed_url(
                object_key.strip(),
                expires_in_seconds=DEFAULT_DOWNLOAD_URL_TTL_SECONDS,
            )
        except EvidenceStorageError as cause:
            raise InfrastructureError(
                sanitized_detail(cause), cause=cause) from cause
        if not isinstance(url, str) or not url.strip():
            raise InfrastructureError("evidence download is unavailable")
        return EvidenceDownloadDTO(
            evidence_id=str(evidence_id),
            tenant_id=str(ctx.tenant_id),
            download_url=url.strip(),
            expires_in_seconds=DEFAULT_DOWNLOAD_URL_TTL_SECONDS,
        )

    # -- orchestration internals -------------------------------

    def _require_workflow_open(
        self, ctx: ApplicationContext, workflow_record: Any
    ) -> None:
        if workflow_record is None:
            return
        workflow = workflow_from_record(workflow_record)
        ensure_tenant_match(ctx, workflow.tenant_id, "workflow")
        if workflow.state in WORKFLOW_TERMINAL_STATES:
            raise TerminalWorkflowError(
                "workflow is permanently closed to new evidence")

    def _find_existing(
        self, ctx: ApplicationContext, content_hash: str
    ) -> dict[str, Any] | None:
        try:
            row = self._evidence.find_by_content_hash(
                ctx.tenant, content_hash)
        except DomainValidationError as cause:
            raise ApplicationValidationError(
                str(cause), cause=cause) from cause
        except DomainPersistenceError as cause:
            raise InfrastructureError(
                sanitized_detail(cause), cause=cause) from cause
        if row is not None and not isinstance(row, dict):
            raise ApplicationValidationError("malformed evidence record")
        return row

    def _link_requirements(
        self,
        ctx: ApplicationContext,
        evidence_id: UUID,
        requirement_ids: list[UUID],
    ) -> tuple[str, ...]:
        """Link requested requirements; absent links stay absent.

        A missing requirement leaves the record in place
        with the link absent (never a silent satisfaction:
        links alone satisfy nothing without accepted
        status plus assessment).
        """
        linked: list[str] = []
        for requirement_id in requirement_ids:
            try:
                self._evidence.associate_requirement(
                    ctx.tenant, evidence_id, requirement_id)
            except DomainNotFoundError:
                continue
            except DomainPersistenceError as cause:
                raise InfrastructureError(
                    sanitized_detail(cause), cause=cause) from cause
            linked.append(str(requirement_id))
        return tuple(linked)

    def _run_processing(
        self,
        ctx: ApplicationContext,
        row: dict[str, Any],
        content: bytes,
        validated,
    ) -> dict[str, Any]:
        evidence_id = _row_id(row)
        row = self._set_state(
            ctx, evidence_id, PROCESSING_PROCESSING)
        try:
            text = extract_upload_text(validated.detected_kind, content)
        except DomainError as cause:
            return self._set_state(
                ctx, evidence_id, PROCESSING_FAILED,
                step="parse", error=_failure_code(cause, "parse"))
        try:
            corpus_record = self._corpus.ingest(
                {
                    "tenant_id": ctx.tenant_id,
                    "source_id": (
                        f"tenant-evidence:{evidence_id.hex}"),
                    "source_type": "other",
                    "source_location": row.get("file_reference_or_uri"),
                    "title": row.get("document_title"),
                    "content": text,
                    "document_version": validated.content_hash,
                    "metadata": {
                        "evidence_id": str(evidence_id),
                        "content_hash": validated.content_hash,
                        "original_filename":
                            validated.original_filename,
                        "mime_type": validated.content_type,
                    },
                },
                tenant_id=ctx.tenant,
            )
        except DomainError as cause:
            return self._set_state(
                ctx, evidence_id, PROCESSING_FAILED,
                step="ingest", error=_failure_code(cause, "ingest"))
        try:
            self._sync.sync(corpus_record, tenant_id=ctx.tenant)
        except (VectorStoreError, EvidenceStorageError,
                DomainPersistenceError) as cause:
            self._set_state(
                ctx, evidence_id, PROCESSING_FAILED,
                step="sync", error=_failure_code(cause, "sync"))
            raise InfrastructureError(
                sanitized_detail(cause), cause=cause) from cause
        except DomainError as cause:
            self._set_state(
                ctx, evidence_id, PROCESSING_FAILED,
                step="sync", error=_failure_code(cause, "sync"))
            raise InfrastructureError(
                sanitized_detail(cause), cause=cause) from cause
        return self._set_state(
            ctx, evidence_id, PROCESSING_READY, step="complete")

    def _set_state(
        self,
        ctx: ApplicationContext,
        evidence_id: UUID,
        status: str,
        *,
        step: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        try:
            row = self._evidence.set_processing_state(
                ctx.tenant,
                evidence_id,
                processing_status=status,
                processing_step=step,
                processing_error=error,
                processed_at=self._clock(),
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
        if not isinstance(row, dict):
            raise ApplicationValidationError("malformed evidence record")
        return row

    def _compensate_put(self, object_key: str) -> None:
        try:
            self._storage.delete(object_key)
        except Exception:
            pass


def _checked_requirement_ids(values: Any) -> list[UUID]:
    if values is None:
        return []
    if not isinstance(values, (list, tuple)):
        raise ApplicationValidationError(
            "malformed requirement identities")
    for value in values:
        checked_uuid(value, "requirement")
    return list(values)


def _optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ApplicationValidationError(
            f"a non-empty {field} is required")
    return value.strip()


def _row_tenant(row: dict[str, Any]) -> UUID:
    tenant_id = row.get("tenant_id")
    if not isinstance(tenant_id, UUID):
        raise ApplicationValidationError(
            "malformed evidence tenant identity")
    return tenant_id


def _row_id(row: dict[str, Any]) -> UUID:
    evidence_id = row.get("id")
    if not isinstance(evidence_id, UUID):
        raise ApplicationValidationError("malformed evidence identity")
    return evidence_id


def _failure_code(cause: BaseException, step: str) -> str:
    """Static step code for processing failures (no internals)."""
    name = type(cause).__name__
    short = "".join(
        ch for ch in name if ch.isalnum() or ch in ("_", "-"))[:64]
    return f"{step}_failed:{short}" if short else f"{step}_failed"


__all__ = [
    "EvidenceDownloadDTO",
    "EvidenceUploadApplicationService",
    "EvidenceUploadDTO",
]
