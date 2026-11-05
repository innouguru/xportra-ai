"""Unit tests for regulatory candidate extraction (Phase 4D.10 Task 4).

Tests the extraction service using fakes — no live database, no hosted
services. Covers successful extraction, failed/partial outcomes, manual
candidate entry with reviewer attribution, idempotency, format rejection,
and authorization denial.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from types import SimpleNamespace
from unittest import TestCase
from uuid import UUID

from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
    InfrastructureError,
)
from xportra.application.regulatory_candidate_extraction_service import (
    EXTRACTION_OUTCOME_FAILED,
    EXTRACTION_OUTCOME_MANUAL,
    EXTRACTION_OUTCOME_PARTIAL,
    EXTRACTION_OUTCOME_SUCCEEDED,
    RegulatoryCandidateExtractionService,
)
from xportra.api.errors import APIError, PermissionDeniedError
from xportra.domain.ingestion import (
    RegulatoryRequirementExtractionResult,
    RegulatoryRequirementExtractionService,
)
from xportra.domain.llm import LLMGenerationConfig, LLMResponse
from xportra.infrastructure.llm import ScriptedLLMClient
from xportra.persistence.database import Database
from xportra.persistence.errors import PersistenceIntegrityError

ACTOR = UUID("aaaaaaaa-0000-0000-0000-000000000001")
NON_GRANTED = UUID("bbbbbbbb-0000-0000-0000-000000000002")
SOURCE = UUID("dddddddd-0000-0000-0000-000000000004")
ARTIFACT = UUID("eeeeeeee-0000-0000-0000-000000000005")
JOB = UUID("ffffffff-0000-0000-0000-000000000006")
NORMALIZATION = UUID("11111111-0000-0000-0000-000000000100")
CANDIDATE = UUID("22222222-0000-0000-0000-000000000200")

CONTENT_TEXT = b"# Sesame Regulation\n\nShall be labeled with origin.\nShall not exceed 50 kg."
CONTENT_MARKDOWN = b"# Sesame Regulation\n\n- Shall be labeled.\n- Shall be inspected."
CONTENT_JSON = b'{"requirements": ["Shall be labeled", "Shall be inspected"]}'


class FakeDatabase(Database):
    """In-memory transaction double."""

    def __init__(self) -> None:
        super().__init__(  # type: ignore[arg-type]
            object(), connection_factory=object()
        )
        self.committed = False
        self.rolled_back = False

    @contextmanager
    def transaction(self):  # type: ignore[override]
        try:
            yield object()
            self.committed = True
        except Exception:
            self.rolled_back = True
            raise


class FakeGrantService:
    def __init__(self, granted: set[UUID] | None = None) -> None:
        self.granted = granted or set()

    def is_granted(self, user_id: UUID, permission: str) -> bool:
        return user_id in self.granted


class FakeSourceRepository:
    def __init__(self, existing: dict[UUID, dict] | None = None) -> None:
        self.sources = dict(existing or {})

    def get(self, source_id: UUID):
        return self.sources.get(source_id)


class FakeArtifactRepository:
    def __init__(self, existing: dict[UUID, dict] | None = None) -> None:
        self.artifacts = dict(existing or {})

    def get(self, artifact_id: UUID):
        return self.artifacts.get(artifact_id)


class FakeJobRepository:
    def __init__(self, existing: dict[UUID, dict] | None = None) -> None:
        self.jobs = dict(existing or {})
        self.completed_job_id: UUID | None = None
        self.claimed_job_id: UUID | None = None
        self.failed_job_id: UUID | None = None
        self.failed_error: str | None = None
        self.stage_history: list[str] = []
        self._claim_started_at = datetime(
            2026, 11, 4, tzinfo=timezone.utc
        )

    def get(self, job_id: UUID):
        return self.jobs.get(job_id)

    def claim(self, job_id):
        self.claimed_job_id = job_id
        job = self.jobs.get(job_id)
        if job is None or job.get("status") not in ("pending", "retryable"):
            return None
        self.jobs[job_id] = dict(job)
        self.jobs[job_id].update({
            "status": "claimed",
            "started_at": self._claim_started_at,
            "completed_at": None,
            "error_details": None,
            "current_stage": "queued",
        })
        return dict(self.jobs[job_id])

    def complete(self, job_id, claim_started_at=None):
        self.completed_job_id = job_id
        job = self.jobs.get(job_id)
        if (
            job is None
            or job.get("status") not in ("claimed", "processing")
            or job.get("started_at") != claim_started_at
        ):
            return None
        self.jobs[job_id] = dict(job)
        self.jobs[job_id].update({
            "status": "completed",
            "completed_at": self._claim_started_at,
            "current_stage": "completed",
        })
        self.stage_history.append("completed")
        return dict(self.jobs[job_id])

    def fail(
        self,
        job_id,
        error_details=None,
        make_retryable=False,
        claim_started_at=None,
    ):
        self.failed_job_id = job_id
        self.failed_error = error_details
        job = self.jobs.get(job_id)
        if (
            job is None
            or job.get("status") not in ("claimed", "processing")
            or job.get("started_at") != claim_started_at
        ):
            return None
        self.jobs[job_id] = dict(job)
        self.jobs[job_id].update({
            "status": "retryable" if make_retryable else "failed",
            "error_details": error_details,
            "completed_at": self._claim_started_at,
            "current_stage": "failed",
        })
        if make_retryable:
            self.jobs[job_id]["retry_count"] = (
                int(self.jobs[job_id].get("retry_count") or 0) + 1
            )
        self.stage_history.append("failed")
        return dict(self.jobs[job_id])

    def update_stage(
        self, job_id, current_stage, stage_updated_at,
        claim_started_at,
    ):
        job = self.jobs.get(job_id)
        if (
            job is None
            or job.get("status") not in ("claimed", "processing")
            or job.get("started_at") != claim_started_at
        ):
            return None
        self.jobs[job_id] = dict(job)
        self.jobs[job_id].update({
            "current_stage": current_stage,
            "stage_updated_at": stage_updated_at,
        })
        self.stage_history.append(current_stage)
        return dict(self.jobs[job_id])


class FakeNormalizationRepository:
    def __init__(self, existing: dict[UUID, dict] | None = None) -> None:
        self.normalizations = dict(existing or {})
        self.created: dict[UUID, dict] = {}

    def get_by_artifact(self, artifact_id: UUID):
        for norm in self.normalizations.values():
            if norm.get("artifact_id") == artifact_id:
                return norm
        return None

    def create(self, **kwargs):
        norm_id = kwargs.get("id", NORMALIZATION)
        row = {
            "id": norm_id,
            "artifact_id": kwargs["artifact_id"],
            "source_id": kwargs["source_id"],
            "document_title": kwargs["document_title"],
            "normalized_text": kwargs["normalized_text"],
            "normalized_content": kwargs["normalized_content"],
            "content_type": kwargs["content_type"],
            "parser_name": kwargs["parser_name"],
            "status": kwargs.get("status", "normalized"),
            "normalized_at": None,
            "created_at": None,
            "updated_at": None,
        }
        self.normalizations[norm_id] = row
        self.created[norm_id] = row
        return row


class FakeMetadataRepository:
    def __init__(self) -> None:
        self.created: list[dict] = []

    def extract(self, normalized_document):
        return {"normalized_document_id": normalized_document.get("id")}

    def process(self, normalized_document):
        return self.extract(normalized_document)


class FakeRequirementRepository:
    def __init__(self, existing: list[dict] | None = None) -> None:
        self.requirements: list[dict] = list(existing or [])
        self.created: list[dict] = []
        self.fail_create = False
        self.extraction_runs: list[dict] = []
        self.extraction_run_candidates: list[dict] = []

    def get(self, requirement_id: UUID):
        for r in self.requirements:
            if r["id"] == requirement_id:
                return r
        return None

    def list_for_document(self, normalized_document_id: UUID):
        return [
            r for r in self.requirements
            if r.get("normalized_document_id") == normalized_document_id
        ]

    def create(self, **kwargs):
        if self.fail_create:
            raise RuntimeError("simulated requirement insert failure")
        for existing in self.requirements:
            if (
                existing.get("normalized_document_id")
                == kwargs.get("normalized_document_id")
                and existing.get("position") == kwargs["position"]
            ):
                cause = SimpleNamespace(
                    sqlstate="23505",
                    diag=SimpleNamespace(
                        constraint_name=(
                            "regulatory_requirements_document_position_key"
                        )
                    ),
                )
                raise PersistenceIntegrityError(
                    "regulatory requirement creation", cause
                )
        req_id = kwargs.get("id", CANDIDATE)
        row = {
            "id": req_id,
            "normalized_document_id": kwargs.get("normalized_document_id"),
            "artifact_id": kwargs["artifact_id"],
            "source_id": kwargs["source_id"],
            "requirement_text": kwargs["requirement_text"],
            "requirement_type": kwargs["requirement_type"],
            "source_location": kwargs["source_location"],
            "position": kwargs["position"],
            "actor": kwargs.get("actor"),
            "condition_metadata": kwargs.get("condition_metadata"),
            "status": kwargs.get("status", "extracted"),
            "ingestion_job_id": kwargs.get("ingestion_job_id"),
            "extraction_outcome": kwargs.get("extraction_outcome", "succeeded"),
            "parser_version": kwargs.get("parser_version"),
            "manual_entry": kwargs.get("manual_entry", False),
            "reviewer_user_id": kwargs.get("reviewer_user_id"),
            "reviewed_at": kwargs.get("reviewed_at"),
            "created_at": None,
            "updated_at": None,
        }
        self.requirements.append(row)
        self.created.append(row)
        return row

    def create_with_extraction_run_candidate(
        self, *, extraction_run_id, candidate_index, values,
    ):
        candidate = self.create(**values)
        resolved = self.resolve_extraction_run_candidate(
            extraction_run_id=extraction_run_id,
            candidate_index=candidate_index,
            candidate_id=candidate["id"],
            resolution_status="persisted",
            is_origin=True,
        )
        if resolved is None:
            self.requirements.remove(candidate)
            self.created.remove(candidate)
            raise RuntimeError(
                "candidate evidence could not be resolved atomically"
            )
        return candidate

    def mark_extraction_succeeded(self, requirement_id):
        for requirement in self.requirements:
            if requirement["id"] == requirement_id:
                requirement["extraction_outcome"] = "succeeded"
                return requirement
        return None

    def create_extraction_run(self, **values):
        self.extraction_runs.append(dict(values))
        return dict(values)

    def create_extraction_run_candidate(
        self, *, extraction_run_id, normalized_document_id,
        candidate_index, evidence_snapshot,
    ):
        row = {
            "extraction_run_id": extraction_run_id,
            "normalized_document_id": normalized_document_id,
            "candidate_index": candidate_index,
            "evidence_snapshot": evidence_snapshot,
            "candidate_id": None,
            "resolution_status": "pending",
            "is_origin": False,
        }
        self.extraction_run_candidates.append(row)
        return row

    def resolve_extraction_run_candidate(
        self, *, extraction_run_id, candidate_index, candidate_id,
        resolution_status, is_origin=False,
    ):
        row = next(
            (
                item for item in self.extraction_run_candidates
                if item["extraction_run_id"] == extraction_run_id
                and item["candidate_index"] == candidate_index
            ),
            None,
        )
        if row is None or row["resolution_status"] != "pending":
            return None
        row["candidate_id"] = candidate_id
        row["resolution_status"] = resolution_status
        row["is_origin"] = is_origin
        return row

    def list_extraction_runs_for_candidate(self, requirement_id):
        return [
            {
                **run,
                **link,
            }
            for link in self.extraction_run_candidates
            if link["candidate_id"] == requirement_id
            for run in self.extraction_runs
            if run["id"] == link["extraction_run_id"]
        ]


class FakeParser:
    """Fake artifact parser: returns parsed content or raises."""

    def __init__(self, content_type: str = "text/plain", should_fail: bool = False,
                 should_return_empty: bool = False) -> None:
        self.content_type = content_type
        self.should_fail = should_fail
        self.should_return_empty = should_return_empty
        self.parse_calls: list[dict] = []

    def parse(self, *, artifact_id, content_type, raw_content):
        self.parse_calls.append(
            {"artifact_id": artifact_id, "content_type": content_type,
             "raw_content_len": len(raw_content) if isinstance(raw_content, bytes) else 0}
        )
        if self.should_fail:
            from xportra.domain.ingestion import ArtifactParseError
            raise ArtifactParseError("simulated parse failure")
        if self.should_return_empty:
            return {
                "artifact_id": artifact_id,
                "document_title": "Empty Doc",
                "normalized_text": "",
                "normalized_content": {"mime_type": content_type, "structure": []},
                "parser_name": "fake_parser",
                "status": "parsed",
            }
        return {
            "artifact_id": artifact_id,
            "document_title": "Test Document",
            "normalized_text": raw_content.decode("utf-8") if isinstance(raw_content, bytes) else str(raw_content),
            "normalized_content": {"mime_type": content_type, "structure": []},
            "parser_name": "fake_parser",
            "status": "parsed",
        }


class FakeNormalizer:
    """Fake normalizer: returns a normalization record."""

    def __init__(self, norm_id: UUID = NORMALIZATION, should_fail: bool = False) -> None:
        self.norm_id = norm_id
        self.should_fail = should_fail
        self.normalize_calls: list[dict] = []

    def normalize(self, *, artifact_id, source_id, content_type, raw_content,
                  parser_name=None, normalized_at=None):
        self.normalize_calls.append(
            {"artifact_id": artifact_id, "source_id": source_id,
             "content_type": content_type}
        )
        if self.should_fail:
            raise RuntimeError("simulated normalization failure")
        return {
            "id": self.norm_id,
            "artifact_id": artifact_id,
            "source_id": source_id,
            "document_title": "Test Document",
            "normalized_text": raw_content.decode("utf-8") if isinstance(raw_content, bytes) else str(raw_content),
            "normalized_content": {"mime_type": content_type, "structure": []},
            "content_type": content_type,
            "parser_name": parser_name or "v1",
            "status": "normalized",
            "normalized_at": None,
            "created_at": None,
            "updated_at": None,
        }


class FakeMetadataExtractor:
    """Fake metadata extractor: best-effort, non-fatal."""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.extract_calls: list[dict] = []

    def extract(self, normalized_document):
        self.extract_calls.append(
            {"normalized_document_id": normalized_document.get("id")}
        )
        if self.should_fail:
            raise RuntimeError("simulated metadata failure")
        return {"normalized_document_id": normalized_document.get("id")}

    def process(self, normalized_document):
        return self.extract(normalized_document)


class FakeCandidateExtractor:
    """Fake candidate extractor: returns candidate records."""

    def __init__(self, candidates: list[dict] | None = None,
                 should_fail: bool = False) -> None:
        self.candidates = list(candidates or [])
        self.should_fail = should_fail
        self.extract_calls: list[dict] = []

    def extract(self, normalized_document):
        self.extract_calls.append(
            {"normalized_document_id": normalized_document.get("id")}
        )
        if self.should_fail:
            raise RuntimeError("simulated candidate extraction failure")
        return list(self.candidates)

    def process(self, normalized_document):
        return self.extract(normalized_document)


class SequencedExtractionResult:
    is_configured = True

    def __init__(self, results):
        self.results = list(results)

    def extract(self, normalized_document):
        return self.results.pop(0)


class FakeIngestionService:
    """Fake ingestion service for job status updates."""

    def __init__(self, job_repo: FakeJobRepository | None = None) -> None:
        self.job_repo = job_repo
        self.completed_job_id: UUID | None = None
        self.claimed_job_id: UUID | None = None
        self.failed_job_id: UUID | None = None
        self.failed_error: str | None = None
        self.fail_calls: list[dict] = []

    def complete_job(
        self, job_id, actor_user_id=None, claim_started_at=None
    ):
        self.completed_job_id = job_id
        if self.job_repo is not None:
            job = self.job_repo.get(job_id)
            return self.job_repo.complete(
                job_id,
                claim_started_at=claim_started_at,
            )
        return {"id": job_id, "status": "completed"}

    def claim_job(self, job_id, actor_user_id=None):
        self.claimed_job_id = job_id
        if self.job_repo is not None:
            return self.job_repo.claim(job_id)
        return {"id": job_id, "status": "claimed"}

    def fail_job(self, job_id, error_details=None, make_retryable=False,
                 actor_user_id=None, claim_started_at=None):
        self.failed_job_id = job_id
        self.failed_error = error_details
        self.fail_calls.append({
            "job_id": job_id,
            "error_details": error_details,
            "make_retryable": make_retryable,
            "claim_started_at": claim_started_at,
        })
        if self.job_repo is not None:
            return self.job_repo.fail(
                job_id, error_details=error_details,
                make_retryable=make_retryable,
                claim_started_at=claim_started_at,
            )
        return {"id": job_id, "status": "retryable" if make_retryable else "failed"}


class FakeStorage:
    """Deterministic in-memory storage — no Supabase contact."""

    def __init__(self, objects: dict[str, bytes] | None = None,
                 should_fail: bool = False) -> None:
        self.objects = dict(objects or {})
        self.should_fail = should_fail
        self.get_calls: list[str] = []

    def upload_artifact(
        self, key: str, content: bytes, *, content_type: str,
        actor_user_id: UUID, audit_ref: str | None = None,
    ) -> None:
        if self.should_fail:
            raise RuntimeError("simulated storage failure")
        self.objects[key] = content

    def get_artifact(self, key: str, actor_user_id: UUID):
        self.get_calls.append(key)
        if self.should_fail:
            raise RuntimeError("simulated storage read failure")
        return self.objects.get(key)

    def create_download_url(self, key: str, actor_user_id: UUID,
                            expires_in_seconds: int = 300) -> str:
        return f"signed://{key}"


class FakeStorageService:
    """Thin wrapper matching RegulatorySourceStorageApplicationService."""

    def __init__(self, storage: FakeStorage) -> None:
        self._storage = storage

    def upload_artifact(
        self, key: str, content: bytes, *, content_type: str,
        actor_user_id: UUID, audit_ref: str | None = None,
    ) -> None:
        self._storage.upload_artifact(
            key, content, content_type=content_type,
            actor_user_id=actor_user_id,
        )

    def get_artifact(self, key: str, actor_user_id: UUID):
        return self._storage.get_artifact(key, actor_user_id)


class ServiceFactory:
    def __init__(
        self,
        *,
        granted_actor: bool = True,
        storage: FakeStorage | None = None,
        parser: FakeParser | None = None,
        normalizer: FakeNormalizer | None = None,
        metadata_extractor: FakeMetadataExtractor | None = None,
        candidate_extractor: FakeCandidateExtractor | None = None,
        requirement_repo: FakeRequirementRepository | None = None,
        source_repo: FakeSourceRepository | None = None,
        artifact_repo: FakeArtifactRepository | None = None,
        job_repo: FakeJobRepository | None = None,
        normalization_repo: FakeNormalizationRepository | None = None,
        ingestion_service: FakeIngestionService | None = None,
    ) -> None:
        self.granted_actor = granted_actor
        self.database = FakeDatabase()
        self.storage = storage or FakeStorage(
            objects={"regulatory-source-artifacts/src/hash": CONTENT_TEXT}
        )
        self.parser = parser or FakeParser()
        self.normalizer = normalizer or FakeNormalizer()
        self.metadata_extractor = metadata_extractor or FakeMetadataExtractor()
        self.candidate_extractor = candidate_extractor or FakeCandidateExtractor(
            candidates=[
                {
                    "id": UUID("33333333-0000-0000-0000-000000000300"),
                    "normalized_document_id": NORMALIZATION,
                    "artifact_id": ARTIFACT,
                    "source_id": SOURCE,
                    "requirement_text": "Shall be labeled with origin.",
                    "requirement_type": "labeling",
                    "source_location": {"section_order": 0, "heading": None},
                    "position": 0,
                    "actor": None,
                    "condition_metadata": None,
                    "status": "extracted",
                },
                {
                    "id": UUID("44444444-0000-0000-0000-000000000400"),
                    "normalized_document_id": NORMALIZATION,
                    "artifact_id": ARTIFACT,
                    "source_id": SOURCE,
                    "requirement_text": "Shall not exceed 50 kg.",
                    "requirement_type": "threshold",
                    "source_location": {"section_order": 1, "heading": None},
                    "position": 1,
                    "actor": None,
                    "condition_metadata": None,
                    "status": "extracted",
                },
            ]
        )
        self.requirement_repo = requirement_repo or FakeRequirementRepository()
        self.source_repo = source_repo or FakeSourceRepository(
            {SOURCE: {"id": SOURCE, "authority_id": UUID("cccccccc-0000-0000-0000-000000000003"),
                      "jurisdiction": "EU", "title": "Test Source", "status": "active"}}
        )
        self.artifact_repo = artifact_repo or FakeArtifactRepository(
            {ARTIFACT: {"id": ARTIFACT, "source_id": SOURCE, "artifact_uri":
                        "regulatory-source-artifacts/src/hash", "content_hash": "hash",
                        "content_length": 100, "content_type": "text/plain",
                        "status": "validated"}}
        )
        self.job_repo = job_repo or FakeJobRepository(
            {JOB: {"id": JOB, "artifact_id": ARTIFACT, "source_id": SOURCE,
                   "status": "pending", "attempt_number": 1,
                   "actor_user_id": ACTOR}}
        )
        self.normalization_repo = normalization_repo or FakeNormalizationRepository()
        self.ingestion_service = FakeIngestionService(job_repo=self.job_repo)

    def service(self) -> RegulatoryCandidateExtractionService:
        grant_service = FakeGrantService({ACTOR} if self.granted_actor else set())
        return RegulatoryCandidateExtractionService(
            self.database,
            source_repo=self.source_repo,
            artifact_repo=self.artifact_repo,
            job_repo=self.job_repo,
            requirement_repo=self.requirement_repo,
            normalization_repo=self.normalization_repo,
            metadata_repo=self.metadata_extractor,  # type: ignore[arg-type]
            grant_service=grant_service,
            storage_service=FakeStorageService(self.storage),
            parser_service=self.parser,
            normalization_service=self.normalizer,
            metadata_service=self.metadata_extractor,
            candidate_service=self.candidate_extractor,
            ingestion_service=self.ingestion_service,
        )


def _b64(content: bytes) -> str:
    import base64
    return base64.b64encode(content).decode("ascii")


class RegulatoryCandidateExtractionTests(TestCase):
    def test_valid_empty_semantic_result_is_successful_and_explicit(self):
        llm = ScriptedLLMClient(responses=[
            LLMResponse(
                json.dumps({"requirements": []}),
                model_identifier="scripted-model",
            )
        ])
        semantic_extractor = RegulatoryRequirementExtractionService(
            llm_client=llm,
            configuration=LLMGenerationConfig(
                model_identifier="scripted-model",
                max_output_tokens=4096,
            ),
        )
        factory = ServiceFactory(candidate_extractor=semantic_extractor)

        result = factory.service().extract_candidates(
            actor_user_id=ACTOR,
            source_id=SOURCE,
            artifact_id=ARTIFACT,
            job_id=JOB,
        )

        self.assertEqual(result["outcome"], EXTRACTION_OUTCOME_SUCCEEDED)
        self.assertEqual(result["candidate_count"], 0)
        self.assertTrue(result["no_qualifying_requirements"])
        self.assertEqual(result["job"]["status"], "completed")

    def test_partial_candidates_retry_and_become_succeeded_after_full_run(self):
        quote = "The shipment must carry a phytosanitary certificate."
        candidate = {
            "id": CANDIDATE,
            "normalized_document_id": NORMALIZATION,
            "artifact_id": ARTIFACT,
            "source_id": SOURCE,
            "requirement_text": quote,
            "requirement_type": "documentation",
            "source_location": {
                "supporting_quote": quote,
                "title": "phytosanitary certificate",
            },
            "position": 10,
            "actor": None,
            "condition_metadata": None,
            "status": "extracted",
        }
        extractor = SequencedExtractionResult([
            RegulatoryRequirementExtractionResult(
                candidates=(candidate,),
                outcome=EXTRACTION_OUTCOME_PARTIAL,
                failed_chunks=({"chunk_index": 2, "reason": "timeout"},),
            ),
            RegulatoryRequirementExtractionResult(
                candidates=(candidate,),
                outcome=EXTRACTION_OUTCOME_SUCCEEDED,
            ),
        ])
        factory = ServiceFactory(candidate_extractor=extractor)
        service = factory.service()

        partial = service.extract_candidates(
            actor_user_id=ACTOR,
            source_id=SOURCE,
            artifact_id=ARTIFACT,
            job_id=JOB,
        )
        self.assertEqual(partial["outcome"], EXTRACTION_OUTCOME_PARTIAL)
        self.assertEqual(partial["job"]["status"], "retryable")
        self.assertEqual(
            factory.requirement_repo.requirements[0]["extraction_outcome"],
            EXTRACTION_OUTCOME_PARTIAL,
        )

        retried = service.extract_candidates(
            actor_user_id=ACTOR,
            source_id=SOURCE,
            artifact_id=ARTIFACT,
            job_id=JOB,
        )
        self.assertEqual(retried["outcome"], EXTRACTION_OUTCOME_SUCCEEDED)
        self.assertEqual(retried["job"]["status"], "completed")
        self.assertEqual(
            retried["candidates"][0]["extraction_outcome"],
            EXTRACTION_OUTCOME_SUCCEEDED,
        )
        self.assertEqual(len(factory.requirement_repo.requirements), 1)
        self.assertEqual(len(factory.requirement_repo.extraction_runs), 2)
        self.assertEqual(
            [run["outcome"] for run in factory.requirement_repo.extraction_runs],
            [EXTRACTION_OUTCOME_PARTIAL, EXTRACTION_OUTCOME_SUCCEEDED],
        )
        self.assertEqual(
            [
                link["resolution_status"]
                for link in factory.requirement_repo.extraction_run_candidates
            ],
            ["persisted", "reused"],
        )

    def test_successful_extraction_creates_candidates_with_provenance(self):
        factory = ServiceFactory()
        service = factory.service()
        result = service.extract_candidates(
            actor_user_id=ACTOR,
            source_id=SOURCE,
            artifact_id=ARTIFACT,
            job_id=JOB,
        )
        self.assertEqual(result["outcome"], EXTRACTION_OUTCOME_SUCCEEDED)
        self.assertEqual(result["candidate_count"], 2)
        self.assertEqual(result["job"]["status"], "completed")
        self.assertEqual(result["job"]["actor_user_id"], ACTOR)
        self.assertEqual(
            factory.job_repo.stage_history,
            [
                "retrieving_artifact",
                "validating_document",
                "extracting_text",
                "normalizing_content",
                "extracting_requirements",
                "saving_candidates",
                "completed",
            ],
        )
        self.assertEqual(factory.job_repo.completed_job_id, JOB)
        # Candidates have provenance fields
        for cand in result["candidates"]:
            self.assertEqual(cand["source_id"], SOURCE)
            self.assertEqual(cand["artifact_id"], ARTIFACT)
            self.assertEqual(cand["ingestion_job_id"], JOB)
            self.assertEqual(cand["extraction_outcome"], EXTRACTION_OUTCOME_SUCCEEDED)
            self.assertEqual(cand["parser_version"], "v1")
            self.assertFalse(cand["manual_entry"])
            self.assertIsNone(cand["reviewer_user_id"])
        self.assertEqual(len(factory.requirement_repo.extraction_runs), 1)
        run = factory.requirement_repo.extraction_runs[0]
        self.assertEqual(run["source_id"], SOURCE)
        self.assertEqual(run["artifact_id"], ARTIFACT)
        self.assertEqual(run["normalized_document_id"], NORMALIZATION)
        self.assertEqual(run["ingestion_job_id"], JOB)
        self.assertEqual(run["artifact_content_hash"], "hash")
        self.assertEqual(run["extraction_method"], "custom_extractor")
        self.assertEqual(run["parser_version"], "v1")
        self.assertEqual(len(factory.requirement_repo.extraction_run_candidates), 2)
        self.assertTrue(
            all(
                item["resolution_status"] == "persisted"
                and item["is_origin"]
                for item in factory.requirement_repo.extraction_run_candidates
            )
        )
        # Storage read was called
        self.assertIn("regulatory-source-artifacts/src/hash",
                      factory.storage.get_calls)

    def test_changed_retry_evidence_is_appended_without_overwriting_candidate(self):
        first_quote = "Shall be labeled with origin."
        second_quote = "Shall not exceed 50 kg."
        first_candidate = {
            "id": CANDIDATE,
            "normalized_document_id": NORMALIZATION,
            "artifact_id": ARTIFACT,
            "source_id": SOURCE,
            "requirement_text": first_quote,
            "requirement_type": "documentation",
            "source_location": {"supporting_quote": first_quote},
            "position": 0,
            "actor": None,
            "condition_metadata": None,
            "status": "extracted",
        }
        second_candidate = {
            **first_candidate,
            "id": UUID("22222222-0000-0000-0000-000000000201"),
            "requirement_text": second_quote,
            "source_location": {"supporting_quote": second_quote},
        }
        extractor = SequencedExtractionResult([
            RegulatoryRequirementExtractionResult(
                candidates=(first_candidate,),
                outcome=EXTRACTION_OUTCOME_PARTIAL,
                failed_chunks=({"chunk_index": 1, "reason": "timeout"},),
            ),
            RegulatoryRequirementExtractionResult(
                candidates=(second_candidate,),
                outcome=EXTRACTION_OUTCOME_SUCCEEDED,
            ),
        ])
        factory = ServiceFactory(candidate_extractor=extractor)
        service = factory.service()

        service.extract_candidates(
            actor_user_id=ACTOR,
            source_id=SOURCE,
            artifact_id=ARTIFACT,
            job_id=JOB,
        )
        retried = service.extract_candidates(
            actor_user_id=ACTOR,
            source_id=SOURCE,
            artifact_id=ARTIFACT,
            job_id=JOB,
        )

        self.assertEqual(
            [
                candidate["requirement_text"]
                for candidate in retried["candidates"]
            ],
            [first_quote, second_quote],
        )
        self.assertEqual(
            [
                link["evidence_snapshot"]["requirement_text"]
                for link in factory.requirement_repo.extraction_run_candidates
            ],
            [first_quote, second_quote],
        )
        self.assertEqual(
            [run["outcome"] for run in factory.requirement_repo.extraction_runs],
            [EXTRACTION_OUTCOME_PARTIAL, EXTRACTION_OUTCOME_SUCCEEDED],
        )

    def test_worker_claim_preserves_original_actor_attribution(self):
        factory = ServiceFactory()
        factory.job_repo.jobs[JOB]["actor_user_id"] = NON_GRANTED

        result = factory.service().extract_candidates(
            actor_user_id=ACTOR,
            source_id=SOURCE,
            artifact_id=ARTIFACT,
            job_id=JOB,
        )

        self.assertEqual(result["job"]["status"], "completed")
        self.assertEqual(result["job"]["actor_user_id"], NON_GRANTED)

    def test_unauthorized_actor_denied(self):
        factory = ServiceFactory(granted_actor=False)
        service = factory.service()
        with self.assertRaises(PermissionDeniedError):
            service.extract_candidates(
                actor_user_id=NON_GRANTED,
                source_id=SOURCE,
                artifact_id=ARTIFACT,
                job_id=JOB,
            )

    def test_missing_source_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        with self.assertRaises(ApplicationNotFoundError):
            service.extract_candidates(
                actor_user_id=ACTOR,
                source_id=UUID("99999999-0000-0000-0000-000000000999"),
                artifact_id=ARTIFACT,
                job_id=JOB,
            )

    def test_missing_artifact_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        with self.assertRaises(ApplicationNotFoundError):
            service.extract_candidates(
                actor_user_id=ACTOR,
                source_id=SOURCE,
                artifact_id=UUID("99999999-0000-0000-0000-000000000999"),
                job_id=JOB,
            )

    def test_missing_job_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        with self.assertRaises(ApplicationNotFoundError):
            service.extract_candidates(
                actor_user_id=ACTOR,
                source_id=SOURCE,
                artifact_id=ARTIFACT,
                job_id=UUID("99999999-0000-0000-0000-000000000999"),
            )

    def test_artifact_not_linked_to_source_rejected(self):
        factory = ServiceFactory()
        # Artifact belongs to a different source
        factory.artifact_repo.artifacts[ARTIFACT]["source_id"] = UUID(
            "88888888-0000-0000-0000-000000000008")
        service = factory.service()
        with self.assertRaises(ApplicationNotFoundError):
            service.extract_candidates(
                actor_user_id=ACTOR,
                source_id=SOURCE,
                artifact_id=ARTIFACT,
                job_id=JOB,
            )

    def test_failed_extraction_records_outcome_and_preserves_evidence(self):
        factory = ServiceFactory(parser=FakeParser(should_fail=True))
        service = factory.service()
        result = service.extract_candidates(
            actor_user_id=ACTOR,
            source_id=SOURCE,
            artifact_id=ARTIFACT,
            job_id=JOB,
        )
        self.assertEqual(result["outcome"], EXTRACTION_OUTCOME_FAILED)
        self.assertEqual(result["candidate_count"], 0)
        self.assertEqual(result["candidates"], [])
        # Job marked failed (retryable)
        self.assertEqual(factory.job_repo.failed_job_id, JOB)
        self.assertIsNotNone(factory.job_repo.failed_error)
        # No candidates created
        self.assertEqual(len(factory.requirement_repo.requirements), 0)

    def test_failed_extraction_within_bound_stays_retryable(self):
        # A first failure of a fresh attempt is retryable by the worker.
        factory = ServiceFactory(parser=FakeParser(should_fail=True))
        factory.job_repo.jobs[JOB]["retry_count"] = 0
        service = factory.service()
        result = service.extract_candidates(
            actor_user_id=ACTOR,
            source_id=SOURCE,
            artifact_id=ARTIFACT,
            job_id=JOB,
        )
        self.assertEqual(result["outcome"], EXTRACTION_OUTCOME_FAILED)
        self.assertEqual(
            factory.ingestion_service.fail_calls[-1]["make_retryable"], True
        )
        self.assertEqual(factory.job_repo.jobs[JOB]["status"], "retryable")

    def test_failed_extraction_beyond_retry_bound_is_terminal(self):
        # Bounded retries: once an attempt's durable retry_count has
        # reached MAX_RETRY_ATTEMPTS, the next failure is terminal —
        # the job is marked 'failed', no longer 'retryable', and only
        # the authorized staff retry control can record a new attempt.
        from xportra.application.regulatory_ingestion_service import (
            MAX_RETRY_ATTEMPTS,
        )
        factory = ServiceFactory(parser=FakeParser(should_fail=True))
        factory.job_repo.jobs[JOB]["retry_count"] = MAX_RETRY_ATTEMPTS
        service = factory.service()
        result = service.extract_candidates(
            actor_user_id=ACTOR,
            source_id=SOURCE,
            artifact_id=ARTIFACT,
            job_id=JOB,
        )
        self.assertEqual(result["outcome"], EXTRACTION_OUTCOME_FAILED)
        self.assertEqual(
            factory.ingestion_service.fail_calls[-1]["make_retryable"], False
        )
        self.assertEqual(factory.job_repo.jobs[JOB]["status"], "failed")

    def test_empty_extraction_records_failed_outcome(self):
        factory = ServiceFactory(
            parser=FakeParser(should_return_empty=True))
        service = factory.service()
        result = service.extract_candidates(
            actor_user_id=ACTOR,
            source_id=SOURCE,
            artifact_id=ARTIFACT,
            job_id=JOB,
        )
        self.assertEqual(result["outcome"], EXTRACTION_OUTCOME_FAILED)
        self.assertEqual(result["candidate_count"], 0)

    def test_storage_read_failure_raises_infrastructure_error(self):
        factory = ServiceFactory(storage=FakeStorage(should_fail=True))
        service = factory.service()
        with self.assertRaises(InfrastructureError):
            service.extract_candidates(
                actor_user_id=ACTOR,
                source_id=SOURCE,
                artifact_id=ARTIFACT,
                job_id=JOB,
            )

    def test_candidate_persistence_failure_is_recorded_and_surfaced(self):
        factory = ServiceFactory()
        factory.requirement_repo.fail_create = True

        with self.assertRaisesRegex(
                InfrastructureError, "candidate persistence failed"):
            factory.service().extract_candidates(
                actor_user_id=ACTOR,
                source_id=SOURCE,
                artifact_id=ARTIFACT,
                job_id=JOB,
            )

        self.assertEqual(factory.job_repo.jobs[JOB]["status"], "retryable")
        self.assertEqual(factory.job_repo.jobs[JOB]["current_stage"], "failed")
        self.assertEqual(
            factory.ingestion_service.fail_calls[-1]["make_retryable"], True
        )

    def test_idempotent_re_extraction_returns_existing_candidates(self):
        factory = ServiceFactory(
            candidate_extractor=FakeCandidateExtractor(candidates=[{
                "id": CANDIDATE,
                "normalized_document_id": NORMALIZATION,
                "artifact_id": ARTIFACT,
                "source_id": SOURCE,
                "requirement_text": "Pre-existing candidate.",
                "requirement_type": "labeling",
                "source_location": {},
                "position": 0,
                "actor": None,
                "condition_metadata": None,
                "status": "extracted",
            }])
        )
        # Pre-create a candidate for the artifact's normalization
        factory.normalization_repo.normalizations[NORMALIZATION] = {
            "id": NORMALIZATION,
            "artifact_id": ARTIFACT,
            "source_id": SOURCE,
            "normalized_text": CONTENT_TEXT.decode("utf-8"),
            "parser_name": "v1",
        }
        factory.requirement_repo.requirements.append({
            "id": CANDIDATE,
            "normalized_document_id": NORMALIZATION,
            "artifact_id": ARTIFACT,
            "source_id": SOURCE,
            "requirement_text": "Pre-existing candidate.",
            "requirement_type": "labeling",
            "source_location": {},
            "position": 0,
            "actor": None,
            "condition_metadata": None,
            "status": "extracted",
            "ingestion_job_id": JOB,
            "extraction_outcome": EXTRACTION_OUTCOME_SUCCEEDED,
            "parser_version": "v1",
            "manual_entry": False,
            "reviewer_user_id": None,
            "reviewed_at": None,
            "created_at": None,
            "updated_at": None,
        })
        service = factory.service()
        result1 = service.extract_candidates(
            actor_user_id=ACTOR, source_id=SOURCE,
            artifact_id=ARTIFACT, job_id=JOB,
        )
        self.assertTrue(result1["duplicate"])
        self.assertEqual(result1["candidate_count"], 1)
        # Only one candidate exists (no duplicate created)
        self.assertEqual(len(factory.requirement_repo.requirements), 1)

    def test_existing_candidates_do_not_hide_missing_candidate_persistence(self):
        factory = ServiceFactory()
        factory.normalization_repo.normalizations[NORMALIZATION] = {
            "id": NORMALIZATION,
            "artifact_id": ARTIFACT,
            "source_id": SOURCE,
            "normalized_text": CONTENT_TEXT.decode("utf-8"),
            "parser_name": "v1",
        }
        factory.requirement_repo.requirements.append({
            "id": CANDIDATE,
            "normalized_document_id": NORMALIZATION,
            "artifact_id": ARTIFACT,
            "source_id": SOURCE,
            "requirement_text": "Already persisted candidate.",
            "requirement_type": "labeling",
            "source_location": {},
            "position": 0,
            "actor": None,
            "condition_metadata": None,
            "status": "extracted",
            "ingestion_job_id": JOB,
            "extraction_outcome": EXTRACTION_OUTCOME_SUCCEEDED,
            "parser_version": "v1",
            "manual_entry": False,
            "reviewer_user_id": None,
            "reviewed_at": None,
            "created_at": None,
            "updated_at": None,
        })

        result = factory.service().extract_candidates(
            actor_user_id=ACTOR,
            source_id=SOURCE,
            artifact_id=ARTIFACT,
            job_id=JOB,
        )

        self.assertTrue(result["duplicate"])
        self.assertEqual(result["job"]["status"], "completed")
        self.assertEqual(result["candidate_count"], 3)
        self.assertEqual(
            {candidate["position"] for candidate in result["candidates"]},
            {0, 1, 2},
        )

    def test_manual_candidate_entry_with_reviewer_attribution(self):
        factory = ServiceFactory()
        service = factory.service()
        row = service.enter_manual_candidate(
            actor_user_id=ACTOR,
            source_id=SOURCE,
            artifact_id=ARTIFACT,
            requirement_text="Manually entered requirement.",
            requirement_type="documentation",
            source_location={"section_order": 5, "heading": "Annex A"},
            position=10,
            justification="Extraction failed; manual recovery.",
        )
        self.assertEqual(row["requirement_text"], "Manually entered requirement.")
        self.assertEqual(row["requirement_type"], "documentation")
        self.assertEqual(row["source_location"], {"section_order": 5, "heading": "Annex A"})
        self.assertEqual(row["position"], 10)
        self.assertEqual(row["extraction_outcome"], EXTRACTION_OUTCOME_MANUAL)
        self.assertTrue(row["manual_entry"])
        self.assertEqual(row["reviewer_user_id"], ACTOR)
        self.assertIsNotNone(row["reviewed_at"])
        self.assertIsNone(row["ingestion_job_id"])  # manual, no job
        self.assertEqual(row["status"], "extracted")

    def test_manual_candidate_empty_text_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        with self.assertRaises(ApplicationValidationError):
            service.enter_manual_candidate(
                actor_user_id=ACTOR,
                source_id=SOURCE,
                artifact_id=ARTIFACT,
                requirement_text="",
            )

    def test_manual_candidate_unauthorized_denied(self):
        factory = ServiceFactory(granted_actor=False)
        service = factory.service()
        with self.assertRaises(PermissionDeniedError):
            service.enter_manual_candidate(
                actor_user_id=NON_GRANTED,
                source_id=SOURCE,
                artifact_id=ARTIFACT,
                requirement_text="Manual requirement.",
            )

    def test_get_candidate_returns_candidate(self):
        factory = ServiceFactory()
        service = factory.service()
        row = service.enter_manual_candidate(
            actor_user_id=ACTOR, source_id=SOURCE,
            artifact_id=ARTIFACT,
            requirement_text="Get me candidate.",
        )
        fetched = service.get_candidate(row["id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["id"], row["id"])

    def test_get_candidate_missing_returns_none(self):
        factory = ServiceFactory()
        service = factory.service()
        self.assertIsNone(
            service.get_candidate(UUID("99999999-0000-0000-0000-000000000999"))
        )

    def test_list_candidates_for_artifact(self):
        factory = ServiceFactory()
        # Add normalization + candidates
        factory.normalization_repo.normalizations[NORMALIZATION] = {
            "id": NORMALIZATION,
            "artifact_id": ARTIFACT,
            "source_id": SOURCE,
        }
        factory.requirement_repo.requirements.append({
            "id": CANDIDATE,
            "normalized_document_id": NORMALIZATION,
            "artifact_id": ARTIFACT,
            "source_id": SOURCE,
            "requirement_text": "Candidate one.",
            "requirement_type": "labeling",
            "source_location": {},
            "position": 0,
            "actor": None,
            "condition_metadata": None,
            "status": "extracted",
            "ingestion_job_id": None,
            "extraction_outcome": EXTRACTION_OUTCOME_SUCCEEDED,
            "parser_version": "v1",
            "manual_entry": False,
            "reviewer_user_id": None,
            "reviewed_at": None,
            "created_at": None,
            "updated_at": None,
        })
        service = factory.service()
        candidates = service.list_candidates_for_artifact(ARTIFACT)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["id"], CANDIDATE)

    def test_candidates_are_not_published_or_approved(self):
        """Candidates have status 'extracted' — not approved/applicable."""
        factory = ServiceFactory()
        service = factory.service()
        result = service.extract_candidates(
            actor_user_id=ACTOR, source_id=SOURCE,
            artifact_id=ARTIFACT, job_id=JOB,
        )
        for cand in result["candidates"]:
            self.assertEqual(cand["status"], "extracted")
            self.assertNotIn("approved", cand.get("extraction_outcome", ""))
            self.assertNotIn("applicable", cand.get("extraction_outcome", ""))
        # No publication or Stage A/B decision is made by extraction.
        self.assertFalse(any(c.get("manual_entry") for c in result["candidates"]))
        self.assertIsNone(result["candidates"][0].get("reviewer_user_id"))

    def test_normalization_failure_marks_job_failed(self):
        factory = ServiceFactory(
            normalizer=FakeNormalizer(should_fail=True))
        service = factory.service()
        with self.assertRaises(InfrastructureError):
            service.extract_candidates(
                actor_user_id=ACTOR, source_id=SOURCE,
                artifact_id=ARTIFACT, job_id=JOB,
            )
        self.assertEqual(factory.job_repo.failed_job_id, JOB)

    def test_candidate_extraction_failure_marks_job_failed(self):
        factory = ServiceFactory(
            candidate_extractor=FakeCandidateExtractor(should_fail=True))
        service = factory.service()
        with self.assertRaises(InfrastructureError):
            service.extract_candidates(
                actor_user_id=ACTOR, source_id=SOURCE,
                artifact_id=ARTIFACT, job_id=JOB,
            )
        self.assertEqual(factory.job_repo.failed_job_id, JOB)
        self.assertEqual(
            factory.requirement_repo.extraction_runs[0]["outcome"],
            EXTRACTION_OUTCOME_FAILED,
        )
        self.assertEqual(
            factory.requirement_repo.extraction_runs[0]["failed_chunks"][0][
                "error_type"
            ],
            "RuntimeError",
        )
        self.assertEqual(
            factory.requirement_repo.extraction_runs[0]["extraction_method"],
            "custom_extractor",
        )
        self.assertEqual(
            factory.requirement_repo.extraction_runs[0]["extraction_version"],
            "unknown",
        )
        self.assertIsNone(
            factory.requirement_repo.extraction_runs[0]["prompt_version"]
        )
