"""Stage B regulatory pilot-applicability approval.

Stage B determines whether a Stage A-verified regulatory requirement applies
to the explicitly defined Nigerian export pilot scope. Stage B is an
applicability decision only — it does NOT publish requirements, mark them
exporter-ready, or connect them to compliance assessments.

This service enforces the ``STAGE_B_APPROVE`` global staff permission on
every operation. Tenant membership or ownership alone is insufficient.

Default rule: Stage A and Stage B must be performed by separate qualified
reviewers. A same-person exception is NOT implemented because no authorized
exception authority or mechanism exists in the governing contracts. The
exception path is fail-closed: any attempt to use the same reviewer for both
stages is denied.
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
    STAGE_B_APPROVE,
)
from xportra.persistence.database import Database
from xportra.persistence.repositories import (
    RegulatoryRequirementRepository,
    RegulatoryReviewFlagRepository,
    RegulatorySourceRepository,
)

STAGE_B_STATUS_APPROVED = "approved"
STAGE_B_STATUS_REJECTED = "rejected"
STAGE_B_STATUS_CLARIFICATION_REQUIRED = "clarification_required"

VALID_STAGE_B_STATUSES = frozenset({
    STAGE_B_STATUS_APPROVED,
    STAGE_B_STATUS_REJECTED,
    STAGE_B_STATUS_CLARIFICATION_REQUIRED,
})

#: Approved pilot scope identifier for the sesame-to-EU pilot.
#: The pilot covers raw/unprocessed food-use sesame (Sesamum indicum)
#: from Nigeria (Kano/Jigawa operational sourcing regions), destined for
#: import and customs clearance in the Netherlands.
PILOT_SCOPE_ID = "sesame-eu-pilot-v1"


class RegulatoryStageBReviewService:
    """Application boundary for Stage B pilot-applicability approval."""

    def __init__(
        self,
        database: Database,
        *,
        source_repo: RegulatorySourceRepository | None = None,
        requirement_repo: RegulatoryRequirementRepository | None = None,
        grant_service: GlobalStaffGrantService | None = None,
    ) -> None:
        self._database = database
        self._source_repo = source_repo or RegulatorySourceRepository(database)
        self._requirement_repo = requirement_repo or RegulatoryRequirementRepository(database)
        self._grant_service = grant_service or GlobalStaffGrantService(database)

    # ---------------------------------------------------------------- queries

    def get_candidate_stage_b(self, candidate_id: UUID) -> dict[str, Any] | None:
        """Return a candidate's Stage B review state."""
        row = self._requirement_repo.get(candidate_id)
        if row is None:
            return None
        return {
            "id": row["id"],
            "source_id": row.get("source_id"),
            "artifact_id": row.get("artifact_id"),
            "requirement_text": row["requirement_text"],
            "source_location": row.get("source_location") or {},
            "extraction_outcome": row["extraction_outcome"],
            "status": row["status"],
            "stage_a_status": row.get("stage_a_status", "pending"),
            "stage_b_status": row.get("stage_b_status", "pending"),
            "stage_b_reviewer_user_id": row.get("stage_b_reviewer_user_id"),
            "stage_b_reviewed_at": row.get("stage_b_reviewed_at"),
            "stage_b_rationale": row.get("stage_b_rationale"),
            "stage_b_pilot_scope": row.get("stage_b_pilot_scope"),
            "manual_entry": row.get("manual_entry", False),
        }

    def list_stage_b_decisions(self, requirement_id: UUID) -> list[dict[str, Any]]:
        """Return all Stage B review decisions for a candidate (append-only history)."""
        with self._database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, requirement_id, stage_b_status, reviewer_user_id,
                           reviewed_at, rationale, pilot_scope,
                           evidence_references, same_person_exception,
                           exception_authorizer_user_id,
                           exception_authorization_ref, exception_justification,
                           created_at
                    FROM xportra.regulatory_stage_b_reviews
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
        if not self._grant_service.is_granted(actor_user_id, STAGE_B_APPROVE):
            raise PermissionDeniedError()

    # ---------------------------------------------------------------- review

    def approve_stage_b(
        self,
        actor_user_id: UUID,
        candidate_id: UUID,
        stage_b_status: str,
        rationale: str,
        pilot_scope: str,
        evidence_references: list[dict[str, Any]] | None = None,
        same_person_exception: bool = False,
        exception_authorizer_user_id: UUID | None = None,
        exception_authorization_ref: str | None = None,
        exception_justification: str | None = None,
    ) -> dict[str, Any]:
        """Record a Stage B pilot-applicability approval decision.

        Valid decisions: ``approved``, ``rejected``,
        ``clarification_required``.

        Preconditions:
        - The actor must hold an active ``STAGE_B_APPROVE`` grant.
        - The candidate must exist and have ``stage_a_status == 'verified'``.
        - The actor must be different from the Stage A reviewer, unless an
          explicit same-person exception is authorized (not implemented;
          fail-closed).
        - Rationale is mandatory.
        - The pilot scope must be specified.

        Records an append-only audit event in
        ``regulatory_stage_b_reviews`` and updates the candidate's
        Stage B columns atomically. Neither Stage B approval nor rejection
        publishes the requirement or makes it exporter-ready.
        """
        self._require_grant(actor_user_id)

        if stage_b_status not in VALID_STAGE_B_STATUSES:
            raise ApplicationValidationError(
                f"invalid stage_b_status: {stage_b_status}"
            )
        if not rationale or not rationale.strip():
            raise ApplicationValidationError("rationale is required")
        if not pilot_scope or not pilot_scope.strip():
            raise ApplicationValidationError("pilot_scope is required")

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

        # Governance: fail closed if the source or candidate has a pending
        # review flag (supersession, version change, material change, stale,
        # or withdrawal). Previous approvals must not be treated as current.
        review_flags = RegulatoryReviewFlagRepository(self._database)
        pending_for_source = review_flags.list_pending_for_source(source_id)
        pending_for_candidate = review_flags.get_for_requirement(candidate_id)
        pending_flags = [f for f in pending_for_source + pending_for_candidate if f.get("status") == "pending_review"]
        if pending_flags:
            raise ApplicationValidationError(
                "current review is blocked by pending governance flags for source or candidate; "
                "re-review is required before any new Stage B approval"
            )

        # Stage A must be verified before Stage B can proceed.
        if row.get("stage_a_status") != "verified":
            raise ApplicationValidationError(
                "candidate has not passed Stage A verification; "
                "Stage B applicability approval requires Stage A verification"
            )

        # Default rule: Stage A and Stage B reviewers must be different.
        # Same-person exception is NOT implemented because no authorized
        # exception authority or mechanism exists in the governing contracts.
        # Fail-closed: deny any same-person attempt.
        stage_a_reviewer = row.get("stage_a_reviewer_user_id")
        if stage_a_reviewer is not None and actor_user_id == stage_a_reviewer:
            if not same_person_exception:
                raise ApplicationValidationError(
                    "same-person Stage A/Stage B review is not permitted; "
                    "Stage A and Stage B must be performed by separate "
                    "qualified reviewers"
                )
            else:
                # Same-person exception requires an approved authority and
                # authorization mechanism. Neither exists in the governing
                # contracts. Fail closed.
                raise ApplicationValidationError(
                    "same-person Stage A/Stage B exception is not implemented; "
                    "no authorized exception authority or mechanism exists. "
                    "This path is fail-closed."
                )

        now = datetime.now(timezone.utc)

        # Update candidate Stage B columns (current state) and record
        # append-only audit event atomically.
        with self._database.transaction() as connection:
            updated_row = self._requirement_repo.update_stage_b(
                requirement_id=candidate_id,
                stage_b_status=stage_b_status,
                reviewer_user_id=actor_user_id,
                reviewed_at=now,
                rationale=rationale.strip(),
                pilot_scope=pilot_scope.strip(),
            )
            if updated_row is None:
                raise ApplicationNotFoundError("candidate requirement not found")

            # Record append-only audit event in regulatory_stage_b_reviews.
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO xportra.regulatory_stage_b_reviews
                    (requirement_id, stage_b_status, reviewer_user_id,
                     reviewed_at, rationale, pilot_scope,
                     evidence_references, same_person_exception,
                     exception_authorizer_user_id,
                     exception_authorization_ref, exception_justification,
                     created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    candidate_id,
                    stage_b_status,
                    actor_user_id,
                    now,
                    rationale.strip(),
                    pilot_scope.strip(),
                    evidence_references if evidence_references is not None else [],
                    same_person_exception,
                    exception_authorizer_user_id,
                    exception_authorization_ref,
                    exception_justification,
                    now,
                    now,
                ),
            )
            audit_row = cursor.fetchone()

        return {
            "id": updated_row["id"],
            "requirement_id": updated_row["id"],
            "source_id": updated_row.get("source_id"),
            "stage_b_status": updated_row["stage_b_status"],
            "stage_b_reviewer_user_id": updated_row["stage_b_reviewer_user_id"],
            "stage_b_reviewed_at": updated_row["stage_b_reviewed_at"],
            "stage_b_rationale": updated_row["stage_b_rationale"],
            "stage_b_pilot_scope": updated_row["stage_b_pilot_scope"],
            "audit_id": audit_row["id"],
            "audit_created_at": audit_row["created_at"],
        }

    # ---------------------------------------------------------------- internal
