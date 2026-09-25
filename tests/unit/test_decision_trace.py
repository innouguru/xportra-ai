"""Phase 6.5 — Compliance reasoning decision trace tests.

Covers ``DecisionTraceService.trace``: recording which authoritative
inputs and evidence contributed to a ``ComplianceAnalysis`` as a
frozen, serializable, deterministic trace — provenance without
chain-of-thought, and never a second decision engine.

Cases are built through the REAL ``ComplianceCaseService``,
analyses through the REAL ``ComplianceReasoningService``, and
answers through the REAL Phase 5 rank/select/prompt/validate
chain — only retrieval input and the LLM are stood in. No Phase
6.1–6.4 test is modified.
"""

import ast
import inspect
import json
import unittest
from uuid import UUID

from xportra.domain.answer_validation import (
    CitationAwareAnswerValidator,
)
from xportra.domain.compliance_reasoning import (
    CERTAINTY_DETERMINED,
    CERTAINTY_UNKNOWN,
    ComplianceAnalysis,
    ComplianceReasoningService,
    EvidenceReference,
    KnowledgeReference,
    SourceReference,
)
from xportra.domain.compliance_report import ComplianceReportService
from xportra.domain.decision_trace import (
    TRACE_STEPS,
    TRACE_STEP_ANALYSIS_CONSTRUCTED,
    TRACE_STEP_DETERMINISTIC_STATE,
    TRACE_STEP_EVIDENCE_SELECTED,
    TRACE_STEP_KNOWLEDGE_RETRIEVED,
    TRACE_STEP_REASONING_GENERATED,
    TRACE_STEP_REASONING_VALIDATED,
    DecisionTrace,
    DecisionTraceError,
    DecisionTraceService,
)
from xportra.domain.errors import DomainValidationError
from xportra.domain.evidence_context import (
    DeterministicContextSelector,
    EvidenceContextBudget,
)
from xportra.domain.evidence_corpus import content_fingerprint
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

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
TENANT = TenantContext(TENANT_ID)
REQUIREMENT_ID = UUID("33333333-3333-3333-3333-333333333333")
APPLICABILITY_ID = UUID("44444444-4444-4444-4444-444444444444")
ASSESSMENT_ID = UUID("55555555-5555-5555-5555-555555555555")
EVIDENCE_ID = UUID("66666666-6666-6666-6666-666666666666")
REJECTED_ID = UUID("77777777-7777-7777-7777-777777777777")
DOCUMENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
CASE_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
REPORT_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")

SERVICE = DecisionTraceService()
REASONING = ComplianceReasoningService()
PROMPT_CONFIG = EvidencePromptConfig(
    system_instructions="Explain the compliance position."
)


def make_knowledge_evidence(**overrides):
    kwargs = dict(
        tenant_id=TENANT_ID,
        chunk_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa00"),
        document_id=DOCUMENT_ID,
        chunk_index=0,
        content="Exporters must file Form NXP before shipment.",
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


def make_validated_answer(text="Filing is required [E1].",
                           contents=("Exporters must file Form NXP.",),
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
            selection, information_need="Form NXP obligation")
    answer = GeneratedAnswer(
        prompt=prompt,
        response=LLMResponse(
            generated_text=text,
            model_identifier="test-model",
            finish_reason="stop"),
        tenant_id=TenantContext(tenant_id))
    return CitationAwareAnswerValidator().validate(answer)


def make_tenant_evidence(evidence_id=EVIDENCE_ID, status="accepted",
                         supports=True, requirement_id=REQUIREMENT_ID,
                         reference="cert://nxp-filing"):
    return EvidenceRecord(
        tenant_id=TENANT_ID,
        evidence_id=evidence_id,
        evidence_type="certificate",
        reference=reference,
        requirement_id=requirement_id,
        status=status,
        metadata={"supports_requirement": supports},
    )


def make_case(applicability_outcome="applicable",
               assessment_outcome="satisfied",
               evidence=(),
               assessment_reason="required evidence present"):
    applicability_result = {
        "id": APPLICABILITY_ID,
        "tenant_id": TENANT_ID,
        "requirement_id": REQUIREMENT_ID,
        "outcome": applicability_outcome,
        "reason": "origin and commodity match",
        "context_fingerprint": "fp-context",
        "context": {"destination": "NG"},
        "status": "determined",
    }
    requirement = {
        "id": REQUIREMENT_ID,
        "requirement_text": "Exporters must file Form NXP.",
        "requirement_type": "documentation",
        "source_location": "https://example.test/guide",
        "source_id": "sonsa/cert-guide",
        "normalized_document_id": DOCUMENT_ID,
        "artifact_id": UUID("99999999-9999-9999-9999-999999999999"),
    }
    if applicability_outcome == "applicable" and (
            assessment_outcome != "unknown" or evidence):
        assessment = {
            "id": ASSESSMENT_ID,
            "tenant_id": TENANT_ID,
            "requirement_id": REQUIREMENT_ID,
            "applicability_result_id": APPLICABILITY_ID,
            "outcome": assessment_outcome,
            "reason": assessment_reason,
            "evidence_id": EVIDENCE_ID if evidence else None,
            "evidence_ids": [r.evidence_id for r in evidence
                             if r.requirement_id == REQUIREMENT_ID],
            "status": "assessed",
        }
    else:
        assessment = None
    return ComplianceCaseService().build(
        applicability_result, requirement, assessment, list(evidence))


def make_analysis(case=None, answer=None):
    case = case if case is not None else make_case(
        evidence=[make_tenant_evidence()])
    answer = answer if answer is not None else make_validated_answer()
    return REASONING.analyze(case, answer, tenant_id=TENANT)


def trace(case=None, analysis=None, answer=None, **kwargs):
    case = case if case is not None else make_case(
        evidence=[make_tenant_evidence()])
    answer = answer if answer is not None else make_validated_answer()
    analysis = analysis if analysis is not None else make_analysis(
        case, answer)
    params = {"tenant_id": TENANT}
    params.update(kwargs)
    return SERVICE.trace(case, analysis, answer, **params)


class ConstructionTests(unittest.TestCase):
    def test_valid_trace_shape(self):
        result = trace()
        self.assertIsInstance(result, DecisionTrace)
        self.assertEqual(result.tenant_id, TENANT_ID)
        self.assertEqual(result.requirement_id, REQUIREMENT_ID)
        self.assertEqual(result.applicability, "applicable")
        self.assertEqual(result.assessment, "satisfied")
        self.assertEqual(result.explanation,
                         "Filing is required [E1].")
        self.assertEqual(result.report_id, None)
        self.assertEqual(len(result.steps), 6)
        self.assertEqual([s.name for s in result.steps],
                         list(TRACE_STEPS))
        self.assertEqual([s.sequence for s in result.steps],
                         [1, 2, 3, 4, 5, 6])

    def test_single_requirement_trace_with_report_binding(self):
        result = trace(report_id=REPORT_ID)
        self.assertEqual(result.report_id, REPORT_ID)
        body = json.loads(json.dumps(result.to_record()))
        self.assertEqual(body["report_id"], str(REPORT_ID))

    def test_multi_evidence_trace(self):
        case = make_case(evidence=[
            make_tenant_evidence(),
            make_tenant_evidence(
                evidence_id=UUID(
                    "66666666-6666-6666-6666-666666666667"),
                reference="cert://second-filing"),
        ])
        answer = make_validated_answer()
        result = trace(case, make_analysis(case, answer), answer)
        self.assertEqual(len(result.supporting_evidence), 2)
        step = result.steps[1]
        self.assertEqual(step.name, TRACE_STEP_EVIDENCE_SELECTED)
        self.assertIn("supporting=2", step.detail)
        self.assertEqual(len(step.references), 2)

    def test_conflicting_evidence_trace(self):
        case = make_case(
            assessment_outcome="not_satisfied",
            evidence=[make_tenant_evidence(
                evidence_id=REJECTED_ID, status="rejected",
                supports=False)],
            assessment_reason="evidence rejected")
        answer = make_validated_answer()
        result = trace(case, make_analysis(case, answer), answer)
        self.assertEqual(len(result.conflicting_evidence), 1)
        self.assertEqual(result.contradiction_state, "present")
        self.assertEqual(result.assessment, "not_satisfied")

    def test_uncertainty_trace(self):
        case = make_case(
            assessment_outcome="unknown", evidence=[],
            assessment_reason="required evidence absent")
        answer = make_validated_answer(text="No basis found.",
                                        contents=())
        result = trace(case, make_analysis(case, answer), answer)
        self.assertEqual(result.uncertainty, CERTAINTY_UNKNOWN)
        self.assertEqual(result.evidence_sufficiency, "missing")
        self.assertTrue(result.missing_information)

    def test_missing_information_trace(self):
        case = make_case(
            assessment_outcome="unknown", evidence=[],
            assessment_reason="required evidence absent")
        answer = make_validated_answer(text="No basis found.",
                                        contents=())
        result = trace(case, make_analysis(case, answer), answer)
        self.assertIn("no tenant evidence linked to this requirement",
                      result.missing_information)
        self.assertEqual(result.context_fingerprint, "fp-context")

    def test_trace_serializes_with_exact_keys(self):
        body = json.loads(json.dumps(trace().to_record()))
        self.assertEqual(
            set(body),
            {"id", "tenant_id", "case_id", "requirement_id",
             "analysis_id", "report_id", "context_fingerprint",
             "applicability", "assessment", "supporting_evidence",
             "conflicting_evidence", "knowledge_references",
             "sources", "explanation", "evidence_sufficiency",
             "contradiction_state", "sufficiency_explanation",
             "uncertainty", "missing_information",
             "answer_fingerprint", "input_fingerprint", "steps"})


class ProvenanceTests(unittest.TestCase):
    def test_evidence_references_preserved(self):
        result = trace()
        self.assertEqual(len(result.supporting_evidence), 1)
        reference = result.supporting_evidence[0]
        self.assertEqual(reference.evidence_id, EVIDENCE_ID)
        self.assertEqual(reference.reference, "cert://nxp-filing")
        self.assertEqual(reference.status, "accepted")

    def test_knowledge_references_preserved(self):
        result = trace()
        (knowledge,) = result.knowledge_references
        self.assertEqual(knowledge.label, "[E1]")
        self.assertEqual(knowledge.document_id, DOCUMENT_ID)
        self.assertEqual(knowledge.source_id, "sonsa/cert-guide")
        self.assertEqual(knowledge.content_fingerprint, "fp-0")

    def test_source_references_preserved(self):
        result = trace()
        by_kind = {s.kind: s.identifier for s in result.sources}
        self.assertEqual(by_kind["regulatory_source"],
                         "sonsa/cert-guide")
        self.assertEqual(by_kind["document"], str(DOCUMENT_ID))

    def test_requirement_association_preserved(self):
        case = make_case(evidence=[make_tenant_evidence()])
        answer = make_validated_answer()
        analysis = make_analysis(case, answer)
        result = trace(case, analysis, answer)
        self.assertEqual(result.requirement_id, REQUIREMENT_ID)
        self.assertEqual(result.requirement_id,
                         analysis.requirement_id)
        self.assertEqual(result.analysis_id, analysis.id)

    def test_case_association_preserved(self):
        case = make_case(evidence=[make_tenant_evidence()])
        answer = make_validated_answer()
        result = trace(case, make_analysis(case, answer), answer)
        self.assertEqual(result.case_id, case["id"])

    def test_tenant_association_preserved(self):
        result = trace()
        self.assertEqual(result.tenant_id, TENANT_ID)


class IntegrityTests(unittest.TestCase):
    def test_foreign_tenant_case_rejected(self):
        case = dict(make_case(evidence=[make_tenant_evidence()]),
                    tenant_id=OTHER_TENANT_ID)
        with self.assertRaises(DecisionTraceError):
            SERVICE.trace(case, make_analysis(),
                          make_validated_answer(), tenant_id=TENANT)

    def test_foreign_case_requirement_rejected(self):
        case = make_case(evidence=[make_tenant_evidence()])
        other_analysis = ComplianceAnalysis(
            id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            tenant_id=TENANT_ID,
            requirement_id=UUID(
                "99999999-9999-9999-9999-999999999999"),
            requirement_text="Another requirement.",
            applicability="applicable",
            assessment="satisfied",
            explanation="Other [E1].",
            supporting_evidence=(),
            conflicting_evidence=(),
            knowledge_references=(),
            sources=(),
            missing_information=(),
            uncertainty=CERTAINTY_DETERMINED,
        )
        with self.assertRaises(DecisionTraceError):
            SERVICE.trace(case, other_analysis,
                          make_validated_answer(), tenant_id=TENANT)

    def test_unknown_evidence_rejected(self):
        case = make_case(evidence=[make_tenant_evidence()])
        answer = make_validated_answer()
        analysis = make_analysis(case, answer)
        foreign = EvidenceReference(
            evidence_id=UUID(
                "99999999-9999-9999-9999-999999999999"),
            evidence_type="certificate",
            reference="cert://unknown",
            status="accepted",
        )
        tampered = ComplianceAnalysis(
            id=analysis.id, tenant_id=analysis.tenant_id,
            requirement_id=analysis.requirement_id,
            requirement_text=analysis.requirement_text,
            applicability=analysis.applicability,
            assessment=analysis.assessment,
            explanation=analysis.explanation,
            supporting_evidence=(
                *analysis.supporting_evidence, foreign),
            conflicting_evidence=(),
            knowledge_references=(),
            sources=analysis.sources,
            missing_information=(),
            uncertainty=analysis.uncertainty)
        with self.assertRaises(DecisionTraceError):
            SERVICE.trace(case, tampered, answer, tenant_id=TENANT)

    def test_unknown_source_rejected(self):
        case = make_case(evidence=[make_tenant_evidence()])
        answer = make_validated_answer()
        analysis = make_analysis(case, answer)
        tampered_sources = (
            SourceReference(kind="regulatory_source",
                            identifier="unknown/source"),)
        tampered = ComplianceAnalysis(
            id=analysis.id, tenant_id=analysis.tenant_id,
            requirement_id=analysis.requirement_id,
            requirement_text=analysis.requirement_text,
            applicability=analysis.applicability,
            assessment=analysis.assessment,
            explanation=analysis.explanation,
            supporting_evidence=analysis.supporting_evidence,
            conflicting_evidence=analysis.conflicting_evidence,
            knowledge_references=analysis.knowledge_references,
            sources=tampered_sources,
            missing_information=analysis.missing_information,
            uncertainty=analysis.uncertainty)
        with self.assertRaises(DecisionTraceError):
            SERVICE.trace(case, tampered, answer, tenant_id=TENANT)

    def test_analysis_case_divergence_rejected(self):
        case = make_case(evidence=[make_tenant_evidence()])
        answer = make_validated_answer()
        analysis = make_analysis(case, answer)
        diverged = dict(
            case, assessment=dict(case["assessment"],
                                 outcome="not_satisfied"))
        with self.assertRaises(DecisionTraceError):
            SERVICE.trace(diverged, analysis, answer,
                          tenant_id=TENANT)

    def test_model_supplied_ids_rejected(self):
        case = make_case(evidence=[make_tenant_evidence()])
        with self.assertRaises(DecisionTraceError):
            SERVICE.trace(case, {"id": str(REQUIREMENT_ID)},
                          make_validated_answer(), tenant_id=TENANT)
        with self.assertRaises(DecisionTraceError):
            SERVICE.trace(
                case, make_analysis(), "satisfied because reasons",
                tenant_id=TENANT)

    def test_invalid_citation_mapping_rejected(self):
        from xportra.domain.llm import GeneratedAnswer

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
        with self.assertRaises(DecisionTraceError):
            SERVICE.trace(make_case(), make_analysis(), bad,
                          tenant_id=TENANT)

    def test_mismatched_answer_citation_mapping_rejected(self):
        case = make_case(evidence=[make_tenant_evidence()])
        cited = make_validated_answer()
        analysis = make_analysis(case, cited)
        uncited = make_validated_answer(text="No basis found.",
                                        contents=())
        with self.assertRaises(DecisionTraceError):
            SERVICE.trace(case, analysis, uncited, tenant_id=TENANT)

    def test_raw_unvalidated_reasoning_rejected(self):
        from xportra.domain.answer_validation import (
            CitationAwareAnswerValidator,
        )

        case = make_case(evidence=[make_tenant_evidence()])
        selection_answer = make_validated_answer()
        raw = selection_answer.answer
        self.assertIsInstance(raw, GeneratedAnswer)
        with self.assertRaises(DecisionTraceError):
            SERVICE.trace(case, make_analysis(), raw,
                          tenant_id=TENANT)


class DeterminismTests(unittest.TestCase):
    def test_equivalent_inputs_produce_equivalent_trace(self):
        first = trace()
        second = trace()
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.input_fingerprint,
                         second.input_fingerprint)
        self.assertEqual(first.answer_fingerprint,
                         second.answer_fingerprint)
        self.assertEqual(first.to_record(), second.to_record())

    def test_canonical_step_order_is_stable(self):
        result = trace()
        self.assertEqual(
            [step.sequence for step in result.steps],
            sorted(step.sequence for step in result.steps))
        self.assertEqual(result.steps[0].name,
                         TRACE_STEP_DETERMINISTIC_STATE)
        self.assertEqual(result.steps[2].name,
                         TRACE_STEP_KNOWLEDGE_RETRIEVED)
        self.assertEqual(result.steps[3].name,
                         TRACE_STEP_REASONING_GENERATED)
        self.assertEqual(result.steps[4].name,
                         TRACE_STEP_REASONING_VALIDATED)
        self.assertEqual(result.steps[5].name,
                         TRACE_STEP_ANALYSIS_CONSTRUCTED)

    def test_meaningful_change_alters_fingerprint(self):
        baseline = trace()
        other_answer = make_validated_answer(
            text="Filing is required before shipment [E1].")
        case = make_case(evidence=[make_tenant_evidence()])
        changed = trace(case,
                        make_analysis(case, other_answer),
                        other_answer)
        self.assertNotEqual(changed.input_fingerprint,
                            baseline.input_fingerprint)
        self.assertNotEqual(changed.id, baseline.id)
        self.assertNotEqual(changed.answer_fingerprint,
                            baseline.answer_fingerprint)

    def test_answer_fingerprint_matches_fingerprint_scheme(self):
        answer = make_validated_answer()
        result = trace(answer=answer)
        self.assertEqual(result.answer_fingerprint,
                         content_fingerprint(answer.answer_text))


class SecurityPrivacyTests(unittest.TestCase):
    def test_no_secret_or_prompt_leakage(self):
        body = json.dumps(trace().to_record()).lower()
        for marker in ("system_instructions", "api_key", "apikey",
                       "chain_of_thought", "scratchpad",
                       "hidden_state", "token-by-token",
                       "openrouter", "qdrant", "bearer "):
            self.assertNotIn(marker, body)

    def test_no_raw_prompt_or_provider_objects(self):
        result = trace()
        self.assertFalse(hasattr(result, "prompt"))
        self.assertFalse(hasattr(result, "generated_answer"))
        self.assertFalse(hasattr(result, "llm_response"))
        for step in result.steps:
            self.assertFalse(hasattr(step, "prompt"))

    def test_trace_takes_no_secret_capable_inputs(self):
        params = set(inspect.signature(
            DecisionTraceService.trace).parameters)
        self.assertTrue(
            params.isdisjoint(
                {"prompt", "system_instructions", "api_key",
                 "secret", "provider", "model reasoning"}))

    def test_malformed_report_identity_rejected(self):
        with self.assertRaises(DecisionTraceError):
            trace(report_id="not-a-uuid")

    def test_missing_tenant_context_rejected(self):
        with self.assertRaises(DomainValidationError):
            SERVICE.trace(make_case(), make_analysis(),
                          make_validated_answer(),
                          tenant_id="not-a-context")


class StatePreservationTests(unittest.TestCase):
    def test_applicability_and_assessment_unchanged(self):
        case = make_case(
            assessment_outcome="not_satisfied",
            evidence=[make_tenant_evidence(
                evidence_id=REJECTED_ID, status="rejected",
                supports=False)],
            assessment_reason="evidence rejected")
        answer = make_validated_answer()
        analysis = make_analysis(case, answer)
        result = trace(case, analysis, answer)
        self.assertEqual(result.applicability,
                         analysis.applicability)
        self.assertEqual(result.assessment, analysis.assessment)
        self.assertEqual(result.uncertainty, analysis.uncertainty)
        self.assertEqual(result.evidence_sufficiency,
                         analysis.evidence_sufficiency)
        self.assertEqual(result.contradiction_state,
                         analysis.contradiction_state)

    def test_decision_reference_unchanged(self):
        case = make_case(evidence=[make_tenant_evidence()])
        answer = make_validated_answer()
        analysis = make_analysis(case, answer)
        summary = {"tenant_id": TENANT_ID, "status": "summary"}
        report = ComplianceReportService().compose(
            [analysis], tenant_id=TENANT, case_id=CASE_ID,
            decision_summary=summary)
        result = trace(case, analysis, answer,
                       report_id=report.id)
        self.assertEqual(result.report_id, report.id)
        self.assertIs(report.decision_summary, summary)
        self.assertEqual(result.context_fingerprint,
                         case["context_fingerprint"])

    def test_trace_records_without_deciding(self):
        result = trace()
        self.assertFalse(hasattr(result, "verdict"))
        self.assertFalse(hasattr(result, "risk"))
        self.assertFalse(hasattr(result, "action"))
        body = result.to_record()
        self.assertNotIn("verdict", body)
        self.assertNotIn("risk_state", body)
        self.assertNotIn("action_type", body)


class FrameworkBoundaryTests(unittest.TestCase):
    def test_trace_module_has_no_infra_imports(self):
        import pathlib

        path = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "domain" / "decision_trace.py")
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
        self.assertIn("json", modules)

    def test_trace_module_has_no_retrieval_or_llm_logic(self):
        import pathlib

        text = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "domain"
                / "decision_trace.py").read_text(encoding="utf-8")
        for marker in ("QdrantClient", "SentenceTransformer",
                       "OpenRouter", "httpx.", "EmbeddingProvider",
                       ".retrieve(", ".generate("):
            self.assertNotIn(marker, text)


if __name__ == "__main__":
    unittest.main()
