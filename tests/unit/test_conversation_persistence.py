"""Workstream 6 — Conversation persistence unit tests.

Tests the ConversationApplicationService persistence layer using
in-memory fakes. Covers conversation creation, retrieval with
messages, listing, message persistence on handle_message, and
tenant isolation.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.api.auth import MemberContext
from xportra.api.dependencies import get_member_context
from xportra.application.context import ApplicationContext
from xportra.application.conversations import (
    ConversationApplicationService,
    DEFAULT_CONVERSATION_CONTEXT_CHARACTERS,
)
from xportra.application.errors import ApplicationValidationError
from xportra.domain.conversation import (
    CONVERSATION_MODE_KNOWLEDGE,
    CONVERSATION_MODE_SHIPMENT_AWARE,
    INTENT_ANSWER_REGULATORY_QUESTION,
    RESPONSE_STATUS_GROUNDED,
    RESPONSE_STATUS_REFUSED_UNKNOWN,
    AssistantResponse,
    CitationReference,
    UNKNOWN_REFUSAL_TEXT,
)
from xportra.persistence.tenant import TenantContext

TENANT_A = TenantContext(UUID("11111111-1111-1111-1111-111111111111"))
TENANT_B = TenantContext(UUID("22222222-2222-2222-2222-222222222222"))

CONVERSATION_ID = UUID("aaaaaaaa-0000-4000-8000-000000000101")
CONVERSATION_ID_B = UUID("aaaaaaaa-0000-4000-8000-000000000102")


class FakeDatabase:
    """Minimal database fake supporting transaction() context manager."""

    class _Connection:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def transaction(self):
        return self._Connection()


class FakeConversationRepo:
    """In-memory conversation repository fake."""

    def __init__(self, database=None) -> None:
        self._database = database or FakeDatabase()
        self._rows: dict[UUID, dict] = {}
        self.touched: list[UUID] = []

    def create_in_transaction(
        self, connection, tenant: TenantContext, conversation_id: UUID, mode: str
    ) -> dict:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        self._rows[conversation_id] = {
            "id": conversation_id,
            "tenant_id": tenant.tenant_id,
            "mode": mode,
            "created_at": now,
            "updated_at": now,
        }
        return dict(self._rows[conversation_id])

    def get(self, tenant: TenantContext, conversation_id: UUID) -> dict | None:
        row = self._rows.get(conversation_id)
        if row is None or row["tenant_id"] != tenant.tenant_id:
            return None
        return dict(row)

    def list_for_tenant(self, tenant: TenantContext) -> list[dict]:
        return [
            dict(r) for r in self._rows.values()
            if r["tenant_id"] == tenant.tenant_id
        ]

    def touch(self, connection, tenant: TenantContext, conversation_id: UUID) -> dict | None:
        self.touched.append(conversation_id)
        row = self.get(tenant, conversation_id)
        return row


class FakeMessageRepo:
    """In-memory message repository fake."""

    def __init__(self) -> None:
        self._messages: dict[UUID, list[dict]] = {}

    def create_in_transaction(
        self, connection, conversation_id: UUID, role: str, content: str, *,
        intent=None, status=None, citations=None, shipment_references=None,
        refusal_reason=None,
    ) -> dict:
        from datetime import datetime, timezone
        import uuid
        message_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        msg = {
            "id": message_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "intent": intent,
            "status": status,
            "citations": citations or [],
            "shipment_references": shipment_references or [],
            "refusal_reason": refusal_reason,
            "created_at": now,
        }
        self._messages.setdefault(conversation_id, []).append(msg)
        return msg

    def list_for_conversation(self, conversation_id: UUID) -> list[dict]:
        return list(self._messages.get(conversation_id, []))

    def get_by_id(self, message_id: UUID) -> dict | None:
        for msgs in self._messages.values():
            for m in msgs:
                if m["id"] == message_id:
                    return m
        return None


class FakeDatabase:
    """Minimal database fake supporting transaction() context manager."""

    class _Connection:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def cursor(self):
            return self
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    def transaction(self):
        return self._Connection()


class ConversationPersistenceTest(unittest.TestCase):
    """Conversation persistence with fakes."""

    def setUp(self) -> None:
        self.fake_db = FakeDatabase()
        self.conv_repo = FakeConversationRepo(database=self.fake_db)
        self.msg_repo = FakeMessageRepo()
        self.service = ConversationApplicationService(
            conversation_repo=self.conv_repo,
            message_repo=self.msg_repo,
            database=self.fake_db,
        )
        self.ctx_a = ApplicationContext(
            actor_id=None, tenant=TENANT_A, role="owner")
        self.ctx_b = ApplicationContext(
            actor_id=None, tenant=TENANT_B, role="owner")

    def test_create_conversation(self):
        result = self.service.create_conversation(
            self.ctx_a, conversation_id=CONVERSATION_ID, mode=CONVERSATION_MODE_KNOWLEDGE)
        self.assertEqual(result["id"], str(CONVERSATION_ID))
        self.assertEqual(result["tenant_id"], str(TENANT_A.tenant_id))
        self.assertEqual(result["mode"], CONVERSATION_MODE_KNOWLEDGE)
        row = self.conv_repo.get(TENANT_A, CONVERSATION_ID)
        self.assertIsNotNone(row)

    def test_create_conversation_tenant_isolation(self):
        self.service.create_conversation(
            self.ctx_a, conversation_id=CONVERSATION_ID, mode=CONVERSATION_MODE_KNOWLEDGE)
        # Tenant B cannot see Tenant A's conversation.
        row = self.conv_repo.get(TENANT_B, CONVERSATION_ID)
        self.assertIsNone(row)
        listed = self.conv_repo.list_for_tenant(TENANT_B)
        self.assertEqual(len(listed), 0)

    def test_get_conversation_with_messages_empty(self):
        self.service.create_conversation(
            self.ctx_a, conversation_id=CONVERSATION_ID, mode=CONVERSATION_MODE_KNOWLEDGE)
        detail = self.service.get_conversation_with_messages(
            self.ctx_a, conversation_id=CONVERSATION_ID)
        self.assertIsNotNone(detail)
        self.assertEqual(detail["id"], str(CONVERSATION_ID))
        self.assertEqual(detail["messages"], [])

    def test_get_conversation_unknown_returns_none(self):
        detail = self.service.get_conversation_with_messages(
            self.ctx_a, conversation_id=UUID("aaaaaaaa-0000-4000-8000-000000000999"))
        self.assertIsNone(detail)

    def test_get_conversation_cross_tenant_returns_none(self):
        self.service.create_conversation(
            self.ctx_a, conversation_id=CONVERSATION_ID, mode=CONVERSATION_MODE_KNOWLEDGE)
        detail = self.service.get_conversation_with_messages(
            self.ctx_b, conversation_id=CONVERSATION_ID)
        self.assertIsNone(detail)

    def test_list_conversations_tenant_only(self):
        self.service.create_conversation(
            self.ctx_a, conversation_id=CONVERSATION_ID, mode=CONVERSATION_MODE_KNOWLEDGE)
        self.service.create_conversation(
            self.ctx_b, conversation_id=CONVERSATION_ID_B, mode=CONVERSATION_MODE_SHIPMENT_AWARE)
        listed_a = self.service.list_conversations(self.ctx_a)
        listed_b = self.service.list_conversations(self.ctx_b)
        self.assertEqual(len(listed_a), 1)
        self.assertEqual(len(listed_b), 1)
        self.assertEqual(listed_a[0]["id"], str(CONVERSATION_ID))
        self.assertEqual(listed_b[0]["id"], str(CONVERSATION_ID_B))

    def test_conversation_http_lifecycle_is_tenant_scoped(self):
        active_tenant = TENANT_A
        app = create_app(services=SimpleNamespace(
            database=self.fake_db,
            conversation_repository=self.conv_repo,
            conversation_message_repository=self.msg_repo,
        ))
        app.dependency_overrides[get_member_context] = lambda: MemberContext(
            active_tenant, "owner")

        with TestClient(app) as client:
            created = client.post(
                "/conversations",
                headers={"X-Development-Tenant-ID": str(TENANT_A.tenant_id)},
                json={"mode": CONVERSATION_MODE_KNOWLEDGE},
            )
            self.assertEqual(created.status_code, 200, created.text)
            conversation_id = created.json()["id"]

            listed = client.get(
                "/conversations",
                headers={"X-Development-Tenant-ID": str(TENANT_A.tenant_id)},
            )
            self.assertEqual(listed.status_code, 200, listed.text)
            self.assertEqual(
                [item["id"] for item in listed.json()["conversations"]],
                [conversation_id],
            )

            detail = client.get(
                f"/conversations/{conversation_id}",
                headers={"X-Development-Tenant-ID": str(TENANT_A.tenant_id)},
            )
            self.assertEqual(detail.status_code, 200, detail.text)
            self.assertEqual(detail.json()["id"], conversation_id)
            self.assertEqual(detail.json()["messages"], [])

            active_tenant = TENANT_B
            hidden = client.get(
                f"/conversations/{conversation_id}",
                headers={"X-Development-Tenant-ID": str(TENANT_B.tenant_id)},
            )
            self.assertEqual(hidden.status_code, 404, hidden.text)

    def test_handle_message_persists_both_sides(self):
        class FakeRag:
            def query(self, information_need, **kwargs):
                evidence = type("Evidence", (), {
                    "chunk_id": UUID("aaaaaaaa-0000-4000-8000-000000000201"),
                    "document_id": UUID("aaaaaaaa-0000-4000-8000-000000000202"),
                    "chunk_index": 0,
                    "source_id": "authority/reg",
                    "source_type": "regulation",
                    "source_location": "https://example.test/reg",
                    "document_version": "2024.1",
                    "content_fingerprint": "fp1",
                    "tenant_id": TENANT_A.tenant_id,
                })()
                citation = type("Citation", (), {
                    "label": "[E1]",
                    "rank_position": 1,
                    "selected": type("Selected", (), {
                        "rank_position": 1,
                        "ranked": type("Ranked", (), {"evidence": evidence})(),
                    })(),
                })()
                validated = type("Validated", (), {
                    "is_empty": False,
                    "status": "valid",
                    "answer_text": "The requirement applies [E1].",
                    "validated_citations": (citation,),
                })()
                return validated

        service = ConversationApplicationService(
            rag=FakeRag(),
            conversation_repo=self.conv_repo,
            message_repo=self.msg_repo,
            database=self.fake_db,
        )
        answer = service.handle_message(
            self.ctx_a,
            conversation_id=CONVERSATION_ID,
            mode=CONVERSATION_MODE_KNOWLEDGE,
            intent=INTENT_ANSWER_REGULATORY_QUESTION,
            user_text="Does this regulation apply?",
            information_need="Does this regulation apply?",
        )
        self.assertEqual(answer.status, RESPONSE_STATUS_GROUNDED)
        # Both messages persisted.
        msgs = self.msg_repo.list_for_conversation(CONVERSATION_ID)
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[0]["content"], "Does this regulation apply?")
        self.assertEqual(msgs[1]["role"], "assistant")
        self.assertEqual(msgs[1]["content"], "The requirement applies [E1].")
        self.assertEqual(len(msgs[1]["citations"]), 1)

    def test_handle_message_without_repos_remains_stateless(self):
        """No repos: handle_message works but stores nothing."""
        service = ConversationApplicationService()  # no repos
        # Should not raise; just returns an answer.
        # But without RAG, knowledge intent raises InfrastructureError.
        with self.assertRaises(Exception):
            service.handle_message(
                self.ctx_a,
                conversation_id=CONVERSATION_ID,
                mode=CONVERSATION_MODE_KNOWLEDGE,
                intent=INTENT_ANSWER_REGULATORY_QUESTION,
                user_text="hello",
                information_need="hello",
            )

    def test_create_conversation_without_repos_raises(self):
        service = ConversationApplicationService()  # no repos
        with self.assertRaises(ApplicationValidationError):
            service.create_conversation(
                self.ctx_a, conversation_id=CONVERSATION_ID, mode=CONVERSATION_MODE_KNOWLEDGE)

    def test_get_conversation_without_repos_raises(self):
        service = ConversationApplicationService()  # no repos
        with self.assertRaises(ApplicationValidationError):
            service.get_conversation_with_messages(
                self.ctx_a, conversation_id=CONVERSATION_ID)

    def test_list_conversations_without_repos_raises(self):
        service = ConversationApplicationService()  # no repos
        with self.assertRaises(ApplicationValidationError):
            service.list_conversations(self.ctx_a)


if __name__ == "__main__":
    unittest.main()
