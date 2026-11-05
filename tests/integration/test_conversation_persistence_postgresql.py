"""Workstream 6 — Conversation persistence direct database tests.

Tests ConversationRepository and ConversationMessageRepository directly
against the isolated local ``xportra_test`` database, bypassing FastAPI
to avoid TestClient/lifespan issues.

Requires ``DATABASE_URL`` pointing at local ``xportra_test``; skipped
otherwise. Never uses production or shared database credentials.
"""

from __future__ import annotations

import os
import unittest
from uuid import UUID, uuid4

from xportra.persistence.database import Database, DatabaseSettings
from xportra.persistence.repositories import (
    ConversationMessageRepository,
    ConversationRepository,
    TenantRepository,
    UserRepository,
    UserTenantMembershipRepository,
)
from xportra.persistence.tenant import TenantContext

USER_A_ID = UUID("66666666-0000-4000-8000-000000000611")
USER_B_ID = UUID("66666666-0000-4000-8000-000000000612")


def _require_database() -> Database:
    if not os.environ.get("DATABASE_URL", "").strip():
        raise unittest.SkipTest("DATABASE_URL is not configured")
    return Database(DatabaseSettings.from_environment())


def _ensure_tenant_and_user(database: Database, slug: str, user_id: UUID):
    """Idempotently ensure tenant, user, and membership exist.

    Returns the actual tenant_id (may be auto-generated).
    """
    tr = TenantRepository(database)
    row = tr.get_by_slug(slug)
    if row is None:
        row = tr.create(legal_name=f"Tenant {slug}", slug=slug)
    tenant_id = row["id"]

    ur = UserRepository(database)
    if ur.get(user_id) is None:
        ur.create(display_name=f"User {user_id}", email=None, status="active")
    mtr = UserTenantMembershipRepository(database)
    try:
        mtr.add(TenantContext(tenant_id), user_id, "owner", "active")
    except Exception:
        pass
    return tenant_id


class ConversationRepositoryDirectTest(unittest.TestCase):
    """Direct repository tests against xportra_test."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.database = _require_database()
        cls.tenant_a_id = _ensure_tenant_and_user(
            cls.database, "ws6-test-tenant-a", USER_A_ID)
        cls.tenant_b_id = _ensure_tenant_and_user(
            cls.database, "ws6-test-tenant-b", USER_B_ID)

    def _new_conv_id(self) -> UUID:
        return uuid4()

    def test_create_and_get_conversation(self):
        repo = ConversationRepository(self.database)
        tenant = TenantContext(self.tenant_a_id)
        conv_id = self._new_conv_id()

        with self.database.transaction() as conn:
            row = repo.create_in_transaction(
                conn, tenant, conv_id, "knowledge")

        self.assertIsNotNone(row)
        self.assertEqual(row["id"], conv_id)
        self.assertEqual(row["tenant_id"], self.tenant_a_id)
        self.assertEqual(row["mode"], "knowledge")

        fetched = repo.get(tenant, conv_id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["id"], conv_id)

    def test_cross_tenant_get_returns_none(self):
        repo = ConversationRepository(self.database)
        tenant_a = TenantContext(self.tenant_a_id)
        tenant_b = TenantContext(self.tenant_b_id)
        conv_id = self._new_conv_id()

        with self.database.transaction() as conn:
            repo.create_in_transaction(
                conn, tenant_a, conv_id, "knowledge")

        fetched = repo.get(tenant_b, conv_id)
        self.assertIsNone(fetched)

    def test_list_for_tenant_isolation(self):
        repo = ConversationRepository(self.database)
        tenant_a = TenantContext(self.tenant_a_id)
        tenant_b = TenantContext(self.tenant_b_id)
        conv_a = self._new_conv_id()
        conv_b = self._new_conv_id()

        with self.database.transaction() as conn:
            repo.create_in_transaction(conn, tenant_a, conv_a, "knowledge")
            repo.create_in_transaction(conn, tenant_b, conv_b, "shipment_aware")

        listed_a = repo.list_for_tenant(tenant_a)
        listed_b = repo.list_for_tenant(tenant_b)
        self.assertTrue(any(c["id"] == conv_a for c in listed_a))
        self.assertTrue(any(c["id"] == conv_b for c in listed_b))
        self.assertFalse(any(c["id"] == conv_b for c in listed_a))
        self.assertFalse(any(c["id"] == conv_a for c in listed_b))

    def test_touch_updates_updated_at(self):
        repo = ConversationRepository(self.database)
        tenant = TenantContext(self.tenant_a_id)
        conv_id = self._new_conv_id()

        with self.database.transaction() as conn:
            repo.create_in_transaction(conn, tenant, conv_id, "knowledge")

        # Re-fetch in a fresh connection (transaction committed).
        before = repo.get(tenant, conv_id)["updated_at"]

        with self.database.transaction() as conn:
            repo.touch(conn, tenant, conv_id)

        after = repo.get(tenant, conv_id)["updated_at"]
        self.assertGreater(after, before)

    def test_message_persistence(self):
        msg_repo = ConversationMessageRepository(self.database)
        # First create a conversation.
        conv_repo = ConversationRepository(self.database)
        conv_id = self._new_conv_id()
        with self.database.transaction() as conn:
            conv_repo.create_in_transaction(
                conn, TenantContext(self.tenant_a_id), conv_id, "knowledge")

        with self.database.transaction() as conn:
            user_row = msg_repo.create_in_transaction(
                conn, conv_id, "user", "What are the requirements?",
                intent="answer_regulatory_question")
            assistant_row = msg_repo.create_in_transaction(
                conn, conv_id, "assistant",
                "The requirement applies [E1].",
                intent="answer_regulatory_question",
                status="grounded",
                citations=[{"label": "[E1]", "rank_position": 1,
                            "source_id": "authority/reg"}],
                shipment_references=[{"kind": "workflow", "id": str(USER_A_ID)}],
                refusal_reason=None)

        self.assertIsNotNone(user_row["id"])
        self.assertEqual(user_row["role"], "user")
        self.assertEqual(user_row["content"], "What are the requirements?")
        self.assertIsNotNone(assistant_row["id"])
        self.assertEqual(assistant_row["role"], "assistant")
        self.assertEqual(assistant_row["status"], "grounded")
        self.assertEqual(len(assistant_row["citations"]), 1)

        messages = msg_repo.list_for_conversation(conv_id)
        self.assertEqual(len(messages), 2)
        roles = [m["role"] for m in messages]
        self.assertIn("user", roles)
        self.assertIn("assistant", roles)

    def test_database_identity_is_xportra_test(self):
        with self.database.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database() AS db_name")
                row = cur.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["db_name"], "xportra_test")


if __name__ == "__main__":
    unittest.main()
