"""Phase 10.2 — Conversational backend foundation tests.

Covers the frozen domain contracts, the stateless read-only
application use case, and the single HTTP endpoint:
identity separation, tenant isolation, conversation
ownership (actor/tenant from server-resolved context),
context binding + revalidation, mode separation, message
lifecycle, grounding/citation contract, authorization, API
error mapping, cross-tenant rejection, malformed input, and
the no-autonomous-mutation property.

Knowledge answers use a hand-built validated-answer double
(validated citations only — no retrieval, no LLM, no
provider). No Phase 1–10.1 test is modified.
"""

import ast
import dataclasses
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
)
from xportra.application.errors import (
    ApplicationValidationError,
    InfrastructureError,
    TenantMismatchError,
)
from xportra.domain.conversation import (
    CONVERSATION_MODE_KNOWLEDGE,
    CONVERSATION_MODE_SHIPMENT_AWARE,
    INTENT_ANSWER_REGULATORY_QUESTION,
    INTENT_EXPLAIN_EVIDENCE_GAPS,
    INTENT_EXPLAIN_FINDING,
    INTENT_EXPLAIN_REQUIREMENT_STATE,
    INTENT_SUMMARIZE_SHIPMENT_STATE,
    RESPONSE_STATUS_GROUNDED,
    RESPONSE_STATUS_PARTIAL,
    RESPONSE_STATUS_REFUSED_UNKNOWN,
    AssistantResponse,
    CitationReference,
    ConversationContext,
    ConversationIdentity,
    ShipmentCitation,
    UserMessage,
)
from xportra.persistence.tenant import TenantContext

TENANT_A = TenantContext(UUID("11111111-1111-1111-1111-111111111111"))
TENANT_B = TenantContext(UUID("22222222-2222-2222-2222-222222222222"))
HEADER_A = {"X-Development-Tenant-ID": str(TENANT_A.tenant_id)}
HEADER_B = {"X-Development-Tenant-ID": str(TENANT_B.tenant_id)}

CONVERSATION_ID = UUID("aaaaaaaa-0000-4000-8000-000000000001")
WORKFLOW_ID = UUID("aaaaaaaa-0000-4000-8000-000000000002")
CASE_ID = UUID("aaaaaaaa-0000-4000-8000-000000000003")
SHIPMENT_ID = UUID("aaaaaaaa-0000-4000-8000-000000000004")
REQUIREMENT_ID = UUID("aaaaaaaa-0000-4000-8000-000000000005")
EVIDENCE_ID = UUID("aaaaaaaa-0000-4000-8000-000000000006")
CHUNK_ID = UUID("aaaaaaaa-0000-4000-8000-000000000007")
DOCUMENT_ID = UUID("aaaaaaaa-0000-4000-8000-000000000008")


def workflow_record(tenant=TENANT_A, state="created",
                    workflow_id=WORKFLOW_ID):
    return {
        "id": str(workflow_id),
        "tenant_id": str(tenant.tenant_id),
        "case_id": str(CASE_ID),
        "shipment_id": str(SHIPMENT_ID),
        "state": state,
        "rounds": [],
        "supplied_evidence_ids": [],
        "open_requirements": [str(REQUIREMENT_ID)],
    }


def app_context(tenant=TENANT_A, role="owner"):
    return ApplicationContext(
        actor_id=None, tenant=tenant, role=role)


def validated_answer_double(text="Filing is required [E1].",
                            status="valid"):
    evidence = SimpleNamespace(
        chunk_id=CHUNK_ID,
        document_id=DOCUMENT_ID,
        chunk_index=0,
        source_id="authority/guide",
        source_type="guidance",
        source_location="https://example.test/guide",
        document_version="2024.1",
        content_fingerprint="fp-0",
    )
    citation = SimpleNamespace(
        label="[E1]",
        rank_position=1,
        selected=SimpleNamespace(
            ranked=SimpleNamespace(evidence=evidence)),
    )
    return SimpleNamespace(
        answer_text=text,
        status=status,
        is_empty=False,
        validated_citations=[citation],
    )


class FakeRAG:
    def __init__(self, validated=None, error=None):
        self.validated = validated
        self.error = error
        self.seen = []

    def query(self, information_need, **kwargs):
        self.seen.append((information_need, kwargs))
        if self.error is not None:
            raise self.error
        return self.validated


class DomainContractTests(unittest.TestCase):
    def test_conversation_identity_is_not_compliance_identity(self):
        identity = ConversationIdentity(CONVERSATION_ID)
        self.assertNotEqual(identity.conversation_id, WORKFLOW_ID)
        self.assertNotEqual(identity.conversation_id, CASE_ID)
        self.assertNotEqual(identity.conversation_id, REQUIREMENT_ID)
        with self.assertRaises(TypeError):
            ConversationIdentity("not-a-uuid")

    def test_contracts_are_frozen(self):
        identity = ConversationIdentity(CONVERSATION_ID)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            identity.conversation_id = WORKFLOW_ID

    def test_knowledge_context_forbids_shipment_context(self):
        with self.assertRaises(ValueError):
            ConversationContext(
                conversation_id=CONVERSATION_ID,
                mode=CONVERSATION_MODE_KNOWLEDGE,
                workflow_id=WORKFLOW_ID)
        with self.assertRaises(ValueError):
            ConversationContext(
                conversation_id=CONVERSATION_ID,
                mode=CONVERSATION_MODE_KNOWLEDGE,
                shipment_id=SHIPMENT_ID)
        context = ConversationContext(
            conversation_id=CONVERSATION_ID,
            mode=CONVERSATION_MODE_KNOWLEDGE)
        self.assertFalse(context.is_shipment_aware)

    def test_shipment_context_requires_workflow(self):
        with self.assertRaises(TypeError):
            ConversationContext(
                conversation_id=CONVERSATION_ID,
                mode=CONVERSATION_MODE_SHIPMENT_AWARE)
        context = ConversationContext(
            conversation_id=CONVERSATION_ID,
            mode=CONVERSATION_MODE_SHIPMENT_AWARE,
            workflow_id=WORKFLOW_ID)
        self.assertTrue(context.is_shipment_aware)

    def test_unknown_mode_rejected(self):
        with self.assertRaises(ValueError):
            ConversationContext(
                conversation_id=CONVERSATION_ID, mode="generic_chat")

    def test_user_message_validation(self):
        message = UserMessage(
            conversation_id=CONVERSATION_ID,
            content="Why is this open?",
            intent=INTENT_EXPLAIN_FINDING)
        self.assertEqual(message.role, "user")
        with self.assertRaises(ValueError):
            UserMessage(
                conversation_id=CONVERSATION_ID, content="   ",
                intent=INTENT_EXPLAIN_FINDING)
        with self.assertRaises(ValueError):
            UserMessage(
                conversation_id=CONVERSATION_ID, content="x" * 2001,
                intent=INTENT_EXPLAIN_FINDING)
        with self.assertRaises(ValueError):
            UserMessage(
                conversation_id=CONVERSATION_ID, content="hi",
                intent="run_analysis")
        with self.assertRaises(ValueError):
            UserMessage(
                conversation_id=CONVERSATION_ID, content="hi",
                intent=INTENT_EXPLAIN_FINDING, role="assistant")

    def test_response_grounding_rules(self):
        ref = ShipmentCitation(kind="workflow", identifier=WORKFLOW_ID)
        grounded = AssistantResponse(
            conversation_id=CONVERSATION_ID,
            mode=CONVERSATION_MODE_SHIPMENT_AWARE,
            intent=INTENT_SUMMARIZE_SHIPMENT_STATE,
            status=RESPONSE_STATUS_GROUNDED,
            summary_text="state quoted",
            shipment_references=(ref,))
        self.assertEqual(grounded.status, RESPONSE_STATUS_GROUNDED)
        # Grounded/partial with no references is ungrounded.
        with self.assertRaises(ValueError):
            AssistantResponse(
                conversation_id=CONVERSATION_ID,
                mode=CONVERSATION_MODE_KNOWLEDGE,
                intent=INTENT_ANSWER_REGULATORY_QUESTION,
                status=RESPONSE_STATUS_GROUNDED,
                summary_text="unsupported claim")
        # Refused answers carry a reason and no references as fact.
        with self.assertRaises(ValueError):
            AssistantResponse(
                conversation_id=CONVERSATION_ID,
                mode=CONVERSATION_MODE_KNOWLEDGE,
                intent=INTENT_ANSWER_REGULATORY_QUESTION,
                status=RESPONSE_STATUS_REFUSED_UNKNOWN,
                summary_text="unknown")
        with self.assertRaises(ValueError):
            AssistantResponse(
                conversation_id=CONVERSATION_ID,
                mode=CONVERSATION_MODE_KNOWLEDGE,
                intent=INTENT_ANSWER_REGULATORY_QUESTION,
                status=RESPONSE_STATUS_REFUSED_UNKNOWN,
                summary_text="unknown",
                refusal_reason="no source",
                shipment_references=(ref,))
        refused = AssistantResponse(
            conversation_id=CONVERSATION_ID,
            mode=CONVERSATION_MODE_KNOWLEDGE,
            intent=INTENT_ANSWER_REGULATORY_QUESTION,
            status=RESPONSE_STATUS_REFUSED_UNKNOWN,
            summary_text="unknown",
            refusal_reason="no source")
        self.assertEqual(refused.status, RESPONSE_STATUS_REFUSED_UNKNOWN)

    def test_citation_carries_no_content_or_scores(self):
        citation = CitationReference(
            label="[E1]", rank_position=1, chunk_id=CHUNK_ID,
            document_id=DOCUMENT_ID, chunk_index=0,
            source_id="authority/guide", source_type="guidance",
            content_fingerprint="fp-0")
        self.assertFalse(hasattr(citation, "content"))
        self.assertFalse(hasattr(citation, "score"))


class ApplicationBoundaryTests(unittest.TestCase):
    def test_shipment_summary_is_grounded_in_workflow(self):
        service = ConversationApplicationService()
        answer = service.handle_message(
            app_context(),
            conversation_id=CONVERSATION_ID,
            mode=CONVERSATION_MODE_SHIPMENT_AWARE,
            intent=INTENT_SUMMARIZE_SHIPMENT_STATE,
            user_text="Summarize this shipment.",
            workflow_record=workflow_record())
        self.assertEqual(answer.status, RESPONSE_STATUS_GROUNDED)
        self.assertIn(str(WORKFLOW_ID), answer.summary_text)
        self.assertIn("'created'", answer.summary_text)
        self.assertEqual(answer.shipment_references[0].identifier,
                         WORKFLOW_ID)
        self.assertEqual(answer.citations, ())

    def test_evidence_gaps_quote_open_requirements(self):
        service = ConversationApplicationService()
        answer = service.handle_message(
            app_context(),
            conversation_id=CONVERSATION_ID,
            mode=CONVERSATION_MODE_SHIPMENT_AWARE,
            intent=INTENT_EXPLAIN_EVIDENCE_GAPS,
            user_text="What am I missing?",
            workflow_record=workflow_record())
        self.assertEqual(answer.status, RESPONSE_STATUS_GROUNDED)
        self.assertIn(str(REQUIREMENT_ID), answer.summary_text)
        # Missing stays missing: no compliance verdict is produced.
        self.assertNotIn("non-compliant", answer.summary_text)
        self.assertNotIn("non_compliant", answer.summary_text)

    def test_requirement_and_finding_answers_are_partial_not_verdicts(self):
        service = ConversationApplicationService()
        for intent in (INTENT_EXPLAIN_REQUIREMENT_STATE,
                       INTENT_EXPLAIN_FINDING):
            answer = service.handle_message(
                app_context(),
                conversation_id=CONVERSATION_ID,
                mode=CONVERSATION_MODE_SHIPMENT_AWARE,
                intent=intent,
                user_text="Why is this open?",
                workflow_record=workflow_record(),
                requirement_id=REQUIREMENT_ID)
            self.assertEqual(answer.status, RESPONSE_STATUS_PARTIAL)
            self.assertIn(str(REQUIREMENT_ID), answer.summary_text)
            self.assertNotIn("satisfied", answer.summary_text)
            self.assertNotIn("not satisfied", answer.summary_text)

    def test_cross_tenant_workflow_rejected(self):
        service = ConversationApplicationService()
        with self.assertRaises(TenantMismatchError):
            service.handle_message(
                app_context(tenant=TENANT_B),
                conversation_id=CONVERSATION_ID,
                mode=CONVERSATION_MODE_SHIPMENT_AWARE,
                intent=INTENT_SUMMARIZE_SHIPMENT_STATE,
                user_text="Summarize.",
                workflow_record=workflow_record(tenant=TENANT_A))

    def test_mode_context_mismatch_rejected(self):
        service = ConversationApplicationService()
        with self.assertRaises(ApplicationValidationError):
            service.handle_message(
                app_context(),
                conversation_id=CONVERSATION_ID,
                mode=CONVERSATION_MODE_KNOWLEDGE,
                intent=INTENT_ANSWER_REGULATORY_QUESTION,
                user_text="What is required?",
                workflow_record=workflow_record())
        with self.assertRaises(ApplicationValidationError):
            service.handle_message(
                app_context(),
                conversation_id=CONVERSATION_ID,
                mode=CONVERSATION_MODE_SHIPMENT_AWARE,
                intent=INTENT_SUMMARIZE_SHIPMENT_STATE,
                user_text="Summarize.")

    def test_shipment_intent_in_knowledge_mode_rejected(self):
        service = ConversationApplicationService()
        with self.assertRaises(ApplicationValidationError):
            service.handle_message(
                app_context(),
                conversation_id=CONVERSATION_ID,
                mode=CONVERSATION_MODE_KNOWLEDGE,
                intent=INTENT_EXPLAIN_EVIDENCE_GAPS,
                user_text="What am I missing?")

    def test_unknown_mode_and_intent_rejected(self):
        service = ConversationApplicationService()
        with self.assertRaises(ApplicationValidationError):
            service.handle_message(
                app_context(), conversation_id=CONVERSATION_ID,
                mode="generic_chat", intent=INTENT_SUMMARIZE_SHIPMENT_STATE,
                user_text="hi", workflow_record=workflow_record())
        with self.assertRaises(ApplicationValidationError):
            service.handle_message(
                app_context(), conversation_id=CONVERSATION_ID,
                mode=CONVERSATION_MODE_KNOWLEDGE,
                intent="finalize_shipment", user_text="hi")

    def test_terminal_workflow_remains_readable(self):
        service = ConversationApplicationService()
        answer = service.handle_message(
            app_context(),
            conversation_id=CONVERSATION_ID,
            mode=CONVERSATION_MODE_SHIPMENT_AWARE,
            intent=INTENT_SUMMARIZE_SHIPMENT_STATE,
            user_text="Summarize.",
            workflow_record=workflow_record(
                state="assessment_package_ready"))
        self.assertEqual(answer.status, RESPONSE_STATUS_GROUNDED)
        self.assertIn("read-only", answer.summary_text)

    def test_resumption_revalidates_without_merging(self):
        service = ConversationApplicationService()
        other_workflow = UUID("bbbbbbbb-0000-4000-8000-000000000002")
        first = service.handle_message(
            app_context(),
            conversation_id=CONVERSATION_ID,
            mode=CONVERSATION_MODE_SHIPMENT_AWARE,
            intent=INTENT_SUMMARIZE_SHIPMENT_STATE,
            user_text="Summarize.",
            workflow_record=workflow_record())
        second = service.handle_message(
            app_context(),
            conversation_id=CONVERSATION_ID,
            mode=CONVERSATION_MODE_SHIPMENT_AWARE,
            intent=INTENT_SUMMARIZE_SHIPMENT_STATE,
            user_text="Summarize.",
            workflow_record=workflow_record(
                workflow_id=other_workflow))
        self.assertIn(str(WORKFLOW_ID), first.summary_text)
        self.assertIn(str(other_workflow), second.summary_text)
        self.assertNotIn(str(other_workflow), first.summary_text)

    def test_knowledge_answer_carries_validated_citations(self):
        rag = FakeRAG(validated_answer_double())
        service = ConversationApplicationService(rag=rag)
        answer = service.handle_message(
            app_context(),
            conversation_id=CONVERSATION_ID,
            mode=CONVERSATION_MODE_KNOWLEDGE,
            intent=INTENT_ANSWER_REGULATORY_QUESTION,
            user_text="What is required?",
            information_need="filing obligation")
        self.assertEqual(answer.status, RESPONSE_STATUS_GROUNDED)
        self.assertEqual(len(answer.citations), 1)
        self.assertEqual(answer.citations[0].chunk_id, CHUNK_ID)
        self.assertEqual(answer.shipment_references, ())
        # Tenant identity travels server-side, never from the client.
        self.assertEqual(rag.seen[0][1]["tenant_id"], TENANT_A)

    def test_empty_retrieval_is_refused_not_fabricated(self):
        rag = FakeRAG(SimpleNamespace(is_empty=True))
        service = ConversationApplicationService(rag=rag)
        answer = service.handle_message(
            app_context(),
            conversation_id=CONVERSATION_ID,
            mode=CONVERSATION_MODE_KNOWLEDGE,
            intent=INTENT_ANSWER_REGULATORY_QUESTION,
            user_text="What is required?",
            information_need="filing obligation")
        self.assertEqual(answer.status, RESPONSE_STATUS_REFUSED_UNKNOWN)
        self.assertIsNotNone(answer.refusal_reason)
        self.assertEqual(answer.citations, ())
        self.assertEqual(answer.shipment_references, ())

    def test_knowledge_needs_information_need(self):
        rag = FakeRAG(validated_answer_double())
        service = ConversationApplicationService(rag=rag)
        with self.assertRaises(ApplicationValidationError):
            service.handle_message(
                app_context(),
                conversation_id=CONVERSATION_ID,
                mode=CONVERSATION_MODE_KNOWLEDGE,
                intent=INTENT_ANSWER_REGULATORY_QUESTION,
                user_text="What is required?")

    def test_unwired_rag_fails_closed(self):
        service = ConversationApplicationService(rag=None)
        with self.assertRaises(InfrastructureError):
            service.handle_message(
                app_context(),
                conversation_id=CONVERSATION_ID,
                mode=CONVERSATION_MODE_KNOWLEDGE,
                intent=INTENT_ANSWER_REGULATORY_QUESTION,
                user_text="What is required?",
                information_need="filing obligation")

    def test_retrieval_failure_propagates_unchanged(self):
        from xportra.domain.errors import VectorStoreError
        rag = FakeRAG(error=VectorStoreError(
            "retrieval", RuntimeError("boom")))
        service = ConversationApplicationService(rag=rag)
        with self.assertRaises(VectorStoreError):
            service.handle_message(
                app_context(),
                conversation_id=CONVERSATION_ID,
                mode=CONVERSATION_MODE_KNOWLEDGE,
                intent=INTENT_ANSWER_REGULATORY_QUESTION,
                user_text="What is required?",
                information_need="filing obligation")

    def test_shipment_mode_regulatory_answer_combines_contexts(self):
        rag = FakeRAG(validated_answer_double())
        service = ConversationApplicationService(rag=rag)
        answer = service.handle_message(
            app_context(),
            conversation_id=CONVERSATION_ID,
            mode=CONVERSATION_MODE_SHIPMENT_AWARE,
            intent=INTENT_ANSWER_REGULATORY_QUESTION,
            user_text="What does the regulation say?",
            workflow_record=workflow_record(),
            information_need="filing obligation")
        self.assertEqual(answer.status, RESPONSE_STATUS_GROUNDED)
        self.assertEqual(answer.shipment_references[0].identifier,
                         WORKFLOW_ID)
        self.assertEqual(len(answer.citations), 1)

    def test_handle_message_does_not_mutate_inputs(self):
        service = ConversationApplicationService()
        record = workflow_record()
        snapshot = dict(record)
        service.handle_message(
            app_context(),
            conversation_id=CONVERSATION_ID,
            mode=CONVERSATION_MODE_SHIPMENT_AWARE,
            intent=INTENT_SUMMARIZE_SHIPMENT_STATE,
            user_text="Summarize.",
            workflow_record=record)
        self.assertEqual(record, snapshot)

    def test_no_mutating_capability_in_boundary(self):
        import xportra.application.conversations as module

        source = open(module.__file__).read()
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported.update(
                    alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                imported.update(
                    alias.name.split(".")[0] for alias in node.names)
        forbidden = {
            "WorkflowApplicationService",
            "AnalysisApplicationService",
            "EvidenceApplicationService",
            "AssessmentApplicationService",
            "ComplianceResultStore",
        }
        self.assertTrue(forbidden.isdisjoint(imported))
        # Capability check over code identifiers (names, attributes,
        # definitions) — documentation prose may name the
        # operations it refuses to provide, but no such
        # capability may exist as code.
        identifiers = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                identifiers.add(node.id)
            elif isinstance(node, ast.Attribute):
                identifiers.add(node.attr)
            elif isinstance(node, (ast.FunctionDef,
                                   ast.AsyncFunctionDef,
                                   ast.ClassDef)):
                identifiers.add(node.name)
        for token in ("finalize", "record_with_requirements",
                      "supply_evidence", "run_analysis",
                      "tool_call", "execute_action"):
            self.assertNotIn(token, identifiers)


def client_with(rag=None):
    return TestClient(
        create_app(services=SimpleNamespace(rag=rag)))


def message_body(**overrides):
    body = {
        "conversation_id": str(CONVERSATION_ID),
        "mode": "shipment_aware",
        "intent": "summarize_shipment_state",
        "user_text": "Summarize this shipment.",
        "workflow": workflow_record(),
    }
    body.update(overrides)
    return body


class ConversationAPITests(unittest.TestCase):
    def test_unauthenticated_rejected(self):
        with client_with() as client:
            response = client.post(
                "/conversations/messages", json=message_body())
        self.assertEqual(response.status_code, 401)

    def test_member_may_ask_read_only_questions(self):
        app = create_app(services=SimpleNamespace(rag=None))
        app.dependency_overrides[get_member_context] = (
            lambda: MemberContext(TENANT_A, "member"))
        with TestClient(app) as client:
            response = client.post(
                "/conversations/messages", json=message_body())
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["shipment_references"][0]["id"],
            str(WORKFLOW_ID))

    def test_shipment_summary_round_trip(self):
        with client_with() as client:
            response = client.post(
                "/conversations/messages", headers=HEADER_A,
                json=message_body())
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["conversation_id"], str(CONVERSATION_ID))
        self.assertEqual(payload["mode"], "shipment_aware")
        self.assertEqual(payload["status"], "grounded")
        self.assertEqual(
            set(payload.keys()),
            {"conversation_id", "mode", "intent", "status",
             "summary_text", "shipment_references", "citations",
             "refusal_reason"})
        self.assertIsNone(payload["refusal_reason"])

    def test_cross_tenant_workflow_rejected_without_oracle(self):
        with client_with() as client:
            response = client.post(
                "/conversations/messages", headers=HEADER_B,
                json=message_body())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["error"]["code"], "tenant_mismatch")
        # No workflow identifiers leak into the refusal.
        self.assertNotIn(str(WORKFLOW_ID), response.text)

    def test_cross_tenant_message_access_rejected(self):
        # A conversation correlated in tenant A carries no
        # authority in tenant B: the workflow context is
        # revalidated, so tenant B cannot read tenant A's state.
        body = message_body(
            intent="explain_evidence_gaps",
            user_text="What am I missing?")
        with client_with() as client:
            response = client.post(
                "/conversations/messages", headers=HEADER_B,
                json=body)
        self.assertEqual(response.status_code, 403)

    def test_knowledge_mode_rejects_shipment_context(self):
        with client_with() as client:
            response = client.post(
                "/conversations/messages", headers=HEADER_A,
                json=message_body(
                    mode="knowledge",
                    intent="answer_regulatory_question",
                    user_text="What is required?",
                    information_need="filing obligation"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["code"], "invalid_input")

    def test_shipment_mode_requires_workflow(self):
        body = message_body()
        del body["workflow"]
        with client_with() as client:
            response = client.post(
                "/conversations/messages", headers=HEADER_A,
                json=body)
        self.assertEqual(response.status_code, 400)

    def test_malformed_input_rejected(self):
        with client_with() as client:
            response = client.post(
                "/conversations/messages", headers=HEADER_A,
                json={"mode": "knowledge"})
        self.assertEqual(response.status_code, 422)

    def test_unknown_intent_rejected_by_schema(self):
        with client_with() as client:
            response = client.post(
                "/conversations/messages", headers=HEADER_A,
                json=message_body(intent="finalize_shipment"))
        self.assertEqual(response.status_code, 422)

    def test_client_tenant_id_forbidden_in_body(self):
        body = message_body()
        body["tenant_id"] = str(TENANT_B.tenant_id)
        with client_with() as client:
            response = client.post(
                "/conversations/messages", headers=HEADER_A,
                json=body)
        self.assertEqual(response.status_code, 422)

    def test_knowledge_without_rag_fails_closed(self):
        with client_with(rag=None) as client:
            response = client.post(
                "/conversations/messages", headers=HEADER_A,
                json={
                    "conversation_id": str(CONVERSATION_ID),
                    "mode": "knowledge",
                    "intent": "answer_regulatory_question",
                    "user_text": "What is required?",
                    "information_need": "filing obligation",
                })
        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(
            payload["error"]["code"], "infrastructure_failure")
        # Static message only — no dynamic detail to sanitize.
        self.assertNotIn("traceback", response.text.lower())

    def test_knowledge_answer_citations_shape(self):
        rag = FakeRAG(validated_answer_double())
        with client_with(rag=rag) as client:
            response = client.post(
                "/conversations/messages", headers=HEADER_A,
                json={
                    "conversation_id": str(CONVERSATION_ID),
                    "mode": "knowledge",
                    "intent": "answer_regulatory_question",
                    "user_text": "What is required?",
                    "information_need": "filing obligation",
                })
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "grounded")
        self.assertEqual(len(payload["citations"]), 1)
        citation = payload["citations"][0]
        self.assertEqual(
            set(citation.keys()),
            {"label", "rank_position", "evidence"})
        self.assertEqual(
            set(citation["evidence"].keys()),
            {"chunk_id", "document_id", "chunk_index", "source_id",
             "source_type", "source_location", "document_version",
             "content_fingerprint"})
        self.assertEqual(payload["shipment_references"], [])

    def test_empty_knowledge_is_refused_over_http(self):
        rag = FakeRAG(SimpleNamespace(is_empty=True))
        with client_with(rag=rag) as client:
            response = client.post(
                "/conversations/messages", headers=HEADER_A,
                json={
                    "conversation_id": str(CONVERSATION_ID),
                    "mode": "knowledge",
                    "intent": "answer_regulatory_question",
                    "user_text": "What is required?",
                    "information_need": "filing obligation",
                })
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["status"], "refused_unknown")
        self.assertIsNotNone(payload["refusal_reason"])
        self.assertEqual(payload["citations"], [])

    def test_openapi_includes_conversation_route(self):
        with client_with() as client:
            response = client.get("/openapi.json", headers=HEADER_A)
        self.assertEqual(response.status_code, 200)
        self.assertIn("/conversations/messages", response.json()["paths"])


if __name__ == "__main__":
    unittest.main()
