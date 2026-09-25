"""Phase 7.3 — Workflow-to-assessment readiness tests.

Covers ``AssessmentReadinessService`` and its integration
into ``ComplianceWorkflowService.finalize``: process
readiness separated from regulatory truth, stale-analysis
handling, unresolved findings remaining finalizable,
tenant/case/shipment/analysis isolation, fail-closed failure
behavior, and the verdict-free final assessment package.

Only the RAG/provider boundary is faked. Cases, validation,
and every Phase 6 service are real. No Phase 1–7.2 test is
modified.
"""

import ast
import json
import unittest
from dataclasses import replace
from uuid import UUID

from xportra.domain.answer_validation import CitationAwareAnswerValidator
from xportra.domain.assessment_readiness import (
    READINESS_ANALYSIS_INTEGRITY_FAILURE,
    READINESS_ANALYSIS_STALE,
    READINESS_CASE_MISMATCH,
    READINESS_INVALID_WORKFLOW_STATE,
    READINESS_MISSING_SHIPMENT_REFERENCE,
    READINESS_NO_ANALYSIS,
    READINESS_TENANT_MISMATCH,
    AssessmentReadinessService,
)
from xportra.domain.compliance_workflow import (
    WORKFLOW_STATE_ANALYSIS_AVAILABLE,
    WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY,
    WORKFLOW_STATE_REANALYSIS_REQUIRED,
    WORKFLOW_STATE_REVIEW_REQUIRED,
    ComplianceWorkflowError,
    ComplianceWorkflowService,
)
from xportra.domain.errors import (
    DomainValidationError,
    LLMProviderError,
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
READINESS = AssessmentReadinessService()
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


def review_workflow(cases=None, summary="default"):
    workflow, result = run_first(cases=cases, summary=summary)
    workflow = SERVICE.submit_for_review(
        workflow, tenant_id=TENANT)
    return workflow, result


def codes(readiness):
    return [issue.code for issue in readiness.reasons]


class ReadyWorkflowTests(unittest.TestCase):
    def test_ready_workflow_reports_ready_without_reasons(self):
        workflow, result = review_workflow()
        readiness = READINESS.check(
            workflow, result, tenant_id=TENANT)
        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.reasons, ())

    def test_readiness_result_is_serializable(self):
        workflow, result = review_workflow()
        readiness = READINESS.check(
            workflow, result, tenant_id=TENANT)
        body = json.loads(json.dumps(readiness.to_record()))
        self.assertEqual(
            body, {"ready": True, "reasons": []})

    def test_finalize_succeeds_when_ready(self):
        workflow, result = review_workflow()
        final_workflow, _ = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        self.assertEqual(
            final_workflow.state,
            WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY)

    def test_absent_decision_summary_is_still_ready(self):
        workflow, result = review_workflow(summary=None)
        self.assertIsNone(result.decision_summary)
        readiness = READINESS.check(
            workflow, result, tenant_id=TENANT)
        self.assertTrue(readiness.ready)
        _, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        self.assertIsNone(package.decision_summary)

    def test_readiness_is_deterministic(self):
        workflow, result = review_workflow()
        first = READINESS.check(
            workflow, result, tenant_id=TENANT).to_record()
        second = READINESS.check(
            workflow, result, tenant_id=TENANT).to_record()
        self.assertEqual(first, second)


class MissingPrerequisiteTests(unittest.TestCase):
    def test_missing_shipment_reference_is_not_ready(self):
        workflow = begin(shipment_id="omit")
        workflow = SERVICE.provide_information(
            workflow, tenant_id=TENANT)
        workflow = SERVICE.note_evidence_pending(
            workflow, tenant_id=TENANT)
        workflow = SERVICE.record_applicability_determined(
            workflow, tenant_id=TENANT)
        workflow, result = run_first(workflow=workflow)
        workflow = SERVICE.submit_for_review(
            workflow, tenant_id=TENANT)
        readiness = READINESS.check(
            workflow, result, tenant_id=TENANT)
        self.assertFalse(readiness.ready)
        self.assertEqual(
            codes(readiness),
            [READINESS_MISSING_SHIPMENT_REFERENCE])
        with self.assertRaises(ComplianceWorkflowError) as raised:
            SERVICE.finalize(workflow, result, tenant_id=TENANT)
        self.assertIn(
            READINESS_MISSING_SHIPMENT_REFERENCE,
            str(raised.exception))

    def test_no_analysis_round_is_not_ready(self):
        workflow, result = review_workflow()
        emptied = replace(workflow, rounds=())
        readiness = READINESS.check(
            emptied, result, tenant_id=TENANT)
        self.assertFalse(readiness.ready)
        self.assertIn(
            READINESS_NO_ANALYSIS, codes(readiness))

    def test_wrong_workflow_state_is_not_ready(self):
        workflow, result = run_first()
        self.assertEqual(
            workflow.state, WORKFLOW_STATE_ANALYSIS_AVAILABLE)
        readiness = READINESS.check(
            workflow, result, tenant_id=TENANT)
        self.assertFalse(readiness.ready)
        self.assertIn(
            READINESS_INVALID_WORKFLOW_STATE, codes(readiness))
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.finalize(workflow, result, tenant_id=TENANT)

    def test_stale_analysis_is_not_ready(self):
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
        readiness = READINESS.check(
            workflow, first, tenant_id=TENANT)
        self.assertFalse(readiness.ready)
        self.assertEqual(
            codes(readiness), [READINESS_ANALYSIS_STALE])
        with self.assertRaises(ComplianceWorkflowError) as raised:
            SERVICE.finalize(workflow, first, tenant_id=TENANT)
        self.assertIn(
            READINESS_ANALYSIS_STALE, str(raised.exception))

    def test_tampered_analyses_fail_integrity(self):
        workflow, first = review_workflow(
            cases=[make_case(1, evidence_statuses=("accepted",))])
        _, second = run_first(cases=[make_case(
            2, evidence_statuses=("accepted",))])
        tampered = replace(first, analyses=second.analyses)
        readiness = READINESS.check(
            workflow, tampered, tenant_id=TENANT)
        self.assertFalse(readiness.ready)
        self.assertIn(
            READINESS_ANALYSIS_INTEGRITY_FAILURE,
            codes(readiness))
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.finalize(workflow, tampered, tenant_id=TENANT)

    def test_tampered_traces_fail_integrity(self):
        workflow, first = review_workflow(
            cases=[make_case(1, evidence_statuses=("accepted",))])
        _, second = run_first(cases=[make_case(
            2, evidence_statuses=("accepted",))])
        tampered = replace(first, traces=second.traces)
        readiness = READINESS.check(
            workflow, tampered, tenant_id=TENANT)
        self.assertFalse(readiness.ready)
        self.assertIn(
            READINESS_ANALYSIS_INTEGRITY_FAILURE,
            codes(readiness))

    def test_malformed_inputs_raise(self):
        workflow, result = review_workflow()
        with self.assertRaises(ComplianceWorkflowError):
            READINESS.check(
                {"state": "review_required"}, result,
                tenant_id=TENANT)
        with self.assertRaises(ComplianceWorkflowError):
            READINESS.check(
                workflow, {"report": {}}, tenant_id=TENANT)
        with self.assertRaises(DomainValidationError):
            READINESS.check(
                workflow, result, tenant_id="not-a-context")
        with self.assertRaises(ComplianceWorkflowError):
            READINESS.check(
                replace(workflow, state="bogus-state"), result,
                tenant_id=TENANT)


class EvidenceIterationTests(unittest.TestCase):
    def test_supplied_evidence_requires_reanalysis_before_ready(self):
        workflow, _ = run_first(cases=[make_case(
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
        self.assertEqual(
            workflow.state, WORKFLOW_STATE_REANALYSIS_REQUIRED)
        workflow, fresh = SERVICE.run_analysis(
            workflow, [make_case(1, evidence_statuses=("accepted",))],
            tenant_id=TENANT, rag_service=FakeRAGService(),
            mode="hybrid",
            context_budget=EvidenceContextBudget(4000),
            decision_summary=make_summary())
        readiness = READINESS.check(
            workflow, fresh, tenant_id=TENANT)
        self.assertFalse(readiness.ready)
        self.assertIn(
            READINESS_INVALID_WORKFLOW_STATE, codes(readiness))
        workflow = SERVICE.submit_for_review(
            workflow, tenant_id=TENANT)
        readiness = READINESS.check(
            workflow, fresh, tenant_id=TENANT)
        self.assertTrue(readiness.ready)
        final_workflow, _ = SERVICE.finalize(
            workflow, fresh, tenant_id=TENANT)
        self.assertEqual(
            final_workflow.state,
            WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY)

    def test_duplicate_supply_keeps_reanalysis_requirement(self):
        workflow, _ = run_first(cases=[make_case(
            1, assessment="unknown", evidence_statuses=(),
            assessment_reason="required evidence absent")])
        workflow = SERVICE.submit_for_review(
            workflow, tenant_id=TENANT)
        workflow = SERVICE.request_additional_evidence(
            workflow, tenant_id=TENANT,
            requirement_ids=[requirement_id(1)])
        evidence_id = UUID("66666666-6666-6666-0000-000000000001")
        workflow = SERVICE.supply_evidence(
            workflow, tenant_id=TENANT,
            evidence_ids=[evidence_id])
        workflow = SERVICE.run_analysis(
            workflow, [make_case(1, evidence_statuses=("accepted",))],
            tenant_id=TENANT, rag_service=FakeRAGService(),
            mode="hybrid",
            context_budget=EvidenceContextBudget(4000),
            decision_summary=make_summary())[0]
        workflow = SERVICE.submit_for_review(
            workflow, tenant_id=TENANT)
        workflow = SERVICE.request_additional_evidence(
            workflow, tenant_id=TENANT,
            requirement_ids=[requirement_id(1)])
        repeated = SERVICE.supply_evidence(
            workflow, tenant_id=TENANT,
            evidence_ids=[evidence_id])
        self.assertEqual(
            repeated.supplied_evidence_ids,
            workflow.supplied_evidence_ids)
        self.assertEqual(
            repeated.state, WORKFLOW_STATE_REANALYSIS_REQUIRED)


class UnresolvedFindingsTests(unittest.TestCase):
    def test_unknown_assessment_with_missing_evidence_is_ready(self):
        workflow, result = review_workflow(cases=[make_case(
            1, assessment="unknown", evidence_statuses=(),
            assessment_reason="required evidence absent")])
        self.assertTrue(result.analyses[0].missing_information)
        readiness = READINESS.check(
            workflow, result, tenant_id=TENANT)
        self.assertTrue(readiness.ready)
        _, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        self.assertIn(
            requirement_id(1), package.open_requirements)

    def test_not_satisfied_assessment_is_ready(self):
        workflow, result = review_workflow(cases=[make_case(
            1, assessment="not_satisfied",
            evidence_statuses=("rejected",),
            assessment_reason="linked evidence rejected")])
        self.assertEqual(
            result.analyses[0].assessment, "not_satisfied")
        readiness = READINESS.check(
            workflow, result, tenant_id=TENANT)
        self.assertTrue(readiness.ready)
        _, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        self.assertEqual(
            package.reasoning_result.analyses[0].assessment,
            "not_satisfied")

    def test_reasoning_fields_are_preserved_unresolved(self):
        workflow, result = review_workflow(cases=[make_case(
            1, assessment="unknown", evidence_statuses=(),
            assessment_reason="required evidence absent")])
        _, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        analysis = package.reasoning_result.analyses[0]
        self.assertEqual(
            analysis.evidence_sufficiency,
            result.analyses[0].evidence_sufficiency)
        self.assertEqual(
            analysis.contradiction_state,
            result.analyses[0].contradiction_state)
        self.assertEqual(
            analysis.uncertainty,
            result.analyses[0].uncertainty)
        self.assertEqual(
            list(analysis.missing_information),
            list(result.analyses[0].missing_information))


class IsolationTests(unittest.TestCase):
    def test_wrong_tenant_caller_is_not_ready(self):
        workflow, result = review_workflow()
        readiness = READINESS.check(
            workflow, result, tenant_id=OTHER_TENANT)
        self.assertFalse(readiness.ready)
        self.assertIn(
            READINESS_TENANT_MISMATCH, codes(readiness))
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.finalize(
                workflow, result, tenant_id=OTHER_TENANT)

    def test_result_from_another_tenant_is_not_ready(self):
        workflow, result = review_workflow()
        tampered = replace(result, tenant_id=OTHER_TENANT_ID)
        readiness = READINESS.check(
            workflow, tampered, tenant_id=TENANT)
        self.assertFalse(readiness.ready)
        self.assertIn(
            READINESS_TENANT_MISMATCH, codes(readiness))
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.finalize(
                workflow, tampered, tenant_id=TENANT)

    def test_result_from_another_case_is_not_ready(self):
        workflow, result = review_workflow()
        tampered = replace(result, case_id=OTHER_CASE_ID)
        readiness = READINESS.check(
            workflow, tampered, tenant_id=TENANT)
        self.assertFalse(readiness.ready)
        self.assertEqual(
            codes(readiness), [READINESS_CASE_MISMATCH])
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.finalize(
                workflow, tampered, tenant_id=TENANT)

    def test_shipment_presence_not_value_is_the_gate(self):
        # Shipment value integrity is established at bind time
        # by the Phase 7.2 boundary; readiness requires a bound
        # shipment reference, never a particular value.
        workflow, result = review_workflow()
        rebound = replace(workflow, shipment_id=UUID(
            "ffffffff-ffff-ffff-ffff-ffffffffffff"))
        readiness = READINESS.check(
            rebound, result, tenant_id=TENANT)
        self.assertTrue(readiness.ready)


class FailureBehaviorTests(unittest.TestCase):
    def test_failed_readiness_makes_zero_provider_calls(self):
        recorder = RecordingApplication()
        service = ComplianceWorkflowService(
            reasoning_application=recorder)
        workflow, result = run_first()
        with self.assertRaises(ComplianceWorkflowError):
            service.finalize(workflow, result, tenant_id=TENANT)
        self.assertEqual(recorder.calls, [])

    def test_failed_finalize_returns_no_partial_package(self):
        workflow, result = run_first()
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.finalize(workflow, result, tenant_id=TENANT)
        self.assertEqual(
            workflow.state, WORKFLOW_STATE_ANALYSIS_AVAILABLE)
        self.assertEqual(len(workflow.rounds), 1)

    def test_failed_analysis_cannot_produce_ready_workflow(self):
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

    def test_invalid_readiness_service_rejected(self):
        with self.assertRaises(ComplianceWorkflowError):
            ComplianceWorkflowService(readiness_service=object())

    def test_injected_readiness_service_is_honored(self):
        class ClosedGate:
            def check(self, workflow, result, *, tenant_id):
                return READINESS.check(
                    workflow, result, tenant_id=tenant_id)

        service = ComplianceWorkflowService(
            readiness_service=ClosedGate())
        workflow, result = review_workflow()
        final_workflow, _ = service.finalize(
            workflow, result, tenant_id=TENANT)
        self.assertEqual(
            final_workflow.state,
            WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY)


class FinalPackageTests(unittest.TestCase):
    def test_package_preserves_authoritative_summary(self):
        summary = make_summary()
        workflow, result = review_workflow(summary=summary)
        _, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        self.assertIs(package.decision_summary, summary)

    def test_package_preserves_phase6_provenance(self):
        workflow, result = review_workflow()
        _, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        self.assertIs(package.reasoning_result, result)
        self.assertEqual(package.rounds, workflow.rounds)
        self.assertEqual(
            package.rounds[-1].report_id, result.report.id)
        self.assertEqual(
            list(package.rounds[-1].analysis_ids),
            [a.id for a in result.analyses])
        self.assertEqual(
            list(package.rounds[-1].trace_ids),
            [t.id for t in result.traces])

    def test_package_contains_no_new_verdict(self):
        workflow, result = review_workflow(summary=None)
        _, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        self.assertFalse(hasattr(package, "verdict"))
        self.assertFalse(hasattr(package, "overall_status"))
        self.assertFalse(hasattr(package, "score"))
        body = json.dumps(package.to_record()).lower()
        for marker in ("verdict", "overall", "compliant",
                       "score", "percent"):
            self.assertNotIn(marker, body)

    def test_package_is_deterministic_and_serializable(self):
        first_flow = review_workflow()
        second_flow = review_workflow()
        _, first_package = SERVICE.finalize(
            *first_flow, tenant_id=TENANT)
        _, second_package = SERVICE.finalize(
            *second_flow, tenant_id=TENANT)
        self.assertEqual(
            first_package.to_record(), second_package.to_record())
        body = json.loads(json.dumps(
            first_package.to_record(), default=str))
        self.assertEqual(
            body["state"],
            WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY)

    def test_readiness_codes_carry_no_verdict_vocabulary(self):
        forbidden = {"compliant", "non_compliant", "pass", "fail",
                     "satisfied", "not_satisfied", "approved",
                     "rejected", "overall", "score"}
        for code in (READINESS_TENANT_MISMATCH,
                     READINESS_CASE_MISMATCH,
                     READINESS_INVALID_WORKFLOW_STATE,
                     READINESS_MISSING_SHIPMENT_REFERENCE,
                     READINESS_NO_ANALYSIS,
                     READINESS_ANALYSIS_STALE,
                     READINESS_ANALYSIS_INTEGRITY_FAILURE):
            self.assertNotIn(code, forbidden)


class FrameworkBoundaryTests(unittest.TestCase):
    def test_readiness_module_has_no_infra_imports(self):
        import pathlib

        path = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "domain" / "assessment_readiness.py")
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

    def test_readiness_module_has_no_duplicate_reasoning_logic(self):
        import pathlib

        text = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "domain"
                / "assessment_readiness.py").read_text(
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
