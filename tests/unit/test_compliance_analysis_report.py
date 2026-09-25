"""Phase 6.2 — Compliance analysis report composition tests.

Covers ``ComplianceReportService.compose``: joining multiple
Phase 6.1 ``ComplianceAnalysis`` objects plus the authoritative
Phase 3.5 decision summary into one ordered, immutable
``ComplianceAnalysisReport`` — composition arithmetic only, no
new verdict, no prose inference.
"""

import ast
import json
import unittest
from uuid import UUID

from xportra.domain.compliance_reasoning import (
    CERTAINTY_DETERMINED,
    CERTAINTY_UNCERTAIN,
    CERTAINTY_UNKNOWN,
    ComplianceAnalysis,
    ComplianceReasoningService,
    EvidenceReference,
    KnowledgeReference,
    SourceReference,
)
from xportra.domain.compliance_report import (
    ComplianceAnalysisReport,
    ComplianceReportError,
    ComplianceReportService,
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
    ComplianceDecisionSummaryService,
    EvidenceRecord,
)
from xportra.domain.llm import GeneratedAnswer, LLMResponse
from xportra.domain.answer_validation import (
    CitationAwareAnswerValidator,
)
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("11111111-1111-1111-1111-111111111111")
OTHER_TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
TENANT = TenantContext(TENANT_ID)
CASE_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
CHUNK_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")
DOCUMENT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def requirement_id(index):
    return UUID(f"00000000-0000-0000-0000-{index:012d}")


SERVICE = ComplianceReportService()
REASONING = ComplianceReasoningService()
PROMPT_CONFIG = EvidencePromptConfig(
    system_instructions="Explain the compliance position.")


def make_analysis(requirement_index=1, applicability="applicable",
                  assessment="satisfied", explanation="Reason [E1].",
                  missing=(), uncertainty=CERTAINTY_DETERMINED,
                  tenant_id=TENANT_ID, with_knowledge=True,
                  conflicting=False):
    requirement_uuid = requirement_id(requirement_index)
    knowledge = ()
    if with_knowledge:
        knowledge = (KnowledgeReference(
            label="[E1]",
            rank_position=1,
            chunk_id=CHUNK_ID,
            document_id=DOCUMENT_ID,
            source_id="sonsa/cert-guide",
            source_type="guidance",
            source_location="https://example.test/guide",
            document_version="2024.1",
            content_fingerprint="fp-1",
        ),)
    supporting = (EvidenceReference(
        evidence_id=UUID(f"66666666-6666-6666-6666-{requirement_index:012d}"),
        evidence_type="certificate",
        reference="cert://evidence",
        status="accepted",
    ),) if assessment == "satisfied" else ()
    conflicting_refs = (EvidenceReference(
        evidence_id=UUID(f"77777777-7777-7777-7777-{requirement_index:012d}"),
        evidence_type="certificate",
        reference="cert://rejected",
        status="rejected",
    ),) if conflicting else ()
    return ComplianceAnalysis(
        id=UUID(f"55555555-5555-5555-5555-{requirement_index:012d}"),
        tenant_id=tenant_id,
        requirement_id=requirement_uuid,
        requirement_text=f"Requirement {requirement_index} text.",
        applicability=applicability,
        assessment=assessment,
        explanation=explanation,
        supporting_evidence=supporting,
        conflicting_evidence=conflicting_refs,
        knowledge_references=knowledge,
        sources=(SourceReference(
            kind="regulatory_source",
            identifier="sonsa/cert-guide"),),
        missing_information=tuple(missing),
        uncertainty=uncertainty,
    )


def make_knowledge_evidence():
    return EvidenceRetrievalResult(
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


def make_summary(tenant_id=TENANT_ID):    return {
        "tenant_id": tenant_id,
        "context_fingerprint": "fp-context",
        "status": "decision_summary",
        "applicability": {"total_requirements": 1},
        "risk": {"classified_count": 0},
        "actions": {"recommendation_count": 0},
    }


def compose(*analyses, **kwargs):
    params = {"tenant_id": TENANT, "case_id": CASE_ID}
    params.update(kwargs)
    return SERVICE.compose(list(analyses), **params)


class SingleAnalysisTests(unittest.TestCase):
    def test_one_analysis_report(self):
        report = compose(make_analysis())
        self.assertIsInstance(report, ComplianceAnalysisReport)
        self.assertEqual(report.total_requirements, 1)
        self.assertEqual(report.applicable_count, 1)
        self.assertEqual(report.satisfied_count, 1)
        self.assertEqual(report.not_satisfied_count, 0)
        self.assertEqual(report.unknown_count, 0)
        self.assertEqual(report.not_applicable_count, 0)
        self.assertFalse(report.is_empty)
        self.assertEqual(report.tenant_id, TENANT_ID)
        self.assertEqual(report.case_id, CASE_ID)

    def test_report_identity_is_deterministic(self):
        first = compose(make_analysis(), make_analysis(2))
        second = compose(make_analysis(), make_analysis(2))
        self.assertEqual(first.id, second.id)


class OrderingTests(unittest.TestCase):
    def test_shuffled_input_ordered_by_requirement(self):
        report = compose(
            make_analysis(3), make_analysis(1), make_analysis(2))
        self.assertEqual(
            [a.requirement_id for a in report.analyses],
            [requirement_id(1), requirement_id(2),
             requirement_id(3)])

    def test_serialized_order_matches(self):
        report = compose(make_analysis(2), make_analysis(1))
        body = json.loads(json.dumps(report.to_record()))
        self.assertEqual(
            [a["requirement_id"] for a in body["analyses"]],
            [str(requirement_id(1)), str(requirement_id(2))])


class StatusCountTests(unittest.TestCase):
    def test_applicable_not_satisfied(self):
        report = compose(make_analysis(
            assessment="not_satisfied",
            uncertainty=CERTAINTY_DETERMINED,
            missing=("satisfying evidence not established: x",)))
        self.assertEqual(report.applicable_count, 1)
        self.assertEqual(report.satisfied_count, 0)
        self.assertEqual(report.not_satisfied_count, 1)
        self.assertEqual(report.unknown_count, 0)

    def test_applicable_unknown(self):
        report = compose(make_analysis(
            assessment="unknown", uncertainty=CERTAINTY_UNKNOWN,
            missing=("assessment incomplete: x",),
            with_knowledge=False))
        self.assertEqual(report.applicable_count, 1)
        self.assertEqual(report.unknown_count, 1)
        self.assertEqual(report.satisfied_count, 0)

    def test_not_applicable_never_satisfied(self):
        report = compose(make_analysis(
            applicability="not_applicable", assessment="unknown",
            with_knowledge=False))
        self.assertEqual(report.not_applicable_count, 1)
        self.assertEqual(report.satisfied_count, 0)
        self.assertEqual(report.unknown_count, 0)
        self.assertEqual(report.applicable_count, 0)

    def test_mixed_statuses(self):
        report = compose(
            make_analysis(1),  # satisfied
            make_analysis(2),  # satisfied
            make_analysis(3, assessment="not_satisfied",
                          uncertainty=CERTAINTY_DETERMINED),
            make_analysis(4, assessment="unknown",
                          uncertainty=CERTAINTY_UNKNOWN,
                          missing=("assessment incomplete: x",),
                          with_knowledge=False),
            make_analysis(5, applicability="not_applicable",
                          assessment="unknown", with_knowledge=False),
            make_analysis(6, applicability="unknown",
                          assessment="unknown",
                          uncertainty=CERTAINTY_UNKNOWN,
                          missing=("applicability undetermined: x",),
                          with_knowledge=False),
        )
        self.assertEqual(report.total_requirements, 6)
        self.assertEqual(report.applicable_count, 4)
        self.assertEqual(report.satisfied_count, 2)
        self.assertEqual(report.not_satisfied_count, 1)
        self.assertEqual(report.unknown_count, 2)
        self.assertEqual(report.not_applicable_count, 1)


class NoInferenceTests(unittest.TestCase):
    def test_satisfied_words_do_not_satisfy(self):
        report = compose(make_analysis(
            assessment="unknown", uncertainty=CERTAINTY_UNKNOWN,
            explanation="Compliant: true. Fully satisfied.",
            missing=("assessment incomplete: x",),
            with_knowledge=False))
        self.assertEqual(report.satisfied_count, 0)
        self.assertEqual(report.unknown_count, 1)

    def test_scope_words_do_not_alter_state(self):
        report = compose(make_analysis(
            explanation="This clearly does not apply."))
        self.assertEqual(report.applicable_count, 1)
        self.assertEqual(report.satisfied_count, 1)


class MissingAggregationTests(unittest.TestCase):
    def test_missing_bound_to_requirement(self):
        report = compose(
            make_analysis(1),
            make_analysis(2, assessment="unknown",
                          uncertainty=CERTAINTY_UNKNOWN,
                          missing=("assessment incomplete: x",
                                   "no tenant evidence linked "
                                   "to this requirement"),
                          with_knowledge=False),
        )
        self.assertEqual(
            report.requirements_with_missing_information,
            (requirement_id(2),))
        (entry,) = report.missing_information
        self.assertEqual(entry.requirement_id, requirement_id(2))
        self.assertEqual(entry.items, (
            "assessment incomplete: x",
            "no tenant evidence linked to this requirement"))

    def test_clean_requirements_excluded(self):
        report = compose(make_analysis(1), make_analysis(2))
        self.assertEqual(
            report.requirements_with_missing_information, ())
        self.assertEqual(report.missing_information, ())


class UncertaintyAggregationTests(unittest.TestCase):
    def test_uncertain_listed_unknown_not_collapsed(self):
        report = compose(
            make_analysis(1),
            make_analysis(2, uncertainty=CERTAINTY_UNCERTAIN,
                          explanation="   "),
            make_analysis(3, assessment="unknown",
                          uncertainty=CERTAINTY_UNKNOWN,
                          missing=("assessment incomplete: x",),
                          with_knowledge=False),
        )
        self.assertEqual(
            report.uncertain_requirement_ids,
            (requirement_id(2),))
        self.assertEqual(report.unknown_count, 1)


class EvidencePreservationTests(unittest.TestCase):
    def test_analysis_objects_preserved_by_reference(self):
        first = make_analysis(1)
        second = make_analysis(2)
        report = compose(second, first)
        self.assertIs(report.analyses[0], first)
        self.assertIs(report.analyses[1], second)

    def test_references_stay_with_their_requirement(self):
        report = compose(make_analysis(1), make_analysis(2))
        for analysis in report.analyses:
            for reference in analysis.supporting_evidence:
                self.assertIn(
                    str(analysis.requirement_id)[-12:],
                    str(reference.evidence_id))
            for citation in analysis.knowledge_references:
                self.assertEqual(citation.label, "[E1]")

    def test_sources_preserved(self):
        report = compose(make_analysis())
        (source,) = report.analyses[0].sources
        self.assertEqual(source.kind, "regulatory_source")
        self.assertEqual(source.identifier, "sonsa/cert-guide")

    def test_conflicting_aggregation(self):
        report = compose(
            make_analysis(1),
            make_analysis(2, assessment="not_satisfied",
                          uncertainty=CERTAINTY_DETERMINED,
                          conflicting=True))
        self.assertEqual(
            report.requirements_with_conflicting_evidence,
            (requirement_id(2),))
        self.assertEqual(report.conflicting_evidence_count, 1)

    def test_citation_labels_verbatim(self):
        report = compose(make_analysis())
        body = json.loads(json.dumps(report.to_record()))
        self.assertEqual(
            body["analyses"][0]["knowledge_references"][0]
            ["label"], "[E1]")
        self.assertEqual(
            body["analyses"][0]["knowledge_references"][0]
            ["chunk_id"], str(CHUNK_ID))


class DecisionSummaryTests(unittest.TestCase):
    def test_summary_carried_by_reference(self):
        summary = make_summary()
        report = compose(make_analysis(), decision_summary=summary)
        self.assertIs(report.decision_summary, summary)

    def test_aggregates_ignore_summary_content(self):
        summary = make_summary()
        summary = dict(
            summary, applicability={"total_requirements": 99})
        report = compose(make_analysis(), decision_summary=summary)
        self.assertEqual(report.total_requirements, 1)
        self.assertEqual(report.satisfied_count, 1)

    def test_cross_tenant_summary_rejected(self):
        with self.assertRaises(ComplianceReportError):
            compose(make_analysis(),
                    decision_summary=make_summary(OTHER_TENANT_ID))

    def test_non_mapping_summary_rejected(self):
        with self.assertRaises(ComplianceReportError):
            compose(make_analysis(), decision_summary="summary")


class RealInteropTests(unittest.TestCase):
    def _real_analysis(self, requirement_index, applicability,
                       assessment, with_citation):
        requirement_uuid = requirement_id(requirement_index)
        applicability_result = {
            "id": UUID(f"44444444-4444-4444-4444-{requirement_index:012d}"),
            "tenant_id": TENANT_ID,
            "requirement_id": requirement_uuid,
            "outcome": applicability,
            "reason": "origin and commodity match",
            "context_fingerprint": "fp-context",
            "context": {"destination": "NG"},
            "status": "determined",
        }
        requirement = {
            "id": requirement_uuid,
            "requirement_text": f"Requirement {requirement_index}.",
            "requirement_type": "documentation",
            "source_location": "https://example.test/guide",
            "source_id": "sonsa/cert-guide",
            "normalized_document_id": DOCUMENT_ID,
            "artifact_id": UUID(
                "99999999-9999-9999-9999-999999999999"),
        }
        assessment_view = None
        if applicability == "applicable" and assessment != "unknown":
            assessment_view = {
                "id": UUID(
                    f"55555555-5555-5555-5555-{requirement_index:012d}"),
                "tenant_id": TENANT_ID,
                "requirement_id": requirement_uuid,
                "applicability_result_id":
                    applicability_result["id"],
                "outcome": assessment,
                "reason": "required evidence present",
                "evidence_id": None,
                "evidence_ids": [],
                "status": "assessed",
            }
        case = ComplianceCaseService().build(
            applicability_result, requirement, assessment_view, [])
        evidence = make_knowledge_evidence() if with_citation else None
        if with_citation:
            candidates = [HybridRetrievalCandidate(
                evidence=evidence,
                semantic_score=0.9,
                lexical_score=None,
                retrieval_sources=frozenset({"semantic"}))]
            ranked = DeterministicEvidenceRanker().rank(
                candidates, top_k=1)
        else:
            ranked = []
        selection = DeterministicContextSelector().select(
            ranked, tenant_id=TENANT,
            budget=EvidenceContextBudget(4000))
        prompt = CitationAwarePromptBuilder(
            config=PROMPT_CONFIG).build(
                selection, information_need="obligation")
        answer = CitationAwareAnswerValidator().validate(
            GeneratedAnswer(
                prompt=prompt,
                response=LLMResponse(
                    generated_text="File it [E1]."
                    if with_citation else "No basis found.",
                    model_identifier="test-model"),
                tenant_id=TENANT))
        return REASONING.analyze(case, answer, tenant_id=TENANT), case

    def test_real_analyses_compose(self):
        first, _ = self._real_analysis(
            1, "applicable", "satisfied", True)
        second, _ = self._real_analysis(
            2, "not_applicable", "unknown", False)
        report = compose(second, first)
        self.assertEqual(report.total_requirements, 2)
        self.assertEqual(report.satisfied_count, 1)
        self.assertEqual(report.not_applicable_count, 1)
        self.assertEqual(
            [a.requirement_id for a in report.analyses],
            [requirement_id(1), requirement_id(2)])

    def test_real_decision_summary_referenced(self):
        _, first_case = self._real_analysis(
            1, "applicable", "satisfied", True)
        _, second_case = self._real_analysis(
            2, "not_applicable", "unknown", False)
        summary = ComplianceDecisionSummaryService().summarize(
            [first_case, second_case], tenant_id=TENANT_ID)
        self.assertEqual(summary["status"], "decision_summary")
        report = compose(
            self._real_analysis(
                1, "applicable", "satisfied", True)[0],
            decision_summary=summary)
        self.assertIs(report.decision_summary, summary)
        self.assertEqual(report.satisfied_count, 1)


class DuplicateTests(unittest.TestCase):
    def test_duplicate_requirement_rejected(self):
        with self.assertRaises(ComplianceReportError):
            compose(make_analysis(1), make_analysis(1))

    def test_same_text_different_identity_allowed(self):
        first = make_analysis(1, explanation="Same words.")
        second = make_analysis(2, explanation="Same words.")
        report = compose(first, second)
        self.assertEqual(report.total_requirements, 2)


class TenantIdentityTests(unittest.TestCase):
    def test_foreign_analysis_rejected(self):
        with self.assertRaises(ComplianceReportError):
            compose(make_analysis(tenant_id=OTHER_TENANT_ID))

    def test_non_context_tenant_rejected(self):
        from xportra.domain.errors import DomainValidationError

        with self.assertRaises(DomainValidationError):
            compose(make_analysis(), tenant_id=TENANT_ID)


class CaseIdentityTests(unittest.TestCase):
    def test_non_uuid_case_id_rejected(self):
        with self.assertRaises(ComplianceReportError):
            compose(make_analysis(), case_id="not-a-uuid")

    def test_bad_fingerprint_rejected(self):
        with self.assertRaises(ComplianceReportError):
            compose(make_analysis(), context_fingerprint="  ")
        with self.assertRaises(ComplianceReportError):
            compose(make_analysis(), context_fingerprint=42)

    def test_case_identity_scopes_report(self):
        first = compose(make_analysis(), case_id=CASE_ID)
        second = compose(
            make_analysis(),
            case_id=UUID("dddddddd-dddd-dddd-dddd-dddddddddddd"))
        self.assertNotEqual(first.id, second.id)
        fingerprinted = compose(
            make_analysis(), context_fingerprint="fp-context")
        self.assertEqual(
            fingerprinted.context_fingerprint, "fp-context")


class EmptyReportTests(unittest.TestCase):
    def test_zero_analyses_valid_without_verdict(self):
        report = compose()
        self.assertTrue(report.is_empty)
        self.assertEqual(report.total_requirements, 0)
        self.assertEqual(report.applicable_count, 0)
        self.assertEqual(report.satisfied_count, 0)
        self.assertEqual(report.not_satisfied_count, 0)
        self.assertEqual(report.unknown_count, 0)
        self.assertEqual(report.not_applicable_count, 0)
        self.assertEqual(report.analyses, ())
        self.assertFalse(hasattr(report, "verdict"))
        self.assertFalse(hasattr(report, "overall_status"))

    def test_all_not_applicable(self):
        report = compose(
            make_analysis(1, applicability="not_applicable",
                          assessment="unknown", with_knowledge=False),
            make_analysis(2, applicability="not_applicable",
                          assessment="unknown", with_knowledge=False),
        )
        self.assertEqual(report.total_requirements, 2)
        self.assertEqual(report.not_applicable_count, 2)
        self.assertEqual(report.satisfied_count, 0)
        self.assertEqual(report.unknown_count, 0)

    def test_all_unknown(self):
        report = compose(
            make_analysis(1, assessment="unknown",
                          uncertainty=CERTAINTY_UNKNOWN,
                          missing=("assessment incomplete: x",),
                          with_knowledge=False),
            make_analysis(2, applicability="unknown",
                          assessment="unknown",
                          uncertainty=CERTAINTY_UNKNOWN,
                          missing=("applicability undetermined: x",),
                          with_knowledge=False),
        )
        self.assertEqual(report.unknown_count, 2)
        self.assertEqual(report.satisfied_count, 0)
        self.assertEqual(
            report.requirements_with_missing_information,
            (requirement_id(1), requirement_id(2)))


class MalformedInputTests(unittest.TestCase):
    def test_non_sequence_rejected(self):
        with self.assertRaises(ComplianceReportError):
            SERVICE.compose(
                {"a": 1}, tenant_id=TENANT, case_id=CASE_ID)
        with self.assertRaises(ComplianceReportError):
            SERVICE.compose(
                "analyses", tenant_id=TENANT, case_id=CASE_ID)

    def test_non_analysis_items_rejected(self):
        with self.assertRaises(ComplianceReportError):
            SERVICE.compose(
                [make_analysis(), {"fake": True}],
                tenant_id=TENANT, case_id=CASE_ID)

    def test_mixed_validity_fails_closed(self):
        with self.assertRaises(ComplianceReportError):
            compose(make_analysis(1),
                    make_analysis(1, tenant_id=OTHER_TENANT_ID))


class FrameworkBoundaryTests(unittest.TestCase):
    def test_report_module_has_no_infra_imports(self):
        import pathlib

        path = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "domain" / "compliance_report.py")
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
        self.assertIn("uuid", modules)

    def test_composer_source_has_no_llm_or_retrieval(self):
        import pathlib

        text = (pathlib.Path(__file__).resolve().parents[2]
                / "xportra" / "domain"
                / "compliance_report.py").read_text(
                    encoding="utf-8")
        for marker in ("LLMClient(", ".generate(", ".query(",
                       ".retrieve(", "QdrantClient", "OpenRouter",
                       "httpx.", "compliant"):
            self.assertNotIn(marker, text)


if __name__ == "__main__":
    unittest.main()
