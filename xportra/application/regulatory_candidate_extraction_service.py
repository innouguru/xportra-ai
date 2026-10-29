"""Regulatory candidate extraction: turn ingested artifacts into
reviewable candidate requirements with full provenance.

This service is the candidate-generation boundary of Phase 4D.10 Task 4.
It reads original artifact bytes from private storage, runs the existing
parsing/normalization/extraction pipeline, and persists candidates with
extraction outcome and provenance. It never publishes or approves
requirements — candidates remain unreviewed until Stage A verification
and Stage B applicability approval.

Candidates are created only from content actually extracted from the
artifact, or explicitly entered by an authorized reviewer (manual entry
recovery path). Failed or partial extraction is recorded explicitly and
never represented as success.
"""
from __future__ import annotations

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
from xportra.domain.ingestion import (
    ArtifactNormalizationService,
    ArtifactParseError,
    ArtifactParsingService,
    RegulatoryMetadataExtractionService,
    RegulatoryRequirementExtractionService,
)
from xportra.persistence.database import Database
from xportra.persistence.repositories import (
    RegulatoryDocumentMetadataRepository,
    RegulatoryDocumentNormalizationRepository,
    RegulatoryIngestionJobRepository,
    RegulatoryRequirementRepository,
    RegulatorySourceArtifactRepository,
    RegulatorySourceRepository,
)

EXTRACTION_OUTCOME_SUCCEEDED = "succeeded"
EXTRACTION_OUTCOME_PARTIAL = "partial"
EXTRACTION_OUTCOME_FAILED = "failed"
EXTRACTION_OUTCOME_MANUAL = "manual"

PARSER_VERSION = "v1"


class RegulatoryCandidateExtractionService:
    """Application boundary for regulatory candidate extraction."""

    def __init__(
        self,
        database: Database,
        *,
        source_repo: RegulatorySourceRepository | None = None,
        artifact_repo: RegulatorySourceArtifactRepository | None = None,
        job_repo: RegulatoryIngestionJobRepository | None = None,
        requirement_repo: RegulatoryRequirementRepository | None = None,
        normalization_repo: RegulatoryDocumentNormalizationRepository | None = None,
        metadata_repo: RegulatoryDocumentMetadataRepository | None = None,
        grant_service: GlobalStaffGrantService | None = None,
        storage_service: RegulatorySourceStorageApplicationService | None = None,
        ingestion_service: RegulatoryIngestionService | None = None,
        parser_service: ArtifactParsingService | None = None,
        normalization_service: ArtifactNormalizationService | None = None,
        metadata_service: RegulatoryMetadataExtractionService | None = None,
        candidate_service: RegulatoryRequirementExtractionService | None = None,
    ) -> None:
        self._database = database
        self._source_repo = source_repo or RegulatorySourceRepository(database)
        self._artifact_repo = artifact_repo or RegulatorySourceArtifactRepository(database)
        self._job_repo = job_repo or RegulatoryIngestionJobRepository(database)
        self._requirement_repo = requirement_repo or RegulatoryRequirementRepository(database)
        self._normalization_repo = normalization_repo or RegulatoryDocumentNormalizationRepository(database)
        self._metadata_repo = metadata_repo or RegulatoryDocumentMetadataRepository(database)
        self._grant_service = grant_service or GlobalStaffGrantService(database)
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
        self._parser = parser_service or ArtifactParsingService()
        self._normalizer = normalization_service or ArtifactNormalizationService(
            self._normalization_repo
        )
        self._metadata_extractor = metadata_service or RegulatoryMetadataExtractionService(
            self._metadata_repo
        )
        self._candidate_extractor = candidate_service or RegulatoryRequirementExtractionService(
            self._requirement_repo
        )

    # ---------------------------------------------------------------- queries

    def get_candidate(self, candidate_id: UUID) -> dict[str, Any] | None:
        return self._requirement_repo.get(candidate_id)

    def get_candidate_with_provenance(self, candidate_id: UUID) -> dict[str, Any] | None:
        """Return a candidate with source, artifact, and ingestion-job provenance.

        Enables a reviewer to trace candidate text back to the source,
        artifact, and extraction run.
        """
        return self._requirement_repo.get_with_provenance(candidate_id)

    def get_job(self, job_id: UUID) -> dict[str, Any] | None:
        return self._job_repo.get(job_id)

    def list_artifacts_for_source(
        self, source_id: UUID
    ) -> list[dict[str, Any]]:
        return self._artifact_repo.list_for_source(source_id)

    def list_candidates_for_artifact(
        self, artifact_id: UUID
    ) -> list[dict[str, Any]]:
        # The normalization repository links artifact -> normalized document.
        normalization = self._normalization_repo.get_by_artifact(artifact_id)
        if normalization is None:
            return []
        return self._requirement_repo.list_for_document(normalization["id"])

    # ---------------------------------------------------------------- authorization

    def _require_grant(self, actor_user_id: UUID | None) -> None:
        from xportra.api.errors import PermissionDeniedError

        if actor_user_id is None:
            raise PermissionDeniedError()
        if not self._grant_service.is_granted(actor_user_id, GRANT_MANAGE):
            raise PermissionDeniedError()

    # ---------------------------------------------------------------- extraction

    def extract_candidates(
        self,
        actor_user_id: UUID,
        source_id: UUID,
        artifact_id: UUID,
        job_id: UUID,
    ) -> dict[str, Any]:
        """Extract candidate requirements from an ingested artifact.

        Reads the original artifact bytes from private storage, runs the
        parsing/normalization/extraction pipeline, and persists candidates
        with extraction outcome and provenance. Idempotent: re-extraction
        of the same artifact returns existing candidates without creating
        duplicates.

        Returns a result dict with ``outcome`` (succeeded/partial/failed),
        ``candidate_count``, ``candidates``, and ``job`` status.
        """
        self._require_grant(actor_user_id)

        # Verify source, artifact, and job exist and are linked.
        source = self._source_repo.get(source_id)
        if source is None:
            raise ApplicationNotFoundError("regulatory source not found")
        artifact = self._artifact_repo.get(artifact_id)
        if artifact is None or artifact.get("source_id") != source_id:
            raise ApplicationNotFoundError("regulatory artifact not found")
        job = self._job_repo.get(job_id)
        if job is None or job.get("artifact_id") != artifact_id:
            raise ApplicationNotFoundError("ingestion job not found")

        # Idempotency: if candidates already exist for this artifact's
        # normalized document, return them without re-extracting.
        existing_normalization = self._normalization_repo.get_by_artifact(artifact_id)
        if existing_normalization is not None:
            existing = self._requirement_repo.list_for_document(
                existing_normalization["id"]
            )
            if existing:
                return {
                    "outcome": EXTRACTION_OUTCOME_SUCCEEDED,
                    "candidate_count": len(existing),
                    "candidates": existing,
                    "job": job,
                    "duplicate": True,
                    "normalization_id": existing_normalization["id"],
                }

        # Read original artifact bytes from private storage.
        artifact_uri = artifact.get("artifact_uri")
        content_type = artifact.get("content_type", "text/plain")
        try:
            content = self._storage.get_artifact(
                artifact_uri, actor_user_id=actor_user_id
            )
        except Exception as exc:  # noqa: BLE001
            self._mark_job_failed(
                job_id, actor_user_id, f"storage read failed: {type(exc).__name__}"
            )
            raise InfrastructureError("artifact storage read unavailable") from exc
        if content is None:
            self._mark_job_failed(
                job_id,
                actor_user_id,
                "artifact object not found in storage",
            )
            raise ApplicationNotFoundError("artifact object not found in storage")

        # Parse the artifact into a normalized document representation.
        try:
            parsed = self._parser.parse(
                artifact_id=artifact_id,
                content_type=content_type,
                raw_content=content,
            )
        except ArtifactParseError as exc:
            # Extraction failed: no usable content. Record failure, preserve
            # original evidence, do not create candidates.
            self._mark_job_failed(
                job_id, actor_user_id, f"extraction failed: {exc}"
            )
            return {
                "outcome": EXTRACTION_OUTCOME_FAILED,
                "candidate_count": 0,
                "candidates": [],
                "job": job,
                "error": str(exc),
                "duplicate": False,
            }

        normalized_text = parsed.get("normalized_text", "") or ""
        if not normalized_text.strip():
            # Parsed but empty: treat as failed (no usable content).
            self._mark_job_failed(
                job_id, actor_user_id, "extraction produced no usable text"
            )
            return {
                "outcome": EXTRACTION_OUTCOME_FAILED,
                "candidate_count": 0,
                "candidates": [],
                "job": job,
                "error": "extraction produced no usable text",
                "duplicate": False,
            }

        # Normalize: persists a normalized document record (idempotent).
        try:
            normalization = self._normalizer.normalize(
                artifact_id=artifact_id,
                source_id=source_id,
                content_type=content_type,
                raw_content=content,
                parser_name=parsed.get("parser_name", PARSER_VERSION),
            )
        except Exception as exc:  # noqa: BLE001
            self._mark_job_failed(
                job_id, actor_user_id, f"normalization failed: {type(exc).__name__}"
            )
            raise InfrastructureError("normalization failed") from exc

        normalization_id = normalization["id"]

        # Extract metadata (optional, best-effort).
        try:
            self._metadata_extractor.extract(normalization)
        except Exception:
            # Metadata extraction is non-fatal; candidates can still proceed.
            pass

        # Extract candidate requirements from the normalized document.
        try:
            candidate_records = self._candidate_extractor.extract(normalization)
        except Exception as exc:  # noqa: BLE001
            self._mark_job_failed(
                job_id, actor_user_id, f"candidate extraction failed: {type(exc).__name__}"
            )
            raise InfrastructureError("candidate extraction failed") from exc

        # Persist candidates with provenance and extraction outcome.
        persisted: list[dict[str, Any]] = []
        for record in candidate_records:
            record["normalized_document_id"] = normalization_id
            record["source_id"] = source_id
            record["ingestion_job_id"] = job_id
            record["extraction_outcome"] = EXTRACTION_OUTCOME_SUCCEEDED
            record["parser_version"] = PARSER_VERSION
            record["manual_entry"] = False
            record["status"] = "extracted"
            try:
                row = self._requirement_repo.create(**record)
                persisted.append(row)
            except Exception:
                # Duplicate (same normalized_document_id + position) — skip,
                # preserves idempotency on retry.
                continue

        # Mark the job completed (claim first, per the job state machine).
        # claim_job returns None when another worker already claimed the
        # job; treat that as an idempotent no-op rather than completing
        # someone else's work.
        claimed = self._ingestion.claim_job(job_id, actor_user_id=actor_user_id)
        if claimed is None:
            job = self._job_repo.get(job_id)
            return {
                "outcome": EXTRACTION_OUTCOME_SUCCEEDED,
                "candidate_count": len(persisted),
                "candidates": persisted,
                "job": job,
                "duplicate": True,
                "normalization_id": normalization_id,
            }
        self._ingestion.complete_job(job_id, actor_user_id=actor_user_id)
        job = self._job_repo.get(job_id)

        return {
            "outcome": EXTRACTION_OUTCOME_SUCCEEDED,
            "candidate_count": len(persisted),
            "candidates": persisted,
            "job": job,
            "duplicate": False,
            "normalization_id": normalization_id,
        }

    def enter_manual_candidate(
        self,
        actor_user_id: UUID,
        source_id: UUID,
        artifact_id: UUID,
        requirement_text: str,
        requirement_type: str = "unknown",
        source_location: dict[str, Any] | None = None,
        position: int = 0,
        justification: str | None = None,
    ) -> dict[str, Any]:
        """Enter a candidate requirement manually (recovery path).

        Used when extraction failed or is partial. The candidate is marked
        ``manual_entry=True`` with reviewer attribution. It passes the same
        Stage A and Stage B gates as extracted candidates; manual entry
        cannot make failed/partial extraction appear successful.
        """
        self._require_grant(actor_user_id)

        source = self._source_repo.get(source_id)
        if source is None:
            raise ApplicationNotFoundError("regulatory source not found")
        artifact = self._artifact_repo.get(artifact_id)
        if artifact is None or artifact.get("source_id") != source_id:
            raise ApplicationNotFoundError("regulatory artifact not found")

        if not requirement_text or not requirement_text.strip():
            raise ApplicationValidationError("requirement_text is required")

        normalization = self._normalization_repo.get_by_artifact(artifact_id)
        if normalization is None:
            # Manual entry with no prior normalization: create a minimal
            # normalization record so the candidate has a provenance anchor.
            from uuid import NAMESPACE_URL, uuid5
            norm_id = uuid5(NAMESPACE_URL, f"{artifact_id}:{source_id}:manual")
            normalization = self._normalization_repo.create(
                id=norm_id,
                artifact_id=artifact_id,
                source_id=source_id,
                document_title="Manual entry",
                normalized_text=requirement_text.strip(),
                normalized_content={"mime_type": "text/plain", "structure": []},
                content_type="text/plain",
                parser_name="manual",
                normalized_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        normalization_id = normalization["id"]

        record = {
            "id": self._candidate_id(
                source_id, artifact_id, requirement_text, position
            ),
            "normalized_document_id": normalization_id,
            "artifact_id": artifact_id,
            "source_id": source_id,
            "requirement_text": requirement_text.strip(),
            "requirement_type": requirement_type,
            "source_location": source_location or {},
            "position": position,
            "actor": str(actor_user_id),
            "condition_metadata": None,
            "status": "extracted",
            "ingestion_job_id": None,
            "extraction_outcome": EXTRACTION_OUTCOME_MANUAL,
            "parser_version": None,
            "manual_entry": True,
            "reviewer_user_id": actor_user_id,
            "reviewed_at": datetime.now(timezone.utc),
        }
        row = self._requirement_repo.create(**record)
        return row

    # ---------------------------------------------------------------- internals

    def _mark_job_failed(
        self,
        job_id: UUID,
        actor_user_id: UUID,
        error_details: str,
    ) -> None:
        try:
            self._ingestion.fail_job(
                job_id,
                error_details=error_details,
                make_retryable=True,
                actor_user_id=actor_user_id,
            )
        except Exception:
            # Job status update is best-effort; the extraction outcome is
            # still returned to the caller.
            pass

    @staticmethod
    def _candidate_id(
        source_id: UUID,
        artifact_id: UUID,
        requirement_text: str,
        position: int,
    ) -> UUID:
        from uuid import NAMESPACE_URL, uuid5

        identity = f"{source_id}:{artifact_id}:{position}:{requirement_text.strip()}"
        return uuid5(NAMESPACE_URL, identity)
