"""PostgreSQL integration tests for Stage A regulatory source and wording
verification.

Tests Stage A review against the isolated local ``xportra_test`` database.
Tests use deterministic test storage — no Supabase Storage or production
service is contacted.

Required tables: authorities, regulatory_sources, regulatory_source_artifacts,
regulatory_ingestion_jobs, regulatory_document_normalizations,
regulatory_document_metadata, regulatory_requirements,
regulatory_stage_a_reviews, users, global_staff_grants.
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
    GlobalStaffGrantService,
)
from xportra.application.regulatory_stage_a_review_service import (
    RegulatoryStageAReviewService,
    STAGE_A_STATUS_CLARIFICATION_REQUIRED,
    STAGE_A_STATUS_REJECTED,
    STAGE_A_STATUS_VERIFIED,
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

ACTOR_SUBJECT = UUID("aaaaaa04-0000-0000-0000-000000000001")
AUTHORITY_ID = UUID("cccccc04-0000-0000-0000-000000000003")
SOURCE_ID = UUID("dddddd04-0000-0000-0000-000000000004")
ARTIFACT_ID = UUID("eeeeee04-0000-0000-0000-000000000005")
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


class RegulatoryStageAReviewIntegrationTests(unittest.TestCase):
    database: Database | None = None

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DATABASE_URL", "").strip():
            raise unittest.SkipTest("DATABASE_URL is not configured")
        cls.database = Database(DatabaseSettings.from_environment())
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
                "apply migrations 001–003, 004–006, 018, 021–025 before running"
            )

    def setUp(self):
        if self.database is None:
            self.skipTest("DATABASE_URL is not configured")
        self.service = RegulatoryStageAReviewService(self.database)
        self._fixture_authority()
        self._fixture_actor_with_grant()
        self._fixture_source()
        self._fixture_artifact()
        self._fixture_candidate()

    def tearDown(self):
        pass  # No cleanup: append-only tables cannot be truncated.

    def _fixture_authority(self):
        repo = AuthorityRepository(self.database)
        if repo.get(AUTHORITY_ID) is None:
            with self.database.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO xportra.authorities
                            (id, name, jurisdiction, authority_type, status)
                        VALUES (%s, %s, %s, 'government', 'active')
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (AUTHORITY_ID, "Test Authority", "EU"),
                    )

    def _fixture_actor_with_grant(self):
        user_repo = UserRepository(self.database)
        existing = user_repo.get_by_supabase_uid(ACTOR_SUBJECT)
        if existing is None:
            row = user_repo.create(
                "Stage A Actor", "stage-a-actor@example.invalid", "active",
                ACTOR_SUBJECT,
            )
            self.actor_id = row["id"]
        else:
            self.actor_id = existing["id"]
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO xportra.tenants (id, legal_name, slug, status) "
                    "VALUES (%s, %s, %s, 'active') ON CONFLICT (id) DO NOTHING",
                    (TENANT, "Stage A Tenant", "stage-a-tenant"),
                )
                cursor.execute(
                    """
                    INSERT INTO xportra.user_tenant_memberships
                        (id, tenant_id, user_id, role, status, added_at,
                         created_at, updated_at)
                    VALUES (gen_random_uuid(), %s, %s, 'owner', 'active',
                            now(), now(), now())
                    ON CONFLICT (tenant_id, user_id) DO NOTHING
                    """,
                    (TENANT, self.actor_id),
                )
                cursor.execute(
                    """
                    INSERT INTO xportra.global_staff_grants
                        (user_id, permission, status, granted_by, reason,
                         created_at, updated_at)
                    VALUES (%s, %s, 'active', %s, %s, now(), now())
                    ON CONFLICT (user_id, permission) DO UPDATE
                        SET status = 'active', updated_at = now()
                    """,
                    (self.actor_id, STAGE_A_VERIFY, self.actor_id,
                     "integration test fixture"),
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
                    ON CONFLICT (id) DO UPDATE
                        SET status = EXCLUDED.status, updated_at = now()
                    RETURNING *
                    """,
                    (
                        SOURCE_ID, AUTHORITY_ID, "EU", "Test Regulation",
                        "1.0", "active", "2024-01-01", "2024-01-01",
                        "https://example.com/regulation",
                    ),
                )

    def _fixture_artifact(self):
        content = b"# Sesame Regulation\n\nShall be labeled with origin.\n"
        content_hash = hashlib.sha256(content).hexdigest()
        key = f"regulatory-source-artifacts/{SOURCE_ID}/{content_hash}"
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO xportra.regulatory_source_artifacts
                        (id, source_id, artifact_uri, content_hash, content_length,
                         content_type, acquisition_channel, acquired_by,
                         acquired_at, status, source_version)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now(), %s, %s)
                    ON CONFLICT (id) DO UPDATE
                        SET content_hash = EXCLUDED.content_hash,
                            updated_at = now()
                    RETURNING *
                    """,
                    (
                        ARTIFACT_ID, SOURCE_ID, key, content_hash, len(content),
                        "text/plain", "manual_upload", str(self.actor_id),
                        "validated", None,
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
                            %s, 'pending', NULL, NULL, NULL, now(), now())
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        CANDIDATE_ID, norm_id,
                        "Shall be labeled with origin.",
                        "labeling",
                        '{"section_order": 0, "heading": null}',
                        0, str(self.actor_id), None,
                        SOURCE_ID,
                    ),
                )

    # ---- Tests ----

    def test_authorized_stage_a_verify(self):
        result = self.service.verify_stage_a(
            actor_user_id=self.actor_id,
            candidate_id=CANDIDATE_ID,
            stage_a_status=STAGE_A_STATUS_VERIFIED,
            rationale="Source text matches extracted wording.",
        )
        self.assertEqual(result["stage_a_status"], STAGE_A_STATUS_VERIFIED)
        self.assertEqual(result["stage_a_reviewer_user_id"], self.actor_id)
        self.assertIsNotNone(result["stage_a_reviewed_at"])
        self.assertEqual(
            result["stage_a_rationale"], "Source text matches extracted wording."
        )
        self.assertIsNotNone(result["audit_id"])

        row = self.service.get_candidate_stage_a(CANDIDATE_ID)
        self.assertEqual(row["stage_a_status"], STAGE_A_STATUS_VERIFIED)
        self.assertEqual(row["stage_a_reviewer_user_id"], self.actor_id)

        history = self.service.list_stage_a_decisions(CANDIDATE_ID)
        self.assertGreaterEqual(len(history), 1)
        self.assertEqual(history[0]["stage_a_status"], STAGE_A_STATUS_VERIFIED)
        self.assertEqual(history[0]["reviewer_user_id"], self.actor_id)

    def test_unauthorized_actor_denied(self):
        service = RegulatoryStageAReviewService(
            self.database,
            grant_service=_FakeGrantService(set()),
        )
        with self.assertRaises(PermissionDeniedError):
            service.verify_stage_a(
                actor_user_id=UUID("bbbbbbbb-0000-0000-0000-000000000002"),
                candidate_id=CANDIDATE_ID,
                stage_a_status=STAGE_A_STATUS_VERIFIED,
                rationale="Test rationale.",
            )

    def test_stage_a_reject(self):
        result = self.service.verify_stage_a(
            actor_user_id=self.actor_id,
            candidate_id=CANDIDATE_ID,
            stage_a_status=STAGE_A_STATUS_REJECTED,
            rationale="Wording not supported by source text.",
        )
        self.assertEqual(result["stage_a_status"], STAGE_A_STATUS_REJECTED)
        self.assertEqual(result["stage_a_reviewer_user_id"], self.actor_id)

        row = self.service.get_candidate_stage_a(CANDIDATE_ID)
        self.assertEqual(row["stage_a_status"], STAGE_A_STATUS_REJECTED)

    def test_stage_a_clarification_required(self):
        result = self.service.verify_stage_a(
            actor_user_id=self.actor_id,
            candidate_id=CANDIDATE_ID,
            stage_a_status=STAGE_A_STATUS_CLARIFICATION_REQUIRED,
            rationale="Source text ambiguous; needs clarification.",
        )
        self.assertEqual(
            result["stage_a_status"], STAGE_A_STATUS_CLARIFICATION_REQUIRED
        )

    def test_nonexistent_candidate_rejected(self):
        with self.assertRaises(ApplicationNotFoundError):
            self.service.verify_stage_a(
                actor_user_id=self.actor_id,
                candidate_id=UUID("99999999-0000-0000-0000-000000000999"),
                stage_a_status=STAGE_A_STATUS_VERIFIED,
                rationale="Test rationale.",
            )

    def test_invalid_stage_a_status_rejected(self):
        with self.assertRaises(ApplicationValidationError):
            self.service.verify_stage_a(
                actor_user_id=self.actor_id,
                candidate_id=CANDIDATE_ID,
                stage_a_status="not_a_status",
                rationale="Test rationale.",
            )

    def test_empty_rationale_rejected(self):
        with self.assertRaises(ApplicationValidationError):
            self.service.verify_stage_a(
                actor_user_id=self.actor_id,
                candidate_id=CANDIDATE_ID,
                stage_a_status=STAGE_A_STATUS_VERIFIED,
                rationale="",
            )

    def test_stage_a_audit_history_append_only(self):
        self.service.verify_stage_a(
            actor_user_id=self.actor_id,
            candidate_id=CANDIDATE_ID,
            stage_a_status=STAGE_A_STATUS_REJECTED,
            rationale="First review: rejected.",
        )
        self.service.verify_stage_a(
            actor_user_id=self.actor_id,
            candidate_id=CANDIDATE_ID,
            stage_a_status=STAGE_A_STATUS_VERIFIED,
            rationale="Second review: verified after correction.",
        )
        history = self.service.list_stage_a_decisions(CANDIDATE_ID)
        self.assertGreaterEqual(len(history), 2)
        statuses = [h["stage_a_status"] for h in history]
        self.assertIn(STAGE_A_STATUS_VERIFIED, statuses)
        self.assertIn(STAGE_A_STATUS_REJECTED, statuses)
        row = self.service.get_candidate_stage_a(CANDIDATE_ID)
        self.assertEqual(row["stage_a_status"], STAGE_A_STATUS_VERIFIED)

    def test_stage_a_does_not_set_applicability(self):
        result = self.service.verify_stage_a(
            actor_user_id=self.actor_id,
            candidate_id=CANDIDATE_ID,
            stage_a_status=STAGE_A_STATUS_VERIFIED,
            rationale="Source verified.",
        )
        row = self.service.get_candidate_stage_a(CANDIDATE_ID)
        self.assertEqual(row["status"], "extracted")
        self.assertEqual(result["stage_a_status"], STAGE_A_STATUS_VERIFIED)


class _FakeGrantService:
    def __init__(self, granted: set) -> None:
        self.granted = granted

    def is_granted(self, user_id: UUID, permission: str) -> bool:
        return user_id in self.granted


if __name__ == "__main__":
    unittest.main()
