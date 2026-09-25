"""Phase 6.1 — Deterministic compliance reasoning contract tests.

Covers ``ComplianceReasoningService.analyze`` (pure composition of
a Phase 2.7 compliance case view and a Phase 5.12
``ValidatedAnswer``) and the thin ``analyze_with_knowledge``
delegation seam to an injected ``RAGApplicationService``.

Cases are built through the REAL ``ComplianceCaseService`` and
answers through the REAL Phase 5 rank/select/prompt/validate
chain — only retrieval (the fake pipeline/selection input) and
the LLM (scripted responses) are stood in, so state-preservation
and reference-integrity assertions exercise the real objects.
"""

import ast
import json
import unittest
from uuid import UUID

from xportra.domain.answer_validation import (
    CitationAwareAnswerValidator,
    VALIDATION_STATUS_EMPTY,
    VALIDATION_STATUS_INVALID_CITATIONS,
    VALIDATION_STATUS_VALID,
    ValidatedAnswer,
)
from xportra.domain.compliance_reasoning import (
    CERTAINTY_DETERMINED,
    CERTAINTY_UNCERTAIN,
    CERTAINTY_UNKNOWN,
    ComplianceAnalysis,
    ComplianceReasoningError,
    ComplianceReasoningService,
)
from xportra.domain.errors import LLMProviderError, VectorStoreError
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

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
TENANT = TenantContext(TENANT_ID)
REQUIREMENT_ID = UUID("33333333-3333-3333-3333-333333333333")
APPLICABILITY_ID = UUID("44444444-4444-4444-4444-444444444444")
ASSESSMENT_ID = UUID("55555555-5555-5555-5555-555555555555")
EVIDENCE_ID = UUID("66666666-6666-6666-6666-666666666666")
REJECTED_ID = UUID("77777777-7777-7777-7777-777777777777")
CHUNK_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")
DOCUMENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

SERVICE = ComplianceReasoningService()
PROMPT_CONFIG = EvidencePromptConfig(
    system_instructions="Explain the compliance position."
)


def make_knowledge_evidence(**overrides):
    kwargs = dict(
        tenant_id=TENANT_ID,
        chunk_id=CHUNK_ID,
        document_id=DOCUMENT_ID,
        chunk_index=0,
        content="Exporters must file Form NXP before shipment.",
        content_fingerprint="fp-1",
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
        # Genuine empty context: the selector's valid empty path.
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
                         supports=True, requirement_id=REQUIREMENT_ID):
    return EvidenceRecord(
        tenant_id=TENANT_ID,
        evidence_id=evidence_id,
        evidence_type="certificate",
        reference="cert://nxp-filing",
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


class FakeRAGService:
    def __init__(self, answer=None, failure=None):
        self._answer = answer
        self._failure = failure
        self.calls = []

    def query(self, information_need, *, tenant_id, mode,
              context_budget, scope=None, top_k=5,
              candidate_pool=None):
        self.calls.append({
            "information_need": information_need,
            "tenant_id": tenant_id,
            "mode": mode,
            "context_budget": context_budget,
            "scope": scope,
            "top_k": top_k,
            "candidate_pool": candidate_pool,
        })
        if self._failure is not None:
            raise self._failure
        return self._answer


class ValidResultTests(unittest.TestCase):
    def test_full_analysis_shape(self):
        case = make_case(evidence=[make_tenant_evidence()])
        analysis = SERVICE.analyze(
            case, make_validated_answer(), tenant_id=TENANT)
        self.assertIsInstance(analysis, ComplianceAnalysis)
        self.assertEqual(analysis.requirement_id, REQUIREMENT_ID)
        self.assertEqual(
            analysis.requirement_text, "Exporters must file Form NXP.")
        self.assertEqual(analysis.applicability, "applicable")
        self.assertEqual(analysis.assessment, "satisfied")
        self.assertEqual(
            analysis.explanation, "Filing is required [E1].")
        self.assertEqual(len(analysis.supporting_evidence), 1)
        self.assertEqual(
            analysis.supporting_evidence[0].evidence_id, EVIDENCE_ID)
        self.assertEqual(analysis.conflicting_evidence, ())
        self.assertEqual(len(analysis.knowledge_references), 1)
        self.assertEqual(
            analysis.knowledge_references[0].label, "[E1]")
        self.assertEqual(analysis.missing_information, ())
        self.assertEqual(analysis.uncertainty, CERTAINTY_DETERMINED)

    def test_result_serializes_for_downstream_use(self):
        case = make_case(evidence=[make_tenant_evidence()])
        analysis = SERVICE.analyze(
            case, make_validated_answer(), tenant_id=TENANT)
        rendered = json.dumps(analysis.to_record())
        body = json.loads(rendered)
        self.assertEqual(body["applicability"], "applicable")
        self.assertEqual(body["assessment"], "satisfied")
        self.assertEqual(body["uncertainty"], CERTAINTY_DETERMINED)
        self.assertEqual(body["knowledge_references"][0]["label"],
                         "[E1]")

    def test_analysis_identity_is_deterministic(self):
        case = make_case(evidence=[make_tenant_evidence()])
        first = SERVICE.analyze(
            case, make_validated_answer(), tenant_id=TENANT)
        second = SERVICE.analyze(
            case, make_validated_answer(), tenant_id=TENANT)
        self.assertEqual(first.id, second.id)


class ApplicabilityTests(unittest.TestCase):
    def test_applicable_preserved(self):
        analysis = SERVICE.analyze(
            make_case(evidence=[make_tenant_evidence()]),
            make_validated_answer(), tenant_id=TENANT)
        self.assertEqual(analysis.applicability, "applicable")

    def test_not_applicable_preserved_with_no_missing(self):
        case = make_case(applicability_outcome="not_applicable")
        analysis = SERVICE.analyze(
            case, make_validated_answer("Not in scope [E1]."),
            tenant_id=TENANT)
        self.assertEqual(analysis.applicability, "not_applicable")
        self.assertEqual(analysis.assessment, "unknown")
        self.assertEqual(analysis.missing_information, ())
        self.assertEqual(analysis.uncertainty, CERTAINTY_DETERMINED)

    def test_unknown_applicability_flagged(self):
        case = make_case(applicability_outcome="unknown")
        analysis = SERVICE.analyze(
            case, make_validated_answer(), tenant_id=TENANT)
        self.assertEqual(analysis.applicability, "unknown")
        self.assertEqual(analysis.uncertainty, CERTAINTY_UNKNOWN)
        self.assertTrue(any(
            entry.startswith("applicability undetermined:")
            for entry in analysis.missing_information))


class AssessmentTests(unittest.TestCase):
    def test_satisfied_determined(self):
        analysis = SERVICE.analyze(
            make_case(evidence=[make_tenant_evidence()]),
            make_validated_answer(), tenant_id=TENANT)
        self.assertEqual(analysis.assessment, "satisfied")
        self.assertEqual(analysis.uncertainty, CERTAINTY_DETERMINED)
        self.assertEqual(analysis.missing_information, ())

    def test_not_satisfied_determined_with_gap(self):
        case = make_case(
            assessment_outcome="not_satisfied",
            evidence=[make_tenant_evidence(
                evidence_id=REJECTED_ID, status="rejected",
                supports=False)],
            assessment_reason="evidence rejected")
        analysis = SERVICE.analyze(
            case, make_validated_answer(), tenant_id=TENANT)
        self.assertEqual(analysis.assessment, "not_satisfied")
        self.assertEqual(analysis.uncertainty, CERTAINTY_DETERMINED)
        self.assertTrue(any(
            entry.startswith(
                "satisfying evidence not established:")
            for entry in analysis.missing_information))

    def test_unknown_assessment_with_nothing_linked(self):
        case = make_case(
            assessment_outcome="unknown", evidence=[],
            assessment_reason="required evidence absent")
        answer = make_validated_answer(
            text="No basis found.", contents=())
        analysis = SERVICE.analyze(case, answer, tenant_id=TENANT)
        self.assertEqual(analysis.assessment, "unknown")
        self.assertEqual(analysis.uncertainty, CERTAINTY_UNKNOWN)
        self.assertIn(
            "assessment incomplete: requirement cannot yet be assessed",
            analysis.missing_information)
        self.assertIn(
            "no tenant evidence linked to this requirement",
            analysis.missing_information)
        self.assertIn(
            "no retrieved knowledge evidence cited",
            analysis.missing_information)


class ConflictingEvidenceTests(unittest.TestCase):
    def test_rejected_evidence_is_conflicting_not_supporting(self):
        case = make_case(
            assessment_outcome="not_satisfied",
            evidence=[make_tenant_evidence(
                evidence_id=REJECTED_ID, status="rejected",
                supports=False)],
            assessment_reason="evidence rejected")
        analysis = SERVICE.analyze(
            case, make_validated_answer(), tenant_id=TENANT)
        self.assertEqual(len(analysis.conflicting_evidence), 1)
        self.assertEqual(
            analysis.conflicting_evidence[0].evidence_id,
            REJECTED_ID)
        self.assertEqual(analysis.supporting_evidence, ())

    def test_archived_evidence_is_conflicting(self):
        case = make_case(
            assessment_outcome="unknown",
            evidence=[make_tenant_evidence(status="archived",
                                           supports=False)],
            assessment_reason="evidence insufficient")
        analysis = SERVICE.analyze(
            case, make_validated_answer(), tenant_id=TENANT)
        self.assertEqual(len(analysis.conflicting_evidence), 1)
        self.assertEqual(analysis.supporting_evidence, ())


class ProvenanceTests(unittest.TestCase):
    def test_knowledge_provenance_matches_retrieved_objects(self):
        analysis = SERVICE.analyze(
            make_case(evidence=[make_tenant_evidence()]),
            make_validated_answer(), tenant_id=TENANT)
        (reference,) = analysis.knowledge_references
        self.assertEqual(reference.chunk_id, UUID(
            "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaa00"))
        self.assertEqual(reference.document_id, DOCUMENT_ID)
        self.assertEqual(reference.source_id, "sonsa/cert-guide")
        self.assertEqual(
            reference.content_fingerprint, "fp-0")

    def test_case_sources_preserved(self):
        analysis = SERVICE.analyze(
            make_case(), make_validated_answer(), tenant_id=TENANT)
        by_kind = {s.kind: s.identifier for s in analysis.sources}
        self.assertEqual(by_kind["regulatory_source"],
                         "sonsa/cert-guide")
        self.assertEqual(by_kind["document"], str(DOCUMENT_ID))


class CitationIntegrityTests(unittest.TestCase):
    def test_invalid_citations_fail_closed(self):
        from xportra.domain.llm import GeneratedAnswer

        validator = CitationAwareAnswerValidator(
            fail_on_invalid_citations=False)
        answer = make_validated_answer(text="See [E1].")
        other = GeneratedAnswer(
            prompt=answer.answer.prompt,
            response=LLMResponse(
                generated_text="See [E9].",
                model_identifier="test-model"),
            tenant_id=TENANT)
        bad = validator.validate(other)
        self.assertEqual(
            bad.status, VALIDATION_STATUS_INVALID_CITATIONS)
        with self.assertRaises(ComplianceReasoningError):
            SERVICE.analyze(make_case(), bad, tenant_id=TENANT)

    def test_citations_come_from_mapping_not_text(self):
        answer = make_validated_answer(
            text="Filing is required [E1].")
        analysis = SERVICE.analyze(
            make_case(), answer, tenant_id=TENANT)
        self.assertIs(
            analysis.knowledge_references[0].label,
            answer.validated_citations[0].label)
        self.assertEqual(
            [r.label for r in analysis.knowledge_references],
            list(answer.extraction.references))

    def test_model_verdict_claim_changes_nothing(self):
        case = make_case(
            assessment_outcome="unknown", evidence=[],
            assessment_reason="required evidence absent")
        answer = make_validated_answer(
            text="Compliant: true. Fully satisfied [E1].")
        analysis = SERVICE.analyze(case, answer, tenant_id=TENANT)
        self.assertEqual(analysis.assessment, "unknown")
        self.assertEqual(analysis.applicability, "applicable")
        self.assertEqual(analysis.uncertainty, CERTAINTY_UNKNOWN)
        self.assertEqual(
            analysis.explanation,
            "Compliant: true. Fully satisfied [E1].")


class TenantIsolationTests(unittest.TestCase):
    def test_case_tenant_mismatch_rejected(self):
        case = make_case()
        case = dict(case, tenant_id=OTHER_TENANT_ID)
        with self.assertRaises(ComplianceReasoningError):
            SERVICE.analyze(
                case, make_validated_answer(), tenant_id=TENANT)

    def test_answer_tenant_mismatch_rejected(self):
        answer = make_validated_answer(tenant_id=OTHER_TENANT_ID)
        with self.assertRaises(ComplianceReasoningError):
            SERVICE.analyze(make_case(), answer, tenant_id=TENANT)

    def test_empty_knowledge_without_provenance_allowed(self):
        case = make_case(
            assessment_outcome="unknown", evidence=[],
            assessment_reason="required evidence absent")
        candidates_answer = make_validated_answer(
            text="   ", contents=())
        self.assertEqual(
            candidates_answer.status, VALIDATION_STATUS_EMPTY)
        self.assertIsNone(candidates_answer.tenant_id)
        analysis = SERVICE.analyze(
            case, candidates_answer, tenant_id=TENANT)
        self.assertEqual(analysis.tenant_id, TENANT_ID)
        self.assertEqual(analysis.knowledge_references, ())


class MalformedDataTests(unittest.TestCase):
    def test_non_dict_case_rejected(self):
        with self.assertRaises(ComplianceReasoningError):
            SERVICE.analyze(
                "not a case", make_validated_answer(),
                tenant_id=TENANT)

    def test_bad_applicability_outcome_rejected(self):
        case = make_case()
        case = dict(
            case,
            applicability=dict(
                case["applicability"], outcome="maybe"))
        with self.assertRaises(ComplianceReasoningError):
            SERVICE.analyze(
                case, make_validated_answer(), tenant_id=TENANT)

    def test_bad_assessment_outcome_rejected(self):
        case = make_case(evidence=[make_tenant_evidence()])
        case = dict(
            case,
            assessment=dict(case["assessment"], outcome="pending"))
        with self.assertRaises(ComplianceReasoningError):
            SERVICE.analyze(
                case, make_validated_answer(), tenant_id=TENANT)

    def test_decisive_assessment_on_non_applicable_rejected(self):
        case = make_case(applicability_outcome="not_applicable")
        case = dict(
            case,
            assessment=dict(case["assessment"], outcome="satisfied"))
        with self.assertRaises(ComplianceReasoningError):
            SERVICE.analyze(
                case, make_validated_answer(), tenant_id=TENANT)

    def test_malformed_evidence_and_citations_rejected(self):
        case = make_case()
        case = dict(case, evidence=[{"nope": True}])
        with self.assertRaises(ComplianceReasoningError):
            SERVICE.analyze(
                case, make_validated_answer(), tenant_id=TENANT)
        with self.assertRaises(ComplianceReasoningError):
            SERVICE.analyze(
                make_case(), "not an answer", tenant_id=TENANT)

    def test_missing_tenant_context_rejected(self):
        from xportra.domain.errors import DomainValidationError

        with self.assertRaises(DomainValidationError):
            SERVICE.analyze(
                make_case(), make_validated_answer(),
                tenant_id="not-a-context")


class OverrideResistanceTests(unittest.TestCase):
    def test_unknown_never_becomes_satisfied(self):
        case = make_case(
            assessment_outcome="unknown",
            evidence=[make_tenant_evidence(
                status="uploaded", supports=False)],
            assessment_reason="evidence insufficient")
        answer = make_validated_answer(
            text="All requirements satisfied [E1].")
        analysis = SERVICE.analyze(case, answer, tenant_id=TENANT)
        self.assertEqual(analysis.assessment, "unknown")
        self.assertEqual(analysis.uncertainty, CERTAINTY_UNKNOWN)

    def test_not_applicable_never_becomes_applicable(self):
        case = make_case(applicability_outcome="not_applicable")
        answer = make_validated_answer(
            text="This clearly applies [E1].")
        analysis = SERVICE.analyze(case, answer, tenant_id=TENANT)
        self.assertEqual(analysis.applicability, "not_applicable")
        self.assertEqual(analysis.assessment, "unknown")


class EmptyOutputTests(unittest.TestCase):
    def test_empty_explanation_on_decisive_state(self):
        case = make_case(evidence=[make_tenant_evidence()])
        analysis = SERVICE.analyze(
            case, make_validated_answer(text="   "),
            tenant_id=TENANT)
        self.assertEqual(analysis.explanation, "   ")
        self.assertEqual(analysis.assessment, "satisfied")
        self.assertEqual(analysis.uncertainty, CERTAINTY_UNCERTAIN)
        self.assertIn("model produced no explanation",
                      analysis.missing_information)

    def test_empty_explanation_on_unknown_state(self):
        case = make_case(
            assessment_outcome="unknown", evidence=[],
            assessment_reason="required evidence absent")
        analysis = SERVICE.analyze(
            case,
            make_validated_answer(text="   ", contents=()),
            tenant_id=TENANT)
        self.assertEqual(analysis.uncertainty, CERTAINTY_UNKNOWN)
        self.assertIn("model produced no explanation",
                      analysis.missing_information)


class ProviderFailureTests(unittest.TestCase):
    def test_llm_failure_propagates_without_analysis(self):
        rag = FakeRAGService(failure=LLMProviderError(
            "generate", RuntimeError("provider down")))
        with self.assertRaises(LLMProviderError):
            SERVICE.analyze_with_knowledge(
                make_case(), "need", tenant_id=TENANT,
                rag_service=rag, mode="hybrid",
                context_budget=EvidenceContextBudget(4000))

    def test_vector_failure_propagates_without_analysis(self):
        rag = FakeRAGService(failure=VectorStoreError(
            "find", RuntimeError("index down")))
        with self.assertRaises(VectorStoreError):
            SERVICE.analyze_with_knowledge(
                make_case(), "need", tenant_id=TENANT,
                rag_service=rag, mode="hybrid",
                context_budget=EvidenceContextBudget(4000))

    def test_orchestration_forwards_and_analyzes(self):
        answer = make_validated_answer()
        rag = FakeRAGService(answer=answer)
        budget = EvidenceContextBudget(1500)
        analysis = SERVICE.analyze_with_knowledge(
            make_case(evidence=[make_tenant_evidence()]),
            "  Form NXP  ", tenant_id=TENANT, rag_service=rag,
            mode="semantic", context_budget=budget,
            top_k=3, candidate_pool=7)
        self.assertEqual(len(rag.calls), 1)
        call = rag.calls[0]
        self.assertEqual(call["tenant_id"], TENANT)
        self.assertEqual(call["mode"], "semantic")
        self.assertIs(call["context_budget"], budget)
        self.assertEqual(call["top_k"], 3)
        self.assertEqual(call["candidate_pool"], 7)
        self.assertEqual(analysis.uncertainty, CERTAINTY_DETERMINED)

    def test_missing_rag_service_rejected(self):
        with self.assertRaises(ComplianceReasoningError):
            SERVICE.analyze_with_knowledge(
                make_case(), "need", tenant_id=TENANT,
                rag_service=None, mode="hybrid",
                context_budget=EvidenceContextBudget(4000))


class FrameworkBoundaryTests(unittest.TestCase):
    def test_reasoning_module_has_no_infra_imports(self):
        import pathlib

        path = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "domain" / "compliance_reasoning.py")
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
        # Relative sibling-domain imports only; stdlib otherwise.
        self.assertIn("uuid", modules)

    def test_service_source_has_no_retrieval_or_llm_logic(self):
        import pathlib

        text = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "domain"
                / "compliance_reasoning.py").read_text(
                    encoding="utf-8")
        for marker in ("QdrantClient", "SentenceTransformer",
                       "OpenRouter", "httpx.", "EmbeddingProvider",
                       ".retrieve(", ".generate("):
            self.assertNotIn(marker, text)


if __name__ == "__main__":
    unittest.main()
