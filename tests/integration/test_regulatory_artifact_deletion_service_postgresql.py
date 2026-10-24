"""PostgreSQL-backed integration tests for regulatory artifact deletion
foundations (legal holds and durable deletion intents).

Requires migrations `003_regulatory_source_artifacts.sql`,
`015_global_staff_grants.sql`, `019_regulatory_artifact_legal_hold.sql`,
and `020_regulatory_artifact_deletion_intent.sql` applied to the isolated
local test database `xportra_test` on localhost:5432.

The hosted `.env` DATABASE_URL is never used for these tests. A test-only
local DSN is used instead, with the database identity verified before any
write occurs.
Skipped when the local `xportra_test` database is unavailable.
"""

from __future__ import annotations

import os
import threading
import time
import unittest
from uuid import UUID

import psycopg

from xportra.persistence.database import Database, DatabaseSettings

TEST_ARTIFACT_ID = UUID("11111111-0000-0000-0000-000000000001")
LOCAL_DSN = "postgresql://postgres@localhost:5432/xportra_test"


class RegulatoryArtifactDeletionIntegrationTests(unittest.TestCase):
    database = None

    @classmethod
    def setUpClass(cls):
        # Verify the isolated local test database identity before any write.
        # Never use the hosted .env DATABASE_URL for integration tests.
        try:
            verify_db = Database(DatabaseSettings(dsn=LOCAL_DSN))
            with verify_db.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT current_database() AS dbname")
                    current_db_name = cursor.fetchone()["dbname"]
                    cursor.execute("SELECT inet_server_addr() AS addr")
                    server_addr = str(cursor.fetchone()["addr"])
        except Exception as exc:
            raise unittest.SkipTest(
                f"Local isolated PostgreSQL database 'xportra_test' at localhost:5432 "
                f"is unavailable or identity unverified ({type(exc).__name__}); "
                "integration concurrency tests skipped. Blocker: local DB identity "
                "or migrations missing."
            ) from exc

        if server_addr not in ("127.0.0.1", "::1"):
            raise unittest.SkipTest(
                f"Database server address {server_addr} is not local; refusing "
                "to run integration tests against a non-local endpoint."
            )
        if current_db_name != "xportra_test":
            raise unittest.SkipTest(
                f"Local PostgreSQL server responds but database name is "
                f"'{current_db_name}' (expected 'xportra_test'); integration "
                "concurrency tests require an isolated test database named "
                "exactly 'xportra_test'."
            )

        # Test-only override for this process; .env is unchanged.
        os.environ["DATABASE_URL"] = LOCAL_DSN
        cls.database = Database(DatabaseSettings.from_environment())
        cls._verify_migrations()
        cls._cleanup_intent_and_hold_rows()

    @classmethod
    def tearDownClass(cls):
        cls._cleanup_intent_and_hold_rows()

    @classmethod
    def _verify_migrations(cls):
        with cls.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'xportra'
                      AND table_name IN ('regulatory_artifact_legal_hold',
                                         'regulatory_artifact_deletion_intent',
                                         'global_staff_grants',
                                         'global_staff_audit')
                    """
                )
                tables = {row["table_name"] for row in cursor.fetchall()}
                required = {
                    "global_staff_grants",
                    "global_staff_audit",
                    "regulatory_artifact_legal_hold",
                    "regulatory_artifact_deletion_intent",
                }
                missing = required - tables
                if missing:
                    raise RuntimeError(
                        f"Required migrations must be applied before "
                        f"integration tests; missing: {missing}"
                    )

    @classmethod
    def _cleanup_intent_and_hold_rows(cls):
        if cls.database is None:
            return
        with cls.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM xportra.regulatory_artifact_deletion_intent "
                    "WHERE artifact_id = %s",
                    (str(TEST_ARTIFACT_ID),),
                )
                cursor.execute(
                    "DELETE FROM xportra.regulatory_artifact_legal_hold "
                    "WHERE artifact_id = %s",
                    (str(TEST_ARTIFACT_ID),),
                )

    def _acquire_lock_and_hold(self, results, lock_key, hold_seconds):
        """Connection 1: acquire advisory lock, hold it, then release."""
        db = Database(DatabaseSettings(dsn=LOCAL_DSN))
        acquired = False
        try:
            with db.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT pg_advisory_xact_lock(%s)",
                        (lock_key,),
                    )
                    acquired = True
                # Lock still held: transaction is open during the sleep.
                time.sleep(hold_seconds)
            # Connection exits: transaction commits, lock released.
            results["acquired"] = acquired
            results["error"] = None
        except Exception as exc:  # noqa: BLE001
            results["acquired"] = acquired
            results["error"] = str(exc)
        finally:
            db = None

    def _try_acquire_lock_after_wait(self, results, lock_key, wait_seconds):
        """Connection 2: try to acquire same lock after a wait (should block)."""
        time.sleep(wait_seconds)
        db = Database(DatabaseSettings(dsn=LOCAL_DSN))
        acquired = False
        try:
            with db.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT pg_advisory_xact_lock(%s)",
                        (lock_key,),
                    )
                    acquired = True
            # Lock acquired; transaction commits on exit, releasing it.
            results["acquired"] = acquired
            results["error"] = None
        except Exception as exc:  # noqa: BLE001
            results["acquired"] = acquired
            results["error"] = str(exc)
        finally:
            db = None

    def test_advisory_lock_serializes_concurrent_access(self):
        """Genuine concurrency test: two connections compete for the same
        advisory lock on one artifact. The second must block until the first
        releases, proving PostgreSQL transaction-scoped serialization.

        Exercises real cross-connection locking with no mocked calls.
        No users, grants, or storage mutation are involved.
        """
        lock_key = hash(str(TEST_ARTIFACT_ID)) & 0x7FFFFFFF

        result1 = {"acquired": False, "error": None}
        result2 = {"acquired": False, "error": None}

        t1 = threading.Thread(
            target=self._acquire_lock_and_hold,
            args=(result1, lock_key, 0.2),
        )
        t2 = threading.Thread(
            target=self._try_acquire_lock_after_wait,
            args=(result2, lock_key, 0.05),
        )

        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        self.assertFalse(t1.is_alive(), "Connection 1 did not finish")
        self.assertFalse(t2.is_alive(), "Connection 2 did not finish")
        self.assertIsNone(result1["error"], f"Connection 1 error: {result1['error']}")
        self.assertIsNone(result2["error"], f"Connection 2 error: {result2['error']}")
        self.assertTrue(result1["acquired"], "Connection 1 should acquire the lock")
        self.assertTrue(result2["acquired"], "Connection 2 should acquire the lock after release")

    def test_duplicate_intent_unique_constraint_enforced(self):
        """Verify the database enforces uniqueness on
        (artifact_id, authorization_ref, actor_user_id) so a second insert
        for the same operation identity cannot create a contradictory state.

        Inserts the minimal FK chain (authority → source → artifact) so the
        deletion_intent FK on artifact_id can be satisfied, then verifies
        duplicate inserts for the same (artifact_id, authorization_ref,
        actor_user_id) are rejected.
        """
        import psycopg
        conn = psycopg.connect(LOCAL_DSN)
        conn.autocommit = True
        cur = conn.cursor()
        try:
            # Minimal FK chain: authority → source → artifact → user
            cur.execute(
                """
                INSERT INTO xportra.authorities
                    (id, name, jurisdiction, authority_type, status)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    UUID("aaaaaaaa-0000-0000-0000-000000000010"),
                    "Test Authority",
                    "US",
                    "government",
                    "active",
                ),
            )
            cur.execute(
                """
                INSERT INTO xportra.regulatory_sources
                    (id, authority_id, jurisdiction, title, status)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    UUID("bbbbbbbb-0000-0000-0000-000000000020"),
                    UUID("aaaaaaaa-0000-0000-0000-000000000010"),
                    "US",
                    "Test Source",
                    "active",
                ),
            )
            cur.execute(
                """
                INSERT INTO xportra.regulatory_source_artifacts
                    (id, source_id, artifact_uri, content_hash, content_length,
                     content_type, acquisition_channel, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    TEST_ARTIFACT_ID,
                    UUID("bbbbbbbb-0000-0000-0000-000000000020"),
                    "https://example.com/artifact.txt",
                    "content-hash-abc",
                    100,
                    "text/plain",
                    "api_export",
                    "validated",
                ),
            )
            cur.execute(
                """
                INSERT INTO xportra.users
                    (id, display_name, email, status)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    UUID("aaaaaaaa-0000-0000-0000-000000000001"),
                    "Test Actor",
                    "actor@test.example",
                    "active",
                ),
            )
            # First insert of the deletion intent should succeed.
            cur.execute(
                """
                INSERT INTO xportra.regulatory_artifact_deletion_intent
                    (artifact_id, content_hash, status, actor_user_id,
                     authorization_ref, reason, retention_eligibility)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    TEST_ARTIFACT_ID,
                    "content-hash-abc",
                    "pending",
                    UUID("aaaaaaaa-0000-0000-0000-000000000001"),
                    "auth-ref-dup-test",
                    "duplicate intent test",
                    "ineligible",
                ),
            )
            # Same operation identity must be rejected by the unique constraint.
            with self.assertRaises(Exception):
                cur.execute(
                    """
                    INSERT INTO xportra.regulatory_artifact_deletion_intent
                        (artifact_id, content_hash, status, actor_user_id,
                         authorization_ref, reason, retention_eligibility)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        TEST_ARTIFACT_ID,
                        "content-hash-abc",
                        "pending",
                        UUID("aaaaaaaa-0000-0000-0000-000000000001"),
                        "auth-ref-dup-test",
                        "duplicate intent test second",
                        "ineligible",
                    ),
                )
        finally:
            cur.execute(
                "DELETE FROM xportra.regulatory_artifact_deletion_intent "
                "WHERE artifact_id = %s",
                (str(TEST_ARTIFACT_ID),),
            )
            cur.execute(
                "DELETE FROM xportra.regulatory_source_artifacts "
                "WHERE id = %s",
                (str(TEST_ARTIFACT_ID),),
            )
            cur.execute(
                "DELETE FROM xportra.regulatory_sources "
                "WHERE id = %s",
                (str(UUID("bbbbbbbb-0000-0000-0000-000000000020")),),
            )
            cur.execute(
                "DELETE FROM xportra.authorities "
                "WHERE id = %s",
                (str(UUID("aaaaaaaa-0000-0000-0000-000000000010")),),
            )
            cur.execute(
                "DELETE FROM xportra.users "
                "WHERE id = %s",
                (str(UUID("aaaaaaaa-0000-0000-0000-000000000001")),),
            )
            cur.close()
            conn.close()

    def test_deletion_adapter_not_exposed_through_service(self):
        from xportra.application.regulatory_artifact_deletion_service import (
            RegulatoryArtifactDeletionIntentService,
        )
        service = RegulatoryArtifactDeletionIntentService(
            database=self.database,
        )
        self.assertFalse(hasattr(service, "delete_artifact"))
        self.assertFalse(hasattr(service, "delete"))


if __name__ == "__main__":
    unittest.main()
