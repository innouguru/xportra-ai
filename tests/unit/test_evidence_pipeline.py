"""Phase 5.6 — Retrieval Pipeline Orchestration tests.

Covers the application-facing orchestration boundary:
``EvidenceRetrievalPipeline`` and
``build_evidence_retrieval_pipeline`` — mode handling, tenant/scope
forwarding, ranker invocation, top-k ownership, failure propagation,
result integrity, determinism, purity, and dependency injection.

Fakes only — no live Qdrant, no embeddings, no LLM.
"""

import unittest
from uuid import UUID

from xportra.domain.evidence_hybrid import HybridRetrievalCandidate
from xportra.domain.evidence_pipeline import (
    EvidenceRetrievalPipeline,
    RetrievalPipeline,
    build_evidence_retrieval_pipeline,
)
from xportra.domain.evidence_ranking import (
    DeterministicEvidenceRanker,
    RankedEvidenceResult,
    _ranking_key,
)
from xportra.domain.evidence_retrieval import (
    DEFAULT_TOP_K,
    EvidenceRetrievalQuery,
    EvidenceRetrievalResult,
    EvidenceRetrievalScope,
)
from xportra.domain.errors import DomainValidationError
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT = TenantContext(TENANT_ID)

DOC_A = UUID("11111111-1111-1111-1111-111111111111")
CHUNK_1 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")
CHUNK_2 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2")
CHUNK_3 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3")

MODEL = "test-embed-model"
DIMS = 4


def make_result(**overrides) -> EvidenceRetrievalResult:
    base = dict(
        tenant_id=TENANT_ID,
        chunk_id=CHUNK_1,
        document_id=DOC_A,
        chunk_index=0,
        content="Exporters must file Form NXP for cocoa exports.",
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


def make_candidate(
    *,
    chunk_id=CHUNK_1,
    semantic_score=0.9,
    lexical_score=None,
    retrieval_sources=frozenset({"semantic"}),
    **overrides,
) -> HybridRetrievalCandidate:
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


class RecordingHybridRetriever:
    """Fake that records its call and returns canned candidates."""

    def __init__(self, candidates=None, error=None):
        self.candidates = candidates if candidates is not None else []
        self.error = error
        self.calls = []

    def retrieve_candidates(self, query, *, tenant_id, mode, scope=None):
        self.calls.append(
            {"query": query, "tenant_id": tenant_id,
             "mode": mode, "scope": scope})
        if self.error is not None:
            raise self.error
        return list(self.candidates)


class RecordingRanker:
    """Fake ranker recording its inputs, returning canned results."""

    def __init__(self, results=None, error=None):
        self.results = results if results is not None else []
        self.error = error
        self.calls = []

    def rank(self, candidates, *, top_k):
        self.calls.append({"candidates": list(candidates), "top_k": top_k})
        if self.error is not None:
            raise self.error
        return list(self.results)


def ranked_for(candidates) -> list[RankedEvidenceResult]:
    """Produce real ranked results via the Phase 5.5 ranker."""
    return DeterministicEvidenceRanker().rank(candidates, top_k=10)


class TestConstruction(unittest.TestCase):
    """Dependency injection: explicit collaborators, fail-closed setup."""

    def test_pipeline_satisfies_retrieval_pipeline_protocol(self):
        pipeline = EvidenceRetrievalPipeline(
            hybrid_retriever=RecordingHybridRetriever(),
            ranker=DeterministicEvidenceRanker())
        self.assertIsInstance(pipeline, RetrievalPipeline)

    def test_missing_hybrid_retriever_rejected(self):
        with self.assertRaises(DomainValidationError):
            EvidenceRetrievalPipeline(
                hybrid_retriever=None, ranker=DeterministicEvidenceRanker())

    def test_string_hybrid_retriever_rejected(self):
        with self.assertRaises(DomainValidationError):
            EvidenceRetrievalPipeline(
                hybrid_retriever="retriever",
                ranker=DeterministicEvidenceRanker())

    def test_missing_rank_method_rejected(self):
        class NotARanker:
            pass

        with self.assertRaises(DomainValidationError):
            EvidenceRetrievalPipeline(
                hybrid_retriever=RecordingHybridRetriever(),
                ranker=NotARanker())

    def test_missing_retrieve_candidates_method_rejected(self):
        class NotARetriever:
            pass

        with self.assertRaises(DomainValidationError):
            EvidenceRetrievalPipeline(
                hybrid_retriever=NotARetriever(),
                ranker=DeterministicEvidenceRanker())


class TestModeHandling(unittest.TestCase):
    """The three Phase 5.4 modes pass through; invalid modes fail closed."""

    def _run(self, retriever, mode):
        pipeline = EvidenceRetrievalPipeline(
            hybrid_retriever=retriever,
            ranker=DeterministicEvidenceRanker())
        return pipeline.retrieve(
            "Form NXP cocoa export", tenant_id=TENANT, mode=mode)

    def test_semantic_mode_forwarded(self):
        retriever = RecordingHybridRetriever()
        self._run(retriever, "semantic")
        self.assertEqual(retriever.calls[0]["mode"], "semantic")

    def test_lexical_mode_forwarded(self):
        retriever = RecordingHybridRetriever()
        self._run(retriever, "lexical")
        self.assertEqual(retriever.calls[0]["mode"], "lexical")

    def test_hybrid_mode_forwarded(self):
        retriever = RecordingHybridRetriever()
        self._run(retriever, "hybrid")
        self.assertEqual(retriever.calls[0]["mode"], "hybrid")

    def test_invalid_mode_fails_closed(self):
        retriever = RecordingHybridRetriever()
        with self.assertRaises(DomainValidationError):
            self._run(retriever, "bm25")
        self.assertEqual(retriever.calls, [])  # never reached retriever

    def test_mode_has_no_silent_default(self):
        retriever = RecordingHybridRetriever()
        pipeline = EvidenceRetrievalPipeline(
            hybrid_retriever=retriever,
            ranker=DeterministicEvidenceRanker())
        with self.assertRaises(TypeError):
            pipeline.retrieve("Form NXP", tenant_id=TENANT)


class TestTenantAndScopeForwarding(unittest.TestCase):
    """Tenant and scope are forwarded unchanged — no second mechanism."""

    def _run(self, retriever, *, tenant, scope):
        pipeline = EvidenceRetrievalPipeline(
            hybrid_retriever=retriever,
            ranker=DeterministicEvidenceRanker())
        return pipeline.retrieve(
            "Form NXP", tenant_id=tenant, mode="hybrid", scope=scope)

    def test_tenant_context_forwarded_unchanged(self):
        retriever = RecordingHybridRetriever()
        self._run(retriever, tenant=TENANT, scope=None)
        self.assertIs(retriever.calls[0]["tenant_id"], TENANT)

    def test_missing_tenant_fails_closed(self):
        retriever = RecordingHybridRetriever()
        pipeline = EvidenceRetrievalPipeline(
            hybrid_retriever=retriever,
            ranker=DeterministicEvidenceRanker())
        with self.assertRaises(DomainValidationError):
            pipeline.retrieve(
                "Form NXP", tenant_id=None, mode="hybrid")
        self.assertEqual(retriever.calls, [])

    def test_non_tenant_context_rejected(self):
        retriever = RecordingHybridRetriever()
        pipeline = EvidenceRetrievalPipeline(
            hybrid_retriever=retriever,
            ranker=DeterministicEvidenceRanker())
        with self.assertRaises(DomainValidationError):
            pipeline.retrieve(
                "Form NXP", tenant_id="tenant-abc", mode="hybrid")
        self.assertEqual(retriever.calls, [])

    def test_none_scope_means_tenant_only_and_forwarded(self):
        retriever = RecordingHybridRetriever()
        self._run(retriever, tenant=TENANT, scope=None)
        self.assertIsNone(retriever.calls[0]["scope"])

    def test_empty_scope_is_tenant_only_and_forwarded(self):
        retriever = RecordingHybridRetriever()
        scope = EvidenceRetrievalScope()
        self._run(retriever, tenant=TENANT, scope=scope)
        forwarded = retriever.calls[0]["scope"]
        self.assertIs(forwarded, scope)
        self.assertTrue(forwarded.is_empty)

    def test_populated_scope_forwarded_unchanged(self):
        retriever = RecordingHybridRetriever()
        scope = EvidenceRetrievalScope(
            source_id="sonsa/cert-guide", document_version="v1")
        self._run(retriever, tenant=TENANT, scope=scope)
        self.assertIs(retriever.calls[0]["scope"], scope)

    def test_malformed_scope_rejected(self):
        retriever = RecordingHybridRetriever()
        pipeline = EvidenceRetrievalPipeline(
            hybrid_retriever=retriever,
            ranker=DeterministicEvidenceRanker())
        with self.assertRaises(DomainValidationError):
            pipeline.retrieve(
                "Form NXP", tenant_id=TENANT, mode="hybrid",
                scope={"source_id": "x"})  # dict must not be reconstructed


class TestRankerInvocationAndTopK(unittest.TestCase):
    """The ranker receives all candidates and owns the final top-k."""

    def _pipeline(self, retriever, ranker):
        return EvidenceRetrievalPipeline(
            hybrid_retriever=retriever, ranker=ranker)

    def test_ranker_receives_full_candidate_pool(self):
        cands = [make_candidate(chunk_id=CHUNK_1),
                 make_candidate(chunk_id=CHUNK_2, semantic_score=0.5),
                 make_candidate(chunk_id=CHUNK_3, semantic_score=0.3)]
        retriever = RecordingHybridRetriever(candidates=cands)
        ranker = RecordingRanker(results=ranked_for(cands))
        self._pipeline(retriever, ranker).retrieve(
            "Form NXP", tenant_id=TENANT, mode="hybrid", top_k=2)
        self.assertEqual(len(ranker.calls[0]["candidates"]), 3)
        self.assertEqual(ranker.calls[0]["top_k"], 2)

    def test_final_top_k_passes_to_ranker_not_retriever_truncation(self):
        # candidate_pool larger than top_k: retriever's query carries the
        # pool; the ranker still truncates to top_k.
        retriever = RecordingHybridRetriever()
        ranker = RecordingRanker()
        self._pipeline(retriever, ranker).retrieve(
            "Form NXP", tenant_id=TENANT, mode="hybrid",
            top_k=3, candidate_pool=10)
        self.assertEqual(retriever.calls[0]["query"].top_k, 10)
        self.assertEqual(ranker.calls[0]["top_k"], 3)

    def test_default_top_k_is_phase_5_1_default(self):
        retriever = RecordingHybridRetriever()
        ranker = RecordingRanker()
        self._pipeline(retriever, ranker).retrieve(
            "Form NXP", tenant_id=TENANT, mode="hybrid")
        self.assertEqual(ranker.calls[0]["top_k"], DEFAULT_TOP_K)
        self.assertEqual(retriever.calls[0]["query"].top_k, DEFAULT_TOP_K)

    def test_default_candidate_pool_equals_top_k(self):
        retriever = RecordingHybridRetriever()
        ranker = RecordingRanker()
        self._pipeline(retriever, ranker).retrieve(
            "Form NXP", tenant_id=TENANT, mode="hybrid", top_k=4)
        self.assertEqual(retriever.calls[0]["query"].top_k, 4)

    def test_candidate_pool_smaller_than_top_k_allowed(self):
        retriever = RecordingHybridRetriever()
        ranker = RecordingRanker()
        self._pipeline(retriever, ranker).retrieve(
            "Form NXP", tenant_id=TENANT, mode="hybrid",
            top_k=5, candidate_pool=2)
        self.assertEqual(retriever.calls[0]["query"].top_k, 2)
        self.assertEqual(ranker.calls[0]["top_k"], 5)

    def test_invalid_top_k_rejected(self):
        retriever = RecordingHybridRetriever()
        ranker = RecordingRanker()
        pipeline = self._pipeline(retriever, ranker)
        for bad in (0, -1, True, 2.5, "3", None):
            with self.assertRaises(Exception):
                pipeline.retrieve(
                    "Form NXP", tenant_id=TENANT, mode="hybrid",
                    top_k=bad)
        self.assertEqual(retriever.calls, [])

    def test_invalid_candidate_pool_rejected(self):
        retriever = RecordingHybridRetriever()
        ranker = RecordingRanker()
        pipeline = self._pipeline(retriever, ranker)
        for bad in (0, -2, True, 1.5, "8"):
            with self.assertRaises(DomainValidationError):
                pipeline.retrieve(
                    "Form NXP", tenant_id=TENANT, mode="hybrid",
                    top_k=1, candidate_pool=bad)
        self.assertEqual(retriever.calls, [])

    def test_ranker_output_returned_verbatim(self):
        cands = [make_candidate(chunk_id=CHUNK_1),
                 make_candidate(chunk_id=CHUNK_2, semantic_score=0.4)]
        real = ranked_for(cands)
        retriever = RecordingHybridRetriever(candidates=cands)
        ranker = RecordingRanker(results=real)
        out = self._pipeline(retriever, ranker).retrieve(
            "Form NXP", tenant_id=TENANT, mode="hybrid")
        self.assertEqual(out, real)
        for a, b in zip(out, real):
            self.assertIs(a, b)  # same objects — no transformation

    def test_malformed_ranker_output_rejected(self):
        retriever = RecordingHybridRetriever(
            candidates=[make_candidate()])
        ranker = RecordingRanker(results=["not a ranked result"])
        with self.assertRaises(DomainValidationError):
            self._pipeline(retriever, ranker).retrieve(
                "Form NXP", tenant_id=TENANT, mode="hybrid")


class TestFailurePropagation(unittest.TestCase):
    """Lower-level failures propagate; [] means genuinely no evidence."""

    def test_retrieval_failure_propagates(self):
        boom = RuntimeError("embedding provider down")
        retriever = RecordingHybridRetriever(error=boom)
        pipeline = EvidenceRetrievalPipeline(
            hybrid_retriever=retriever,
            ranker=DeterministicEvidenceRanker())
        with self.assertRaises(RuntimeError) as ctx:
            pipeline.retrieve(
                "Form NXP", tenant_id=TENANT, mode="hybrid")
        self.assertIs(ctx.exception, boom)

    def test_ranking_failure_propagates(self):
        boom = DomainValidationError("ranker rejected malformed candidate")
        retriever = RecordingHybridRetriever(
            candidates=[make_candidate()])
        ranker = RecordingRanker(error=boom)
        pipeline = EvidenceRetrievalPipeline(
            hybrid_retriever=retriever, ranker=ranker)
        with self.assertRaises(DomainValidationError) as ctx:
            pipeline.retrieve(
                "Form NXP", tenant_id=TENANT, mode="hybrid")
        self.assertIs(ctx.exception, boom)

    def test_empty_candidates_yield_empty_result_no_error(self):
        retriever = RecordingHybridRetriever(candidates=[])
        pipeline = EvidenceRetrievalPipeline(
            hybrid_retriever=retriever,
            ranker=DeterministicEvidenceRanker())
        result = pipeline.retrieve(
            "Form NXP", tenant_id=TENANT, mode="hybrid")
        self.assertEqual(result, [])


class TestDeterminismAndPurity(unittest.TestCase):
    """Repeated runs are identical; dependencies' data is never mutated."""

    def test_deterministic_repeated_execution(self):
        cands = [make_candidate(chunk_id=CHUNK_2, semantic_score=0.5),
                 make_candidate(chunk_id=CHUNK_1, semantic_score=0.9),
                 make_candidate(chunk_id=CHUNK_3, semantic_score=0.7)]
        pipeline = EvidenceRetrievalPipeline(
            hybrid_retriever=RecordingHybridRetriever(candidates=cands),
            ranker=DeterministicEvidenceRanker())
        first = pipeline.retrieve(
            "Form NXP", tenant_id=TENANT, mode="hybrid")
        for _ in range(2):
            again = pipeline.retrieve(
                "Form NXP", tenant_id=TENANT, mode="hybrid")
            self.assertEqual(
                [(r.evidence.chunk_id, r.rank_position) for r in first],
                [(r.evidence.chunk_id, r.rank_position) for r in again])

    def test_dependency_results_not_mutated(self):
        cands = [make_candidate(chunk_id=CHUNK_2, semantic_score=0.5),
                 make_candidate(chunk_id=CHUNK_1, semantic_score=0.9)]
        retriever = RecordingHybridRetriever(candidates=cands)
        pipeline = EvidenceRetrievalPipeline(
            hybrid_retriever=retriever,
            ranker=DeterministicEvidenceRanker())
        pipeline.retrieve("Form NXP", tenant_id=TENANT, mode="hybrid")
        # The retriever's canned list order is untouched.
        self.assertEqual(
            [c.evidence.chunk_id for c in retriever.candidates],
            [CHUNK_2, CHUNK_1])
        # Candidate fields untouched.
        for cand in cands:
            self.assertIsNotNone(cand.semantic_score)
            self.assertEqual(
                cand.retrieval_sources, frozenset({"semantic"}))

    def test_query_text_preserved_by_phase_5_2_semantics(self):
        retriever = RecordingHybridRetriever()
        pipeline = EvidenceRetrievalPipeline(
            hybrid_retriever=retriever,
            ranker=DeterministicEvidenceRanker())
        pipeline.retrieve(
            "  Form   NXP  ", tenant_id=TENANT, mode="hybrid")
        # Normalization belongs to Phase 5.2 (trim + collapse), which the
        # pipeline gets for free by constructing the Phase 5.2 query.
        self.assertEqual(retriever.calls[0]["query"].text, "Form NXP")


class TestResultIntegrity(unittest.TestCase):
    """Ranked results keep rank position, scores, sources, ranking key."""

    def _real_pipeline(self, cands):
        return EvidenceRetrievalPipeline(
            hybrid_retriever=RecordingHybridRetriever(candidates=cands),
            ranker=DeterministicEvidenceRanker())

    def test_full_ranked_provenance_preserved(self):
        cands = [
            make_candidate(chunk_id=CHUNK_1, semantic_score=0.66,
                           lexical_score=7,
                           retrieval_sources=frozenset(
                               {"semantic", "lexical"}),
                           content_fingerprint="fp-a"),
            make_candidate(chunk_id=CHUNK_2, semantic_score=0.9),
        ]
        out = self._real_pipeline(cands).retrieve(
            "Form NXP", tenant_id=TENANT, mode="hybrid", top_k=2)
        self.assertEqual([r.rank_position for r in out], [1, 2])
        top = out[0]  # both-path outranks semantic-only
        self.assertEqual(top.evidence.chunk_id, CHUNK_1)
        self.assertEqual(top.semantic_score, 0.66)
        self.assertEqual(top.lexical_score, 7)
        self.assertEqual(top.retrieval_sources,
                         frozenset({"semantic", "lexical"}))
        self.assertEqual(top.ranking_key, _ranking_key(cands[0]))
        self.assertEqual(top.evidence.content_fingerprint, "fp-a")
        self.assertEqual(top.evidence.tenant_id, TENANT_ID)

    def test_top_k_truncation_preserves_rank_positions(self):
        cands = [make_candidate(chunk_id=CHUNK_1, semantic_score=0.9),
                 make_candidate(chunk_id=CHUNK_2, semantic_score=0.5),
                 make_candidate(chunk_id=CHUNK_3, semantic_score=0.3)]
        out = self._real_pipeline(cands).retrieve(
            "Form NXP", tenant_id=TENANT, mode="hybrid", top_k=2)
        self.assertEqual(len(out), 2)
        self.assertEqual([r.rank_position for r in out], [1, 2])


class TestNoProviderDependencies(unittest.TestCase):
    """The pipeline module imports stdlib + domain code only."""

    def test_no_qdrant_embedding_or_network_imports(self):
        import ast
        import inspect
        import xportra.domain.evidence_pipeline as module

        tree = ast.parse(inspect.getsource(module))
        imported_roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(
                    alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.level == 0:  # relative = intra-domain, allowed
                    imported_roots.add(node.module.split(".")[0])
        forbidden = {"qdrant_client", "httpx", "requests", "urllib",
                     "socket", "openai", "anthropic"}
        self.assertFalse(
            imported_roots & forbidden,
            f"provider/network import found: {imported_roots & forbidden}")
        self.assertTrue(
            imported_roots <= {"typing", "__future__"},
            f"unexpected absolute imports: {imported_roots}")


class TestFactoryWiring(unittest.TestCase):
    """build_evidence_retrieval_pipeline composes the concrete pieces."""

    def test_factory_defaults_to_deterministic_ranker(self):
        pipeline = build_evidence_retrieval_pipeline(
            semantic_retriever=_SemanticFake([]),
            lexical_index=_LexicalFake([]))
        self.assertIsInstance(pipeline, EvidenceRetrievalPipeline)

    def test_factory_with_explicit_ranker(self):
        custom = RecordingRanker()
        pipeline = build_evidence_retrieval_pipeline(
            semantic_retriever=_SemanticFake([]),
            lexical_index=_LexicalFake([]),
            ranker=custom)
        self.assertIsInstance(pipeline, EvidenceRetrievalPipeline)

    def test_factory_produces_working_pipeline(self):
        fake_semantic = _SemanticFake([make_result(chunk_id=CHUNK_1,
                                                   score=0.9)])
        fake_lexical = _LexicalFake([])
        pipeline = build_evidence_retrieval_pipeline(
            semantic_retriever=fake_semantic,
            lexical_index=fake_lexical)
        out = pipeline.retrieve(
            "Form NXP", tenant_id=TENANT, mode="semantic", top_k=1)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].rank_position, 1)
        self.assertEqual(out[0].evidence.chunk_id, CHUNK_1)

    def test_factory_rejects_missing_dependencies(self):
        with self.assertRaises(DomainValidationError):
            build_evidence_retrieval_pipeline(
                semantic_retriever=None,
                lexical_index=_LexicalFake([]))
        with self.assertRaises(DomainValidationError):
            build_evidence_retrieval_pipeline(
                semantic_retriever=_SemanticFake([]),
                lexical_index=None)


# ---- fakes for the factory tests (compose real Phase 5.4 pieces) ----


class _SemanticFake:
    """Minimal EvidenceRetriever fake for factory wiring."""

    def __init__(self, results):
        self._results = results

    def retrieve(self, query, *, tenant_id, scope=None):
        return list(self._results)


class _LexicalFake:
    """Minimal EvidenceLexicalIndex fake for factory wiring."""

    def __init__(self, results):
        self._results = results

    def find_lexical(self, terms, *, tenant_id, top_k, scope=None):
        return list(self._results)


if __name__ == "__main__":
    unittest.main()
