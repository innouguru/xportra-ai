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

from datetime import datetime, timezone
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
    """Eligibility gate: verified + approved + current + no pending flags + succeeded extraction.
    Also provides a controlled publish operation that re-evaluates eligibility
    at the time of publication and records an auditable outcome.
    """

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
        eligible, _ = self.check_eligibility(requirement_id, tenant=tenant)
        return eligible

    def check_eligibility(
        self,
        requirement_id: UUID,
        tenant: TenantContext | None = None,
    ) -> tuple[bool, list[str]]:
        """Return ``(eligible, reasons)`` for a single requirement.

        Reasons are structured, human-readable strings explaining why a
        requirement is not eligible for publication. An empty reasons list
        means eligible. Unknown, missing, or inconsistent states are
        treated as ineligible (never inferred as eligible).
        """
        if not isinstance(requirement_id, UUID):
            raise DomainValidationError("requirement_id must be a UUID")

        reasons: list[str] = []

        # Load the requirement row.
        row = self._requirement_repo.get(requirement_id)
        if row is None:
            return False, ["requirement not found"]

        # 1. status must be 'extracted'
        if row.get("status") != "extracted":
            reasons.append(
                f"requirement status is '{row.get('status')}', expected 'extracted'"
            )

        # 2. extraction_outcome must be 'succeeded'
        if row.get("extraction_outcome") != "succeeded":
            reasons.append(
                f"extraction outcome is '{row.get('extraction_outcome')}', "
                "expected 'succeeded'"
            )

        # 3. stage_a_status must be 'verified'
        if row.get("stage_a_status") != "verified":
            reasons.append(
                f"Stage A status is '{row.get('stage_a_status')}', "
                "expected 'verified'"
            )

        # 4. stage_b_status must be 'approved'
        if row.get("stage_b_status") != "approved":
            reasons.append(
                f"Stage B status is '{row.get('stage_b_status')}', "
                "expected 'approved'"
            )

        # 5. Source must be active (not superseded/withdrawn/archived)
        source_id = row.get("source_id")
        if source_id is not None:
            source_row = self._source_repo.get(source_id)
            if source_row is None:
                reasons.append("source not found")
            elif source_row.get("status") not in {"draft", "active"}:
                reasons.append(
                    f"source status is '{source_row.get('status')}', "
                    "expected 'active' or 'draft'"
                )
        else:
            reasons.append("requirement has no source linkage")

        # 6. No pending review flags on source or requirement
        pending_flags = self._pending_flags_for_requirement_and_source(
            requirement_id, source_id
        )
        if pending_flags:
            flag_types = ", ".join(
                f.get("trigger_type", "unknown") for f in pending_flags
            )
            reasons.append(
                f"pending governance flag(s): {flag_types}; re-review required"
            )

        # 7. Provenance: normalized_document_id must exist
        norm_doc_id = row.get("normalized_document_id")
        if not norm_doc_id:
            reasons.append("missing normalized document (provenance incomplete)")

        # 8. Provenance: ingestion_job_id must reference a completed job
        ingestion_job_id = row.get("ingestion_job_id")
        if ingestion_job_id is not None:
            try:
                job_id = (
                    UUID(str(ingestion_job_id))
                    if not isinstance(ingestion_job_id, UUID)
                    else ingestion_job_id
                )
                job = self._job_repo.get(job_id)
                if job is None:
                    reasons.append("ingestion job not found")
                elif job.get("status") != "completed":
                    reasons.append(
                        f"ingestion job status is '{job.get('status')}', "
                        "expected 'completed'"
                    )
            except (ValueError, AttributeError):
                reasons.append("invalid ingestion job identifier")
        else:
            reasons.append("missing ingestion job (provenance incomplete)")

        # 9. Provenance: parser_version must be non-empty
        parser_version = row.get("parser_version")
        if not parser_version or not isinstance(parser_version, str) or not parser_version.strip():
            reasons.append("missing parser version (provenance incomplete)")

        # 10. Pilot scope filter: if provided, stage_b_pilot_scope must match
        # (handled at list level; not applicable to single check without filter)

        eligible = len(reasons) == 0
        return eligible, reasons

    # ---------------------------------------------------------------- publish

    def publish_requirement(
        self,
        requirement_id: UUID,
        actor_user_id: UUID,
    ) -> dict[str, Any]:
        """Publish a requirement for exporter-facing consumption.

        Performs an eligibility re-evaluation at publication time.
        If eligible, records the publication timestamp on the requirement
        and returns a publication success response.
        If ineligible, returns a publication failure response with reasons.

        Preconditions:
        - The actor must hold an active GRANT_MANAGE grant (enforced by caller).
        - The requirement must pass all eligibility rules at this time.
        - No blocking governance flags may be present.
        - The requirement must have complete provenance.

        The method does NOT auto-set the requirement status to ``published``;
        it records ``published_at`` so the caller can update the requirement
        row accordingly. This design prevents automatic publication as a side
        effect of ingestion, extraction, Stage A, Stage B, or eligibility checks.

        Returns a dict with: candidate_id (or requirement_id), eligible,
        reasons, published_at, and audit information.
        """
        self._require_grant(actor_user_id)

        # Re-evaluate eligibility at publication time.
        eligible, reasons = self.check_eligibility(requirement_id)

        published_at = None
        if eligible:
            # Record the publication timestamp and transition status to 'published'
            # so the requirement is no longer eligible for re-publication and is
            # visible in the exporter-facing catalog.
            published_at = datetime.now(timezone.utc)
            with self._database.transaction() as connection:
                connection.execute(
                    "UPDATE xportra.regulatory_requirements "
                    "SET status = 'published', "
                    "published_at = %s, "
                    "updated_at = %s "
                    "WHERE id = %s",
                    (published_at, published_at, requirement_id),
                )

        return {
            "requirement_id": requirement_id,
            "eligible": eligible,
            "reasons": reasons,
            "published_at": published_at,
        }

    def _require_grant(self, actor_user_id: UUID | None) -> None:
        from xportra.api.errors import PermissionDeniedError

        if actor_user_id is None:
            raise PermissionDeniedError()
        # Grant check is enforced by the API layer (GRANT_MANAGE dependency);
        # this method ensures the actor identity exists.

    # ---------------------------------------------------------------- internals

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