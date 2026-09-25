"""Phase 8.2 — HTTP endpoint exposure tests.

Covers the thin compliance adapter: authentication via
the existing Phase 1 boundary, owner/member
authorization, tenant isolation, workflow/evidence/
analysis/assessment journeys, categorized error mapping,
terminal-closure enforcement, response privacy, the
AST route boundary, and OpenAPI coherence.

RAG is faked with the deterministic validated-answer
chain; all domain and application services are real. No
Phase 1–8.1 test is modified.
"""

import ast
import json
import unittest
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.api.auth import MemberContext
from xportra.api.dependencies import get_member_context
from xportra.domain.answer_validation import CitationAwareAnswerValidator
from xportra.domain.errors import LLMProviderError
from xportra.domain.evidence_context import (
    DeterministicContextSelector,
    EvidenceContextBudget,
)
from xportra.domain.evidence_hybrid import HybridRetrievalCandidate
from xportra.domain.evidence_prompt import (
    CitationAwarePromptBuilder,
    EvidencePromptConfig,
)
from xportra.domain.evidence_ranking import DeterministicEvidenceRanker
from xportra.domain.evidence_retrieval import EvidenceRetrievalResult
from xportra.domain.ingestion import (
    ComplianceCaseService,
    EvidenceRecord,
)
from xportra.domain.llm import GeneratedAnswer, LLMResponse
from xportra.persistence.tenant import TenantContext

TENANT_A = TenantContext(UUID("11111111-1111-1111-1111-111111111111"))
TENANT_B = TenantContext(UUID("22222222-2222-2222-2222-222222222222"))
HEADER_A = {"X-Development-Tenant-ID": str(TENANT_A.tenant_id)}
HEADER_B = {"X-Development-Tenant-ID": str(TENANT_B.tenant_id)}
CASE_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
SHIPMENT_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
DOCUMENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
EVIDENCE_ID = UUID("66666666-6666-6666-0000-000000000001")

PROMPT_CONFIG = EvidencePromptConfig(
    system_instructions="Explain the compliance position."
)


def requirement_id(index):
    return UUID(f"00000000-0000-0000-0000-{index:012d}")


def make_knowledge_evidence(**overrides):
    kwargs = dict(
        tenant_id=TENANT_A.tenant_id,
        chunk_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa00"),
        document_id=DOCUMENT_ID,
        chunk_index=0,
        content="Exporters must file the required form.",
        content_fingerprint="fp-0",
        source_id="sonsa/cert-guide",
        source_type="guidance",
        source_location="https://example.test/guide",
        document_version="2024.1",
        embedding_model="test-embed-model",
        embedding_dimensions=4,
        score=0.9,
    )
    kwargs.update(overrides)
    return EvidenceRetrievalResult(**kwargs)


def make_validated_answer(text="The filing is required [E1].",
                           contents=("Exporters must file the form.",)):
    candidates = []
    for index, content in enumerate(contents):
        evidence = make_knowledge_evidence(
            content=content,
            chunk_id=UUID(
                f"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa0{index}"),
            content_fingerprint=f"fp-{index}",
            score=0.9 - index * 0.1,
        )
        candidates.append(HybridRetrievalCandidate(
            evidence=evidence,
            semantic_score=0.9 - index * 0.1,
            lexical_score=None,
            retrieval_sources=frozenset({"semantic"})))
    ranked = DeterministicEvidenceRanker().rank(
        candidates, top_k=len(candidates))
    selection = DeterministicContextSelector().select(
        ranked, tenant_id=TENANT_A,
        budget=EvidenceContextBudget(4000))
    prompt = CitationAwarePromptBuilder(
        config=PROMPT_CONFIG).build(
            selection, information_need="filing obligation")
    answer = GeneratedAnswer(
        prompt=prompt,
        response=LLMResponse(
            generated_text=text,
            model_identifier="test-model",
            finish_reason="stop"),
        tenant_id=TENANT_A)
    return CitationAwareAnswerValidator().validate(answer)


def make_case(index=1, applicability="applicable",
              assessment="satisfied", evidence_statuses=(),
              assessment_reason="required evidence present"):
    req_id = requirement_id(index)
    records = []
    for slot, status in enumerate(evidence_statuses):
        records.append(EvidenceRecord(
            tenant_id=TENANT_A.tenant_id,
            evidence_id=UUID(
                f"66666666-6666-6666-{slot:04d}-{index:012d}"),
            evidence_type="certificate",
            reference=f"cert://filing-{index}-{slot}",
            requirement_id=req_id,
            status=status,
            metadata={"supports_requirement": (
                status in ("accepted", "reviewed"))},
        ))
    applicability_result = {
        "id": UUID(f"11111111-1111-1111-1111-{index:012d}"),
        "tenant_id": TENANT_A.tenant_id,
        "requirement_id": req_id,
        "outcome": applicability,
        "reason": "origin and commodity match",
        "context_fingerprint": "fp-context",
        "context": {"destination": "NG"},
        "status": "determined",
    }
    requirement = {
        "id": req_id,
        "requirement_text": f"Requirement {index} filing duty.",
        "requirement_type": "documentation",
        "source_location": "https://example.test/guide",
        "source_id": "sonsa/cert-guide",
        "normalized_document_id": DOCUMENT_ID,
        "artifact_id": UUID("99999999-9999-9999-9999-999999999999"),
    }
    if applicability == "applicable" and (
            assessment != "unknown" or records):
        assessment_result = {
            "id": UUID(f"22222222-2222-2222-2222-{index:012d}"),
            "tenant_id": TENANT_A.tenant_id,
            "requirement_id": req_id,
            "applicability_result_id": applicability_result["id"],
            "outcome": assessment,
            "reason": assessment_reason,
            "evidence_id": records[0].evidence_id if records else None,
            "evidence_ids": [r.evidence_id for r in records],
            "status": "assessed",
        }
    else:
        assessment_result = None
    case = ComplianceCaseService().build(
        applicability_result, requirement, assessment_result,
        records)
    return json.loads(json.dumps(case, default=str))


class FakeRAGService:
    def __init__(self, failure=None):
        self._answers = [make_validated_answer()]
        self._failure = failure
        self.calls = []

    def query(self, information_need, *, tenant_id, mode,
              context_budget, scope=None, top_k=5,
              candidate_pool=None):
        self.calls.append(information_need)
        if self._failure is not None:
            raise self._failure
        return self._answers[0]


def make_summary():
    return {
        "tenant_id": str(TENANT_A.tenant_id),
        "context_fingerprint": "fp-context",
        "status": "decision_summary",
        "applicability": {"total_requirements": 1},
        "risk": {"classified_count": 0},
        "actions": {"recommendation_count": 0},
    }


def _owner_context():
    from xportra.application.context import ApplicationContext

    return ApplicationContext(
        actor_id=None, tenant=TENANT_A, role="owner")


class FakeEvidenceStore:
    def get(self, tenant, evidence_id):
        return None


def client_with(rag=None):
    return TestClient(
        create_app(services=SimpleNamespace(
            rag=rag, evidence=FakeEvidenceStore())))


def workflow_body(record):
    return {"workflow": record}


def start_record(client, headers=HEADER_A, shipment=True):
    body = {"case_id": str(CASE_ID)}
    if shipment:
        body["shipment_id"] = str(SHIPMENT_ID)
    response = client.post(
        "/compliance/workflows/start", headers=headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()["workflow"]


def progress_record(client, record, headers=HEADER_A):
    for path in ("provide-information", "note-evidence-pending",
                 "record-applicability"):
        response = client.post(
            f"/compliance/workflows/{path}", headers=headers,
            json=workflow_body(record))
        assert response.status_code == 200, (path, response.text)
        record = response.json()["workflow"]
    return record


def analyzed_record(client, record, headers=HEADER_A):
    case = make_case(evidence_statuses=("accepted",))
    response = client.post(
        "/compliance/workflows/analyze", headers=headers,
        json={"workflow": record, "cases": [case],
              "decision_summary": make_summary()})
    assert response.status_code == 200, response.text
    return response.json()["workflow"], response.json()["report"]


class AuthenticationTests(unittest.TestCase):
    def test_unauthenticated_request_rejected(self):
        with client_with() as client:
            response = client.post(
                "/compliance/workflows/start",
                json={"case_id": str(CASE_ID)})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["error"]["code"],
            "authentication_required")

    def test_development_header_authenticates(self):
        with client_with() as client:
            response = client.post(
                "/compliance/workflows/start", headers=HEADER_A,
                json={"case_id": str(CASE_ID)})
        self.assertEqual(response.status_code, 201)

    def test_malformed_development_identity_rejected(self):
        with client_with() as client:
            response = client.post(
                "/compliance/workflows/start",
                headers={"X-Development-Tenant-ID": "not-a-uuid"},
                json={"case_id": str(CASE_ID)})
        self.assertIn(response.status_code, (400, 422))


class AuthorizationTests(unittest.TestCase):
    def _member_client(self, rag=None):
        app = create_app(services=SimpleNamespace(rag=rag))
        app.dependency_overrides[get_member_context] = (
            lambda: MemberContext(TENANT_A, "member"))
        return TestClient(app)

    def test_member_may_read_but_not_progress(self):
        with client_with() as owner:
            record = start_record(owner)
        with self._member_client() as client:
            response = client.post(
                "/compliance/workflows/provide-information",
                json=workflow_body(record))
            self.assertEqual(response.status_code, 403)
            self.assertEqual(
                response.json()["error"]["code"],
                "permission_denied")
            response = client.post(
                "/compliance/workflows/status",
                json=workflow_body(record))
            self.assertEqual(response.status_code, 200)

    def test_member_may_not_run_analysis(self):
        with client_with() as owner:
            record = start_record(owner)
            record = progress_record(owner, record)
        with self._member_client(
                rag=FakeRAGService()) as client:
            response = client.post(
                "/compliance/workflows/analyze", json={
                    "workflow": record,
                    "cases": [make_case(
                        evidence_statuses=("accepted",))],
                })
            self.assertEqual(response.status_code, 403)

    def test_member_may_assess_and_check_readiness(self):
        with self._member_client() as client:
            response = client.post(
                "/compliance/assessments/applicability", json={
                    "requirements": [{
                        "id": str(requirement_id(1)),
                        "requirement_text": "File the form.",
                        "requirement_type": "documentation",
                    }],
                })
            self.assertEqual(response.status_code, 200)


class TenantIsolationTests(unittest.TestCase):
    def test_cross_tenant_record_rejected(self):
        with client_with() as client:
            record = start_record(client, headers=HEADER_A)
            response = client.post(
                "/compliance/workflows/provide-information",
                headers=HEADER_B,
                json=workflow_body(record))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["error"]["code"], "tenant_mismatch")

    def test_tenant_never_comes_from_body(self):
        with client_with() as client:
            record = start_record(client, headers=HEADER_A)
            record["tenant_id"] = str(TENANT_B.tenant_id)
            response = client.post(
                "/compliance/workflows/status", headers=HEADER_A,
                json=workflow_body(record))
        self.assertEqual(response.status_code, 403)

    def test_evidence_lookup_does_not_leak(self):
        with client_with() as client:
            response = client.get(
                "/compliance-evidence/eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
                headers=HEADER_A)
        self.assertEqual(response.status_code, 404)


class WorkflowJourneyTests(unittest.TestCase):
    def test_create_and_progress_workflow(self):
        with client_with() as client:
            record = start_record(client)
            self.assertEqual(
                record["tenant_id"], str(TENANT_A.tenant_id))
            for path, state in (
                    ("provide-information",
                     "information_provided"),
                    ("note-evidence-pending", "evidence_pending"),
                    ("record-applicability",
                     "applicability_determined")):
                response = client.post(
                    f"/compliance/workflows/{path}",
                    headers=HEADER_A,
                    json=workflow_body(record))
                self.assertEqual(response.status_code, 200)
                record = response.json()["workflow"]
                self.assertEqual(
                    response.json()["summary"]["state"], state)
            response = client.post(
                "/compliance/workflows/status", headers=HEADER_A,
                json=workflow_body(record))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.json()["state"],
                "applicability_determined")

    def test_invalid_transition_maps_to_409(self):
        with client_with() as client:
            record = start_record(client)
            response = client.post(
                "/compliance/workflows/submit-for-review",
                headers=HEADER_A,
                json=workflow_body(record))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"],
            "invalid_transition")

    def test_malformed_body_maps_to_422(self):
        with client_with() as client:
            response = client.post(
                "/compliance/workflows/status", headers=HEADER_A,
                json={"workflow": {"nope": True}})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["error"]["code"], "validation_error")

    def test_closure_query(self):
        with client_with() as client:
            record = start_record(client)
            response = client.post(
                "/compliance/workflows/is-closed",
                headers=HEADER_A,
                json=workflow_body(record))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_closed"])


class SupplyEvidenceTests(unittest.TestCase):
    def test_valid_supply_advances_workflow(self):
        with client_with(rag=FakeRAGService()) as client:
            record = start_record(client)
            record = progress_record(client, record)
            record, _ = analyzed_record(client, record)
            for path in ("submit-for-review",):
                response = client.post(
                    f"/compliance/workflows/{path}",
                    headers=HEADER_A,
                    json=workflow_body(record))
                self.assertEqual(response.status_code, 200)
                record = response.json()["workflow"]
            response = client.post(
                "/compliance/workflows/request-additional-evidence",
                headers=HEADER_A,
                json={"workflow": record,
                      "requirement_ids": [
                          str(requirement_id(1))]},
            )
            self.assertEqual(response.status_code, 200)
            record = response.json()["workflow"]
            response = client.post(
                "/compliance/workflows/supply-evidence",
                headers=HEADER_A,
                json={"workflow": record,
                      "evidence_id": str(EVIDENCE_ID)},
            )
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(
                body["summary"]["state"], "reanalysis_required")
            self.assertIn(
                str(EVIDENCE_ID),
                body["summary"]["supplied_evidence_ids"])

    def test_empty_evidence_request_rejected(self):
        with client_with() as client:
            record = start_record(client)
            response = client.post(
                "/compliance/workflows/request-additional-evidence",
                headers=HEADER_A,
                json={"workflow": record, "requirement_ids": []},
            )
            self.assertEqual(response.status_code, 422)


class AnalysisEndpointTests(unittest.TestCase):
    def test_analyze_delegates_and_reports(self):
        with client_with(rag=FakeRAGService()) as client:
            record = start_record(client)
            record = progress_record(client, record)
            record, report = analyzed_record(client, record)
            self.assertEqual(len(record["rounds"]), 1)
            self.assertEqual(len(report["findings"]), 1)
            self.assertEqual(
                report["findings"][0]["assessment"],
                "satisfied")

    def test_analyze_wrong_state_maps_to_409(self):
        with client_with(rag=FakeRAGService()) as client:
            record = start_record(client)
            response = client.post(
                "/compliance/workflows/analyze", headers=HEADER_A,
                json={"workflow": record,
                      "cases": [make_case()]})
        self.assertEqual(response.status_code, 409)

    def test_unwired_analysis_maps_to_503(self):
        with client_with() as client:
            record = start_record(client)
            record = progress_record(client, record)
            response = client.post(
                "/compliance/workflows/analyze", headers=HEADER_A,
                json={"workflow": record,
                      "cases": [make_case()]})
        self.assertEqual(response.status_code, 503)

    def test_provider_failure_maps_to_503(self):
        rag = FakeRAGService(failure=LLMProviderError(
            "generate", RuntimeError("provider down")))
        with client_with(rag=rag) as client:
            record = start_record(client)
            record = progress_record(client, record)
            response = client.post(
                "/compliance/workflows/analyze", headers=HEADER_A,
                json={"workflow": record,
                      "cases": [make_case()]})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error"]["code"],
            "infrastructure_failure")

    def test_analysis_invents_no_verdict(self):
        with client_with(rag=FakeRAGService()) as client:
            record = start_record(client)
            record = progress_record(client, record)
            _, report = analyzed_record(client, record)
            body = json.dumps(report).lower()
            for marker in ("verdict", "overall", "compliant",
                           "score", "percent"):
                self.assertNotIn(marker, body)


class AssessmentEndpointTests(unittest.TestCase):
    def test_applicability_endpoint(self):
        with client_with() as client:
            response = client.post(
                "/compliance/assessments/applicability",
                headers=HEADER_A,
                json={
                    "requirements": [{
                        "id": str(requirement_id(1)),
                        "requirement_text": "File the form.",
                        "requirement_type": "documentation",
                    }],
                    "exporter": {
                        "country_of_registration": "NG"},
                    "destination": {"country_code": "GH"},
                })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["counts"]["total_requirements"], 1)

    def test_case_readiness_endpoint(self):
        with client_with() as client:
            response = client.post(
                "/compliance/assessments/case-readiness",
                headers=HEADER_A,
                json={"cases": [make_case(
                    1, assessment="unknown", evidence_statuses=(),
                    assessment_reason="required evidence absent")]})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn(body["readiness_state"],
                      {"ready", "partially_ready", "not_ready"})


class TerminalClosureTests(unittest.TestCase):
    def _finalized_record(self):
        from xportra.application import (
            AnalysisApplicationService,
            WorkflowApplicationService,
        )

        workflows = WorkflowApplicationService()
        analysis = AnalysisApplicationService(
            rag_service=FakeRAGService())
        record, _ = workflows.start_workflow(
            _owner_context(), CASE_ID, shipment_id=SHIPMENT_ID)
        record, _ = workflows.provide_information(
            _owner_context(), record)
        record, _ = workflows.note_evidence_pending(
            _owner_context(), record)
        record, _ = workflows.record_applicability(
            _owner_context(), record)
        record, result, _ = analysis.run_analysis(
            _owner_context(), record,
            [make_case(evidence_statuses=("accepted",))],
            max_context_chars=4000,
            decision_summary=make_summary())
        record, _ = workflows.submit_for_review(
            _owner_context(), record)
        record, _ = workflows.finalize_package(
            _owner_context(), record, result)
        return record

    def test_terminal_supply_maps_to_409(self):
        with client_with() as client:
            record = self._finalized_record()
            response = client.post(
                "/compliance/workflows/supply-evidence",
                headers=HEADER_A,
                json={"workflow": record,
                      "evidence_id": str(EVIDENCE_ID)},
            )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"],
            "terminal_workflow")

    def test_terminal_analyze_maps_to_409(self):
        with client_with(rag=FakeRAGService()) as client:
            record = self._finalized_record()
            response = client.post(
                "/compliance/workflows/analyze", headers=HEADER_A,
                json={"workflow": record,
                      "cases": [make_case()]})
        self.assertEqual(response.status_code, 409)

    def test_closure_query_reports_closed(self):
        with client_with() as client:
            record = self._finalized_record()
            response = client.post(
                "/compliance/workflows/is-closed",
                headers=HEADER_A,
                json=workflow_body(record))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_closed"])


class SerializationPrivacyTests(unittest.TestCase):
    def test_history_response_leaks_no_internals(self):
        with client_with(rag=FakeRAGService()) as client:
            record = start_record(client)
            record = progress_record(client, record)
            record, _ = analyzed_record(client, record)
            response = client.post(
                "/compliance/workflows/history", headers=HEADER_A,
                json=workflow_body(record))
            self.assertEqual(response.status_code, 200)
            body = json.dumps(response.json()).lower()
            for marker in ("prompt", "secret", "api_key",
                           "password", "openrouter", "qdrant",
                           "generated_text", "model_identifier",
                           "input_fingerprint",
                           "content_fingerprint",
                           "answer_fingerprint",
                           "chain-of-thought"):
                self.assertNotIn(marker, body)

    def test_error_responses_hide_internals(self):
        with client_with() as client:
            record = start_record(client)
            response = client.post(
                "/compliance/workflows/supply-evidence",
                headers=HEADER_A,
                json={"workflow": record,
                      "evidence_id": str(EVIDENCE_ID)},
            )
            self.assertEqual(response.status_code, 409)
            body = json.dumps(response.json()).lower()
            self.assertNotIn("traceback", body)
            self.assertIn("error", response.json())
            self.assertIn("code", response.json()["error"])


class RouteBoundaryTests(unittest.TestCase):
    def test_routes_call_application_not_domain(self):
        import pathlib

        text = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "api" / "compliance.py").read_text(
                    encoding="utf-8")
        for marker in ("qdrant", "QdrantClient", "openai",
                       "anthropic", "SentenceTransformer",
                       "OpenRouter", "psycopg",
                       "xportra.infrastructure",
                       "ComplianceWorkflowService",
                       "ShipmentIntakeService",
                       "ComplianceReasoningApplication",
                       "RAGApplicationService",
                       ".retrieve(", ".generate(", ".query(",
                       "ComplianceEvidenceService"):
            self.assertNotIn(marker, text)
        for marker in ("WorkflowApplicationService",
                       "AnalysisApplicationService",
                       "AssessmentApplicationService",
                       "ApplicationContext"):
            self.assertIn(marker, text)


class OpenAPIContractTests(unittest.TestCase):
    def test_openapi_lists_compliance_paths(self):
        with client_with() as client:
            response = client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        expected = (
            "/compliance/workflows/start",
            "/compliance/workflows/provide-information",
            "/compliance/workflows/note-evidence-pending",
            "/compliance/workflows/record-applicability",
            "/compliance/workflows/submit-for-review",
            "/compliance/workflows/request-additional-evidence",
            "/compliance/workflows/supply-evidence",
            "/compliance/workflows/status",
            "/compliance/workflows/history",
            "/compliance/workflows/is-closed",
            "/compliance/workflows/analyze",
            "/compliance/assessments/applicability",
            "/compliance/assessments/case-readiness",
        )
        for path in expected:
            self.assertIn(path, paths)


if __name__ == "__main__":
    unittest.main()
