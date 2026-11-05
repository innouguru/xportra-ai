"""Focused unit tests for durable ingestion worker mechanism (Task 3B).

Tests authorization enforcement (GRANT_MANAGE required), startup/shutdown
contracts, safe skip when unconfigured, bounded polling behavior, and
crash-recovery contract notes. No live DB or hosted infrastructure
required for authorization/startup contracts; full DB integration is
skipped when DATABASE_URL is absent.
"""
from __future__ import annotations

import inspect
import os
import threading
import time
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch
from uuid import UUID

from xportra.application.regulatory_ingestion_service import RegulatoryIngestionService
from xportra.application.global_staff import GRANT_MANAGE
from xportra.application.regulatory_ingestion_worker import (
    RegulatoryIngestionWorker,
    POLL_INTERVAL_SECONDS,
    LEASE_TIMEOUT_SECONDS,
)
from xportra.persistence.repositories import RegulatoryIngestionJobRepository


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
        worker = RegulatoryIngestionWorker(
            db, extraction_service=lambda database: object()
        )
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

    def test_missing_worker_configuration_logs_sanitized_startup_warning(self):
        configured_value = "not-a-valid-worker-id"
        with patch.dict(
                os.environ,
                {"REGULATORY_WORKER_ACTOR_USER_ID": configured_value}):
            worker = RegulatoryIngestionWorker(FakeDB())

        with self.assertLogs(
                "xportra.application.regulatory_ingestion_worker",
                level="WARNING") as captured:
            worker.start()

        diagnostic = "\n".join(captured.output)
        self.assertIn("missing or invalid", diagnostic)
        self.assertNotIn(configured_value, diagnostic)
        self.assertFalse(worker._running)

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

    def test_expired_lease_recovery_respects_authorization(self):
        db = FakeDB()
        worker = RegulatoryIngestionWorker(db)
        worker._grants = FakeGrantRepo({})
        self.assertEqual(worker._recover_expired_lease(), 0)

    def test_expired_lease_recovery_uses_bound_parameter_sql(self):
        # Regression: the earlier implementation spliced the timeout into
        # a Postgres ``interval '%s seconds'`` literal, which is a mis-
        # nested string substitution (invalid once parameters are bound)
        # and would fail lease recovery silently. The recovery SQL must
        # now pass the timeout as a bound parameter via make_interval.
        from xportra.application.regulatory_ingestion_worker import (
            RegulatoryIngestionWorker as Worker,
        )
        source = inspect.getsource(Worker._recover_expired_lease)
        self.assertNotIn("interval '%s", source)
        self.assertIn("make_interval", source)
        self.assertIn("(LEASE_TIMEOUT_SECONDS,)", source)


class TestAtomicClaimQuery(TestCase):
    def test_claim_next_filters_artifacts_and_preserves_locking_order(self):
        captured = {}
        claimed = {"id": UUID("ffffffff-0000-0000-0000-000000000006")}

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def execute(self, query):
                captured["query"] = query

            def fetchone(self):
                return claimed

        class Transaction:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return None

            def cursor(self):
                return Cursor()

        class Database:
            def transaction(self):
                return Transaction()

        result = RegulatoryIngestionJobRepository(Database()).claim_next()

        query = captured["query"]
        self.assertEqual(result, claimed)
        self.assertIn("status IN ('pending', 'retryable')", query)
        self.assertIn("artifact_id IS NOT NULL", query)
        self.assertIn("ORDER BY created_at ASC, id ASC", query)
        self.assertIn("LIMIT 1\n                            FOR UPDATE SKIP LOCKED", query)


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

    def extract_candidates(
        self, actor_user_id, source_id, artifact_id, job_id,
        claim_started_at=None,
    ):
        self.calls.append(
            {
                "actor_user_id": actor_user_id,
                "source_id": source_id,
                "artifact_id": artifact_id,
                "job_id": job_id,
                "claim_started_at": claim_started_at,
            }
        )
        if self.should_fail:
            raise RuntimeError(self.fail_error)
        return dict(self.result)


class FakeJobRepo:
    def __init__(self, jobs=None):
        self.jobs = dict(jobs or {})
        self.get_calls: list[UUID] = []
        self.claim_next_calls = 0
        self.claim_calls: list[UUID] = []
        self.renew_calls: list[tuple[UUID, datetime]] = []
        self._claim_started_at = datetime(
            2026, 11, 4, tzinfo=timezone.utc
        )

    def get(self, job_id):
        self.get_calls.append(job_id)
        return self.jobs.get(job_id)

    def _claim(self, job):
        if job is None or job.get("status") not in ("pending", "retryable"):
            return None
        job.update({
            "status": "claimed",
            "started_at": self._claim_started_at,
            "current_stage": "queued",
        })
        return dict(job)

    def claim(self, job_id):
        self.claim_calls.append(job_id)
        return self._claim(self.jobs.get(job_id))

    def claim_next(self):
        self.claim_next_calls += 1
        eligible = [
            job
            for job in self.jobs.values()
            if job.get("artifact_id") is not None
            and job.get("status") in ("pending", "retryable")
        ]
        eligible.sort(key=lambda job: job.get("created_at", 0))
        return self._claim(eligible[0] if eligible else None)

    def renew_claim(self, job_id, claim_started_at):
        self.renew_calls.append((job_id, claim_started_at))
        job = self.jobs.get(job_id)
        if (
            job is None
            or job.get("status") not in ("claimed", "processing")
            or job.get("started_at") != claim_started_at
        ):
            return None
        return {"id": job_id}


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

    def test_process_pending_job_is_atomically_claimed_before_extraction(self):
        job_repo = FakeJobRepo(
            {self.job: {"id": self.job, "artifact_id": self.artifact,
                        "source_id": self.source, "status": "pending"}}
        )
        extraction_service = FakeExtractionService()
        worker = self._make_worker(job_repo, extraction_service)

        worker._poll_cycle()

        self.assertEqual(len(extraction_service.calls), 1)
        call = extraction_service.calls[0]
        self.assertEqual(call["actor_user_id"], self.actor)
        self.assertEqual(call["source_id"], self.source)
        self.assertEqual(call["artifact_id"], self.artifact)
        self.assertEqual(call["job_id"], self.job)
        self.assertEqual(call["claim_started_at"], job_repo._claim_started_at)
        self.assertEqual(job_repo.claim_next_calls, 1)
        self.assertEqual(job_repo.jobs[self.job]["status"], "claimed")

    def test_placeholder_is_not_claimed_or_processed(self):
        job_repo = FakeJobRepo(
            {self.job: {"id": self.job, "artifact_id": None,
                        "source_id": self.source, "status": "pending"}}
        )
        extraction_service = FakeExtractionService()
        worker = self._make_worker(job_repo, extraction_service)

        worker._poll_cycle()

        self.assertEqual(len(extraction_service.calls), 0)
        self.assertEqual(job_repo.jobs[self.job]["status"], "pending")

    def test_process_missing_job_is_noop(self):
        job_repo = FakeJobRepo({})
        extraction_service = FakeExtractionService()
        worker = self._make_worker(job_repo, extraction_service)

        worker._poll_cycle()

        self.assertEqual(len(extraction_service.calls), 0)

    def test_extraction_failure_is_logged_without_completing_claim(self):
        job_repo = FakeJobRepo(
            {self.job: {"id": self.job, "artifact_id": self.artifact,
                        "source_id": self.source, "status": "pending"}}
        )
        extraction_service = FakeExtractionService(should_fail=True)
        worker = self._make_worker(job_repo, extraction_service)

        with self.assertLogs(
                "xportra.application.regulatory_ingestion_worker",
                level="ERROR") as captured:
            worker._poll_cycle()

        self.assertEqual(len(extraction_service.calls), 1)
        self.assertIn("RuntimeError", "\n".join(captured.output))
        self.assertEqual(job_repo.jobs[self.job]["status"], "claimed")

    def test_unauthorized_worker_skips_processing(self):
        job_repo = FakeJobRepo(
            {self.job: {"id": self.job, "artifact_id": self.artifact,
                        "source_id": self.source, "status": "pending"}}
        )
        extraction_service = FakeExtractionService()
        worker = self._make_worker(job_repo, extraction_service, granted=False)

        worker._poll_cycle()

        self.assertEqual(len(extraction_service.calls), 0)
        self.assertEqual(job_repo.claim_next_calls, 0)

    def test_process_retryable_job(self):
        job_repo = FakeJobRepo(
            {self.job: {"id": self.job, "artifact_id": self.artifact,
                        "source_id": self.source, "status": "retryable"}}
        )
        extraction_service = FakeExtractionService()
        worker = self._make_worker(job_repo, extraction_service)

        worker._poll_cycle()

        self.assertEqual(len(extraction_service.calls), 1)
        self.assertEqual(extraction_service.calls[0]["job_id"], self.job)
        self.assertEqual(job_repo.jobs[self.job]["status"], "claimed")


class TestWorkerClaimContention(TestCase):
    def test_second_claim_attempt_cannot_claim_already_claimed_job(self):
        job_id = UUID("ffffffff-0000-0000-0000-000000000006")
        artifact_id = UUID("eeeeeeee-0000-0000-0000-000000000005")
        job_repo = FakeJobRepo({
            job_id: {
                "id": job_id,
                "artifact_id": artifact_id,
                "status": "pending",
            }
        })

        first_claim = job_repo.claim(job_id)
        second_claim = job_repo.claim(job_id)

        self.assertIsNotNone(first_claim)
        self.assertIsNone(second_claim)
        self.assertEqual(job_repo.jobs[job_id]["status"], "claimed")

    def test_lease_heartbeat_renews_claim_during_processing(self):
        job_id = UUID("ffffffff-0000-0000-0000-000000000006")
        claim_started_at = datetime(2026, 11, 4, tzinfo=timezone.utc)
        job_repo = FakeJobRepo({
            job_id: {
                "id": job_id,
                "status": "claimed",
                "started_at": claim_started_at,
            }
        })
        worker = RegulatoryIngestionWorker(FakeDB(), job_repo=job_repo)
        stop_event = threading.Event()
        heartbeat = threading.Thread(
            target=worker._renew_claim_lease,
            args=(job_id, claim_started_at, stop_event),
        )

        with patch(
                "xportra.application.regulatory_ingestion_worker."
                "LEASE_TIMEOUT_SECONDS", 0.3):
            heartbeat.start()
            time.sleep(0.25)
            stop_event.set()
            heartbeat.join(timeout=1)

        self.assertFalse(heartbeat.is_alive())
        self.assertGreaterEqual(len(job_repo.renew_calls), 1)


class PollQueryExcludesPlaceholderJobsTests(TestCase):
    def setUp(self):
        self.actor = UUID("aaaaaaaa-0000-0000-0000-000000000001")
        self.source = UUID("dddddddd-0000-0000-0000-000000000004")
        self.artifact = UUID("eeeeeeee-0000-0000-0000-000000000005")
        self.placeholder = UUID("ffffffff-0000-0000-0000-000000000006")
        self.valid_job = UUID("ffffffff-0000-0000-0000-000000000007")

    def _job(self, job_id, artifact_id, status, created_at):
        return {
            "id": job_id,
            "artifact_id": artifact_id,
            "source_id": self.source,
            "status": status,
            "created_at": created_at,
        }

    def _poll(self, jobs):
        job_repo = FakeJobRepo({job["id"]: job for job in jobs})
        extraction_service = FakeExtractionService()
        worker = RegulatoryIngestionWorker(
            FakeDB(),
            extraction_service=extraction_service,
            job_repo=job_repo,
        )
        worker._actor_id = self.actor
        worker._grants = FakeGrantRepo({
            (self.actor, GRANT_MANAGE): True
        })

        worker._poll_cycle()
        return job_repo, extraction_service

    def test_pending_registration_placeholder_is_skipped_and_unchanged(self):
        placeholder = self._job(self.placeholder, None, "pending", 1)

        job_repo, extraction_service = self._poll([placeholder])

        self.assertEqual(extraction_service.calls, [])
        self.assertEqual(job_repo.claim_next_calls, 1)
        self.assertEqual(placeholder["status"], "pending")

    def test_pending_job_with_artifact_is_selected(self):
        valid = self._job(self.valid_job, self.artifact, "pending", 1)

        _, extraction_service = self._poll([valid])

        self.assertEqual(
            [call["job_id"] for call in extraction_service.calls],
            [self.valid_job],
        )

    def test_placeholder_cannot_starve_valid_ingestion_job(self):
        placeholder = self._job(self.placeholder, None, "pending", 1)
        valid = self._job(self.valid_job, self.artifact, "pending", 2)

        _, extraction_service = self._poll([placeholder, valid])

        self.assertEqual(
            [call["job_id"] for call in extraction_service.calls],
            [self.valid_job],
        )
        self.assertEqual(placeholder["status"], "pending")

    def test_retryable_artifact_job_remains_selectable(self):
        retryable = self._job(
            self.valid_job, self.artifact, "retryable", 1
        )

        _, extraction_service = self._poll([retryable])

        self.assertEqual(
            [call["job_id"] for call in extraction_service.calls],
            [self.valid_job],
        )
