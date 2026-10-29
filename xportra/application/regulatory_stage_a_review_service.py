"""Stage A regulatory source and wording verification.

Stage A verifies that the source and artifact provenance are adequate,
that the exact source text/location supports the extracted wording, and
that the interpretation has been reviewed. Stage A does NOT assert that
the requirement applies to the Nigerian export pilot — that is a
separate Stage B decision. Stage A-verified candidates are still not
published or exporter-applicable requirements.

This service enforces the ``STAGE_A_VERIFY`` global staff permission
on every operation. Tenant membership or ownership alone is
insufficient.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
)
from xportra.application.global_staff import (
    GlobalStaffGrantService,
    STAGE_A_VERIFY,
)
from xportra.persistence.database import Database
from xportra.persistence.repositories import (
    RegulatoryRequirementRepository,
    RegulatoryReviewFlagRepository,
    RegulatorySourceArtifactRepository,
    RegulatorySourceRepository,
)

STAGE_A_STATUS_VERIFIED = "verified"
STAGE_A_STATUS_REJECTED = "rejected"
STAGE_A_STATUS_CLARIFICATION_REQUIRED = "clarification_required"

VALID_STAGE_A_STATUSES = frozenset({
    STAGE_A_STATUS_VERIFIED,
    STAGE_A_STATUS_REJECTED,
    STAGE_A_STATUS_CLARIFICATION_REQUIRED,
})


class RegulatoryStageAReviewService:
    """Application boundary for Stage A source and wording verification."""

    def __init__(
        self,
        database: Database,
        *,
        source_repo: RegulatorySourceRepository | None = None,
        artifact_repo: RegulatorySourceArtifactRepository | None = None,
        requirement_repo: RegulatoryRequirementRepository | None = None,
        grant_service: GlobalStaffGrantService | None = None,
    ) -> None:
        self._database = database
        self._source_repo = source_repo or RegulatorySourceRepository(database)
        self._artifact_repo = artifact_repo or RegulatorySourceArtifactRepository(database)
        self._requirement_repo = requirement_repo or RegulatoryRequirementRepository(database)
        self._grant_service = grant_service or GlobalStaffGrantService(database)

    # ---------------------------------------------------------------- queries

    def get_candidate_stage_a(self, candidate_id: UUID) -> dict[str, Any] | None:
        """Return a candidate's Stage A review state with provenance.

        Includes candidate text, source/artifact references, ingestion-job
        provenance, and source metadata so a reviewer can make an informed
        Stage A decision.
        """
        row = self._requirement_repo.get(candidate_id)
        if row is None:
            return None
        provenance = self._requirement_repo.get_with_provenance(candidate_id)
        result = {
            "id": row["id"],
            "source_id": row.get("source_id"),
            "artifact_id": row.get("artifact_id"),
            "requirement_text": row["requirement_text"],
            "requirement_type": row.get("requirement_type"),
            "source_location": row.get("source_location") or {},
            "position": row.get("position"),
            "extraction_outcome": row["extraction_outcome"],
            "status": row["status"],
            "stage_a_status": row.get("stage_a_status", "pending"),
            "stage_a_reviewer_user_id": row.get("stage_a_reviewer_user_id"),
            "stage_a_reviewed_at": row.get("stage_a_reviewed_at"),
            "stage_a_rationale": row.get("stage_a_rationale"),
            "manual_entry": row.get("manual_entry", False),
            # Provenance for review traceability.
            "source_title": provenance.get("source_title") if provenance else None,
            "source_jurisdiction": provenance.get("source_jurisdiction") if provenance else None,
            "source_version": provenance.get("source_version") if provenance else None,
            "source_status": provenance.get("source_status") if provenance else None,
            "source_authority_id": provenance.get("source_authority_id") if provenance else None,
            "artifact_uri": provenance.get("artifact_uri") if provenance else None,
            "artifact_content_hash": provenance.get("artifact_content_hash") if provenance else None,
            "artifact_content_length": provenance.get("artifact_content_length") if provenance else None,
            "artifact_content_type": provenance.get("artifact_content_type") if provenance else None,
            "artifact_acquisition_channel": provenance.get("artifact_acquisition_channel") if provenance else None,
            "ingestion_job_id": row.get("ingestion_job_id"),
            "ingestion_job_status": provenance.get("ingestion_job_status") if provenance else None,
            "ingestion_job_error_details": provenance.get("ingestion_job_error_details") if provenance else None,
            "ingestion_job_parser_version": provenance.get("ingestion_job_parser_version") if provenance else None,
        }
        return result

    def list_stage_a_decisions(self, requirement_id: UUID) -> list[dict[str, Any]]:
        """Return all Stage A review decisions for a candidate (append-only history)."""
        with self._database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, requirement_id, stage_a_status, reviewer_user_id,
                           reviewed_at, rationale, source_id, created_at
                    FROM xportra.regulatory_stage_a_reviews
                    WHERE requirement_id = %s
                    ORDER BY created_at DESC, id DESC
                    """,
                    (requirement_id,),
                )
                return [dict(row) for row in cursor.fetchall()]

    # ---------------------------------------------------------------- authorization

    def _require_grant(self, actor_user_id: UUID | None) -> None:
        from xportra.api.errors import PermissionDeniedError

        if actor_user_id is None:
            raise PermissionDeniedError()
        if not self._grant_service.is_granted(actor_user_id, STAGE_A_VERIFY):
            raise PermissionDeniedError()

    # ---------------------------------------------------------------- review

    def verify_stage_a(
        self,
        actor_user_id: UUID,
        candidate_id: UUID,
        stage_a_status: str,
        rationale: str,
    ) -> dict[str, Any]:
        """Record a Stage A review decision for a candidate.

        Valid decisions: ``verified``, ``rejected``, ``clarification_required``.

        A candidate with ``extraction_outcome == 'failed'`` cannot be
        marked ``verified`` — insufficient source evidence blocks
        verification. Manual candidates (``manual_entry == True``) may be
        reviewed but manual entry is not itself proof of verification.

        Records an append-only audit event in
        ``regulatory_stage_a_reviews`` and updates the candidate's
        Stage A columns. Neither Stage A verification nor rejection
        approves pilot applicability or publishes the requirement.
        """
        self._require_grant(actor_user_id)

        if stage_a_status not in VALID_STAGE_A_STATUSES:
            raise ApplicationValidationError(
                f"invalid stage_a_status: {stage_a_status}"
            )
        if not rationale or not rationale.strip():
            raise ApplicationValidationError("rationale is required")

        # Load the candidate with provenance.
        row = self._requirement_repo.get(candidate_id)
        if row is None:
            raise ApplicationNotFoundError("candidate requirement not found")

        source_id = row.get("source_id")
        if source_id is None:
            raise ApplicationNotFoundError("candidate has no source linkage")

        source = self._source_repo.get(source_id)
        if source is None:
            raise ApplicationNotFoundError("regulatory source not found")

        # Governance: fail closed if a pending review flag exists for the
        # source or candidate. Prior verification/rejection must not be
        # silently preserved as current when supersession, version change,
        # material change, or staleness requires renewed review.
        review_flags = RegulatoryReviewFlagRepository(self._database)
        pending_for_source = review_flags.list_pending_for_source(source_id)
        pending_for_candidate = review_flags.get_for_requirement(candidate_id)
        pending = [f for f in pending_for_source + pending_for_candidate if f.get("status") == "pending_review"]
        if pending:
            raise ApplicationValidationError(
                "current review is blocked by pending governance flags for source or candidate; "
                "re-review is required before any new Stage A verification"
            )

        # Failed extraction candidates cannot be verified.
        if (
            stage_a_status == STAGE_A_STATUS_VERIFIED
            and row.get("extraction_outcome") == "failed"
        ):
            raise ApplicationValidationError(
                "candidate with failed extraction cannot be stage-a verified"
            )

        now = datetime.now(timezone.utc)

        # Update candidate Stage A columns (current state) and record
        # append-only audit event atomically. The regulatory_stage_a_reviews
        # table serves as the append-only audit trail for Stage A decisions;
        # global_staff_audit is reserved for grant/revoke events only.
        with self._database.transaction() as connection:
            updated_row = self._requirement_repo.update_stage_a(
                requirement_id=candidate_id,
                stage_a_status=stage_a_status,
                reviewer_user_id=actor_user_id,
                reviewed_at=now,
                rationale=rationale.strip(),
            )
            if updated_row is None:
                raise ApplicationNotFoundError("candidate requirement not found")

            # Record append-only audit event in regulatory_stage_a_reviews.
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO xportra.regulatory_stage_a_reviews
                    (requirement_id, stage_a_status, reviewer_user_id,
                     reviewed_at, rationale, source_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    candidate_id,
                    stage_a_status,
                    actor_user_id,
                    now,
                    rationale.strip(),
                    source_id,
                    now,
                    now,
                ),
            )
            audit_row = cursor.fetchone()

        return {
            "id": updated_row["id"],
            "requirement_id": updated_row["id"],
            "source_id": updated_row.get("source_id"),
            "stage_a_status": updated_row["stage_a_status"],
            "stage_a_reviewer_user_id": updated_row["stage_a_reviewer_user_id"],
            "stage_a_reviewed_at": updated_row["stage_a_reviewed_at"],
            "stage_a_rationale": updated_row["stage_a_rationale"],
            "audit_id": audit_row["id"],
            "audit_created_at": audit_row["created_at"],
        }

    # ---------------------------------------------------------------- internal
