"""Regulatory source intake: source registration, artifact upload,
and durable ingestion job creation.

All mutations require an active ``GRANT_MANAGE`` global staff grant.
Original artifacts are stored in the private regulatory-source bucket
and remain immutable; ingestion jobs are durable and start in ``pending``
state for the background worker to claim.

Storage is uploaded before the database transaction. If the database
transaction fails after storage succeeds, the object remains in storage
as an orphan and is not claimed as a successful registration — safe
failure evidence is preserved and no deletion is attempted.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
    InfrastructureError,
)
from xportra.application.global_staff import GlobalStaffGrantService, GRANT_MANAGE
from xportra.application.regulatory_ingestion_service import RegulatoryIngestionService
from xportra.persistence.database import Database
from xportra.persistence.repositories import (
    AuthorityRepository,
    RegulatoryIngestionJobRepository,
    RegulatoryRequirementRepository,
    RegulatoryReviewFlagRepository,
    RegulatorySourceArtifactRepository,
    RegulatorySourceRepository,
)

MAX_ARTIFACT_CONTENT_BYTES = 10 * 1024 * 1024  # 10 MB
ACCEPTED_ARTIFACT_CONTENT_TYPES = frozenset({
    "text/plain", "text/markdown", "application/json",
})
VALID_SOURCE_STATUSES = frozenset({
    "draft", "active", "superseded", "withdrawn", "archived",
})


class RegulatorySourceIntakeService:
    """Application boundary for regulatory source intake."""

    def __init__(
        self,
        database: Database,
        *,
        source_repo: RegulatorySourceRepository | None = None,
        artifact_repo: RegulatorySourceArtifactRepository | None = None,
        job_repo: RegulatoryIngestionJobRepository | None = None,
        authority_repo: AuthorityRepository | None = None,
        grant_service: GlobalStaffGrantService | None = None,
        requirement_repo: RegulatoryRequirementRepository | None = None,
        review_flag_repo: RegulatoryReviewFlagRepository | None = None,
        storage_service: RegulatorySourceStorageApplicationService | None = None,
        ingestion_service: RegulatoryIngestionService | None = None,
    ) -> None:
        self._database = database
        self._source_repo = source_repo or RegulatorySourceRepository(database)
        self._artifact_repo = artifact_repo or RegulatorySourceArtifactRepository(database)
        self._job_repo = job_repo or RegulatoryIngestionJobRepository(database)
        self._authority_repo = authority_repo or AuthorityRepository(database)
        self._grant_service = grant_service or GlobalStaffGrantService(database)
        self._requirement_repo = requirement_repo or RegulatoryRequirementRepository(database)
        self._flag_repo = review_flag_repo or RegulatoryReviewFlagRepository(database)
        if storage_service is not None:
            self._storage = storage_service
        else:
            from xportra.application.regulatory_artifact_storage_service import (
                RegulatorySourceStorageApplicationService,
            )
            self._storage = RegulatorySourceStorageApplicationService(
                grant_service=self._grant_service,
            )
        self._ingestion = ingestion_service or RegulatoryIngestionService(database)

    # ---------------------------------------------------------------- queries

    def get_source(self, source_id: UUID) -> dict[str, Any] | None:
        return self._source_repo.get(source_id)

    def list_sources(self) -> list[dict[str, Any]]:
        """List all registered regulatory sources (administration view).

        Read-only display of stored rows, including supersession
        relationships as recorded — no inferred supersession.
        """
        return [dict(row) for row in self._source_repo.list_all()]

    def list_artifacts(self, source_id: UUID) -> list[dict[str, Any]]:
        return self._artifact_repo.list_for_source(source_id)

    def get_job(self, job_id: UUID) -> dict[str, Any] | None:
        return self._job_repo.get(job_id)

    def list_jobs(self, source_id: UUID) -> list[dict[str, Any]]:
        return self._job_repo.list_for_source(source_id)

    # ---------------------------------------------------------------- mutations

    def _require_grant(self, actor_user_id: UUID | None) -> None:
        from xportra.api.errors import PermissionDeniedError

        if actor_user_id is None:
            raise PermissionDeniedError()
        if not self._grant_service.is_granted(actor_user_id, GRANT_MANAGE):
            raise PermissionDeniedError()

    def register_source(
        self,
        actor_user_id: UUID,
        authority_id: UUID,
        jurisdiction: str,
        title: str,
        version: str | None = None,
        status: str = "draft",
        effective_date: Any | None = None,
        publication_date: Any | None = None,
        source_url: str | None = None,
    ) -> dict[str, Any]:
        self._require_grant(actor_user_id)
        if status not in VALID_SOURCE_STATUSES:
            raise ApplicationValidationError(f"invalid source status: {status}")
        authority = self._authority_repo.get(authority_id)
        if authority is None:
            raise ApplicationNotFoundError("authority not found")
        source_row = self._source_repo.create(
            authority_id=authority_id,
            jurisdiction=jurisdiction,
            title=title,
            version=version,
            status=status,
            effective_date=effective_date,
            publication_date=publication_date,
            source_url=source_url,
        )
        # Create the pending ingestion job per Phase 4D.10 (Task 3B contract).
        job_row = self._job_repo.create(
            artifact_id=None,
            source_id=source_row["id"],
            actor_user_id=actor_user_id,
            parser_version="v1",
            status="pending",
        )
        return {
            "id": source_row["id"],
            "source_id": source_row["id"],
            "authority_id": source_row.get("authority_id"),
            "jurisdiction": source_row.get("jurisdiction"),
            "title": source_row.get("title"),
            "version": source_row.get("version"),
            "status": source_row.get("status"),
            "effective_date": source_row.get("effective_date"),
            "publication_date": source_row.get("publication_date"),
            "source_url": source_row.get("source_url"),
            "supersedes_source_id": source_row.get("supersedes_source_id"),
            "superseded_by_source_id": source_row.get("superseded_by_source_id"),
            "updated_at": source_row.get("updated_at"),
            "pending_ingestion_job_id": job_row["id"],
        }

    def record_supersession(
        self,
        actor_user_id: UUID,
        source_id: UUID,
        supersedes_source_id: UUID,
        rationale: str,
    ) -> dict[str, Any]:
        """Record that ``source_id`` supersedes ``supersedes_source_id``.

        Requires an active ``GRANT_MANAGE`` grant. Validates that both
        sources exist, rejects self-supersession, and prevents cycles and
        duplicate supersession links. Updates both source rows atomically
        and creates pending governance flags for every requirement linked
        to the superseded source.
        """
        self._require_grant(actor_user_id)
        if not rationale or not rationale.strip():
            raise ApplicationValidationError("rationale is required")

        source = self._source_repo.get(source_id)
        if source is None:
            raise ApplicationNotFoundError("source not found")
        superseded_source = self._source_repo.get(supersedes_source_id)
        if superseded_source is None:
            raise ApplicationNotFoundError("superseded source not found")
        if source_id == supersedes_source_id:
            raise ApplicationValidationError("self-supersession is not permitted")
        if source.get("supersedes_source_id") is not None:
            raise ApplicationValidationError(
                "source already supersedes another source"
            )
        if superseded_source.get("superseded_by_source_id") is not None:
            raise ApplicationValidationError(
                "superseded source is already superseded by another source"
            )
        if superseded_source.get("superseded_by_source_id") == source_id:
            raise ApplicationValidationError(
                "cycle detected: superseded source already points back to this source"
            )
        if superseded_source.get("status") == "superseded":
            raise ApplicationValidationError(
                "superseded source is already superseded"
            )

        # Indirect-cycle prevention: traverse supersession graph from supersedes_source_id
        # (the superseded source) through existing supersession links. If any path
        # reaches source_id, then making source_id supersede supersedes_source_id
        # would create a cycle (supersedes_source_id -> ... -> source_id -> supersedes_source_id).
        visited: set[UUID] = set()
        current: UUID | None = supersedes_source_id
        while current is not None:
            if current == source_id:
                raise ApplicationValidationError(
                    "indirect supersession cycle detected"
                )
            if current in visited:
                break
            visited.add(current)
            src_row = self._source_repo.get(current)
            current = src_row.get("supersedes_source_id") if src_row else None

        now = datetime.now(timezone.utc)
        requirements = self._requirement_repo.list_for_source(supersedes_source_id)
        with self._database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s)::bigint)",
                    (f"regulatory_supersession_{source_id}:{supersedes_source_id}",),
                )
            self._source_repo.update_source_in_transaction(
                connection,
                source_id,
                supersedes_source_id=supersedes_source_id,
            )
            self._source_repo.update_source_in_transaction(
                connection,
                supersedes_source_id,
                superseded_by_source_id=source_id,
                status="superseded",
            )
            for req in requirements:
                self._flag_repo.create_in_transaction(
                    connection,
                    requirement_id=req["id"],
                    trigger_source_id=supersedes_source_id,
                    trigger_type="supersession",
                    actor_user_id=actor_user_id,
                    rationale=rationale.strip(),
                )

        updated = self._source_repo.get(source_id)
        return {
            "id": updated["id"],
            "source_id": updated["id"],
            "supersedes_source_id": updated.get("supersedes_source_id"),
            "superseded_by_source_id": updated.get("superseded_by_source_id"),
            "status": updated.get("status"),
            "updated_at": updated.get("updated_at"),
        }

    def upload_artifact(
        self,
        actor_user_id: UUID,
        source_id: UUID,
        content_base64: str,
        content_type: str,
        source_version: str | None = None,
    ) -> dict[str, Any]:
        """Upload an original artifact and create a durable pending job.

        Idempotent: identical content for the same source returns the
        existing artifact and its latest job without creating duplicates.
        Concurrent duplicate uploads are serialized by an advisory lock.
        """
        self._require_grant(actor_user_id)
        content = self._decode_content(content_base64)
        if len(content) > MAX_ARTIFACT_CONTENT_BYTES:
            raise ApplicationValidationError("artifact exceeds size limit")
        mime_type = (content_type or "").strip().lower()
        if mime_type not in ACCEPTED_ARTIFACT_CONTENT_TYPES:
            if mime_type == "application/pdf":
                raise ApplicationValidationError(
                    "PDF artifacts are not supported in this release"
                )
            raise ApplicationValidationError(
                f"unsupported artifact content type: {content_type}"
            )
        content_hash = hashlib.sha256(content).hexdigest()
        source = self._source_repo.get(source_id)
        if source is None:
            raise ApplicationNotFoundError("regulatory source not found")
        key = f"regulatory-source-artifacts/{source_id}/{content_hash}"
        try:
            self._storage.upload_artifact(
                key, content, content_type=mime_type,
                actor_user_id=actor_user_id,
            )
        except Exception as exc:  # noqa: BLE001
            raise InfrastructureError("artifact storage unavailable") from exc
        with self._database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s)::bigint)",
                    (f"regulatory_artifact_{source_id}:{content_hash}",),
                )
            existing = self._artifact_repo.list_for_source(source_id)
            for artifact in existing:
                if artifact.get("content_hash") == content_hash:
                    jobs = self._job_repo.list_for_artifact(artifact["id"])
                    latest_job = jobs[0] if jobs else None
                    return {
                        "artifact": artifact,
                        "job": latest_job,
                        "duplicate": True,
                    }
            artifact_row = self._artifact_repo.create(
                source_id=source_id,
                artifact_uri=key,
                content_hash=content_hash,
                content_length=len(content),
                content_type=mime_type,
                acquisition_channel="manual_upload",
                acquired_by=str(actor_user_id),
                acquired_at=datetime.now(timezone.utc),
                status="validated",
                source_version=source_version,
            )
            job_row = self._job_repo.create(
                artifact_id=artifact_row["id"],
                source_id=source_id,
                actor_user_id=actor_user_id,
                parser_version="v1",
            )
        return {
            "artifact": artifact_row,
            "job": job_row,
            "duplicate": False,
        }

    @staticmethod
    def _decode_content(content_base64: str) -> bytes:
        from xportra.api.errors import APIError

        try:
            return base64.b64decode(content_base64, validate=True)
        except (binascii.Error, ValueError) as cause:
            raise APIError(
                422, "malformed_upload_content",
                "Artifact content must be valid base64",
            ) from cause
