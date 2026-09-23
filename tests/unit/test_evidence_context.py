"""Phase 5.7 — Budget-Aware Context Selection tests.

Covers the deterministic context-selection boundary:
``EvidenceContextBudget``, ``SelectedEvidence``,
``EvidenceContextSelection``, ``ContextSelector`` protocol, and
``DeterministicContextSelector`` — budget validation, greedy
in-rank-order selection, oversized-item policy, ordering/provenance
guarantees, fail-closed integrity, purity, and exact accounting.

Fakes only — no live Qdrant, no embeddings, no LLM, no tokenizer.
"""

import unittest
from uuid import UUID

from xportra.domain.evidence_context import (
    DeterministicContextSelector,
    EvidenceContextBudget,
    EvidenceContextSelection,
    SelectedEvidence,
)
from xportra.domain.errors import DomainValidationError
from xportra.domain.evidence_ranking import DeterministicEvidenceRanker
from xportra.domain.evidence_retrieval import EvidenceRetrievalResult
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT = TenantContext(TENANT_ID)
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

DOC_A = UUID("11111111-1111-1111-1111-111111111111")
CHUNK_1 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")
CHUNK_2 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2")
CHUNK_3 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3")
CHUNK_4 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa4")

MODEL = "test-embed-model"
DIMS = 4

SELECTOR = DeterministicContextSelector()


def make_result(**overrides) -> EvidenceRetrievalResult:
    base = dict(
        tenant_id=TENANT_ID,
        chunk_id=CHUNK_1,
        document_id=DOC_A,
        chunk_index=0,
        content="Exporters must file Form NXP.",
        content_fingerprint="fp-1",
        source_id="sonsa/cert-guide",
        source_type="guidance",
        source_location="https://example.test/guide",
        document_version="v1",
        embedding_model=MODEL,
        embedding_dimensions=DIMS,
        score=0.9,
    )
    base.update(overrides)
    return EvidenceRetrievalResult(**base)


def make_ranked(
    contents,
    *,
    tenant_id=TENANT_ID,
    **overrides,
):
    """Build a realistic ranked list via the Phase 5.5 ranker.

    Content fingerprints are unique per item (sha256-style distinctness
    is not required — the Phase 5.2 duplicate rule keys on
    document+fingerprint, so distinct fingerprints prevent silent
    collapse).
    """
    candidates = []
    from xportra.domain.evidence_hybrid import HybridRetrievalCandidate

    for index, content in enumerate(contents, start=1):
        evidence = make_result(
            chunk_id=UUID(f"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa{index}"),
            content=content,
            content_fingerprint=f"fp-{index}",
            score=1.0 - index * 0.1,
            tenant_id=tenant_id,
            **overrides,
        )
        candidates.append(
            HybridRetrievalCandidate(
                evidence=evidence,
                semantic_score=evidence.score,
                lexical_score=None,
                retrieval_sources=frozenset({"semantic"}),
            )
        )
    return DeterministicEvidenceRanker().rank(candidates, top_k=len(candidates))


class TestBudgetValidation(unittest.TestCase):
    """EvidenceContextBudget is strict: positive int or nothing."""

    def test_positive_budget_accepted(self):
        budget = EvidenceContextBudget(max_characters=500)
        self.assertEqual(budget.max_characters, 500)

    def test_zero_rejected(self):
        with self.assertRaises(DomainValidationError):
            EvidenceContextBudget(max_characters=0)

    def test_negative_rejected(self):
        with self.assertRaises(DomainValidationError):
            EvidenceContextBudget(max_characters=-10)

    def test_boolean_rejected(self):
        with self.assertRaises(DomainValidationError):
            EvidenceContextBudget(max_characters=True)

    def test_float_rejected(self):
        with self.assertRaises(DomainValidationError):
            EvidenceContextBudget(max_characters=100.0)

    def test_string_rejected(self):
        with self.assertRaises(DomainValidationError):
            EvidenceContextBudget(max_characters="500")

    def test_none_rejected(self):
        with self.assertRaises(DomainValidationError):
            EvidenceContextBudget(max_characters=None)


class TestSelection(unittest.TestCase):
    """Greedy in-rank-order selection with skip-and-continue."""

    def test_empty_input_returns_empty_selection(self):
        selection = SELECTOR.select([], tenant_id=TENANT,
                                    budget=EvidenceContextBudget(100))
        self.assertIsInstance(selection, EvidenceContextSelection)
        self.assertEqual(selection.selected_items, ())
        self.assertEqual(selection.used_budget, 0)
        self.assertEqual(selection.remaining_budget, 100)
        self.assertEqual(selection.skipped_rank_positions, ())

    def test_single_item_within_budget(self):
        ranked = make_ranked(["short content"])
        selection = SELECTOR.select(ranked, tenant_id=TENANT,
                                    budget=EvidenceContextBudget(500))
        self.assertEqual(len(selection.selected_items), 1)
        self.assertEqual(selection.used_budget, len("short content"))

    def test_multiple_items_within_budget(self):
        ranked = make_ranked(["alpha", "beta", "gamma"])
        selection = SELECTOR.select(ranked, tenant_id=TENANT,
                                    budget=EvidenceContextBudget(500))
        self.assertEqual(len(selection.selected_items), 3)
        self.assertEqual(
            selection.used_budget,
            len("alpha") + len("beta") + len("gamma"))

    def test_exact_budget_boundary_included(self):
        ranked = make_ranked(["abcde"])  # 5 chars
        selection = SELECTOR.select(ranked, tenant_id=TENANT,
                                    budget=EvidenceContextBudget(5))
        self.assertEqual(len(selection.selected_items), 1)
        self.assertEqual(selection.used_budget, 5)
        self.assertEqual(selection.remaining_budget, 0)

    def test_item_exceeding_remaining_budget_is_skipped(self):
        ranked = make_ranked(["aaaaaaaaaa", "bb"])  # 10, 2 chars
        selection = SELECTOR.select(ranked, tenant_id=TENANT,
                                    budget=EvidenceContextBudget(10))
        # rank 1 fills the budget (10); rank 2 exceeds remaining → skipped
        self.assertEqual(len(selection.selected_items), 1)
        self.assertEqual(selection.used_budget, 10)
        self.assertEqual(selection.skipped_rank_positions, (2,))

    def test_first_item_exceeding_total_budget_fails_closed(self):
        ranked = make_ranked(["x" * 50])
        with self.assertRaises(DomainValidationError):
            SELECTOR.select(ranked, tenant_id=TENANT,
                            budget=EvidenceContextBudget(10))

    def test_later_item_exceeding_total_budget_fails_closed(self):
        ranked = make_ranked(["small", "x" * 50])
        with self.assertRaises(DomainValidationError):
            SELECTOR.select(ranked, tenant_id=TENANT,
                            budget=EvidenceContextBudget(20))

    def test_deterministic_continuation_after_skip(self):
        # 6, 10, 3 chars with budget 13: rank 1 in (6), rank 2 skipped
        # (10 > 7 remaining), rank 3 in (3). Rank gap at 2.
        ranked = make_ranked(["aaaaaa", "b" * 10, "ccc"])
        selection = SELECTOR.select(ranked, tenant_id=TENANT,
                                    budget=EvidenceContextBudget(13))
        self.assertEqual(
            [i.rank_position for i in selection.selected_items], [1, 3])
        self.assertEqual(selection.used_budget, 9)
        self.assertEqual(selection.skipped_rank_positions, (2,))

    def test_no_budget_violation_ever(self):
        contents = ["a" * 7, "b" * 5, "c" * 4, "d" * 9, "e" * 2]
        ranked = make_ranked(contents)
        budget = EvidenceContextBudget(12)
        selection = SELECTOR.select(ranked, tenant_id=TENANT, budget=budget)
        self.assertLessEqual(selection.used_budget, 12)
        self.assertEqual(
            selection.used_budget,
            sum(i.character_count for i in selection.selected_items))

    def test_first_fits_second_skipped_leaves_gap(self):
        # Budget 10, items 6+6: greedy takes rank 1 (6), rank 2 exceeds
        # the remaining 4 → skipped. Valid, deterministic, no violation.
        ranked = make_ranked(["a" * 6, "b" * 6])
        selection = SELECTOR.select(ranked, tenant_id=TENANT,
                                    budget=EvidenceContextBudget(10))
        self.assertEqual(len(selection.selected_items), 1)
        self.assertEqual(selection.used_budget, 6)
        self.assertEqual(selection.remaining_budget, 4)
        self.assertEqual(selection.skipped_rank_positions, (2,))

    def test_single_item_larger_than_total_budget_fails_closed(self):
        # The oversized-item policy: > total budget is corruption, not a
        # skip — fail closed (documented; chunking bounds content at
        # 1200 chars so production cannot hit this path).
        ranked = make_ranked(["a" * 12])
        with self.assertRaises(DomainValidationError):
            SELECTOR.select(ranked, tenant_id=TENANT,
                            budget=EvidenceContextBudget(10))


class TestOrdering(unittest.TestCase):
    """Selected results keep rank order; gaps are explicit and valid."""

    def test_rank_order_preserved_with_gaps(self):
        ranked = make_ranked(["aaaaaa", "b" * 10, "ccc"])  # 6, 10, 3
        selection = SELECTOR.select(ranked, tenant_id=TENANT,
                                    budget=EvidenceContextBudget(13))
        self.assertEqual(
            [i.rank_position for i in selection.selected_items], [1, 3])

    def test_no_reordering_of_selected_items(self):
        ranked = make_ranked(["one", "two", "three", "four"])
        selection = SELECTOR.select(ranked, tenant_id=TENANT,
                                    budget=EvidenceContextBudget(100))
        positions = [i.rank_position for i in selection.selected_items]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(positions, [1, 2, 3, 4])

    def test_selector_does_not_rescore_or_reorder(self):
        # Reversed-content fixture: selection order must equal input
        # (rank) order regardless of content length.
        ranked = make_ranked(["tiny", "longer-content", "mid"])
        selection = SELECTOR.select(ranked, tenant_id=TENANT,
                                    budget=EvidenceContextBudget(100))
        self.assertEqual(
            [i.rank_position for i in selection.selected_items], [1, 2, 3])


class TestProvenance(unittest.TestCase):
    """Selection wraps by reference — everything survives unchanged."""

    def _select(self, contents, budget=1000):
        ranked = make_ranked(contents)
        selection = SELECTOR.select(
            ranked, tenant_id=TENANT,
            budget=budget if isinstance(budget, EvidenceContextBudget)
            else EvidenceContextBudget(budget))
        return ranked, selection

    def test_ranked_result_carried_by_reference(self):
        ranked, selection = self._select(["alpha"])
        self.assertIs(selection.selected_items[0].ranked, ranked[0])

    def test_tenant_preserved(self):
        ranked, selection = self._select(["alpha"])
        self.assertEqual(
            selection.selected_items[0].ranked.evidence.tenant_id, TENANT_ID)

    def test_document_and_version_preserved(self):
        ranked, selection = self._select(
            ["alpha"], budget=1000)  # all same doc/version by default
        evidence = selection.selected_items[0].ranked.evidence
        self.assertEqual(evidence.document_id, DOC_A)
        self.assertEqual(evidence.document_version, "v1")
        self.assertEqual(evidence.chunk_index, 0)

    def test_source_provenance_preserved(self):
        ranked, selection = self._select(["alpha"])
        evidence = selection.selected_items[0].ranked.evidence
        self.assertEqual(evidence.source_id, "sonsa/cert-guide")
        self.assertEqual(evidence.source_type, "guidance")
        self.assertEqual(evidence.source_location,
                         "https://example.test/guide")

    def test_content_fingerprint_preserved(self):
        ranked, selection = self._select(["alpha"])
        self.assertEqual(
            selection.selected_items[0].ranked.evidence.content_fingerprint,
            "fp-1")

    def test_original_ranking_information_preserved(self):
        ranked, selection = self._select(["alpha", "beta"])
        first = selection.selected_items[0].ranked
        self.assertEqual(first.rank_position, 1)
        self.assertEqual(first.semantic_score, 0.9)
        self.assertIsNone(first.lexical_score)
        self.assertEqual(first.retrieval_sources, frozenset({"semantic"}))
        self.assertIsNotNone(first.ranking_key)

    def test_to_record_exposes_selection_provenance(self):
        ranked, selection = self._select(["alpha"])
        record = selection.to_record()
        self.assertEqual(record["budget"], 1000)
        self.assertEqual(record["used_budget"], 5)
        self.assertEqual(record["remaining_budget"], 995)
        self.assertEqual(record["skipped_rank_positions"], [])
        self.assertEqual(len(record["selected_items"]), 1)
        item = record["selected_items"][0]
        self.assertEqual(item["rank_position"], 1)
        self.assertEqual(item["character_count"], 5)
        self.assertEqual(item["ranked"]["rank_position"], 1)


class TestIntegrity(unittest.TestCase):
    """Malformed ranked evidence fails closed — never silently repaired."""

    def test_duplicate_chunk_identity_rejected(self):
        ranked = make_ranked(["alpha", "beta"])
        from xportra.domain.evidence_ranking import RankedEvidenceResult

        tampered = RankedEvidenceResult(
            rank_position=2,
            evidence=ranked[1].evidence,
            semantic_score=ranked[1].semantic_score,
            lexical_score=ranked[1].lexical_score,
            retrieval_sources=ranked[1].retrieval_sources,
            ranking_key=ranked[1].ranking_key,
        )
        # Rebuild rank 2 with rank 1's chunk identity (same doc/fingerprint
        # source ids are irrelevant; chunk identity is what matters).
        import dataclasses

        dup_evidence = dataclasses.replace(
            ranked[0].evidence, content="beta",
            content_fingerprint="fp-dup")
        tampered = RankedEvidenceResult(
            rank_position=2,
            evidence=dup_evidence,
            semantic_score=0.5,
            lexical_score=None,
            retrieval_sources=frozenset({"semantic"}),
            ranking_key=(1, -0.5, 0.0, dup_evidence.chunk_id),
        )
        with self.assertRaises(DomainValidationError):
            SELECTOR.select([ranked[0], tampered], tenant_id=TENANT,
                            budget=EvidenceContextBudget(100))

    def test_malformed_rank_position_rejected(self):
        ranked = make_ranked(["alpha"])
        from xportra.domain.evidence_ranking import RankedEvidenceResult

        bad = RankedEvidenceResult(
            rank_position=0,
            evidence=ranked[0].evidence,
            semantic_score=ranked[0].semantic_score,
            lexical_score=ranked[0].lexical_score,
            retrieval_sources=ranked[0].retrieval_sources,
            ranking_key=ranked[0].ranking_key,
        )
        with self.assertRaises(DomainValidationError):
            SELECTOR.select([bad], tenant_id=TENANT,
                            budget=EvidenceContextBudget(100))

    def test_non_ascending_rank_order_rejected(self):
        ranked = make_ranked(["alpha", "beta"])
        with self.assertRaises(DomainValidationError):
            SELECTOR.select([ranked[1], ranked[0]], tenant_id=TENANT,
                            budget=EvidenceContextBudget(100))

    def test_malformed_content_rejected(self):
        ranked = make_ranked(["alpha"])
        # Bypass the frozen EvidenceRetrievalResult validation.
        object.__setattr__(ranked[0].evidence, "content", "")
        with self.assertRaises(DomainValidationError):
            SELECTOR.select(ranked, tenant_id=TENANT,
                            budget=EvidenceContextBudget(100))

    def test_tenant_mismatch_rejected(self):
        ranked = make_ranked(
            ["alpha"], tenant_id=OTHER_TENANT_ID)
        with self.assertRaises(DomainValidationError):
            SELECTOR.select(ranked, tenant_id=TENANT,
                            budget=EvidenceContextBudget(100))

    def test_non_ranked_input_rejected(self):
        with self.assertRaises(DomainValidationError):
            SELECTOR.select(["not a ranked result"], tenant_id=TENANT,
                            budget=EvidenceContextBudget(100))

    def test_malformed_ranked_list_rejected(self):
        with self.assertRaises(DomainValidationError):
            SELECTOR.select("not a list", tenant_id=TENANT,
                            budget=EvidenceContextBudget(100))

    def test_missing_tenant_rejected(self):
        ranked = make_ranked(["alpha"])
        with self.assertRaises(DomainValidationError):
            SELECTOR.select(ranked, tenant_id=None,
                            budget=EvidenceContextBudget(100))

    def test_non_tenant_context_rejected(self):
        ranked = make_ranked(["alpha"])
        with self.assertRaises(DomainValidationError):
            SELECTOR.select(ranked, tenant_id="tenant-abc",
                            budget=EvidenceContextBudget(100))

    def test_invalid_budget_object_rejected(self):
        ranked = make_ranked(["alpha"])
        with self.assertRaises(DomainValidationError):
            SELECTOR.select(ranked, tenant_id=TENANT, budget=None)
        with self.assertRaises(DomainValidationError):
            SELECTOR.select(ranked, tenant_id=TENANT, budget=100)


class TestPurity(unittest.TestCase):
    """Pure domain logic: no infrastructure, no mutation."""

    def test_no_qdrant_http_or_llm_imports(self):
        import ast
        import inspect
        import xportra.domain.evidence_context as module

        tree = ast.parse(inspect.getsource(module))
        imported_roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.level == 0:
                    imported_roots.add(node.module.split(".")[0])
        forbidden = {"qdrant_client", "httpx", "requests", "urllib",
                     "socket", "openai", "anthropic", "tiktoken",
                     "transformers"}
        self.assertFalse(
            imported_roots & forbidden,
            f"forbidden import found: {imported_roots & forbidden}")
        self.assertTrue(
            imported_roots <= {"dataclasses", "typing", "__future__"},
            f"unexpected absolute imports: {imported_roots}")

    def test_input_ranked_results_not_mutated(self):
        ranked = make_ranked(["alpha", "beta", "gamma"])
        snapshot = [(r.rank_position, r.evidence.content,
                     r.semantic_score) for r in ranked]
        SELECTOR.select(ranked, tenant_id=TENANT,
                        budget=EvidenceContextBudget(7))
        self.assertEqual(
            [(r.rank_position, r.evidence.content, r.semantic_score)
             for r in ranked],
            snapshot)
        self.assertEqual(len(ranked), 3)


class TestAccounting(unittest.TestCase):
    """used/remaining are exact and deterministic."""

    def test_used_budget_exact_sum(self):
        ranked = make_ranked(["abc", "de", "fghij"])
        selection = SELECTOR.select(ranked, tenant_id=TENANT,
                                    budget=EvidenceContextBudget(100))
        self.assertEqual(selection.used_budget, 3 + 2 + 5)
        self.assertEqual(selection.remaining_budget, 100 - 10)

    def test_remaining_budget_zero_at_exact_boundary(self):
        ranked = make_ranked(["abcde"])
        selection = SELECTOR.select(ranked, tenant_id=TENANT,
                                    budget=EvidenceContextBudget(5))
        self.assertEqual(selection.remaining_budget, 0)

    def test_accounting_deterministic_across_runs(self):
        ranked = make_ranked(["aaaaaa", "b" * 10, "ccc"])
        first = SELECTOR.select(ranked, tenant_id=TENANT,
                                budget=EvidenceContextBudget(13))
        for _ in range(3):
            again = SELECTOR.select(ranked, tenant_id=TENANT,
                                    budget=EvidenceContextBudget(13))
            self.assertEqual(first, again)

    def test_off_by_one_boundary_excluded(self):
        # Budget 8 with 9-char content: 8 < 9 so it does NOT fit the
        # TOTAL budget → fail-closed path (see oversized-item policy).
        ranked = make_ranked(["abcdefghi"])
        with self.assertRaises(DomainValidationError):
            SELECTOR.select(ranked, tenant_id=TENANT,
                            budget=EvidenceContextBudget(8))

    def test_off_by_one_boundary_included_when_exactly_equal(self):
        # Budget 9 with 9-char content: exactly fits — included.
        ranked = make_ranked(["abcdefghi"])
        selection = SELECTOR.select(ranked, tenant_id=TENANT,
                                    budget=EvidenceContextBudget(9))
        self.assertEqual(len(selection.selected_items), 1)
        self.assertEqual(selection.used_budget, 9)
        self.assertEqual(selection.remaining_budget, 0)


if __name__ == "__main__":
    unittest.main()
