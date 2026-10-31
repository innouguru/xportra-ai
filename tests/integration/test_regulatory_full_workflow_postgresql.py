"""PostgreSQL end-to-end integration test for the regulatory workflow (M8).

Exercises the full pipeline against the isolated local ``xportra_test``
database with all migrations applied:

    source registration -> text artifact entry -> ingestion job ->
    candidate extraction -> Stage A verification with wording
    correction -> Stage B applicability approval -> publication
    eligibility -> publication, plus the manual recovery path and the
    M7 source-withdrawal governance flow.

Requires ``DATABASE_URL`` (local only); skipped otherwise. Storage is
exercised through a deterministic in-memory adapter — no Supabase
Storage or production service is contacted. Production database
configuration must never be used by this suite.
"""

from __future__ import annotations

import os
import unittest
from uuid import UUID

from xportra.application.errors import ApplicationValidationError
from xportra.application.global_staff import (
    GRANT_MANAGE,
    STAGE_A_VERIFY,
    STAGE_B_APPROVE,
)
from xportra.application.regulatory_candidate_extraction_service import (
    RegulatoryCandidateExtractionService,
)
from xportra.application.regulatory_publication_eligibility_service import (
    RegulatoryPublicationEligibilityService,
)
from xportra.application.regulatory_source_intake_service import (
    RegulatorySourceIntakeService,
)
from xportra.application.regulatory_stage_a_review_service import (
    RegulatoryStageAReviewService,
)
from xportra.application.regulatory_stage_b_review_service import (
    RegulatoryStageBReviewService,
)
from xportra.persistence.database import Database, DatabaseSettings

AUTHORITY_ID = UUID("ccccccb2-0000-0000-0000-000000000003")
ACTOR_A_SUBJECT = UUID("aaaaaab2-0000-0000-0000-000000000001")
ACTOR_B_SUBJECT = UUID("bbbbbbb2-0000-0000-0000-000000000002")
TENANT_ID = UUID("99999992-0000-0000-0000-000000000099")


class FakeStorage:
    """Deterministic in-memory storage — no Supabase contact."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload_artifact(
        self, key: str, content: bytes, *, content_type: str,
        actor_user_id: UUID, audit_ref: str | None = None,
    ) -> None:
        self.objects[key] = content

    def get_artifact(self, key: str, actor_user_id: UUID):
        return self.objects.get(key)


class FakeStorageService:
    def __init__(self, storage: FakeStorage) -> None:
        self._storage = storage

    def upload_artifact(
        self, key: str, content: bytes, *, content_type: str,
        actor_user_id: UUID, audit_ref: str | None = None,
    ) -> None:
        self._storage.upload_artifact(
            key, content, content_type=content_type,
            actor_user_id=actor_user_id,
        )

    def get_artifact(self, key: str, actor_user_id: UUID):
        return self._storage.get_artifact(key, actor_user_id)


class RegulatoryFullWorkflowIntegrationTests(unittest.TestCase):
    database: Database | None = None
    actor_a: UUID | None = None
    actor_b: UUID | None = None

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DATABASE_URL", "").strip():
            raise unittest.SkipTest("DATABASE_URL is not configured")
        cls.database = Database(DatabaseSettings.from_environment())
        with cls.database.connection() as connection:
            with connection.cursor() as cursor:
                row = cursor.execute(
                    "SELECT current_database(), current_user"
                ).fetchone()
                if row["current_database"] != "xportra_test":
                    raise unittest.SkipTest(
                        "refusing to run E2E outside xportra_test "
                        f"(got {row['current_database']})"
                    )
        cls._fixture_users_and_grants()

    @classmethod
    def tearDownClass(cls):
        if cls.database is None:
            return
        cls._cleanup()

    @classmethod
    def _fixture_users_and_grants(cls):
        from xportra.persistence.repositories import UserRepository

        user_repo = UserRepository(cls.database)
        row_a = user_repo.get_by_supabase_uid(ACTOR_A_SUBJECT)
        if row_a is None:
            row_a = user_repo.create(
                "E2E Stage A Actor", "e2e-actor-a@example.invalid",
                "active", ACTOR_A_SUBJECT,
            )
        row_b = user_repo.get_by_supabase_uid(ACTOR_B_SUBJECT)
        if row_b is None:
            row_b = user_repo.create(
                "E2E Stage B Actor", "e2e-actor-b@example.invalid",
                "active", ACTOR_B_SUBJECT,
            )
        cls.actor_a = row_a["id"]
        cls.actor_b = row_b["id"]
        with cls.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO xportra.tenants (id, legal_name, slug, status)
                    VALUES (%s, %s, %s, 'active')
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (TENANT_ID, "E2E Tenant", "e2e-tenant"),
                )
                cursor.execute(
                    """
                    INSERT INTO xportra.user_tenant_memberships
                        (id, tenant_id, user_id, role, status,
                         added_at, created_at, updated_at)
                    VALUES (gen_random_uuid(), %s, %s, 'owner', 'active',
                            now(), now(), now())
                    ON CONFLICT (tenant_id, user_id) DO NOTHING
                    """,
                    (TENANT_ID, cls.actor_a),
                )
                for user_id in (cls.actor_a, cls.actor_b):
                    for permission in (GRANT_MANAGE, STAGE_A_VERIFY,
                                       STAGE_B_APPROVE):
                        cursor.execute(
                            """
                            INSERT INTO xportra.global_staff_grants
                                (user_id, permission, status, granted_by,
                                 reason, created_at, updated_at)
                            VALUES (%s, %s, 'active', %s,
                                    'e2e integration fixture', now(), now())
                            ON CONFLICT (user_id, permission) DO UPDATE
                                SET status = 'active', updated_at = now()
                            """,
                            (user_id, permission, user_id),
                        )
                cursor.execute(
                    """
                    INSERT INTO xportra.authorities
                        (id, name, jurisdiction, authority_type, status)
                    VALUES (%s, %s, %s, 'government', 'active')
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (AUTHORITY_ID, "E2E Test Authority", "EU"),
                )

    @classmethod
    def _cleanup(cls):
        with cls.database.transaction() as connection:
            with connection.cursor() as cursor:
                # Local fixture cleanup only: bypass append-only triggers
                # for this transaction (requires a superuser session —
                # the isolated local test database, never production).
                cursor.execute("SET session_replication_role = 'replica'")
                cursor.execute(
                    """
                    DELETE FROM xportra.regulatory_requirement_wording_corrections
                    WHERE requirement_id IN (
                        SELECT id FROM xportra.regulatory_requirements
                        WHERE source_id IN (SELECT id FROM xportra.regulatory_sources
                                            WHERE authority_id = %s))
                    """,
                    (AUTHORITY_ID,),
                )
                for table in (
                    "regulatory_stage_a_reviews",
                    "regulatory_stage_b_reviews",
                    "regulatory_review_flags",
                ):
                    cursor.execute(
                        f"""
                        DELETE FROM xportra.{table}
                        WHERE requirement_id IN (
                            SELECT id FROM xportra.regulatory_requirements
                            WHERE source_id IN (SELECT id FROM xportra.regulatory_sources
                                                WHERE authority_id = %s))
                        """,
                        (AUTHORITY_ID,),
                    )
                cursor.execute(
                    """
                    DELETE FROM xportra.regulatory_requirements
                    WHERE source_id IN (SELECT id FROM xportra.regulatory_sources
                                        WHERE authority_id = %s)
                    """,
                    (AUTHORITY_ID,),
                )
                cursor.execute(
                    """
                    DELETE FROM xportra.regulatory_document_metadata
                    WHERE normalized_document_id IN (
                        SELECT id FROM xportra.regulatory_document_normalizations
                        WHERE source_id IN (SELECT id FROM xportra.regulatory_sources
                                            WHERE authority_id = %s))
                    """,
                    (AUTHORITY_ID,),
                )
                cursor.execute(
                    """
                    DELETE FROM xportra.regulatory_document_normalizations
                    WHERE source_id IN (SELECT id FROM xportra.regulatory_sources
                                        WHERE authority_id = %s)
                    """,
                    (AUTHORITY_ID,),
                )
                cursor.execute(
                    """
                    DELETE FROM xportra.regulatory_ingestion_jobs
                    WHERE source_id IN (SELECT id FROM xportra.regulatory_sources
                                        WHERE authority_id = %s)
                    """,
                    (AUTHORITY_ID,),
                )
                cursor.execute(
                    """
                    DELETE FROM xportra.regulatory_source_artifacts
                    WHERE source_id IN (SELECT id FROM xportra.regulatory_sources
                                        WHERE authority_id = %s)
                    """,
                    (AUTHORITY_ID,),
                )
                cursor.execute(
                    """
                    DELETE FROM xportra.regulatory_sources
                    WHERE authority_id = %s
                    """,
                    (AUTHORITY_ID,),
                )
                cursor.execute(
                    "DELETE FROM xportra.authorities WHERE id = %s",
                    (AUTHORITY_ID,),
                )
                for user_id in (cls.actor_a, cls.actor_b):
                    cursor.execute(
                        "DELETE FROM xportra.global_staff_grants "
                        "WHERE user_id = %s",
                        (user_id,),
                    )
                cursor.execute(
                    "DELETE FROM xportra.user_tenant_memberships "
                    "WHERE user_id = %s",
                    (cls.actor_a,),
                )
                cursor.execute(
                    "DELETE FROM xportra.tenants WHERE id = %s",
                    (TENANT_ID,),
                )
                cursor.execute(
                    "DELETE FROM xportra.users WHERE id IN (%s, %s)",
                    (cls.actor_a, cls.actor_b),
                )

    def setUp(self):
        if self.database is None:
            self.skipTest("DATABASE_URL is not configured")
        self.storage = FakeStorage()
        storage_service = FakeStorageService(self.storage)
        self.intake = RegulatorySourceIntakeService(
            self.database, storage_service=storage_service,
        )
        self.extraction = RegulatoryCandidateExtractionService(
            self.database, storage_service=storage_service,
        )
        self.stage_a = RegulatoryStageAReviewService(self.database)
        self.stage_b = RegulatoryStageBReviewService(self.database)
        self.publication = RegulatoryPublicationEligibilityService(self.database)

    def _register_active_source(self, title: str):
        return self.intake.register_source(
            actor_user_id=self.actor_a,
            authority_id=AUTHORITY_ID,
            jurisdiction="EU",
            title=title,
            version="1.0",
            status="active",
            effective_date="2024-01-01",
        )

    def test_full_workflow_extracted_candidate_to_publication(self):
        """M1 -> M6 happy path: extracted candidate reaches 'published'."""
        source = self._register_active_source("E2E Sesame Regulation")
        artifact_result = self.intake.enter_text_artifact(
            actor_user_id=self.actor_a,
            source_id=source["id"],
            content_text=(
                "# E2E Sesame Regulation\n\n"
                "Shall be labeled with origin.\n"
                "Shall not exceed 50 kg.\n"
            ),
            content_type="text/plain",
        )
        self.assertFalse(artifact_result["duplicate"])
        artifact = artifact_result["artifact"]
        job = artifact_result["job"]
        self.assertEqual(job["status"], "pending")

        extraction = self.extraction.extract_candidates(
            actor_user_id=self.actor_a,
            source_id=source["id"],
            artifact_id=artifact["id"],
            job_id=job["id"],
        )
        self.assertEqual(extraction["outcome"], "succeeded")
        self.assertGreaterEqual(extraction["candidate_count"], 1)
        self.assertEqual(extraction["job"]["status"], "completed")
        candidate = extraction["candidates"][0]

        # Stage A with wording correction (M5).
        stage_a = self.stage_a.verify_stage_a(
            actor_user_id=self.actor_a,
            candidate_id=candidate["id"],
            stage_a_status="verified",
            rationale="Wording verified against source text with correction.",
            corrected_requirement_text=(
                "Packages shall be labeled with the country of origin."
            ),
        )
        self.assertEqual(stage_a["stage_a_status"], "verified")
        self.assertIsNotNone(stage_a["wording_correction_id"])

        # Append-only wording history retained.
        corrections = self.stage_a.list_wording_corrections(candidate["id"])
        self.assertEqual(len(corrections), 1)
        self.assertEqual(
            corrections[0]["original_text"], candidate["requirement_text"]
        )
        self.assertEqual(
            corrections[0]["corrected_text"],
            "Packages shall be labeled with the country of origin.",
        )

        row = self.stage_a.get_candidate_stage_a(candidate["id"])
        self.assertEqual(
            row["requirement_text"],
            "Packages shall be labeled with the country of origin.",
        )

        # Stage B by a different reviewer (same-person rule enforced).
        with self.assertRaises(ApplicationValidationError):
            self.stage_b.approve_stage_b(
                actor_user_id=self.actor_a,
                candidate_id=candidate["id"],
                stage_b_status="approved",
                rationale="Same-person attempt.",
                pilot_scope="pilot",
            )
        stage_b = self.stage_b.approve_stage_b(
            actor_user_id=self.actor_b,
            candidate_id=candidate["id"],
            stage_b_status="approved",
            rationale="Applies to the pilot scope.",
            pilot_scope="exporter_readiness",
        )
        self.assertEqual(stage_b["stage_b_status"], "approved")

        eligible, reasons = self.publication.check_eligibility(candidate["id"])
        self.assertTrue(eligible, reasons)

        published = self.publication.publish_requirement(
            candidate["id"], self.actor_a,
        )
        self.assertTrue(published["eligible"], published["reasons"])
        self.assertIsNotNone(published["published_at"])
        final_row = self.extraction.get_candidate(candidate["id"])
        self.assertEqual(final_row["status"], "published")

        # Published requirement is no longer eligible for republication.
        ineligible, _ = self.publication.check_eligibility(candidate["id"])
        self.assertFalse(ineligible)

    def test_full_workflow_manual_candidate_to_publication(self):
        """M3/M6 recovery path: manual candidate reaches 'published'."""
        source = self._register_active_source("E2E Manual Regulation")
        text_result = self.intake.enter_text_artifact(
            actor_user_id=self.actor_a,
            source_id=source["id"],
            content_text="Ambiguous reference text for recovery.",
            content_type="text/plain",
        )
        artifact = text_result["artifact"]
        candidate = self.extraction.enter_manual_candidate(
            actor_user_id=self.actor_a,
            source_id=source["id"],
            artifact_id=artifact["id"],
            requirement_text="Exporters shall retain records for five years.",
            requirement_type="documentation",
        )
        self.assertTrue(candidate["manual_entry"])
        self.assertEqual(candidate["extraction_outcome"], "manual")
        self.assertEqual(candidate["reviewer_user_id"], self.actor_a)

        self.stage_a.verify_stage_a(
            actor_user_id=self.actor_a,
            candidate_id=candidate["id"],
            stage_a_status="verified",
            rationale="Manual entry matches source context.",
        )
        self.stage_b.approve_stage_b(
            actor_user_id=self.actor_b,
            candidate_id=candidate["id"],
            stage_b_status="approved",
            rationale="Applies to pilot documentation scope.",
            pilot_scope="exporter_readiness",
        )
        eligible, reasons = self.publication.check_eligibility(candidate["id"])
        self.assertTrue(eligible, reasons)
        published = self.publication.publish_requirement(
            candidate["id"], self.actor_a,
        )
        self.assertTrue(published["eligible"], published["reasons"])

    def test_withdrawal_blocks_verification_and_publication(self):
        """M7: withdrawn source raises flags and closes every gate."""
        source = self._register_active_source("E2E Withdrawn Regulation")
        text_result = self.intake.enter_text_artifact(
            actor_user_id=self.actor_a,
            source_id=source["id"],
            content_text="Shall be withdrawn with the source.",
            content_type="text/plain",
        )
        extraction = self.extraction.extract_candidates(
            actor_user_id=self.actor_a,
            source_id=source["id"],
            artifact_id=text_result["artifact"]["id"],
            job_id=text_result["job"]["id"],
        )
        self.assertEqual(extraction["outcome"], "succeeded")
        candidate = extraction["candidates"][0]

        withdrawal = self.intake.withdraw_source(
            actor_user_id=self.actor_a,
            source_id=source["id"],
            rationale="Regulation retracted by the authority.",
        )
        self.assertEqual(withdrawal["status"], "withdrawn")
        self.assertGreaterEqual(withdrawal["governance_flags_raised"], 1)

        # Stage A re-verification is blocked by pending withdrawal flags.
        with self.assertRaises(ApplicationValidationError) as ctx:
            self.stage_a.verify_stage_a(
                actor_user_id=self.actor_a,
                candidate_id=candidate["id"],
                stage_a_status="verified",
                rationale="Attempt to verify on a withdrawn source.",
            )
        self.assertIn("pending governance flags", str(ctx.exception))

        # Stage B approval is likewise blocked.
        with self.assertRaises(ApplicationValidationError) as ctx:
            self.stage_b.approve_stage_b(
                actor_user_id=self.actor_b,
                candidate_id=candidate["id"],
                stage_b_status="approved",
                rationale="Attempt to approve on a withdrawn source.",
                pilot_scope="pilot",
            )
        self.assertIn("pending governance flags", str(ctx.exception))

        # Publication eligibility fails closed.
        eligible, reasons = self.publication.check_eligibility(candidate["id"])
        self.assertFalse(eligible)
        self.assertTrue(
            any("withdrawn" in reason for reason in reasons),
            reasons,
        )

        # Withdrawing an already withdrawn source is refused.
        with self.assertRaises(ApplicationValidationError):
            self.intake.withdraw_source(
                actor_user_id=self.actor_a,
                source_id=source["id"],
                rationale="Duplicate withdrawal attempt.",
            )


if __name__ == "__main__":
    unittest.main()
