"""Minimal regulatory ingestion job lifecycle.

Only the job persistence boundary is implemented; actual parsing/extraction
remains deferred to the direct processing path (``RegulatorySourceIntakeService``).
No background worker mechanism is selected; this service creates durable
records that a future worker would claim if the old orchestration is re-enabled.

The active ingestion pipeline does not require this service — document upload
via ``RegulatorySourceIntakeService`` triggers the complete processing pipeline
directly.  This service is retained for compatibility with existing job records
and retrospective analysis.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
)
from xportra.application.global_staff import GlobalStaffGrantService, GRANT_MANAGE
from xportra.persistence.repositories import (
    RegulatoryIngestionJobRepository,
)
from xportra.persistence.database import Database
from xportra.persistence.errors import PersistenceIntegrityError

#: Maximum worker-driven retryable-failure cycles per ingestion attempt.
#: Each retryable failure increments ``retry_count``; when a further
#: failure would exceed the bound the attempt becomes terminally
#: ``failed``.  A separately authorized staff retry control (retry_job)
#: records a NEW attempt row and resets the counter — prior attempts
#: remain immutable history.  The bound prevents unbounded automatic
#: retries of a persistently failing artifact.  In the simplified pipeline
#: this cap is informational only; retry logic resides in the extraction
#: service, not the job lifecycle.
MAX_RETRY_ATTEMPTS = 5


class RegulatoryIngestionService:
    """Minimal ingestion job lifecycle with global-staff authorization.

    Retained for compatibility with existing ``regulatory_ingestion_jobs``
    rows and staff-managed retries.  The active ingestion pipeline
    (``RegulatorySourceIntakeService.upload_artifact`` / ``enter_text_artifact``)
    does not call any method on this service — processing occurs directly.
    """

    def __init__(self, database: Database) -> None:
        self._database = database
        self._job_repo = RegulatoryIngestionJobRepository(database)
        self._grant_service = GlobalStaffGrantService(database)

    def start_ingestion(
        self,
        artifact_id: UUID,
        source_id: UUID,
        actor_user_id: UUID,
        audit_ref: str | None = None,
        parser_version: str = "v1",
    ) -> Any:
        """Not used in the active pipeline.

        The simplified ingestion path does not create jobs via this service;
        artifacts are processed directly by ``RegulatorySourceIntakeService``.
        """
        if not self._grant_service.is_granted(actor_user_id, GRANT_MANAGE):
            from xportra.api.errors import PermissionDeniedError
            raise PermissionDeniedError()
        return self._job_repo.create(
            artifact_id=artifact_id,
            source_id=source_id,
            actor_user_id=actor_user_id,
            audit_ref=audit_ref,
            parser_version=parser_version,
        )

    def claim_job(self, job_id: UUID, actor_user_id: UUID) -> Any:
        """Not used in the active pipeline."""
        from xportra.api.errors import PermissionDeniedError
        raise PermissionDeniedError(
            "job claiming is not active in the simplified pipeline"
        )

    def complete_job(
        self,
        job_id: UUID,
        actor_user_id: UUID | None = None,
        claim_started_at: datetime | None = None,
    ) -> Any:
        """Not used in the active pipeline."""
        from xportra.api.errors import PermissionDeniedError
        raise PermissionDeniedError(
            "job completion is not active in the simplified pipeline"
        )

    def fail_job(
        self,
        job_id: UUID,
        error_details: str | None = None,
        make_retryable: bool = False,
        actor_user_id: UUID | None = None,
        claim_started_at: datetime | None = None,
    ) -> Any:
        """Not used in the active pipeline."""
        from xportra.api.errors import PermissionDeniedError
        raise PermissionDeniedError(
            "job failure is not active in the simplified pipeline"
        )

    def retry_job(self, job_id: UUID, actor_user_id: UUID) -> Any:
        """Not used in the active pipeline."""
        from xportra.api.errors import PermissionDeniedError
        raise PermissionDeniedError(
            "job retry is not active in the simplified pipeline"
        )