"""Link a completed regulatory ingestion result to an EvidenceDocument.

Preserves provenance: source_id, artifact_id, content_hash,
parser_version, document_version. Does not imply publication
approval or regulatory eligibility — the EvidenceDocument status
remains independent of Stage A / Stage B governance.

Idempotency: uses EvidenceDocumentRepository.get_by_source_identity
with (tenant_id, source_id, document_version) derived from the
regulatory source and artifact version. Retries of the same job do
not create duplicate evidence documents.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
)
from xportra.application.global_staff import GlobalStaffGrantService, GRANT_MANAGE
from xportra.domain.evidence_corpus import EvidenceDocument
from xportra.persistence.database import Database
from xportra.persistence.repositories import (
    EvidenceDocumentRepository,
    RegulatoryDocumentNormalizationRepository,
    RegulatoryIngestionJobRepository,
    RegulatorySourceArtifactRepository,
    RegulatorySourceRepository,
)
from xportra.persistence.tenant import TenantContext


class RegulatoryIngestionEvidenceLinkService:
    """Narrow linkage service: completed ingestion job -> EvidenceDocument."""

    def __init__(
        self,
        database: Database,
        *,
        job_repo: RegulatoryIngestionJobRepository | None = None,
        artifact_repo: RegulatorySourceArtifactRepository | None = None,
        source_repo: RegulatorySourceRepository | None = None,
        normalization_repo: RegulatoryDocumentNormalizationRepository | None = None,
        evidence_doc_repo: EvidenceDocumentRepository | None = None,
        grant_service: GlobalStaffGrantService | None = None,
        storage_service: Any = None,
    ) -> None:
        self._database = database
        self._job_repo = job_repo or RegulatoryIngestionJobRepository(database)
        self._artifact_repo = artifact_repo or RegulatorySourceArtifactRepository(database)
        self._source_repo = source_repo or RegulatorySourceRepository(database)
        self._normalization_repo = normalization_repo or RegulatoryDocumentNormalizationRepository(database)
        self._evidence_doc_repo = evidence_doc_repo or EvidenceDocumentRepository(database)
        self._grant_service = grant_service or GlobalStaffGrantService(database)
        self._storage_service = storage_service

    def _require_grant(self, actor_user_id: UUID | None) -> None:
        from xportra.api.errors import PermissionDeniedError
        if actor_user_id is None:
            raise PermissionDeniedError()
        if not self._grant_service.is_granted(actor_user_id, GRANT_MANAGE):
            raise PermissionDeniedError()

    def link_ingestion_result_to_evidence_document(
        self,
        actor_user_id: UUID,
        job_id: UUID,
        tenant: TenantContext,
        *,
        metadata_extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Link a completed ingestion job to an EvidenceDocument.

        Idempotent: same (tenant, source, version) returns existing
        document without duplication. Retries safe: duplicate attempts
        with completed job return the same linked document record.
        """
        self._require_grant(actor_user_id)

        job = self._job_repo.get(job_id)
        if job is None:
            raise ApplicationNotFoundError("regulatory ingestion job not found")
        if job.get("status") != "completed":
            raise ApplicationValidationError(
                f"ingestion job is not completed (current status: {job.get('status')}); "
                "evidence linkage requires a completed ingestion result"
            )

        artifact = self._artifact_repo.get(job.get("artifact_id"))
        if artifact is None:
            raise ApplicationNotFoundError("regulatory artifact linked to job not found")
        source = self._source_repo.get(artifact.get("source_id"))
        if source is None:
            raise ApplicationNotFoundError("regulatory source linked to artifact not found")

        source_id_str = str(source.get("id", ""))
        artifact_version = artifact.get("source_version") or source.get("version") or ""
        version_str = (artifact_version or "").strip()

        # Idempotency: check existing evidence document for same source + version.
        existing = self._evidence_doc_repo.get_by_source_identity(
            tenant, source.get("id"), version_str or None
        )
        if existing:
            return dict(existing)

        # Prefer normalized text from ingestion pipeline (real linkage to processed content).
        normalization = self._normalization_repo.get_by_artifact(artifact.get("id"))
        if normalization:
            content = normalization.get("normalized_text", "") or ""
            title = normalization.get("document_title", source.get("title", "Regulatory artifact"))
        else:
            # Fallback: retrieve original bytes from private storage (requires storage service)
            # and decode to text. If storage service unavailable or retrieval fails,
            # fail closed — we do not fabricate content.
            artifact_uri = artifact.get("artifact_uri")
            if artifact_uri and self._storage_service is not None:
                try:
                    from xportra.application.regulatory_artifact_storage_service import RegulatorySourceStorageApplicationService
                    content_bytes = self._storage_service.get_artifact(
                        artifact_uri, actor_user_id=actor_user_id
                    )
                    content = content_bytes.decode("utf-8") if isinstance(content_bytes, bytes) else str(content_bytes)
                    title = source.get("title", "Regulatory artifact")
                except Exception as exc:
                    raise ApplicationValidationError(
                        "cannot retrieve artifact content for evidence linkage: storage unavailable"
                    ) from exc
            else:
                raise ApplicationValidationError(
                    "regulatory ingestion result is completed but no normalized document or artifact content is available for evidence linkage"
                )

        if not content or not content.strip():
            raise ApplicationValidationError(
                "linked regulatory content is empty; evidence document requires non-empty content"
            )

        document_version_for_stable = version_str or None
        evidence_document = EvidenceDocument.create(
            tenant=tenant,
            source_id=source_id_str,
            document_version=document_version_for_stable,
            title=str(title).strip() if title else "Regulatory artifact",
            content=content,
            source_type="regulation",
            status="active",
            metadata={
                "artifact_id": str(artifact.get("id")),
                "content_hash": artifact.get("content_hash"),
                "parser_version": job.get("parser_version", "v1"),
                "ingestion_job_id": str(job.get("id")),
                "source_version": artifact.get("source_version"),
                **(metadata_extra or {}),
            },
        )

        result_row = self._evidence_doc_repo.create(evidence_document.to_record())
        return dict(result_row)
