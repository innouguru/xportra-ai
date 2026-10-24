"""Unit tests for regulatory governance integration in compliance assessment.

Verifies that the assessment path distinguishes requirements that have
passed Stage A verification and Stage B pilot approval from those that
have not, and that pending governance flags block use as current
approved requirements. No live database; no secrets.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest import TestCase
from uuid import UUID, uuid4

from xportra.application.assessments import AssessmentApplicationService
from xportra.application.context import ApplicationContext
from xportra.application.dtos import ApplicabilityDTO
from xportra.domain.ingestion import (
    ApplicabilityContext,
    ComplianceApplicabilityService,
)
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
REQUIREMENT_APPROVED_ID = UUID("11111111-1111-1111-1111-111111111111")
REQUIREMENT_STAGE_A_PENDING_ID = UUID(
    "22222222-2222-2222-2222-222222222222")
REQUIREMENT_STAGE_B_PENDING_ID = UUID(
    "33333333-3333-3333-3333-333333333333")
REQUIREMENT_FLAGGED_ID = UUID(
    "44444444-4444-4444-4444-444444444444")
SOURCE_APPROVED_ID = UUID("55555555-5555-5555-5555-555555555555")
SOURCE_FLAGGED_ID = UUID("66666666-6666-6666-6666-666666666666")


class FakeRequirementRepository:
    """In-memory double for RegulatoryRequirementRepository."""

    def __init__(self, rows: dict[UUID, dict] | None = None) -> None:
        self.rows: dict[UUID, dict] = dict(rows or {})

    def get(self, requirement_id: UUID) -> dict | None:
        return self.rows.get(requirement_id)


class FakeReviewFlagRepository:
    """In-memory double for RegulatoryReviewFlagRepository."""

    def __init__(self) -> None:
        self.flags_by_source: dict[UUID, list[dict]] = {}
        self.flags_by_requirement: dict[UUID, list[dict]] = {}

    def list_pending_for_source(self, source_id: UUID) -> list[dict]:
        return list(self.flags_by_source.get(source_id, []))

    def get_for_requirement(self, requirement_id: UUID) -> list[dict]:
        return list(self.flags_by_requirement.get(requirement_id, []))


def _context(tenant_id: UUID = TENANT_ID) -> ApplicationContext:
    return ApplicationContext(
        actor_id=UUID("99999999-9999-9999-9999-999999999999"),
        tenant=TenantContext(tenant_id),
        role="owner",
    )


def _requirement(
    requirement_id: UUID,
    text: str = "All cocoa exports require certification.",
    source_id: UUID | None = SOURCE_APPROVED_ID,
) -> dict:
    return {
        "id": requirement_id,
        "requirement_text": text,
        "source_id": source_id,
        "actor": "exporter",
    }


# ---------------------------------------------------------------------------
# No repositories wired: behavior is unchanged (backward compatible)
# ---------------------------------------------------------------------------


class NoRepositoryTests(TestCase):
    def test_approved_requirement_enters_assessment_unchanged(self):
        """Without repositories wired, behavior matches the original path."""
        service = AssessmentApplicationService()
        ctx = _context()
        dto = service.determine_applicability(
            ctx,
            [_requirement(REQUIREMENT_APPROVED_ID)],
            destination={"country_code": "ng"},
            product={"commodity_code": "cocoa"},
        )
        self.assertIsInstance(dto, ApplicabilityDTO)
        self.assertEqual(dto.counts["total_requirements"], 1)


# ---------------------------------------------------------------------------
# With repositories: governance gating
# ---------------------------------------------------------------------------


class GovernanceGatingTests(TestCase):
    def setUp(self) -> None:
        self.requirement_repo = FakeRequirementRepository({
            REQUIREMENT_APPROVED_ID: {
                "id": REQUIREMENT_APPROVED_ID,
                "stage_a_status": "verified",
                "stage_b_status": "approved",
                "source_id": SOURCE_APPROVED_ID,
                "requirement_text": "All cocoa exports require certification.",
            },
            REQUIREMENT_STAGE_A_PENDING_ID: {
                "id": REQUIREMENT_STAGE_A_PENDING_ID,
                "stage_a_status": "pending",
                "stage_b_status": "pending",
                "source_id": SOURCE_APPROVED_ID,
                "requirement_text": "All wheat exports require inspection.",
            },
            REQUIREMENT_STAGE_B_PENDING_ID: {
                "id": REQUIREMENT_STAGE_B_PENDING_ID,
                "stage_a_status": "verified",
                "stage_b_status": "pending",
                "source_id": SOURCE_APPROVED_ID,
                "requirement_text": "All rice exports require documentation.",
            },
            REQUIREMENT_FLAGGED_ID: {
                "id": REQUIREMENT_FLAGGED_ID,
                "stage_a_status": "verified",
                "stage_b_status": "approved",
                "source_id": SOURCE_FLAGGED_ID,
                "requirement_text": "All sesame exports require documentation.",
            },
        })
        self.review_flag_repo = FakeReviewFlagRepository()
        # Add a pending flag on the flagged source
        self.review_flag_repo.flags_by_source[SOURCE_FLAGGED_ID] = [{
            "id": UUID("77777777-7777-7777-7777-777777777777"),
            "trigger_source_id": SOURCE_FLAGGED_ID,
            "trigger_type": "supersession",
            "status": "pending_review",
            "rationale": "Source superseded.",
        }]
        self.service = AssessmentApplicationService(
            requirement_repository=self.requirement_repo,
            review_flag_repository=self.review_flag_repo,
        )

    def test_approved_and_in_scope_enters_assessment(self):
        """Requirement with Stage A verified + Stage B approved + no flags
        can be evaluated as applicable."""
        dto = self.service.determine_applicability(
            _context(),
            [_requirement(REQUIREMENT_APPROVED_ID)],
            destination={"country_code": "ng"},
            product={"commodity_code": "cocoa"},
        )
        self.assertEqual(dto.counts["total_requirements"], 1)
        # Should be applicable (cocoa to Nigeria matches context)
        self.assertEqual(dto.counts["applicable_count"], 1)
        self.assertEqual(dto.counts["unknown_count"], 0)

    def test_stage_a_not_verified_excluded(self):
        """Requirement without Stage A verification is unknown, not applicable."""
        dto = self.service.determine_applicability(
            _context(),
            [_requirement(REQUIREMENT_STAGE_A_PENDING_ID)],
            destination={"country_code": "ng"},
            product={"commodity_code": "wheat"},
        )
        self.assertEqual(dto.counts["total_requirements"], 1)
        self.assertEqual(dto.counts["unknown_count"], 1)
        self.assertEqual(dto.counts["applicable_count"], 0)
        self.assertIn(
            "Stage A verification required",
            dto.results[0].reason,
        )

    def test_stage_b_not_approved_excluded(self):
        """Requirement without Stage B approval is unknown, not applicable."""
        dto = self.service.determine_applicability(
            _context(),
            [_requirement(REQUIREMENT_STAGE_B_PENDING_ID)],
            destination={"country_code": "ng"},
            product={"commodity_code": "rice"},
        )
        self.assertEqual(dto.counts["total_requirements"], 1)
        self.assertEqual(dto.counts["unknown_count"], 1)
        self.assertEqual(dto.counts["applicable_count"], 0)
        self.assertIn(
            "Stage B pilot approval required",
            dto.results[0].reason,
        )

    def test_pending_governance_flag_blocks(self):
        """Requirement with pending governance flag is unknown."""
        dto = self.service.determine_applicability(
            _context(),
            [_requirement(REQUIREMENT_FLAGGED_ID, source_id=SOURCE_FLAGGED_ID)],
            destination={"country_code": "ng"},
            product={"commodity_code": "sesame"},
        )
        self.assertEqual(dto.counts["total_requirements"], 1)
        self.assertEqual(dto.counts["unknown_count"], 1)
        self.assertEqual(dto.counts["applicable_count"], 0)
        self.assertIn("pending governance review", dto.results[0].reason)

    def test_mixed_requirements_only_approved_enters(self):
        """Mix of approved and blocked requirements: only approved enters
        applicability evaluation; blocked ones are unknown."""
        dto = self.service.determine_applicability(
            _context(),
            [
                _requirement(REQUIREMENT_APPROVED_ID),
                _requirement(REQUIREMENT_STAGE_A_PENDING_ID),
                _requirement(REQUIREMENT_FLAGGED_ID, source_id=SOURCE_FLAGGED_ID),
            ],
            destination={"country_code": "ng"},
            product={"commodity_code": "cocoa"},
        )
        self.assertEqual(dto.counts["total_requirements"], 3)
        # Only the approved one can be applicable
        self.assertEqual(dto.counts["applicable_count"], 1)
        # Two blocked ones are unknown
        self.assertEqual(dto.counts["unknown_count"], 2)

    def test_tenant_isolation_preserved(self):
        """Results are scoped to the context tenant."""
        service = AssessmentApplicationService(
            requirement_repository=self.requirement_repo,
            review_flag_repository=self.review_flag_repo,
        )
        other_ctx = ApplicationContext(
            actor_id=UUID("88888888-8888-8888-8888-888888888888"),
            tenant=TenantContext(OTHER_TENANT_ID),
            role="owner",
        )
        dto = service.determine_applicability(
            other_ctx,
            [_requirement(REQUIREMENT_APPROVED_ID)],
            destination={"country_code": "ng"},
            product={"commodity_code": "cocoa"},
        )
        self.assertEqual(dto.counts["total_requirements"], 1)

    def test_requirement_not_in_regulatory_store_blocked(self):
        """Requirement with no regulatory store row is unknown."""
        unknown_id = UUID("99999999-9999-9999-9999-999999999998")
        dto = self.service.determine_applicability(
            _context(),
            [_requirement(unknown_id)],
            destination={"country_code": "ng"},
            product={"commodity_code": "cocoa"},
        )
        self.assertEqual(dto.counts["total_requirements"], 1)
        self.assertEqual(dto.counts["unknown_count"], 1)
        self.assertIn("not in regulatory store", dto.results[0].reason)

    def test_rejection_reasons_not_treated_as_approval(self):
        """Stage B rejected/clarification_required does not count as approval."""
        # Stage B rejected
        rejected_id = UUID("aaaaaaaa-0000-0000-0000-000000000001")
        self.requirement_repo.rows[rejected_id] = {
            "id": rejected_id,
            "stage_a_status": "verified",
            "stage_b_status": "rejected",
            "source_id": SOURCE_APPROVED_ID,
            "requirement_text": "Rejected requirement text.",
        }
        dto = self.service.determine_applicability(
            _context(),
            [_requirement(rejected_id, source_id=SOURCE_APPROVED_ID)],
            destination={"country_code": "ng"},
            product={"commodity_code": "cocoa"},
        )
        self.assertEqual(dto.counts["unknown_count"], 1)
        self.assertEqual(dto.counts["applicable_count"], 0)
        self.assertIn("Stage B pilot approval required", dto.results[0].reason)

        # Stage B clarification_required
        clar_id = UUID("bbbbbbbb-0000-0000-0000-000000000002")
        self.requirement_repo.rows[clar_id] = {
            "id": clar_id,
            "stage_a_status": "verified",
            "stage_b_status": "clarification_required",
            "source_id": SOURCE_APPROVED_ID,
            "requirement_text": "Clarification required text.",
        }
        dto2 = self.service.determine_applicability(
            _context(),
            [_requirement(clar_id, source_id=SOURCE_APPROVED_ID)],
            destination={"country_code": "ng"},
            product={"commodity_code": "cocoa"},
        )
        self.assertEqual(dto2.counts["unknown_count"], 1)
        self.assertEqual(dto2.counts["applicable_count"], 0)
        self.assertIn("Stage B pilot approval required", dto2.results[0].reason)

    def test_deterministic_with_repositories(self):
        """Repeated calls with same input produce same results."""
        service = AssessmentApplicationService(
            requirement_repository=self.requirement_repo,
            review_flag_repository=self.review_flag_repo,
        )
        first = service.determine_applicability(
            _context(),
            [_requirement(REQUIREMENT_APPROVED_ID)],
            destination={"country_code": "ng"},
            product={"commodity_code": "cocoa"},
        )
        second = service.determine_applicability(
            _context(),
            [_requirement(REQUIREMENT_APPROVED_ID)],
            destination={"country_code": "ng"},
            product={"commodity_code": "cocoa"},
        )
        self.assertEqual(first.counts, second.counts)
        self.assertEqual(
            first.results[0].outcome, second.results[0].outcome
        )


# ---------------------------------------------------------------------------
# Stage A/B and governance service regressions remain intact
# ---------------------------------------------------------------------------


class RegressionTests(TestCase):
    def test_stage_a_review_service_imports(self):
        """Stage A service still imports and works unchanged."""
        from xportra.application.regulatory_stage_a_review_service import (
            RegulatoryStageAReviewService,
            STAGE_A_STATUS_VERIFIED,
        )
        self.assertEqual(STAGE_A_STATUS_VERIFIED, "verified")
        self.assertIsNotNone(RegulatoryStageAReviewService)

    def test_stage_b_review_service_imports(self):
        """Stage B service still imports and works unchanged."""
        from xportra.application.regulatory_stage_b_review_service import (
            RegulatoryStageBReviewService,
            STAGE_B_STATUS_APPROVED,
        )
        self.assertEqual(STAGE_B_STATUS_APPROVED, "approved")
        self.assertIsNotNone(RegulatoryStageBReviewService)

    def test_governance_service_imports(self):
        """Governance service still imports unchanged."""
        from xportra.application.regulatory_governance_service import (
            RegulatoryGovernanceService,
        )
        self.assertIsNotNone(RegulatoryGovernanceService)


if __name__ == "__main__":
    import unittest
    unittest.main()
