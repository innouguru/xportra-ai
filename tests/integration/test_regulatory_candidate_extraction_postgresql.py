"""PostgreSQL integration tests for regulatory candidate extraction.

Tests candidate extraction against the isolated local ``xportra_test``
database. Storage is exercised through a deterministic in-memory adapter
— no Supabase Storage or production service is contacted.

Required tables: authorities, regulatory_sources, regulatory_source_artifacts,
regulatory_ingestion_jobs, regulatory_document_normalizations,
regulatory_document_metadata, regulatory_requirements, users,
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
from xportra.application.global_staff import GRANT_MANAGE, GlobalStaffGrantService
from xportra.application.regulatory_candidate_extraction_service import (
    EXTRACTION_OUTCOME_FAILED,
    EXTRACTION_OUTCOME_MANUAL,
    EXTRACTION_OUTCOME_SUCCEEDED,
    RegulatoryCandidateExtractionService,
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

ACTOR_SUBJECT = UUID("aaaaaa03-0000-0000-0000-000000000001")
AUTHORITY_ID = UUID("cccccc03-0000-0000-0000-000000000003")
SOURCE_ID = UUID("dddddd03-0000-0000-0000-000000000004")
ARTIFACT_ID = UUID("eeeeee03-0000-0000-0000-000000000005")
JOB_ID = UUID("ffffffff-0003-0000-0000-000000000006")
TENANT = UUID("99999999-0000-0000-0000-000000000099")

REQUIRED_TABLES = (
    "authorities",
    "regulatory_sources",
    "regulatory_source_artifacts",
    "regulatory_ingestion_jobs",
    "regulatory_document_normalizations",
    "regulatory_document_metadata",
    "regulatory_requirements",
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


class RegulatoryCandidateExtractionIntegrationTests(unittest.TestCase):
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
        if cls.database is not None:
            cls._cleanup_all()

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
                "apply migrations 001–003, 004–006, 018, 021 before running"
            )

    @classmethod
    def _cleanup_all(cls):
        if cls.database is None:
            return
        with cls.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM xportra.regulatory_requirements "
                    "WHERE normalized_document_id IN "
                    "(SELECT id FROM xportra.regulatory_document_normalizations "
                    "WHERE source_id = %s)", (SOURCE_ID,)
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_document_metadata "
                    "WHERE normalized_document_id IN "
                    "(SELECT id FROM xportra.regulatory_document_normalizations "
                    "WHERE source_id = %s)", (SOURCE_ID,)
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_document_normalizations "
                    "WHERE source_id = %s", (SOURCE_ID,)
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_ingestion_jobs "
                    "WHERE source_id = %s", (SOURCE_ID,)
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_source_artifacts "
                    "WHERE source_id = %s", (SOURCE_ID,)
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_sources WHERE id = %s",
                    (SOURCE_ID,),
                )
                cursor.execute(
                    "DELETE FROM xportra.authorities WHERE id = %s",
                    (AUTHORITY_ID,),
                )
                cursor.execute(
                    "DELETE FROM xportra.global_staff_grants "
                    "WHERE user_id IN (SELECT id FROM xportra.users "
                    "WHERE supabase_uid = %s)", (ACTOR_SUBJECT,)
                )
                cursor.execute(
                    "DELETE FROM xportra.users WHERE supabase_uid = %s",
                    (ACTOR_SUBJECT,),
                )
                cursor.execute(
                    "DELETE FROM xportra.user_tenant_memberships "
                    "WHERE user_id IN (SELECT id FROM xportra.users "
                    "WHERE supabase_uid = %s)", (ACTOR_SUBJECT,)
                )

    def setUp(self):
        if self.database is None:
            self.skipTest("DATABASE_URL is not configured")
        self.storage = FakeStorage()
        self.service = RegulatoryCandidateExtractionService(
            self.database,
            storage_service=FakeStorageService(self.storage),
        )
        self._fixture_authority()
        self._fixture_actor_with_grant()
        self._fixture_source()
        self._fixture_artifact()
        self._fixture_job()

    def tearDown(self):
        if self.database is None:
            return
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM xportra.regulatory_requirements "
                    "WHERE normalized_document_id IN "
                    "(SELECT id FROM xportra.regulatory_document_normalizations "
                    "WHERE source_id = %s)", (SOURCE_ID,)
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_document_metadata "
                    "WHERE normalized_document_id IN "
                    "(SELECT id FROM xportra.regulatory_document_normalizations "
                    "WHERE source_id = %s)", (SOURCE_ID,)
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_document_normalizations "
                    "WHERE source_id = %s", (SOURCE_ID,)
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_ingestion_jobs "
                    "WHERE source_id = %s", (SOURCE_ID,)
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_source_artifacts "
                    "WHERE source_id = %s", (SOURCE_ID,)
                )

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
                        RETURNING *
                        """,
                        (AUTHORITY_ID, "Test Authority", "EU"),
                    )

    def _fixture_actor_with_grant(self):
        user_repo = UserRepository(self.database)
        membership_repo = UserTenantMembershipRepository(self.database)
        existing = user_repo.get_by_supabase_uid(ACTOR_SUBJECT)
        if existing is None:
            row = user_repo.create(
                "Integration Actor", "integration-actor@example.invalid",
                "active", ACTOR_SUBJECT,
            )
            self.actor_id = row["id"]
        else:
            self.actor_id = existing["id"]
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO xportra.tenants (id, legal_name, slug, status) "
                    "VALUES (%s, %s, %s, 'active') ON CONFLICT (id) DO NOTHING",
                    (TENANT, "Integration Tenant", "integration-tenant"),
                )
                cursor.execute(
                    """
                    INSERT INTO xportra.user_tenant_memberships
                        (id, tenant_id, user_id, role, status, added_at, created_at, updated_at)
                    VALUES (gen_random_uuid(), %s, %s, 'owner', 'active', now(), now(), now())
                    ON CONFLICT (tenant_id, user_id) DO NOTHING
                    """,
                    (TENANT, self.actor_id),
                )
        # Directly insert grant_manage row (bootstrap is a separate gate).
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
                    (self.actor_id, GRANT_MANAGE, self.actor_id,
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
        content = b"# Sesame Regulation\n\nShall be labeled with origin.\nShall not exceed 50 kg."
        content_hash = hashlib.sha256(content).hexdigest()
        key = f"regulatory-source-artifacts/{SOURCE_ID}/{content_hash}"
        self.storage.objects[key] = content
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

    def _fixture_job(self):
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO xportra.regulatory_ingestion_jobs
                        (id, artifact_id, source_id, status, attempt_number,
                         actor_user_id, parser_version)
                    VALUES (%s, %s, %s, 'pending', 1, %s, 'v1')
                    ON CONFLICT (id) DO UPDATE
                        SET status = EXCLUDED.status, updated_at = now()
                    RETURNING *
                    """,
                    (JOB_ID, ARTIFACT_ID, SOURCE_ID, self.actor_id),
                )

    # ---- Tests ----

    def test_successful_extraction_persists_candidates_with_provenance(self):
        result = self.service.extract_candidates(
            actor_user_id=self.actor_id,
            source_id=SOURCE_ID,
            artifact_id=ARTIFACT_ID,
            job_id=JOB_ID,
        )
        self.assertEqual(result["outcome"], EXTRACTION_OUTCOME_SUCCEEDED)
        self.assertGreaterEqual(result["candidate_count"], 1)
        self.assertEqual(result["job"]["status"], "completed")
        for cand in result["candidates"]:
            self.assertEqual(cand["source_id"], SOURCE_ID)
            self.assertEqual(cand["ingestion_job_id"], JOB_ID)
            self.assertEqual(cand["extraction_outcome"], EXTRACTION_OUTCOME_SUCCEEDED)
            self.assertEqual(cand["parser_version"], "v1")
            self.assertFalse(cand["manual_entry"])

    def test_duplicate_extraction_is_idempotent(self):
        result1 = self.service.extract_candidates(
            actor_user_id=self.actor_id,
            source_id=SOURCE_ID,
            artifact_id=ARTIFACT_ID,
            job_id=JOB_ID,
        )
        self.assertFalse(result1["duplicate"])
        count1 = result1["candidate_count"]

        # Re-extract same artifact with a new job
        job2_id = UUID("ffffffff-0003-0000-0000-000000000007")
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO xportra.regulatory_ingestion_jobs
                        (id, artifact_id, source_id, status, attempt_number,
                         actor_user_id, parser_version)
                    VALUES (%s, %s, %s, 'pending', 2, %s, 'v1')
                    RETURNING *
                    """,
                    (job2_id, ARTIFACT_ID, SOURCE_ID, self.actor_id),
                )
        result2 = self.service.extract_candidates(
            actor_user_id=self.actor_id,
            source_id=SOURCE_ID,
            artifact_id=ARTIFACT_ID,
            job_id=job2_id,
        )
        # Idempotent: same candidates, no duplicates
        self.assertTrue(result2["duplicate"])
        self.assertEqual(result2["candidate_count"], count1)

    def test_unauthorized_actor_denied(self):
        service = RegulatoryCandidateExtractionService(
            self.database,
            grant_service=_FakeGrantService(set()),
            storage_service=FakeStorageService(self.storage),
        )
        with self.assertRaises(PermissionDeniedError):
            service.extract_candidates(
                actor_user_id=UUID("bbbbbbbb-0000-0000-0000-000000000002"),
                source_id=SOURCE_ID,
                artifact_id=ARTIFACT_ID,
                job_id=JOB_ID,
            )

    def test_manual_candidate_entry_with_reviewer_attribution(self):
        row = self.service.enter_manual_candidate(
            actor_user_id=self.actor_id,
            source_id=SOURCE_ID,
            artifact_id=ARTIFACT_ID,
            requirement_text="Manually entered recovery requirement.",
            requirement_type="documentation",
            source_location={"section_order": 9, "heading": "Annex B"},
            position=42,
            justification="Extraction failed; manual recovery.",
        )
        self.assertEqual(row["requirement_text"], "Manually entered recovery requirement.")
        self.assertEqual(row["extraction_outcome"], EXTRACTION_OUTCOME_MANUAL)
        self.assertTrue(row["manual_entry"])
        self.assertEqual(row["reviewer_user_id"], self.actor_id)
        self.assertIsNotNone(row["reviewed_at"])
        self.assertIsNone(row["ingestion_job_id"])

    def test_manual_candidate_empty_text_rejected(self):
        with self.assertRaises(ApplicationValidationError):
            self.service.enter_manual_candidate(
                actor_user_id=self.actor_id,
                source_id=SOURCE_ID,
                artifact_id=ARTIFACT_ID,
                requirement_text="",
            )

    def test_candidates_have_extracted_status_not_approved(self):
        result = self.service.extract_candidates(
            actor_user_id=self.actor_id,
            source_id=SOURCE_ID,
            artifact_id=ARTIFACT_ID,
            job_id=JOB_ID,
        )
        for cand in result["candidates"]:
            self.assertEqual(cand["status"], "extracted")
        # Extraction does not publish or approve — no Stage A/B decision made.


class _FakeGrantService:
    def __init__(self, granted: set) -> None:
        self.granted = granted

    def is_granted(self, user_id: UUID, permission: str) -> bool:
        return user_id in self.granted


if __name__ == "__main__":
    unittest.main()
