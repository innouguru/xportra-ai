"""Durable regulatory ingestion job lifecycle — minimal contract.

Only the job persistence and authorization boundary are implemented.
Actual parsing/extraction remains deferred to later Phase 4D tasks
(ADR-0017 §3, §4). No background worker mechanism is selected; this
service creates durable records that a future worker would claim.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from xportra.application.global_staff import GlobalStaffGrantService, GRANT_MANAGE
from xportra.application.global_staff import GlobalStaffGrantService
from xportra.persistence.repositories import (
    RegulatorySourceArtifactRepository,
    RegulatoryIngestionJobRepository,
)
from xportra.persistence.database import Database


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
        return self._job_repo.complete(job_id, actor_user_id)

    def fail_job(
        self,
        job_id: UUID,
        error_details: str | None = None,
        make_retryable: bool = False,
        actor_user_id: UUID | None = None,
    ) -> Any:
        return self._job_repo.fail(
            job_id,
            error_details=error_details,
            make_retryable=make_retryable,
            actor_user_id=actor_user_id,
        )
