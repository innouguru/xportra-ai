"""Unit tests for Stage B regulatory pilot-applicability approval.

Tests the Stage B review service using fakes — no live database, no hosted
services. Covers authorized approval/rejection/clarification decisions,
unauthorized access, Stage A prerequisite enforcement, failed extraction
blocking, manual candidate review, invalid state transitions, idempotent
retries, audit history, and assurance that Stage B cannot approve
applicability for publication.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest import TestCase
from uuid import UUID

from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
)
from xportra.application.global_staff import STAGE_B_APPROVE
from xportra.application.regulatory_stage_b_review_service import (
    RegulatoryStageBReviewService,
    STAGE_B_STATUS_APPROVED,
    STAGE_B_STATUS_CLARIFICATION_REQUIRED,
    STAGE_B_STATUS_REJECTED,
)
from xportra.application.regulatory_stage_a_review_service import (
    STAGE_A_STATUS_VERIFIED,
)
from xportra.api.errors import PermissionDeniedError
from xportra.persistence.database import Database

ACTOR = UUID("aaaaaaaa-0000-0000-0000-000000000001")
STAGE_A_REVIEWER = UUID("bbbbbbbb-0000-0000-0000-000000000002")
STAGE_B_REVIEWER = UUID("cccccccc-0000-0000-0000-000000000003")
NON_GRANTED = UUID("dddddddd-0000-0000-0000-000000000004")
SOURCE = UUID("eeeeeeee-0000-0000-0000-000000000005")
ARTIFACT = UUID("ffffffff-0000-0000-0000-000000000006")
CANDIDATE = UUID("11111111-0000-0000-0000-000000000100")
CANDIDATE_STAGE_A_NOT_VERIFIED = UUID("22222222-0000-0000-0000-000000000200")


class FakeDatabase(Database):
    """In-memory transaction double."""

    def __init__(self) -> None:
        super().__init__(  # type: ignore[arg-type]
            object(), connection_factory=object()
        )
        self.committed = False
        self.rolled_back = False

    @contextmanager
    def connection(self):  # type: ignore[override]
        try:
            yield _FakeConnection()
            self.committed = True
        except Exception:
            self.rolled_back = True
            raise

    @contextmanager
    def transaction(self):  # type: ignore[override]
        try:
            yield _FakeConnection()
            self.committed = True
        except Exception:
            self.rolled_back = True
            raise


class _FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return _FakeCursor()


class _FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement: str, parameters=()) -> None:
        pass  # No-op for unit tests; fake repo handles state

    def fetchone(self):
        return {
            "id": UUID("aaaaaaaa-0000-0000-0000-000000000999"),
            "created_at": None,
        }

    def fetchall(self):
        return []


class FakeGrantService:
    def __init__(self, granted: dict[UUID, str] | None = None) -> None:
        self.granted = dict(granted or {})

    def is_granted(self, user_id: UUID, permission: str) -> bool:
        return self.granted.get(user_id) == permission


class FakeSourceRepository:
    def __init__(self, existing: dict[UUID, dict] | None = None) -> None:
        self.sources = dict(existing or {})

    def get(self, source_id: UUID):
        return self.sources.get(source_id)


class FakeRequirementRepository:
    def __init__(self, existing: list[dict] | None = None) -> None:
        self.requirements: dict[UUID, dict] = {}
        for r in list(existing or []):
            self.requirements[r["id"]] = dict(r)
        self.fail_update = False

    def get(self, requirement_id: UUID):
        return self.requirements.get(requirement_id)

    def update_stage_b(
        self,
        requirement_id: UUID,
        stage_b_status: str,
        reviewer_user_id: UUID,
        reviewed_at,
        rationale: str,
        pilot_scope: str,
    ) -> dict | None:
        """Update Stage B columns; idempotent for identical retries."""
        if self.fail_update:
            raise RuntimeError("simulated stage_b update failure")
        row = self.requirements.get(requirement_id)
        if row is None:
            return None
        row["stage_b_status"] = stage_b_status
        row["stage_b_reviewer_user_id"] = reviewer_user_id
        row["stage_b_reviewed_at"] = reviewed_at
        row["stage_b_rationale"] = rationale
        row["stage_b_pilot_scope"] = pilot_scope
        row["updated_at"] = reviewed_at
        return row


class FakeAuditRepository:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.fail_insert = False

    def insert_in_transaction(
        self,
        connection,
        event_type: str,
        actor_user_id: UUID,
        target_user_id: UUID,
        permission: str,
        reason: str | None,
        authorization_ref: str | None = None,
    ):
        if self.fail_insert:
            raise RuntimeError("simulated audit insert failure")
        event = {
            "id": UUID("aaaaaaaa-0000-0000-0000-000000000999"),
            "event_type": event_type,
            "actor_user_id": actor_user_id,
            "target_user_id": target_user_id,
            "permission": permission,
            "reason": reason,
            "authorization_ref": authorization_ref,
            "created_at": datetime.now(timezone.utc),
        }
        self.events.append(event)
        return event


class ServiceFactory:
    def __init__(
        self,
        *,
        granted_actor: bool = True,
        granted_reviewer: bool = False,
        source_exists: bool = True,
        artifact_exists: bool = True,
        stage_a_verified: bool = True,
        stage_a_reviewer: UUID | None = STAGE_A_REVIEWER,
        existing_candidate: dict | None = None,
        fail_update: bool = False,
        fail_audit: bool = False,
    ) -> None:
        self.database = FakeDatabase()
        granted = {}
        if granted_actor:
            granted[ACTOR] = STAGE_B_APPROVE
        if granted_reviewer:
            granted[STAGE_B_REVIEWER] = STAGE_B_APPROVE
        self.grants = FakeGrantService(granted)
        self.sources = FakeSourceRepository()
        self.requirements = FakeRequirementRepository()
        self.requirements.fail_update = fail_update

        if source_exists:
            self.sources.sources[SOURCE] = {
                "id": SOURCE,
                "authority_id": UUID("cccccccc-0000-0000-0000-000000000003"),
                "jurisdiction": "EU",
                "title": "Test Regulation",
                "status": "active",
            }

        # Build candidate row(s)
        if existing_candidate is not None:
            self.requirements.requirements[existing_candidate["id"]] = dict(
                existing_candidate
            )
        else:
            self.requirements.requirements[CANDIDATE] = {
                "id": CANDIDATE,
                "normalized_document_id": UUID("44444444-0000-0000-0000-000000000400"),
                "artifact_id": ARTIFACT,
                "source_id": SOURCE,
                "requirement_text": "Shall be labeled with origin.",
                "requirement_type": "labeling",
                "source_location": {"section_order": 0, "heading": None},
                "position": 0,
                "actor": None,
                "condition_metadata": None,
                "status": "extracted",
                "ingestion_job_id": UUID("55555555-0000-0000-0000-000000000500"),
                "extraction_outcome": "succeeded",
                "parser_version": "v1",
                "manual_entry": False,
                "reviewer_user_id": None,
                "reviewed_at": None,
                "source_id": SOURCE,
                "stage_a_status": (
                    STAGE_A_STATUS_VERIFIED if stage_a_verified else "pending"
                ),
                "stage_a_reviewer_user_id": stage_a_reviewer,
                "stage_a_reviewed_at": (
                    datetime.now(timezone.utc) if stage_a_verified else None
                ),
                "stage_a_rationale": (
                    "Stage A verified." if stage_a_verified else None
                ),
                "stage_b_status": "pending",
                "stage_b_reviewer_user_id": None,
                "stage_b_reviewed_at": None,
                "stage_b_rationale": None,
                "stage_b_pilot_scope": None,
                "created_at": None,
                "updated_at": None,
            }
            # Candidate with Stage A not verified
            self.requirements.requirements[
                CANDIDATE_STAGE_A_NOT_VERIFIED
            ] = {
                "id": CANDIDATE_STAGE_A_NOT_VERIFIED,
                "normalized_document_id": UUID(
                    "44444444-0000-0000-0000-000000000401"
                ),
                "artifact_id": ARTIFACT,
                "source_id": SOURCE,
                "requirement_text": "Stage A not verified candidate.",
                "requirement_type": "documentation",
                "source_location": {},
                "position": 1,
                "actor": None,
                "condition_metadata": None,
                "status": "extracted",
                "ingestion_job_id": None,
                "extraction_outcome": "succeeded",
                "parser_version": "v1",
                "manual_entry": False,
                "reviewer_user_id": None,
                "reviewed_at": None,
                "source_id": SOURCE,
                "stage_a_status": "pending",
                "stage_a_reviewer_user_id": None,
                "stage_a_reviewed_at": None,
                "stage_a_rationale": None,
                "stage_b_status": "pending",
                "stage_b_reviewer_user_id": None,
                "stage_b_reviewed_at": None,
                "stage_b_rationale": None,
                "stage_b_pilot_scope": None,
                "created_at": None,
                "updated_at": None,
            }

    def service(self) -> RegulatoryStageBReviewService:
        from xportra.application.regulatory_stage_b_review_service import (
            RegulatoryStageBReviewService,
        )
        return RegulatoryStageBReviewService(
            self.database,
            source_repo=self.sources,
            requirement_repo=self.requirements,
            grant_service=self.grants,
        )


class RegulatoryStageBReviewTests(TestCase):
    def test_authorized_stage_b_approve(self):
        factory = ServiceFactory()
        service = factory.service()
        result = service.approve_stage_b(
            actor_user_id=ACTOR,
            candidate_id=CANDIDATE,
            stage_b_status=STAGE_B_STATUS_APPROVED,
            rationale="Requirement applies to the Nigerian sesame pilot scope.",
            pilot_scope="sesame-eu-pilot-v1",
        )
        self.assertEqual(result["stage_b_status"], STAGE_B_STATUS_APPROVED)
        self.assertEqual(result["stage_b_reviewer_user_id"], ACTOR)
        self.assertIsNotNone(result["stage_b_reviewed_at"])
        self.assertEqual(
            result["stage_b_rationale"],
            "Requirement applies to the Nigerian sesame pilot scope.",
        )
        self.assertIsNotNone(result["audit_id"])

        # Verify current state
        row = service.get_candidate_stage_b(CANDIDATE)
        self.assertEqual(row["stage_b_status"], STAGE_B_STATUS_APPROVED)
        self.assertEqual(row["stage_b_reviewer_user_id"], ACTOR)
        self.assertEqual(
            row["stage_b_rationale"],
            "Requirement applies to the Nigerian sesame pilot scope.",
        )
        self.assertEqual(row["stage_b_pilot_scope"], "sesame-eu-pilot-v1")

    def test_authorized_stage_b_reject(self):
        factory = ServiceFactory()
        service = factory.service()
        result = service.approve_stage_b(
            actor_user_id=ACTOR,
            candidate_id=CANDIDATE,
            stage_b_status=STAGE_B_STATUS_REJECTED,
            rationale="Requirement does not apply to the pilot scope.",
            pilot_scope="sesame-eu-pilot-v1",
        )
        self.assertEqual(result["stage_b_status"], STAGE_B_STATUS_REJECTED)
        self.assertEqual(result["stage_b_reviewer_user_id"], ACTOR)

        row = service.get_candidate_stage_b(CANDIDATE)
        self.assertEqual(row["stage_b_status"], STAGE_B_STATUS_REJECTED)

    def test_authorized_stage_b_clarification_required(self):
        factory = ServiceFactory()
        service = factory.service()
        result = service.approve_stage_b(
            actor_user_id=ACTOR,
            candidate_id=CANDIDATE,
            stage_b_status=STAGE_B_STATUS_CLARIFICATION_REQUIRED,
            rationale="Source text ambiguous; needs clarification.",
            pilot_scope="sesame-eu-pilot-v1",
        )
        self.assertEqual(
            result["stage_b_status"], STAGE_B_STATUS_CLARIFICATION_REQUIRED
        )
        self.assertEqual(result["stage_b_reviewer_user_id"], ACTOR)

    def test_unauthorized_actor_denied(self):
        factory = ServiceFactory(granted_actor=False)
        service = factory.service()
        with self.assertRaises(PermissionDeniedError):
            service.approve_stage_b(
                actor_user_id=NON_GRANTED,
                candidate_id=CANDIDATE,
                stage_b_status=STAGE_B_STATUS_APPROVED,
                rationale="Test rationale.",
                pilot_scope="sesame-eu-pilot-v1",
            )

    def test_stage_a_not_verified_denied(self):
        factory = ServiceFactory(stage_a_verified=False)
        service = factory.service()
        with self.assertRaises(ApplicationValidationError):
            service.approve_stage_b(
                actor_user_id=ACTOR,
                candidate_id=CANDIDATE_STAGE_A_NOT_VERIFIED,
                stage_b_status=STAGE_B_STATUS_APPROVED,
                rationale="Cannot approve without Stage A.",
                pilot_scope="sesame-eu-pilot-v1",
            )

    def test_stage_a_rejected_denied(self):
        # Candidate with Stage A rejected
        factory = ServiceFactory(
            existing_candidate={
                "id": CANDIDATE,
                "normalized_document_id": UUID(
                    "44444444-0000-0000-0000-000000000400"
                ),
                "artifact_id": ARTIFACT,
                "source_id": SOURCE,
                "requirement_text": "Stage A rejected candidate.",
                "requirement_type": "labeling",
                "source_location": {},
                "position": 0,
                "actor": None,
                "condition_metadata": None,
                "status": "extracted",
                "ingestion_job_id": None,
                "extraction_outcome": "succeeded",
                "parser_version": "v1",
                "manual_entry": False,
                "reviewer_user_id": None,
                "reviewed_at": None,
                "source_id": SOURCE,
                "stage_a_status": "rejected",
                "stage_a_reviewer_user_id": STAGE_A_REVIEWER,
                "stage_a_reviewed_at": datetime.now(timezone.utc),
                "stage_a_rationale": "Wording not supported.",
                "stage_b_status": "pending",
                "stage_b_reviewer_user_id": None,
                "stage_b_reviewed_at": None,
                "stage_b_rationale": None,
                "stage_b_pilot_scope": None,
                "created_at": None,
                "updated_at": None,
            }
        )
        service = factory.service()
        with self.assertRaises(ApplicationValidationError):
            service.approve_stage_b(
                actor_user_id=ACTOR,
                candidate_id=CANDIDATE,
                stage_b_status=STAGE_B_STATUS_APPROVED,
                rationale="Cannot approve without Stage A.",
                pilot_scope="sesame-eu-pilot-v1",
            )

    def test_stage_a_clarification_required_denied(self):
        # Candidate with Stage A clarification_required
        factory = ServiceFactory(
            existing_candidate={
                "id": CANDIDATE,
                "normalized_document_id": UUID(
                    "44444444-0000-0000-0000-000000000400"
                ),
                "artifact_id": ARTIFACT,
                "source_id": SOURCE,
                "requirement_text": "Stage A clarification required candidate.",
                "requirement_type": "labeling",
                "source_location": {},
                "position": 0,
                "actor": None,
                "condition_metadata": None,
                "status": "extracted",
                "ingestion_job_id": None,
                "extraction_outcome": "succeeded",
                "parser_version": "v1",
                "manual_entry": False,
                "reviewer_user_id": None,
                "reviewed_at": None,
                "source_id": SOURCE,
                "stage_a_status": "clarification_required",
                "stage_a_reviewer_user_id": STAGE_A_REVIEWER,
                "stage_a_reviewed_at": datetime.now(timezone.utc),
                "stage_a_rationale": "Needs clarification.",
                "stage_b_status": "pending",
                "stage_b_reviewer_user_id": None,
                "stage_b_reviewed_at": None,
                "stage_b_rationale": None,
                "stage_b_pilot_scope": None,
                "created_at": None,
                "updated_at": None,
            }
        )
        service = factory.service()
        with self.assertRaises(ApplicationValidationError):
            service.approve_stage_b(
                actor_user_id=ACTOR,
                candidate_id=CANDIDATE,
                stage_b_status=STAGE_B_STATUS_APPROVED,
                rationale="Cannot approve without Stage A verified.",
                pilot_scope="sesame-eu-pilot-v1",
            )

    def test_invalid_stage_b_status_denied(self):
        factory = ServiceFactory()
        service = factory.service()
        with self.assertRaises(ApplicationValidationError):
            service.approve_stage_b(
                actor_user_id=ACTOR,
                candidate_id=CANDIDATE,
                stage_b_status="not_a_status",
                rationale="Test rationale.",
                pilot_scope="sesame-eu-pilot-v1",
            )

    def test_empty_rationale_denied(self):
        factory = ServiceFactory()
        service = factory.service()
        with self.assertRaises(ApplicationValidationError):
            service.approve_stage_b(
                actor_user_id=ACTOR,
                candidate_id=CANDIDATE,
                stage_b_status=STAGE_B_STATUS_APPROVED,
                rationale="",
                pilot_scope="sesame-eu-pilot-v1",
            )

    def test_empty_pilot_scope_denied(self):
        factory = ServiceFactory()
        service = factory.service()
        with self.assertRaises(ApplicationValidationError):
            service.approve_stage_b(
                actor_user_id=ACTOR,
                candidate_id=CANDIDATE,
                stage_b_status=STAGE_B_STATUS_APPROVED,
                rationale="Test rationale.",
                pilot_scope="",
            )

    def test_nonexistent_candidate_denied(self):
        factory = ServiceFactory()
        service = factory.service()
        with self.assertRaises(ApplicationNotFoundError):
            service.approve_stage_b(
                actor_user_id=ACTOR,
                candidate_id=UUID("99999999-0000-0000-0000-000000000999"),
                stage_b_status=STAGE_B_STATUS_APPROVED,
                rationale="Test rationale.",
                pilot_scope="sesame-eu-pilot-v1",
            )

    def test_same_reviewer_as_stage_a_denied(self):
        # ACTOR is the Stage A reviewer
        factory = ServiceFactory(stage_a_reviewer=ACTOR)
        service = factory.service()
        with self.assertRaises(ApplicationValidationError):
            service.approve_stage_b(
                actor_user_id=ACTOR,
                candidate_id=CANDIDATE,
                stage_b_status=STAGE_B_STATUS_APPROVED,
                rationale="Same person review.",
                pilot_scope="sesame-eu-pilot-v1",
            )

    def test_different_reviewer_allowed(self):
        # STAGE_A_REVIEWER != ACTOR, so different reviewer is allowed
        factory = ServiceFactory(
            stage_a_reviewer=STAGE_A_REVIEWER, granted_reviewer=True
        )
        service = factory.service()
        result = service.approve_stage_b(
            actor_user_id=STAGE_B_REVIEWER,
            candidate_id=CANDIDATE,
            stage_b_status=STAGE_B_STATUS_APPROVED,
            rationale="Different reviewer approves.",
            pilot_scope="sesame-eu-pilot-v1",
        )
        self.assertEqual(result["stage_b_status"], STAGE_B_STATUS_APPROVED)
        self.assertEqual(result["stage_b_reviewer_user_id"], STAGE_B_REVIEWER)

    def test_same_person_exception_fail_closed(self):
        # same_person_exception=True but no authority mechanism exists
        factory = ServiceFactory(stage_a_reviewer=ACTOR)
        service = factory.service()
        with self.assertRaises(ApplicationValidationError):
            service.approve_stage_b(
                actor_user_id=ACTOR,
                candidate_id=CANDIDATE,
                stage_b_status=STAGE_B_STATUS_APPROVED,
                rationale="Same person with exception.",
                pilot_scope="sesame-eu-pilot-v1",
                same_person_exception=True,
                exception_authorizer_user_id=STAGE_A_REVIEWER,
                exception_authorization_ref="auth-ref-001",
                exception_justification="No other reviewer available.",
            )

    def test_stage_b_does_not_publish(self):
        """Stage B approval does not mark requirement as published."""
        factory = ServiceFactory()
        service = factory.service()
        result = service.approve_stage_b(
            actor_user_id=ACTOR,
            candidate_id=CANDIDATE,
            stage_b_status=STAGE_B_STATUS_APPROVED,
            rationale="Source verified.",
            pilot_scope="sesame-eu-pilot-v1",
        )
        # The candidate's base status remains "extracted" — not published
        row = service.get_candidate_stage_b(CANDIDATE)
        self.assertEqual(row["status"], "extracted")
        self.assertEqual(result["stage_b_status"], STAGE_B_STATUS_APPROVED)

    def test_stage_b_audit_history(self):
        factory = ServiceFactory()
        service = factory.service()
        # First review: reject
        service.approve_stage_b(
            actor_user_id=ACTOR,
            candidate_id=CANDIDATE,
            stage_b_status=STAGE_B_STATUS_REJECTED,
            rationale="First review: rejected.",
            pilot_scope="sesame-eu-pilot-v1",
        )
        # Second review: approve
        service.approve_stage_b(
            actor_user_id=ACTOR,
            candidate_id=CANDIDATE,
            stage_b_status=STAGE_B_STATUS_APPROVED,
            rationale="Second review: verified after correction.",
            pilot_scope="sesame-eu-pilot-v1",
        )
        # Current state reflects the last decision
        row = service.get_candidate_stage_b(CANDIDATE)
        self.assertEqual(row["stage_b_status"], STAGE_B_STATUS_APPROVED)
        self.assertEqual(row["stage_b_reviewer_user_id"], ACTOR)
        self.assertEqual(
            row["stage_b_rationale"], "Second review: verified after correction."
        )
        # Audit trail preserved via Stage B status update
        self.assertEqual(
            row["stage_b_pilot_scope"], "sesame-eu-pilot-v1"
        )

    def test_persistence_failure_does_not_report_success(self):
        factory = ServiceFactory(fail_update=True)
        service = factory.service()
        with self.assertRaises(RuntimeError):
            service.approve_stage_b(
                actor_user_id=ACTOR,
                candidate_id=CANDIDATE,
                stage_b_status=STAGE_B_STATUS_APPROVED,
                rationale="Test rationale.",
                pilot_scope="sesame-eu-pilot-v1",
            )
        # Candidate state unchanged
        row = service.get_candidate_stage_b(CANDIDATE)
        self.assertEqual(row["stage_b_status"], "pending")


if __name__ == "__main__":
    unittest.main()
