"""PostgreSQL integration tests for regulatory governance integration
in compliance assessment.

Tests that the assessment path correctly gates requirements based on
Stage A verification, Stage B pilot approval, and pending governance
flags against the isolated local ``xportra_test`` database.
"""
from __future__ import annotations

import os
import unittest
from uuid import UUID

from xportra.application.assessments import AssessmentApplicationService
from xportra.application.context import ApplicationContext
from xportra.persistence.database import Database, DatabaseSettings
from xportra.persistence.repositories import (
    RegulatoryRequirementRepository,
    RegulatoryReviewFlagRepository,
)
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ACTOR_ID = UUID("aaaaaa07-0000-0000-0000-000000000001")
SOURCE_ID = UUID("dddddd04-0000-0000-0000-000000000004")

# Existing requirements in xportra_test:
#   2222...200: stage_a='pending', stage_b='pending'  -> should be blocked
#   1111...100: stage_a='verified', stage_b='rejected' -> should be blocked
EXISTING_STAGE_A_PENDING_ID = UUID("22222222-0000-0000-0000-000000000200")
EXISTING_STAGE_B_REJECTED_ID = UUID("11111111-0000-0000-0000-000000000100")

# New test requirements (unique IDs)
APPROVED_REQ_ID = UUID("cccccccc-0000-0000-0000-000000000100")
STAGE_A_ONLY_REQ_ID = UUID("dddddddd-0000-0000-0000-000000000200")

# Flagged source/requirement
FLAGGED_SOURCE_ID = UUID("eeeeeeee-0000-0000-0000-000000000300")
FLAGGED_REQ_ID = UUID("ffffffff-0000-0000-0000-000000000400")
FLAG_ID = UUID("77777777-7777-7777-7777-777777777777")


class AssessmentRegulatoryIntegrationTests(unittest.TestCase):
    database: Database | None = None

    @classmethod
    def setUpClass(cls):
        cls.database = Database(
            DatabaseSettings(dsn="postgresql://postgres:postgres@localhost:5432/xportra_test"))
        with cls.database.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user")
                row = cur.fetchone()
                assert row["current_database"] == "xportra_test", (
                    f"Expected xportra_test, got {row['current_database']}"
                )
        cls._seed_test_data()

    @classmethod
    def _seed_test_data(cls):
        """Insert test-owned requirement rows and governance flags."""
        with cls.database.transaction() as conn:
            with conn.cursor() as cur:
                # The flagged source references this authority; the source
                # insert below fails on a freshly migrated database unless
                # the authority row exists first. A unique (name,
                # jurisdiction) avoids colliding with the shared
                # "Test Authority" rows other fixtures seed.
                cur.execute(
                    """
                    INSERT INTO xportra.authorities
                        (id, name, jurisdiction, authority_type, status)
                    VALUES (%s, 'Flagged Regulation Authority', 'EU',
                            'government', 'active')
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (UUID("cccccc05-0000-0000-0000-000000000005"),),
                )
                # Flagged source
                cur.execute(
                    """
                    INSERT INTO xportra.regulatory_sources
                        (id, authority_id, jurisdiction, title, version, status,
                         effective_date, publication_date, source_url,
                         retrieval_timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        FLAGGED_SOURCE_ID, UUID("cccccc05-0000-0000-0000-000000000005"),
                        "EU", "Flagged Regulation", "1.0", "active",
                        "2024-01-01", "2024-01-01", "https://example.com/flagged",
                    ),
                )
                # Approved requirement: stage_a=verified, stage_b=approved
                cur.execute(
                    """
                    INSERT INTO xportra.regulatory_requirements
                        (id, normalized_document_id, requirement_text,
                         requirement_type, source_location, position, actor,
                         condition_metadata, status, ingestion_job_id,
                         extraction_outcome, parser_version, manual_entry,
                         reviewer_user_id, reviewed_at, source_id,
                         stage_a_status, stage_a_reviewer_user_id,
                         stage_a_reviewed_at, stage_a_rationale,
                         stage_b_status, stage_b_reviewer_user_id,
                         stage_b_reviewed_at, stage_b_rationale,
                         stage_b_pilot_scope, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'extracted',
                            NULL, 'succeeded', 'v1', FALSE, %s, now(),
                            %s, 'verified', %s, now(), 'Verified.',
                            'approved', %s, now(), 'Approved.',
                            'sesame-eu-pilot-v1', now(), now())
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        APPROVED_REQ_ID, UUID("44444444-0000-0000-0000-000000000404"),
                        "Shall be labeled with origin.", "labeling",
                        '{"section_order": 0, "heading": null}', 100, "exporter",
                        None, ACTOR_ID, SOURCE_ID, ACTOR_ID, ACTOR_ID,
                    ),
                )
                # Stage A verified only, no Stage B
                cur.execute(
                    """
                    INSERT INTO xportra.regulatory_requirements
                        (id, normalized_document_id, requirement_text,
                         requirement_type, source_location, position, actor,
                         condition_metadata, status, ingestion_job_id,
                         extraction_outcome, parser_version, manual_entry,
                         reviewer_user_id, reviewed_at, source_id,
                         stage_a_status, stage_a_reviewer_user_id,
                         stage_a_reviewed_at, stage_a_rationale,
                         stage_b_status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'extracted',
                            NULL, 'succeeded', 'v1', FALSE, %s, now(),
                            %s, 'verified', %s, now(), 'Verified.',
                            'pending', now(), now())
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        STAGE_A_ONLY_REQ_ID, UUID("44444444-0000-0000-0000-000000000404"),
                        "All wheat exports require inspection.", "labeling",
                        '{"section_order": 0, "heading": null}', 101, "exporter",
                        None, ACTOR_ID, SOURCE_ID, ACTOR_ID,
                    ),
                )
                # Flagged requirement row (stage_a=verified, stage_b=approved but flagged)
                cur.execute(
                    """
                    INSERT INTO xportra.regulatory_requirements
                        (id, normalized_document_id, requirement_text,
                         requirement_type, source_location, position, actor,
                         condition_metadata, status, ingestion_job_id,
                         extraction_outcome, parser_version, manual_entry,
                         reviewer_user_id, reviewed_at, source_id,
                         stage_a_status, stage_a_reviewer_user_id,
                         stage_a_reviewed_at, stage_a_rationale,
                         stage_b_status, stage_b_reviewer_user_id,
                         stage_b_reviewed_at, stage_b_rationale,
                         stage_b_pilot_scope, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'extracted',
                            NULL, 'succeeded', 'v1', FALSE, %s, now(),
                            %s, 'verified', %s, now(), 'Verified.',
                            'approved', %s, now(), 'Approved.',
                            'sesame-eu-pilot-v1', now(), now())
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        FLAGGED_REQ_ID, UUID("44444444-0000-0000-0000-000000000404"),
                        "All sesame exports require documentation.",
                        "labeling", '{"section_order": 0, "heading": null}',
                        102, "exporter", None, ACTOR_ID, FLAGGED_SOURCE_ID,
                        ACTOR_ID, ACTOR_ID,
                    ),
                )
                # Governance flag on a source (inserted after requirement row exists)
                cur.execute(
                    """
                    INSERT INTO xportra.regulatory_review_flags
                        (id, requirement_id, trigger_source_id, trigger_type,
                         status, actor_user_id, rationale, created_at,
                         updated_at)
                    VALUES (%s, %s, %s, 'supersession', 'pending_review',
                            %s, 'Source superseded.', now(), now())
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        FLAG_ID, FLAGGED_REQ_ID, FLAGGED_SOURCE_ID, ACTOR_ID,
                    ),
                )

    @classmethod
    def tearDownClass(cls):
        pass  # No cleanup: append-only tables cannot be truncated.

    def setUp(self):
        self.requirement_repo = RegulatoryRequirementRepository(self.database)
        self.review_flag_repo = RegulatoryReviewFlagRepository(self.database)
        self.service = AssessmentApplicationService(
            requirement_repository=self.requirement_repo,
            review_flag_repository=self.review_flag_repo,
        )

    def _context(self) -> ApplicationContext:
        return ApplicationContext(
            actor_id=ACTOR_ID,
            tenant=TenantContext(TENANT_ID),
            role="owner",
        )

    def test_approved_requirement_enters_assessment(self):
        """Stage A verified + Stage B approved + no flags -> applicable."""
        dto = self.service.determine_applicability(
            self._context(),
            [{"id": APPROVED_REQ_ID,
              "requirement_text": "Cocoa to Nigeria", "actor": "exporter"}],
            destination={"country_code": "ng"},
            product={"commodity_code": "cocoa"},
        )
        self.assertEqual(dto.counts["total_requirements"], 1)
        self.assertEqual(dto.counts["applicable_count"], 1)
        self.assertEqual(dto.counts["unknown_count"], 0)

    def test_stage_a_pending_blocked(self):
        """Existing requirement with stage_a='pending' -> unknown."""
        dto = self.service.determine_applicability(
            self._context(),
            [{"id": EXISTING_STAGE_A_PENDING_ID,
              "requirement_text": "Wheat to Ghana", "actor": "exporter"}],
            destination={"country_code": "gh"},
            product={"commodity_code": "wheat"},
        )
        self.assertEqual(dto.counts["total_requirements"], 1)
        self.assertEqual(dto.counts["unknown_count"], 1)
        self.assertEqual(dto.counts["applicable_count"], 0)
        self.assertIn("Stage A verification required", dto.results[0].reason)

    def test_stage_b_rejected_blocked(self):
        """Existing requirement with stage_b='rejected' -> unknown."""
        dto = self.service.determine_applicability(
            self._context(),
            [{"id": EXISTING_STAGE_B_REJECTED_ID,
              "requirement_text": "Rice to Nigeria", "actor": "exporter"}],
            destination={"country_code": "ng"},
            product={"commodity_code": "rice"},
        )
        self.assertEqual(dto.counts["total_requirements"], 1)
        self.assertEqual(dto.counts["unknown_count"], 1)
        self.assertEqual(dto.counts["applicable_count"], 0)
        self.assertIn("Stage B pilot approval required", dto.results[0].reason)

    def test_pending_governance_flag_blocks(self):
        """Requirement with pending governance flag -> unknown."""
        dto = self.service.determine_applicability(
            self._context(),
            [{"id": FLAGGED_REQ_ID, "requirement_text": "Sesame to Nigeria",
              "actor": "exporter"}],
            destination={"country_code": "ng"},
            product={"commodity_code": "sesame"},
        )
        self.assertEqual(dto.counts["total_requirements"], 1)
        self.assertEqual(dto.counts["unknown_count"], 1)
        self.assertEqual(dto.counts["applicable_count"], 0)
        self.assertIn("pending governance review", dto.results[0].reason)

    def test_stage_a_only_blocked(self):
        """Requirement with Stage A verified but no Stage B -> unknown."""
        dto = self.service.determine_applicability(
            self._context(),
            [{"id": STAGE_A_ONLY_REQ_ID, "requirement_text": "Wheat to Ghana",
              "actor": "exporter"}],
            destination={"country_code": "gh"},
            product={"commodity_code": "wheat"},
        )
        self.assertEqual(dto.counts["total_requirements"], 1)
        self.assertEqual(dto.counts["unknown_count"], 1)
        self.assertEqual(dto.counts["applicable_count"], 0)
        self.assertIn("Stage B pilot approval required", dto.results[0].reason)

    def test_mixed_requirements(self):
        """Mix of approved and blocked: only approved can be applicable."""
        dto = self.service.determine_applicability(
            self._context(),
            [
                {"id": APPROVED_REQ_ID, "requirement_text": "Cocoa to Nigeria",
                 "actor": "exporter"},
                {"id": EXISTING_STAGE_A_PENDING_ID,
                 "requirement_text": "Wheat to Ghana", "actor": "exporter"},
                {"id": FLAGGED_REQ_ID, "requirement_text": "Sesame to Nigeria",
                 "actor": "exporter"},
            ],
            destination={"country_code": "ng"},
            product={"commodity_code": "cocoa"},
        )
        self.assertEqual(dto.counts["total_requirements"], 3)
        self.assertEqual(dto.counts["applicable_count"], 1)
        self.assertEqual(dto.counts["unknown_count"], 2)

    def test_tenant_isolation_preserved(self):
        """Different tenant context produces its own results."""
        other_ctx = ApplicationContext(
            actor_id=ACTOR_ID,
            tenant=TenantContext(UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")),
            role="owner",
        )
        dto = self.service.determine_applicability(
            other_ctx,
            [{"id": APPROVED_REQ_ID, "requirement_text": "Cocoa to Nigeria",
              "actor": "exporter"}],
            destination={"country_code": "ng"},
            product={"commodity_code": "cocoa"},
        )
        self.assertEqual(dto.counts["total_requirements"], 1)


if __name__ == "__main__":
    unittest.main()
