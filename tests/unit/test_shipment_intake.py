"""Phase 7.2 — Shipment & evidence intake formalization tests.

Covers ``ShipmentIntakeService``: the shipment reference and its
once-early workflow binding, the domain evidence reference and
its handoff into the Phase 7.1 workflow, tenant/case isolation,
deterministic-first failure behavior, and serialization.

Only the RAG/provider boundary is faked. Cases, validation,
the workflow service, and every Phase 6 service are real. No
Phase 1–7.1 test is modified.
"""

import ast
import json
import unittest
from uuid import UUID

from xportra.domain.answer_validation import CitationAwareAnswerValidator
from xportra.domain.compliance_workflow import (
    WORKFLOW_STATE_ADDITIONAL_EVIDENCE_REQUESTED,
    WORKFLOW_STATE_APPLICABILITY_DETERMINED,
    WORKFLOW_STATE_CREATED,
    WORKFLOW_STATE_EVIDENCE_PENDING,
    WORKFLOW_STATE_INFORMATION_PROVIDED,
    WORKFLOW_STATE_REANALYSIS_REQUIRED,
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
from xportra.domain.shipment_intake import (
    ShipmentIntakeError,
    ShipmentIntakeService,
    ShipmentReference,
    SuppliedEvidenceReference,
)
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
TENANT = TenantContext(TENANT_ID)
OTHER_TENANT = TenantContext(OTHER_TENANT_ID)
CASE_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
OTHER_CASE_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
SHIPMENT_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
OTHER_SHIPMENT_ID = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
EVIDENCE_ID = UUID("66666666-6666-6666-0000-000000000001")
DOCUMENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

WORKFLOWS = ComplianceWorkflowService()
INTAKE = ShipmentIntakeService()
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


def make_case(index=1, evidence_statuses=("accepted",)):
    req_id = requirement_id(index)
    records = [
        EvidenceRecord(
            tenant_id=TENANT_ID,
            evidence_id=UUID(
                f"66666666-6666-6666-{slot:04d}-{index:012d}"),
            evidence_type="certificate",
            reference=f"cert://filing-{index}-{slot}",
            requirement_id=req_id,
            status=status,
            metadata={"supports_requirement": (
                status in ("accepted", "reviewed"))},
        )
        for slot, status in enumerate(evidence_statuses)
    ]
    applicability_result = {
        "id": UUID(f"11111111-1111-1111-1111-{index:012d}"),
        "tenant_id": TENANT_ID,
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
    assessment_result = {
        "id": UUID(f"22222222-2222-2222-2222-{index:012d}"),
        "tenant_id": TENANT_ID,
        "requirement_id": req_id,
        "applicability_result_id": applicability_result["id"],
        "outcome": "satisfied",
        "reason": "required evidence present",
        "evidence_id": records[0].evidence_id if records else None,
        "evidence_ids": [r.evidence_id for r in records],
        "status": "assessed",
    }
    return ComplianceCaseService().build(
        applicability_result, requirement, assessment_result,
        records)


def make_summary():
    return {
        "tenant_id": TENANT_ID,
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
        return self._answers[0]


def begin_workflow():
    return WORKFLOWS.begin(tenant_id=TENANT, case_id=CASE_ID)


def shipment():
    return INTAKE.register_shipment(
        tenant_id=TENANT, shipment_id=SHIPMENT_ID,
        case_id=CASE_ID)


def evidence_ref(evidence_id=EVIDENCE_ID, requirement_id=None):
    return INTAKE.reference_evidence(
        tenant_id=TENANT, evidence_id=evidence_id,
        case_id=CASE_ID, requirement_id=requirement_id)


def ready_for_supply():
    """Workflow in additional_evidence_requested with a round."""
    workflow = WORKFLOWS.begin(tenant_id=TENANT, case_id=CASE_ID)
    workflow = WORKFLOWS.provide_information(
        workflow, tenant_id=TENANT)
    workflow = WORKFLOWS.note_evidence_pending(
        workflow, tenant_id=TENANT)
    workflow = WORKFLOWS.record_applicability_determined(
        workflow, tenant_id=TENANT)
    workflow, _ = WORKFLOWS.run_analysis(
        workflow, [make_case()], tenant_id=TENANT,
        rag_service=FakeRAGService(), mode="hybrid",
        context_budget=EvidenceContextBudget(4000),
        decision_summary=make_summary())
    workflow = WORKFLOWS.submit_for_review(
        workflow, tenant_id=TENANT)
    return WORKFLOWS.request_additional_evidence(
        workflow, tenant_id=TENANT,
        requirement_ids=[requirement_id(1)])


class ShipmentReferenceTests(unittest.TestCase):
    def test_valid_reference_accepted_and_bound(self):
        workflow = INTAKE.bind_shipment(
            begin_workflow(), shipment(), tenant_id=TENANT)
        self.assertEqual(workflow.shipment_id, SHIPMENT_ID)
        self.assertEqual(workflow.state, WORKFLOW_STATE_CREATED)
        body = json.loads(json.dumps(shipment().to_record()))
        self.assertEqual(body, {
            "tenant_id": str(TENANT_ID),
            "shipment_id": str(SHIPMENT_ID),
            "case_id": str(CASE_ID),
        })

    def test_binding_in_early_states(self):
        workflow = begin_workflow()
        for step in (WORKFLOWS.provide_information,
                     WORKFLOWS.note_evidence_pending):
            workflow = step(workflow, tenant_id=TENANT)
            bound = INTAKE.bind_shipment(
                workflow, shipment(), tenant_id=TENANT)
            self.assertEqual(bound.shipment_id, SHIPMENT_ID)

    def test_tenant_mismatch_rejected(self):
        foreign = INTAKE.register_shipment(
            tenant_id=OTHER_TENANT, shipment_id=SHIPMENT_ID,
            case_id=CASE_ID)
        with self.assertRaises(ShipmentIntakeError):
            INTAKE.bind_shipment(
                begin_workflow(), foreign, tenant_id=TENANT)

    def test_shipment_cannot_silently_change(self):
        workflow = INTAKE.bind_shipment(
            begin_workflow(), shipment(), tenant_id=TENANT)
        other = INTAKE.register_shipment(
            tenant_id=TENANT, shipment_id=OTHER_SHIPMENT_ID,
            case_id=CASE_ID)
        with self.assertRaises(ShipmentIntakeError):
            INTAKE.bind_shipment(
                workflow, other, tenant_id=TENANT)
        self.assertEqual(workflow.shipment_id, SHIPMENT_ID)

    def test_identical_rebind_is_idempotent(self):
        workflow = INTAKE.bind_shipment(
            begin_workflow(), shipment(), tenant_id=TENANT)
        rebound = INTAKE.bind_shipment(
            workflow, shipment(), tenant_id=TENANT)
        self.assertEqual(rebound, workflow)

    def test_late_binding_rejected(self):
        workflow = begin_workflow()
        workflow = WORKFLOWS.provide_information(
            workflow, tenant_id=TENANT)
        workflow = WORKFLOWS.note_evidence_pending(
            workflow, tenant_id=TENANT)
        workflow = WORKFLOWS.record_applicability_determined(
            workflow, tenant_id=TENANT)
        with self.assertRaises(ShipmentIntakeError):
            INTAKE.bind_shipment(
                workflow, shipment(), tenant_id=TENANT)

    def test_wrong_case_reference_rejected(self):
        foreign = INTAKE.register_shipment(
            tenant_id=TENANT, shipment_id=SHIPMENT_ID,
            case_id=OTHER_CASE_ID)
        with self.assertRaises(ShipmentIntakeError):
            INTAKE.bind_shipment(
                begin_workflow(), foreign, tenant_id=TENANT)

    def test_raw_shipment_data_rejected(self):
        with self.assertRaises(ShipmentIntakeError):
            INTAKE.bind_shipment(
                begin_workflow(),
                {"shipment_id": str(SHIPMENT_ID)}, tenant_id=TENANT)
        with self.assertRaises(ShipmentIntakeError):
            INTAKE.register_shipment(
                tenant_id=TENANT, shipment_id="not-a-uuid",
                case_id=CASE_ID)

    def test_missing_tenant_context_rejected(self):
        with self.assertRaises(DomainValidationError):
            INTAKE.register_shipment(
                tenant_id="not-a-context",
                shipment_id=SHIPMENT_ID, case_id=CASE_ID)


class EvidenceReferenceTests(unittest.TestCase):
    def test_valid_reference_accepted(self):
        reference = evidence_ref(
            requirement_id=requirement_id(1))
        self.assertEqual(reference.tenant_id, TENANT_ID)
        self.assertEqual(reference.evidence_id, EVIDENCE_ID)
        self.assertEqual(reference.case_id, CASE_ID)
        self.assertEqual(reference.requirement_id,
                         requirement_id(1))
        body = json.loads(json.dumps(reference.to_record()))
        self.assertEqual(body["evidence_id"], str(EVIDENCE_ID))
        self.assertEqual(
            body["requirement_id"], str(requirement_id(1)))

    def test_case_level_reference_without_requirement(self):
        reference = evidence_ref()
        self.assertIsNone(reference.requirement_id)
        body = json.loads(json.dumps(reference.to_record()))
        self.assertIsNone(body["requirement_id"])

    def test_wrong_tenant_rejected_at_supply(self):
        workflow = ready_for_supply()
        foreign = INTAKE.reference_evidence(
            tenant_id=OTHER_TENANT, evidence_id=EVIDENCE_ID,
            case_id=CASE_ID)
        with self.assertRaises(ShipmentIntakeError):
            INTAKE.supply_to_workflow(
                workflow, foreign, tenant_id=TENANT)
        self.assertEqual(
            workflow.state,
            WORKFLOW_STATE_ADDITIONAL_EVIDENCE_REQUESTED)

    def test_wrong_case_rejected_at_supply(self):
        workflow = ready_for_supply()
        foreign = INTAKE.reference_evidence(
            tenant_id=TENANT, evidence_id=EVIDENCE_ID,
            case_id=OTHER_CASE_ID)
        with self.assertRaises(ShipmentIntakeError):
            INTAKE.supply_to_workflow(
                workflow, foreign, tenant_id=TENANT)

    def test_malformed_identities_rejected(self):
        with self.assertRaises(ShipmentIntakeError):
            INTAKE.reference_evidence(
                tenant_id=TENANT, evidence_id="not-a-uuid",
                case_id=CASE_ID)
        with self.assertRaises(ShipmentIntakeError):
            SuppliedEvidenceReference(
                tenant_id=TENANT_ID, evidence_id=EVIDENCE_ID,
                case_id=CASE_ID,
                requirement_id="not-a-uuid")

    def test_raw_file_content_rejected(self):
        workflow = ready_for_supply()
        for raw in (b"file-bytes", "cert://filing",
                    {"evidence_id": str(EVIDENCE_ID)}):
            with self.assertRaises(ShipmentIntakeError):
                INTAKE.supply_to_workflow(
                    workflow, raw, tenant_id=TENANT)


class EvidenceHandoffTests(unittest.TestCase):
    def test_supply_advances_workflow_with_reference(self):
        workflow = INTAKE.supply_to_workflow(
            ready_for_supply(), evidence_ref(),
            tenant_id=TENANT)
        self.assertEqual(
            workflow.state, WORKFLOW_STATE_REANALYSIS_REQUIRED)
        self.assertIn(EVIDENCE_ID, workflow.supplied_evidence_ids)

    def test_handoff_uses_existing_workflow_transition(self):
        before = ready_for_supply()
        after = INTAKE.supply_to_workflow(
            before, evidence_ref(), tenant_id=TENANT)
        self.assertEqual(len(before.rounds), 1)
        self.assertEqual(after.rounds, before.rounds)
        self.assertEqual(
            after.supplied_evidence_ids, (EVIDENCE_ID,))

    def test_duplicate_supply_is_deterministic(self):
        workflow = INTAKE.supply_to_workflow(
            ready_for_supply(), evidence_ref(),
            tenant_id=TENANT)
        workflow, _ = WORKFLOWS.run_analysis(
            workflow, [make_case()], tenant_id=TENANT,
            rag_service=FakeRAGService(), mode="hybrid",
            context_budget=EvidenceContextBudget(4000),
            decision_summary=make_summary())
        workflow = WORKFLOWS.submit_for_review(
            workflow, tenant_id=TENANT)
        workflow = WORKFLOWS.request_additional_evidence(
            workflow, tenant_id=TENANT,
            requirement_ids=[requirement_id(1)])
        repeated = INTAKE.supply_to_workflow(
            workflow, evidence_ref(), tenant_id=TENANT)
        self.assertEqual(
            repeated.supplied_evidence_ids, (EVIDENCE_ID,))

    def test_supply_in_wrong_state_fails_closed(self):
        workflow = begin_workflow()
        with self.assertRaises(DomainValidationError):
            INTAKE.supply_to_workflow(
                workflow, evidence_ref(), tenant_id=TENANT)
        self.assertEqual(workflow.state, WORKFLOW_STATE_CREATED)
        self.assertEqual(workflow.supplied_evidence_ids, ())

    def test_missing_intake_service_dependency_rejected(self):
        with self.assertRaises(ShipmentIntakeError):
            ShipmentIntakeService(workflow_service=object())


class Phase6IntegrationTests(unittest.TestCase):
    def test_supplied_evidence_available_at_reanalysis(self):
        supplied = UUID("66666666-6666-0000-0000-000000000001")
        workflow = ready_for_supply()
        workflow = INTAKE.supply_to_workflow(
            workflow,
            INTAKE.reference_evidence(
                tenant_id=TENANT, evidence_id=supplied,
                case_id=CASE_ID,
                requirement_id=requirement_id(1)),
            tenant_id=TENANT)
        self.assertIn(supplied, workflow.supplied_evidence_ids)
        workflow, result = WORKFLOWS.run_analysis(
            workflow, [make_case()], tenant_id=TENANT,
            rag_service=FakeRAGService(), mode="hybrid",
            context_budget=EvidenceContextBudget(4000),
            decision_summary=make_summary())
        self.assertEqual(len(workflow.rounds), 2)
        self.assertEqual(
            workflow.rounds[1].report_id, result.report.id)

    def test_intake_adds_no_reasoning_or_retrieval(self):
        workflow = ready_for_supply()
        before_rounds = workflow.rounds
        after = INTAKE.supply_to_workflow(
            workflow, evidence_ref(), tenant_id=TENANT)
        self.assertEqual(after.rounds, before_rounds)


class IsolationTests(unittest.TestCase):
    def test_cross_tenant_bind_rejected(self):
        with self.assertRaises(ShipmentIntakeError):
            INTAKE.bind_shipment(
                begin_workflow(), shipment(),
                tenant_id=OTHER_TENANT)

    def test_cross_tenant_supply_rejected(self):
        with self.assertRaises(ShipmentIntakeError):
            INTAKE.supply_to_workflow(
                ready_for_supply(), evidence_ref(),
                tenant_id=OTHER_TENANT)

    def test_cross_case_supply_rejected(self):
        workflow = ready_for_supply()
        self.assertEqual(workflow.case_id, CASE_ID)
        foreign = INTAKE.reference_evidence(
            tenant_id=TENANT, evidence_id=EVIDENCE_ID,
            case_id=OTHER_CASE_ID)
        with self.assertRaises(ShipmentIntakeError):
            INTAKE.supply_to_workflow(
                workflow, foreign, tenant_id=TENANT)


class FailureBehaviorTests(unittest.TestCase):
    def test_invalid_supply_causes_zero_provider_calls(self):
        rag = FakeRAGService()
        workflow = begin_workflow()
        with self.assertRaises(DomainValidationError):
            INTAKE.supply_to_workflow(
                workflow, evidence_ref(), tenant_id=TENANT)
        self.assertEqual(rag.calls, [])
        self.assertEqual(workflow.supplied_evidence_ids, ())

    def test_failed_handoff_produces_no_new_state(self):
        workflow = ready_for_supply()
        snapshot = workflow.to_record()
        with self.assertRaises(ShipmentIntakeError):
            INTAKE.supply_to_workflow(
                workflow, "not-a-reference", tenant_id=TENANT)
        self.assertEqual(workflow.to_record(), snapshot)

    def test_stale_reference_rejected(self):
        workflow = ready_for_supply()
        stale = SuppliedEvidenceReference(
            tenant_id=TENANT_ID, evidence_id=EVIDENCE_ID,
            case_id=OTHER_CASE_ID)
        with self.assertRaises(ShipmentIntakeError):
            INTAKE.supply_to_workflow(
                workflow, stale, tenant_id=TENANT)


class SerializationTests(unittest.TestCase):
    def test_references_are_deterministic(self):
        first = shipment()
        second = INTAKE.register_shipment(
            tenant_id=TENANT, shipment_id=SHIPMENT_ID,
            case_id=CASE_ID)
        self.assertEqual(first, second)
        self.assertEqual(first.to_record(), second.to_record())

    def test_workflow_record_carries_shipment(self):
        workflow = INTAKE.bind_shipment(
            begin_workflow(), shipment(), tenant_id=TENANT)
        body = json.loads(json.dumps(workflow.to_record()))
        self.assertEqual(body["shipment_id"], str(SHIPMENT_ID))
        self.assertEqual(body["case_id"], str(CASE_ID))


class FrameworkBoundaryTests(unittest.TestCase):
    def test_intake_module_has_no_infra_imports(self):
        import pathlib

        path = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "domain" / "shipment_intake.py")
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
             "anthropic", "httpx", "xportra", "psycopg"}))
        self.assertIn("dataclasses", modules)

    def test_intake_never_records_parses_or_indexes(self):
        import pathlib

        text = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "domain"
                / "shipment_intake.py").read_text(encoding="utf-8")
        for marker in ("QdrantClient", "SentenceTransformer",
                       "OpenRouter", "httpx.", "EmbeddingProvider",
                       ".retrieve(", ".generate(", ".query(",
                       "EvidenceRequirementRepository",
                       ".create(", ".record(", "Database"):
            self.assertNotIn(marker, text)


if __name__ == "__main__":
    unittest.main()
