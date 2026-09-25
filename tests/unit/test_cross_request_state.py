"""Phase 8.3 — Workflow/result transfer-or-store contract tests.

Covers the cross-request lifecycle answer: workflow
records transfer client-side and rehydrate
deterministically; deterministic inputs reconstruct from
authoritative records; live Phase 6 results are
in-session only (stale/foreign results fail closed, never
persisted, never client-sourced); terminal closure holds
across transfers; concurrency is safe because the server
holds no mutable workflow state; and the authenticated
actor reaches ``ApplicationContext.actor_id`` without
being forgeable or disturbing tenant/role derivation.

RAG uses scripted validated answers (distinct texts prove
round divergence); no live provider runs. No Phase 1–8.2
test is modified.
"""

import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import jwt as pyjwt
from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.api.auth import MemberContext
from xportra.api.dependencies import get_member_context, get_request_actor
from xportra.api.errors import AuthenticationError
from xportra.application import (
    AnalysisApplicationService,
    EvidenceApplicationService,
    WorkflowApplicationService,
)
from xportra.application.context import ApplicationContext
from xportra.application.errors import (
    ApplicationAuthorizationError,
    TenantMismatchError,
    TerminalWorkflowError,
    WorkflowNotReadyError,
    StaleAnalysisError,
)
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
SUBJECT_A = UUID("aaaaaaa1-0000-0000-0000-000000000001")
ACTOR_CTX_A = ApplicationContext(
    actor_id=SUBJECT_A, tenant=TENANT_A, role="owner")
CTX_A = ApplicationContext(
    actor_id=None, tenant=TENANT_A, role="owner")
CTX_B = ApplicationContext(
    actor_id=None, tenant=TENANT_B, role="owner")
CASE_A = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
CASE_B = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
SHIPMENT_A = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
DOCUMENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
EVIDENCE_ID = UUID("66666666-6666-6666-0000-000000000001")
JWT_SECRET = "phase-8-3-unit-test-jwt-secret-0123456789abcdef"

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


def make_case(index=1, assessment="satisfied", evidence_statuses=(),
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
        "outcome": "applicable",
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
    if assessment != "unknown" or records:
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
    return ComplianceCaseService().build(
        applicability_result, requirement, assessment_result,
        records)


def make_summary():
    return {
        "tenant_id": TENANT_A.tenant_id,
        "context_fingerprint": "fp-context",
        "status": "decision_summary",
        "applicability": {"total_requirements": 1},
        "risk": {"classified_count": 0},
        "actions": {"recommendation_count": 0},
    }


class FakeRAGService:
    """Scripted answers: distinct texts prove round divergence."""

    def __init__(self, texts=None, failure=None):
        self._texts = list(texts or ["The filing is required [E1]."])
        self._failure = failure
        self.calls = []

    def query(self, information_need, *, tenant_id, mode,
              context_budget, scope=None, top_k=5,
              candidate_pool=None):
        self.calls.append(information_need)
        if self._failure is not None:
            raise self._failure
        text = self._texts[min(len(self.calls) - 1,
                               len(self._texts) - 1)]
        return make_validated_answer(text=text)


def workflows():
    return WorkflowApplicationService()


def analysis(rag):
    return AnalysisApplicationService(rag_service=rag)


def start_record(ctx=CTX_A, case_id=CASE_A):
    record, _ = workflows().start_workflow(
        ctx, case_id, shipment_id=SHIPMENT_A)
    return record


def progress_record(record, ctx=CTX_A):
    for op in ("provide_information", "note_evidence_pending",
               "record_applicability"):
        record, _ = getattr(workflows(), op)(ctx, record)
    return record


def run_record(record, rag, ctx=CTX_A, cases=None,
               summary="default"):
    params = {"max_context_chars": 4000}
    if summary == "default":
        params["decision_summary"] = make_summary()
    elif summary is not None:
        params["decision_summary"] = summary
    return analysis(rag).run_analysis(
        ctx, record,
        cases if cases is not None else [make_case(
            evidence_statuses=("accepted",))],
        **params)


def review_record(record, ctx=CTX_A):
    record, _ = workflows().submit_for_review(ctx, record)
    return record


def transfer(record):
    """Simulate the HTTP boundary: JSON out and back in."""
    return json.loads(json.dumps(record))


def make_bearer(subject=SUBJECT_A, secret=JWT_SECRET):
    now = datetime.now(timezone.utc)
    return pyjwt.encode(
        {"aud": "authenticated", "sub": str(subject),
         "iat": now, "exp": now + timedelta(hours=1)},
        secret, algorithm="HS256")


class ActorIdentityTests(unittest.TestCase):
    def test_no_credentials_yields_no_actor(self):
        self.assertIsNone(get_request_actor(
            authorization=None, x_development_tenant_id=None))

    def test_development_header_yields_no_actor(self):
        self.assertIsNone(get_request_actor(
            authorization=None,
            x_development_tenant_id=str(TENANT_A.tenant_id)))

    def test_production_development_header_disabled(self):
        old = os.environ.get("APP_ENV")
        os.environ["APP_ENV"] = "production"
        try:
            with self.assertRaises(Exception) as raised:
                get_request_actor(
                    authorization=None,
                    x_development_tenant_id=str(
                        TENANT_A.tenant_id))
            self.assertEqual(
                raised.exception.code,
                "development_tenant_context_disabled")
        finally:
            if old is None:
                del os.environ["APP_ENV"]
            else:
                os.environ["APP_ENV"] = old

    def test_bearer_yields_subject(self):
        old = os.environ.get("SUPABASE_JWT_SECRET")
        os.environ["SUPABASE_JWT_SECRET"] = JWT_SECRET
        try:
            self.assertEqual(
                get_request_actor(
                    authorization="Bearer " + make_bearer(),
                    x_development_tenant_id=None),
                SUBJECT_A)
        finally:
            if old is None:
                del os.environ["SUPABASE_JWT_SECRET"]
            else:
                os.environ["SUPABASE_JWT_SECRET"] = old

    def test_garbage_bearer_fails_closed(self):
        old = os.environ.get("SUPABASE_JWT_SECRET")
        os.environ["SUPABASE_JWT_SECRET"] = JWT_SECRET
        try:
            with self.assertRaises(AuthenticationError):
                get_request_actor(
                    authorization="Bearer not.a.token",
                    x_development_tenant_id=None)
        finally:
            if old is None:
                del os.environ["SUPABASE_JWT_SECRET"]
            else:
                os.environ["SUPABASE_JWT_SECRET"] = old

    def test_use_cases_accept_actor_context(self):
        rag = FakeRAGService()
        record = start_record(ACTOR_CTX_A)
        record = transfer(record)
        record = progress_record(record, ACTOR_CTX_A)
        record, result, _ = run_record(record, rag, ACTOR_CTX_A)
        record = transfer(review_record(record, ACTOR_CTX_A))
        record, package = workflows().finalize_package(
            ACTOR_CTX_A, record, result)
        self.assertEqual(record["state"],
                         "assessment_package_ready")
        self.assertEqual(str(package.workflow_id),
                         record["id"])

    def test_actor_flows_through_api_without_breaking(self):
        app = create_app(services=SimpleNamespace(rag=None))
        app.dependency_overrides[get_request_actor] = (
            lambda: SUBJECT_A)
        with TestClient(app) as client:
            response = client.post(
                "/compliance/workflows/start",
                headers={"X-Development-Tenant-ID": str(
                    TENANT_A.tenant_id)},
                json={"case_id": str(CASE_A),
                      "shipment_id": str(SHIPMENT_A)})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json()["summary"]["tenant_id"],
            str(TENANT_A.tenant_id))

    def test_body_actor_id_rejected(self):
        with TestClient(create_app(
                services=SimpleNamespace(rag=None))) as client:
            response = client.post(
                "/compliance/workflows/start",
                headers={"X-Development-Tenant-ID": str(
                    TENANT_A.tenant_id)},
                json={"case_id": str(CASE_A),
                      "actor_id": str(SUBJECT_A)})
        self.assertEqual(response.status_code, 422)

    def test_tenant_role_still_server_derived(self):
        app = create_app(services=SimpleNamespace(rag=None))
        app.dependency_overrides[get_request_actor] = (
            lambda: SUBJECT_A)
        app.dependency_overrides[get_member_context] = (
            lambda: MemberContext(TENANT_B, "member"))
        with TestClient(app) as client:
            response = client.post(
                "/compliance/workflows/start",
                headers={"X-Development-Tenant-ID": str(
                    TENANT_B.tenant_id)},
                json={"case_id": str(CASE_A)})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json()["error"]["code"],
            "permission_denied")


class TransferTests(unittest.TestCase):
    def test_record_round_trip_across_calls(self):
        record = transfer(start_record())
        record = transfer(progress_record(record))
        direct = progress_record(start_record())
        self.assertEqual(record, direct)

    def test_stable_ids_resolve(self):
        first, _ = workflows().start_workflow(
            CTX_A, CASE_A, shipment_id=SHIPMENT_A)
        second, _ = workflows().start_workflow(
            CTX_A, CASE_A, shipment_id=SHIPMENT_A)
        self.assertEqual(first["id"], second["id"])

    def test_tampered_record_fails_closed(self):
        record = start_record()
        record["tenant_id"] = str(TENANT_B.tenant_id)
        before = dict(record)
        with self.assertRaises(TenantMismatchError):
            workflows().provide_information(CTX_A, record)
        self.assertEqual(record, before)


class ResultLifecycleTests(unittest.TestCase):
    def _two_rounds(self):
        rag = FakeRAGService(texts=[
            "The filing is required [E1].",
            "A certificate filing is required [E1].",
        ])
        record = progress_record(start_record())
        record, first, _ = run_record(record, rag)
        record = review_record(transfer(record))
        record, _ = workflows().request_additional_evidence(
            CTX_A, record, [requirement_id(1)])
        record, _ = workflows().supply_evidence(
            CTX_A, record, EVIDENCE_ID)
        record, second, _ = run_record(record, rag)
        return record, first, second

    def test_divergent_texts_yield_distinct_rounds(self):
        record, first, second = self._two_rounds()
        self.assertNotEqual(first.report.id, second.report.id)
        self.assertEqual(len(record["rounds"]), 2)

    def test_stale_result_cannot_finalize(self):
        record, first, second = self._two_rounds()
        record = review_record(transfer(record))
        with self.assertRaises(StaleAnalysisError) as raised:
            workflows().finalize_package(CTX_A, record, first)
        self.assertTrue(any(
            code == "analysis_stale"
            for code, _ in raised.exception.reasons))
        record, package = workflows().finalize_package(
            CTX_A, record, second)
        self.assertEqual(package.report.report_id,
                         str(second.report.id))

    def test_supply_invalidates_prior_result(self):
        rag = FakeRAGService()
        record = progress_record(start_record())
        record, first, _ = run_record(record, rag)
        record = review_record(transfer(record))
        record, _ = workflows().request_additional_evidence(
            CTX_A, record, [requirement_id(1)])
        record, _ = workflows().supply_evidence(
            CTX_A, record, EVIDENCE_ID)
        readiness = workflows().check_readiness(
            CTX_A, transfer(record), first)
        self.assertFalse(readiness.ready)

    def test_terminal_holds_across_transfer(self):
        rag = FakeRAGService()
        record = progress_record(start_record())
        record, result, _ = run_record(record, rag)
        record = review_record(transfer(record))
        record, _ = workflows().finalize_package(
            CTX_A, record, result)
        moved = transfer(record)
        self.assertTrue(workflows().is_closed(CTX_A, moved))
        with self.assertRaises(TerminalWorkflowError):
            workflows().supply_evidence(
                CTX_A, moved, EVIDENCE_ID)
        with self.assertRaises(TerminalWorkflowError):
            analysis(rag).run_analysis(
                CTX_A, moved, [make_case()],
                max_context_chars=4000)
        with self.assertRaises(TerminalWorkflowError):
            workflows().finalize_package(CTX_A, moved, result)

    def test_prior_result_unmutated_by_new_analysis(self):
        record, first, second = self._two_rounds()
        self.assertEqual(len(first.analyses), 1)
        self.assertNotEqual(first.report.id, second.report.id)

    def test_round_linkage_survives_transfer(self):
        record, _, second = self._two_rounds()
        moved = transfer(record)
        self.assertEqual(
            moved["rounds"][-1]["report_id"],
            str(second.report.id))


class FinalizationTests(unittest.TestCase):
    def test_finalize_consumes_current_result_only(self):
        rag = FakeRAGService()
        record = progress_record(start_record())
        record, result, _ = run_record(record, rag)
        record = review_record(transfer(record))
        record, package = workflows().finalize_package(
            CTX_A, record, result)
        self.assertEqual(
            [str(a) for a in
             package.open_requirements], [])
        self.assertEqual(package.report.report_id,
                         str(result.report.id))

    def test_readiness_still_gates(self):
        rag = FakeRAGService()
        record = progress_record(start_record())
        record, result, _ = run_record(record, rag)
        with self.assertRaises(WorkflowNotReadyError) as raised:
            workflows().finalize_package(
                CTX_A, transfer(record), result)
        self.assertTrue(raised.exception.reasons)

    def test_second_finalize_impossible_across_transfer(self):
        rag = FakeRAGService()
        record = progress_record(start_record())
        record, result, _ = run_record(record, rag)
        record = review_record(transfer(record))
        record, _ = workflows().finalize_package(
            CTX_A, record, result)
        with self.assertRaises(TerminalWorkflowError):
            workflows().finalize_package(
                CTX_A, transfer(record), result)


class ProvenanceTests(unittest.TestCase):
    def test_source_refs_survive_transfer_journey(self):
        rag = FakeRAGService()
        record = progress_record(start_record())
        record, _, report = run_record(record, rag)
        report = transfer(report.to_dict())
        finding = report["findings"][0]
        self.assertTrue(finding["sources"])
        self.assertTrue(all(
            "identifier" in source or "source_id" in source
            for source in finding["sources"]))

    def test_summary_authority_unchanged(self):
        rag = FakeRAGService()
        summary = make_summary()
        record = progress_record(start_record())
        record, result, _ = run_record(
            record, rag, summary=summary)
        record = review_record(transfer(record))
        _, package = workflows().finalize_package(
            CTX_A, record, result)
        self.assertIs(package.decision_summary, summary)


class PrivacyTests(unittest.TestCase):
    MARKERS = ("prompt", "secret", "api_key", "password",
               "openrouter", "qdrant", "generated_text",
               "model_identifier", "input_fingerprint",
               "content_fingerprint", "answer_fingerprint",
               "chain-of-thought")

    def test_transfer_structures_carry_no_internals(self):
        rag = FakeRAGService()
        record = progress_record(transfer(start_record()))
        record, result, report = run_record(record, rag)
        transferred = transfer(record)
        report_body = json.dumps(
            transfer(report.to_dict())).lower()
        for marker in self.MARKERS:
            self.assertNotIn(marker, report_body)
        record_body = json.dumps(transferred).lower()
        for marker in ("prompt", "secret", "api_key", "password",
                       "openrouter", "qdrant", "generated_text",
                       "model_identifier", "chain-of-thought"):
            self.assertNotIn(marker, record_body)
        # The sole fingerprint occurrence in a workflow
        # record is the round linkage the domain itself
        # requires for rehydration — round identity, not
        # provider internals.
        self.assertNotIn("content_fingerprint", record_body)
        self.assertNotIn("answer_fingerprint", record_body)

    def test_domain_receives_tenant_context_only(self):
        from xportra.domain.compliance_workflow import (
            ComplianceWorkflowService,
        )

        seen = []

        class RecordingService(ComplianceWorkflowService):
            def begin(self, *, tenant_id, case_id,
                      shipment_id=None):
                seen.append(tenant_id)
                return super().begin(
                    tenant_id=tenant_id, case_id=case_id,
                    shipment_id=shipment_id)

        service = WorkflowApplicationService(
            workflow_service=RecordingService())
        service.start_workflow(
            ACTOR_CTX_A, CASE_A, shipment_id=SHIPMENT_A)
        self.assertEqual(len(seen), 1)
        self.assertIsInstance(seen[0], TenantContext)
        self.assertEqual(seen[0].tenant_id, TENANT_A.tenant_id)


class TenantMatrixTests(unittest.TestCase):
    def _tenant_b_result(self):
        import dataclasses

        rag = FakeRAGService()
        record = progress_record(start_record())
        _, result, _ = run_record(record, rag)
        return dataclasses.replace(
            result, tenant_id=TENANT_B.tenant_id)

    def test_a_result_with_b_record_rejected(self):
        rag = FakeRAGService()
        record_b = progress_record(
            start_record(CTX_A, CASE_B))
        record_b, result_b, _ = run_record(record_b, rag)
        record_a = progress_record(start_record(CTX_A, CASE_A))
        before = transfer(record_a)
        with self.assertRaises(WorkflowNotReadyError):
            workflows().finalize_package(
                CTX_A, transfer(record_a), result_b)
        self.assertEqual(record_a, before)

    def test_b_result_with_a_record_rejected(self):
        rag = FakeRAGService()
        record = progress_record(start_record())
        record, _, _ = run_record(record, rag)
        record = review_record(transfer(record))
        foreign = self._tenant_b_result()
        with self.assertRaises(WorkflowNotReadyError) as raised:
            workflows().finalize_package(
                CTX_A, transfer(record), foreign)
        self.assertTrue(any(
            code == "tenant_mismatch"
            for code, _ in raised.exception.reasons))

    def test_b_actor_with_a_record_rejected(self):
        record = start_record()
        before = transfer(record)
        with self.assertRaises(TenantMismatchError):
            workflows().provide_information(CTX_B, record)
        self.assertEqual(record, before)

    def test_auth_failure_propagates_untouched(self):
        from xportra.application import EvidenceApplicationService

        class DenyingEvidenceService:
            def record(self, *args, **kwargs):
                raise ApplicationAuthorizationError("denied")

            def get(self, *args, **kwargs):
                raise ApplicationAuthorizationError("denied")

        service = EvidenceApplicationService(
            evidence_service=DenyingEvidenceService())
        with self.assertRaises(ApplicationAuthorizationError):
            service.record_evidence(
                CTX_A, document_title="title",
                document_type="certificate",
                file_reference_or_uri="uri://doc")


class ConcurrencyTests(unittest.TestCase):
    def test_same_base_double_analysis_diverges_safely(self):
        rag_a = FakeRAGService(
            texts=["The filing is required [E1]."])
        rag_b = FakeRAGService(
            texts=["A certificate filing is required [E1]."])
        base = transfer(progress_record(start_record()))
        record_a, _, _ = run_record(dict(base), rag_a)
        record_b, _, _ = run_record(dict(base), rag_b)
        self.assertNotEqual(
            record_a["rounds"][0]["report_id"],
            record_b["rounds"][0]["report_id"])
        for service in (workflows(), analysis(rag_a)):
            self.assertNotIn("rounds", service.__dict__)
            self.assertNotIn("workflow", service.__dict__)

    def test_loser_finalize_rejected(self):
        rag_a = FakeRAGService(
            texts=["The filing is required [E1]."])
        rag_b = FakeRAGService(
            texts=["A certificate filing is required [E1]."])
        base = transfer(progress_record(start_record()))
        record_a, result_a, _ = run_record(dict(base), rag_a)
        record_b, _, _ = run_record(dict(base), rag_b)
        reviewed_b = review_record(transfer(record_b))
        with self.assertRaises(StaleAnalysisError):
            workflows().finalize_package(
                CTX_A, reviewed_b, result_a)
        reviewed_a = review_record(transfer(record_a))
        finalized, _ = workflows().finalize_package(
            CTX_A, reviewed_a, result_a)
        self.assertTrue(workflows().is_closed(
            CTX_A, transfer(finalized)))

    def test_cross_tenant_requests_stay_isolated(self):
        record_a = transfer(start_record())
        record_b = transfer(start_record(CTX_B, CASE_B))
        with self.assertRaises(TenantMismatchError):
            workflows().provide_information(CTX_B, record_a)
        with self.assertRaises(TenantMismatchError):
            workflows().provide_information(CTX_A, record_b)
        self.assertEqual(record_a["tenant_id"],
                         str(TENANT_A.tenant_id))
        self.assertEqual(record_b["tenant_id"],
                         str(TENANT_B.tenant_id))


if __name__ == "__main__":
    unittest.main()
