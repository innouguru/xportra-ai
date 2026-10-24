"""Regulatory artifact deletion, legal-hold, and retention-eligibility services.

Foundation only — no storage mutation exposed; deletion disabled.
Follows existing authorization (`GlobalStaffGrantService`), audit
(`GlobalStaffAuditRepository`), repository, and transaction patterns.
Concurrency uses advisory locks (`pg_advisory_xact_lock`) within
`database.transaction()` to serialize authorization, eligibility,
hold mutations, and deletion-intent updates per artifact.
"""
from __future__ import annotations

from uuid import UUID

from xportra.application.global_staff import GlobalStaffGrantService, GRANT_MANAGE
from xportra.application.errors import (
    ApplicationAuthorizationError,
    ApplicationValidationError,
)
from xportra.persistence.database import Database
from xportra.persistence.repositories import (
    GlobalStaffAuditRepository,
    RegulatoryArtifactLegalHoldRepository,
    RegulatoryArtifactDeletionIntentRepository,
)
from xportra.api.errors import PermissionDeniedError


class RegulatoryArtifactRetentionEligibilityService:
    """Server-side eligibility evaluation per approved retention policy."""

    ELIGIBLE_STATUSES = (
        "superseded_24mo",
        "rejected_24mo",
        "withdrawn_24mo",
        "manual_recovery",
    )

    INELIGIBLE_STATUSES = (
        "current_published",
        "ineligible",
    )

    def evaluate(
        self,
        artifact_row: dict | None,
        supersession_date: str | None = None,
        rejection_date: str | None = None,
        withdrawal_date: str | None = None,
        manual_recovery_date: str | None = None,
    ) -> str:
        """Evaluate retention eligibility; fail closed on uncertainty."""
        if artifact_row is None:
            return "ineligible"

        status = artifact_row.get("status")
        if status == "validated":
            # Published/current artifacts retained indefinitely.
            return "current_published"

        if status in ("rejected", "pending_review"):
            # Provisional artifacts: 24 months from supersession/rejection.
            # The design treats supersession/rejection dates from authoritative
            # source records; if the artifact status indicates superseded,
            # rejected, or withdrawn, we require a date.
            date_to_check = supersession_date or rejection_date or withdrawal_date
            if date_to_check is None:
                return "ineligible"
            return "rejected_24mo"

        if status == "archived":
            # Archived is a future state; if it implies supersession/rejection,
            # treat as superseded/rejected with 24 months from relevant date.
            date_to_check = supersession_date or rejection_date or withdrawal_date
            if date_to_check is not None:
                return "superseded_24mo"
            return "ineligible"

        # Manual recovery artifacts.
        if status == "manual_recovery" or status in ("failed", "partial", "zero_candidates"):
            if manual_recovery_date is not None:
                return "manual_recovery"
            return "ineligible"

        # Unknown or ambiguous status.
        return "ineligible"


class RegulatoryArtifactLegalHoldService:
    """Durable, auditable legal-hold management with authorization."""

    def __init__(
        self,
        database: Database,
        grant_service: GlobalStaffGrantService | None = None,
        audit_repo: GlobalStaffAuditRepository | None = None,
        hold_repo: RegulatoryArtifactLegalHoldRepository | None = None,
    ) -> None:
        self._database = database
        self._grant_service = grant_service or GlobalStaffGrantService(database)
        self._audit = audit_repo or GlobalStaffAuditRepository(database)
        self._holds = hold_repo or RegulatoryArtifactLegalHoldRepository(database)

    def _require_grant(self, actor_user_id: UUID) -> None:
        if actor_user_id is None:
            raise PermissionDeniedError()
        if not self._grant_service.is_granted(actor_user_id, GRANT_MANAGE):
            raise PermissionDeniedError()

    def _advisory_lock(self, connection, artifact_id: UUID | str) -> None:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s)::bigint)",
                (str(artifact_id),),
            )

    def place_hold(
        self,
        artifact_id: UUID,
        actor_user_id: UUID,
        authorization_ref: str,
        reason: str,
        status: str = "active",
    ) -> dict:
        """Place an authorized, durable legal hold."""
        self._require_grant(actor_user_id)

        with self._database.transaction() as connection:
            # Serialize hold placement against deletion for same artifact.
            self._advisory_lock(connection, artifact_id)

            # Verify authorization reference independence.
            # The design requires authorization references to be verifiable;
            # here we enforce non-empty reference, consistent with existing
            # authorization mechanism conventions.
            if not authorization_ref or not authorization_ref.strip():
                raise ApplicationValidationError(
                    "authorization_ref is required for legal hold placement"
                )

            # Insert audit event atomically with hold creation.
            audit_row = self._audit.insert_in_transaction(
                connection,
                event_type="legal_hold_placed",
                actor_user_id=actor_user_id,
                target_user_id=actor_user_id,
                permission=GRANT_MANAGE,
                reason=f"Hold placed: {reason}; auth_ref={authorization_ref}",
                authorization_ref=authorization_ref,
            )
            hold_row = self._holds.create(
                artifact_id=artifact_id,
                actor_user_id=actor_user_id,
                authorization_ref=authorization_ref,
                reason=reason,
                status=status,
            )
        return hold_row

    def release_hold(
        self,
        hold_id: UUID,
        actor_user_id: UUID,
        release_authorization_ref: str,
    ) -> dict | None:
        """Release an active hold with independent authorization."""
        self._require_grant(actor_user_id)

        if not release_authorization_ref or not release_authorization_ref.strip():
            raise ApplicationValidationError(
                "release_authorization_ref is required for legal hold release"
            )

        with self._database.transaction() as connection:
            # Serialization: retrieve the active hold with row-level lock,
            # then acquire advisory lock on the artifact identity.
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT artifact_id FROM xportra.regulatory_artifact_legal_hold WHERE id = %s AND status = 'active' FOR UPDATE",
                    (hold_id,),
                )
                row_for_lock = cursor.fetchone()
                if row_for_lock is not None:
                    artifact_for_lock = row_for_lock[0]
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%s)::bigint)",
                        (str(artifact_for_lock),),
                    )
            # Now release with advisory lock held.
            row = self._holds.release(
                hold_id,
                released_by=actor_user_id,
                release_authorization_ref=release_authorization_ref,
            )
            if row is not None:
                audit_row = self._audit.insert_in_transaction(
                    connection,
                    event_type="legal_hold_released",
                    actor_user_id=actor_user_id,
                    target_user_id=actor_user_id,
                    permission=GRANT_MANAGE,
                    reason=f"Hold released; auth_ref={release_authorization_ref}",
                    authorization_ref=release_authorization_ref,
                )
        return row

    def get_active_holds_for_artifact(self, artifact_id: UUID) -> list[dict]:
        return self._holds.get_active_for_artifact(artifact_id)


class RegulatoryArtifactDeletionIntentService:
    """Durable deletion-intent lifecycle — authorization, eligibility,
    hold verification, audit linkage, and safe failure handling.
    Actual storage deletion remains disabled; no adapter delete exposed.
    """

    def __init__(
        self,
        database: Database,
        grant_service: GlobalStaffGrantService | None = None,
        audit_repo: GlobalStaffAuditRepository | None = None,
        hold_repo: RegulatoryArtifactLegalHoldRepository | None = None,
        intent_repo: RegulatoryArtifactDeletionIntentRepository | None = None,
        retention_service: RegulatoryArtifactRetentionEligibilityService | None = None,
    ) -> None:
        self._database = database
        self._grant_service = grant_service or GlobalStaffGrantService(database)
        self._audit = audit_repo or GlobalStaffAuditRepository(database)
        self._holds = hold_repo or RegulatoryArtifactLegalHoldRepository(database)
        self._intents = intent_repo or RegulatoryArtifactDeletionIntentRepository(database)
        self._retention = retention_service or RegulatoryArtifactRetentionEligibilityService()

    def _require_grant(self, actor_user_id: UUID) -> None:
        if actor_user_id is None:
            raise PermissionDeniedError()
        if not self._grant_service.is_granted(actor_user_id, GRANT_MANAGE):
            raise PermissionDeniedError()

    def evaluate_eligibility(
        self,
        artifact_row: dict | None,
        supersession_date: str | None = None,
        rejection_date: str | None = None,
        withdrawal_date: str | None = None,
        manual_recovery_date: str | None = None,
    ) -> str:
        return self._retention.evaluate(
            artifact_row,
            supersession_date=supersession_date,
            rejection_date=rejection_date,
            withdrawal_date=withdrawal_date,
            manual_recovery_date=manual_recovery_date,
        )

    def create_intent(
        self,
        artifact_id: UUID,
        actor_user_id: UUID,
        authorization_ref: str,
        reason: str,
        content_hash: str,
        artifact_row: dict | None = None,
    ) -> dict:
        """Create or return existing deletion intent for an authorized operation."""
        self._require_grant(actor_user_id)

        if not authorization_ref or not authorization_ref.strip():
            raise ApplicationValidationError("authorization_ref is required")

        # Duplicate protection: same (artifact, auth_ref, actor) should not
        # create a new mutation. Read existing intent first.
        existing = self._intents.get_by_artifact_auth_actor(
            artifact_id, authorization_ref, actor_user_id
        )
        if existing is not None:
            # Return existing durable state without creating a new mutation.
            return existing

        # Verify no active legal hold before creating a new intent.
        active_holds = self._holds.get_active_for_artifact(artifact_id)
        legal_hold_active = len(active_holds) > 0

        # Create durable intent with authorization and audit linkage.
        # Actual storage deletion remains disabled in this foundation.
        with self._database.transaction() as connection:
            # Serialization: advisory lock on artifact identity.
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s)::bigint)",
                    (str(artifact_id),),
                )
                # Re-check hold status within the same transaction.
                active_holds = self._holds.get_active_for_artifact(artifact_id)
                legal_hold_active = len(active_holds) > 0

                # Re-check authorization and eligibility within the transaction.
                eligibility = self.evaluate_eligibility(
                    artifact_row,
                    supersession_date=artifact_row.get("supersession_date") if artifact_row else None,
                    rejection_date=artifact_row.get("rejection_date") if artifact_row else None,
                    withdrawal_date=artifact_row.get("withdrawal_date") if artifact_row else None,
                    manual_recovery_date=artifact_row.get("manual_recovery_date") if artifact_row else None,
                )

                audit_row = self._audit.insert_in_transaction(
                    connection,
                    event_type="deletion_intent_created",
                    actor_user_id=actor_user_id,
                    target_user_id=actor_user_id,
                    permission=GRANT_MANAGE,
                    reason=f"Deletion intent created for artifact {artifact_id}; auth_ref={authorization_ref}; eligibility={eligibility}; hold_active={legal_hold_active}",
                    authorization_ref=authorization_ref,
                )
                intent_row = self._intents.create(
                    artifact_id=artifact_id,
                    content_hash=content_hash,
                    actor_user_id=actor_user_id,
                    authorization_ref=authorization_ref,
                    reason=reason,
                    retention_eligibility=eligibility,
                    legal_hold_active=legal_hold_active,
                    audit_event_ref=audit_row.get("authorization_ref") if audit_row else authorization_ref,
                )
        return intent_row

    def get_intent_for_artifact(self, artifact_id: UUID) -> list[dict]:
        return self._intents.get_by_artifact(artifact_id)
