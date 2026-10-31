"""PostgreSQL integration tests for regulatory governance (Task 7).

Tests review-flag persistence against isolated local `xportra_test`.
"""
from __future__ import annotations

import os
import unittest
from uuid import UUID

from xportra.application.errors import ApplicationValidationError
from xportra.application.regulatory_governance_service import (
    RegulatoryGovernanceService,
    TRIGGER_TYPE_SUPERSESSION,
)
from xportra.persistence.database import Database, DatabaseSettings
from xportra.persistence.repositories import (
    RegulatoryReviewFlagRepository,
    UserRepository,
    UserTenantMembershipRepository,
)
from xportra.persistence.tenant import TenantContext

    SOURCE_ID = UUID("dddddd04-0000-0000-0000-000000000004")
    AUTHORITY_ID = UUID("cccccc04-0000-0000-0000-000000000003")
ACTOR = UUID("aaaaaa07-0000-0000-0000-000000000001")

REQUIRED_TABLES = ("regulatory_review_flags",)


class RegulatoryGovernanceIntegrationTests(unittest.TestCase):
    database: Database | None = None

    @classmethod
    def setUpClass(cls):
        cls.database = Database(
            DatabaseSettings(dsn="postgresql://postgres:postgres@localhost:5432/xportra_test")
        )
        with cls.database.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user")
                row = cur.fetchone()
                assert row["current_database"] == "xportra_test", (
                    f"Expected xportra_test, got {row['current_database']}"
                )

    def setUp(self):
        self.service = RegulatoryGovernanceService(self.database)
        self.flag_repo = RegulatoryReviewFlagRepository(self.database)
        # Ensure actor exists to satisfy FK.
        # Insert actor with exact internal UUID to satisfy FK.
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO xportra.users (id, display_name, email, status, supabase_uid, created_at, updated_at) VALUES (%s, %s, %s, %s, %s, now(), now()) ON CONFLICT (id) DO NOTHING",
                        (ACTOR, "Governance Actor", "governance-actor@example.invalid", "active", ACTOR),
                )
        # Provide tenant context for membership (optional for FK only).
        membership_repo = UserTenantMembershipRepository(self.database)
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO xportra.tenants (id, legal_name, slug, status) VALUES (%s, %s, %s, 'active') ON CONFLICT (id) DO NOTHING",
                    (UUID("99999999-0000-0000-0000-000000000099"), "Test Tenant", "test-tenant"),
                )
                # The flag service validates the trigger source; on a
                # freshly migrated database no other fixture has seeded
                # the shared source yet, so seed authority and source
                # here (idempotent).
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
                authority_id = cursor.fetchone()["id"]
                cursor.execute(
                    """
                    INSERT INTO xportra.regulatory_sources
                        (id, authority_id, jurisdiction, title, version, status,
                         effective_date, publication_date, source_url,
                         retrieval_timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (id) DO UPDATE
                        SET status = EXCLUDED.status, updated_at = now()
                    """,
                    (
                        SOURCE_ID, authority_id, "EU", "Test Regulation",
                        "1.0", "active", "2024-01-01", "2024-01-01",
                        "https://example.com/regulation",
                    ),
                )

    def test_supersession_flag_persists_and_retrieves(self):
        result = self.service.flag_review_required(
            actor_user_id=ACTOR,
            trigger_type=TRIGGER_TYPE_SUPERSESSION,
            trigger_source_id=SOURCE_ID,
            rationale="Supersession recorded.",
        )
        self.assertEqual(result["trigger_type"], TRIGGER_TYPE_SUPERSESSION)
        flags = self.flag_repo.get_for_source(SOURCE_ID)
        self.assertGreaterEqual(len(flags), 1)
        self.assertTrue(any(f["status"] == "pending_review" for f in flags))

    def test_stale_flag_fails_closed_for_unknown_currentness(self):
        # Freshness is not declared current; unknown/stale triggers review.
        result = self.service.flag_review_required(
            actor_user_id=ACTOR,
            trigger_type="stale",
            trigger_source_id=SOURCE_ID,
            rationale="No verified currentness evidence.",
        )
        self.assertEqual(result["status"], "pending_review")

    def test_review_completion_updates_state(self):
        created = self.service.flag_review_required(
            actor_user_id=ACTOR,
            trigger_type=TRIGGER_TYPE_SUPERSESSION,
            trigger_source_id=SOURCE_ID,
            rationale="Requires re-review.",
        )
        completed = self.service.complete_review(
            actor_user_id=ACTOR,
            flag_id=created["id"],
            rationale="Re-reviewed.",
        )
        self.assertEqual(completed["status"], "review_completed")

    @classmethod
    def tearDownClass(cls):
        # The flags raised above intentionally stay pending for the
        # assertions in this class, but later integration classes reuse
        # the same source (stage A/B, assessment). Pending governance
        # flags block re-review by design, so complete them here to keep
        # the shared, persistent test database unblocked.
        with cls.database.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE xportra.regulatory_review_flags
                    SET status = 'review_completed', updated_at = now()
                    WHERE trigger_source_id = %s AND status = 'pending_review'
                    """,
                    (SOURCE_ID,),
                )


if __name__ == "__main__":
    unittest.main()
