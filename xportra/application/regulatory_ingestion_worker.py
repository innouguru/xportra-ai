"""PostgreSQL-backed ingestion worker for Phase 4D.10 Task 3B.

Runs within the existing FastAPI process (no Docker, no new external
queue, no new paid service). Uses the database as the source of truth.
Polls `regulatory_ingestion_jobs` atomically, claims eligible work, and
drives each job through the existing candidate-extraction pipeline
(parse → normalize → extract → persist) so that a pending job becomes a
durable processing outcome (completed or failed/retryable). Handles
bounded retries, safe shutdown, and crash recovery via lease-timeout
reset.

The worker does not invent a new authorization model; it requires a
configured service identity (`actor_user_id`) that holds an active
`GRANT_MANAGE` grant. If the identity is missing or ungranted, the
worker skips execution (fail-closed) rather than creating a new
permission mechanism.

This mechanism is the smallest viable option under the current
Render/no-Docker/budget constraints (ADR-0017 §3, deployment audit
`XPORTA-V1-DEPLOYMENT.md` §14). It does not claim exactly-once
delivery — safe retries and idempotency through attempt numbering
are the current contract. A product-owner decision remains required
before selecting a dedicated worker identity or full background
execution framework.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any
from uuid import UUID

from xportra.application.global_staff import GlobalStaffGrantService, GRANT_MANAGE
from xportra.application.regulatory_candidate_extraction_service import (
    RegulatoryCandidateExtractionService,
)
from xportra.persistence.database import Database
from xportra.persistence.repositories import (
    RegulatoryIngestionJobRepository,
)

logger = logging.getLogger(__name__)

# Safe defaults; can be overridden by environment variables but never
# require new secrets or infrastructure. The worker skips execution
# if no configured identity or grant is found.
POLL_INTERVAL_SECONDS = int(os.environ.get("REGULATORY_INGESTION_POLL_INTERVAL", "30"))
LEASE_TIMEOUT_SECONDS = int(os.environ.get("REGULATORY_INGESTION_LEASE_TIMEOUT", "300"))


def _configured_service_actor_user_id() -> UUID | None:
    raw = os.environ.get("REGULATORY_WORKER_ACTOR_USER_ID", "").strip()
    if not raw:
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


class RegulatoryIngestionWorker:
    """PostgreSQL-backed polling ingestion worker (in-process, bounded).

    Discovers pending/retryable ingestion jobs and drives each one
    through the candidate-extraction pipeline. Jobs without an artifact
    (source-registration placeholders created by
    ``RegulatorySourceIntakeService.register_source``) are skipped: they
    have no content to process and remain pending until an artifact is
    uploaded, which creates its own job.
    """

    def __init__(
        self,
        database: Database,
        *,
        extraction_service: Any | None = None,
        job_repo: RegulatoryIngestionJobRepository | None = None,
    ) -> None:
        self._database = database
        self._jobs = job_repo or RegulatoryIngestionJobRepository(database)
        self._grants = GlobalStaffGrantService(database)
        self._actor_id = _configured_service_actor_user_id()
        self._running = False
        self._poll_task: asyncio.Task[Any] | None = None
        self._extraction_service_factory = (
            extraction_service
            if extraction_service is not None
            else lambda db: RegulatoryCandidateExtractionService(db)
        )

    def _is_authorized(self) -> bool:
        if self._actor_id is None:
            return False
        return self._grants.is_granted(self._actor_id, GRANT_MANAGE)

    def _recover_expired_lease(self) -> int:
        """Reset claimed/processing jobs whose lease (lease timeout after
        ``started_at``) has expired. Executed at worker startup so a
        crashed worker's in-flight jobs become retryable again instead of
        being wedged forever. Uses ``make_interval`` with a bound
        parameter so the timeout is passed as data, not string-spliced.
        """
        if not self._is_authorized():
            return 0
        with self._database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE xportra.regulatory_ingestion_jobs
                    SET status = 'retryable',
                        completed_at = NULL,
                        error_details = 'lease_expired_recovery',
                        updated_at = now()
                    WHERE status IN ('claimed', 'processing')
                      AND started_at IS NOT NULL
                      AND started_at < now() - make_interval(secs => %s)
                    RETURNING id
                    """,
                    (LEASE_TIMEOUT_SECONDS,),
                )
                expired_rows = cursor.fetchall()
                return len(expired_rows)

    def _poll_cycle(self) -> None:
        if not self._is_authorized():
            logger.warning(
                "Regulatory ingestion worker skipped: no configured service identity or active grant_manage grant."
            )
            return
        # Reserve one eligible job without changing its status. The
        # extraction service performs the atomic claim
        # (pending/retryable -> claimed) and drives the job to
        # completion or failure. Holding a DB lock across the service
        # call would risk deadlocks, so the reservation transaction is
        # committed before processing.
        job_id: UUID | None = None
        with self._database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM xportra.regulatory_ingestion_jobs WHERE status IN ('pending', 'retryable') ORDER BY created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED"
                )
                row = cursor.fetchone()
                if row is None:
                    return
                job_id = row[0]
        # Lock released; process outside the transaction.
        if job_id is not None:
            self._process_job(job_id)

    def _process_job(self, job_id: UUID) -> None:
        if not self._is_authorized():
            return
        job = self._jobs.get(job_id)
        if job is None:
            return
        # Source-registration placeholders have no artifact to process.
        if not job.get("artifact_id"):
            return
        service = self._extraction_service_factory(self._database)
        try:
            service.extract_candidates(
                actor_user_id=self._actor_id,
                source_id=job["source_id"],
                artifact_id=job["artifact_id"],
                job_id=job_id,
            )
        except Exception as exc:  # noqa: BLE001
            # The extraction service marks the job retryable/failed for
            # recoverable errors; unexpected errors are logged so the
            # job stays visible for operator inspection rather than
            # being falsely completed.
            logger.exception(
                "Ingestion job %s failed during extraction: %s", job_id, exc
            )

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        # Crash recovery on startup: reset expired claims before polling.
        reset_count = self._recover_expired_lease()
        if reset_count > 0:
            logger.info("Regulatory ingestion worker recovered %d expired lease(s)", reset_count)
        # Start bounded polling loop (asynchronous, non-blocking to request handling).
        loop = asyncio.get_event_loop()
        self._poll_task = loop.create_task(self._poll_loop())

    async def _poll_loop(self) -> None:
        while self._running:
            try:
                self._poll_cycle()
            except Exception as exc:  # noqa: BLE001
                logger.exception("Regulatory ingestion poll cycle failed: %s", exc)
            try:
                await asyncio.sleep(POLL_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                break

    def stop(self) -> None:
        self._running = False
        if self._poll_task is not None:
            self._poll_task.cancel()
