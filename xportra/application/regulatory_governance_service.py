"""Regulatory governance service for source freshness, supersession,
and review-requirement tracking.

This is a governance boundary — not a publication or exporter-facing
integration. It records when supersession, version change, material
change, or staleness requires renewed Stage A / Stage B review, and
prevents superseded/stale material from being silently treated as
current approval.

Freshness is not inferred automatically from timestamps. If no approved
currentness evidence exists, the mechanism records an explicit
unknown/unverified or pending-review state rather than declaring the
source current. The same-person exception remains unavailable (fail-closed);
re-review must pass independent Stage A verification and Stage B
approval.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from xportra.application.errors import ApplicationValidationError
from xportra.application.global_staff import STAGE_A_VERIFY, STAGE_B_APPROVE
from xportra.persistence.database import Database
from xportra.persistence.repositories import (
    RegulatoryReviewFlagRepository,
    RegulatoryRequirementRepository,
    RegulatorySourceRepository,
)

TRIGGER_TYPE_SUPERSESSION = "supersession"
TRIGGER_TYPE_VERSION_CHANGE = "version_change"
TRIGGER_TYPE_MATERIAL_CHANGE = "material_change"
TRIGGER_TYPE_STALE = "stale"
TRIGGER_TYPE_WITHDRAWAL = "withdrawal"

VALID_TRIGGER_TYPES = frozenset({
    TRIGGER_TYPE_SUPERSESSION,
    TRIGGER_TYPE_VERSION_CHANGE,
    TRIGGER_TYPE_MATERIAL_CHANGE,
    TRIGGER_TYPE_STALE,
    TRIGGER_TYPE_WITHDRAWAL,
})

REVIEW_STATUS_PENDING = "pending_review"
REVIEW_STATUS_COMPLETED = "review_completed"
REVIEW_STATUS_DISMISSED = "dismissed"


class RegulatoryGovernanceService:
    """Application boundary for review-flag governance only."""

    def __init__(
        self,
        database: Database,
        *,
        source_repo: RegulatorySourceRepository | None = None,
        requirement_repo: RegulatoryRequirementRepository | None = None,
        review_flag_repo: RegulatoryReviewFlagRepository | None = None,
    ) -> None:
        self._database = database
        self._source_repo = source_repo or RegulatorySourceRepository(database)
        self._requirement_repo = requirement_repo or RegulatoryRequirementRepository(database)
        self._flag_repo = review_flag_repo or RegulatoryReviewFlagRepository(database)

    def flag_review_required(
        self,
        actor_user_id: UUID,
        trigger_type: str,
        trigger_source_id: UUID,
        requirement_id: UUID | None = None,
        rationale: str = "",
    ) -> dict[str, Any]:
        if trigger_type not in VALID_TRIGGER_TYPES:
            raise ApplicationValidationError(f"invalid trigger_type: {trigger_type}")
        if not rationale or not rationale.strip():
            raise ApplicationValidationError("rationale is required for review flag")

        # Verify source exists; fail closed.
        source = self._source_repo.get(trigger_source_id)
        if source is None:
            raise ApplicationValidationError("trigger source not found")

        # If a requirement is linked, verify it exists.
        if requirement_id is not None:
            row = self._requirement_repo.get(requirement_id)
            if row is None:
                raise ApplicationValidationError("linked requirement not found")

        return self._flag_repo.create(
            requirement_id=requirement_id,
            trigger_source_id=trigger_source_id,
            trigger_type=trigger_type,
            actor_user_id=actor_user_id,
            rationale=rationale.strip(),
        )

    def complete_review(
        self,
        actor_user_id: UUID,
        flag_id: UUID,
        rationale: str | None = None,
    ) -> dict[str, Any] | None:
        if not rationale or not rationale.strip():
            raise ApplicationValidationError("rationale is required")
        flag_row = self._flag_repo.get_by_id(flag_id)
        if flag_row is None:
            raise ApplicationValidationError("review flag not found")
        flag_created_at = flag_row.get("created_at")
        requirement_id = flag_row.get("requirement_id")
        if requirement_id is not None:
            req_row = self._requirement_repo.get(requirement_id)
            if req_row is None:
                raise ApplicationValidationError("linked requirement not found")
            # Stage A verification must be performed AFTER the flag was raised
            # to address the re-review requirement. A historical Stage A
            # decision predating the flag does not satisfy re-review.
            if req_row.get("stage_a_status") != "verified":
                raise ApplicationValidationError(
                    "re-review cannot be completed: linked candidate lacks Stage A verification"
                )
            stage_a_reviewed_at = req_row.get("stage_a_reviewed_at")
            if stage_a_reviewed_at is None or stage_a_reviewed_at <= flag_created_at:
                raise ApplicationValidationError(
                    "re-review cannot be completed: Stage A verification does not "
                    "post-date the governance flag"
                )
            # Stage B must be APPROVED (rejected/clarification_required do not
            # establish applicability approval) and must occur after the flag.
            stage_b = req_row.get("stage_b_status", "pending")
            if stage_b != "approved":
                raise ApplicationValidationError(
                    "re-review cannot be completed: linked candidate lacks an "
                    "approved Stage B applicability decision"
                )
            stage_b_reviewed_at = req_row.get("stage_b_reviewed_at")
            if stage_b_reviewed_at is None or stage_b_reviewed_at <= flag_created_at:
                raise ApplicationValidationError(
                    "re-review cannot be completed: Stage B applicability decision "
                    "does not post-date the governance flag"
                )
        updated = self._flag_repo.update_status(
            flag_id, REVIEW_STATUS_COMPLETED, rationale=rationale.strip()
        )
        if updated is None:
            raise ApplicationValidationError("review flag not found after verification")
        return dict(updated)

    def get_flags_for_source(self, source_id: UUID) -> list[dict[str, Any]]:
        return self._flag_repo.get_for_source(source_id)

    def get_flags_for_requirement(self, requirement_id: UUID) -> list[dict[str, Any]]:
        return self._flag_repo.get_for_requirement(requirement_id)

    def list_pending_for_source(self, source_id: UUID) -> list[dict[str, Any]]:
        return self._flag_repo.list_pending_for_source(source_id)
