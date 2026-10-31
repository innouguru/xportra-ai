"""PostgreSQL integration tests for Stage B regulatory pilot-applicability
approval.

Tests Stage B review against the isolated local ``xportra_test`` database.
Tests use deterministic test storage — no Supabase Storage or production
service is contacted.

Required tables: authorities, regulatory_sources, regulatory_source_artifacts,
regulatory_ingestion_jobs, regulatory_document_normalizations,
regulatory_document_metadata, regulatory_requirements,
regulatory_stage_a_reviews, regulatory_stage_b_reviews, users,
global_staff_grants.
"""

from __future__ import annotations

import base64
import hashlib
import os
import unittest
from uuid import UUID

from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
)
from xportra.api.errors import PermissionDeniedError
from xportra.application.global_staff import (
    STAGE_A_VERIFY,
    STAGE_B_APPROVE,
    GlobalStaffGrantService,
)
from xportra.application.regulatory_candidate_extraction_service import (
    RegulatoryCandidateExtractionService,
)
from xportra.application.regulatory_stage_a_review_service import (
    RegulatoryStageAReviewService,
    STAGE_A_STATUS_VERIFIED,
)
from xportra.application.regulatory_stage_b_review_service import (
    RegulatoryStageBReviewService,
    STAGE_B_STATUS_APPROVED,
    STAGE_B_STATUS_CLARIFICATION_REQUIRED,
    STAGE_B_STATUS_REJECTED,
)
from xportra.persistence.database import Database, DatabaseSettings
from xportra.persistence.repositories import (
    AuthorityRepository,
    RegulatorySourceArtifactRepository,
    RegulatorySourceRepository,
    UserRepository,
    UserTenantMembershipRepository,
)
from xportra.persistence.tenant import TenantContext

ACTOR_SUBJECT = UUID("aaaaaa05-0000-0000-0000-000000000001")
AUTHORITY_ID = UUID("cccccc04-0000-0000-0000-000000000003")
SOURCE_ID = UUID("dddddd04-0000-0000-0000-000000000004")
ARTIFACT_ID = UUID("eeeeee04-0000-0000-0000-000000000005")
STAGE_A_REVIEWER_SUBJECT = UUID("bbbbbb05-0000-0000-0000-000000000002")
STAGE_B_REVIEWER_SUBJECT = UUID("cccccc05-0000-0000-0000-000000000003")
CANDIDATE_ID = UUID("11111111-0000-0000-0000-000000000100")
TENANT = UUID("99999999-0000-0000-0000-000000000099")

REQUIRED_TABLES = (
    "authorities",
    "regulatory_sources",
    "regulatory_source_artifacts",
    "regulatory_ingestion_jobs",
    "regulatory_document_normalizations",
    "regulatory_document_metadata",
    "regulatory_requirements",
    "regulatory_stage_a_reviews",
    "regulatory_stage_b_reviews",
    "users",
    "global_staff_grants",
)


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


class RegulatoryStageBReviewIntegrationTests(unittest.TestCase):
    database: Database | None = None
    storage: FakeStorage | None = None

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DATABASE_URL", "").strip():
            raise unittest.SkipTest("DATABASE_URL is not configured")
        cls.database = Database(DatabaseSettings.from_environment())
        cls.storage = FakeStorage()
        cls._verify_identity()
        cls._verify_tables(REQUIRED_TABLES)

    @classmethod
    def tearDownClass(cls):
        pass  # No cleanup: append-only tables cannot be truncated.

    @classmethod
    def _verify_identity(cls):
        with cls.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database(), current_user")
                row = cursor.fetchone()
                assert row["current_database"] == "xportra_test", (
                    f"Expected xportra_test, got {row['current_database']}"
                )

    @classmethod
    def _verify_tables(cls, tables):
        with cls.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'xportra'
                      AND table_name = ANY(%s)
                    """,
                    (list(tables),),
                )
                found = {row["table_name"] for row in cursor.fetchall()}
        missing = sorted(set(tables) - found)
        if missing:
            raise unittest.SkipTest(
                f"required tables missing: {missing}; "
                "apply migrations 001–003, 004–006, 018, 021–028 before running"
            )

    def setUp(self):
        if self.database is None:
            self.skipTest("DATABASE_URL is not configured")
        self.storage = FakeStorage()
        self.service = RegulatoryStageBReviewService(self.database)
        self._fixture_authority()
        self._fixture_stage_a_reviewer_with_grant()
        self._fixture_stage_b_reviewer_with_grant()
        self._fixture_source()
        self._fixture_artifact()
        self._fixture_candidate()

    def tearDown(self):
        pass  # No cleanup: append-only tables cannot be truncated.

    def _fixture_authority(self):
        repo = AuthorityRepository(self.database)
        if repo.get(AUTHORITY_ID) is not None:
            self.authority_id = AUTHORITY_ID
            return
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO xportra.authorities
                        (id, name, jurisdiction, authority_type, status)
                    VALUES (%s, %s, %s, 'government', 'active')
                    ON CONFLICT (name, jurisdiction) DO UPDATE
                        SET status = 'active'
                    RETURNING id
                    """,
                    (AUTHORITY_ID, "Test Authority", "EU"),
                )
                # Another fixture may already own ("Test Authority", "EU")
                # under a different id; adopt it for the source insert.
                self.authority_id = cursor.fetchone()["id"]

    def _fixture_user_with_grant(
        self, supabase_uid: UUID, role: str = "owner"
    ) -> UUID:
        user_repo = UserRepository(self.database)
        membership_repo = UserTenantMembershipRepository(self.database)
        existing = user_repo.get_by_supabase_uid(supabase_uid)
        if existing is None:
            row = user_repo.create(
                "Stage Reviewer", f"reviewer-{supabase_uid}@example.invalid",
                "active", supabase_uid,
            )
            user_id = row["id"]
        else:
            user_id = existing["id"]
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO xportra.tenants (id, legal_name, slug, status) "
                    "VALUES (%s, %s, %s, 'active') ON CONFLICT (id) DO NOTHING",
                    (TENANT, "Stage Tenant", "stage-tenant"),
                )
                cursor.execute(
                    """
                    INSERT INTO xportra.user_tenant_memberships
                        (id, tenant_id, user_id, role, status, added_at,
                         created_at, updated_at)
                    VALUES (gen_random_uuid(), %s, %s, %s, 'active',
                            now(), now(), now())
                    ON CONFLICT (tenant_id, user_id) DO NOTHING
                    """,
                    (TENANT, user_id, role),
                )
        return user_id

    def _fixture_stage_a_reviewer_with_grant(self):
        self.stage_a_reviewer_id = self._fixture_user_with_grant(
            STAGE_A_REVIEWER_SUBJECT
        )
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO xportra.global_staff_grants
                        (user_id, permission, status, granted_by, reason,
                         created_at, updated_at)
                    VALUES (%s, %s, 'active', %s, %s, now(), now())
                    ON CONFLICT (user_id, permission) DO UPDATE
                        SET status = 'active', updated_at = now()
                    """,
                    (self.stage_a_reviewer_id, STAGE_A_VERIFY,
                     self.stage_a_reviewer_id, "integration test fixture"),
                )

    def _fixture_stage_b_reviewer_with_grant(self):
        self.stage_b_reviewer_id = self._fixture_user_with_grant(
            STAGE_B_REVIEWER_SUBJECT
        )
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO xportra.global_staff_grants
                        (user_id, permission, status, granted_by, reason,
                         created_at, updated_at)
                    VALUES (%s, %s, 'active', %s, %s, now(), now())
                    ON CONFLICT (user_id, permission) DO UPDATE
                        SET status = 'active', updated_at = now()
                    """,
                    (self.stage_b_reviewer_id, STAGE_B_APPROVE,
                     self.stage_b_reviewer_id, "integration test fixture"),
                )

    def _fixture_source(self):
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO xportra.regulatory_sources
                        (id, authority_id, jurisdiction, title, version, status,
                         effective_date, publication_date, source_url,
                         retrieval_timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        SOURCE_ID, self.authority_id, "EU", "Test Regulation",
                        "1.0", "active", "2024-01-01", "2024-01-01",
                        "https://example.com/regulation",
                    ),
                )

    def _fixture_artifact(self):
        content = b"# Sesame Regulation\n\nShall be labeled with origin.\n"
        content_hash = hashlib.sha256(content).hexdigest()
        key = f"regulatory-source-artifacts/{SOURCE_ID}/{content_hash}"
        self.storage.objects[key] = content
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO xportra.regulatory_source_artifacts
                        (id, source_id, artifact_uri, content_hash,
                         content_length, content_type, acquisition_channel,
                         acquired_by, acquired_at, status, source_version)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now(), %s, %s)
                    ON CONFLICT (id) DO UPDATE
                        SET content_hash = EXCLUDED.content_hash,
                            content_length = EXCLUDED.content_length,
                            content_type = EXCLUDED.content_type,
                            acquisition_channel = EXCLUDED.acquisition_channel,
                            acquired_by = EXCLUDED.acquired_by,
                            status = EXCLUDED.status,
                            source_version = EXCLUDED.source_version
                    """,
                    (
                        ARTIFACT_ID, SOURCE_ID, key, content_hash,
                        len(content), "text/plain", "manual_upload",
                        str(self.stage_a_reviewer_id), "validated", None,
                    ),
                )

    def _fixture_candidate(self):
        norm_id = UUID("44444444-0000-0000-0000-000000000404")
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO xportra.regulatory_document_normalizations
                        (id, artifact_id, source_id, document_title,
                         normalized_text, normalized_content, content_type,
                         parser_name, status, normalized_at, created_at,
                         updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'normalized',
                            now(), now(), now())
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        norm_id, ARTIFACT_ID, SOURCE_ID,
                        "Test Regulation",
                        "Shall be labeled with origin.",
                        '{"mime_type": "text/plain", "structure": []}',
                        "text/plain", "v1",
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO xportra.regulatory_requirements
                        (id, normalized_document_id, requirement_text,
                         requirement_type, source_location, position, actor,
                         condition_metadata, status, ingestion_job_id,
                         extraction_outcome, parser_version, manual_entry,
                         reviewer_user_id, reviewed_at, source_id,
                         stage_a_status, stage_a_reviewer_user_id,
                         stage_a_reviewed_at, stage_a_rationale,
                         created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'extracted',
                            NULL, 'succeeded', 'v1', FALSE, NULL, NULL,
                            %s, 'verified', %s, now(), %s,
                            now(), now())
                    ON CONFLICT (id) DO UPDATE
                        SET stage_a_status = EXCLUDED.stage_a_status,
                            stage_a_reviewer_user_id = EXCLUDED.stage_a_reviewer_user_id,
                            stage_a_reviewed_at = EXCLUDED.stage_a_reviewed_at,
                            stage_a_rationale = EXCLUDED.stage_a_rationale
                    """,
                    (
                        CANDIDATE_ID, norm_id,
                        "Shall be labeled with origin.",
                        "labeling",
                        '{"section_order": 0, "heading": null}',
                        0, str(self.stage_a_reviewer_id), None,
                        SOURCE_ID,
                        self.stage_a_reviewer_id,
                        "Source text verified against artifact.",
                    ),
                )

    # ---- Tests ----

    def test_authorized_stage_b_approve(self):
        result = self.service.approve_stage_b(
            actor_user_id=self.stage_b_reviewer_id,
            candidate_id=CANDIDATE_ID,
            stage_b_status=STAGE_B_STATUS_APPROVED,
            rationale="Requirement applies to the Nigerian sesame pilot scope.",
            pilot_scope="sesame-eu-pilot-v1",
        )
        self.assertEqual(result["stage_b_status"], STAGE_B_STATUS_APPROVED)
        self.assertEqual(result["stage_b_reviewer_user_id"],
                         self.stage_b_reviewer_id)
        self.assertIsNotNone(result["stage_b_reviewed_at"])
        self.assertEqual(
            result["stage_b_rationale"],
            "Requirement applies to the Nigerian sesame pilot scope.",
        )
        self.assertIsNotNone(result["audit_id"])

        # Verify current state
        row = self.service.get_candidate_stage_b(CANDIDATE_ID)
        self.assertEqual(row["stage_b_status"], STAGE_B_STATUS_APPROVED)
        self.assertEqual(row["stage_b_reviewer_user_id"],
                         self.stage_b_reviewer_id)
        self.assertEqual(
            row["stage_b_rationale"],
            "Requirement applies to the Nigerian sesame pilot scope.",
        )
        self.assertEqual(row["stage_b_pilot_scope"], "sesame-eu-pilot-v1")

        # Verify audit history
        history = self.service.list_stage_b_decisions(CANDIDATE_ID)
        self.assertGreaterEqual(len(history), 1)
        latest = history[0]
        self.assertEqual(latest["stage_b_status"], STAGE_B_STATUS_APPROVED)
        self.assertEqual(latest["reviewer_user_id"], self.stage_b_reviewer_id)

    def test_stage_b_reject(self):
        result = self.service.approve_stage_b(
            actor_user_id=self.stage_b_reviewer_id,
            candidate_id=CANDIDATE_ID,
            stage_b_status=STAGE_B_STATUS_REJECTED,
            rationale="Requirement does not apply to the pilot scope.",
            pilot_scope="sesame-eu-pilot-v1",
        )
        self.assertEqual(result["stage_b_status"], STAGE_B_STATUS_REJECTED)
        self.assertEqual(result["stage_b_reviewer_user_id"],
                         self.stage_b_reviewer_id)

        row = self.service.get_candidate_stage_b(CANDIDATE_ID)
        self.assertEqual(row["stage_b_status"], STAGE_B_STATUS_REJECTED)

    def test_stage_b_clarification_required(self):
        result = self.service.approve_stage_b(
            actor_user_id=self.stage_b_reviewer_id,
            candidate_id=CANDIDATE_ID,
            stage_b_status=STAGE_B_STATUS_CLARIFICATION_REQUIRED,
            rationale="Source text ambiguous; needs clarification.",
            pilot_scope="sesame-eu-pilot-v1",
        )
        self.assertEqual(
            result["stage_b_status"], STAGE_B_STATUS_CLARIFICATION_REQUIRED
        )
        self.assertEqual(result["stage_b_reviewer_user_id"],
                         self.stage_b_reviewer_id)

    def test_unauthorized_actor_denied(self):
        service = RegulatoryStageBReviewService(
            self.database,
            grant_service=_FakeGrantService(set()),
        )
        with self.assertRaises(PermissionDeniedError):
            service.approve_stage_b(
                actor_user_id=UUID("bbbbbbbb-0000-0000-0000-000000000004"),
                candidate_id=CANDIDATE_ID,
                stage_b_status=STAGE_B_STATUS_APPROVED,
                rationale="Test rationale.",
                pilot_scope="sesame-eu-pilot-v1",
            )

    def test_stage_a_not_verified_denied(self):
        # Candidate with stage_a_status = 'pending'
        factory_cand_id = UUID("22222222-0000-0000-0000-000000000200")
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO xportra.regulatory_requirements
                        (id, normalized_document_id, requirement_text,
                         requirement_type, source_location, position, actor,
                         condition_metadata, status, ingestion_job_id,
                         extraction_outcome, parser_version, manual_entry,
                         reviewer_user_id, reviewed_at, source_id,
                         stage_a_status, stage_a_reviewer_user_id,
                         stage_a_reviewed_at, stage_a_rationale,
                         created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'extracted',
                            NULL, 'succeeded', 'v1', FALSE, NULL, NULL,
                            %s, 'pending', NULL, NULL, NULL,
                            now(), now())
                    RETURNING *
                    """,
                    (
                        factory_cand_id, UUID("44444444-0000-0000-0000-000000000404"),
                        "Stage A not verified candidate.", "labeling",
                        '{"section_order": 0, "heading": null}', 1,
                        str(self.stage_a_reviewer_id), None,
                        SOURCE_ID,
                    ),
                )
        with self.assertRaises(ApplicationValidationError):
            self.service.approve_stage_b(
                actor_user_id=self.stage_b_reviewer_id,
                candidate_id=factory_cand_id,
                stage_b_status=STAGE_B_STATUS_APPROVED,
                rationale="Cannot approve without Stage A.",
                pilot_scope="sesame-eu-pilot-v1",
            )

    def test_invalid_stage_b_status_denied(self):
        with self.assertRaises(ApplicationValidationError):
            self.service.approve_stage_b(
                actor_user_id=self.stage_b_reviewer_id,
                candidate_id=CANDIDATE_ID,
                stage_b_status="not_a_status",
                rationale="Test rationale.",
                pilot_scope="sesame-eu-pilot-v1",
            )

    def test_empty_rationale_denied(self):
        with self.assertRaises(ApplicationValidationError):
            self.service.approve_stage_b(
                actor_user_id=self.stage_b_reviewer_id,
                candidate_id=CANDIDATE_ID,
                stage_b_status=STAGE_B_STATUS_APPROVED,
                rationale="",
                pilot_scope="sesame-eu-pilot-v1",
            )

    def test_empty_pilot_scope_denied(self):
        with self.assertRaises(ApplicationValidationError):
            self.service.approve_stage_b(
                actor_user_id=self.stage_b_reviewer_id,
                candidate_id=CANDIDATE_ID,
                stage_b_status=STAGE_B_STATUS_APPROVED,
                rationale="Test rationale.",
                pilot_scope="",
            )

    def test_nonexistent_candidate_denied(self):
        with self.assertRaises(ApplicationNotFoundError):
            self.service.approve_stage_b(
                actor_user_id=self.stage_b_reviewer_id,
                candidate_id=UUID("99999999-0000-0000-0000-000000000999"),
                stage_b_status=STAGE_B_STATUS_APPROVED,
                rationale="Test rationale.",
                pilot_scope="sesame-eu-pilot-v1",
            )

    def test_same_reviewer_as_stage_a_denied(self):
        # Stage B reviewer is the same as Stage A reviewer
        service_same = RegulatoryStageBReviewService(
            self.database,
            grant_service=_FakeGrantService({self.stage_a_reviewer_id:
                                             STAGE_B_APPROVE}),
        )
        with self.assertRaises(ApplicationValidationError):
            service_same.approve_stage_b(
                actor_user_id=self.stage_a_reviewer_id,
                candidate_id=CANDIDATE_ID,
                stage_b_status=STAGE_B_STATUS_APPROVED,
                rationale="Same person review.",
                pilot_scope="sesame-eu-pilot-v1",
            )

    def test_stage_b_does_not_publish(self):
        """Stage B approval does not mark requirement as published."""
        result = self.service.approve_stage_b(
            actor_user_id=self.stage_b_reviewer_id,
            candidate_id=CANDIDATE_ID,
            stage_b_status=STAGE_B_STATUS_APPROVED,
            rationale="Source verified.",
            pilot_scope="sesame-eu-pilot-v1",
        )
        # The candidate's base status remains "extracted" — not published
        row = self.service.get_candidate_stage_b(CANDIDATE_ID)
        self.assertEqual(row["status"], "extracted")
        self.assertEqual(result["stage_b_status"], STAGE_B_STATUS_APPROVED)

    def test_stage_b_audit_history_append_only(self):
        # First review: reject
        self.service.approve_stage_b(
            actor_user_id=self.stage_b_reviewer_id,
            candidate_id=CANDIDATE_ID,
            stage_b_status=STAGE_B_STATUS_REJECTED,
            rationale="First review: rejected.",
            pilot_scope="sesame-eu-pilot-v1",
        )
        # Second review: approve
        self.service.approve_stage_b(
            actor_user_id=self.stage_b_reviewer_id,
            candidate_id=CANDIDATE_ID,
            stage_b_status=STAGE_B_STATUS_APPROVED,
            rationale="Second review: approved after correction.",
            pilot_scope="sesame-eu-pilot-v1",
        )
        # Both decisions preserved
        history = self.service.list_stage_b_decisions(CANDIDATE_ID)
        self.assertGreaterEqual(len(history), 2)
        statuses = [h["stage_b_status"] for h in history]
        self.assertIn(STAGE_B_STATUS_APPROVED, statuses)
        self.assertIn(STAGE_B_STATUS_REJECTED, statuses)
        # Current state reflects the last decision
        row = self.service.get_candidate_stage_b(CANDIDATE_ID)
        self.assertEqual(row["stage_b_status"], STAGE_B_STATUS_APPROVED)


class _FakeGrantService:
    def __init__(self, granted: set) -> None:
        self.granted = granted

    def is_granted(self, user_id: UUID, permission: str) -> bool:
        return user_id in self.granted


if __name__ == "__main__":
    unittest.main()
