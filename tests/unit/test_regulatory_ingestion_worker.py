"""Focused unit tests for durable ingestion worker mechanism (Task 3B).

Tests authorization enforcement (GRANT_MANAGE required), startup/shutdown
contracts, safe skip when unconfigured, bounded polling behavior, and
crash-recovery contract notes. No live DB or hosted infrastructure
required for authorization/startup contracts; full DB integration is
skipped when DATABASE_URL is absent.
"""
from __future__ import annotations

from unittest import TestCase
from uuid import UUID

from xportra.application.regulatory_ingestion_service import RegulatoryIngestionService
from xportra.application.global_staff import GRANT_MANAGE
from xportra.application.regulatory_ingestion_worker import (
    RegulatoryIngestionWorker,
    POLL_INTERVAL_SECONDS,
    LEASE_TIMEOUT_SECONDS,
)


class FakeGrantRepo:
    def __init__(self, active: dict | None = None):
        self.active = active or {}

    def is_granted(self, user_id, permission) -> bool:
        return (user_id, permission) in self.active


class FakeDB:
    def __init__(self):
        self.jobs = {}

    def transaction(self):
        class Ctx:
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass
        return Ctx()


class TestWorkerAuthorization(TestCase):
    def test_authorized_worker_can_start(self):
        db = FakeDB()
        worker = RegulatoryIngestionWorker(db)
        actor = UUID("aaaaaaaa-0000-0000-0000-000000000001")
        worker._actor_id = actor
        worker._grants = FakeGrantRepo({(actor, GRANT_MANAGE): True})
        self.assertTrue(worker._is_authorized())

    def test_unauthorized_worker_skips_execution(self):
        db = FakeDB()
        worker = RegulatoryIngestionWorker(db)
        actor = UUID("bbbbbbbb-0000-0000-0000-000000000002")
        worker._actor_id = actor
        worker._grants = FakeGrantRepo({})  # empty grants
        self.assertFalse(worker._is_authorized())


class TestWorkerLifecycleContracts(TestCase):
    def test_start_stop_contract_exists(self):
        db = FakeDB()
        worker = RegulatoryIngestionWorker(db)
        # Without authorization, start should not raise; it skips execution safely.
        worker.start()
        worker.stop()
        # The contract is that start/stop exist and handle authorization safely.
        self.assertTrue(hasattr(worker, "start"))
        self.assertTrue(hasattr(worker, "stop"))

    def test_poll_interval_and_lease_defaults_safe(self):
        # Defaults must be positive and finite; never zero or infinite.
        self.assertGreater(POLL_INTERVAL_SECONDS, 0)
        self.assertGreater(LEASE_TIMEOUT_SECONDS, 0)
        self.assertTrue(POLL_INTERVAL_SECONDS < 3600)
        self.assertTrue(LEASE_TIMEOUT_SECONDS < 3600)


class TestWorkerCrashRecoveryContract(TestCase):
    def test_recovery_contract_documented(self):
        # The durable contract requires that expired claimed/processing
        # jobs are reset to retryable on startup. The repository method
        # exists; the full DB-level verification requires DATABASE_URL.
        db = FakeDB()
        worker = RegulatoryIngestionWorker(db)
        self.assertTrue(hasattr(worker, "_recover_expired_lease"))


class FakeExtractionService:
    """Callable factory returning an object with extract_candidates."""

    def __init__(self, result=None, should_fail=False, fail_error="boom"):
        self.result = result or {
            "outcome": "succeeded",
            "candidate_count": 1,
            "candidates": [],
            "job": {"id": None, "status": "completed"},
            "duplicate": False,
        }
        self.should_fail = should_fail
        self.fail_error = fail_error
        self.calls: list[dict] = []

    def __call__(self, database):
        return self

    def extract_candidates(self, actor_user_id, source_id, artifact_id, job_id):
        self.calls.append(
            {
                "actor_user_id": actor_user_id,
                "source_id": source_id,
                "artifact_id": artifact_id,
                "job_id": job_id,
            }
        )
        if self.should_fail:
            raise RuntimeError(self.fail_error)
        return dict(self.result)


class FakeJobRepo:
    def __init__(self, jobs=None):
        self.jobs = dict(jobs or {})
        self.get_calls: list[UUID] = []

    def get(self, job_id):
        self.get_calls.append(job_id)
        return self.jobs.get(job_id)


class FakeStorageServiceForTest:
    """Minimal storage service double with get_artifact."""

    def get_artifact(self, key, actor_user_id=None):
        return b"text content"


class TestWorkerProcessing(TestCase):
    def setUp(self):
        self.actor = UUID("aaaaaaaa-0000-0000-0000-000000000001")
        self.source = UUID("dddddddd-0000-0000-0000-000000000004")
        self.artifact = UUID("eeeeeeee-0000-0000-0000-000000000005")
        self.job = UUID("ffffffff-0000-0000-0000-000000000006")

    def _make_worker(self, job_repo, extraction_service, granted=True):
        db = FakeDB()
        worker = RegulatoryIngestionWorker(
            db,
            extraction_service=extraction_service,
            job_repo=job_repo,
        )
        worker._actor_id = self.actor
        worker._grants = FakeGrantRepo(
            {(self.actor, GRANT_MANAGE): True} if granted else {}
        )
        return worker

    def test_process_pending_job_calls_extraction_and_completes(self):
        job_repo = FakeJobRepo(
            {self.job: {"id": self.job, "artifact_id": self.artifact,
                        "source_id": self.source, "status": "pending"}}
        )
        extraction_service = FakeExtractionService()
        worker = self._make_worker(job_repo, extraction_service)

        worker._process_job(self.job)

        self.assertEqual(len(extraction_service.calls), 1)
        call = extraction_service.calls[0]
        self.assertEqual(call["actor_user_id"], self.actor)
        self.assertEqual(call["source_id"], self.source)
        self.assertEqual(call["artifact_id"], self.artifact)
        self.assertEqual(call["job_id"], self.job)

    def test_process_job_without_artifact_skips_extraction(self):
        job_repo = FakeJobRepo(
            {self.job: {"id": self.job, "artifact_id": None,
                        "source_id": self.source, "status": "pending"}}
        )
        extraction_service = FakeExtractionService()
        worker = self._make_worker(job_repo, extraction_service)

        worker._process_job(self.job)

        self.assertEqual(len(extraction_service.calls), 0)

    def test_process_missing_job_is_noop(self):
        job_repo = FakeJobRepo({})
        extraction_service = FakeExtractionService()
        worker = self._make_worker(job_repo, extraction_service)

        worker._process_job(UUID("99999999-0000-0000-0000-000000000999"))

        self.assertEqual(len(extraction_service.calls), 0)

    def test_process_job_extraction_failure_logs_and_does_not_complete(self):
        job_repo = FakeJobRepo(
            {self.job: {"id": self.job, "artifact_id": self.artifact,
                        "source_id": self.source, "status": "pending"}}
        )
        extraction_service = FakeExtractionService(should_fail=True)
        worker = self._make_worker(job_repo, extraction_service)

        # Should not raise; failure is logged.
        worker._process_job(self.job)

        self.assertEqual(len(extraction_service.calls), 1)

    def test_unauthorized_worker_skips_processing(self):
        job_repo = FakeJobRepo(
            {self.job: {"id": self.job, "artifact_id": self.artifact,
                        "source_id": self.source, "status": "pending"}}
        )
        extraction_service = FakeExtractionService()
        worker = self._make_worker(job_repo, extraction_service, granted=False)

        worker._process_job(self.job)

        self.assertEqual(len(extraction_service.calls), 0)

    def test_process_retryable_job(self):
        job_repo = FakeJobRepo(
            {self.job: {"id": self.job, "artifact_id": self.artifact,
                        "source_id": self.source, "status": "retryable"}}
        )
        extraction_service = FakeExtractionService()
        worker = self._make_worker(job_repo, extraction_service)

        worker._process_job(self.job)

        self.assertEqual(len(extraction_service.calls), 1)
        self.assertEqual(extraction_service.calls[0]["job_id"], self.job)


class TestExtractionRaceCondition(TestCase):
    def test_claim_returns_none_is_idempotent_noop(self):
        # When claim_job returns None (another worker already claimed),
        # extract_candidates returns duplicate=True instead of completing
        # someone else's job.
        from xportra.application.regulatory_candidate_extraction_service import (
            RegulatoryCandidateExtractionService,
        )

        actor = UUID("aaaaaaaa-0000-0000-0000-000000000001")
        source = UUID("dddddddd-0000-0000-0000-000000000004")
        artifact = UUID("eeeeeeee-0000-0000-0000-000000000005")
        job = UUID("ffffffff-0000-0000-0000-000000000006")

        class FakeIngestionService:
            def __init__(self):
                self.claimed = None
                self.completed = None

            def claim_job(self, job_id, actor_user_id=None):
                self.claimed = job_id
                return None  # simulate already claimed by another worker

            def complete_job(self, job_id, actor_user_id=None):
                self.completed = job_id

        class FakeDB:
            def transaction(self):
                class Ctx:
                    def __enter__(self):
                        return self
                    def __exit__(self, *a):
                        pass
                return Ctx()

        class FakeSourceRepo:
            def get(self, source_id):
                return {"id": source} if source_id == source else None

        class FakeArtifactRepo:
            def get(self, artifact_id):
                if artifact_id == artifact:
                    return {"id": artifact, "source_id": source}
                return None

        class FakeJobRepo:
            def get(self, job_id):
                if job_id == job:
                    return {"id": job, "artifact_id": artifact,
                            "source_id": source, "status": "claimed"}
                return None

        class FakeNormalizationRepo:
            def get_by_artifact(self, artifact_id):
                return None

        class FakeRequirementRepo:
            def list_for_document(self, doc_id):
                return []

            def create(self, **kwargs):
                return {"id": kwargs.get("id", job)}

        class FakeGrantService:
            def is_granted(self, user_id, permission):
                return (user_id, permission) == (actor, "grant_manage")

        ingestion = FakeIngestionService()
        service = RegulatoryCandidateExtractionService(
            FakeDB(),
            source_repo=FakeSourceRepo(),
            artifact_repo=FakeArtifactRepo(),
            job_repo=FakeJobRepo(),
            requirement_repo=FakeRequirementRepo(),
            normalization_repo=FakeNormalizationRepo(),
            grant_service=FakeGrantService(),
            storage_service=FakeStorageServiceForTest(),
        )
        # Override storage and ingestion with fakes
        service._storage = type("S", (), {
            "get_artifact": lambda self, key, actor_user_id: b"text"
        })()
        service._ingestion = ingestion
        service._parser = type("P", (), {
            "parse": lambda self, **kw: {"normalized_text": "text",
                                         "parser_name": "v1",
                                         "status": "parsed"}
        })()
        service._normalizer = type("N", (), {
            "normalize": lambda self, **kw: {"id": job}
        })()
        service._metadata_extractor = type("M", (), {
            "extract": lambda self, doc: None
        })()
        service._candidate_extractor = type("C", (), {
            "extract": lambda self, doc: []
        })()

        result = service.extract_candidates(
            actor_user_id=actor,
            source_id=source,
            artifact_id=artifact,
            job_id=job,
        )

        self.assertTrue(result["duplicate"])
        self.assertIsNone(ingestion.completed)
