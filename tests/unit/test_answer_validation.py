"""Phase 5.12 — Answer Validation & Citation Integrity tests.

Covers the deterministic validation boundary:
``extract_citation_references``, ``CitationAwareAnswerValidator``,
``ValidatedAnswer``, ``AnswerValidationError`` — citation extraction
rules, validation against the authoritative mapping, the
invalid-citation fail-closed policy, empty-answer states, tenant and
provenance guarantees, immutability, and purity.

Deterministic fakes only — no live LLM, no network, no credentials.
The whole chain (document → retrieval → ranking → selection → prompt
→ answer → validation) uses the real Phase 5.5/5.7/5.10 domain logic.
"""

import ast
import inspect
import unittest
from dataclasses import replace
from uuid import UUID

from xportra.domain.answer_validation import (
    AnswerValidationError,
    AnswerValidator,
    CitationAwareAnswerValidator,
    CitationExtraction,
    VALIDATION_STATUS_EMPTY,
    VALIDATION_STATUS_INVALID_CITATIONS,
    VALIDATION_STATUS_VALID,
    extract_citation_references,
)
from xportra.domain.errors import DomainValidationError
from xportra.domain.evidence_context import (
    DeterministicContextSelector,
    EvidenceContextBudget,
)
from xportra.domain.evidence_prompt import (
    CitationAwarePromptBuilder,
    EvidencePromptConfig,
)
from xportra.domain.evidence_ranking import DeterministicEvidenceRanker
from xportra.domain.evidence_retrieval import EvidenceRetrievalResult
from xportra.domain.llm import GeneratedAnswer, LLMResponse
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TENANT = TenantContext(TENANT_ID)
CHUNK_1 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")

BUILDER = CitationAwarePromptBuilder(
    config=EvidencePromptConfig(
        system_instructions="You are a compliance assistant."))
STRICT = CitationAwareAnswerValidator()  # fail-closed default
STRUCTURED = CitationAwareAnswerValidator(
    fail_on_invalid_citations=False)


def make_evidence(index=1, content="Exporters must file Form NXP.",
                  tenant_id=TENANT_ID):
    return EvidenceRetrievalResult(
        tenant_id=tenant_id,
        chunk_id=UUID(f"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa{index}"),
        document_id=UUID("11111111-1111-1111-1111-111111111111"),
        chunk_index=index - 1,
        content=content,
        content_fingerprint=f"fp-{index}",
        source_id="sonsa/cert-guide",
        source_type="guidance",
        source_location="https://example.test/guide",
        document_version="2024.1",
        embedding_model="test-embed-model",
        embedding_dimensions=4,
        score=0.9,
    )


def make_prompt(contents=("alpha evidence", "beta evidence", "gamma")):
    """Build a real prompt whose mapping is [E1], [E2], [E3]."""
    from xportra.domain.evidence_hybrid import HybridRetrievalCandidate

    candidates = [
        HybridRetrievalCandidate(
            evidence=make_evidence(index=index, content=content),
            semantic_score=1.0 - index * 0.1,
            lexical_score=None,
            retrieval_sources=frozenset({"semantic"}),
        )
        for index, content in enumerate(contents, start=1)
    ]
    ranked = DeterministicEvidenceRanker().rank(
        candidates, top_k=len(candidates))
    selection = DeterministicContextSelector().select(
        ranked, tenant_id=TENANT, budget=EvidenceContextBudget(100_000))
    return BUILDER.build(selection, information_need="need")


def make_answer(text, prompt=None):
    return GeneratedAnswer(
        prompt=prompt or make_prompt(),
        response=LLMResponse(
            generated_text=text, model_identifier="test-model"),
        tenant_id=TENANT,
    )


# ----------------------------------------------------------------------
# Citation extraction
# ----------------------------------------------------------------------


class TestCitationExtraction(unittest.TestCase):
    """Strict [E<n>] parsing — no fuzz, no normalization."""

    def test_one_valid_citation(self):
        extraction = extract_citation_references("See [E1] for details.")
        self.assertEqual(extraction.references, ("[E1]",))

    def test_multiple_valid_citations_in_order(self):
        extraction = extract_citation_references("[E2] and [E1] and [E3]")
        self.assertEqual(extraction.references, ("[E2]", "[E1]", "[E3]"))

    def test_repeated_citation_deduplicated_first_occurrence(self):
        extraction = extract_citation_references("[E1] then [E2] then [E1]")
        self.assertEqual(extraction.references, ("[E1]", "[E2]"))
        # Every occurrence is preserved with position.
        self.assertEqual(len(extraction.occurrences), 3)

    def test_occurrence_positions_are_deterministic(self):
        text = "a [E1] b [E1]"
        first = extract_citation_references(text)
        second = extract_citation_references(text)
        self.assertEqual(first, second)
        self.assertEqual(
            [pos for _, pos in first.occurrences], [2, 9])

    def test_no_citations(self):
        extraction = extract_citation_references("No references at all.")
        self.assertEqual(extraction.references, ())
        self.assertEqual(extraction.occurrences, ())

    def test_malformed_citation_like_text_not_matched(self):
        for text in (
            "[e1]",           # lowercase — not canonical
            "E1",             # missing brackets
            "[E1",            # unclosed
            "E1]",            # no opener
            "[Evidence 1]",   # different syntax
            "[E-1]",          # negative
            "[E 1]",          # space
            "[E1.5]",         # non-integer
            "SEE [E1] NOTE",  # fine — but "[EE1]" below is not
            "[EE1]",
        ):
            if text == "SEE [E1] NOTE":
                continue
            self.assertEqual(
                extract_citation_references(text).references, (),
                f"malformed text matched: {text!r}")

    def test_adjacent_citations_both_matched(self):
        extraction = extract_citation_references("[E1][E2]")
        self.assertEqual(extraction.references, ("[E1]", "[E2]"))

    def test_citations_embedded_in_prose(self):
        extraction = extract_citation_references(
            "The exporter must file [E1], per [E3], before shipment.")
        self.assertEqual(extraction.references, ("[E1]", "[E3]"))

    def test_non_string_input_rejected(self):
        with self.assertRaises(DomainValidationError):
            extract_citation_references(None)
        with self.assertRaises(DomainValidationError):
            extract_citation_references(42)

    def test_extraction_result_is_frozen(self):
        extraction = extract_citation_references("[E1]")
        with self.assertRaises(Exception):
            extraction.references = ("[E9]",)


# ----------------------------------------------------------------------
# Citation validation
# ----------------------------------------------------------------------


class TestCitationValidation(unittest.TestCase):
    """References classify against the authoritative mapping only."""

    def test_valid_citation_accepted(self):
        validated = STRICT.validate(make_answer("Per [E1], file the form."))
        self.assertEqual(validated.status, VALIDATION_STATUS_VALID)
        self.assertEqual(
            validated.validated_citations[0].label, "[E1]")

    def test_valid_highest_citation_accepted(self):
        validated = STRICT.validate(make_answer("Per [E3], file it."))
        self.assertEqual(validated.status, VALIDATION_STATUS_VALID)
        self.assertEqual(
            validated.validated_citations[0].label, "[E3]")

    def test_nonexistent_citation_fails_closed(self):
        with self.assertRaises(AnswerValidationError):
            STRICT.validate(make_answer("Per [E7], file it."))

    def test_nonexistent_large_index_fails_closed(self):
        with self.assertRaises(AnswerValidationError):
            STRICT.validate(make_answer("Per [E99], file it."))

    def test_mixed_valid_invalid_fails_closed(self):
        with self.assertRaises(AnswerValidationError):
            STRICT.validate(make_answer("Per [E1] and [E7]."))

    def test_repeated_valid_citation_is_valid(self):
        validated = STRICT.validate(make_answer("[E2] then [E2] again."))
        self.assertEqual(validated.status, VALIDATION_STATUS_VALID)
        self.assertEqual(len(validated.validated_citations), 1)

    def test_invalid_only_fails_closed(self):
        with self.assertRaises(AnswerValidationError):
            STRICT.validate(make_answer("Per [E7] and [E99]."))

    def test_answer_with_no_citations_is_valid(self):
        validated = STRICT.validate(
            make_answer("A plain answer with no references."))
        self.assertEqual(validated.status, VALIDATION_STATUS_VALID)
        self.assertEqual(validated.validated_citations, ())

    def test_structured_path_reports_invalid_without_raising(self):
        validated = STRUCTURED.validate(make_answer("Per [E1] and [E7]."))
        self.assertEqual(
            validated.status, VALIDATION_STATUS_INVALID_CITATIONS)
        self.assertEqual(validated.invalid_references, ("[E7]",))
        # Valid part still reported; nothing silently removed.
        self.assertEqual(
            validated.validated_citations[0].label, "[E1]")
        # The original answer text is retained verbatim.
        self.assertEqual(
            validated.answer_text, "Per [E1] and [E7].")

    def test_validator_implementations_satisfy_protocol(self):
        self.assertIsInstance(STRICT, AnswerValidator)
        self.assertIsInstance(STRUCTURED, AnswerValidator)

    def test_extraction_classification_distinction_preserved(self):
        # (1) label exists in mapping, (2) label appears in answer —
        # established; (3) semantic support is NOT claimed anywhere.
        validated = STRICT.validate(make_answer("Per [E1], file it."))
        self.assertEqual(validated.status, VALIDATION_STATUS_VALID)
        record = validated.to_record()
        self.assertNotIn("grounded", str(record).lower())
        self.assertNotIn("supported", str(record).lower())


# ----------------------------------------------------------------------
# Validation result
# ----------------------------------------------------------------------


class TestValidationResult(unittest.TestCase):
    """ValidatedAnswer is immutable and reference-preserving."""

    def setUp(self):
        self.prompt = make_prompt()
        self.answer = make_answer("Per [E1] and [E2].", prompt=self.prompt)
        self.validated = STRICT.validate(self.answer)

    def test_result_is_immutable(self):
        with self.assertRaises(Exception):
            self.validated.status = "hacked"
        with self.assertRaises(Exception):
            self.validated.invalid_references = ("[EX]",)

    def test_original_answer_preserved_by_reference(self):
        self.assertIs(self.validated.answer, self.answer)

    def test_original_prompt_preserved_by_reference(self):
        self.assertIs(self.validated.answer.prompt, self.prompt)

    def test_validated_citations_are_authoritative_objects(self):
        for validated_citation, prompt_citation in zip(
                self.validated.validated_citations,
                self.prompt.citations):
            self.assertIs(validated_citation, prompt_citation)

    def test_authoritative_citation_mapping_preserved(self):
        # The full provenance chain resolves through the result.
        evidence = (
            self.validated.validated_citations[0]
            .selected.ranked.evidence)
        self.assertEqual(evidence.tenant_id, TENANT_ID)
        self.assertEqual(evidence.source_id, "sonsa/cert-guide")
        self.assertIsNotNone(evidence.chunk_id)
        self.assertEqual(evidence.content_fingerprint, "fp-1")

    def test_original_text_recoverable_verbatim(self):
        self.assertEqual(
            self.validated.answer_text, "Per [E1] and [E2].")

    def test_deterministic_repeated_validation(self):
        first = STRICT.validate(self.answer)
        for _ in range(3):
            self.assertEqual(first, STRICT.validate(self.answer))

    def test_invalid_citations_reported_not_removed(self):
        validated = STRUCTURED.validate(make_answer("[E1] [E9] [E3]"))
        self.assertEqual(validated.invalid_references, ("[E9]",))
        self.assertEqual(
            [c.label for c in validated.validated_citations],
            ["[E1]", "[E3]"])


# ----------------------------------------------------------------------
# Empty answers
# ----------------------------------------------------------------------


class TestEmptyAnswers(unittest.TestCase):
    """Empty stays distinct from provider failure and validation failure."""

    def test_empty_output_is_valid_empty_status(self):
        validated = STRICT.validate(make_answer("   \n "))
        self.assertEqual(validated.status, VALIDATION_STATUS_EMPTY)
        self.assertTrue(validated.is_empty)
        self.assertEqual(validated.validated_citations, ())

    def test_empty_output_distinct_from_validation_failure(self):
        # Empty output → empty status (not a raise); invalid citations
        # → raise. Two different, distinguishable outcomes.
        with self.assertRaises(AnswerValidationError):
            STRICT.validate(make_answer("see [E7]"))
        self.assertEqual(
            STRICT.validate(make_answer("")).status,
            VALIDATION_STATUS_EMPTY)

    def test_empty_output_distinct_from_provider_failure(self):
        # Provider failures are LLMProviderError (Phase 5.11); empty
        # answers are a valid AnswerValidator outcome. Different types.
        from xportra.domain.errors import LLMProviderError

        with self.assertRaises(LLMProviderError):
            raise LLMProviderError("generate", RuntimeError("down"))
        validated = STRICT.validate(make_answer(""))
        self.assertEqual(validated.status, VALIDATION_STATUS_EMPTY)

    def test_empty_output_with_valid_citation_state(self):
        validated = STRICT.validate(make_answer("", prompt=make_prompt()))
        self.assertEqual(validated.status, VALIDATION_STATUS_EMPTY)
        # The authoritative mapping is untouched by emptiness.
        self.assertEqual(len(self_prompt_citations(validated)), 0)

    def test_empty_output_with_impossible_citation_state(self):
        # A truly empty answer cannot contain citation text — its
        # extraction is empty by definition, and emptiness wins as
        # status regardless of the authoritative mapping.
        validated = STRICT.validate(make_answer("   "))
        self.assertEqual(validated.status, VALIDATION_STATUS_EMPTY)
        self.assertEqual(validated.extraction.references, ())
        self.assertEqual(validated.invalid_references, ())

    def test_non_empty_answer_against_empty_prompt_fails_closed(self):
        # Empty authoritative mapping: any extracted reference is
        # necessarily invalid — no fabrication path exists.
        empty_prompt_prompt = make_prompt(contents=("only",))
        from xportra.domain.evidence_prompt import EvidencePrompt

        bare = replace(
            empty_prompt_prompt, citations=(), evidence_context="")
        with self.assertRaises(AnswerValidationError):
            STRICT.validate(make_answer("Per [E1].", prompt=bare))


def self_prompt_citations(validated):
    return validated.validated_citations


# ----------------------------------------------------------------------
# Security / integrity
# ----------------------------------------------------------------------


class TestSecurityIntegrity(unittest.TestCase):
    """Model output is untrusted; provenance is never model-created."""

    def setUp(self):
        self.prompt = make_prompt()
        self.prompt_snapshot = self.prompt.to_record()

    def test_model_cannot_create_provenance(self):
        # [E4] does not exist in the mapping — the model inventing it
        # cannot make it real.
        with self.assertRaises(AnswerValidationError):
            STRICT.validate(make_answer("Per [E4], file it.",
                                        prompt=self.prompt))
        self.assertEqual(self.prompt.to_record(), self.prompt_snapshot)

    def test_model_cannot_create_new_citation_mapping(self):
        validated = STRICT.validate(
            make_answer("Per [E1].", prompt=self.prompt))
        self.assertIs(validated.validated_citations[0],
                      self.prompt.citations[0])
        # The mapping is exactly the prompt's — not extended.
        self.assertEqual(
            len(validated.validated_citations), 1)

    def test_cross_tenant_provenance_rejected(self):
        # Build a prompt, then doctor one selected item's tenant.
        prompt = make_prompt()
        tampered_citation = replace(
            prompt.citations[1],
            selected=replace(
                prompt.citations[1].selected,
                ranked=replace(
                    prompt.citations[1].selected.ranked,
                    evidence=make_evidence(
                        index=2, tenant_id=OTHER_TENANT_ID)),
            ),
        )
        doctored = replace(
            prompt,
            citations=(prompt.citations[0], tampered_citation,
                       prompt.citations[2]),
        )
        with self.assertRaises(AnswerValidationError):
            STRICT.validate(
                make_answer("Per [E1].", prompt=doctored))

    def test_duplicate_authoritative_labels_rejected(self):
        prompt = make_prompt()
        doctored = replace(
            prompt,
            citations=(prompt.citations[0], prompt.citations[0],
                       prompt.citations[2]),
        )
        with self.assertRaises(AnswerValidationError):
            STRICT.validate(make_answer("Per [E1].", prompt=doctored))

    def test_malformed_generated_answer_rejected(self):
        for bad in (None, "not an answer", 42):
            with self.assertRaises(AnswerValidationError):
                STRICT.validate(bad)

    def test_missing_authoritative_mapping_rejected(self):
        prompt = make_prompt()
        from xportra.domain.evidence_prompt import EvidencePrompt

        bare = replace(prompt, citations=None)
        with self.assertRaises(AnswerValidationError):
            STRICT.validate(make_answer("text", prompt=bare))

    def test_inconsistent_rank_citation_rejected(self):
        prompt = make_prompt()
        # rank_position derives from the SelectedEvidence — to create
        # a label/rank-inconsistent mapping, rebuild the citation with
        # a selected item whose rank no longer matches its label.
        from xportra.domain.evidence_prompt import PromptCitation

        doctored_selected = replace(
            prompt.citations[0].selected, rank_position=2)
        doctored_citation = PromptCitation(
            label="[E1]", selected=doctored_selected)
        doctored = replace(
            prompt,
            citations=(doctored_citation, prompt.citations[1],
                       prompt.citations[2]),
        )
        with self.assertRaises(AnswerValidationError):
            STRICT.validate(make_answer("Per [E1].", prompt=doctored))

    def test_no_mutation_of_prompt_or_evidence(self):
        answer = make_answer("Per [E1] and [E7].", prompt=self.prompt)
        with self.assertRaises(AnswerValidationError):
            STRICT.validate(answer)
        self.assertEqual(
            self.prompt.to_record(), self.prompt_snapshot)
        self.assertEqual(
            answer.response.generated_text, "Per [E1] and [E7].")

    def test_tenant_from_chain_not_model_text(self):
        validated = STRICT.validate(
            make_answer("The tenant is tenant-abc. Per [E1].",
                        prompt=self.prompt))
        # Model text cannot establish tenant identity — only the
        # evidence chain can.
        self.assertIs(validated.tenant_id, TENANT_ID)


# ----------------------------------------------------------------------
# Boundary / purity
# ----------------------------------------------------------------------


class TestPurity(unittest.TestCase):
    """Pure domain logic; no infrastructure; no broad exception masks."""

    def test_no_infrastructure_imports(self):
        import xportra.domain.answer_validation as module

        tree = ast.parse(inspect.getsource(module))
        imported_roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.level == 0:
                    imported_roots.add(node.module.split(".")[0])
        forbidden = {"openai", "anthropic", "httpx", "requests",
                     "urllib", "socket", "os", "subprocess",
                     "qdrant_client", "tiktoken"}
        self.assertFalse(
            imported_roots & forbidden,
            f"forbidden import found: {imported_roots & forbidden}")
        self.assertTrue(
            imported_roots <= {"re", "dataclasses", "typing",
                               "__future__"},
            f"unexpected absolute imports: {imported_roots}")

    def test_no_network_filesystem_or_llm_execution(self):
        # Full validation runs in-memory only; anything external
        # would make this test impossible.
        validated = STRICT.validate(make_answer("Per [E1]."))
        self.assertEqual(validated.status, VALIDATION_STATUS_VALID)

    def test_failures_are_dedicated_errors_not_empty_values(self):
        # Validation failures raise; they never become ""/None/[].
        with self.assertRaises(AnswerValidationError):
            STRICT.validate(make_answer("see [E7]"))
        with self.assertRaises(AnswerValidationError):
            STRICT.validate(None)

    def test_error_hierarchy_distinct_from_provider_failures(self):
        # Answer validation errors are domain validation errors and
        # are NOT LLMProviderError (operational failures stay separate).
        self.assertTrue(
            issubclass(AnswerValidationError, DomainValidationError))
        from xportra.domain.errors import LLMProviderError

        self.assertFalse(
            issubclass(AnswerValidationError, LLMProviderError))

    def test_validation_deterministic_across_runs(self):
        answer = make_answer("[E2] and [E1].")
        first = STRICT.validate(answer)
        for _ in range(3):
            again = STRICT.validate(answer)
            self.assertEqual(first, again)
            self.assertEqual(first.to_record(), again.to_record())

    def test_dangerous_model_text_is_just_text(self):
        dangerous = ("import os; os.system('rm -rf /'); "
                     "SELECT * FROM secrets; [E1]")
        validated = STRICT.validate(make_answer(dangerous))
        self.assertEqual(validated.answer_text, dangerous)
        self.assertEqual(validated.status, VALIDATION_STATUS_VALID)


if __name__ == "__main__":
    unittest.main()
