"""PostgreSQL-backed ingestion worker — disabled; processing occurs
directly from artifact upload per the simplified pipeline (Task 4D.10).

This module is preserved for backward compatibility and import
compatibility but the active ingestion path no longer depends on
polling ``regulatory_ingestion_jobs`` or driving stage-gated
extraction.  Document upload via ``RegulatorySourceIntakeService``
triggers the complete processing pipeline directly.
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
# require new secrets or infrastructure.  The worker is effectively
# disabled in the simplified pipeline — processing is driven by
# ``RegulatorySourceIntakeService`` uploads.
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
    """PostgreSQL-backed polling ingestion worker (disabled).

    The active regulatory ingestion pipeline no longer depends on this
    worker.  Document processing is triggered directly by
    ``RegulatorySourceIntakeService`` artifact uploads.  This class
    is retained for import compatibility and potential manual
    reconciliation, but ``start()`` is a no‑op and ``_poll_cycle()``
    performs no job claiming or processing.
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
            and self._llm_client is not None
            and self._llm_configuration is not None
        )
        self._publication_indexer = publication_indexer
        self._running = False
        self._poll_task: asyncio.Task[Any] | None = None

    # ── startup / shutdown ──────────────────────────────────────
    def _is_authorized(self) -> bool:
        return self.startup_skip_reason() is None

    def startup_skip_reason(self) -> str | None:
        """In the simplified pipeline the worker is always skipped."""
        return (
            "REGULATORY_INGESTION_WORKER_DISABLED: "
            "active ingestion pipeline driven by artifact upload, not worker polling"
        )

    def startup_skip_reason_classic(self) -> str | None:
        """Classic skip reason (for reference only)."""
        if self._actor_id is None:
            return "REGULATORY_WORKER_ACTOR_USER_ID is missing or invalid"
        if not self._grants.is_granted(self._actor_id, GRANT_MANAGE):
            return "configured worker actor lacks an active GRANT_MANAGE grant"
        if not self._can_extract and self._publication_indexer is None:
            return "no configured regulatory worker capability is available"
        return None

    def start(self) -> None:
        """No-op: the simplified pipeline does not use a background worker."""
        self._running = False
        logger.info(
            "Regulatory ingestion worker startup skipped: "
            "pipeline driven by artifact upload, not worker polling"
        )

    def stop(self) -> None:
        """No-op."""
        pass

    # ── poll cycle ─────────────────────────────────────────────
    def _poll_cycle(self) -> None:
        """No-op: the simplified pipeline does not claim or process jobs."""
        logger.debug(
            "Regulatory ingestion poll cycle skipped: pipeline driven "
            "by artifact upload, not worker polling"
        )

    async def _poll_loop(self) -> None:
        """No-op async poll loop."""
        while self._running:
            try:
                await asyncio.sleep(
                    int(os.environ.get("REGULATORY_INGESTION_POLL_INTERVAL", "30"))
                )
            except asyncio.CancelledError:
                break

    # ── lease recovery ─────────────────────────────────────────
    def _recover_expired_lease(self) -> int:
        """No-op: lease recovery is not applicable in the simplified pipeline."""
        return 0

    # ── job claim / complete / fail / retry ─────────────────────
    def claim_job(self, job_id: UUID, actor_user_id: UUID) -> Any:
        """Not used in the simplified pipeline."""
        from xportra.api.errors import PermissionDeniedError
        raise PermissionDeniedError(
            "job claiming is not active in the simplified pipeline"
        )

    def complete_job(
        self, job_id: UUID, actor_user_id: UUID | None = None,
        claim_started_at: datetime | None = None,
    ) -> Any:
        """Not used in the simplified pipeline."""
        from xportra.api.errors import PermissionDeniedError
        raise PermissionDeniedError(
            "job completion is not active in the simplified pipeline"
        )

    def fail_job(
        self, job_id: UUID,
        error_details: str | None = None,
        make_retryable: bool = False,
        actor_user_id: UUID | None = None,
        claim_started_at: datetime | None = None,
    ) -> Any:
        """Not used in the simplified pipeline."""
        from xportra.api.errors import PermissionDeniedError
        raise PermissionDeniedError(
            "job failure is not active in the simplified pipeline"
        )

    def retry_job(self, job_id: UUID, actor_user_id: UUID) -> Any:
        """Not used in the simplified pipeline."""
        from xportra.api.errors import PermissionDeniedError
        raise PermissionDeniedError(
            "job retry is not active in the simplified pipeline"
        )