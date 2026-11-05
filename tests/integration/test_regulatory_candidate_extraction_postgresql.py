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
import json
import os
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID

from psycopg.errors import ForeignKeyViolation, RaiseException

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
    RegulatoryIngestionJobRepository,
    RegulatorySourceArtifactRepository,
    RegulatorySourceRepository,
    UserRepository,
    UserTenantMembershipRepository,
)
from xportra.persistence.tenant import TenantContext
from xportra.application.regulatory_ingestion_worker import (
    RegulatoryIngestionWorker,
)
from xportra.domain.llm import LLMGenerationConfig, LLMResponse
from xportra.infrastructure.llm import ScriptedLLMClient

ACTOR_SUBJECT = UUID("aaaaaa03-0000-0000-0000-000000000001")
AUTHORITY_ID = UUID("cccccc03-0000-0000-0000-000000000003")
SOURCE_ID = UUID("dddddd03-0000-0000-0000-000000000004")
ARTIFACT_ID = UUID("eeeeee03-0000-0000-0000-000000000005")
JOB_ID = UUID("ffffffff-0003-0000-0000-000000000006")
TENANT = UUID("99999999-0000-0000-0000-000000000099")
SCRIPTED_MODEL = "scripted-regulatory-integration-model"


def _configured_extraction_service(database, storage_service, quotes):
    requirements = [
        {
            "title": quote,
            "description": quote,
            "requirement_type": "obligation",
            "category": "obligation",
            "supporting_quote": quote,
            "page_reference": None,
            "section_reference": None,
            "product_category": None,
            "effective_date": None,
            "actor": None,
            "condition": None,
            "threshold": None,
        }
        for quote in quotes
    ]
    client = ScriptedLLMClient(responses=[
        LLMResponse(
            json.dumps({"requirements": requirements}),
            model_identifier=SCRIPTED_MODEL,
        )
    ])
    return RegulatoryCandidateExtractionService(
        database,
        storage_service=storage_service,
        llm_client=client,
        llm_configuration=LLMGenerationConfig(
            model_identifier=SCRIPTED_MODEL,
            max_output_tokens=4096,
        ),
    )

REQUIRED_TABLES = (
    "authorities",
    "regulatory_sources",
    "regulatory_source_artifacts",
    "regulatory_ingestion_jobs",
    "regulatory_document_normalizations",
    "regulatory_document_metadata",
    "regulatory_requirements",
    "regulatory_requirement_extraction_runs",
    "regulatory_requirement_extraction_run_candidates",
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
        cls._cleanup_all()

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
                cls._delete_extraction_history(cursor)
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

    @classmethod
    def _delete_extraction_history(cls, cursor):
        # Test fixture cleanup runs as the local database owner. Keep the
        # append-only triggers enabled except for this scoped cleanup.
        cursor.execute(
            "ALTER TABLE xportra.regulatory_requirement_extraction_runs "
            "DISABLE TRIGGER regulatory_requirement_extraction_runs_no_mutation"
        )
        cursor.execute(
            "ALTER TABLE xportra.regulatory_requirement_extraction_run_candidates "
            "DISABLE TRIGGER "
            "regulatory_requirement_extraction_run_candidates_resolve_once"
        )
        try:
            cursor.execute(
                "DELETE FROM xportra.regulatory_requirement_extraction_run_candidates "
                "WHERE normalized_document_id IN "
                "(SELECT id FROM xportra.regulatory_document_normalizations "
                "WHERE source_id = %s)", (SOURCE_ID,)
            )
            cursor.execute(
                "DELETE FROM xportra.regulatory_requirement_extraction_runs "
                "WHERE normalized_document_id IN "
                "(SELECT id FROM xportra.regulatory_document_normalizations "
                "WHERE source_id = %s)", (SOURCE_ID,)
            )
        finally:
            cursor.execute(
                "ALTER TABLE xportra.regulatory_requirement_extraction_runs "
                "ENABLE TRIGGER regulatory_requirement_extraction_runs_no_mutation"
            )
            cursor.execute(
                "ALTER TABLE xportra.regulatory_requirement_extraction_run_candidates "
                "ENABLE TRIGGER "
                "regulatory_requirement_extraction_run_candidates_resolve_once"
            )

    def setUp(self):
        if self.database is None:
            self.skipTest("DATABASE_URL is not configured")
        self.storage = FakeStorage()
        storage_service = FakeStorageService(self.storage)
        self.service = _configured_extraction_service(
            self.database,
            storage_service,
            (
                "Shall be labeled with origin.",
                "Shall not exceed 50 kg.",
            ),
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
                self._delete_extraction_history(cursor)
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
                    (
                        AUTHORITY_ID,
                        f"Workstream 1 Integration Authority {AUTHORITY_ID}",
                        "EU",
                    ),
                )
                self.authority_id = cursor.fetchone()["id"]

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
                        SOURCE_ID, self.authority_id, "EU", "Test Regulation",
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
                            source_version = EXCLUDED.source_version,
                            updated_at = now()
                    RETURNING *
                    """,
                    (
                        ARTIFACT_ID, SOURCE_ID, key, content_hash, len(content),
                        "text/plain", "manual_upload", str(self.actor_id),
                        "validated", "artifact-2024-v1",
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

    def _create_job(
        self, job_id, *, artifact_id=ARTIFACT_ID, attempt_number=2,
        created_at=None,
    ):
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO xportra.regulatory_ingestion_jobs
                        (id, artifact_id, source_id, status, attempt_number,
                         actor_user_id, parser_version, created_at)
                    VALUES (%s, %s, %s, 'pending', %s, %s, 'v1',
                            COALESCE(%s, now()))
                    RETURNING *
                    """,
                    (
                        job_id,
                        artifact_id,
                        SOURCE_ID,
                        attempt_number,
                        self.actor_id,
                        created_at,
                    ),
                )
                return cursor.fetchone()

    # ---- Tests ----

    def test_claim_next_skips_older_registration_placeholder(self):
        placeholder_id = UUID("ffffffff-0003-0000-0000-000000000008")
        self._create_job(
            placeholder_id,
            artifact_id=None,
            attempt_number=99,
            created_at=datetime.now(timezone.utc) - timedelta(days=1),
        )

        claimed = RegulatoryIngestionJobRepository(
            self.database
        ).claim_next()

        self.assertEqual(claimed["id"], JOB_ID)
        self.assertEqual(claimed["status"], "claimed")
        self.assertEqual(claimed["actor_user_id"], self.actor_id)
        self.assertEqual(
            RegulatoryIngestionJobRepository(self.database).get(
                placeholder_id
            )["status"],
            "pending",
        )

    def test_claim_next_selects_pending_artifact_job(self):
        claimed = RegulatoryIngestionJobRepository(
            self.database
        ).claim_next()

        self.assertEqual(claimed["id"], JOB_ID)
        self.assertEqual(claimed["status"], "claimed")
        self.assertIsNotNone(claimed["started_at"])
        self.assertEqual(claimed["current_stage"], "queued")

    def test_concurrent_claim_next_calls_claim_distinct_jobs(self):
        second_job_id = UUID("ffffffff-0003-0000-0000-000000000009")
        self._create_job(second_job_id, attempt_number=2)
        repo = RegulatoryIngestionJobRepository(self.database)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(repo.claim_next)
                for _ in range(2)
            ]
            claims = [future.result(timeout=10) for future in futures]

        claimed_ids = [claim["id"] for claim in claims]
        self.assertEqual(set(claimed_ids), {JOB_ID, second_job_id})

    def test_duplicate_claim_and_stale_owner_updates_are_rejected(self):
        repo = RegulatoryIngestionJobRepository(self.database)
        claim = repo.claim(JOB_ID)
        self.assertIsNotNone(claim)
        self.assertIsNone(repo.claim(JOB_ID))

        stale_token = claim["started_at"] - timedelta(microseconds=1)
        self.assertIsNone(repo.complete(JOB_ID, stale_token))
        self.assertIsNone(repo.fail(
            JOB_ID,
            error_details="stale",
            make_retryable=True,
            claim_started_at=stale_token,
        ))
        self.assertEqual(repo.get(JOB_ID)["status"], "claimed")

        completed = repo.complete(JOB_ID, claim["started_at"])
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["current_stage"], "completed")

    def test_retryable_job_can_be_reclaimed_and_failure_count_is_preserved(self):
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE xportra.regulatory_ingestion_jobs
                    SET status = 'retryable', retry_count = 2,
                        error_details = 'transient failure',
                        current_stage = 'failed'
                    WHERE id = %s
                    """,
                    (JOB_ID,),
                )

        repo = RegulatoryIngestionJobRepository(self.database)
        claim = repo.claim_next()

        self.assertEqual(claim["id"], JOB_ID)
        self.assertEqual(claim["status"], "claimed")
        self.assertEqual(claim["retry_count"], 2)
        self.assertIsNone(claim["error_details"])

        failed = repo.fail(
            JOB_ID,
            error_details="transient failure",
            make_retryable=True,
            claim_started_at=claim["started_at"],
        )
        self.assertEqual(failed["status"], "retryable")
        self.assertEqual(failed["retry_count"], 3)
        self.assertEqual(failed["current_stage"], "failed")

    def test_expired_claim_is_recovered_for_retry(self):
        repo = RegulatoryIngestionJobRepository(self.database)
        claim = repo.claim(JOB_ID)
        self.assertIsNotNone(claim)
        time.sleep(0.01)

        worker = RegulatoryIngestionWorker(
            self.database, extraction_service=lambda database: None
        )
        worker._actor_id = self.actor_id
        with patch(
                "xportra.application.regulatory_ingestion_worker."
                "LEASE_TIMEOUT_SECONDS", 0):
            recovered_count = worker._recover_expired_lease()

        self.assertGreaterEqual(recovered_count, 1)
        recovered = repo.get(JOB_ID)
        self.assertEqual(recovered["status"], "retryable")
        self.assertEqual(recovered["current_stage"], "queued")
        self.assertEqual(repo.claim(JOB_ID)["id"], JOB_ID)

    def test_job_extraction_history_includes_empty_successful_run(self):
        client = ScriptedLLMClient(responses=[
            LLMResponse(
                json.dumps({"requirements": []}),
                model_identifier=SCRIPTED_MODEL,
            )
        ])
        self.service = RegulatoryCandidateExtractionService(
            self.database,
            storage_service=FakeStorageService(self.storage),
            llm_client=client,
            llm_configuration=LLMGenerationConfig(
                model_identifier=SCRIPTED_MODEL,
                max_output_tokens=4096,
            ),
        )

        result = self.service.extract_candidates(
            actor_user_id=self.actor_id,
            source_id=SOURCE_ID,
            artifact_id=ARTIFACT_ID,
            job_id=JOB_ID,
        )
        history = self.service.get_job_extraction_history(JOB_ID)

        self.assertEqual(EXTRACTION_OUTCOME_SUCCEEDED, result["outcome"])
        self.assertEqual(0, result["candidate_count"])
        self.assertEqual(JOB_ID, history["job_id"])
        self.assertEqual(1, len(history["items"]))
        self.assertEqual(
            EXTRACTION_OUTCOME_SUCCEEDED, history["items"][0]["outcome"]
        )
        self.assertEqual(0, history["items"][0]["candidate_count"])
        self.assertEqual([], history["items"][0]["candidates"])

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
        self.assertEqual(result["job"]["current_stage"], "completed")
        for cand in result["candidates"]:
            self.assertEqual(cand["source_id"], SOURCE_ID)
            self.assertEqual(cand["ingestion_job_id"], JOB_ID)
            self.assertEqual(cand["extraction_outcome"], EXTRACTION_OUTCOME_SUCCEEDED)
            self.assertEqual(cand["parser_version"], "v1")
            self.assertFalse(cand["manual_entry"])
            detailed = self.service.get_candidate_with_provenance(cand["id"])
            self.assertEqual(detailed["source_id"], SOURCE_ID)
            self.assertEqual(detailed["artifact_id"], ARTIFACT_ID)
            self.assertEqual(
                detailed["artifact_source_version"], "artifact-2024-v1"
            )
            self.assertEqual(
                detailed["normalized_document_id"],
                cand["normalized_document_id"],
            )
            self.assertEqual(detailed["artifact_content_hash"],
                             hashlib.sha256(
                                 self.storage.objects[
                                     detailed["artifact_uri"]
                                 ]
                             ).hexdigest())
            self.assertEqual(len(detailed["extraction_history"]), 1)
            history = detailed["extraction_history"][0]
            self.assertEqual(history["ingestion_job_id"], JOB_ID)
            self.assertEqual(history["artifact_id"], ARTIFACT_ID)
            self.assertEqual(history["source_id"], SOURCE_ID)
            self.assertEqual(
                history["artifact_source_version"], "artifact-2024-v1"
            )
            self.assertEqual(
                history["artifact_content_hash"],
                detailed["artifact_content_hash"],
            )
            self.assertIn(SCRIPTED_MODEL, history["model_identifiers"])
            self.assertEqual(history["extraction_method"],
                             "llm_semantic_chunked")
            self.assertTrue(history["is_origin"])
            self.assertEqual(history["resolution_status"], "persisted")
            self.assertEqual(
                history["evidence_snapshot"]["source_location"][
                    "supporting_quote"
                ],
                cand["source_location"]["supporting_quote"],
            )

    def test_reprocessing_preserves_changed_evidence_in_run_history(self):
        first_quote = "Shall be labeled with origin."
        second_quote = "Shall not exceed 50 kg."
        rejected = {
            "title": "Unsupported quote",
            "description": "Unsupported quote",
            "requirement_type": "obligation",
            "category": "obligation",
            "supporting_quote": "This unsupported quote does not occur.",
            "page_reference": None,
            "section_reference": None,
            "product_category": None,
            "effective_date": None,
            "actor": None,
            "condition": None,
            "threshold": None,
        }

        def candidate_payload(quote):
            return {
                "title": quote,
                "description": quote,
                "requirement_type": "obligation",
                "category": "obligation",
                "supporting_quote": quote,
                "page_reference": None,
                "section_reference": None,
                "product_category": None,
                "effective_date": None,
                "actor": None,
                "condition": None,
                "threshold": None,
            }

        client = ScriptedLLMClient(responses=[
            LLMResponse(
                json.dumps({"requirements": [
                    candidate_payload(first_quote),
                    rejected,
                ]}),
                model_identifier=SCRIPTED_MODEL,
            ),
            LLMResponse(
                json.dumps({"requirements": [
                    candidate_payload(second_quote),
                ]}),
                model_identifier=SCRIPTED_MODEL,
            ),
        ])
        self.service = RegulatoryCandidateExtractionService(
            self.database,
            storage_service=FakeStorageService(self.storage),
            llm_client=client,
            llm_configuration=LLMGenerationConfig(
                model_identifier=SCRIPTED_MODEL,
                max_output_tokens=4096,
            ),
        )

        first = self.service.extract_candidates(
            actor_user_id=self.actor_id,
            source_id=SOURCE_ID,
            artifact_id=ARTIFACT_ID,
            job_id=JOB_ID,
        )
        self.assertEqual(first["outcome"], "partial")
        original_candidate = first["candidates"][0]
        second = self.service.extract_candidates(
            actor_user_id=self.actor_id,
            source_id=SOURCE_ID,
            artifact_id=ARTIFACT_ID,
            job_id=JOB_ID,
        )

        self.assertEqual(second["outcome"], EXTRACTION_OUTCOME_SUCCEEDED)
        self.assertEqual(
            original_candidate["requirement_text"], first_quote
        )
        self.assertEqual(
            {candidate["requirement_text"] for candidate in second["candidates"]},
            {first_quote, second_quote},
        )
        second_candidate = next(
            candidate
            for candidate in second["candidates"]
            if candidate["requirement_text"] == second_quote
        )
        history = self.service.get_candidate_with_provenance(
            second_candidate["id"]
        )["extraction_history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(
            history[0]["evidence_snapshot"]["source_location"][
                "supporting_quote"
            ],
            second_quote,
        )
        self.assertEqual(history[0]["outcome"], EXTRACTION_OUTCOME_SUCCEEDED)

    def test_artifact_normalization_and_extraction_history_are_immutable(self):
        result = self.service.extract_candidates(
            actor_user_id=self.actor_id,
            source_id=SOURCE_ID,
            artifact_id=ARTIFACT_ID,
            job_id=JOB_ID,
        )
        candidate = result["candidates"][0]
        history = self.service.get_candidate_with_provenance(
            candidate["id"]
        )["extraction_history"][0]

        rejected_updates = (
            (
                "UPDATE xportra.regulatory_source_artifacts "
                "SET source_version = 'rewritten' WHERE id = %s",
                (ARTIFACT_ID,),
            ),
            (
                "UPDATE xportra.regulatory_document_normalizations "
                "SET normalized_text = 'rewritten' WHERE id = %s",
                (candidate["normalized_document_id"],),
            ),
            (
                "UPDATE xportra.regulatory_requirement_extraction_runs "
                "SET outcome = 'failed' WHERE id = %s",
                (history["extraction_run_id"],),
            ),
            (
                "UPDATE xportra.regulatory_requirement_extraction_run_candidates "
                "SET evidence_snapshot = '{}'::jsonb "
                "WHERE extraction_run_id = %s AND candidate_index = %s",
                (history["extraction_run_id"], history["candidate_index"]),
            ),
        )
        for statement, parameters in rejected_updates:
            with self.subTest(statement=statement):
                with self.assertRaises(RaiseException):
                    with self.database.transaction() as connection:
                        with connection.cursor() as cursor:
                            cursor.execute(statement, parameters)

    def test_extraction_run_rejects_mismatched_artifact_version(self):
        result = self.service.extract_candidates(
            actor_user_id=self.actor_id,
            source_id=SOURCE_ID,
            artifact_id=ARTIFACT_ID,
            job_id=JOB_ID,
        )
        history = self.service.get_candidate_with_provenance(
            result["candidates"][0]["id"]
        )["extraction_history"][0]

        with self.assertRaises(ForeignKeyViolation):
            with self.database.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO
                            xportra.regulatory_requirement_extraction_runs
                            (normalized_document_id, artifact_id, source_id,
                             ingestion_job_id, artifact_content_hash,
                             artifact_source_version, normalized_text_sha256,
                             parser_version, extraction_method,
                             extraction_version, prompt_version,
                             configured_model_identifier, model_identifiers,
                             provider_names, outcome, failed_chunks,
                             rejected_candidate_count, started_at, completed_at)
                        SELECT normalized_document_id, artifact_id, source_id,
                               ingestion_job_id, artifact_content_hash,
                               'mismatched-version', normalized_text_sha256,
                               parser_version, extraction_method,
                               extraction_version, prompt_version,
                               configured_model_identifier, model_identifiers,
                               provider_names, outcome, failed_chunks,
                               rejected_candidate_count, started_at, completed_at
                        FROM xportra.regulatory_requirement_extraction_runs
                        WHERE id = %s
                        """,
                        (history["extraction_run_id"],),
                    )

    def test_run_candidate_foreign_key_rejects_wrong_candidate(self):
        result = self.service.extract_candidates(
            actor_user_id=self.actor_id,
            source_id=SOURCE_ID,
            artifact_id=ARTIFACT_ID,
            job_id=JOB_ID,
        )
        candidate = result["candidates"][0]
        history = self.service.get_candidate_with_provenance(
            candidate["id"]
        )["extraction_history"][0]
        invalid_candidate_id = UUID(
            "00000000-0000-0000-0000-000000000001"
        )

        with self.assertRaises(ForeignKeyViolation):
            with self.database.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO
                            xportra.regulatory_requirement_extraction_run_candidates
                            (extraction_run_id, normalized_document_id,
                             candidate_index, evidence_snapshot)
                        VALUES (%s, %s, 1000, '{}'::jsonb)
                        """,
                        (
                            history["extraction_run_id"],
                            candidate["normalized_document_id"],
                        ),
                    )
                    cursor.execute(
                        """
                        UPDATE
                            xportra.regulatory_requirement_extraction_run_candidates
                        SET candidate_id = %s, resolution_status = 'persisted',
                            is_origin = FALSE
                        WHERE extraction_run_id = %s
                          AND candidate_index = 1000
                        """,
                        (
                            invalid_candidate_id,
                            history["extraction_run_id"],
                        ),
                    )

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
