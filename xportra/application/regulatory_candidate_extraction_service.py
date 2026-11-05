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

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from xportra.application.errors import (
    ApplicationError,
    ApplicationNotFoundError,
    ApplicationValidationError,
    InfrastructureError,
)
from xportra.application.global_staff import GlobalStaffGrantService, GRANT_MANAGE
from xportra.application.regulatory_ingestion_service import (
    MAX_RETRY_ATTEMPTS,
    RegulatoryIngestionService,
)
from xportra.domain.ingestion import (
    ArtifactNormalizationService,
    ArtifactParseError,
    ArtifactParsingService,
    RegulatoryMetadataExtractionService,
    RegulatoryRequirementExtractionService,
    RegulatoryRequirementExtractionResult,
)
from xportra.domain.llm import LLMClient, LLMGenerationConfig
from xportra.persistence.database import Database
from xportra.persistence.errors import PersistenceIntegrityError
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
logger = logging.getLogger(__name__)


class IngestionClaimLostError(RuntimeError):
    """Raised when a worker no longer owns the ingestion-job claim."""


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
        candidate_service: Any | None = None,
        llm_client: LLMClient | None = None,
        llm_configuration: LLMGenerationConfig | None = None,
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
            self._requirement_repo,
            llm_client=llm_client,
            configuration=llm_configuration,
        )

    # ---------------------------------------------------------------- queries

    def get_candidate(self, candidate_id: UUID) -> dict[str, Any] | None:
        return self._requirement_repo.get(candidate_id)

    def get_candidate_with_provenance(self, candidate_id: UUID) -> dict[str, Any] | None:
        """Return a candidate with source, artifact, and ingestion-job provenance.

        Enables a reviewer to trace candidate text back to the source,
        artifact, and extraction run.
        """
        candidate = self._requirement_repo.get_with_provenance(candidate_id)
        if candidate is not None:
            candidate["extraction_history"] = (
                self._requirement_repo.list_extraction_runs_for_candidate(
                    candidate_id
                )
            )
        return candidate

    def get_job(self, job_id: UUID) -> dict[str, Any] | None:
        return self._job_repo.get(job_id)

    def get_job_extraction_history(
        self, job_id: UUID
    ) -> dict[str, Any] | None:
        """Return persisted extraction outcomes and snapshots for one job."""
        if self._job_repo.get(job_id) is None:
            return None

        runs: list[dict[str, Any]] = []
        run_by_id: dict[UUID, dict[str, Any]] = {}
        for row in self._requirement_repo.list_extraction_runs_for_job(job_id):
            run_id = row["extraction_run_id"]
            run = run_by_id.get(run_id)
            if run is None:
                run = {
                    "extraction_run_id": run_id,
                    "normalized_document_id": row["normalized_document_id"],
                    "artifact_id": row["artifact_id"],
                    "source_id": row["source_id"],
                    "ingestion_job_id": row["ingestion_job_id"],
                    "artifact_content_hash": row["artifact_content_hash"],
                    "artifact_source_version": row["artifact_source_version"],
                    "normalized_text_sha256": row["normalized_text_sha256"],
                    "parser_version": row["parser_version"],
                    "extraction_method": row["extraction_method"],
                    "extraction_version": row["extraction_version"],
                    "prompt_version": row["prompt_version"],
                    "configured_model_identifier": (
                        row["configured_model_identifier"]
                    ),
                    "model_identifiers": row["model_identifiers"],
                    "provider_names": row["provider_names"],
                    "outcome": row["outcome"],
                    "failed_chunks": row["failed_chunks"],
                    "rejected_candidate_count": (
                        row["rejected_candidate_count"]
                    ),
                    "started_at": row["started_at"],
                    "completed_at": row["completed_at"],
                    "candidate_count": 0,
                    "persisted_candidate_count": 0,
                    "candidates": [],
                }
                run_by_id[run_id] = run
                runs.append(run)

            if row["candidate_index"] is None:
                continue
            run["candidate_count"] += 1
            if row["candidate_id"] is not None:
                run["persisted_candidate_count"] += 1
            run["candidates"].append(
                {
                    "candidate_index": row["candidate_index"],
                    "candidate_id": row["candidate_id"],
                    "evidence_snapshot": row["evidence_snapshot"],
                    "resolution_status": row["resolution_status"],
                    "is_origin": row["is_origin"],
                }
            )

        return {"job_id": job_id, "items": runs}

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

    def _update_job_stage(
        self,
        job_id: UUID,
        current_stage: str,
        claim_started_at: datetime,
    ) -> None:
        """Persist the current processing stage and its timestamp."""
        updated = self._job_repo.update_stage(
            job_id,
            current_stage,
            datetime.now(timezone.utc),
            claim_started_at,
        )
        if updated is None:
            raise IngestionClaimLostError(
                f"claim for ingestion job {job_id} is no longer owned"
            )

    def _candidate_has_completed_extraction(
        self, candidate: dict[str, Any]
    ) -> bool:
        if (
            candidate.get("extraction_outcome")
            != EXTRACTION_OUTCOME_SUCCEEDED
            or candidate.get("ingestion_job_id") is None
        ):
            return False
        prior_job = self._job_repo.get(candidate["ingestion_job_id"])
        return prior_job is not None and prior_job.get("status") == "completed"

    @classmethod
    def _json_compatible(cls, value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {
                str(key): cls._json_compatible(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [cls._json_compatible(item) for item in value]
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        raise TypeError(
            f"unsupported extraction evidence value: {type(value).__name__}"
        )

    def _record_extraction_run(
        self,
        *,
        extraction: RegulatoryRequirementExtractionResult,
        extraction_run_id: UUID,
        normalization: dict[str, Any],
        artifact: dict[str, Any],
        job_id: UUID,
        parser_version: str,
        started_at: datetime,
        completed_at: datetime,
    ) -> None:
        normalized_text = normalization.get("normalized_text")
        if not isinstance(normalized_text, str):
            raise InfrastructureError(
                "normalized source text is unavailable for provenance"
            )
        self._requirement_repo.create_extraction_run(
            id=extraction_run_id,
            normalized_document_id=normalization["id"],
            artifact_id=artifact["id"],
            source_id=artifact["source_id"],
            ingestion_job_id=job_id,
            artifact_content_hash=artifact["content_hash"],
            artifact_source_version=artifact.get("source_version"),
            normalized_text_sha256=hashlib.sha256(
                normalized_text.encode("utf-8")
            ).hexdigest(),
            parser_version=parser_version,
            extraction_method=extraction.extraction_method,
            extraction_version=extraction.extraction_version,
            prompt_version=extraction.prompt_version,
            configured_model_identifier=(
                extraction.configured_model_identifier
            ),
            model_identifiers=list(extraction.model_identifiers),
            provider_names=list(extraction.provider_names),
            outcome=extraction.outcome,
            failed_chunks=[
                self._json_compatible(dict(chunk))
                for chunk in extraction.failed_chunks
            ],
            rejected_candidate_count=extraction.rejected_candidate_count,
            started_at=started_at,
            completed_at=completed_at,
        )

    def extract_candidates(
        self,
        actor_user_id: UUID,
        source_id: UUID,
        artifact_id: UUID,
        job_id: UUID,
        *,
        claim_started_at: datetime | None = None,
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
        if not getattr(self._candidate_extractor, "is_configured", True):
            raise InfrastructureError(
                "semantic regulatory requirement extraction is not configured"
            )

        claim = None
        extraction_run_id: UUID | None = None
        pending_run_candidate_indices: set[int] = set()
        if claim_started_at is None:
            claim = self._ingestion.claim_job(
                job_id, actor_user_id=actor_user_id
            )
            if claim is None:
                job = self._job_repo.get(job_id)
                if job is None:
                    raise ApplicationNotFoundError("ingestion job not found")
                if job.get("status") == "completed":
                    normalization = self._normalization_repo.get_by_artifact(
                        artifact_id
                    )
                    candidates = (
                        self._requirement_repo.list_for_document(
                            normalization["id"]
                        )
                        if normalization is not None
                        else []
                    )
                    return {
                        "outcome": EXTRACTION_OUTCOME_SUCCEEDED,
                        "candidate_count": len(candidates),
                        "candidates": candidates,
                        "job": job,
                        "duplicate": True,
                        "normalization_id": (
                            normalization["id"]
                            if normalization is not None
                            else None
                        ),
                    }
                raise ApplicationValidationError(
                    f"ingestion job status is '{job.get('status')}'; "
                    "the job is not claimable"
                )
            claim_started_at = claim.get("started_at")
        else:
            claim = self._job_repo.get(job_id)

        if (
            claim is None
            or claim.get("status") not in ("claimed", "processing")
            or claim.get("started_at") != claim_started_at
        ):
            raise IngestionClaimLostError(
                f"claim for ingestion job {job_id} is no longer owned"
            )

        stage = "retrieving_artifact"
        try:
            existing_normalization = self._normalization_repo.get_by_artifact(
                artifact_id
            )
            content_type = "text/plain"
            content: bytes | None = None
            if existing_normalization is None:
                self._update_job_stage(
                    job_id, stage, claim_started_at
                )
                artifact = self._artifact_repo.get(artifact_id)
                if artifact is None:
                    raise ApplicationNotFoundError(
                        "regulatory artifact not found"
                    )
                source = self._source_repo.get(source_id)
                current_job = self._job_repo.get(job_id)
                if source is None:
                    raise ApplicationNotFoundError(
                        "regulatory source not found"
                    )
                if artifact.get("source_id") != source_id:
                    raise ApplicationNotFoundError(
                        "regulatory artifact not found"
                    )
                if (
                    current_job is None
                    or current_job.get("artifact_id") != artifact_id
                    or current_job.get("source_id") != source_id
                ):
                    raise ApplicationNotFoundError(
                        "ingestion job not found"
                    )
                if (
                    current_job.get("status") not in ("claimed", "processing")
                    or current_job.get("started_at") != claim_started_at
                ):
                    raise IngestionClaimLostError(
                        f"claim for ingestion job {job_id} is no longer owned"
                    )
                content_type = artifact.get("content_type", "text/plain")
                content = self._storage.get_artifact(
                    artifact.get("artifact_uri"),
                    actor_user_id=actor_user_id,
                )
                if content is None:
                    raise ApplicationNotFoundError(
                        "artifact object not found in storage"
                    )

            stage = "validating_document"
            self._update_job_stage(
                job_id, stage, claim_started_at
            )
            source = self._source_repo.get(source_id)
            artifact = self._artifact_repo.get(artifact_id)
            current_job = self._job_repo.get(job_id)
            if source is None:
                raise ApplicationNotFoundError("regulatory source not found")
            if artifact is None or artifact.get("source_id") != source_id:
                raise ApplicationNotFoundError("regulatory artifact not found")
            if (
                current_job is None
                or current_job.get("artifact_id") != artifact_id
                or current_job.get("source_id") != source_id
            ):
                raise ApplicationNotFoundError("ingestion job not found")
            if (
                current_job.get("status") not in ("claimed", "processing")
                or current_job.get("started_at") != claim_started_at
            ):
                raise IngestionClaimLostError(
                    f"claim for ingestion job {job_id} is no longer owned"
                )

            normalization = existing_normalization
            if normalization is None:
                stage = "extracting_text"
                self._update_job_stage(
                    job_id, stage, claim_started_at
                )
                try:
                    parsed = self._parser.parse(
                        artifact_id=artifact_id,
                        content_type=content_type,
                        raw_content=content,
                    )
                except ArtifactParseError:
                    raise
                normalized_text = parsed.get("normalized_text", "") or ""
                if not normalized_text.strip():
                    raise ArtifactParseError(
                        "extraction produced no usable text"
                    )

                stage = "normalizing_content"
                self._update_job_stage(
                    job_id, stage, claim_started_at
                )
                normalization = self._normalizer.normalize(
                    artifact_id=artifact_id,
                    source_id=source_id,
                    content_type=content_type,
                    raw_content=content,
                    parser_name=parsed.get("parser_name", PARSER_VERSION),
                )
                try:
                    self._metadata_extractor.extract(normalization)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "Metadata extraction for ingestion job %s failed (%s).",
                        job_id,
                        type(exc).__name__,
                    )

            prior_candidates = self._requirement_repo.list_for_document(
                normalization["id"]
            )
            if prior_candidates and all(
                self._candidate_has_completed_extraction(candidate)
                for candidate in prior_candidates
            ):
                self._update_job_stage(
                    job_id, "completed", claim_started_at
                )
                completed_job = self._ingestion.complete_job(
                    job_id,
                    actor_user_id=actor_user_id,
                    claim_started_at=claim_started_at,
                )
                if completed_job is None:
                    raise IngestionClaimLostError(
                        f"claim for ingestion job {job_id} is no longer owned"
                    )
                return {
                    "outcome": EXTRACTION_OUTCOME_SUCCEEDED,
                    "candidate_count": len(prior_candidates),
                    "candidates": prior_candidates,
                    "job": completed_job,
                    "failed_chunks": [],
                    "rejected_candidate_count": 0,
                    "no_qualifying_requirements": False,
                    "duplicate": True,
                    "normalization_id": normalization["id"],
                }

            stage = "extracting_requirements"
            self._update_job_stage(
                job_id, stage, claim_started_at
            )
            extraction_started_at = datetime.now(timezone.utc)
            try:
                extraction = self._candidate_extractor.extract(
                    normalization
                )
            except Exception as exc:
                extraction_completed_at = datetime.now(timezone.utc)
                failed_extraction = RegulatoryRequirementExtractionResult(
                    candidates=(),
                    outcome=EXTRACTION_OUTCOME_FAILED,
                    failed_chunks=({
                        "reason": "extraction_invocation_failed",
                        "error_type": type(exc).__name__,
                    },),
                    extraction_method=getattr(
                        self._candidate_extractor,
                        "EXTRACTION_METHOD",
                        "custom_extractor",
                    ),
                    extraction_version=getattr(
                        self._candidate_extractor,
                        "EXTRACTION_VERSION",
                        "unknown",
                    ),
                    prompt_version=getattr(
                        self._candidate_extractor,
                        "PROMPT_VERSION",
                        None,
                    ),
                    configured_model_identifier=getattr(
                        self._candidate_extractor,
                        "configured_model_identifier",
                        None,
                    ),
                )
                extraction_run_id = uuid4()
                self._record_extraction_run(
                    extraction=failed_extraction,
                    extraction_run_id=extraction_run_id,
                    normalization=normalization,
                    artifact=artifact,
                    job_id=job_id,
                    parser_version=(
                        current_job.get("parser_version") or PARSER_VERSION
                    ),
                    started_at=extraction_started_at,
                    completed_at=extraction_completed_at,
                )
                raise
            extraction_completed_at = datetime.now(timezone.utc)
            if isinstance(extraction, RegulatoryRequirementExtractionResult):
                candidate_records = list(extraction.candidates)
                extraction_outcome = extraction.outcome
                failed_chunks = list(extraction.failed_chunks)
                rejected_candidate_count = (
                    extraction.rejected_candidate_count
                )
            else:
                candidate_records = extraction
                extraction_outcome = EXTRACTION_OUTCOME_SUCCEEDED
                failed_chunks = []
                rejected_candidate_count = 0
                extraction = RegulatoryRequirementExtractionResult(
                    candidates=tuple(candidate_records),
                    outcome=extraction_outcome,
                    extraction_method="custom_extractor",
                    extraction_version="unknown",
                    prompt_version=None,
                )
            extraction_run_id = uuid4()
            self._record_extraction_run(
                extraction=extraction,
                extraction_run_id=extraction_run_id,
                normalization=normalization,
                artifact=artifact,
                job_id=job_id,
                parser_version=(
                    current_job.get("parser_version") or PARSER_VERSION
                ),
                started_at=extraction_started_at,
                completed_at=extraction_completed_at,
            )
            if extraction_outcome == EXTRACTION_OUTCOME_FAILED:
                failed_job = self._mark_job_failed(
                    job_id,
                    actor_user_id,
                    claim_started_at,
                    claim,
                    "semantic requirement extraction failed for all chunks",
                )
                candidates = self._requirement_repo.list_for_document(
                    normalization["id"]
                )
                return {
                    "outcome": EXTRACTION_OUTCOME_FAILED,
                    "candidate_count": len(candidates),
                    "candidates": candidates,
                    "job": failed_job,
                    "failed_chunks": failed_chunks,
                    "rejected_candidate_count": rejected_candidate_count,
                    "no_qualifying_requirements": False,
                    "duplicate": False,
                    "normalization_id": normalization["id"],
                }

            stage = "saving_candidates"
            self._update_job_stage(
                job_id, stage, claim_started_at
            )
            existing_candidates = self._requirement_repo.list_for_document(
                normalization["id"]
            )
            existing_positions = {
                candidate.get("position"): candidate
                for candidate in existing_candidates
            }
            existing_quotes: dict[str, dict[str, Any]] = {}
            for candidate in existing_candidates:
                location = candidate.get("source_location")
                quote = (
                    location.get("supporting_quote")
                    if isinstance(location, dict)
                    else None
                )
                if not isinstance(quote, str) or not quote:
                    quote = candidate.get("requirement_text")
                if isinstance(quote, str) and quote:
                    existing_quotes[quote] = candidate
            next_position = max(
                (
                    position for position in existing_positions
                    if isinstance(position, int)
                ),
                default=-1,
            ) + 1
            for candidate_index, record in enumerate(candidate_records):
                evidence_snapshot = self._json_compatible(record)
                self._requirement_repo.create_extraction_run_candidate(
                    extraction_run_id=extraction_run_id,
                    normalized_document_id=normalization["id"],
                    candidate_index=candidate_index,
                    evidence_snapshot=evidence_snapshot,
                )
                pending_run_candidate_indices.add(candidate_index)
                location = record.get("source_location")
                quote = (
                    location.get("supporting_quote")
                    if isinstance(location, dict)
                    else None
                )
                if not isinstance(quote, str) or not quote:
                    quote = record.get("requirement_text")
                existing = existing_quotes.get(quote)
                if existing is not None:
                    if (
                        extraction_outcome == EXTRACTION_OUTCOME_SUCCEEDED
                        and existing.get("extraction_outcome")
                        == EXTRACTION_OUTCOME_PARTIAL
                    ):
                        self._requirement_repo.mark_extraction_succeeded(
                            existing["id"]
                        )
                    resolved = (
                        self._requirement_repo.resolve_extraction_run_candidate(
                            extraction_run_id=extraction_run_id,
                            candidate_index=candidate_index,
                            candidate_id=existing["id"],
                            resolution_status="reused",
                        )
                    )
                    if resolved is None:
                        raise InfrastructureError(
                            "extraction evidence could not be linked to its candidate"
                        )
                    pending_run_candidate_indices.remove(candidate_index)
                    continue
                if record.get("position") in existing_positions:
                    record["position"] = next_position
                    next_position += 1
                record["normalized_document_id"] = normalization["id"]
                record["source_id"] = source_id
                record["ingestion_job_id"] = job_id
                record["extraction_outcome"] = extraction_outcome
                record["parser_version"] = PARSER_VERSION
                record["manual_entry"] = False
                record["status"] = "extracted"
                try:
                    persisted = (
                        self._requirement_repo
                        .create_with_extraction_run_candidate(
                            extraction_run_id=extraction_run_id,
                            candidate_index=candidate_index,
                            values=record,
                        )
                    )
                except PersistenceIntegrityError as exc:
                    if self._is_duplicate_candidate_position(exc):
                        duplicate_candidates = (
                            self._requirement_repo.list_for_document(
                                normalization["id"]
                            )
                        )
                        duplicate = next(
                            (
                                candidate
                                for candidate in duplicate_candidates
                                if self._candidate_quote(candidate) == quote
                            ),
                            None,
                        )
                        if duplicate is not None:
                            resolved = (
                                self._requirement_repo
                                .resolve_extraction_run_candidate(
                                    extraction_run_id=extraction_run_id,
                                    candidate_index=candidate_index,
                                    candidate_id=duplicate["id"],
                                    resolution_status="reused",
                                )
                            )
                            if resolved is None:
                                raise InfrastructureError(
                                    "extraction evidence could not be linked to its candidate"
                                )
                            pending_run_candidate_indices.remove(
                                candidate_index
                            )
                            continue
                    raise
                pending_run_candidate_indices.remove(candidate_index)
                existing_positions[record["position"]] = record
                if isinstance(quote, str) and quote:
                    existing_quotes[quote] = record

            candidates = self._requirement_repo.list_for_document(
                normalization["id"]
            )
            if extraction_outcome == EXTRACTION_OUTCOME_PARTIAL:
                failed_job = self._mark_job_failed(
                    job_id,
                    actor_user_id,
                    claim_started_at,
                    claim,
                    "semantic requirement extraction was partial",
                )
                return {
                    "outcome": EXTRACTION_OUTCOME_PARTIAL,
                    "candidate_count": len(candidates),
                    "candidates": candidates,
                    "job": failed_job,
                    "failed_chunks": failed_chunks,
                    "rejected_candidate_count": rejected_candidate_count,
                    "no_qualifying_requirements": False,
                    "duplicate": False,
                    "normalization_id": normalization["id"],
                }
            completed_job = self._ingestion.complete_job(
                job_id,
                actor_user_id=actor_user_id,
                claim_started_at=claim_started_at,
            )
            if completed_job is None:
                raise IngestionClaimLostError(
                    f"claim for ingestion job {job_id} is no longer owned"
                )

            return {
                "outcome": EXTRACTION_OUTCOME_SUCCEEDED,
                "candidate_count": len(candidates),
                "candidates": candidates,
                "job": completed_job,
                "failed_chunks": failed_chunks,
                "rejected_candidate_count": rejected_candidate_count,
                "no_qualifying_requirements": not candidate_records,
                "duplicate": bool(existing_normalization is not None),
                "normalization_id": normalization["id"],
            }
        except IngestionClaimLostError:
            raise
        except ArtifactParseError as exc:
            failed_job = self._mark_job_failed(
                job_id,
                actor_user_id,
                claim_started_at,
                claim,
                f"{stage} failed: {exc}",
            )
            return {
                "outcome": EXTRACTION_OUTCOME_FAILED,
                "candidate_count": 0,
                "candidates": [],
                "job": failed_job,
                "error": str(exc),
                "duplicate": False,
            }
        except ApplicationError:
            if extraction_run_id is not None:
                for candidate_index in sorted(
                    pending_run_candidate_indices
                ):
                    self._requirement_repo.resolve_extraction_run_candidate(
                        extraction_run_id=extraction_run_id,
                        candidate_index=candidate_index,
                        candidate_id=None,
                        resolution_status="persistence_failed",
                    )
            self._mark_job_failed(
                job_id,
                actor_user_id,
                claim_started_at,
                claim,
                f"{stage} failed",
            )
            raise
        except Exception as exc:  # noqa: BLE001
            if extraction_run_id is not None:
                for candidate_index in sorted(
                    pending_run_candidate_indices
                ):
                    self._requirement_repo.resolve_extraction_run_candidate(
                        extraction_run_id=extraction_run_id,
                        candidate_index=candidate_index,
                        candidate_id=None,
                        resolution_status="persistence_failed",
                    )
            self._mark_job_failed(
                job_id,
                actor_user_id,
                claim_started_at,
                claim,
                f"{stage} failed: {type(exc).__name__}",
            )
            if stage == "normalizing_content":
                raise InfrastructureError("normalization failed") from exc
            if stage == "extracting_requirements":
                raise InfrastructureError(
                    "candidate extraction failed"
                ) from exc
            if stage == "saving_candidates":
                raise InfrastructureError(
                    "candidate persistence failed"
                ) from exc
            if stage == "retrieving_artifact":
                raise InfrastructureError(
                    "artifact storage read unavailable"
                ) from exc
            raise InfrastructureError(
                "regulatory candidate extraction failed"
            ) from exc

    @staticmethod
    def _candidate_quote(candidate: dict[str, Any]) -> str | None:
        location = candidate.get("source_location")
        quote = (
            location.get("supporting_quote")
            if isinstance(location, dict)
            else None
        )
        return quote if isinstance(quote, str) and quote else candidate.get(
            "requirement_text"
        )

    @staticmethod
    def _is_duplicate_candidate_position(
        error: PersistenceIntegrityError,
    ) -> bool:
        cause = error.cause
        diagnostic = getattr(cause, "diag", None)
        return (
            getattr(cause, "sqlstate", None) == "23505"
            and getattr(
                diagnostic, "constraint_name", None
            ) == "regulatory_requirements_document_position_key"
        )

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
        claim_started_at: datetime,
        claimed_job: dict[str, Any],
        error_details: str,
    ) -> dict[str, Any]:
        # Bounded retries: a persistently failing attempt stays retryable
        # up to MAX_RETRY_ATTEMPTS retryable-failure cycles (tracked by
        # the durable retry_count column); after the bound the failure is
        # terminal and only an authorized staff retry control can record
        # a new attempt. Prior attempts remain immutable history.
        retry_count = int(claimed_job.get("retry_count") or 0)
        make_retryable = retry_count < MAX_RETRY_ATTEMPTS
        failed_job = self._ingestion.fail_job(
            job_id,
            error_details=error_details,
            make_retryable=make_retryable,
            actor_user_id=actor_user_id,
            claim_started_at=claim_started_at,
        )
        if failed_job is None:
            raise IngestionClaimLostError(
                f"claim for ingestion job {job_id} is no longer owned"
            )
        return failed_job

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
