"""Phase 6.6 — End-to-end compliance reasoning composition tests.

Covers ``ComplianceReasoningApplication.analyze_case``: the single
safe orchestration boundary composing deterministic case state,
Phase 5 retrieval, validated structured reasoning, analysis,
report, and traces — plus the end-to-end invariant matrix
(tenant/case/requirement isolation, deterministic authority,
provenance, uncertainty, failure semantics, trace privacy,
deterministic identity).

Only the RAG/provider boundary is faked (scripted answers,
counting, failure injection). Cases, ranking, selection,
prompts, validation, and every Phase 6 service are real. No
Phase 6.1–6.5 test is modified.
"""

import ast
import json
import unittest
from uuid import UUID

from xportra.domain.answer_validation import (
    CitationAwareAnswerValidator,
    VALIDATION_STATUS_INVALID_CITATIONS,
)
from xportra.domain.compliance_reasoning import ComplianceAnalysis
from xportra.domain.decision_trace import DecisionTrace
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
    ComplianceReasoningApplicationError,
    ComplianceReasoningResult,
)
from xportra.domain.reasoning_generation import ReasoningGenerationError
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
TENANT = TenantContext(TENANT_ID)
CASE_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
DOCUMENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

APP = ComplianceReasoningApplication()
PROMPT_CONFIG = EvidencePromptConfig(
    system_instructions="Explain the compliance position."
)


def requirement_id(index):
    return UUID(f"00000000-0000-0000-0000-{index:012d}")


def applicability_id(index):
    return UUID(f"11111111-1111-1111-1111-{index:012d}")


def assessment_id(index):
    return UUID(f"22222222-2222-2222-2222-{index:012d}")


def evidence_id(index, slot=0):
    return UUID(f"66666666-6666-6666-{slot:04d}-{index:012d}")


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
            evidence_id=evidence_id(index, slot),
            evidence_type="certificate",
            reference=f"cert://filing-{index}-{slot}",
            requirement_id=req_id,
            status=status,
            metadata={"supports_requirement": (
                status in ("accepted", "reviewed"))},
        ))
    applicability_result = {
        "id": applicability_id(index),
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
            "id": assessment_id(index),
            "tenant_id": TENANT_ID,
            "requirement_id": req_id,
            "applicability_result_id": applicability_id(index),
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
    """Scripted RAG boundary stand-in (counts every invocation)."""

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


def analyze(cases, rag=None, summary="default", **kwargs):
    params = {
        "tenant_id": TENANT,
        "case_id": CASE_ID,
        "rag_service": rag or FakeRAGService(),
        "mode": "hybrid",
        "context_budget": EvidenceContextBudget(4000),
    }
    if summary == "default":
        params["decision_summary"] = make_summary()
    elif summary is not None:
        params["decision_summary"] = summary
    params.update(kwargs)
    if isinstance(cases, dict):
        cases = [cases]
    return APP.analyze_case(list(cases), **params)


class HappyPathTests(unittest.TestCase):
    def test_one_applicable_requirement(self):
        result = analyze(make_case())
        self.assertIsInstance(result, ComplianceReasoningResult)
        self.assertEqual(result.case_id, CASE_ID)
        self.assertEqual(result.tenant_id, TENANT_ID)
        self.assertEqual(len(result.analyses), 1)
        self.assertEqual(len(result.traces), 1)
        self.assertIsInstance(result.traces[0], DecisionTrace)
        self.assertEqual(result.report.total_requirements, 1)
        self.assertEqual(result.report.satisfied_count, 1)
        self.assertEqual(result.traces[0].report_id, result.report.id)
        self.assertEqual(result.report.case_id, CASE_ID)

    def test_multiple_requirements_ordered(self):
        result = analyze([make_case(3), make_case(1),
                          make_case(2)])
        self.assertEqual(
            [a.requirement_id for a in result.analyses],
            [requirement_id(1), requirement_id(2),
             requirement_id(3)])
        self.assertEqual(
            [t.requirement_id for t in result.traces],
            [requirement_id(1), requirement_id(2),
             requirement_id(3)])
        self.assertEqual(result.report.total_requirements, 3)

    def test_mixed_requirement_states(self):
        rag = FakeRAGService(answers=[
            make_validated_answer(),
            make_validated_answer("Rejected filing stands [E1]."),
            make_validated_answer(text="No basis found.",
                                  contents=()),
            make_validated_answer("Not in scope [E1]."),
        ])
        result = analyze([
            make_case(1, evidence_statuses=("accepted",)),
            make_case(2, assessment="not_satisfied",
                      evidence_statuses=("rejected",),
                      assessment_reason="evidence rejected"),
            make_case(3, assessment="unknown", evidence_statuses=(),
                      assessment_reason="required evidence absent"),
            make_case(4, applicability="not_applicable"),
        ], rag=rag)
        self.assertEqual(result.report.satisfied_count, 1)
        self.assertEqual(result.report.not_satisfied_count, 1)
        self.assertEqual(result.report.unknown_count, 1)
        self.assertEqual(result.report.not_applicable_count, 1)
        by_requirement = {a.requirement_id: a
                          for a in result.analyses}
        self.assertEqual(
            by_requirement[requirement_id(1)].evidence_sufficiency,
            "supported")
        self.assertEqual(
            by_requirement[requirement_id(3)].evidence_sufficiency,
            "missing")
        self.assertEqual(
            by_requirement[requirement_id(4)].evidence_sufficiency,
            "unknown")

    def test_supporting_evidence_and_knowledge_present(self):
        result = analyze(
            make_case(evidence_statuses=("accepted",)))
        (analysis,) = result.analyses
        self.assertEqual(len(analysis.supporting_evidence), 1)
        self.assertEqual(len(analysis.knowledge_references), 1)
        self.assertEqual(analysis.knowledge_references[0].label,
                         "[E1]")
        (trace,) = result.traces
        self.assertEqual(len(trace.supporting_evidence), 1)
        self.assertEqual(len(trace.knowledge_references), 1)

    def test_result_serializes(self):
        body = json.loads(json.dumps(analyze(
            [make_case(1), make_case(2)],
            summary=None).to_record()))
        self.assertEqual(body["case_id"], str(CASE_ID))
        self.assertEqual(len(body["analyses"]), 2)
        self.assertEqual(len(body["traces"]), 2)
        self.assertEqual(body["report"]["total_requirements"], 2)


class DeterministicStatesTests(unittest.TestCase):
    def test_satisfied_end_to_end(self):
        (analysis,) = analyze(
            make_case(evidence_statuses=("accepted",))).analyses
        self.assertEqual(analysis.assessment, "satisfied")
        self.assertEqual(analysis.evidence_sufficiency, "supported")
        self.assertEqual(analysis.uncertainty, "determined")

    def test_not_satisfied_end_to_end(self):
        (analysis,) = analyze(make_case(
            assessment="not_satisfied",
            evidence_statuses=("rejected",),
            assessment_reason="evidence rejected")).analyses
        self.assertEqual(analysis.assessment, "not_satisfied")
        self.assertEqual(analysis.evidence_sufficiency, "supported")

    def test_unknown_end_to_end(self):
        (analysis,) = analyze(make_case(
            assessment="unknown", evidence_statuses=(),
            assessment_reason="required evidence absent")).analyses
        self.assertEqual(analysis.assessment, "unknown")
        self.assertEqual(analysis.uncertainty, "unknown")

    def test_not_applicable_end_to_end(self):
        (analysis,) = analyze(
            make_case(applicability="not_applicable")).analyses
        self.assertEqual(analysis.applicability, "not_applicable")
        self.assertEqual(analysis.assessment, "unknown")
        self.assertEqual(analysis.evidence_sufficiency, "unknown")


class EvidenceConditionsTests(unittest.TestCase):
    def test_sufficient(self):
        (analysis,) = analyze(
            make_case(evidence_statuses=("accepted",))).analyses
        self.assertEqual(analysis.evidence_sufficiency, "supported")

    def test_missing(self):
        (analysis,) = analyze(make_case(
            assessment="unknown", evidence_statuses=(),
            assessment_reason="required evidence absent")).analyses
        self.assertEqual(analysis.evidence_sufficiency, "missing")

    def test_insufficient(self):
        (analysis,) = analyze(make_case(
            assessment="unknown", evidence_statuses=("uploaded",),
            assessment_reason="evidence insufficient")).analyses
        self.assertEqual(analysis.evidence_sufficiency,
                         "insufficient")

    def test_conflicting(self):
        (analysis,) = analyze(make_case(
            assessment="not_satisfied",
            evidence_statuses=("rejected",),
            assessment_reason="evidence rejected")).analyses
        self.assertEqual(analysis.contradiction_state, "present")
        self.assertEqual(len(analysis.conflicting_evidence), 1)


class DeterministicFirstTests(unittest.TestCase):
    def test_empty_cases_rejected_without_provider_call(self):
        rag = FakeRAGService()
        with self.assertRaises(ComplianceReasoningApplicationError):
            analyze([], rag=rag)
        self.assertEqual(rag.calls, [])

    def test_non_list_cases_rejected(self):
        rag = FakeRAGService()
        with self.assertRaises(ComplianceReasoningApplicationError):
            APP.analyze_case(
                "not cases", tenant_id=TENANT, case_id=CASE_ID,
                rag_service=rag, mode="hybrid",
                context_budget=EvidenceContextBudget(4000),
                decision_summary=make_summary())
        self.assertEqual(rag.calls, [])

    def test_cross_tenant_case_rejected_without_provider_call(self):
        rag = FakeRAGService()
        case = dict(make_case(),
                    tenant_id=OTHER_TENANT_ID)
        with self.assertRaises(ComplianceReasoningApplicationError):
            analyze(case, rag=rag)
        self.assertEqual(rag.calls, [])

    def test_inconsistent_context_rejected_without_provider_call(self):
        rag = FakeRAGService()
        first = make_case(1)
        second = dict(make_case(2), context_fingerprint="other")
        with self.assertRaises(ComplianceReasoningApplicationError):
            analyze([first, second], rag=rag)
        self.assertEqual(rag.calls, [])

    def test_duplicate_requirement_rejected_without_provider_call(self):
        rag = FakeRAGService()
        with self.assertRaises(ComplianceReasoningApplicationError):
            analyze([make_case(1), make_case(1)], rag=rag)
        self.assertEqual(rag.calls, [])

    def test_malformed_case_id_rejected(self):
        rag = FakeRAGService()
        with self.assertRaises(ComplianceReasoningApplicationError):
            analyze(make_case(), rag=rag, case_id="not-a-uuid")
        self.assertEqual(rag.calls, [])

    def test_foreign_decision_summary_rejected(self):
        rag = FakeRAGService()
        with self.assertRaises(ComplianceReasoningApplicationError):
            analyze(make_case(), rag=rag,
                    summary=make_summary(OTHER_TENANT_ID))
        self.assertEqual(rag.calls, [])

    def test_malformed_summary_rejected(self):
        rag = FakeRAGService()
        with self.assertRaises(ComplianceReasoningApplicationError):
            analyze(make_case(), rag=rag, summary="summary")
        self.assertEqual(rag.calls, [])

    def test_missing_tenant_context_rejected(self):
        with self.assertRaises(DomainValidationError):
            APP.analyze_case(
                [make_case()], tenant_id="not-a-context",
                case_id=CASE_ID, rag_service=FakeRAGService(),
                mode="hybrid",
                context_budget=EvidenceContextBudget(4000))


class ProviderFailureTests(unittest.TestCase):
    def test_retrieval_failure_propagates(self):
        rag = FakeRAGService(failure=VectorStoreError(
            "find", RuntimeError("index down")))
        with self.assertRaises(VectorStoreError):
            analyze(make_case(), rag=rag)

    def test_provider_failure_propagates(self):
        rag = FakeRAGService(failure=LLMProviderError(
            "generate", RuntimeError("provider down")))
        with self.assertRaises(LLMProviderError):
            analyze(make_case(), rag=rag)

    def test_failures_never_become_compliance_states(self):
        for failure in (VectorStoreError(
                "find", RuntimeError("index down")),
                        LLMProviderError(
                            "generate", RuntimeError("down"))):
            rag = FakeRAGService(failure=failure)
            try:
                analyze(make_case(), rag=rag)
            except (VectorStoreError, LLMProviderError):
                continue
            self.fail("provider failure must remain a failure")

    def test_malformed_structured_output_fails(self):
        rag = FakeRAGService(answers=[make_validated_answer(
            text="EXPLANATION:\n")])
        with self.assertRaises(ReasoningGenerationError):
            analyze(make_case(), rag=rag)

    def test_reasoning_validation_failure_fails(self):
        validator = CitationAwareAnswerValidator(
            fail_on_invalid_citations=False)
        good = make_validated_answer(text="See [E1].")
        other = GeneratedAnswer(
            prompt=good.answer.prompt,
            response=LLMResponse(
                generated_text="See [E9].",
                model_identifier="test-model"),
            tenant_id=TENANT)
        bad = validator.validate(other)
        self.assertEqual(
            bad.status, VALIDATION_STATUS_INVALID_CITATIONS)
        rag = FakeRAGService(answers=[bad])
        with self.assertRaises(DomainValidationError):
            analyze(make_case(), rag=rag)

    def test_partial_failure_fails_closed_without_partial_result(self):
        rag = FakeRAGService(
            answers=[make_validated_answer()],
            failure=None)
        calls = []

        original = rag.query

        def flaky(need, **kwargs):
            calls.append(need)
            if len(calls) == 2:
                raise LLMProviderError(
                    "generate", RuntimeError("provider down"))
            return original(need, **kwargs)

        rag.query = flaky
        with self.assertRaises(LLMProviderError):
            analyze([make_case(1), make_case(2), make_case(3)],
                    rag=rag)
        self.assertEqual(len(calls), 2)

    def test_report_composition_failure_propagates(self):
        class BrokenReports:
            def compose(self, *args, **kwargs):
                raise DomainValidationError("broken report")

        app = ComplianceReasoningApplication(
            report_service=BrokenReports())
        with self.assertRaises(DomainValidationError):
            app.analyze_case(
                [make_case()], tenant_id=TENANT, case_id=CASE_ID,
                rag_service=FakeRAGService(), mode="hybrid",
                context_budget=EvidenceContextBudget(4000),
                decision_summary=make_summary())

    def test_trace_construction_failure_propagates(self):
        class BrokenTraces:
            def trace(self, *args, **kwargs):
                raise DomainValidationError("broken trace")

        app = ComplianceReasoningApplication(
            trace_service=BrokenTraces())
        with self.assertRaises(DomainValidationError):
            app.analyze_case(
                [make_case()], tenant_id=TENANT, case_id=CASE_ID,
                rag_service=FakeRAGService(), mode="hybrid",
                context_budget=EvidenceContextBudget(4000),
                decision_summary=make_summary())


class SecurityIntegrityTests(unittest.TestCase):
    def test_cross_case_context_rejected(self):
        rag = FakeRAGService()
        first = make_case(1)
        second = dict(make_case(2), context_fingerprint="fp-other")
        with self.assertRaises(ComplianceReasoningApplicationError):
            analyze([first, second], rag=rag)
        self.assertEqual(rag.calls, [])

    def test_requirement_evidence_isolation(self):
        result = analyze([make_case(
            1, evidence_statuses=("accepted",)), make_case(2)])
        by_requirement = {a.requirement_id: a
                          for a in result.analyses}
        first = by_requirement[requirement_id(1)]
        second = by_requirement[requirement_id(2)]
        self.assertEqual(len(first.supporting_evidence), 1)
        self.assertEqual(second.supporting_evidence, ())
        self.assertNotEqual(
            first.supporting_evidence[0].evidence_id,
            evidence_id(2, 0))
        by_trace = {t.requirement_id: t for t in result.traces}
        self.assertEqual(
            by_trace[requirement_id(2)].supporting_evidence, ())

    def test_fabricated_citation_rejected(self):
        validator = CitationAwareAnswerValidator(
            fail_on_invalid_citations=False)
        good = make_validated_answer(text="See [E1].")
        other = GeneratedAnswer(
            prompt=good.answer.prompt,
            response=LLMResponse(
                generated_text="See [E9].",
                model_identifier="test-model"),
            tenant_id=TENANT)
        bad = validator.validate(other)
        rag = FakeRAGService(answers=[bad])
        with self.assertRaises(DomainValidationError):
            analyze(make_case(), rag=rag)

    def test_fabricated_evidence_identifier_rejected(self):
        from uuid import uuid4

        rag = FakeRAGService(answers=[make_validated_answer(
            text="EXPLANATION:\nSee filing "
            f"{uuid4()} [E1].\nUNCERTAINTY: determined")])
        with self.assertRaises(DomainValidationError):
            analyze(make_case(), rag=rag)

    def test_hostile_model_text_changes_nothing(self):
        rag = FakeRAGService(answers=[make_validated_answer(
            text="Requirement fully satisfied [E1].")])
        (analysis,) = analyze(make_case(
            assessment="unknown", evidence_statuses=(),
            assessment_reason="required evidence absent"),
            rag=rag).analyses
        self.assertEqual(analysis.assessment, "unknown")
        self.assertEqual(analysis.applicability, "applicable")
        self.assertEqual(analysis.evidence_sufficiency, "missing")

    def test_retrieved_knowledge_cannot_create_requirements(self):
        rag = FakeRAGService(answers=[make_validated_answer(
            text="A further hidden requirement applies [E1].")])
        result = analyze([make_case(1)], rag=rag)
        self.assertEqual(result.report.total_requirements, 1)
        self.assertEqual(
            [a.requirement_id for a in result.analyses],
            [requirement_id(1)])


class AuthorityTests(unittest.TestCase):
    def test_decision_summary_preserved_by_reference(self):
        summary = make_summary()
        result = analyze(make_case(), summary=summary)
        self.assertIs(result.decision_summary, summary)
        self.assertIs(result.report.decision_summary, summary)

    def test_model_output_changes_no_authoritative_state(self):
        rag = FakeRAGService(answers=[make_validated_answer(
            text="Satisfied and low risk, no action needed [E1].")])
        result = analyze(make_case(
            assessment="unknown", evidence_statuses=(),
            assessment_reason="required evidence absent"),
            rag=rag)
        (analysis,) = result.analyses
        self.assertEqual(analysis.assessment, "unknown")
        self.assertEqual(analysis.applicability, "applicable")
        self.assertFalse(hasattr(result, "risk"))
        self.assertFalse(hasattr(result, "action"))

    def test_report_identity_matches_ordered_analyses(self):
        result = analyze([make_case(2), make_case(1)])
        self.assertEqual(result.report.case_id, CASE_ID)
        self.assertEqual(result.report.total_requirements, 2)
        self.assertEqual(
            [a.requirement_id for a in result.report.analyses],
            [requirement_id(1), requirement_id(2)])

    def test_trace_report_reference_correct(self):
        result = analyze([make_case(1), make_case(2)])
        for trace in result.traces:
            self.assertEqual(trace.report_id, result.report.id)
            self.assertEqual(trace.tenant_id, TENANT_ID)


class NoVerdictTests(unittest.TestCase):
    def test_result_carries_no_overall_verdict(self):
        result = analyze([make_case(1), make_case(2)],
                         summary=None)
        self.assertFalse(hasattr(result, "verdict"))
        self.assertFalse(hasattr(result, "overall_status"))
        self.assertFalse(hasattr(result, "compliant"))
        body = json.dumps(result.to_record()).lower()
        for marker in ("verdict", "overall", "compliant",
                       "risk_state", "action_type"):
            self.assertNotIn(marker, body)

    def test_result_keys_are_fixed(self):
        body = json.loads(json.dumps(analyze(
            make_case(), summary=None).to_record()))
        self.assertEqual(
            set(body),
            {"case_id", "tenant_id", "analyses", "report",
             "traces", "decision_summary"})


class DeterminismTests(unittest.TestCase):
    def test_equivalent_inputs_produce_stable_identities(self):
        first = analyze([make_case(1), make_case(2)])
        second = analyze([make_case(1), make_case(2)])
        self.assertEqual(first.report.id, second.report.id)
        self.assertEqual(
            [t.id for t in first.traces],
            [t.id for t in second.traces])
        self.assertEqual(
            [t.input_fingerprint for t in first.traces],
            [t.input_fingerprint for t in second.traces])
        self.assertEqual(first.to_record(), second.to_record())

    def test_input_order_does_not_change_identity(self):
        ordered = analyze([make_case(1), make_case(2)])
        shuffled = analyze([make_case(2), make_case(1)])
        self.assertEqual(shuffled.report.id, ordered.report.id)
        self.assertEqual(
            [t.id for t in shuffled.traces],
            [t.id for t in ordered.traces])


class TracePrivacyTests(unittest.TestCase):
    def test_no_secrets_or_internals_in_result(self):
        body = json.dumps(analyze(
            [make_case(1, evidence_statuses=("accepted",))],
            summary=None).to_record()).lower()
        for marker in ("system_instructions", "api_key", "apikey",
                       "chain_of_thought", "scratchpad",
                       "hidden_state", "token-by-token",
                       "openrouter", "qdrant", "bearer "):
            self.assertNotIn(marker, body)

    def test_unknown_remains_unknown_end_to_end(self):
        result = analyze(make_case(
            assessment="unknown", evidence_statuses=(),
            assessment_reason="required evidence absent"))
        (analysis,) = result.analyses
        (trace,) = result.traces
        self.assertEqual(analysis.assessment, "unknown")
        self.assertEqual(trace.assessment, "unknown")
        self.assertEqual(trace.uncertainty, "unknown")


class FrameworkBoundaryTests(unittest.TestCase):
    def test_application_module_has_no_infra_imports(self):
        import pathlib

        path = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "domain" / "reasoning_application.py")
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

    def test_application_has_no_retrieval_or_llm_logic(self):
        import pathlib

        text = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "domain"
                / "reasoning_application.py").read_text(
                    encoding="utf-8")
        for marker in ("QdrantClient", "SentenceTransformer",
                       "OpenRouter", "httpx.", "EmbeddingProvider",
                       ".retrieve(", ".generate("):
            self.assertNotIn(marker, text)

    def test_missing_services_rejected(self):
        with self.assertRaises(ComplianceReasoningApplicationError):
            ComplianceReasoningApplication(
                structured_service=object())
        with self.assertRaises(DomainValidationError):
            analyze(make_case(), summary=None,
                    tenant_id="not-a-context")


if __name__ == "__main__":
    unittest.main()
