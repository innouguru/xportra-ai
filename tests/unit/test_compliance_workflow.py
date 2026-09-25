"""Phase 7.1 — Compliance user workflow contract tests.

Covers ``ComplianceWorkflowService``: explicit process-state
progression separated from regulatory truth, the iterative
evidence/re-analysis loop with distinguishable rounds,
delegation to the existing Phase 6 composition boundary,
tenant/case isolation, fail-closed failure behavior, and the
verdict-free final assessment package.

Only the RAG/provider boundary is faked. Cases, validation,
and every Phase 6 service are real. No Phase 1–6 test is
modified.
"""

import ast
import json
import unittest
from uuid import UUID

from xportra.domain.answer_validation import CitationAwareAnswerValidator
from xportra.domain.compliance_workflow import (
    WORKFLOW_STATES,
    WORKFLOW_STATE_ADDITIONAL_EVIDENCE_REQUESTED,
    WORKFLOW_STATE_ANALYSIS_AVAILABLE,
    WORKFLOW_STATE_APPLICABILITY_DETERMINED,
    WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY,
    WORKFLOW_STATE_CREATED,
    WORKFLOW_STATE_EVIDENCE_PENDING,
    WORKFLOW_STATE_INFORMATION_PROVIDED,
    WORKFLOW_STATE_REANALYSIS_REQUIRED,
    WORKFLOW_STATE_REVIEW_REQUIRED,
    AssessmentPackage,
    ComplianceWorkflow,
    ComplianceWorkflowError,
    ComplianceWorkflowService,
)
from xportra.domain.errors import (
    DomainValidationError,
    LLMProviderError,
    VectorStoreError,
)
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
from xportra.domain.reasoning_application import (
    ComplianceReasoningApplication,
)
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
TENANT = TenantContext(TENANT_ID)
OTHER_TENANT = TenantContext(OTHER_TENANT_ID)
CASE_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
OTHER_CASE_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
SHIPMENT_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
DOCUMENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

SERVICE = ComplianceWorkflowService()
PROMPT_CONFIG = EvidencePromptConfig(
    system_instructions="Explain the compliance position."
)


def requirement_id(index):
    return UUID(f"00000000-0000-0000-0000-{index:012d}")


def make_knowledge_evidence(**overrides):
    kwargs = dict(
        tenant_id=TENANT_ID,
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
                           contents=("Exporters must file the form.",),
                           tenant_id=TENANT_ID):
    if contents:
        candidates = []
        for index, content in enumerate(contents):
            evidence = make_knowledge_evidence(
                content=content,
                tenant_id=tenant_id,
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
            ranked,
            tenant_id=TenantContext(tenant_id),
            budget=EvidenceContextBudget(4000))
    else:
        selection = DeterministicContextSelector().select(
            [],
            tenant_id=TenantContext(tenant_id),
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
        tenant_id=TenantContext(tenant_id))
    return CitationAwareAnswerValidator().validate(answer)


def make_case(index=1, applicability="applicable",
              assessment="satisfied", evidence_statuses=(),
              assessment_reason="required evidence present"):
    req_id = requirement_id(index)
    records = []
    for slot, status in enumerate(evidence_statuses):
        records.append(EvidenceRecord(
            tenant_id=TENANT_ID,
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
        "tenant_id": TENANT_ID,
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
            "tenant_id": TENANT_ID,
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


def make_summary(tenant_id=TENANT_ID):
    return {
        "tenant_id": tenant_id,
        "context_fingerprint": "fp-context",
        "status": "decision_summary",
        "applicability": {"total_requirements": 1},
        "risk": {"classified_count": 0},
        "actions": {"recommendation_count": 0},
    }


class FakeRAGService:
    def __init__(self, answers=None, failure=None):
        self._answers = list(answers or [make_validated_answer()])
        self._failure = failure
        self.calls = []

    def query(self, information_need, *, tenant_id, mode,
              context_budget, scope=None, top_k=5,
              candidate_pool=None):
        self.calls.append(information_need)
        if self._failure is not None:
            raise self._failure
        if len(self._answers) > 1:
            return self._answers.pop(0)
        return self._answers[0]


class RecordingApplication(ComplianceReasoningApplication):
    def __init__(self):
        super().__init__()
        self.calls = []

    def analyze_case(self, cases, **kwargs):
        self.calls.append((list(cases), dict(kwargs)))
        return super().analyze_case(cases, **kwargs)


def begin(shipment_id=SHIPMENT_ID):
    if shipment_id == "omit":
        return SERVICE.begin(tenant_id=TENANT, case_id=CASE_ID)
    return SERVICE.begin(
        tenant_id=TENANT, case_id=CASE_ID,
        shipment_id=shipment_id)


def ready_workflow():
    workflow = begin()
    workflow = SERVICE.provide_information(
        workflow, tenant_id=TENANT)
    workflow = SERVICE.note_evidence_pending(
        workflow, tenant_id=TENANT)
    return SERVICE.record_applicability_determined(
        workflow, tenant_id=TENANT)


def run_first(workflow=None, cases=None, rag=None, summary="default"):
    workflow = workflow if workflow is not None else ready_workflow()
    cases = cases if cases is not None else [make_case(
        evidence_statuses=("accepted",))]
    params = {
        "tenant_id": TENANT,
        "rag_service": rag or FakeRAGService(),
        "mode": "hybrid",
        "context_budget": EvidenceContextBudget(4000),
    }
    if summary == "default":
        params["decision_summary"] = make_summary()
    elif summary is not None:
        params["decision_summary"] = summary
    return SERVICE.run_analysis(workflow, cases, **params)


class CreationTests(unittest.TestCase):
    def test_valid_begin_enters_initial_state(self):
        workflow = begin()
        self.assertIsInstance(workflow, ComplianceWorkflow)
        self.assertEqual(workflow.state, WORKFLOW_STATE_CREATED)
        self.assertEqual(workflow.tenant_id, TENANT_ID)
        self.assertEqual(workflow.case_id, CASE_ID)
        self.assertEqual(workflow.shipment_id, SHIPMENT_ID)
        self.assertEqual(workflow.rounds, ())

    def test_begin_without_shipment(self):
        workflow = begin(shipment_id="omit")
        self.assertIsNone(workflow.shipment_id)
        self.assertEqual(workflow.state, WORKFLOW_STATE_CREATED)

    def test_begin_identity_is_deterministic(self):
        self.assertEqual(begin().id, begin().id)

    def test_invalid_tenant_fails(self):
        with self.assertRaises(DomainValidationError):
            SERVICE.begin(
                tenant_id="not-a-context", case_id=CASE_ID)

    def test_invalid_case_identity_fails(self):
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.begin(tenant_id=TENANT, case_id="not-a-uuid")

    def test_invalid_shipment_identity_fails(self):
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.begin(
                tenant_id=TENANT, case_id=CASE_ID,
                shipment_id="not-a-uuid")

    def test_non_workflow_input_fails(self):
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.provide_information(
                {"state": "created"}, tenant_id=TENANT)


class ProgressionTests(unittest.TestCase):
    def test_full_progression_to_package_ready(self):
        workflow, result = run_first()
        self.assertEqual(
            workflow.state, WORKFLOW_STATE_ANALYSIS_AVAILABLE)
        workflow = SERVICE.submit_for_review(
            workflow, tenant_id=TENANT)
        self.assertEqual(workflow.state, WORKFLOW_STATE_REVIEW_REQUIRED)
        workflow, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        self.assertEqual(
            workflow.state,
            WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY)
        self.assertIsInstance(package, AssessmentPackage)

    def test_run_analysis_from_created_fails(self):
        rag = FakeRAGService()
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.run_analysis(
                begin(), [make_case()], tenant_id=TENANT,
                rag_service=rag, mode="hybrid",
                context_budget=EvidenceContextBudget(4000),
                decision_summary=make_summary())
        self.assertEqual(rag.calls, [])

    def test_finalize_from_analysis_available_fails(self):
        workflow, result = run_first()
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.finalize(workflow, result, tenant_id=TENANT)

    def test_terminal_state_has_no_outgoing_transition(self):
        workflow, result = run_first()
        workflow = SERVICE.submit_for_review(
            workflow, tenant_id=TENANT)
        workflow, _ = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.submit_for_review(workflow, tenant_id=TENANT)
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.supply_evidence(
                workflow, tenant_id=TENANT,
                evidence_ids=[UUID(
                    "66666666-6666-6666-0000-000000000001")])

    def test_regulatory_truth_is_not_workflow_state(self):
        forbidden = {"compliant", "non_compliant", "satisfied",
                     "not_satisfied", "unknown", "applicable",
                     "not_applicable", "low", "medium", "high"}
        self.assertTrue(forbidden.isdisjoint(WORKFLOW_STATES))
        self.assertEqual(len(WORKFLOW_STATES), 9)


class EvidenceLoopTests(unittest.TestCase):
    def test_evidence_loop_produces_distinct_rounds(self):
        workflow, first = run_first(cases=[make_case(
            1, assessment="unknown", evidence_statuses=(),
            assessment_reason="required evidence absent")])
        self.assertEqual(workflow.rounds[0].round_index, 1)
        workflow = SERVICE.submit_for_review(
            workflow, tenant_id=TENANT)
        workflow = SERVICE.request_additional_evidence(
            workflow, tenant_id=TENANT,
            requirement_ids=[requirement_id(1)])
        self.assertEqual(
            workflow.state,
            WORKFLOW_STATE_ADDITIONAL_EVIDENCE_REQUESTED)
        self.assertEqual(
            workflow.open_requirements, (requirement_id(1),))
        new_evidence = UUID("66666666-6666-6666-0000-000000000001")
        workflow = SERVICE.supply_evidence(
            workflow, tenant_id=TENANT,
            evidence_ids=[new_evidence])
        self.assertEqual(
            workflow.state, WORKFLOW_STATE_REANALYSIS_REQUIRED)
        self.assertIn(new_evidence, workflow.supplied_evidence_ids)
        workflow, second = SERVICE.run_analysis(
            workflow, [make_case(1, evidence_statuses=("accepted",))],
            tenant_id=TENANT, rag_service=FakeRAGService(),
            mode="hybrid",
            context_budget=EvidenceContextBudget(4000),
            decision_summary=make_summary())
        self.assertEqual(len(workflow.rounds), 2)
        self.assertEqual(workflow.rounds[1].round_index, 2)
        self.assertNotEqual(workflow.rounds[1].report_id,
                            workflow.rounds[0].report_id)
        self.assertNotEqual(
            workflow.rounds[1].input_fingerprints,
            workflow.rounds[0].input_fingerprints)
        self.assertEqual(second.analyses[0].assessment, "satisfied")

    def test_existing_round_is_not_silently_mutated(self):
        workflow = ready_workflow()
        advanced, _ = run_first(workflow=workflow)
        self.assertEqual(workflow.rounds, ())
        self.assertEqual(
            workflow.state,
            WORKFLOW_STATE_APPLICABILITY_DETERMINED)
        self.assertEqual(len(advanced.rounds), 1)

    def test_evidence_request_requires_requirements(self):
        workflow, _ = run_first()
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.request_additional_evidence(
                workflow, tenant_id=TENANT, requirement_ids=[])
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.request_additional_evidence(
                workflow, tenant_id=TENANT,
                requirement_ids=["not-a-uuid"])

    def test_supply_evidence_requires_evidence(self):
        workflow, _ = run_first()
        workflow = SERVICE.submit_for_review(
            workflow, tenant_id=TENANT)
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.supply_evidence(
                workflow, tenant_id=TENANT, evidence_ids=[])

    def test_missing_evidence_remains_explicit(self):
        workflow, result = run_first(cases=[make_case(
            1, assessment="unknown", evidence_statuses=(),
            assessment_reason="required evidence absent")])
        self.assertTrue(
            result.analyses[0].missing_information)
        workflow = SERVICE.submit_for_review(
            workflow, tenant_id=TENANT)
        workflow, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        self.assertIn(requirement_id(1),
                      package.open_requirements)


class Phase6IntegrationTests(unittest.TestCase):
    def test_workflow_delegates_to_phase6_boundary(self):
        recorder = RecordingApplication()
        service = ComplianceWorkflowService(
            reasoning_application=recorder)
        workflow = ready_workflow()
        cases = [make_case(evidence_statuses=("accepted",))]
        advanced, result = service.run_analysis(
            workflow, cases, tenant_id=TENANT,
            rag_service=FakeRAGService(), mode="hybrid",
            context_budget=EvidenceContextBudget(4000),
            decision_summary=make_summary())
        self.assertEqual(len(recorder.calls), 1)
        sent_cases, sent_kwargs = recorder.calls[0]
        self.assertEqual(sent_cases, cases)
        self.assertEqual(sent_kwargs["case_id"], CASE_ID)
        self.assertEqual(
            advanced.rounds[0].report_id, result.report.id)
        self.assertEqual(
            [t.id for t in result.traces],
            list(advanced.rounds[0].trace_ids))

    def test_phase6_result_preserved_by_identity(self):
        recorder = RecordingApplication()
        service = ComplianceWorkflowService(
            reasoning_application=recorder)
        _, result = service.run_analysis(
            ready_workflow(), [make_case()], tenant_id=TENANT,
            rag_service=FakeRAGService(), mode="hybrid",
            context_budget=EvidenceContextBudget(4000),
            decision_summary=make_summary())
        self.assertEqual(len(result.analyses), 1)
        self.assertEqual(result.report.total_requirements, 1)
        self.assertEqual(len(result.traces), 1)

    def test_missing_reasoning_application_rejected(self):
        with self.assertRaises(ComplianceWorkflowError):
            ComplianceWorkflowService(
                reasoning_application=object())


class IsolationTests(unittest.TestCase):
    def test_cross_tenant_operation_rejected(self):
        workflow = begin()
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.provide_information(
                workflow, tenant_id=OTHER_TENANT)
        workflow, _ = run_first()
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.submit_for_review(
                workflow, tenant_id=OTHER_TENANT)

    def test_cross_case_result_rejected(self):
        workflow, result = run_first()
        self.assertEqual(result.case_id, CASE_ID)
        other_workflow = SERVICE.begin(
            tenant_id=TENANT, case_id=OTHER_CASE_ID)
        other_workflow = SERVICE.provide_information(
            other_workflow, tenant_id=TENANT)
        other_workflow = SERVICE.note_evidence_pending(
            other_workflow, tenant_id=TENANT)
        other_workflow = (
            SERVICE.record_applicability_determined(
                other_workflow, tenant_id=TENANT))
        other_workflow = SERVICE.submit_for_review(
            SERVICE.run_analysis(
                other_workflow, [make_case()],
                tenant_id=TENANT, rag_service=FakeRAGService(),
                mode="hybrid",
                context_budget=EvidenceContextBudget(4000),
                decision_summary=make_summary())[0],
            tenant_id=TENANT)
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.finalize(
                other_workflow, result, tenant_id=TENANT)

    def test_finalize_requires_latest_round(self):
        workflow, first = run_first(cases=[make_case(
            1, assessment="unknown", evidence_statuses=(),
            assessment_reason="required evidence absent")])
        workflow = SERVICE.submit_for_review(
            workflow, tenant_id=TENANT)
        workflow = SERVICE.request_additional_evidence(
            workflow, tenant_id=TENANT,
            requirement_ids=[requirement_id(1)])
        workflow = SERVICE.supply_evidence(
            workflow, tenant_id=TENANT,
            evidence_ids=[UUID(
                "66666666-6666-6666-0000-000000000001")])
        workflow, _ = SERVICE.run_analysis(
            workflow, [make_case(1, evidence_statuses=("accepted",))],
            tenant_id=TENANT, rag_service=FakeRAGService(),
            mode="hybrid",
            context_budget=EvidenceContextBudget(4000),
            decision_summary=make_summary())
        workflow = SERVICE.submit_for_review(
            workflow, tenant_id=TENANT)
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.finalize(workflow, first, tenant_id=TENANT)


class FailureBehaviorTests(unittest.TestCase):
    def test_invalid_cases_prevent_provider_invocation(self):
        rag = FakeRAGService()
        with self.assertRaises(DomainValidationError):
            SERVICE.run_analysis(
                ready_workflow(), [{"nope": True}],
                tenant_id=TENANT, rag_service=rag, mode="hybrid",
                context_budget=EvidenceContextBudget(4000),
                decision_summary=make_summary())
        self.assertEqual(rag.calls, [])

    def test_retrieval_failure_propagates_without_result(self):
        rag = FakeRAGService(failure=VectorStoreError(
            "find", RuntimeError("index down")))
        with self.assertRaises(VectorStoreError):
            run_first(rag=rag)

    def test_provider_failure_propagates_without_result(self):
        rag = FakeRAGService(failure=LLMProviderError(
            "generate", RuntimeError("provider down")))
        with self.assertRaises(LLMProviderError):
            run_first(rag=rag)

    def test_analysis_failure_produces_no_workflow_result(self):
        class BrokenApp(ComplianceReasoningApplication):
            def analyze_case(self, cases, **kwargs):
                raise LLMProviderError(
                    "generate", RuntimeError("provider down"))

        service = ComplianceWorkflowService(
            reasoning_application=BrokenApp())
        with self.assertRaises(LLMProviderError):
            service.run_analysis(
                ready_workflow(), [make_case()], tenant_id=TENANT,
                rag_service=FakeRAGService(), mode="hybrid",
                context_budget=EvidenceContextBudget(4000),
                decision_summary=make_summary())


class FinalPackageTests(unittest.TestCase):
    def test_package_preserves_authoritative_summary(self):
        summary = make_summary()
        workflow, result = run_first(summary=summary)
        workflow = SERVICE.submit_for_review(
            workflow, tenant_id=TENANT)
        final_workflow, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        self.assertIs(package.decision_summary, summary)
        self.assertIs(package.reasoning_result, result)
        self.assertEqual(package.rounds, final_workflow.rounds)
        self.assertEqual(len(package.rounds), 1)

    def test_package_preserves_provenance(self):
        workflow, result = run_first(
            cases=[make_case(evidence_statuses=("accepted",))],
            summary=None)
        workflow = SERVICE.submit_for_review(
            workflow, tenant_id=TENANT)
        _, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        self.assertEqual(package.workflow_id, workflow.id)
        self.assertEqual(package.case_id, CASE_ID)
        self.assertEqual(package.shipment_id, SHIPMENT_ID)
        self.assertEqual(len(package.rounds), 1)
        self.assertEqual(
            package.rounds[0].report_id, result.report.id)
        self.assertEqual(
            [str(v) for v in package.rounds[0].analysis_ids],
            [str(a.id) for a in result.analyses])
        body = json.loads(json.dumps(package.to_record()))
        self.assertEqual(body["state"],
                         WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY)

    def test_package_contains_no_new_verdict(self):
        workflow, result = run_first(summary=None)
        workflow = SERVICE.submit_for_review(
            workflow, tenant_id=TENANT)
        _, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        self.assertFalse(hasattr(package, "verdict"))
        self.assertFalse(hasattr(package, "overall_status"))
        self.assertFalse(hasattr(package, "score"))
        body = json.dumps(package.to_record()).lower()
        for marker in ("verdict", "overall", "compliant",
                       "score", "percent"):
            self.assertNotIn(marker, body)


class FrameworkBoundaryTests(unittest.TestCase):
    def test_workflow_module_has_no_infra_imports(self):
        import pathlib

        path = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "domain" / "compliance_workflow.py")
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(
                    alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.level == 0:
                    modules.add(node.module.split(".")[0])
        self.assertTrue(modules.isdisjoint(
            {"fastapi", "starlette", "qdrant_client", "openai",
             "anthropic", "httpx", "xportra"}))
        self.assertIn("dataclasses", modules)

    def test_workflow_contains_no_duplicate_reasoning_logic(self):
        import pathlib

        text = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "domain"
                / "compliance_workflow.py").read_text(
                    encoding="utf-8")
        for marker in ("QdrantClient", "SentenceTransformer",
                       "OpenRouter", "httpx.", "EmbeddingProvider",
                       ".retrieve(", ".generate(", ".query(",
                       "RAGApplicationService",
                       "RegulatoryRequirementApplicability",
                       "RequirementAssessmentService"):
            self.assertNotIn(marker, text)


if __name__ == "__main__":
    unittest.main()
