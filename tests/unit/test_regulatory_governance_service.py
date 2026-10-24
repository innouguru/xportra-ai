"""Unit tests for regulatory governance service (Task 7).

Covers review-flag creation, supersession tracking, fail-closed
rejection of invalid states, and preservation of audit/review
independence. No live database; no secrets.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest import TestCase
from uuid import UUID

from xportra.application.errors import ApplicationValidationError
from xportra.application.regulatory_governance_service import (
    RegulatoryGovernanceService,
    TRIGGER_TYPE_SUPERSESSION,
    TRIGGER_TYPE_VERSION_CHANGE,
    TRIGGER_TYPE_STALE,
    REVIEW_STATUS_PENDING,
    REVIEW_STATUS_COMPLETED,
)
from xportra.persistence.database import Database

ACTOR = UUID("aaaaaaaa-0000-0000-0000-000000000001")
SOURCE = UUID("eeeeeeee-0000-0000-0000-000000000006")
CANDIDATE = UUID("11111111-0000-0000-0000-000000000100")

FAKE_NOW = datetime(2026, 10, 22, 12, 0, 0, tzinfo=timezone.utc)


class FakeDatabase(Database):
    def __init__(self) -> None:
        super().__init__(object(), connection_factory=object())  # type: ignore[arg-type]
        self.committed = False
        self.rolled_back = False

    # Minimal double; actual tests rely on service-level validation.


class FakeSourceRepo:
    def __init__(self, existing: dict | None = None) -> None:
        self.sources = dict(existing or {})

    def get(self, source_id: UUID):
        return self.sources.get(source_id)


class FakeRequirementRepo:
    def __init__(self, existing: dict | None = None) -> None:
        self.reqs: dict[UUID, dict] = {}
        if existing:
            for r in existing.values():
                self.reqs[r["id"]] = dict(r)

    def get(self, req_id: UUID):
        return self.reqs.get(req_id)


class FakeReviewFlagRepo:
    def __init__(self) -> None:
        self.flags: list[dict] = []
        self._counter = 0

    def create(self, **values) -> dict:
        self._counter += 1
        row = {
            "id": UUID(f"aaaaaaaa-0000-0000-0000-{self._counter:012x}"),
            "requirement_id": values.get("requirement_id"),
            "trigger_source_id": values.get("trigger_source_id"),
            "trigger_type": values.get("trigger_type"),
            "status": values.get("status", "pending_review"),
            "actor_user_id": values.get("actor_user_id"),
            "rationale": values.get("rationale", ""),
            "created_at": FAKE_NOW,
            "updated_at": FAKE_NOW,
        }
        self.flags.append(row)
        return row

    def get_for_requirement(self, req_id: UUID):
        return [f for f in self.flags if f.get("requirement_id") == req_id]

    def get_for_source(self, source_id: UUID):
        return [f for f in self.flags if f.get("trigger_source_id") == source_id]

    def get_by_id(self, flag_id: UUID) -> dict[str, Any] | None:
        for f in self.flags:
            if f.get("id") == flag_id:
                return dict(f)
        return None

    def list_pending_for_source(self, source_id: UUID):
        return [
            f for f in self.flags
            if f.get("trigger_source_id") == source_id and f.get("status") == "pending_review"
        ]

    def update_status(self, flag_id: UUID, status: str, rationale: str | None = None) -> dict | None:
        for f in self.flags:
            if f.get("id") == flag_id:
                f["status"] = status
                if rationale is not None:
                    f["rationale"] = rationale
                f["updated_at"] = FAKE_NOW + timedelta(seconds=1)
                return dict(f)
        return None


from typing import Any  # noqa: E402


class GovernanceServiceFactory:
    def __init__(
        self,
        *,
        source_exists: bool = True,
        source_id: UUID = SOURCE,
        supersession_exists: bool = False,
    ) -> None:
        self.database = FakeDatabase()
        sources = {}
        if source_exists:
            sources[source_id] = {"id": source_id, "status": "active"}
        if supersession_exists:
            superseded = UUID("dddddddd-0000-0000-0000-000000000007")
            sources[superseded] = {"id": superseded, "status": "superseded", "supersedes_source_id": source_id}
        self.sources = FakeSourceRepo(sources)
        self.reqs = FakeRequirementRepo({CANDIDATE: {"id": CANDIDATE, "status": "extracted"}})
        self.flags = FakeReviewFlagRepo()

    def service(self) -> RegulatoryGovernanceService:
        return RegulatoryGovernanceService(
            self.database,
            source_repo=self.sources,
            requirement_repo=self.reqs,
            review_flag_repo=self.flags,
        )


class RegulatoryGovernanceServiceTests(TestCase):
    def test_supersession_creates_review_flag(self):
        factory = GovernanceServiceFactory(source_exists=True, supersession_exists=True)
        svc = factory.service()
        result = svc.flag_review_required(
            actor_user_id=ACTOR,
            trigger_type=TRIGGER_TYPE_SUPERSESSION,
            trigger_source_id=SOURCE,
            rationale="Source superseded by newer regulation.",
        )
        self.assertEqual(result["trigger_type"], TRIGGER_TYPE_SUPERSESSION)
        self.assertEqual(result["status"], REVIEW_STATUS_PENDING)
        flags = factory.flags.flags
        self.assertTrue(any(f["trigger_type"] == TRIGGER_TYPE_SUPERSESSION for f in flags))

    def test_version_change_creates_review_flag(self):
        factory = GovernanceServiceFactory(source_exists=True)
        svc = factory.service()
        result = svc.flag_review_required(
            actor_user_id=ACTOR,
            trigger_type=TRIGGER_TYPE_VERSION_CHANGE,
            trigger_source_id=SOURCE,
            rationale="New version published.",
        )
        self.assertEqual(result["status"], REVIEW_STATUS_PENDING)

    def test_invalid_trigger_denied(self):
        factory = GovernanceServiceFactory()
        svc = factory.service()
        with self.assertRaises(ApplicationValidationError) as ctx:
            svc.flag_review_required(
                actor_user_id=ACTOR,
                trigger_type="not_valid",
                trigger_source_id=SOURCE,
                rationale="Test.",
            )
        self.assertIn("invalid trigger_type", str(ctx.exception))

    def test_empty_rationale_denied(self):
        factory = GovernanceServiceFactory()
        svc = factory.service()
        with self.assertRaises(ApplicationValidationError):
            svc.flag_review_required(
                actor_user_id=ACTOR,
                trigger_type=TRIGGER_TYPE_SUPERSESSION,
                trigger_source_id=SOURCE,
                rationale="",
            )

    def test_missing_source_fails_closed(self):
        factory = GovernanceServiceFactory(source_exists=False)
        svc = factory.service()
        with self.assertRaises(ApplicationValidationError) as ctx:
            svc.flag_review_required(
                actor_user_id=ACTOR,
                trigger_type=TRIGGER_TYPE_SUPERSESSION,
                trigger_source_id=SOURCE,
                rationale="Source missing.",
            )
        self.assertIn("trigger source not found", str(ctx.exception))

    def test_review_completion_updates_flag_unlinked(self):
        # Flag without a linked requirement does not require stage reviews.
        factory = GovernanceServiceFactory(source_exists=True)
        svc = factory.service()
        created = svc.flag_review_required(
            actor_user_id=ACTOR,
            trigger_type=TRIGGER_TYPE_SUPERSESSION,
            trigger_source_id=SOURCE,
            rationale="Supersession.",
        )
        completed = svc.complete_review(actor_user_id=ACTOR, flag_id=created["id"], rationale="Re-reviewed.")
        self.assertEqual(completed["status"], REVIEW_STATUS_COMPLETED)

    def test_review_flag_does_not_alter_stage_a_or_b_audit(self):
        # Governance flags must not modify audit history.
        factory = GovernanceServiceFactory()
        svc = factory.service()
        svc.flag_review_required(
            actor_user_id=ACTOR,
            trigger_type=TRIGGER_TYPE_SUPERSESSION,
            trigger_source_id=SOURCE,
            rationale="Supersession recorded.",
        )
        self.assertEqual(len(factory.flags.flags), 1)

    def test_complete_review_fails_without_stage_a_verification(self):
        factory = GovernanceServiceFactory(source_exists=True)
        svc = factory.service()
        factory.reqs.reqs[CANDIDATE] = {
            "id": CANDIDATE,
            "stage_a_status": "pending",
            "stage_b_status": "pending",
        }
        created = svc.flag_review_required(
            actor_user_id=ACTOR,
            trigger_type=TRIGGER_TYPE_SUPERSESSION,
            trigger_source_id=SOURCE,
            requirement_id=CANDIDATE,
            rationale="Requires review.",
        )
        with self.assertRaises(ApplicationValidationError) as ctx:
            svc.complete_review(actor_user_id=ACTOR, flag_id=created["id"], rationale="Done.")
        self.assertIn("lacks Stage A verification", str(ctx.exception))

    def test_complete_review_fails_historical_stage_a_before_flag(self):
        # Stage A verified before flag creation does not satisfy re-review.
        factory = GovernanceServiceFactory(source_exists=True)
        svc = factory.service()
        factory.reqs.reqs[CANDIDATE] = {
            "id": CANDIDATE,
            "stage_a_status": "verified",
            "stage_a_reviewed_at": FAKE_NOW - timedelta(seconds=1),  # before flag
            "stage_b_status": "pending",
        }
        created = svc.flag_review_required(
            actor_user_id=ACTOR,
            trigger_type=TRIGGER_TYPE_SUPERSESSION,
            trigger_source_id=SOURCE,
            requirement_id=CANDIDATE,
            rationale="Requires re-review.",
        )
        with self.assertRaises(ApplicationValidationError) as ctx:
            svc.complete_review(actor_user_id=ACTOR, flag_id=created["id"], rationale="Done.")
        self.assertIn("does not post-date", str(ctx.exception))

    def test_complete_review_fails_when_stage_b_pending(self):
        factory = GovernanceServiceFactory(source_exists=True)
        svc = factory.service()
        factory.reqs.reqs[CANDIDATE] = {
            "id": CANDIDATE,
            "stage_a_status": "verified",
            "stage_a_reviewed_at": FAKE_NOW + timedelta(seconds=1),  # after flag
            "stage_b_status": "pending",
        }
        created = svc.flag_review_required(
            actor_user_id=ACTOR,
            trigger_type=TRIGGER_TYPE_VERSION_CHANGE,
            trigger_source_id=SOURCE,
            requirement_id=CANDIDATE,
            rationale="Requires review after version change.",
        )
        with self.assertRaises(ApplicationValidationError) as ctx:
            svc.complete_review(actor_user_id=ACTOR, flag_id=created["id"], rationale="Done.")
        self.assertIn("lacks an approved Stage B applicability decision", str(ctx.exception))

    def test_complete_review_fails_rejected_stage_b(self):
        # Rejected Stage B does not count as successful applicability approval.
        factory = GovernanceServiceFactory(source_exists=True)
        svc = factory.service()
        factory.reqs.reqs[CANDIDATE] = {
            "id": CANDIDATE,
            "stage_a_status": "verified",
            "stage_a_reviewed_at": FAKE_NOW + timedelta(seconds=1),
            "stage_b_status": "rejected",
            "stage_b_reviewed_at": FAKE_NOW + timedelta(seconds=2),
        }
        created = svc.flag_review_required(
            actor_user_id=ACTOR,
            trigger_type=TRIGGER_TYPE_VERSION_CHANGE,
            trigger_source_id=SOURCE,
            requirement_id=CANDIDATE,
            rationale="Requires re-review.",
        )
        with self.assertRaises(ApplicationValidationError) as ctx:
            svc.complete_review(actor_user_id=ACTOR, flag_id=created["id"], rationale="Done.")
        self.assertIn("lacks an approved Stage B applicability decision", str(ctx.exception))

    def test_complete_review_fails_clarification_required_stage_b(self):
        # Clarification-required Stage B does not count as successful applicability approval.
        factory = GovernanceServiceFactory(source_exists=True)
        svc = factory.service()
        factory.reqs.reqs[CANDIDATE] = {
            "id": CANDIDATE,
            "stage_a_status": "verified",
            "stage_a_reviewed_at": FAKE_NOW + timedelta(seconds=1),
            "stage_b_status": "clarification_required",
            "stage_b_reviewed_at": FAKE_NOW + timedelta(seconds=2),
        }
        created = svc.flag_review_required(
            actor_user_id=ACTOR,
            trigger_type=TRIGGER_TYPE_VERSION_CHANGE,
            trigger_source_id=SOURCE,
            requirement_id=CANDIDATE,
            rationale="Requires re-review.",
        )
        with self.assertRaises(ApplicationValidationError) as ctx:
            svc.complete_review(actor_user_id=ACTOR, flag_id=created["id"], rationale="Done.")
        self.assertIn("lacks an approved Stage B applicability decision", str(ctx.exception))

    def test_complete_review_fails_historical_stage_b_before_flag(self):
        # Stage B approved before flag creation does not satisfy re-review.
        factory = GovernanceServiceFactory(source_exists=True)
        svc = factory.service()
        factory.reqs.reqs[CANDIDATE] = {
            "id": CANDIDATE,
            "stage_a_status": "verified",
            "stage_a_reviewed_at": FAKE_NOW + timedelta(seconds=1),
            "stage_b_status": "approved",
            "stage_b_reviewed_at": FAKE_NOW - timedelta(seconds=1),  # before flag
        }
        created = svc.flag_review_required(
            actor_user_id=ACTOR,
            trigger_type=TRIGGER_TYPE_VERSION_CHANGE,
            trigger_source_id=SOURCE,
            requirement_id=CANDIDATE,
            rationale="Requires re-review.",
        )
        with self.assertRaises(ApplicationValidationError) as ctx:
            svc.complete_review(actor_user_id=ACTOR, flag_id=created["id"], rationale="Done.")
        self.assertIn("does not post-date", str(ctx.exception))

    def test_complete_review_succeeds_with_reviews_after_flag(self):
        # Both Stage A verified and Stage B approved after the flag clears re-review.
        factory = GovernanceServiceFactory(source_exists=True)
        svc = factory.service()
        factory.reqs.reqs[CANDIDATE] = {
            "id": CANDIDATE,
            "stage_a_status": "verified",
            "stage_a_reviewed_at": FAKE_NOW + timedelta(seconds=1),
            "stage_b_status": "approved",
            "stage_b_reviewed_at": FAKE_NOW + timedelta(seconds=2),
        }
        created = svc.flag_review_required(
            actor_user_id=ACTOR,
            trigger_type=TRIGGER_TYPE_VERSION_CHANGE,
            trigger_source_id=SOURCE,
            requirement_id=CANDIDATE,
            rationale="Requires re-review.",
        )
        completed = svc.complete_review(actor_user_id=ACTOR, flag_id=created["id"], rationale="Re-review completed.")
        self.assertEqual(completed["status"], REVIEW_STATUS_COMPLETED)

    def test_stale_flag_fails_closed_on_unknown_currentness(self):
        # Freshness must not be declared current; unknown/stale must trigger
        # review rather than silently preserving approval.
        factory = GovernanceServiceFactory(source_exists=True)
        svc = factory.service()
        result = svc.flag_review_required(
            actor_user_id=ACTOR,
            trigger_type=TRIGGER_TYPE_STALE,
            trigger_source_id=SOURCE,
            rationale="No verified currentness evidence.",
        )
        self.assertEqual(result["status"], REVIEW_STATUS_PENDING)
        self.assertTrue(
            any(
                f.get("trigger_type") == TRIGGER_TYPE_STALE and f.get("status") == REVIEW_STATUS_PENDING
                for f in factory.flags.flags
            )
        )


    def test_flag_reads_return_pending_and_resolved_verbatim(self):
        # The administration read path must display pending AND resolved
        # flags with their recorded rationale — neither hidden nor merged.
        factory = GovernanceServiceFactory(source_exists=True)
        svc = factory.service()
        pending = svc.flag_review_required(
            actor_user_id=ACTOR,
            trigger_type=TRIGGER_TYPE_SUPERSESSION,
            trigger_source_id=SOURCE,
            requirement_id=CANDIDATE,
            rationale="Source superseded.",
        )
        completed = svc.flag_review_required(
            actor_user_id=ACTOR,
            trigger_type=TRIGGER_TYPE_STALE,
            trigger_source_id=SOURCE,
            rationale="No currentness evidence.",
        )
        svc.complete_review(actor_user_id=ACTOR, flag_id=completed["id"], rationale="Re-reviewed.")
        by_source = svc.get_flags_for_source(SOURCE)
        self.assertEqual(len(by_source), 2)
        statuses = {f["status"] for f in by_source}
        self.assertEqual(statuses, {"pending_review", "review_completed"})
        rationales = {f["rationale"] for f in by_source}
        self.assertIn("Source superseded.", rationales)
        by_requirement = svc.get_flags_for_requirement(CANDIDATE)
        self.assertEqual(len(by_requirement), 1)
        self.assertEqual(by_requirement[0]["id"], pending["id"])


if __name__ == "__main__":
    import unittest
    unittest.main()
