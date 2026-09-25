"""Phase 7.5 — Workflow closure/reopening policy tests.

Locks the explicit terminal rule: `assessment_package_ready`
is permanently closed. Every mutating operation (7.1
transitions, re-analysis, second finalization, and the 7.2
supply/bind handoff) fails closed on a finalized workflow
without mutation and — for analysis — without provider
calls. Continuation after finalization is a fresh
progression, never mutation.

Only the RAG/provider boundary is faked. Cases, validation,
and every Phase 6/7 service are real. No Phase 1–7.4 test
is modified.
"""

import unittest
from uuid import UUID

from xportra.domain.answer_validation import CitationAwareAnswerValidator
from xportra.domain.compliance_workflow import (
    WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY,
    WORKFLOW_STATE_CREATED,
    WORKFLOW_STATES,
    WORKFLOW_TERMINAL_STATES,
    ComplianceWorkflowError,
    ComplianceWorkflowService,
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
from xportra.domain.shipment_intake import (
    ShipmentIntakeError,
    ShipmentIntakeService,
)
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
TENANT = TenantContext(TENANT_ID)
OTHER_TENANT = TenantContext(OTHER_TENANT_ID)
CASE_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
SHIPMENT_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
OTHER_SHIPMENT_ID = UUID(
    "ffffffff-ffff-ffff-ffff-ffffffffffff")
DOCUMENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
EVIDENCE_ID = UUID("66666666-6666-6666-0000-000000000001")

SERVICE = ComplianceWorkflowService()
INTAKE = ShipmentIntakeService(workflow_service=SERVICE)
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


def finalize_flow(cases=None):
    workflow = SERVICE.begin(
        tenant_id=TENANT, case_id=CASE_ID,
        shipment_id=SHIPMENT_ID)
    workflow = SERVICE.provide_information(
        workflow, tenant_id=TENANT)
    workflow = SERVICE.note_evidence_pending(
        workflow, tenant_id=TENANT)
    workflow = SERVICE.record_applicability_determined(
        workflow, tenant_id=TENANT)
    cases = cases if cases is not None else [make_case(
        evidence_statuses=("accepted",))]
    workflow, result = SERVICE.run_analysis(
        workflow, cases, tenant_id=TENANT,
        rag_service=FakeRAGService(), mode="hybrid",
        context_budget=EvidenceContextBudget(4000),
        decision_summary=make_summary())
    workflow = SERVICE.submit_for_review(
        workflow, tenant_id=TENANT)
    finalized, package = SERVICE.finalize(
        workflow, result, tenant_id=TENANT)
    return finalized, package, result


class TerminalRejectionTests(unittest.TestCase):
    def test_progression_operations_rejected_after_final(self):
        workflow, _, _ = finalize_flow()
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.provide_information(
                workflow, tenant_id=TENANT)
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.note_evidence_pending(
                workflow, tenant_id=TENANT)
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.record_applicability_determined(
                workflow, tenant_id=TENANT)
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.submit_for_review(
                workflow, tenant_id=TENANT)

    def test_evidence_loop_rejected_after_final(self):
        workflow, _, _ = finalize_flow()
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.request_additional_evidence(
                workflow, tenant_id=TENANT,
                requirement_ids=[requirement_id(1)])
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.supply_evidence(
                workflow, tenant_id=TENANT,
                evidence_ids=[EVIDENCE_ID])

    def test_reanalysis_rejected_without_provider_calls(self):
        recorder = RecordingApplication()
        service = ComplianceWorkflowService(
            reasoning_application=recorder)
        workflow, _, _ = finalize_flow()
        rag = FakeRAGService()
        with self.assertRaises(ComplianceWorkflowError):
            service.run_analysis(
                workflow, [make_case()], tenant_id=TENANT,
                rag_service=rag, mode="hybrid",
                context_budget=EvidenceContextBudget(4000),
                decision_summary=make_summary())
        self.assertEqual(recorder.calls, [])
        self.assertEqual(rag.calls, [])

    def test_second_finalize_rejected(self):
        workflow, package, result = finalize_flow()
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.finalize(workflow, result, tenant_id=TENANT)
        self.assertEqual(
            workflow.state, WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY)

    def test_intake_supply_rejected_after_final(self):
        workflow, _, _ = finalize_flow()
        reference = INTAKE.reference_evidence(
            tenant_id=TENANT, evidence_id=EVIDENCE_ID,
            case_id=CASE_ID)
        with self.assertRaises(ComplianceWorkflowError):
            INTAKE.supply_to_workflow(
                workflow, reference, tenant_id=TENANT)

    def test_shipment_switch_rejected_after_final(self):
        workflow, _, _ = finalize_flow()
        reference = INTAKE.register_shipment(
            tenant_id=TENANT, shipment_id=OTHER_SHIPMENT_ID,
            case_id=CASE_ID)
        with self.assertRaises(ShipmentIntakeError):
            INTAKE.bind_shipment(
                workflow, reference, tenant_id=TENANT)

    def test_identical_rebind_is_a_no_op_after_final(self):
        workflow, _, _ = finalize_flow()
        reference = INTAKE.register_shipment(
            tenant_id=TENANT, shipment_id=SHIPMENT_ID,
            case_id=CASE_ID)
        rebound = INTAKE.bind_shipment(
            workflow, reference, tenant_id=TENANT)
        self.assertEqual(rebound, workflow)


class NoMutationTests(unittest.TestCase):
    def test_rejected_supply_changes_nothing(self):
        workflow, package, _ = finalize_flow()
        snapshot = workflow
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.supply_evidence(
                workflow, tenant_id=TENANT,
                evidence_ids=[EVIDENCE_ID])
        self.assertEqual(workflow, snapshot)
        self.assertEqual(
            workflow.supplied_evidence_ids,
            snapshot.supplied_evidence_ids)

    def test_rejected_finalize_preserves_package(self):
        workflow, package, result = finalize_flow()
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.finalize(workflow, result, tenant_id=TENANT)
        self.assertEqual(package.workflow_id, workflow.id)
        self.assertEqual(
            package.state, WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY)


class ClosureContractTests(unittest.TestCase):
    def test_terminal_states_contain_only_final_state(self):
        self.assertEqual(
            WORKFLOW_TERMINAL_STATES,
            {WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY})

    def test_is_closed_for_finalized_workflow(self):
        workflow, _, _ = finalize_flow()
        self.assertTrue(SERVICE.is_closed(
            workflow, tenant_id=TENANT))

    def test_is_closed_false_before_finalization(self):
        workflow = SERVICE.begin(
            tenant_id=TENANT, case_id=CASE_ID,
            shipment_id=SHIPMENT_ID)
        self.assertFalse(SERVICE.is_closed(
            workflow, tenant_id=TENANT))
        workflow = SERVICE.provide_information(
            workflow, tenant_id=TENANT)
        workflow = SERVICE.note_evidence_pending(
            workflow, tenant_id=TENANT)
        workflow = SERVICE.record_applicability_determined(
            workflow, tenant_id=TENANT)
        workflow, _ = SERVICE.run_analysis(
            workflow, [make_case(
                evidence_statuses=("accepted",))],
            tenant_id=TENANT, rag_service=FakeRAGService(),
            mode="hybrid",
            context_budget=EvidenceContextBudget(4000),
            decision_summary=make_summary())
        self.assertFalse(SERVICE.is_closed(
            workflow, tenant_id=TENANT))
        workflow = SERVICE.submit_for_review(
            workflow, tenant_id=TENANT)
        self.assertFalse(SERVICE.is_closed(
            workflow, tenant_id=TENANT))

    def test_is_closed_validates_tenant(self):
        workflow, _, _ = finalize_flow()
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.is_closed(workflow, tenant_id=OTHER_TENANT)
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.is_closed(
                {"state": "created"}, tenant_id=TENANT)

    def test_machine_shape_locks_closure(self):
        from xportra.domain.compliance_workflow import (
            _WORKFLOW_TRANSITIONS,
        )

        self.assertEqual(set(WORKFLOW_STATES), set(
            _WORKFLOW_TRANSITIONS))
        for state, targets in _WORKFLOW_TRANSITIONS.items():
            if state in WORKFLOW_TERMINAL_STATES:
                self.assertEqual(targets, ())
            else:
                self.assertTrue(targets)


class FindingNeutralityTests(unittest.TestCase):
    def test_closure_applies_with_unresolved_findings(self):
        workflow, package, _ = finalize_flow(cases=[make_case(
            1, assessment="unknown", evidence_statuses=(),
            assessment_reason="required evidence absent")])
        self.assertTrue(SERVICE.is_closed(
            workflow, tenant_id=TENANT))
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.supply_evidence(
                workflow, tenant_id=TENANT,
                evidence_ids=[EVIDENCE_ID])
        self.assertIn(
            requirement_id(1), package.open_requirements)

    def test_closure_applies_with_not_satisfied(self):
        workflow, _, _ = finalize_flow(cases=[make_case(
            1, assessment="not_satisfied",
            evidence_statuses=("rejected",),
            assessment_reason="linked evidence rejected")])
        self.assertTrue(SERVICE.is_closed(
            workflow, tenant_id=TENANT))
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.request_additional_evidence(
                workflow, tenant_id=TENANT,
                requirement_ids=[requirement_id(1)])


class IsolationTests(unittest.TestCase):
    def test_cross_tenant_operations_rejected_after_final(self):
        recorder = RecordingApplication()
        service = ComplianceWorkflowService(
            reasoning_application=recorder)
        workflow, _, _ = finalize_flow()
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.supply_evidence(
                workflow, tenant_id=OTHER_TENANT,
                evidence_ids=[EVIDENCE_ID])
        with self.assertRaises(ComplianceWorkflowError):
            service.run_analysis(
                workflow, [make_case()], tenant_id=OTHER_TENANT,
                rag_service=FakeRAGService(), mode="hybrid",
                context_budget=EvidenceContextBudget(4000),
                decision_summary=make_summary())
        self.assertEqual(recorder.calls, [])
        with self.assertRaises(ComplianceWorkflowError):
            SERVICE.is_closed(workflow, tenant_id=OTHER_TENANT)


class ContinuationTests(unittest.TestCase):
    def test_fresh_progression_after_finalization(self):
        finalized, _, _ = finalize_flow()
        fresh = SERVICE.begin(
            tenant_id=TENANT, case_id=CASE_ID,
            shipment_id=SHIPMENT_ID)
        self.assertEqual(fresh.state, WORKFLOW_STATE_CREATED)
        self.assertEqual(fresh.id, finalized.id)
        advanced = SERVICE.provide_information(
            fresh, tenant_id=TENANT)
        self.assertEqual(
            advanced.state, "information_provided")
        self.assertEqual(
            finalized.state,
            WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY)

    def test_final_package_reference_stays_valid(self):
        workflow, package, result = finalize_flow()
        self.assertEqual(package.workflow_id, workflow.id)
        self.assertEqual(package.tenant_id, TENANT_ID)
        self.assertEqual(package.case_id, CASE_ID)
        self.assertEqual(package.shipment_id, SHIPMENT_ID)
        self.assertIs(package.reasoning_result, result)
        self.assertEqual(
            package.rounds, workflow.rounds)


if __name__ == "__main__":
    unittest.main()
