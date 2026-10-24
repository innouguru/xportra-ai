"""Regression test: governance flags block Stage B approval.

Uses a minimal monkey-patch on the repository class to inject a
pending-flag response, confirming the fail-closed enforcement
path without requiring a full database transaction.
"""
from unittest import TestCase
from uuid import UUID

from xportra.application.errors import ApplicationValidationError
from xportra.application.regulatory_governance_service import (
    TRIGGER_TYPE_SUPERSESSION,
)
from xportra.application.regulatory_stage_b_review_service import (
    RegulatoryStageBReviewService,
    STAGE_B_STATUS_APPROVED,
)
from tests.unit.test_regulatory_stage_b_review import (
    ServiceFactory,
    ACTOR,
    SOURCE,
    CANDIDATE,
)


class GovernanceBlocksStageBTests(TestCase):
    def test_pending_flag_blocks_stage_b_approve(self):
        factory = ServiceFactory()
        import unittest.mock
        import xportra.application.regulatory_stage_b_review_service as stage_b_mod
        original_class = stage_b_mod.RegulatoryReviewFlagRepository

        class PendingRepo(original_class):
            def list_pending_for_source(self, source_id):
                return [{"status": "pending_review", "trigger_type": "supersession"}]
            def get_for_requirement(self, req_id):
                return [{"status": "pending_review", "trigger_type": "stale"}]

        stage_b_mod.RegulatoryReviewFlagRepository = PendingRepo
        try:
            service = factory.service()
            with self.assertRaises(ApplicationValidationError) as ctx:
                service.approve_stage_b(
                    actor_user_id=ACTOR,
                    candidate_id=CANDIDATE,
                    stage_b_status=STAGE_B_STATUS_APPROVED,
                    rationale="Test.",
                    pilot_scope="sesame-eu-pilot-v1",
                )
            msg = str(ctx.exception)
            self.assertTrue(
                "pending governance flags" in msg or "re-review is required" in msg,
                f"Expected governance block message, got: {msg}",
            )
        finally:
            stage_b_mod.RegulatoryReviewFlagRepository = original_class
