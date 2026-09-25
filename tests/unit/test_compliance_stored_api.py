"""Phase 8.5 — Stored-path HTTP exposure tests.

Covers the thin stored-path adapter: finalize from the
server-known latest, stored package reads, stored report
reads — with authentication, owner/member authorization,
tenant isolation, categorized error mapping, terminal
closure, response privacy, the AST route boundary, and
OpenAPI coherence.

RAG is faked with the deterministic validated-answer
chain; the result store is faked with tenant-scoped
in-memory doubles honoring the repository contract
(conflicts, scoping, linkage); all domain and
application services are real. No Phase 1–8.4 test is
modified.
"""

import ast
import json
import unittest
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.api.auth import MemberContext
from xportra.api.dependencies import get_member_context, get_request_actor
from xportra.application.errors import ApplicationNotFoundError
from xportra.domain.answer_validation import CitationAwareAnswerValidator
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
ACTOR_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CASE_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
SHIPMENT_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
DOCUMENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
EVIDENCE_ID = UUID("66666666-6666-6666-0000-000000000001")
ACTOR_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

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


class FakeResultStore:
    """Tenant-scoped in-memory double honoring store semantics.

    Holds live result objects keyed by stable identity with
    the same scoping, linkage, and conflict behavior as the
    normalized store: unknown identities resolve to
    ``None`` (→ 404 downstream), divergent round slots keep
    the first writer, and a recorded package blocks
    second finalization.
    """

    def __init__(self):
        self.results = {}
        self.rounds = {}
        self.packages = {}
        self.seen_actors = []

    def _tenant(self, ctx):
        self.seen_actors.append(ctx.actor_id)
        return ctx.tenant_id

    def store_analysis_result(self, ctx, workflow, result):
        tenant_id = self._tenant(ctx)
        key = (tenant_id, result.report.id)
        self.results[key] = result
        slot = (tenant_id, workflow.id)
        entries = self.rounds.setdefault(slot, [])
        latest = workflow.rounds[-1]
        for entry in entries:
            if entry["round_index"] == latest.round_index:
                return {
                    "report_id": result.report.id,
                    "round_index": latest.round_index,
                }
        entries.append({
            "round_index": latest.round_index,
            "report_id": latest.report_id,
            "case_id": workflow.case_id,
            "analysis_ids": tuple(a.id for a in result.analyses),
            "trace_ids": tuple(t.id for t in result.traces),
            "input_fingerprints": tuple(
                t.input_fingerprint for t in result.traces),
        })
        return {
            "report_id": result.report.id,
            "round_index": latest.round_index,
        }

    def latest_round_for_workflow(self, ctx, workflow_id):
        entries = self.rounds.get(
            (self._tenant(ctx), workflow_id), [])
        return entries[-1] if entries else None

    def rounds_for_workflow(self, ctx, workflow_id):
        return list(self.rounds.get(
            (self._tenant(ctx), workflow_id), []))

    def load_result(self, ctx, report_id):
        result = self.results.get(
            (self._tenant(ctx), report_id))
        if result is None:
            raise ApplicationNotFoundError(
                "analysis report was not found")
        return result

    def store_package_linkage(self, ctx, workflow, report_id,
                              round_index, open_requirements):
        tenant_id = self._tenant(ctx)
        key = (tenant_id, workflow.id)
        self.packages[key] = {
            "workflow_id": workflow.id,
            "case_id": workflow.case_id,
            "report_id": report_id,
            "round_index": round_index,
            "open_requirements": tuple(open_requirements),
        }
        return dict(self.packages[key])

    def load_package(self, ctx, workflow_id):
        return self.packages.get(
            (self._tenant(ctx), workflow_id))


def client_with(rag=None, store=None):
    return TestClient(
        create_app(services=SimpleNamespace(
            rag=rag, result_store=store)))


def stored_client(rag=None):
    return client_with(
        rag=rag if rag is not None else FakeRAGService(),
        store=FakeResultStore())


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


def reviewed_record(client, record, headers=HEADER_A):
    response = client.post(
        "/compliance/workflows/submit-for-review",
        headers=headers, json=workflow_body(record))
    assert response.status_code == 200, response.text
    return response.json()["workflow"]


def finalized_record(client, record, headers=HEADER_A):
    response = client.post(
        "/compliance/workflows/finalize", headers=headers,
        json=workflow_body(record))
    assert response.status_code == 201, response.text
    body = response.json()
    return body["workflow"], body["package"]


class FinalizeEndpointTests(unittest.TestCase):
    def test_finalize_happy_path(self):
        with stored_client() as client:
            record = start_record(client)
            record = progress_record(client, record)
            record, report = analyzed_record(client, record)
            record = reviewed_record(client, record)
            response = client.post(
                "/compliance/workflows/finalize", headers=HEADER_A,
                json=workflow_body(record))
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(
            body["workflow"]["state"], "assessment_package_ready")
        self.assertEqual(
            body["package"]["report"]["report_id"],
            report["report_id"])
        self.assertEqual(
            body["package"]["workflow_id"], body["workflow"]["id"])

    def test_finalize_not_ready(self):
        with stored_client() as client:
            record = start_record(client)
            record = progress_record(client, record)
            record, _ = analyzed_record(client, record)
            response = client.post(
                "/compliance/workflows/finalize", headers=HEADER_A,
                json=workflow_body(record))
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertEqual(body["error"]["code"], "not_ready")
        self.assertIn("reasons", body["error"]["details"])

    def test_finalize_stale_record(self):
        with stored_client() as client:
            record = start_record(client)
            record = progress_record(client, record)
            record, _ = analyzed_record(client, record)
            record = reviewed_record(client, record)
            forged = dict(record)
            forged_round = dict(forged["rounds"][0])
            forged_round["report_id"] = str(UUID(int=7))
            forged["rounds"] = [forged_round]
            response = client.post(
                "/compliance/workflows/finalize", headers=HEADER_A,
                json=workflow_body(forged))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"], "stale_analysis")

    def test_finalize_without_stored_result(self):
        with stored_client() as client:
            record = start_record(client)
            record = progress_record(client, record)
            forged = dict(record)
            forged["state"] = "review_required"
            response = client.post(
                "/compliance/workflows/finalize", headers=HEADER_A,
                json=workflow_body(forged))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["error"]["code"], "not_found")

    def test_second_finalize_rejected(self):
        with stored_client() as client:
            record = start_record(client)
            record = progress_record(client, record)
            record, _ = analyzed_record(client, record)
            pre_terminal = reviewed_record(client, record)
            record, _ = finalized_record(client, pre_terminal)
            response = client.post(
                "/compliance/workflows/finalize", headers=HEADER_A,
                json=workflow_body(record))
            self.assertEqual(response.status_code, 409)
            self.assertEqual(
                response.json()["error"]["code"],
                "terminal_workflow")
            response = client.post(
                "/compliance/workflows/finalize", headers=HEADER_A,
                json=workflow_body(pre_terminal))
            self.assertEqual(response.status_code, 409)
            self.assertEqual(
                response.json()["error"]["code"],
                "terminal_workflow")

    def test_finalize_unwired_store(self):
        with client_with(rag=FakeRAGService()) as client:
            record = start_record(client)
            response = client.post(
                "/compliance/workflows/finalize", headers=HEADER_A,
                json=workflow_body(record))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error"]["code"],
            "result_store_not_configured")

    def test_finalize_malformed_body(self):
        with stored_client() as client:
            response = client.post(
                "/compliance/workflows/finalize", headers=HEADER_A,
                json={"workflow": {"nope": True}})
        self.assertEqual(response.status_code, 422)


class PackageEndpointTests(unittest.TestCase):
    def test_package_read_after_finalize(self):
        with stored_client() as client:
            record = start_record(client)
            record = progress_record(client, record)
            record, report = analyzed_record(client, record)
            record = reviewed_record(client, record)
            record, package = finalized_record(client, record)
            response = client.post(
                "/compliance/workflows/package", headers=HEADER_A,
                json=workflow_body(record))
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            body["report"]["report_id"], report["report_id"])
        self.assertEqual(body["state"], "assessment_package_ready")
        self.assertEqual(body["workflow_id"], record["id"])
        self.assertEqual(package["report"]["report_id"],
                         report["report_id"])

    def test_package_unknown_workflow(self):
        with stored_client() as client:
            record = start_record(client)
            response = client.post(
                "/compliance/workflows/package", headers=HEADER_A,
                json=workflow_body(record))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["error"]["code"], "not_found")

    def test_package_unwired_store(self):
        with client_with() as client:
            record = start_record(client)
            response = client.post(
                "/compliance/workflows/package", headers=HEADER_A,
                json=workflow_body(record))
        self.assertEqual(response.status_code, 503)


class ReportEndpointTests(unittest.TestCase):
    def test_report_read_after_analyze(self):
        with stored_client() as client:
            record = start_record(client)
            record = progress_record(client, record)
            _, report = analyzed_record(client, record)
            response = client.get(
                f"/compliance/reports/{report['report_id']}",
                headers=HEADER_A)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["report_id"], report["report_id"])
        self.assertEqual(len(body["findings"]), 1)
        finding = body["findings"][0]
        self.assertEqual(finding["assessment"], "satisfied")
        self.assertTrue(finding["sources"])

    def test_report_unknown_id(self):
        with stored_client() as client:
            response = client.get(
                f"/compliance/reports/{UUID(int=9)}",
                headers=HEADER_A)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.json()["error"]["code"], "not_found")

    def test_report_malformed_id(self):
        with stored_client() as client:
            response = client.get(
                "/compliance/reports/not-a-uuid",
                headers=HEADER_A)
        self.assertEqual(response.status_code, 422)

    def test_report_unwired_store(self):
        with client_with() as client:
            response = client.get(
                f"/compliance/reports/{UUID(int=9)}",
                headers=HEADER_A)
        self.assertEqual(response.status_code, 503)


class StoredTenantIsolationTests(unittest.TestCase):
    def test_cross_tenant_finalize_rejected(self):
        with stored_client() as client:
            record = start_record(client)
            record = progress_record(client, record)
            record, _ = analyzed_record(client, record)
            record = reviewed_record(client, record)
            response = client.post(
                "/compliance/workflows/finalize", headers=HEADER_B,
                json=workflow_body(record))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["error"]["code"], "tenant_mismatch")

    def test_cross_tenant_package_rejected(self):
        with stored_client() as client:
            record = start_record(client)
            record = progress_record(client, record)
            record, _ = analyzed_record(client, record)
            record = reviewed_record(client, record)
            record, _ = finalized_record(client, record)
            response = client.post(
                "/compliance/workflows/package", headers=HEADER_B,
                json=workflow_body(record))
        self.assertEqual(response.status_code, 403)

    def test_cross_tenant_report_not_found(self):
        with stored_client() as client:
            record = start_record(client)
            record = progress_record(client, record)
            _, report = analyzed_record(client, record)
            response = client.get(
                f"/compliance/reports/{report['report_id']}",
                headers=HEADER_B)
        self.assertEqual(response.status_code, 404)


class StoredAuthenticationTests(unittest.TestCase):
    def test_unauthenticated_finalize_rejected(self):
        with stored_client() as client:
            record = start_record(client)
            response = client.post(
                "/compliance/workflows/finalize",
                json=workflow_body(record))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["error"]["code"],
            "authentication_required")

    def test_member_cannot_finalize_but_can_read(self):
        from xportra.api.dependencies import get_member_context

        store = FakeResultStore()
        app = create_app(services=SimpleNamespace(
            rag=FakeRAGService(), result_store=store))
        with TestClient(app) as owner:
            record = start_record(owner)
            record = progress_record(owner, record)
            record, report = analyzed_record(owner, record)
            record = reviewed_record(owner, record)
            record, _ = finalized_record(owner, record)
        app.dependency_overrides[get_member_context] = (
            lambda: MemberContext(TENANT_A, "member"))
        with TestClient(app) as member:
            response = member.post(
                "/compliance/workflows/finalize", json=workflow_body(record))
            self.assertEqual(response.status_code, 403)
            self.assertEqual(
                response.json()["error"]["code"],
                "permission_denied")
            response = member.post(
                "/compliance/workflows/package", json=workflow_body(record))
            self.assertEqual(response.status_code, 200)
            response = member.get(
                f"/compliance/reports/{report['report_id']}")
            self.assertEqual(response.status_code, 200)

    def test_actor_propagates_through_stored_paths(self):
        from xportra.api.dependencies import get_request_actor

        store = FakeResultStore()
        app = create_app(services=SimpleNamespace(
            rag=FakeRAGService(), result_store=store))
        app.dependency_overrides[get_request_actor] = (
            lambda: ACTOR_ID)
        with TestClient(app) as client:
            record = start_record(client)
            record = progress_record(client, record)
            record, _ = analyzed_record(client, record)
            record = reviewed_record(client, record)
            response = client.post(
                "/compliance/workflows/finalize", headers=HEADER_A,
                json=workflow_body(record))
            self.assertEqual(response.status_code, 201)
        self.assertTrue(store.seen_actors)
        self.assertTrue(all(
            actor == ACTOR_ID for actor in store.seen_actors))


class StoredPrivacyTests(unittest.TestCase):
    PRIVACY_MARKERS = (
        "prompt", "secret", "api_key", "password", "openrouter",
        "qdrant", "generated_text", "model_identifier",
        "input_fingerprint", "content_fingerprint",
        "answer_fingerprint", "chain-of-thought",
    )
    VERDICT_MARKERS = ("verdict", "overall", "compliant", "score",
                       "percent")

    def test_package_response_leaks_no_internals(self):
        with stored_client() as client:
            record = start_record(client)
            record = progress_record(client, record)
            record, _ = analyzed_record(client, record)
            record = reviewed_record(client, record)
            _, package = finalized_record(client, record)
            body = json.dumps(package).lower()
            for marker in self.PRIVACY_MARKERS:
                self.assertNotIn(marker, body)
            for marker in self.VERDICT_MARKERS:
                self.assertNotIn(marker, body)

    def test_report_response_leaks_no_internals(self):
        with stored_client() as client:
            record = start_record(client)
            record = progress_record(client, record)
            _, report = analyzed_record(client, record)
            body = json.dumps(report).lower()
            for marker in self.PRIVACY_MARKERS:
                self.assertNotIn(marker, body)

    def test_error_responses_hide_internals(self):
        with stored_client() as client:
            response = client.post(
                "/compliance/workflows/finalize", headers=HEADER_A,
                json={"workflow": {"nope": True}})
            self.assertEqual(response.status_code, 422)
            body = json.dumps(response.json()).lower()
            self.assertNotIn("traceback", body)


class StoredRouteBoundaryTests(unittest.TestCase):
    def test_routes_call_application_not_domain(self):
        import pathlib

        text = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "api" / "compliance.py").read_text(
                    encoding="utf-8")
        for marker in ("qdrant", "QdrantClient", "openai",
                       "anthropic", "SentenceTransformer",
                       "OpenRouter", "psycopg",
                       "xportra.infrastructure",
                       "xportra.persistence",
                       "ComplianceWorkflowService",
                       "ShipmentIntakeService",
                       "ComplianceReasoningApplication",
                       "ComplianceResultStore",
                       "RAGApplicationService",
                       ".retrieve(", ".generate(", ".query(",
                       "ComplianceEvidenceService"):
            self.assertNotIn(marker, text)
        for marker in ("WorkflowApplicationService",
                       "AnalysisApplicationService",
                       "AssessmentApplicationService",
                       "ApplicationContext",
                       "ResultStoreDependency"):
            self.assertIn(marker, text)


class StoredOpenAPIContractTests(unittest.TestCase):
    def test_openapi_lists_stored_paths(self):
        with stored_client() as client:
            response = client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        paths = response.json()["paths"]
        for path in ("/compliance/workflows/finalize",
                     "/compliance/workflows/package",
                     "/compliance/reports/{report_id}"):
            self.assertIn(path, paths)
        finalize = paths["/compliance/workflows/finalize"]["post"]
        self.assertEqual(
            finalize["responses"]["201"]["description"],
            "Successful Response")


if __name__ == "__main__":
    unittest.main()
