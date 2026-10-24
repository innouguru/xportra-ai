"""PostgreSQL integration tests for regulatory source intake.

These tests require a live local PostgreSQL database (``DATABASE_URL``)
pointing at the isolated ``xportra_test`` database with migrations
001–003 applied. They are skipped when ``DATABASE_URL`` is not
configured or when required tables are missing.

Storage is exercised through a deterministic in-memory adapter — no
Supabase Storage or production service is contacted.

Each test creates its own fixture records and cleans them up in
``tearDown`` so tests are isolated.
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
from xportra.application.global_staff import (
    GRANT_MANAGE,
    GlobalStaffGrantService,
)
from xportra.application.regulatory_source_intake_service import (
    RegulatorySourceIntakeService,
)
from xportra.api.errors import APIError, PermissionDeniedError
from xportra.persistence.database import Database, DatabaseSettings
from xportra.persistence.repositories import (
    AuthorityRepository,
    RegulatoryIngestionJobRepository,
    RegulatoryRequirementRepository,
    RegulatorySourceRepository,
    UserRepository,
)
from xportra.persistence.tenant import TenantContext

ACTOR_SUBJECT = UUID("aaaaaa02-0000-0000-0000-000000000001")
AUTHORITY_ID = UUID("cccccc02-0000-0000-0000-000000000003")
TENANT = UUID("99999999-0000-0000-0000-000000000099")

#: Required tables for source registration tests.
REQUIRED_TABLES = (
    "authorities",
    "regulatory_sources",
    "regulatory_source_artifacts",
    "users",
    "global_staff_grants",
)

#: Additional table required for artifact upload / durable job tests.
JOB_TABLE = "regulatory_ingestion_jobs"


class FakeStorage:
    """Deterministic in-memory storage adapter — no Supabase contact."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def upload_artifact(
        self, key: str, content: bytes, *, content_type: str,
        actor_user_id: UUID, audit_ref: str | None = None,
    ) -> None:
        self.objects[key] = content


class RegulatorySourceIntakeIntegrationTests(unittest.TestCase):
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
                cursor.execute("SELECT current_user, current_database()")
                row = cursor.fetchone()
                cls.db_user = row["current_user"]
                cls.db_name = row["current_database"]

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
                "apply migrations 001–003 before running integration tests"
            )

    @classmethod
    def _has_table(cls, table_name: str) -> bool:
        if cls.database is None:
            return False
        with cls.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'xportra' AND table_name = %s
                    """,
                    (table_name,),
                )
                return cursor.fetchone() is not None

    @classmethod
    def _cleanup_all(cls):
        if cls.database is None:
            return
        with cls.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM xportra.authorities WHERE id = %s",
                    (AUTHORITY_ID,),
                )

    def setUp(self):
        if self.database is None:
            self.skipTest("DATABASE_URL is not configured")
        self.storage = FakeStorage()
        self.service = RegulatorySourceIntakeService(
            self.database,
            storage_service=_FakeStorageService(self.storage),
        )
        self._fixture_authority()
        self._fixture_user_with_grant()
        self.source_ids: list[UUID] = []

    def _fixture_authority(self):
        authority_repo = AuthorityRepository(self.database)
        existing = authority_repo.get(AUTHORITY_ID)
        if existing is None:
            # Try to find by name/jurisdiction in case it was created
            # by another test class with the same name/jurisdiction
            with self.database.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id FROM xportra.authorities
                        WHERE name = %s AND jurisdiction = %s
                        LIMIT 1
                        """,
                        ("Test Authority", "EU"),
                    )
                    row = cursor.fetchone()
                    if row is not None:
                        # Use existing authority id
                        globals()['AUTHORITY_ID'] = row['id']
                        return
                    # Create new authority
                    cursor.execute(
                        """
                        INSERT INTO xportra.authorities
                            (id, name, jurisdiction, authority_type, status)
                        VALUES (%s, %s, %s, 'government', 'active')
                        RETURNING *
                        """,
                        (AUTHORITY_ID, "Test Authority", "EU"),
                    )

    def _fixture_user_with_grant(self):
        user_repo = UserRepository(self.database)
        existing = user_repo.get_by_supabase_uid(ACTOR_SUBJECT)
        if existing is None:
            row = user_repo.create(
                "Intake Actor", "intake-actor@example.invalid", "active",
                ACTOR_SUBJECT,
            )
            self.actor_id = row["id"]
        else:
            self.actor_id = existing["id"]
        # Directly insert an active grant_manage row (self-grant via the
        # service is denied by design; bootstrap is a separate operational
        # gate). This is test fixture setup only.
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

    def tearDown(self):
        if self.database is None:
            return
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                # Clear supersession links before deleting sources
                cursor.execute(
                    "UPDATE xportra.regulatory_sources "
                    "SET superseded_by_source_id = NULL "
                    "WHERE superseded_by_source_id = ANY(%s)",
                    (self.source_ids,),
                )
                cursor.execute(
                    "UPDATE xportra.regulatory_sources "
                    "SET supersedes_source_id = NULL "
                    "WHERE supersedes_source_id = ANY(%s)",
                    (self.source_ids,),
                )
                for source_id in self.source_ids:
                    cursor.execute(
                        "DELETE FROM xportra.regulatory_ingestion_jobs "
                        "WHERE source_id = %s",
                        (source_id,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.regulatory_source_artifacts "
                        "WHERE source_id = %s",
                        (source_id,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.regulatory_sources WHERE id = %s",
                        (source_id,),
                    )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_review_flags "
                    "WHERE trigger_source_id = ANY(%s)",
                    (self.source_ids,),
                )

    def _b64(self, content: bytes) -> str:
        return base64.b64encode(content).decode("ascii")

    # ---- 1. Source registration ----

    def test_create_source_persists_fields(self):
        row = self.service.register_source(
            actor_user_id=self.actor_id,
            authority_id=AUTHORITY_ID,
            jurisdiction="EU",
            title="Regulation (EU) 2019/1793",
            version="1.0",
            status="draft",
            effective_date="2019-06-25",
            publication_date="2019-04-25",
            source_url="https://eur-lex.europa.eu/legal-content/EN/TXT/",
        )
        self.source_ids.append(row["id"])
        self.assertEqual(row["authority_id"], AUTHORITY_ID)
        self.assertEqual(row["jurisdiction"], "EU")
        self.assertEqual(row["title"], "Regulation (EU) 2019/1793")
        self.assertEqual(row["version"], "1.0")
        self.assertEqual(row["status"], "draft")

        fetched = self.service.get_source(row["id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["id"], row["id"])

    def test_register_source_invalid_status_rejected(self):
        with self.assertRaises(ApplicationValidationError):
            self.service.register_source(
                actor_user_id=self.actor_id,
                authority_id=AUTHORITY_ID,
                jurisdiction="EU",
                title="Test",
                status="not_a_status",
            )

    def test_register_source_invalid_authority_rejected(self):
        with self.assertRaises(ApplicationNotFoundError):
            self.service.register_source(
                actor_user_id=self.actor_id,
                authority_id=UUID("99999999-0000-0000-0000-000000000999"),
                jurisdiction="EU",
                title="Test",
            )

    # ---- 2. Artifact upload and durable job (requires migration 018) ----

    def _require_job_table(self):
        if not self._has_table(JOB_TABLE):
            self.skipTest(
                f"table {JOB_TABLE} missing (migration 018 not applied)"
            )

    def test_upload_artifact_creates_pending_job(self):
        self._require_job_table()
        source = self.service.register_source(
            actor_user_id=self.actor_id,
            authority_id=AUTHORITY_ID,
            jurisdiction="EU",
            title="Test Source",
        )
        self.source_ids.append(source["id"])
        content = b"# Sesame Regulation\nShall be safe."
        result = self.service.upload_artifact(
            actor_user_id=self.actor_id,
            source_id=source["id"],
            content_base64=self._b64(content),
            content_type="text/markdown",
        )
        self.assertFalse(result["duplicate"])
        artifact = result["artifact"]
        job = result["job"]
        self.assertEqual(artifact["source_id"], source["id"])
        self.assertEqual(artifact["content_type"], "text/markdown")
        self.assertEqual(artifact["status"], "validated")
        expected_hash = hashlib.sha256(content).hexdigest()
        self.assertEqual(artifact["content_hash"], expected_hash)
        self.assertEqual(job["status"], "pending")
        self.assertIsNone(job["completed_at"])
        self.assertEqual(job["source_id"], source["id"])
        self.assertEqual(job["actor_user_id"], self.actor_id)

    def test_duplicate_upload_same_content_one_artifact(self):
        self._require_job_table()
        source = self.service.register_source(
            actor_user_id=self.actor_id,
            authority_id=AUTHORITY_ID,
            jurisdiction="EU",
            title="Test Source",
        )
        self.source_ids.append(source["id"])
        content = b"identical content for idempotency"
        result1 = self.service.upload_artifact(
            actor_user_id=self.actor_id,
            source_id=source["id"],
            content_base64=self._b64(content),
            content_type="text/plain",
        )
        self.assertFalse(result1["duplicate"])
        result2 = self.service.upload_artifact(
            actor_user_id=self.actor_id,
            source_id=source["id"],
            content_base64=self._b64(content),
            content_type="text/plain",
        )
        self.assertTrue(result2["duplicate"])
        self.assertEqual(result2["artifact"]["id"], result1["artifact"]["id"])
        jobs = self.service.list_jobs(source["id"])
        self.assertEqual(len(jobs), 1)

    def test_missing_source_upload_rejected(self):
        self._require_job_table()
        with self.assertRaises(ApplicationNotFoundError):
            self.service.upload_artifact(
                actor_user_id=self.actor_id,
                source_id=UUID("99999999-0000-0000-0000-000000000999"),
                content_base64=self._b64(b"hello"),
                content_type="text/plain",
            )

    # ---- 3. Unauthorized access ----

    def test_unauthorized_actor_denied(self):
        service = RegulatorySourceIntakeService(
            self.database,
            grant_service=_FakeGrantService(set()),
            storage_service=_FakeStorageService(self.storage),
        )
        with self.assertRaises(PermissionDeniedError):
            service.register_source(
                actor_user_id=UUID("aaaaaa02-0000-0000-0000-000000000999"),
                authority_id=AUTHORITY_ID,
                jurisdiction="EU",
                title="Test",
            )


class _FakeGrantService:
    def __init__(self, granted: set) -> None:
        self.granted = granted

    def is_granted(self, user_id: UUID, permission: str) -> bool:
        return user_id in self.granted


class _FakeStorageService:
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


# ---- 4. Source supersession ----

class RegulatorySupersessionIntegrationTests(unittest.TestCase):
    database: Database | None = None

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DATABASE_URL", "").strip():
            raise unittest.SkipTest("DATABASE_URL is not configured")
        cls.database = Database(DatabaseSettings.from_environment())
        cls.storage = FakeStorage()
        cls._verify_identity()
        cls._verify_tables(REQUIRED_TABLES + ("regulatory_review_flags",))

    @classmethod
    def tearDownClass(cls):
        if cls.database is not None:
            cls._cleanup_all()

    @classmethod
    def _verify_identity(cls):
        with cls.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_user, current_database()")
                row = cursor.fetchone()
                cls.db_user = row["current_user"]
                cls.db_name = row["current_database"]

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
                "apply migrations 001–003 before running integration tests"
            )

    @classmethod
    def _cleanup_all(cls):
        if cls.database is None:
            return
        with cls.database.transaction() as connection:
            with connection.cursor() as cursor:
                # Clear supersession links before deleting sources
                cursor.execute(
                    "UPDATE xportra.regulatory_sources "
                    "SET supersedes_source_id = NULL, superseded_by_source_id = NULL",
                )
                # Clean up requirements linked to fixture-owned sources (before normalization delete)
                cursor.execute(
                    "DELETE FROM xportra.regulatory_requirements WHERE source_id IN (SELECT id FROM xportra.regulatory_sources WHERE authority_id = %s)",
                    (AUTHORITY_ID,),
                )
                # Clean up review flags by trigger source or linked requirement
                cursor.execute(
                    "DELETE FROM xportra.regulatory_review_flags WHERE trigger_source_id IN (SELECT id FROM xportra.regulatory_sources WHERE authority_id = %s)",
                    (AUTHORITY_ID,),
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_review_flags WHERE requirement_id IN (SELECT id FROM xportra.regulatory_requirements WHERE source_id IN (SELECT id FROM xportra.regulatory_sources WHERE authority_id = %s))",
                    (AUTHORITY_ID,),
                )
                # Clean up normalization records (after requirements deleted)
                cursor.execute(
                    "DELETE FROM xportra.regulatory_document_normalizations WHERE id = %s",
                    (UUID("77777777-0000-0000-0000-000000000700"),),
                )
                cursor.execute(
                    "UPDATE xportra.regulatory_sources "
                    "SET supersedes_source_id = NULL, superseded_by_source_id = NULL",
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_source_artifacts "
                    "WHERE source_id IN "
                    "(SELECT id FROM xportra.regulatory_sources "
                    "WHERE authority_id = %s)",
                    (AUTHORITY_ID,),
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_ingestion_jobs "
                    "WHERE source_id IN "
                    "(SELECT id FROM xportra.regulatory_sources "
                    "WHERE authority_id = %s)",
                    (AUTHORITY_ID,),
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_sources "
                    "WHERE authority_id = %s",
                    (AUTHORITY_ID,),
                )
                cursor.execute(
                    "DELETE FROM xportra.authorities WHERE id = %s",
                    (AUTHORITY_ID,),
                )
                cursor.execute(
                    "DELETE FROM xportra.global_staff_grants "
                    "WHERE user_id IN "
                    "(SELECT id FROM xportra.users WHERE supabase_uid = %s)",
                    (ACTOR_SUBJECT,),
                )
                cursor.execute(
                    "DELETE FROM xportra.users WHERE supabase_uid = %s",
                    (ACTOR_SUBJECT,),
                )

    def setUp(self):
        if self.database is None:
            self.skipTest("DATABASE_URL is not configured")
        self.storage = FakeStorage()
        self.service = RegulatorySourceIntakeService(
            self.database,
            storage_service=_FakeStorageService(self.storage),
        )
        self.source_ids: list[UUID] = []
        self._fixture_authority()
        self._fixture_user_with_grant()

    def _fixture_authority(self):
        authority_repo = AuthorityRepository(self.database)
        if authority_repo.get(AUTHORITY_ID) is None:
            with self.database.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO xportra.authorities
                            (id, name, jurisdiction, authority_type, status)
                        VALUES (%s, %s, %s, 'government', 'active')
                        ON CONFLICT (name, jurisdiction) DO NOTHING
                        RETURNING *
                        """,
                        (AUTHORITY_ID, "Supersession Authority", "EU"),
                    )

    def _fixture_user_with_grant(self):
        user_repo = UserRepository(self.database)
        existing = user_repo.get_by_supabase_uid(ACTOR_SUBJECT)
        if existing is None:
            row = user_repo.create(
                "Supersession Actor", "supersession-actor@example.invalid",
                "active", ACTOR_SUBJECT,
            )
            self.actor_id = row["id"]
        else:
            self.actor_id = existing["id"]
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

    def tearDown(self):
        if self.database is None:
            return
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                # Clear supersession links before deleting sources
                cursor.execute(
                    "UPDATE xportra.regulatory_sources "
                    "SET superseded_by_source_id = NULL "
                    "WHERE superseded_by_source_id = ANY(%s)",
                    (self.source_ids,),
                )
                cursor.execute(
                    "UPDATE xportra.regulatory_sources "
                    "SET supersedes_source_id = NULL "
                    "WHERE supersedes_source_id = ANY(%s)",
                    (self.source_ids,),
                )
                for source_id in self.source_ids:
                    # Delete requirements linked to this source (before normalization/artifact deletes)
                    cursor.execute(
                        "DELETE FROM xportra.regulatory_requirements WHERE source_id = %s",
                        (source_id,),
                    )
                    # Delete normalization records referencing artifacts for this source
                    cursor.execute(
                        "DELETE FROM xportra.regulatory_document_normalizations WHERE artifact_id IN (SELECT id FROM xportra.regulatory_source_artifacts WHERE source_id = %s)",
                        (source_id,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.regulatory_ingestion_jobs "
                        "WHERE source_id = %s",
                        (source_id,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.regulatory_source_artifacts "
                        "WHERE source_id = %s",
                        (source_id,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.regulatory_sources WHERE id = %s",
                        (source_id,),
                    )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_review_flags "
                    "WHERE trigger_source_id = ANY(%s)",
                    (self.source_ids,),
                )

    def _b64(self, content: bytes) -> str:
        return base64.b64encode(content).decode("ascii")

    def _register_source(self, title: str, version: str, status: str = "active"):
        row = self.service.register_source(
            actor_user_id=self.actor_id,
            authority_id=AUTHORITY_ID,
            jurisdiction="EU",
            title=title,
            version=version,
            status=status,
        )
        self.source_ids.append(row["id"])
        return row

    # ---- Supersession tests ----

    def test_authorized_record_supersession(self):
        source_a = self._register_source("New Regulation", "2.0")
        source_b = self._register_source("Old Regulation", "1.0")
        result = self.service.record_supersession(
            actor_user_id=self.actor_id,
            source_id=source_a["id"],
            supersedes_source_id=source_b["id"],
            rationale="New version replaces old regulation.",
        )
        self.assertEqual(result["supersedes_source_id"], source_b["id"])
        self.assertEqual(result["source_id"], source_a["id"])
        self.assertEqual(result["status"], "active")

        # Verify superseded source is marked as superseded
        updated_source_b = self.service.get_source(source_b["id"])
        self.assertEqual(updated_source_b["status"], "superseded")
        self.assertEqual(updated_source_b["superseded_by_source_id"], source_a["id"])

    def test_unauthorized_record_supersession_denied(self):
        service = RegulatorySourceIntakeService(
            self.database,
            grant_service=_FakeGrantService(set()),
            storage_service=_FakeStorageService(self.storage),
        )
        source_a = self._register_source("New Regulation", "2.0")
        source_b = self._register_source("Old Regulation", "1.0")
        with self.assertRaises(PermissionDeniedError):
            service.record_supersession(
                actor_user_id=UUID("aaaaaa02-0000-0000-0000-000000000999"),
                source_id=source_a["id"],
                supersedes_source_id=source_b["id"],
                rationale="Unauthorized attempt.",
            )

    def test_self_supersession_denied(self):
        source_a = self._register_source("Test Regulation", "1.0")
        with self.assertRaises(ApplicationValidationError) as ctx:
            self.service.record_supersession(
                actor_user_id=self.actor_id,
                source_id=source_a["id"],
                supersedes_source_id=source_a["id"],
                rationale="Self-supersession attempt.",
            )
        self.assertIn("self-supersession", str(ctx.exception))

    def test_missing_source_denied(self):
        source_b = self._register_source("Old Regulation", "1.0")
        with self.assertRaises(ApplicationNotFoundError):
            self.service.record_supersession(
                actor_user_id=self.actor_id,
                source_id=UUID("99999999-0000-0000-0000-000000000999"),
                supersedes_source_id=source_b["id"],
                rationale="Missing source.",
            )

    def test_missing_superseded_source_denied(self):
        source_a = self._register_source("New Regulation", "2.0")
        with self.assertRaises(ApplicationNotFoundError):
            self.service.record_supersession(
                actor_user_id=self.actor_id,
                source_id=source_a["id"],
                supersedes_source_id=UUID("99999999-0000-0000-0000-000000000999"),
                rationale="Missing superseded source.",
            )

    def test_duplicate_supersession_denied(self):
        source_a = self._register_source("New Regulation", "2.0")
        source_b = self._register_source("Old Regulation", "1.0")
        self.service.record_supersession(
            actor_user_id=self.actor_id,
            source_id=source_a["id"],
            supersedes_source_id=source_b["id"],
            rationale="First supersession.",
        )
        with self.assertRaises(ApplicationValidationError) as ctx:
            self.service.record_supersession(
                actor_user_id=self.actor_id,
                source_id=source_a["id"],
                supersedes_source_id=source_b["id"],
                rationale="Duplicate supersession.",
            )
        self.assertIn("already supersedes another source", str(ctx.exception))

    def test_supersession_flags_affected_requirements(self):
        # Register two sources
        source_a = self._register_source("New Regulation", "2.0")
        source_b = self._register_source("Old Regulation", "1.0")

        # Ensure the normalization reference exists (requires a linked artifact and source)
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO xportra.regulatory_source_artifacts (id, source_id, artifact_uri, content_hash, content_length, content_type, acquisition_channel, acquired_by, acquired_at, status, source_version, created_at, updated_at) VALUES (%s, %s, 'test/artifact', 'hash', 10, 'text/plain', 'manual_upload', %s, now(), 'validated', NULL, now(), now()) ON CONFLICT DO NOTHING RETURNING id",
                    (UUID("88888888-0000-0000-0000-000000000800"), source_b["id"], UUID("aaaaaa02-0000-0000-0000-000000000001"),),
                )
                cursor.execute(
                    "INSERT INTO xportra.regulatory_document_normalizations (id, artifact_id, source_id, document_title, normalized_text, normalized_content, content_type, parser_name, status, normalized_at, created_at, updated_at) VALUES (%s, %s, %s, 'test', 'test', '{}', 'text/plain', 'v1', 'normalized', now(), now(), now()) ON CONFLICT DO NOTHING RETURNING id",
                    (UUID("77777777-0000-0000-0000-000000000700"), UUID("88888888-0000-0000-0000-000000000800"), source_b["id"],),
                )
        # Create a requirement linked to source_b
        req_repo = RegulatoryRequirementRepository(self.database)
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
                         stage_b_status, stage_b_reviewer_user_id,
                         stage_b_reviewed_at, stage_b_rationale,
                         stage_b_pilot_scope, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'extracted',
                            NULL, 'succeeded', 'v1', FALSE, NULL, NULL,
                            %s, 'verified', NULL, NULL, NULL,
                            'pending', NULL, NULL, NULL, NULL,
                            now(), now())
                    ON CONFLICT DO NOTHING
                    RETURNING id
                    """,
                    (
                        UUID("99999999-0000-0000-0000-000000000601"),
                        UUID("77777777-0000-0000-0000-000000000700"),
                        "Old requirement text.", "labeling",
                        '{"section_order": 0, "heading": null}',
                        0, None, None, source_b["id"],
                    ),
                )
                req_row = cursor.fetchone()

        result = self.service.record_supersession(
            actor_user_id=self.actor_id,
            source_id=source_a["id"],
            supersedes_source_id=source_b["id"],
            rationale="New regulation replaces old.",
        )
        self.assertEqual(result["supersedes_source_id"], source_b["id"])

        # Verify governance flag was created for the requirement
        flags = [f for f in self.service._flag_repo.get_for_source(source_b["id"]) if f.get("trigger_type") == "supersession"]
        self.assertGreaterEqual(len(flags), 1)
        self.assertEqual(flags[0]["status"], "pending_review")


if __name__ == "__main__":
    unittest.main()
