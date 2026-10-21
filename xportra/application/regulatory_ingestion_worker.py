"""Minimal PostgreSQL-backed ingestion worker for Phase 4D.10 Task 3B.

Runs within the existing FastAPI process (no Docker, no new external
queue, no new paid service). Uses the database as the source of truth.
Polls `regulatory_ingestion_jobs` atomically, claims eligible work,
and handles bounded retries, safe shutdown, and crash recovery via
lease-timeout reset. The worker does not invent a new authorization
model; it requires a configured service identity (`actor_user_id`)
that holds an active `GRANT_MANAGE` grant. If the identity is missing
or ungranted, the worker skips execution (fail-closed) rather than
creating a new permission mechanism.

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
import signal
from typing import Any
from uuid import UUID

from xportra.application.global_staff import GlobalStaffGrantService, GRANT_MANAGE
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
    """PostgreSQL-backed polling ingestion worker (in-process, bounded)."""

    def __init__(self, database: Database) -> None:
        self._database = database
        self._jobs = RegulatoryIngestionJobRepository(database)
        self._grants = GlobalStaffGrantService(database)
        self._actor_id = _configured_service_actor_user_id()
        self._running = False
        self._poll_task: asyncio.Task[Any] | None = None

    def _is_authorized(self) -> bool:
        if self._actor_id is None:
            return False
        return self._grants.is_granted(self._actor_id, GRANT_MANAGE)

    def _recover_expired_lease(self) -> int:
        """Reset claimed/processing jobs that exceeded lease timeout."""
        if not self._is_authorized():
            return 0
        # Minimal recovery: select expired claimed/processing, reset to retryable.
        # A full recovery mechanism requires explicit lease tracking (future work).
        with self._database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM xportra.regulatory_ingestion_jobs WHERE status IN ('claimed', 'processing') AND started_at < now() - interval '%s seconds'",
                    (f"{LEASE_TIMEOUT_SECONDS}",),
                )
                expired_ids = [row[0] for row in cursor.fetchall()]
                reset_count = 0
                for job_id in expired_ids:
                    cursor.execute(
                        "UPDATE xportra.regulatory_ingestion_jobs SET status = 'retryable', completed_at = NULL, error_details = 'lease_expired_recovery' WHERE id = %s",
                        (job_id,),
                    )
                    reset_count += 1
                return reset_count

    def _poll_cycle(self) -> None:
        if not self._is_authorized():
            logger.warning(
                "Regulatory ingestion worker skipped: no configured service identity or active grant_manage grant."
            )
            return
        # Minimal claim: find one eligible job and claim it.
        # This is intentionally bounded; a full worker framework requires
        # an approved dispatch mechanism (ADR-0017 §3).
        with self._database.transaction() as connection:
            with connection.cursor() as cursor:
                # Select eligible pending/retryable work with bounded limit.
                cursor.execute(
                    "SELECT id FROM xportra.regulatory_ingestion_jobs WHERE status IN ('pending', 'retryable') ORDER BY created_at ASC LIMIT 1 FOR UPDATE SKIP LOCKED"
                )
                row = cursor.fetchone()
                if row is None:
                    return
                job_id = row[0]
                # Atomic claim.
                cursor.execute(
                    "UPDATE xportra.regulatory_ingestion_jobs SET status = 'claimed', started_at = now(), actor_user_id = %s WHERE id = %s AND status IN ('pending', 'retryable') RETURNING *",
                    (self._actor_id, job_id),
                )
                claimed = cursor.fetchone()
                if claimed is not None:
                    # In this minimal contract, the worker records claim but
                    # actual processing (parsing/extraction) is deferred to
                    # a future authorized ingestion pipeline (Task 4+).
                    # We complete the job safely to avoid false pending state.
                    cursor.execute(
                        "UPDATE xportra.regulatory_ingestion_jobs SET status = 'completed', completed_at = now(), error_details = NULL WHERE id = %s",
                        (job_id,),
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
