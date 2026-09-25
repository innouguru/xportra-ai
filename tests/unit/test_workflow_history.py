"""Phase 7.4 — Workflow history & audit view tests.

Covers ``WorkflowHistoryService``: a deterministic
read-only projection over existing 7.1–7.3 workflow
artifacts — creation, shipment binding, evidence supplies,
analysis rounds, current readiness, and final-package
reference — with no events recorded, no timestamps
invented, no persistence, and no new state machine.

Only the RAG/provider boundary is faked. Cases, validation,
and every Phase 6/7 service are real. No Phase 1–7.3 test
is modified.
"""

import ast
import dataclasses
import json
import unittest
from uuid import UUID

from xportra.domain.answer_validation import CitationAwareAnswerValidator
from xportra.domain.assessment_readiness import (
    READINESS_INVALID_WORKFLOW_STATE,
    AssessmentReadinessService,
)
from xportra.domain.compliance_workflow import (
    WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY,
    ComplianceWorkflowService,
)
from xportra.domain.errors import DomainValidationError
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
from xportra.domain.shipment_intake import ShipmentIntakeService
from xportra.domain.workflow_history import (
    HISTORY_ANALYSIS_COMPLETED,
    HISTORY_EVIDENCE_SUPPLIED,
    HISTORY_FINAL_PACKAGE_READY,
    HISTORY_SHIPMENT_BOUND,
    HISTORY_WORKFLOW_CREATED,
    WorkflowHistoryError,
    WorkflowHistoryService,
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
EVIDENCE_A = UUID("66666666-6666-6666-0000-0000000000a1")
EVIDENCE_B = UUID("66666666-6666-6666-0000-0000000000b2")

SERVICE = ComplianceWorkflowService()
HISTORY = WorkflowHistoryService()
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


def begin(shipment_id=SHIPMENT_ID):
    if shipment_id == "omit":
        return SERVICE.begin(tenant_id=TENANT, case_id=CASE_ID)
    return SERVICE.begin(
        tenant_id=TENANT, case_id=CASE_ID,
        shipment_id=shipment_id)


def run_first(workflow=None, cases=None, summary="default"):
    if workflow is None:
        workflow = begin()
        workflow = SERVICE.provide_information(
            workflow, tenant_id=TENANT)
        workflow = SERVICE.note_evidence_pending(
            workflow, tenant_id=TENANT)
        workflow = SERVICE.record_applicability_determined(
            workflow, tenant_id=TENANT)
    cases = cases if cases is not None else [make_case(
        evidence_statuses=("accepted",))]
    params = {
        "tenant_id": TENANT,
        "rag_service": FakeRAGService(),
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


def two_supply_flow():
    workflow, _ = run_first(cases=[make_case(
        1, assessment="unknown", evidence_statuses=(),
        assessment_reason="required evidence absent")])
    workflow = SERVICE.submit_for_review(
        workflow, tenant_id=TENANT)
    workflow = SERVICE.request_additional_evidence(
        workflow, tenant_id=TENANT,
        requirement_ids=[requirement_id(1)])
    workflow = SERVICE.supply_evidence(
        workflow, tenant_id=TENANT, evidence_ids=[EVIDENCE_A])
    workflow, _ = SERVICE.run_analysis(
        workflow, [make_case(1, evidence_statuses=("accepted",))],
        tenant_id=TENANT, rag_service=FakeRAGService(),
        mode="hybrid", context_budget=EvidenceContextBudget(4000),
        decision_summary=make_summary())
    workflow = SERVICE.submit_for_review(
        workflow, tenant_id=TENANT)
    workflow = SERVICE.request_additional_evidence(
        workflow, tenant_id=TENANT,
        requirement_ids=[requirement_id(1)])
    workflow = SERVICE.supply_evidence(
        workflow, tenant_id=TENANT, evidence_ids=[EVIDENCE_B])
    return workflow


def kinds(view):
    return [entry.kind for entry in view.entries]


class ConstructionTests(unittest.TestCase):
    def test_minimal_workflow_produces_minimal_view(self):
        workflow = begin()
        view = HISTORY.project(workflow, tenant_id=TENANT)
        self.assertEqual(view.workflow_id, workflow.id)
        self.assertEqual(view.tenant_id, TENANT_ID)
        self.assertEqual(view.case_id, CASE_ID)
        self.assertEqual(view.shipment_id, SHIPMENT_ID)
        self.assertEqual(view.state, "created")
        self.assertEqual(
            kinds(view),
            [HISTORY_WORKFLOW_CREATED, HISTORY_SHIPMENT_BOUND])
        self.assertEqual(view.round_count, 0)
        self.assertIsNone(view.latest_report_id)
        self.assertIsNone(view.readiness)
        self.assertIsNone(view.final_package)
        self.assertFalse(view.decision_summary_present)

    def test_unshipped_workflow_produces_creation_only_view(self):
        workflow = begin(shipment_id="omit")
        view = HISTORY.project(workflow, tenant_id=TENANT)
        self.assertIsNone(view.shipment_id)
        self.assertEqual(kinds(view), [HISTORY_WORKFLOW_CREATED])

    def test_projection_is_deterministic(self):
        workflow, result = review_workflow()
        first = HISTORY.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result).to_record()
        second = HISTORY.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result).to_record()
        self.assertEqual(first, second)

    def test_view_and_entries_are_immutable(self):
        workflow, result = review_workflow()
        view = HISTORY.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result)
        with self.assertRaises(dataclasses.FrozenInstanceError):
            view.state = "mutated"
        with self.assertRaises(dataclasses.FrozenInstanceError):
            view.entries[0].detail = "mutated"

    def test_view_serialization_has_fixed_shape(self):
        workflow, result = review_workflow()
        view = HISTORY.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result)
        body = json.loads(json.dumps(view.to_record()))
        self.assertEqual(
            set(body),
            {"workflow_id", "tenant_id", "case_id",
             "shipment_id", "state", "entries",
             "supplied_evidence_ids", "open_requirements",
             "round_count", "latest_report_id",
             "decision_summary_present", "readiness",
             "final_package"})
        for entry in body["entries"]:
            self.assertEqual(
                set(entry),
                {"sequence", "kind", "detail", "references"})

    def test_projection_does_not_mutate_workflow(self):
        workflow, result = review_workflow()
        snapshot = workflow
        HISTORY.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result)
        self.assertEqual(workflow, snapshot)
        self.assertEqual(
            workflow.supplied_evidence_ids,
            snapshot.supplied_evidence_ids)
        self.assertEqual(workflow.rounds, snapshot.rounds)


class HistoryContentTests(unittest.TestCase):
    def test_creation_entry_carries_identities(self):
        view = HISTORY.project(begin(), tenant_id=TENANT)
        entry = view.entries[0]
        self.assertEqual(entry.sequence, 0)
        self.assertEqual(entry.kind, HISTORY_WORKFLOW_CREATED)
        labels = {pair["label"]: pair["value"]
                  for pair in entry.to_record()["references"]}
        self.assertEqual(labels["tenant_id"], str(TENANT_ID))
        self.assertEqual(labels["case_id"], str(CASE_ID))

    def test_unbound_shipment_has_no_shipment_entry(self):
        workflow = begin(shipment_id="omit")
        view = HISTORY.project(workflow, tenant_id=TENANT)
        self.assertIsNone(view.shipment_id)
        self.assertNotIn(
            HISTORY_SHIPMENT_BOUND, kinds(view))

    def test_bound_shipment_is_represented(self):
        intake = ShipmentIntakeService(
            workflow_service=SERVICE)
        workflow = begin(shipment_id="omit")
        reference = intake.register_shipment(
            tenant_id=TENANT, shipment_id=SHIPMENT_ID,
            case_id=CASE_ID)
        workflow = intake.bind_shipment(
            workflow, reference, tenant_id=TENANT)
        view = HISTORY.project(workflow, tenant_id=TENANT)
        self.assertEqual(view.shipment_id, SHIPMENT_ID)
        shipment_entries = [
            e for e in view.entries
            if e.kind == HISTORY_SHIPMENT_BOUND]
        self.assertEqual(len(shipment_entries), 1)
        labels = {pair["label"]: pair["value"]
                  for pair in shipment_entries[0].to_record()[
                      "references"]}
        self.assertEqual(labels["shipment_id"], str(SHIPMENT_ID))

    def test_evidence_supplies_preserve_order(self):
        view = HISTORY.project(
            two_supply_flow(), tenant_id=TENANT)
        self.assertEqual(
            view.supplied_evidence_ids,
            (EVIDENCE_A, EVIDENCE_B))
        supply_entries = [
            e for e in view.entries
            if e.kind == HISTORY_EVIDENCE_SUPPLIED]
        self.assertEqual(len(supply_entries), 2)
        first_labels = {pair["label"]: pair["value"]
                        for pair in supply_entries[0].to_record()[
                            "references"]}
        second_labels = {pair["label"]: pair["value"]
                         for pair in supply_entries[1].to_record()[
                             "references"]}
        self.assertEqual(first_labels["evidence_id"],
                         str(EVIDENCE_A))
        self.assertEqual(first_labels["supply_position"], "0")
        self.assertEqual(second_labels["evidence_id"],
                         str(EVIDENCE_B))
        self.assertEqual(second_labels["supply_position"], "1")

    def test_analysis_rounds_preserve_round_order(self):
        workflow = two_supply_flow()
        view = HISTORY.project(workflow, tenant_id=TENANT)
        self.assertEqual(view.round_count, 2)
        round_entries = [
            e for e in view.entries
            if e.kind == HISTORY_ANALYSIS_COMPLETED]
        self.assertEqual(len(round_entries), 2)
        for position, entry in enumerate(round_entries):
            labels = {pair["label"]: pair["value"]
                      for pair in entry.to_record()["references"]}
            self.assertEqual(
                labels["round_index"], str(position + 1))
            self.assertEqual(
                labels["report_id"],
                str(workflow.rounds[position].report_id))
        self.assertEqual(
            view.latest_report_id, workflow.rounds[-1].report_id)

    def test_current_state_and_open_requirements_shown(self):
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
            evidence_ids=[EVIDENCE_A])
        view = HISTORY.project(workflow, tenant_id=TENANT)
        self.assertEqual(view.state, "reanalysis_required")
        self.assertEqual(
            view.open_requirements, (requirement_id(1),))

    def test_final_package_shown_by_reference(self):
        workflow, result = review_workflow()
        workflow, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        view = HISTORY.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result,
            assessment_package=package)
        self.assertEqual(view.state,
                         WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY)
        self.assertIsNotNone(view.final_package)
        self.assertEqual(view.final_package.workflow_id,
                         workflow.id)
        self.assertEqual(view.final_package.report_id,
                         result.report.id)
        self.assertEqual(view.final_package.round_count, 1)
        self.assertTrue(
            view.final_package.decision_summary_present)
        self.assertEqual(
            kinds(view)[-1], HISTORY_FINAL_PACKAGE_READY)

    def test_readiness_computed_when_result_supplied(self):
        workflow, result = review_workflow()
        view = HISTORY.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result)
        self.assertIsNotNone(view.readiness)
        self.assertTrue(view.readiness.ready)
        self.assertTrue(view.decision_summary_present)

    def test_terminal_workflow_reports_honest_readiness(self):
        workflow, result = review_workflow()
        workflow, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        view = HISTORY.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result,
            assessment_package=package)
        self.assertFalse(view.readiness.ready)
        self.assertIn(
            READINESS_INVALID_WORKFLOW_STATE,
            [issue.code for issue in view.readiness.reasons])

    def test_absent_summary_flag_is_accurate(self):
        workflow, result = review_workflow(summary=None)
        view = HISTORY.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result)
        self.assertFalse(view.decision_summary_present)


class OrderingTests(unittest.TestCase):
    def test_sequences_are_contiguous_from_zero(self):
        workflow, result = review_workflow()
        workflow, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        view = HISTORY.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result,
            assessment_package=package)
        self.assertEqual(
            [e.sequence for e in view.entries],
            list(range(len(view.entries))))

    def test_entries_follow_grouped_presentation_order(self):
        view = HISTORY.project(
            two_supply_flow(), tenant_id=TENANT)
        self.assertEqual(
            kinds(view),
            [HISTORY_WORKFLOW_CREATED,
             HISTORY_SHIPMENT_BOUND,
             HISTORY_EVIDENCE_SUPPLIED,
             HISTORY_EVIDENCE_SUPPLIED,
             HISTORY_ANALYSIS_COMPLETED,
             HISTORY_ANALYSIS_COMPLETED])

    def test_no_timestamps_anywhere_in_serialization(self):
        workflow, result = review_workflow()
        workflow, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        view = HISTORY.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result,
            assessment_package=package)
        body = view.to_record()

        def keys_of(node, found):
            if isinstance(node, dict):
                for key, value in node.items():
                    found.add(key)
                    keys_of(value, found)
            elif isinstance(node, (list, tuple)):
                for value in node:
                    keys_of(value, found)

        found: set[str] = set()
        keys_of(body, found)
        for forbidden in ("timestamp", "time", "created_at",
                          "occurred_at", "date", "datetime"):
            self.assertNotIn(forbidden, found)


class ProvenanceTests(unittest.TestCase):
    def test_round_references_match_recorded_round(self):
        workflow, _ = review_workflow()
        view = HISTORY.project(workflow, tenant_id=TENANT)
        entry = [e for e in view.entries
                 if e.kind == HISTORY_ANALYSIS_COMPLETED][0]
        round_record = workflow.rounds[0]
        labels: dict[str, list[str]] = {}
        for pair in entry.to_record()["references"]:
            labels.setdefault(pair["label"], []).append(
                pair["value"])
        self.assertEqual(
            labels["report_id"], [str(round_record.report_id)])
        self.assertEqual(
            labels["analysis_id"],
            [str(v) for v in round_record.analysis_ids])
        self.assertEqual(
            labels["trace_id"],
            [str(v) for v in round_record.trace_ids])
        self.assertEqual(
            labels["input_fingerprint"],
            list(round_record.input_fingerprints))

    def test_reasoning_content_is_not_copied(self):
        workflow, result = review_workflow()
        view = HISTORY.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result)
        body = json.dumps(view.to_record())
        self.assertNotIn("Exporters must file", body)
        self.assertNotIn("The filing is required", body)
        self.assertNotIn(
            result.analyses[0].explanation, body)

    def test_package_reference_preserves_provenance(self):
        workflow, result = review_workflow(summary=None)
        workflow, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        view = HISTORY.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result,
            assessment_package=package)
        self.assertFalse(
            view.final_package.decision_summary_present)
        self.assertEqual(
            view.final_package.round_count,
            len(workflow.rounds))


class IsolationTests(unittest.TestCase):
    def test_wrong_tenant_caller_rejected(self):
        workflow = begin()
        with self.assertRaises(WorkflowHistoryError):
            HISTORY.project(workflow, tenant_id=OTHER_TENANT)

    def test_result_from_another_tenant_rejected(self):
        from dataclasses import replace

        workflow, result = review_workflow()
        tampered = replace(result, tenant_id=OTHER_TENANT_ID)
        with self.assertRaises(WorkflowHistoryError):
            HISTORY.project(
                workflow, tenant_id=TENANT,
                reasoning_result=tampered)

    def test_result_from_another_case_rejected(self):
        from dataclasses import replace

        workflow, result = review_workflow()
        tampered = replace(result, case_id=OTHER_CASE_ID)
        with self.assertRaises(WorkflowHistoryError):
            HISTORY.project(
                workflow, tenant_id=TENANT,
                reasoning_result=tampered)

    def test_spliced_result_report_rejected(self):
        workflow, first = review_workflow(
            cases=[make_case(1, evidence_statuses=("accepted",))])
        _, second = run_first(cases=[make_case(
            2, evidence_statuses=("accepted",))])
        from dataclasses import replace

        tampered = replace(first, report=second.report)
        with self.assertRaises(WorkflowHistoryError):
            HISTORY.project(
                workflow, tenant_id=TENANT,
                reasoning_result=tampered)

    def test_package_from_another_workflow_rejected(self):
        OTHER_SHIPMENT = UUID(
            "ffffffff-ffff-ffff-ffff-ffffffffffff")
        foreign_base = SERVICE.begin(
            tenant_id=TENANT, case_id=CASE_ID,
            shipment_id=OTHER_SHIPMENT)
        foreign_base = SERVICE.provide_information(
            foreign_base, tenant_id=TENANT)
        foreign_base = SERVICE.note_evidence_pending(
            foreign_base, tenant_id=TENANT)
        foreign_base = SERVICE.record_applicability_determined(
            foreign_base, tenant_id=TENANT)
        foreign_workflow, foreign_result = run_first(
            workflow=foreign_base)
        foreign_workflow = SERVICE.submit_for_review(
            foreign_workflow, tenant_id=TENANT)
        _, foreign_package = SERVICE.finalize(
            foreign_workflow, foreign_result, tenant_id=TENANT)
        workflow, _ = review_workflow()
        with self.assertRaises(WorkflowHistoryError):
            HISTORY.project(
                workflow, tenant_id=TENANT,
                assessment_package=foreign_package)

    def test_malformed_inputs_rejected(self):
        workflow, result = review_workflow()
        with self.assertRaises(WorkflowHistoryError):
            HISTORY.project(
                {"state": "created"}, tenant_id=TENANT)
        with self.assertRaises(DomainValidationError):
            HISTORY.project(
                workflow, tenant_id="not-a-context")
        with self.assertRaises(WorkflowHistoryError):
            HISTORY.project(
                workflow, tenant_id=TENANT,
                reasoning_result={"report": {}})
        with self.assertRaises(WorkflowHistoryError):
            HISTORY.project(
                workflow, tenant_id=TENANT,
                assessment_package={"rounds": []})
        with self.assertRaises(WorkflowHistoryError):
            WorkflowHistoryService(readiness_service=object())


class PurityTests(unittest.TestCase):
    def test_service_holds_no_projection_state(self):
        workflow, result = review_workflow()
        service = WorkflowHistoryService()
        service.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result)
        self.assertEqual(
            set(service.__dict__), {"_readiness_service"})

    def test_repeated_projection_creates_no_trail(self):
        workflow, result = review_workflow()
        first = HISTORY.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result)
        second = HISTORY.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result)
        self.assertEqual(first, second)
        self.assertEqual(len(second.entries), len(first.entries))

    def test_injected_readiness_service_is_honored(self):
        service = WorkflowHistoryService(
            readiness_service=AssessmentReadinessService())
        workflow, result = review_workflow()
        view = service.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result)
        self.assertTrue(view.readiness.ready)

    def test_history_module_has_no_infra_imports(self):
        import pathlib

        path = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "domain" / "workflow_history.py")
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

    def test_history_module_calls_no_side_effect_boundary(self):
        import pathlib

        text = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "domain"
                / "workflow_history.py").read_text(
                    encoding="utf-8")
        for marker in ("datetime", "now()", ".query(",
                       ".retrieve(", ".generate(", "finalize(",
                       "supply_evidence(", "run_analysis(",
                       "RAGApplicationService",
                       "ComplianceEvidenceService",
                       "ShipmentIntakeService", "psycopg",
                       "QdrantClient", "SentenceTransformer",
                       "OpenRouter", "httpx.", "fastapi"):
            self.assertNotIn(marker, text)


class PrivacyTests(unittest.TestCase):
    def test_serialized_view_exposes_no_sensitive_material(self):
        workflow, result = review_workflow()
        workflow, package = SERVICE.finalize(
            workflow, result, tenant_id=TENANT)
        view = HISTORY.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result,
            assessment_package=package)
        body = json.dumps(view.to_record()).lower()
        for marker in ("prompt", "secret", "api_key", "token",
                       "password", "openrouter", "qdrant",
                       "generated_text", "model_identifier",
                       "certificate"):
            self.assertNotIn(marker, body)

    def test_references_are_identifier_strings_only(self):
        workflow, result = review_workflow()
        view = HISTORY.project(
            workflow, tenant_id=TENANT,
            reasoning_result=result)
        for entry in view.entries:
            for label, value in entry.references:
                self.assertIsInstance(label, str)
                self.assertIsInstance(value, str)
                self.assertLessEqual(len(value), 128)


if __name__ == "__main__":
    unittest.main()
