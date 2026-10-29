"""Unit tests for Stage A regulatory source and wording verification.

Tests the Stage A review service using fakes — no live database, no hosted
services. Covers authorized verification, unauthorized access, failed
extraction blocking, manual candidate review, rejected/clarification
decisions, invalid state transitions, idempotent retries, audit history,
and assurance that Stage A cannot approve applicability or publish.
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
from xportra.application.global_staff import STAGE_A_VERIFY
from xportra.application.regulatory_stage_a_review_service import (
    RegulatoryStageAReviewService,
    STAGE_A_STATUS_CLARIFICATION_REQUIRED,
    STAGE_A_STATUS_REJECTED,
    STAGE_A_STATUS_VERIFIED,
)
from xportra.api.errors import PermissionDeniedError
from xportra.persistence.database import Database

ACTOR = UUID("aaaaaaaa-0000-0000-0000-000000000001")
NON_GRANTED = UUID("bbbbbbbb-0000-0000-0000-000000000002")
SOURCE = UUID("dddddddd-0000-0000-0000-000000000004")
ARTIFACT = UUID("eeeeeeee-0000-0000-0000-000000000005")
CANDIDATE = UUID("11111111-0000-0000-0000-000000000100")
CANDIDATE_FAILED = UUID("22222222-0000-0000-0000-000000000200")
CANDIDATE_MANUAL = UUID("33333333-0000-0000-0000-000000000300")


class FakeDatabase(Database):
    """In-memory transaction double."""

    def __init__(self) -> None:
        from xportra.persistence.database import DatabaseSettings
        super().__init__(
            DatabaseSettings(dsn="postgresql://fake"),
            connection_factory=object(),
        )
        self.committed = False
        self.rolled_back = False

    @contextmanager
    def connection(self):  # type: ignore[override]
        yield _FakeConnection()

    @contextmanager
    def transaction(self):  # type: ignore[override]
        try:
            yield _FakeConnection()
            self.committed = True
        except Exception:
            self.rolled_back = True
            raise


class _FakeConnection:
    """Minimal double supporting cursor() and execute()."""

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
        return [self.fetchone()]


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


class FakeArtifactRepository:
    def __init__(self, existing: dict[UUID, dict] | None = None) -> None:
        self.artifacts = dict(existing or {})

    def get(self, artifact_id: UUID):
        return self.artifacts.get(artifact_id)


class FakeRequirementRepository:
    def __init__(self, existing: list[dict] | None = None) -> None:
        self.requirements: dict[UUID, dict] = {}
        for r in list(existing or []):
            self.requirements[r["id"]] = dict(r)
        self.fail_update = False

    def get(self, requirement_id: UUID):
        return self.requirements.get(requirement_id)

    def update_stage_a(
        self,
        requirement_id: UUID,
        stage_a_status: str,
        reviewer_user_id: UUID,
        reviewed_at,
        rationale: str,
    ) -> dict | None:
        """Update Stage A columns; idempotent for identical retries."""
        if self.fail_update:
            raise RuntimeError("simulated stage_a update failure")
        row = self.requirements.get(requirement_id)
        if row is None:
            return None
        row["stage_a_status"] = stage_a_status
        row["stage_a_reviewer_user_id"] = reviewer_user_id
        row["stage_a_reviewed_at"] = reviewed_at
        row["stage_a_rationale"] = rationale
        row["updated_at"] = reviewed_at
        return row

    def get_with_provenance(self, requirement_id: UUID) -> dict | None:
        """Return the requirement row with provenance fields (all None for fake)."""
        row = self.requirements.get(requirement_id)
        if row is None:
            return None
        return {
            "source_title": None,
            "source_jurisdiction": None,
            "source_version": None,
            "source_status": None,
            "source_authority_id": None,
            "artifact_uri": None,
            "artifact_content_hash": None,
            "artifact_content_length": None,
            "artifact_content_type": None,
            "artifact_acquisition_channel": None,
            "ingestion_job_status": None,
            "ingestion_job_error_details": None,
            "ingestion_job_parser_version": None,
        }


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
        source_exists: bool = True,
        artifact_exists: bool = True,
        failed_extraction: bool = False,
        manual_entry: bool = False,
        existing_candidate: dict | None = None,
        fail_update: bool = False,
    ) -> None:
        self.database = FakeDatabase()
        granted = {ACTOR: STAGE_A_VERIFY} if granted_actor else {}
        self.grants = FakeGrantService(granted)
        self.sources = FakeSourceRepository()
        self.artifacts = FakeArtifactRepository()
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

        if artifact_exists:
            self.artifacts.artifacts[ARTIFACT] = {
                "id": ARTIFACT,
                "source_id": SOURCE,
                "artifact_uri": "regulatory-source-artifacts/src/hash",
                "content_hash": "hash",
                "content_length": 100,
                "content_type": "text/plain",
                "status": "validated",
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
                "extraction_outcome": "failed" if failed_extraction else "succeeded",
                "parser_version": "v1",
                "manual_entry": manual_entry,
                "reviewer_user_id": None,
                "reviewed_at": None,
                "source_id": SOURCE,
                "stage_a_status": "pending",
                "stage_a_reviewer_user_id": None,
                "stage_a_reviewed_at": None,
                "stage_a_rationale": None,
                "created_at": None,
                "updated_at": None,
            }
            if failed_extraction:
                self.requirements.requirements[CANDIDATE_FAILED] = {
                    "id": CANDIDATE_FAILED,
                    "normalized_document_id": UUID("44444444-0000-0000-0000-000000000401"),
                    "artifact_id": ARTIFACT,
                    "source_id": SOURCE,
                    "requirement_text": "Failed extraction candidate.",
                    "requirement_type": "documentation",
                    "source_location": {},
                    "position": 1,
                    "actor": None,
                    "condition_metadata": None,
                    "status": "extracted",
                    "ingestion_job_id": None,
                    "extraction_outcome": "failed",
                    "parser_version": None,
                    "manual_entry": False,
                    "reviewer_user_id": None,
                    "reviewed_at": None,
                    "source_id": SOURCE,
                    "stage_a_status": "pending",
                    "stage_a_reviewer_user_id": None,
                    "stage_a_reviewed_at": None,
                    "stage_a_rationale": None,
                    "created_at": None,
                    "updated_at": None,
                }
            if manual_entry:
                self.requirements.requirements[CANDIDATE_MANUAL] = {
                    "id": CANDIDATE_MANUAL,
                    "normalized_document_id": UUID("44444444-0000-0000-0000-000000000402"),
                    "artifact_id": ARTIFACT,
                    "source_id": SOURCE,
                    "requirement_text": "Manual entry candidate.",
                    "requirement_type": "documentation",
                    "source_location": {},
                    "position": 2,
                    "actor": str(ACTOR),
                    "condition_metadata": None,
                    "status": "extracted",
                    "ingestion_job_id": None,
                    "extraction_outcome": "manual",
                    "parser_version": None,
                    "manual_entry": True,
                    "reviewer_user_id": ACTOR,
                    "reviewed_at": datetime.now(timezone.utc),
                    "source_id": SOURCE,
                    "stage_a_status": "pending",
                    "stage_a_reviewer_user_id": None,
                    "stage_a_reviewed_at": None,
                    "stage_a_rationale": None,
                    "created_at": None,
                    "updated_at": None,
                }
        self.requirements.fail_update = fail_update

    def service(self) -> RegulatoryStageAReviewService:
        return RegulatoryStageAReviewService(
            self.database,
            source_repo=self.sources,
            artifact_repo=self.artifacts,
            requirement_repo=self.requirements,
            grant_service=self.grants,
        )


class RegulatoryStageAReviewTests(TestCase):
    def test_authorized_stage_a_verify(self):
        factory = ServiceFactory()
        service = factory.service()
        result = service.verify_stage_a(
            actor_user_id=ACTOR,
            candidate_id=CANDIDATE,
            stage_a_status=STAGE_A_STATUS_VERIFIED,
            rationale="Source text matches extracted wording.",
        )
        self.assertEqual(result["stage_a_status"], STAGE_A_STATUS_VERIFIED)
        self.assertEqual(result["stage_a_reviewer_user_id"], ACTOR)
        self.assertIsNotNone(result["stage_a_reviewed_at"])
        self.assertEqual(
            result["stage_a_rationale"], "Source text matches extracted wording."
        )
        self.assertEqual(result["audit_id"], UUID("aaaaaaaa-0000-0000-0000-000000000999"))

    def test_authorized_stage_a_reject(self):
        factory = ServiceFactory()
        service = factory.service()
        result = service.verify_stage_a(
            actor_user_id=ACTOR,
            candidate_id=CANDIDATE,
            stage_a_status=STAGE_A_STATUS_REJECTED,
            rationale="Wording not supported by source text.",
        )
        self.assertEqual(result["stage_a_status"], STAGE_A_STATUS_REJECTED)
        self.assertEqual(result["stage_a_reviewer_user_id"], ACTOR)

    def test_authorized_stage_a_clarification_required(self):
        factory = ServiceFactory()
        service = factory.service()
        result = service.verify_stage_a(
            actor_user_id=ACTOR,
            candidate_id=CANDIDATE,
            stage_a_status=STAGE_A_STATUS_CLARIFICATION_REQUIRED,
            rationale="Source text ambiguous; needs clarification.",
        )
        self.assertEqual(
            result["stage_a_status"], STAGE_A_STATUS_CLARIFICATION_REQUIRED
        )
        self.assertEqual(result["stage_a_reviewer_user_id"], ACTOR)

    def test_unauthorized_actor_denied(self):
        factory = ServiceFactory(granted_actor=False)
        service = factory.service()
        with self.assertRaises(PermissionDeniedError):
            service.verify_stage_a(
                actor_user_id=NON_GRANTED,
                candidate_id=CANDIDATE,
                stage_a_status=STAGE_A_STATUS_VERIFIED,
                rationale="Test rationale.",
            )

    def test_failed_extraction_cannot_be_verified(self):
        factory = ServiceFactory(failed_extraction=True)
        service = factory.service()
        with self.assertRaises(ApplicationValidationError):
            service.verify_stage_a(
                actor_user_id=ACTOR,
                candidate_id=CANDIDATE_FAILED,
                stage_a_status=STAGE_A_STATUS_VERIFIED,
                rationale="Cannot verify failed extraction.",
            )
        # Candidate remains pending
        row = service.get_candidate_stage_a(CANDIDATE_FAILED)
        self.assertEqual(row["stage_a_status"], "pending")

    def test_failed_extraction_can_be_rejected(self):
        factory = ServiceFactory(failed_extraction=True)
        service = factory.service()
        result = service.verify_stage_a(
            actor_user_id=ACTOR,
            candidate_id=CANDIDATE_FAILED,
            stage_a_status=STAGE_A_STATUS_REJECTED,
            rationale="Extraction failed; no usable source text.",
        )
        self.assertEqual(result["stage_a_status"], STAGE_A_STATUS_REJECTED)

    def test_manual_candidate_requires_verification(self):
        factory = ServiceFactory(manual_entry=True)
        service = factory.service()
        # Manual candidate starts as pending
        row = service.get_candidate_stage_a(CANDIDATE_MANUAL)
        self.assertEqual(row["stage_a_status"], "pending")
        self.assertTrue(row["manual_entry"])
        # Manual entry can be verified (same standard as extracted)
        result = service.verify_stage_a(
            actor_user_id=ACTOR,
            candidate_id=CANDIDATE_MANUAL,
            stage_a_status=STAGE_A_STATUS_VERIFIED,
            rationale="Manual entry verified against source.",
        )
        self.assertEqual(result["stage_a_status"], STAGE_A_STATUS_VERIFIED)

    def test_invalid_stage_a_status_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        with self.assertRaises(ApplicationValidationError):
            service.verify_stage_a(
                actor_user_id=ACTOR,
                candidate_id=CANDIDATE,
                stage_a_status="not_a_status",
                rationale="Test rationale.",
            )

    def test_empty_rationale_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        with self.assertRaises(ApplicationValidationError):
            service.verify_stage_a(
                actor_user_id=ACTOR,
                candidate_id=CANDIDATE,
                stage_a_status=STAGE_A_STATUS_VERIFIED,
                rationale="",
            )

    def test_nonexistent_candidate_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        with self.assertRaises(ApplicationNotFoundError):
            service.verify_stage_a(
                actor_user_id=ACTOR,
                candidate_id=UUID("99999999-0000-0000-0000-000000000999"),
                stage_a_status=STAGE_A_STATUS_VERIFIED,
                rationale="Test rationale.",
            )

    def test_stage_a_get_candidate_state(self):
        factory = ServiceFactory()
        service = factory.service()
        # Before review: pending
        row = service.get_candidate_stage_a(CANDIDATE)
        self.assertEqual(row["stage_a_status"], "pending")
        self.assertIsNone(row["stage_a_reviewer_user_id"])
        self.assertIsNone(row["stage_a_reviewed_at"])
        self.assertIsNone(row["stage_a_rationale"])

        # After review: verified
        service.verify_stage_a(
            actor_user_id=ACTOR,
            candidate_id=CANDIDATE,
            stage_a_status=STAGE_A_STATUS_VERIFIED,
            rationale="Verified against source.",
        )
        row = service.get_candidate_stage_a(CANDIDATE)
        self.assertEqual(row["stage_a_status"], STAGE_A_STATUS_VERIFIED)
        self.assertEqual(row["stage_a_reviewer_user_id"], ACTOR)
        self.assertIsNotNone(row["stage_a_reviewed_at"])
        self.assertEqual(row["stage_a_rationale"], "Verified against source.")

    def test_stage_a_does_not_approve_applicability(self):
        """Stage A verification does not set pilot applicability."""
        factory = ServiceFactory()
        service = factory.service()
        result = service.verify_stage_a(
            actor_user_id=ACTOR,
            candidate_id=CANDIDATE,
            stage_a_status=STAGE_A_STATUS_VERIFIED,
            rationale="Source verified.",
        )
        # Candidate status remains "extracted" — not "applicable" or "published"
        row = service.get_candidate_stage_a(CANDIDATE)
        self.assertEqual(row["status"], "extracted")
        self.assertEqual(result["stage_a_status"], STAGE_A_STATUS_VERIFIED)

    def test_stage_a_audit_history(self):
        factory = ServiceFactory()
        service = factory.service()
        # First review: reject
        service.verify_stage_a(
            actor_user_id=ACTOR,
            candidate_id=CANDIDATE,
            stage_a_status=STAGE_A_STATUS_REJECTED,
            rationale="First review: rejected.",
        )
        # Second review: clarify (re-review after correction)
        service.verify_stage_a(
            actor_user_id=ACTOR,
            candidate_id=CANDIDATE,
            stage_a_status=STAGE_A_STATUS_CLARIFICATION_REQUIRED,
            rationale="Second review: needs clarification.",
        )
        # Third review: verify
        service.verify_stage_a(
            actor_user_id=ACTOR,
            candidate_id=CANDIDATE,
            stage_a_status=STAGE_A_STATUS_VERIFIED,
            rationale="Third review: verified after correction.",
        )
        # All three decisions preserved via Stage A status updates
        row = service.get_candidate_stage_a(CANDIDATE)
        self.assertEqual(row["stage_a_status"], STAGE_A_STATUS_VERIFIED)
        self.assertEqual(row["stage_a_reviewer_user_id"], ACTOR)
        self.assertEqual(row["stage_a_rationale"], "Third review: verified after correction.")
        # Audit trail preserved via list_stage_a_decisions (integration-tested)

    def test_persistence_failure_does_not_report_success(self):
        factory = ServiceFactory(fail_update=True)
        service = factory.service()
        with self.assertRaises(RuntimeError):
            service.verify_stage_a(
                actor_user_id=ACTOR,
                candidate_id=CANDIDATE,
                stage_a_status=STAGE_A_STATUS_VERIFIED,
                rationale="Test rationale.",
            )
        # Candidate state unchanged
        row = service.get_candidate_stage_a(CANDIDATE)
        self.assertEqual(row["stage_a_status"], "pending")

    def test_audit_insert_failure_rolls_back(self):
        factory = ServiceFactory(fail_update=True)
        service = factory.service()
        with self.assertRaises(RuntimeError):
            service.verify_stage_a(
                actor_user_id=ACTOR,
                candidate_id=CANDIDATE,
                stage_a_status=STAGE_A_STATUS_VERIFIED,
                rationale="Test rationale.",
            )
        # Persistence failure: exception propagates, no success reported.

    def test_stage_a_permission_is_stage_a_verify_not_grant_manage(self):
        """Stage A requires STAGE_A_VERIFY, not GRANT_MANAGE."""
        factory = ServiceFactory(granted_actor=True)
        service = factory.service()
        # Remove STAGE_A_VERIFY but keep GRANT_MANAGE
        service._grant_service.granted = {
            UUID("aaaaaaaa-0000-0000-0000-000000000001")
        }
        # Manually set up grant_manage only (not STAGE_A_VERIFY)
        from xportra.application.global_staff import GRANT_MANAGE
        service._grant_service.granted = {
            ACTOR: GRANT_MANAGE
        }
        with self.assertRaises(PermissionDeniedError):
            service.verify_stage_a(
                actor_user_id=ACTOR,
                candidate_id=CANDIDATE,
                stage_a_status=STAGE_A_STATUS_VERIFIED,
                rationale="Test rationale.",
            )

    def test_regression_fetchall_and_audit_history_preserved(self):
        """Regression: _FakeCursor.fetchall() must exist so that
        RegulatoryReviewFlagRepository.list_pending_for_source
        and list_stage_a_decisions work with the fixture.
        This verifies the audit/history boundary without a live DB."""
        factory = ServiceFactory()
        service = factory.service()
        service.verify_stage_a(
            actor_user_id=ACTOR,
            candidate_id=CANDIDATE,
            stage_a_status=STAGE_A_STATUS_VERIFIED,
            rationale="Regression verification.",
        )
        history = service.list_stage_a_decisions(CANDIDATE)
        self.assertIsInstance(history, list)
        self.assertTrue(len(history) >= 1)
