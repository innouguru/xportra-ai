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
import threading
from datetime import datetime
from typing import Any
from uuid import UUID

from xportra.application.global_staff import GlobalStaffGrantService, GRANT_MANAGE
from xportra.application.regulatory_candidate_extraction_service import (
    IngestionClaimLostError,
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
        publication_indexer: Any | None = None,
        llm_client: Any | None = None,
        llm_configuration: Any | None = None,
    ) -> None:
        self._database = database
        self._jobs = job_repo or RegulatoryIngestionJobRepository(database)
        self._grants = GlobalStaffGrantService(database)
        self._actor_id = _configured_service_actor_user_id()
        self._llm_client = llm_client
        self._llm_configuration = llm_configuration
        self._uses_default_extraction = extraction_service is None
        self._can_extract = (
            not self._uses_default_extraction
            or (
                self._llm_client is not None
                and self._llm_configuration is not None
            )
        )
        self._publication_indexer = publication_indexer
        self._running = False
        self._poll_task: asyncio.Task[Any] | None = None
        self._extraction_service_factory = (
            extraction_service
            if extraction_service is not None
            else lambda db: RegulatoryCandidateExtractionService(
                db,
                llm_client=self._llm_client,
                llm_configuration=self._llm_configuration,
            )
        )

    def _is_authorized(self) -> bool:
        return self.startup_skip_reason() is None

    def startup_skip_reason(self) -> str | None:
        if self._actor_id is None:
            return "REGULATORY_WORKER_ACTOR_USER_ID is missing or invalid"
        if not self._grants.is_granted(self._actor_id, GRANT_MANAGE):
            return "configured worker actor lacks an active GRANT_MANAGE grant"
        if not self._can_extract and self._publication_indexer is None:
            return "no configured regulatory worker capability is available"
        return None

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
                        current_stage = 'queued',
                        stage_updated_at = clock_timestamp(),
                        updated_at = now()
                    WHERE status IN ('claimed', 'processing')
                      AND COALESCE(updated_at, started_at) < now()
                          - make_interval(secs => %s)
                    RETURNING id
                    """,
                    (LEASE_TIMEOUT_SECONDS,),
                )
                expired_rows = cursor.fetchall()
                return len(expired_rows)

    def _poll_cycle(self) -> None:
        skip_reason = self.startup_skip_reason()
        if skip_reason is not None:
            logger.warning("Regulatory ingestion worker skipped: %s.", skip_reason)
            return
        if self._publication_indexer is not None:
            try:
                self._publication_indexer.process_next()
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Regulatory publication indexing poll failed (%s).",
                    type(exc).__name__,
                )
        if self._can_extract:
            claimed_job = self._jobs.claim_next()
            if claimed_job is not None:
                self._process_job(claimed_job)

    def _process_job(self, claimed_job: dict[str, Any]) -> None:
        if not self._is_authorized():
            return
        job_id = claimed_job["id"]
        if not claimed_job.get("artifact_id"):
            return
        stop_heartbeat = threading.Event()
        heartbeat = threading.Thread(
            target=self._renew_claim_lease,
            args=(job_id, claimed_job["started_at"], stop_heartbeat),
            daemon=True,
        )
        heartbeat.start()
        try:
            service = self._extraction_service_factory(self._database)
            service.extract_candidates(
                actor_user_id=self._actor_id,
                source_id=claimed_job["source_id"],
                artifact_id=claimed_job["artifact_id"],
                job_id=job_id,
                claim_started_at=claimed_job["started_at"],
            )
        except IngestionClaimLostError:
            logger.info(
                "Ingestion job %s processing stopped because its claim expired.",
                job_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Ingestion job %s failed during extraction (%s).",
                job_id,
                type(exc).__name__,
            )
        finally:
            stop_heartbeat.set()
            heartbeat.join()

    def _renew_claim_lease(
        self,
        job_id: UUID,
        claim_started_at: datetime,
        stop_event: threading.Event,
    ) -> None:
        interval = max(0.1, min(LEASE_TIMEOUT_SECONDS / 3, 60))
        while not stop_event.wait(interval):
            try:
                if self._jobs.renew_claim(job_id, claim_started_at) is None:
                    logger.info(
                        "Ingestion job %s lease renewal stopped because its "
                        "claim is no longer active.",
                        job_id,
                    )
                    return
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Ingestion job %s lease renewal failed (%s).",
                    job_id,
                    type(exc).__name__,
                )

    def start(self) -> None:
        if self._running:
            return
        skip_reason = self.startup_skip_reason()
        if skip_reason is not None:
            logger.warning(
                "Regulatory ingestion worker startup skipped: %s.",
                skip_reason,
            )
            return
        self._running = True
        # Crash recovery on startup: reset expired claims before polling.
        reset_count = (
            self._recover_expired_lease() if self._can_extract else 0)
        if reset_count > 0:
            logger.info("Regulatory ingestion worker recovered %d expired lease(s)", reset_count)
        # Start bounded polling loop (asynchronous, non-blocking to request handling).
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # No event loop available (e.g., in certain test contexts without
            # an active asyncio runtime). The worker will be started when an
            # event loop is available; polling is deferred until then.
            self._poll_task = None
            return
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
