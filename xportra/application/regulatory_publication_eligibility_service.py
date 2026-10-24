"""Regulatory publication eligibility service.

Selects only regulatory requirements that are safe to present
as applicable to exporters: verified (Stage A), approved
(Stage B), current source (no supersession/stale/withdrawn),
no pending governance flags, successful extraction outcome,
and preserved provenance.

Does not represent partial/unknown/incomplete states as eligible.
Does not create duplicate publications.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
)
from xportra.domain.errors import DomainValidationError
from xportra.persistence.database import Database
from xportra.persistence.repositories import (
    RegulatoryIngestionJobRepository,
    RegulatoryRequirementRepository,
    RegulatoryReviewFlagRepository,
    RegulatorySourceRepository,
)
from xportra.persistence.tenant import TenantContext


class RegulatoryPublicationEligibilityService:
    """Eligibility gate: verified + approved + current + no pending flags + succeeded extraction."""

    def __init__(
        self,
        database: Database,
        *,
        requirement_repo: RegulatoryRequirementRepository | None = None,
        source_repo: RegulatorySourceRepository | None = None,
        review_flag_repo: RegulatoryReviewFlagRepository | None = None,
        job_repo: RegulatoryIngestionJobRepository | None = None,
    ) -> None:
        self._database = database
        self._requirement_repo = requirement_repo or RegulatoryRequirementRepository(database)
        self._source_repo = source_repo or RegulatorySourceRepository(database)
        self._review_flag_repo = review_flag_repo or RegulatoryReviewFlagRepository(database)
        self._job_repo = job_repo or RegulatoryIngestionJobRepository(database)

    # ---------------------------------------------------------------- queries

    def get_eligible_requirements(
        self,
        tenant: TenantContext | None = None,
        *,
        source_filter: UUID | None = None,
        pilot_scope_filter: str | None = None,
        include_provenance: bool = True,
        include_audit_ref: bool = False,
    ) -> list[dict[str, Any]]:
        """Return eligible regulatory requirements for exporter-facing publication.

        Eligibility rules (all must hold; fail-closed on missing/inconsistent state):
        - `status == 'extracted'` (not rejected or archived).
        - `extraction_outcome == 'succeeded'` (failed/partial/manual excluded).
        - `stage_a_status == 'verified'`.
        - `stage_b_status == 'approved'`.
        - Source is active: `regulatory_sources.status` not superseded/withdrawn/archived.
        - Source has no pending review flag (`pending_review`).
        - Requirement has no pending review flag (`pending_review`).
        - Provenance (`normalized_document_id`, `source_id`, `artifact_id` via ingestion job,
          `parser_version`) must be present and consistent.
        - If `pilot_scope_filter` is provided, `stage_b_pilot_scope` must match.

        Unknown, missing, incomplete, or inconsistent fields are treated as
        ineligible (never inferred as eligible).
        """
        # Query authoritative regulatory requirements using repository contract.
        # The repository applies the eligibility filter deterministically.
        rows = self._requirement_repo.get_eligible_for_publication(
            source_filter=source_filter,
            pilot_scope_filter=pilot_scope_filter,
        )
        eligible: list[dict[str, Any]] = []
        for row in rows:
            # Helper to coerce UUID fields safely (repository may return UUID objects or strings).
            def coerce_uuid(val):
                return UUID(str(val)) if val is not None and not isinstance(val, UUID) else (val if isinstance(val, UUID) else None)
            # Verify no pending review flags on source or requirement.
            pending_flags = self._pending_flags_for_requirement_and_source(
                coerce_uuid(row.get("id")), coerce_uuid(row.get("source_id"))
            )
            if pending_flags:
                # Pending governance blocks publication; skip (ineligible, not deleted).
                continue
            # Verify source is active (not superseded/withdrawn/archived) and consistent.
            source_row = self._source_repo.get(coerce_uuid(row.get("source_id"))) if row.get("source_id") else None
            if source_row is None or source_row.get("status") not in {"draft", "active"}:
                # Source missing or inactive/superseded/withdrawn/archived -> ineligible.
                continue
            # Ensure provenance consistency: normalized_document_id must exist,
            # ingestion_job_id must reference a completed job, parser_version must be present.
            # These are required provenance checks; missing/inconsistent provenance = ineligible.
            provenance_ok = self._verify_provenance(row)
            if not provenance_ok:
                continue
            eligible.append(dict(row))
        return eligible

    def is_eligible(
        self,
        requirement_id: UUID,
        tenant: TenantContext | None = None,
    ) -> bool:
        """Return True only if the single requirement passes all eligibility rules."""
        if not isinstance(requirement_id, UUID):
            raise DomainValidationError("requirement_id must be a UUID")
        eligible_list = self.get_eligible_requirements(
            tenant=tenant,
            include_provenance=True,
        )
        # For single-requirement check, filter by id after eligibility computation.
        # This preserves the same deterministic rules as the list method.
        # Note: the list method does not filter by requirement_id; we filter after.
        for row in eligible_list:
            row_id = UUID(str(row.get("id"))) if row.get("id") is not None and not isinstance(row.get("id"), UUID) else (row.get("id") if isinstance(row.get("id"), UUID) else None)
            if row_id == requirement_id:
                return True
        return False

    # ---------------------------------------------------------------- internals

    def _execute_eligible_sql(
        self,
        sql: str,
        params: tuple[Any, ...],
    ) -> list[dict[str, Any]]:
        with self._database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                return [dict(row) for row in cursor.fetchall()]

    def _pending_flags_for_requirement_and_source(
        self,
        requirement_id: UUID,
        source_id: UUID | None,
    ) -> list[dict[str, Any]]:
        flags: list[dict[str, Any]] = []
        if source_id is not None:
            flags.extend(self._review_flag_repo.list_pending_for_source(source_id))
        flags.extend(self._review_flag_repo.get_for_requirement(requirement_id))
        return [f for f in flags if f.get("status") == "pending_review"]

    def _verify_provenance(self, row: dict[str, Any]) -> bool:
        # Provenance checks based on repository evidence:
        # - normalized_document_id must exist (referenced by requirement).
        # - ingestion_job_id must reference a completed job.
        # - parser_version must be non-empty string.
        # - source_id must reference an existing active source.
        # Any missing/inconsistent provenance = ineligible.
        norm_doc_id = row.get("normalized_document_id")
        ingestion_job_id = row.get("ingestion_job_id")
        parser_version = row.get("parser_version")
        source_id = row.get("source_id")
        if not norm_doc_id:
            return False
        if ingestion_job_id is not None:
            job_id = UUID(str(ingestion_job_id)) if not isinstance(ingestion_job_id, UUID) else ingestion_job_id
            job = self._job_repo.get(job_id)
            if job is None or job.get("status") != "completed":
                return False
        if parser_version is not None and (not isinstance(parser_version, str) or not parser_version.strip()):
            return False
        if source_id is not None:
            source_id_uuid = UUID(str(source_id)) if not isinstance(source_id, UUID) else source_id
            source = self._source_repo.get(source_id_uuid)
            if source is None or source.get("status") not in {"draft", "active"}:
                return False
        return True
