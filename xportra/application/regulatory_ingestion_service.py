"""Durable regulatory ingestion job lifecycle — minimal contract.

Only the job persistence and authorization boundary are implemented.
Actual parsing/extraction remains deferred to later Phase 4D tasks
(ADR-0017 §3, §4). No background worker mechanism is selected; this
service creates durable records that a future worker would claim.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
)
from xportra.application.global_staff import GlobalStaffGrantService, GRANT_MANAGE
from xportra.application.global_staff import GlobalStaffGrantService
from xportra.persistence.repositories import (
    RegulatorySourceArtifactRepository,
    RegulatoryIngestionJobRepository,
)
from xportra.persistence.database import Database
from xportra.persistence.errors import PersistenceIntegrityError

#: Maximum worker-driven retryable-failure cycles per ingestion attempt.
#: Each retryable failure increments ``retry_count``; when a further
#: failure would exceed the bound the attempt becomes terminally
#: ``failed``. A separately authorized staff retry control (retry_job)
#: records a NEW attempt row and resets the counter — prior attempts
#: remain immutable history. The bound prevents unbounded automatic
#: retries of a persistently failing artifact.
MAX_RETRY_ATTEMPTS = 5


class RegulatoryIngestionService:
    """Durable ingestion job lifecycle with global-staff authorization."""

    def __init__(self, database: Database) -> None:
        self._database = database
        self._artifact_repo = RegulatorySourceArtifactRepository(database)
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
        # Authorization is enforced server-side by the caller using
        # require_global_staff; this service verifies explicitly
        # rather than trusting the request.
        if not self._grant_service.is_granted(actor_user_id, GRANT_MANAGE):
            from xportra.api.errors import PermissionDeniedError
            raise PermissionDeniedError()
        # Idempotency: duplicate byte-level ingestion is handled at
        # the artifact layer (content_hash + source identity); the
        # job layer creates a new attempt for each retry.
        return self._job_repo.create(
            artifact_id=artifact_id,
            source_id=source_id,
            actor_user_id=actor_user_id,
            audit_ref=audit_ref,
            parser_version=parser_version,
        )

    def claim_job(self, job_id: UUID, actor_user_id: UUID) -> Any:
        if not self._grant_service.is_granted(actor_user_id, GRANT_MANAGE):
            from xportra.api.errors import PermissionDeniedError
            raise PermissionDeniedError()
        return self._job_repo.claim(job_id, actor_user_id)

    def complete_job(self, job_id: UUID, actor_user_id: UUID | None = None) -> Any:
        if actor_user_id is None:
            from xportra.api.errors import PermissionDeniedError
            raise PermissionDeniedError()
        if not self._grant_service.is_granted(actor_user_id, GRANT_MANAGE):
            from xportra.api.errors import PermissionDeniedError
            raise PermissionDeniedError()
        return self._job_repo.complete(job_id, actor_user_id)

    def fail_job(
        self,
        job_id: UUID,
        error_details: str | None = None,
        make_retryable: bool = False,
        actor_user_id: UUID | None = None,
    ) -> Any:
        if actor_user_id is None:
            from xportra.api.errors import PermissionDeniedError
            raise PermissionDeniedError()
        if not self._grant_service.is_granted(actor_user_id, GRANT_MANAGE):
            from xportra.api.errors import PermissionDeniedError
            raise PermissionDeniedError()
        return self._job_repo.fail(
            job_id,
            error_details=error_details,
            make_retryable=make_retryable,
            actor_user_id=actor_user_id,
        )

    def retry_job(self, job_id: UUID, actor_user_id: UUID) -> Any:
        """Record a new bounded, authorized retry attempt for a failed job.

        Requires an active ``GRANT_MANAGE`` grant. Only terminally
        ``failed`` jobs can be retried this way (``retryable`` jobs are
        automatically reclaimed by the worker; actively claimed or
        processing jobs must not be disturbed). The retry is a NEW
        attempt row linked to the same artifact (``attempt_number`` =
        next attempt after the recorded maximum), so prior attempts
        remain immutable history. Capped at :data:`MAX_RETRY_ATTEMPTS`
        recorded attempts per artifact; a concurrent duplicate retry is
        idempotently resolved to the same new attempt row.
        """
        from xportra.api.errors import PermissionDeniedError

        if actor_user_id is None:
            raise PermissionDeniedError()
        if not self._grant_service.is_granted(actor_user_id, GRANT_MANAGE):
            raise PermissionDeniedError()

        job = self._job_repo.get(job_id)
        if job is None:
            raise ApplicationNotFoundError("ingestion job not found")
        if job.get("status") != "failed":
            raise ApplicationValidationError(
                f"ingestion job status is '{job.get('status')}'; only a "
                "terminally failed job can be retried by staff (retryable "
                "jobs are picked up by the worker automatically)"
            )

        max_attempt = self._job_repo.max_attempts_for_artifact(job["artifact_id"])
        if max_attempt >= MAX_RETRY_ATTEMPTS:
            raise ApplicationValidationError(
                f"retry limit reached: {max_attempt} attempts are already "
                f"recorded for this artifact (limit {MAX_RETRY_ATTEMPTS})"
            )
        next_attempt = max_attempt + 1
        try:
            return self._job_repo.create(
                artifact_id=job["artifact_id"],
                source_id=job["source_id"],
                actor_user_id=actor_user_id,
                audit_ref=job.get("audit_ref"),
                parser_version=job.get("parser_version") or "v1",
                attempt_number=next_attempt,
            )
        except PersistenceIntegrityError as exc:
            # Concurrent duplicate retry: reconcile idempotently to the
            # single attempt row that already exists (or surface the error).
            existing = self._job_repo.get_by_artifact_attempt(
                job["artifact_id"], next_attempt
            )
            if existing is not None:
                return existing
            raise
