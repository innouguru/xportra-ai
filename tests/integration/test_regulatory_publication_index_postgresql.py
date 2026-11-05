"""PostgreSQL integration tests for publication-index outbox lifecycle."""

from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
from uuid import uuid4

from xportra.persistence.database import Database, DatabaseSettings
from xportra.persistence.regulatory_publication_index import (
    RegulatoryPublicationIndexJobRepository,
)


class RegulatoryPublicationIndexPostgreSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database_url = os.environ.get("DATABASE_URL", "").strip()
        if not database_url:
            raise unittest.SkipTest("DATABASE_URL is not configured")
        parsed = urlparse(database_url)
        if (
            parsed.path.lstrip("/") != "xportra_test"
            or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
        ):
            raise unittest.SkipTest(
                "publication-index integration tests require local "
                "xportra_test"
            )
        cls.database = Database(DatabaseSettings.from_environment())
        with cls.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT current_database(), current_user,
                           inet_server_addr(), current_setting('server_version')
                    """
                )
                identity = cursor.fetchone()
        if (
            identity["current_database"] != "xportra_test"
            or str(identity["inet_server_addr"]) not in {
                "127.0.0.1", "::1"
            }
        ):
            raise unittest.SkipTest(
                "connection did not resolve to local xportra_test"
            )
        with cls.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT to_regclass("
                    "'xportra.regulatory_publication_index_jobs')"
                )
                if cursor.fetchone()["to_regclass"] is None:
                    raise unittest.SkipTest(
                        "migration 036 is not applied to xportra_test"
                    )

    def setUp(self):
        self.authority_id = uuid4()
        self.source_id = uuid4()
        self.artifact_id = uuid4()
        self.document_id = uuid4()
        self.requirement_id = uuid4()
        self.jobs = RegulatoryPublicationIndexJobRepository(
            self.database)
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO xportra.authorities
                        (id, name, jurisdiction, authority_type, status)
                    VALUES (%s, %s, 'NG', 'government', 'active')
                    """,
                    (self.authority_id, f"index-test-{self.authority_id}"),
                )
                cursor.execute(
                    """
                    INSERT INTO xportra.regulatory_sources
                        (id, authority_id, jurisdiction, title, version,
                         status)
                    VALUES (%s, %s, 'NG', 'Index test source', 'test-v1',
                            'active')
                    """,
                    (self.source_id, self.authority_id),
                )
                cursor.execute(
                    """
                    INSERT INTO xportra.regulatory_source_artifacts
                        (id, source_id, artifact_uri, content_hash,
                         content_length, content_type, acquisition_channel,
                         status, source_version)
                    VALUES (%s, %s, 'test://publication-index', 'test-hash',
                            1, 'text/plain', 'manual_upload', 'validated',
                            'test-v1')
                    """,
                    (self.artifact_id, self.source_id),
                )
                cursor.execute(
                    """
                    INSERT INTO xportra.regulatory_document_normalizations
                        (id, artifact_id, source_id, document_title,
                         normalized_text, normalized_content, content_type,
                         parser_name, status)
                    VALUES (%s, %s, %s, 'Index test source',
                            'Requirement text', '{"text":"Requirement text"}',
                            'text/plain', 'test-parser', 'normalized')
                    """,
                    (self.document_id, self.artifact_id, self.source_id),
                )
                cursor.execute(
                    """
                    INSERT INTO xportra.regulatory_requirements
                        (id, normalized_document_id, requirement_text,
                         requirement_type, source_location, position, status,
                         source_id, parser_version, extraction_outcome,
                         stage_a_status, stage_b_status)
                    VALUES (%s, %s, 'The exporter must retain the record.',
                            'obligation', '{"page":1}', 0, 'extracted',
                            %s, 'test-parser-v1', 'succeeded', 'verified',
                            'approved')
                    """,
                    (
                        self.requirement_id,
                        self.document_id,
                        self.source_id,
                    ),
                )

    def tearDown(self):
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM xportra.regulatory_review_flags
                    WHERE requirement_id = %s OR trigger_source_id = %s
                    """,
                    (self.requirement_id, self.source_id),
                )
                cursor.execute(
                    """
                    DELETE FROM xportra.regulatory_publication_index_jobs
                    WHERE requirement_id = %s
                    """,
                    (self.requirement_id,),
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_requirements WHERE id = %s",
                    (self.requirement_id,),
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_document_normalizations "
                    "WHERE id = %s",
                    (self.document_id,),
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_source_artifacts "
                    "WHERE id = %s",
                    (self.artifact_id,),
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_sources WHERE id = %s",
                    (self.source_id,),
                )
                cursor.execute(
                    "DELETE FROM xportra.authorities WHERE id = %s",
                    (self.authority_id,),
                )

    def _publish(self):
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE xportra.regulatory_requirements
                    SET status = 'published', published_at = now()
                    WHERE id = %s
                    """,
                    (self.requirement_id,),
                )

    def _job(self):
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT requirement_id, desired_state, status,
                           attempt_count, indexed_chunk_ids
                    FROM xportra.regulatory_publication_index_jobs
                    WHERE requirement_id = %s
                    """,
                    (self.requirement_id,),
                )
                return cursor.fetchone()

    def test_publication_atomically_schedules_claimable_index_work(self):
        self.assertIsNone(self._job())

        self._publish()

        job = self._job()
        self.assertEqual(job["desired_state"], "published")
        self.assertEqual(job["status"], "pending")
        claimed = self.jobs.claim_next()
        self.assertEqual(claimed["requirement_id"], self.requirement_id)
        self.assertEqual(claimed["desired_state"], "published")
        self.assertEqual(self.jobs.claim_next(), None)

    def test_concurrent_claims_do_not_duplicate_a_job(self):
        self._publish()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(
                lambda _unused: self.jobs.claim_next(),
                range(2),
            ))

        claimed = [result for result in results if result is not None]
        self.assertEqual(len(claimed), 1)
        self.assertEqual(claimed[0]["requirement_id"], self.requirement_id)

    def test_indexed_requirement_metadata_change_schedules_reindex(self):
        self._publish()
        claimed = self.jobs.claim_next()
        self.jobs.complete_claim(
            self.requirement_id,
            claimed["claim_token"],
            indexed_chunk_ids=[uuid4()],
            publication_fingerprint="previous-fingerprint",
        )
        previous = self.jobs.currently_eligible_requirement_ids(
            {self.requirement_id})[self.requirement_id]

        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE xportra.regulatory_requirements
                    SET source_location = '{"page":2}',
                        parser_version = 'test-parser-v2'
                    WHERE id = %s
                    """,
                    (self.requirement_id,),
                )

        job = self._job()
        current = self.jobs.currently_eligible_requirement_ids(
            {self.requirement_id})[self.requirement_id]
        self.assertEqual(job["desired_state"], "published")
        self.assertEqual(job["status"], "pending")
        self.assertEqual(len(job["indexed_chunk_ids"]), 1)
        self.assertNotEqual(current, previous)

    def test_expired_claim_is_recovered_without_changing_job_identity(self):
        self._publish()
        first = self.jobs.claim_next()
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE xportra.regulatory_publication_index_jobs
                    SET lease_expires_at = now() - interval '1 second'
                    WHERE requirement_id = %s
                    """,
                    (self.requirement_id,),
                )

        recovered = self.jobs.claim_next()

        self.assertEqual(recovered["requirement_id"], self.requirement_id)
        self.assertNotEqual(recovered["claim_token"], first["claim_token"])
        self.assertEqual(recovered["attempt_count"], 2)

    def test_rejection_withdrawal_and_pending_flags_schedule_removal(self):
        self._publish()
        claimed = self.jobs.claim_next()
        self.jobs.complete_claim(
            self.requirement_id,
            claimed["claim_token"],
            indexed_chunk_ids=[uuid4()],
            publication_fingerprint="fingerprint",
        )

        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE xportra.regulatory_requirements
                    SET status = 'rejected'
                    WHERE id = %s
                    """,
                    (self.requirement_id,),
                )
        job = self._job()
        self.assertEqual(job["desired_state"], "removed")
        self.assertEqual(job["status"], "pending")
        self.assertEqual(len(job["indexed_chunk_ids"]), 1)

    def test_source_withdrawal_and_pending_flag_are_rechecked(self):
        self._publish()
        current = self.jobs.currently_eligible_requirement_ids(
            {self.requirement_id})
        self.assertEqual(set(current), {self.requirement_id})
        self.assertEqual(len(current[self.requirement_id]), 64)
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO xportra.regulatory_review_flags
                        (requirement_id, trigger_source_id, trigger_type,
                         status, rationale)
                    VALUES (%s, %s, 'withdrawal', 'pending_review',
                            'integration test')
                    """,
                    (self.requirement_id, self.source_id),
                )
        self.assertEqual(
            self.jobs.currently_eligible_requirement_ids(
                {self.requirement_id}),
            {},
        )
        self.assertEqual(self._job()["desired_state"], "removed")

        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE xportra.regulatory_review_flags
                    SET status = 'dismissed'
                    WHERE requirement_id = %s
                    """,
                    (self.requirement_id,),
                )
                cursor.execute(
                    """
                    UPDATE xportra.regulatory_sources
                    SET status = 'withdrawn'
                    WHERE id = %s
                    """,
                    (self.source_id,),
                )
        self.assertEqual(
            self.jobs.currently_eligible_requirement_ids(
                {self.requirement_id}),
            {},
        )
        self.assertEqual(self._job()["desired_state"], "removed")


if __name__ == "__main__":
    unittest.main()
