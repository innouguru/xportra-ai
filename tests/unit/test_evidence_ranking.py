"""Phase 5.5 — Retrieval Ranking & Reranking tests.

Covers the deterministic evidence ranking boundary: the
``EvidenceRanker`` protocol, ``DeterministicEvidenceRanker`` policy
(provenance tiers, per-path scores, chunk-id tie-breaking),
``RankedEvidenceResult`` provenance preservation, top-k semantics,
fail-closed validation, purity (no mutation, no I/O), and
provider independence.

Fakes only — no live Qdrant, no embeddings, no LLM.
"""

import unittest
from uuid import UUID, uuid4

from xportra.domain.errors import DomainValidationError
from xportra.domain.evidence_hybrid import HybridRetrievalCandidate
from xportra.domain.evidence_ranking import (
    PROVENANCE_BOTH,
    PROVENANCE_LEXICAL_ONLY,
    PROVENANCE_SEMANTIC_ONLY,
    DeterministicEvidenceRanker,
    EvidenceRanker,
    RankedEvidenceResult,
    _provenance_tier,
)
from xportra.domain.evidence_retrieval import EvidenceRetrievalResult
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT = TenantContext(TENANT_ID)

DOC_A = UUID("11111111-1111-1111-1111-111111111111")
DOC_B = UUID("22222222-2222-2222-2222-222222222222")
CHUNK_1 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")
CHUNK_2 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2")
CHUNK_3 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3")
CHUNK_4 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa4")
CHUNK_5 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa5")

SRC_GUIDANCE = "sonsa/cert-guide"
SRC_REGULATION = "nafdac/cocoa-regulation"
MODEL = "test-embed-model"
DIMS = 4

RANKER = DeterministicEvidenceRanker()


def make_result(**overrides) -> EvidenceRetrievalResult:
    base = dict(
        tenant_id=TENANT_ID,
        chunk_id=CHUNK_1,
        document_id=DOC_A,
        chunk_index=0,
        content="Exporters must file Form NXP for cocoa exports.",
        content_fingerprint="fp-1",
        source_id=SRC_GUIDANCE,
        source_type="guidance",
        source_location="https://example.test/guide",
        document_version="v1",
        embedding_model=MODEL,
        embedding_dimensions=DIMS,
        score=0.9,
    )
    base.update(overrides)
    return EvidenceRetrievalResult(**base)


def make_candidate(
    *,
    chunk_id=CHUNK_1,
    semantic_score=0.9,
    lexical_score=None,
    retrieval_sources=frozenset({"semantic"}),
    **overrides,
) -> HybridRetrievalCandidate:
    """Build a candidate whose evidence carries the same per-path scores."""
    evidence = make_result(
        chunk_id=chunk_id,
        score=(semantic_score if semantic_score is not None
               else lexical_score),
        **overrides,
    )
    return HybridRetrievalCandidate(
        evidence=evidence,
        semantic_score=semantic_score,
        lexical_score=lexical_score,
        retrieval_sources=retrieval_sources,
    )


def bypass(candidate: HybridRetrievalCandidate, field: str, value) -> None:
    """Simulate a monkeypatch/subclass bypass of frozen validation."""
    object.__setattr__(candidate, field, value)


class TestProvenanceTiers(unittest.TestCase):
    """The provenance-tier mapping drives the first sort component."""

    def test_both_paths_highest(self):
        cand = make_candidate(
            semantic_score=0.5, lexical_score=2,
            retrieval_sources=frozenset({"semantic", "lexical"}))
        self.assertEqual(_provenance_tier(cand), PROVENANCE_BOTH)

    def test_semantic_only_middle(self):
        cand = make_candidate(retrieval_sources=frozenset({"semantic"}))
        self.assertEqual(_provenance_tier(cand), PROVENANCE_SEMANTIC_ONLY)
        self.assertLess(PROVENANCE_BOTH, PROVENANCE_SEMANTIC_ONLY)

    def test_lexical_only_lowest(self):
        cand = make_candidate(
            semantic_score=None, lexical_score=3,
            retrieval_sources=frozenset({"lexical"}))
        self.assertEqual(_provenance_tier(cand), PROVENANCE_LEXICAL_ONLY)
        self.assertLess(PROVENANCE_SEMANTIC_ONLY, PROVENANCE_LEXICAL_ONLY)

    def test_unsupported_source_is_malformed(self):
        cand = make_candidate()
        bypass(cand, "retrieval_sources", frozenset({"semantic", "bogus"}))
        with self.assertRaises(DomainValidationError):
            _provenance_tier(cand)


class TestRankingPolicyCorrectness(unittest.TestCase):
    """Order: provenance tier, semantic desc, lexical desc, chunk_id asc."""

    def test_empty_candidate_set_returns_empty_list(self):
        self.assertEqual(RANKER.rank([], top_k=5), [])

    def test_single_candidate_is_ranked_first(self):
        cand = make_candidate(chunk_id=CHUNK_1, semantic_score=0.42)
        result = RANKER.rank([cand], top_k=5)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].rank_position, 1)
        self.assertEqual(result[0].evidence.chunk_id, CHUNK_1)

    def test_multiple_candidates_ordered_by_semantic_score(self):
        cands = [
            make_candidate(chunk_id=CHUNK_1, semantic_score=0.6),
            make_candidate(chunk_id=CHUNK_2, semantic_score=0.9),
            make_candidate(chunk_id=CHUNK_3, semantic_score=0.75),
        ]
        result = RANKER.rank(cands, top_k=3)
        self.assertEqual(
            [r.evidence.chunk_id for r in result],
            [CHUNK_2, CHUNK_3, CHUNK_1],
        )
        self.assertEqual([r.rank_position for r in result], [1, 2, 3])

    def test_both_paths_outrank_single_path_regardless_of_score(self):
        both = make_candidate(
            chunk_id=CHUNK_1, semantic_score=0.1, lexical_score=1,
            retrieval_sources=frozenset({"semantic", "lexical"}))
        semantic_only = make_candidate(
            chunk_id=CHUNK_2, semantic_score=0.99)
        result = RANKER.rank([semantic_only, both], top_k=2)
        self.assertEqual(result[0].evidence.chunk_id, CHUNK_1)
        self.assertEqual(result[0].retrieval_sources,
                         frozenset({"semantic", "lexical"}))
        self.assertEqual(result[1].evidence.chunk_id, CHUNK_2)

    def test_semantic_only_outranks_lexical_only(self):
        semantic_only = make_candidate(
            chunk_id=CHUNK_1, semantic_score=0.2)
        lexical_only = make_candidate(
            chunk_id=CHUNK_2, semantic_score=None, lexical_score=999,
            retrieval_sources=frozenset({"lexical"}))
        result = RANKER.rank([lexical_only, semantic_only], top_k=2)
        self.assertEqual(
            [r.evidence.chunk_id for r in result], [CHUNK_1, CHUNK_2])

    def test_lexical_score_orders_within_lexical_tier(self):
        # Lexical-only candidates share a tier: ordered by lexical desc.
        cands = [
            make_candidate(chunk_id=CHUNK_1, semantic_score=None,
                           lexical_score=2,
                           retrieval_sources=frozenset({"lexical"})),
            make_candidate(chunk_id=CHUNK_2, semantic_score=None,
                           lexical_score=10,
                           retrieval_sources=frozenset({"lexical"})),
            make_candidate(chunk_id=CHUNK_3, semantic_score=None,
                           lexical_score=5,
                           retrieval_sources=frozenset({"lexical"})),
        ]
        result = RANKER.rank(cands, top_k=3)
        self.assertEqual(
            [r.evidence.chunk_id for r in result],
            [CHUNK_2, CHUNK_3, CHUNK_1],
        )

    def test_lexical_breaks_semantic_tie_within_tier(self):
        # Both-path tier, equal semantic scores: lexical desc decides.
        cands = [
            make_candidate(chunk_id=CHUNK_1, semantic_score=0.8,
                           lexical_score=1,
                           retrieval_sources=frozenset({"semantic", "lexical"})),
            make_candidate(chunk_id=CHUNK_2, semantic_score=0.8,
                           lexical_score=4,
                           retrieval_sources=frozenset({"semantic", "lexical"})),
        ]
        result = RANKER.rank(cands, top_k=2)
        self.assertEqual(
            [r.evidence.chunk_id for r in result], [CHUNK_2, CHUNK_1])

    def test_chunk_id_breaks_full_tie_ascending(self):
        cands = [
            make_candidate(chunk_id=CHUNK_3, semantic_score=0.5),
            make_candidate(chunk_id=CHUNK_1, semantic_score=0.5),
            make_candidate(chunk_id=CHUNK_2, semantic_score=0.5),
        ]
        result = RANKER.rank(cands, top_k=3)
        self.assertEqual(
            [r.evidence.chunk_id for r in result],
            sorted([CHUNK_1, CHUNK_2, CHUNK_3]),
        )

    def test_chunk_id_breaks_full_tie_for_both_path(self):
        cands = [
            make_candidate(chunk_id=CHUNK_4, semantic_score=0.7,
                           lexical_score=3,
                           retrieval_sources=frozenset({"semantic", "lexical"})),
            make_candidate(chunk_id=CHUNK_2, semantic_score=0.7,
                           lexical_score=3,
                           retrieval_sources=frozenset({"semantic", "lexical"})),
        ]
        result = RANKER.rank(cands, top_k=2)
        self.assertEqual(
            [r.evidence.chunk_id for r in result], [CHUNK_2, CHUNK_4])


class TestProvenancePreservation(unittest.TestCase):
    """Ranking changes order only — every provenance field survives."""

    def test_evidence_object_carried_by_reference_not_copied(self):
        cand = make_candidate(chunk_id=CHUNK_1, semantic_score=0.8)
        result = RANKER.rank([cand], top_k=1)[0]
        self.assertIs(result.evidence, cand.evidence)

    def test_full_evidence_provenance_preserved(self):
        cand = make_candidate(
            chunk_id=CHUNK_2,
            document_id=DOC_B,
            source_id=SRC_REGULATION,
            source_type="regulation",
            document_version="v3",
            content_fingerprint="fp-9",
        )
        result = RANKER.rank([cand], top_k=1)[0]
        evidence = result.evidence
        self.assertEqual(evidence.tenant_id, TENANT_ID)
        self.assertEqual(evidence.chunk_id, CHUNK_2)
        self.assertEqual(evidence.document_id, DOC_B)
        self.assertEqual(evidence.document_version, "v3")
        self.assertEqual(evidence.source_id, SRC_REGULATION)
        self.assertEqual(evidence.source_type, "regulation")
        self.assertEqual(evidence.content_fingerprint, "fp-9")
        self.assertEqual(evidence.embedding_model, MODEL)
        self.assertEqual(evidence.embedding_dimensions, DIMS)

    def test_semantic_only_candidate_preserves_scores(self):
        cand = make_candidate(chunk_id=CHUNK_1, semantic_score=0.72,
                              lexical_score=None)
        result = RANKER.rank([cand], top_k=1)[0]
        self.assertEqual(result.semantic_score, 0.72)
        self.assertIsNone(result.lexical_score)

    def test_lexical_only_candidate_preserves_scores(self):
        cand = make_candidate(chunk_id=CHUNK_2, semantic_score=None,
                              lexical_score=4,
                              retrieval_sources=frozenset({"lexical"}))
        result = RANKER.rank([cand], top_k=1)[0]
        self.assertIsNone(result.semantic_score)
        self.assertEqual(result.lexical_score, 4)

    def test_both_path_candidate_preserves_both_scores(self):
        cand = make_candidate(chunk_id=CHUNK_3, semantic_score=0.66,
                              lexical_score=7,
                              retrieval_sources=frozenset({"semantic", "lexical"}))
        result = RANKER.rank([cand], top_k=1)[0]
        self.assertEqual(result.semantic_score, 0.66)
        self.assertEqual(result.lexical_score, 7)
        self.assertEqual(result.retrieval_sources,
                         frozenset({"semantic", "lexical"}))

    def test_retrieval_sources_preserved_for_all_provenances(self):
        cands = [
            make_candidate(chunk_id=CHUNK_1,
                           retrieval_sources=frozenset({"semantic"})),
            make_candidate(chunk_id=CHUNK_2, semantic_score=None,
                           lexical_score=2,
                           retrieval_sources=frozenset({"lexical"})),
            make_candidate(chunk_id=CHUNK_3, lexical_score=2,
                           retrieval_sources=frozenset({"semantic", "lexical"})),
        ]
        result = RANKER.rank(cands, top_k=3)
        self.assertEqual(
            [r.retrieval_sources for r in result],
            [frozenset({"semantic", "lexical"}),
             frozenset({"semantic"}),
             frozenset({"lexical"})],
        )


class TestExplainability(unittest.TestCase):
    """Structured ranking provenance, not natural-language explanation."""

    def test_rank_position_is_explicit_and_one_based(self):
        cands = [
            make_candidate(chunk_id=CHUNK_1, semantic_score=0.4),
            make_candidate(chunk_id=CHUNK_2, semantic_score=0.8),
        ]
        result = RANKER.rank(cands, top_k=2)
        self.assertEqual([r.rank_position for r in result], [1, 2])

    def test_ranking_key_reflects_policy_inputs(self):
        cand = make_candidate(
            chunk_id=CHUNK_1, semantic_score=0.8, lexical_score=3,
            retrieval_sources=frozenset({"semantic", "lexical"}))
        result = RANKER.rank([cand], top_k=1)[0]
        tier, neg_semantic, neg_lexical, chunk_id = result.ranking_key
        self.assertEqual(tier, PROVENANCE_BOTH)
        self.assertEqual(neg_semantic, -0.8)
        self.assertEqual(neg_lexical, -3)
        self.assertEqual(chunk_id, CHUNK_1)

    def test_ranking_key_determines_order(self):
        cands = [
            make_candidate(chunk_id=CHUNK_2, semantic_score=0.9),
            make_candidate(chunk_id=CHUNK_1, semantic_score=0.5),
        ]
        result = RANKER.rank(cands, top_k=2)
        self.assertLess(result[0].ranking_key, result[1].ranking_key)

    def test_to_record_preserves_ranking_provenance(self):
        cand = make_candidate(
            chunk_id=CHUNK_2, semantic_score=None, lexical_score=5,
            retrieval_sources=frozenset({"lexical"}))
        result = RANKER.rank([cand], top_k=1)[0]
        record = result.to_record()
        self.assertEqual(record["rank_position"], 1)
        self.assertIsNone(record["semantic_score"])
        self.assertEqual(record["lexical_score"], 5)
        self.assertEqual(record["retrieval_sources"], ["lexical"])
        self.assertEqual(record["evidence"]["chunk_id"], CHUNK_2)
        self.assertEqual(record["ranking_key"], list(result.ranking_key))


class TestDeterminism(unittest.TestCase):
    """Same candidate set — any input order — always ranks identically."""

    def _candidates(self):
        return [
            make_candidate(chunk_id=CHUNK_1, semantic_score=0.6),
            make_candidate(chunk_id=CHUNK_2, semantic_score=None,
                           lexical_score=8,
                           retrieval_sources=frozenset({"lexical"})),
            make_candidate(chunk_id=CHUNK_3, semantic_score=0.9,
                           lexical_score=2,
                           retrieval_sources=frozenset({"semantic", "lexical"})),
            make_candidate(chunk_id=CHUNK_4, semantic_score=0.9),
        ]

    def test_repeated_ranking_produces_identical_order(self):
        first = RANKER.rank(self._candidates(), top_k=4)
        for _ in range(3):
            again = RANKER.rank(self._candidates(), top_k=4)
            self.assertEqual(
                [r.evidence.chunk_id for r in first],
                [r.evidence.chunk_id for r in again],
            )

    def test_input_order_does_not_affect_output_order(self):
        cands = self._candidates()
        forward = RANKER.rank(cands, top_k=4)
        backward = RANKER.rank(list(reversed(cands)), top_k=4)
        self.assertEqual(
            [r.evidence.chunk_id for r in forward],
            [r.evidence.chunk_id for r in backward],
        )
        # Expected deterministic order: both-path (CHUNK_3, semantic .9)
        # > semantic-only .9 (CHUNK_4) > semantic-only .6 (CHUNK_1)
        # > lexical-only (CHUNK_2).
        self.assertEqual(
            [r.evidence.chunk_id for r in forward],
            [CHUNK_3, CHUNK_4, CHUNK_1, CHUNK_2],
        )

    def test_ranking_key_is_derived_from_fields_not_mutation_order(self):
        cands = self._candidates()
        forward = RANKER.rank(cands, top_k=4)
        backward = RANKER.rank(list(reversed(cands)), top_k=4)
        self.assertEqual(
            {r.evidence.chunk_id: r.ranking_key for r in forward},
            {r.evidence.chunk_id: r.ranking_key for r in backward},
        )


class TestTopKSemantics(unittest.TestCase):
    """``top_k`` truncates the FINAL ranked result, not the candidate pool."""

    def _pool(self):
        return [
            make_candidate(chunk_id=CHUNK_1, semantic_score=0.6),
            make_candidate(chunk_id=CHUNK_2, semantic_score=0.9),
            make_candidate(chunk_id=CHUNK_3, semantic_score=0.75),
        ]

    def test_top_k_truncates_ranked_results(self):
        result = RANKER.rank(self._pool(), top_k=2)
        self.assertEqual(len(result), 2)
        self.assertEqual([r.rank_position for r in result], [1, 2])
        self.assertEqual(
            [r.evidence.chunk_id for r in result], [CHUNK_2, CHUNK_3])

    def test_top_k_one_returns_only_best(self):
        result = RANKER.rank(self._pool(), top_k=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].evidence.chunk_id, CHUNK_2)

    def test_top_k_larger_than_pool_returns_all(self):
        result = RANKER.rank(self._pool(), top_k=50)
        self.assertEqual(len(result), 3)
        self.assertEqual([r.rank_position for r in result], [1, 2, 3])

    def test_invalid_top_k_zero(self):
        with self.assertRaises(DomainValidationError):
            RANKER.rank(self._pool(), top_k=0)

    def test_invalid_top_k_negative(self):
        with self.assertRaises(DomainValidationError):
            RANKER.rank(self._pool(), top_k=-3)

    def test_invalid_top_k_bool(self):
        with self.assertRaises(DomainValidationError):
            RANKER.rank(self._pool(), top_k=True)

    def test_invalid_top_k_float(self):
        with self.assertRaises(DomainValidationError):
            RANKER.rank(self._pool(), top_k=2.0)

    def test_invalid_top_k_string(self):
        with self.assertRaises(DomainValidationError):
            RANKER.rank(self._pool(), top_k="5")

    def test_invalid_top_k_none(self):
        with self.assertRaises(DomainValidationError):
            RANKER.rank(self._pool(), top_k=None)


class TestInvalidInputHandling(unittest.TestCase):
    """Malformed candidates fail closed — never silently normalized."""

    def test_non_candidate_object_rejected(self):
        with self.assertRaises(DomainValidationError):
            RANKER.rank(["not a candidate"], top_k=1)

    def test_none_element_rejected(self):
        with self.assertRaises(DomainValidationError):
            RANKER.rank([None], top_k=1)

    def test_malformed_candidate_list_rejected(self):
        with self.assertRaises(DomainValidationError):
            RANKER.rank("not a list", top_k=1)

    def test_tuple_of_candidates_accepted(self):
        cands = tuple([
            make_candidate(chunk_id=CHUNK_1, semantic_score=0.5),
            make_candidate(chunk_id=CHUNK_2, semantic_score=0.7),
        ])
        result = RANKER.rank(cands, top_k=2)
        self.assertEqual(len(result), 2)

    def test_non_finite_semantic_score_rejected(self):
        cand = make_candidate(chunk_id=CHUNK_1, semantic_score=0.5)
        bypass(cand, "semantic_score", float("nan"))
        with self.assertRaises(DomainValidationError):
            RANKER.rank([cand], top_k=1)

    def test_infinite_lexical_score_rejected(self):
        cand = make_candidate(chunk_id=CHUNK_1, semantic_score=None,
                              lexical_score=1.0,
                              retrieval_sources=frozenset({"lexical"}))
        bypass(cand, "lexical_score", float("inf"))
        with self.assertRaises(DomainValidationError):
            RANKER.rank([cand], top_k=1)

    def test_boolean_score_rejected(self):
        cand = make_candidate(chunk_id=CHUNK_1, semantic_score=0.5)
        bypass(cand, "semantic_score", True)
        with self.assertRaises(DomainValidationError):
            RANKER.rank([cand], top_k=1)

    def test_string_score_rejected(self):
        cand = make_candidate(chunk_id=CHUNK_1, semantic_score=0.5)
        bypass(cand, "semantic_score", "0.9")
        with self.assertRaises(DomainValidationError):
            RANKER.rank([cand], top_k=1)

    def test_candidate_without_any_score_rejected(self):
        # Phase 5.4 construction forbids this; simulate a validation
        # bypass to prove the ranker independently enforces the invariant.
        cand = make_candidate(chunk_id=CHUNK_1, semantic_score=0.5)
        bypass(cand, "semantic_score", None)
        bypass(cand, "retrieval_sources", frozenset())
        with self.assertRaises(DomainValidationError):
            RANKER.rank([cand], top_k=1)

    def test_inconsistent_semantic_provenance_rejected(self):
        cand = make_candidate(chunk_id=CHUNK_1, semantic_score=0.5,
                              lexical_score=2,
                              retrieval_sources=frozenset({"semantic", "lexical"}))
        bypass(cand, "semantic_score", None)
        with self.assertRaises(DomainValidationError):
            RANKER.rank([cand], top_k=1)

    def test_inconsistent_lexical_provenance_rejected(self):
        cand = make_candidate(chunk_id=CHUNK_1, semantic_score=0.5,
                              lexical_score=None)
        bypass(cand, "lexical_score", 3)
        with self.assertRaises(DomainValidationError):
            RANKER.rank([cand], top_k=1)

    def test_non_frozenset_sources_rejected(self):
        cand = make_candidate(chunk_id=CHUNK_1)
        bypass(cand, "retrieval_sources", {"semantic"})
        with self.assertRaises(DomainValidationError):
            RANKER.rank([cand], top_k=1)

    def test_duplicate_chunk_identity_rejected(self):
        # Phase 5.4's union never emits duplicate chunk_ids; a duplicate
        # identity in the ranker input is an integrity violation.
        cands = [
            make_candidate(chunk_id=CHUNK_1, semantic_score=0.9),
            make_candidate(chunk_id=CHUNK_1, semantic_score=0.4,
                           content_fingerprint="fp-other"),
        ]
        with self.assertRaises(DomainValidationError):
            RANKER.rank(cands, top_k=2)


class TestPurity(unittest.TestCase):
    """Ranking is a pure domain operation."""

    def test_input_candidate_list_order_not_mutated(self):
        cands = [
            make_candidate(chunk_id=CHUNK_2, semantic_score=0.9),
            make_candidate(chunk_id=CHUNK_1, semantic_score=0.5),
        ]
        before = [c.evidence.chunk_id for c in cands]
        RANKER.rank(cands, top_k=2)
        self.assertEqual([c.evidence.chunk_id for c in cands], before)

    def test_candidate_fields_not_mutated(self):
        cands = [
            make_candidate(chunk_id=CHUNK_1, semantic_score=0.5),
            make_candidate(chunk_id=CHUNK_2, semantic_score=None,
                           lexical_score=3,
                           retrieval_sources=frozenset({"lexical"})),
        ]
        snapshots = [
            (c.semantic_score, c.lexical_score,
             frozenset(c.retrieval_sources), c.evidence)
            for c in cands
        ]
        RANKER.rank(cands, top_k=2)
        for cand, (semantic, lexical, sources, evidence) in zip(
                cands, snapshots):
            self.assertEqual(cand.semantic_score, semantic)
            self.assertEqual(cand.lexical_score, lexical)
            self.assertEqual(cand.retrieval_sources, sources)
            self.assertIs(cand.evidence, evidence)

    def test_scores_and_provenance_identical_on_candidates_and_results(self):
        cands = self._ranked_pair()
        for cand, result in cands:
            self.assertEqual(result.semantic_score, cand.semantic_score)
            self.assertEqual(result.lexical_score, cand.lexical_score)
            self.assertEqual(result.retrieval_sources,
                             cand.retrieval_sources)
            self.assertEqual(result.evidence.to_record(),
                             cand.evidence.to_record())

    def _ranked_pair(self):
        cands = [
            make_candidate(chunk_id=CHUNK_1, semantic_score=0.5,
                           lexical_score=2,
                           retrieval_sources=frozenset({"semantic", "lexical"})),
            make_candidate(chunk_id=CHUNK_2, semantic_score=0.7),
        ]
        results = RANKER.rank(cands, top_k=2)
        by_chunk = {c.evidence.chunk_id: c for c in cands}
        return [(by_chunk[r.evidence.chunk_id], r) for r in results]

    def test_no_provider_or_network_imports_in_ranking_module(self):
        """The ranking module imports only stdlib and domain code."""
        import ast
        import inspect
        import pathlib
        import xportra.domain.evidence_ranking as module

        source = inspect.getsource(module)
        tree = ast.parse(source)
        imported_roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                # level > 0 marks a relative (intra-domain) import —
                # only absolute imports can reach a provider SDK.
                if node.level == 0:
                    imported_roots.add(node.module.split(".")[0])
        forbidden = {"qdrant_client", "httpx", "requests", "urllib",
                     "socket", "openai", "anthropic"}
        self.assertFalse(
            imported_roots & forbidden,
            f"provider/network import found: {imported_roots & forbidden}")
        self.assertTrue(
            imported_roots <= {"math", "dataclasses", "typing", "uuid",
                               "__future__"},
            f"unexpected absolute imports: {imported_roots}")

    def test_module_namespaces_stay_in_domain_and_stdlib(self):
        import xportra.domain.evidence_ranking as module

        allowed_modules = {"builtins", "dataclasses", "typing", "uuid",
                           "math", "__future__"}
        for name, value in vars(module).items():
            if name.startswith("__"):
                continue
            origin = getattr(value, "__module__", None)
            if origin is None:
                continue  # plain value (int, frozenset, …) — no import origin
            if origin == "xportra.domain.evidence_ranking":
                continue
            self.assertTrue(
                origin.startswith("xportra.domain")
                or origin in allowed_modules,
                f"unexpected import origin for {name}: {origin}",
            )


class TestEvidenceRankerProtocol(unittest.TestCase):
    """The protocol is the replaceable provider-independent boundary."""

    def test_concrete_ranker_satisfies_protocol(self):
        self.assertIsInstance(RANKER, EvidenceRanker)

    def test_protocol_is_runtime_checkable(self):
        self.assertTrue(hasattr(EvidenceRanker, "__protocol_attrs__")
                        or hasattr(EvidenceRanker, "_is_protocol"))

    def test_rank_requires_top_k_keyword(self):
        cands = [make_candidate(chunk_id=CHUNK_1, semantic_score=0.5)]
        with self.assertRaises(TypeError):
            RANKER.rank(cands)  # type: ignore[call-arg]


if __name__ == "__main__":
    unittest.main()
