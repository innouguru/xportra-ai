"""Phase 5.8 — Retrieval-to-Context Pipeline Composition tests.

Covers the composition boundary only:
``EvidenceContextPipeline`` and ``build_evidence_context_pipeline`` —
dependency injection, parameter propagation to the Phase 5.6
retrieval pipeline and Phase 5.7 context selector, mode forwarding,
empty behavior, failure propagation, result integrity, budget
ownership, and purity.

Fakes only — no live Qdrant, no embeddings, no LLM, no network.
Lower-level semantics (retrieval, ranking, selection) are NOT
re-tested here; they have their own focused suites.
"""

import ast
import inspect
import unittest
from uuid import UUID

from xportra.domain.errors import DomainValidationError
from xportra.domain.evidence_context import (
    DeterministicContextSelector,
    EvidenceContextBudget,
    EvidenceContextSelection,
    SelectedEvidence,
)
from xportra.domain.evidence_context_pipeline import (
    EvidenceContextPipeline,
    build_evidence_context_pipeline,
)
from xportra.domain.evidence_ranking import (
    DeterministicEvidenceRanker,
    RankedEvidenceResult,
)
from xportra.domain.evidence_retrieval import EvidenceRetrievalResult
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
TENANT = TenantContext(TENANT_ID)

DOC_A = UUID("11111111-1111-1111-1111-111111111111")
CHUNK_1 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")
CHUNK_2 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2")

MODEL = "test-embed-model"
DIMS = 4


def make_evidence(index=1, content="Exporters must file Form NXP."):
    return EvidenceRetrievalResult(
        tenant_id=TENANT_ID,
        chunk_id=UUID(f"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa{index}"),
        document_id=DOC_A,
        chunk_index=0,
        content=content,
        content_fingerprint=f"fp-{index}",
        source_id="sonsa/cert-guide",
        source_type="guidance",
        source_location="https://example.test/guide",
        document_version="v1",
        embedding_model=MODEL,
        embedding_dimensions=DIMS,
        score=0.9,
    )


def make_ranked(contents):
    """Build a realistic ranked list via the real Phase 5.5 ranker."""
    from xportra.domain.evidence_hybrid import HybridRetrievalCandidate

    candidates = []
    for index, content in enumerate(contents, start=1):
        evidence = make_evidence(index=index, content=content)
        candidates.append(
            HybridRetrievalCandidate(
                evidence=evidence,
                semantic_score=1.0 - index * 0.1,
                lexical_score=None,
                retrieval_sources=frozenset({"semantic"}),
            )
        )
    return DeterministicEvidenceRanker().rank(
        candidates, top_k=len(candidates))


class FakeRetrievalPipeline:
    """Records calls; returns a canned ranked list."""

    def __init__(self, ranked=None, error=None):
        self.ranked = ranked if ranked is not None else []
        self.error = error
        self.calls = []

    def retrieve(self, information_need, **kwargs):
        self.calls.append((information_need, kwargs))
        if self.error is not None:
            raise self.error
        return self.ranked


class FakeContextSelector:
    """Records calls; returns a canned selection."""

    def __init__(self, selection=None, error=None):
        self.selection = selection
        self.error = error
        self.calls = []

    def select(self, ranked, *, tenant_id, budget):
        self.calls.append(
            {"ranked": ranked, "tenant_id": tenant_id, "budget": budget})
        if self.error is not None:
            raise self.error
        if self.selection is not None:
            return self.selection
        return EvidenceContextSelection(
            budget=budget,
            selected_items=(),
            used_budget=0,
            skipped_rank_positions=(),
        )


def make_pipeline(ranked=None, *, retrieval_error=None,
                  selection=None, selector_error=None):
    retrieval = FakeRetrievalPipeline(
        ranked=ranked, error=retrieval_error)
    selector = FakeContextSelector(
        selection=selection, error=selector_error)
    pipeline = EvidenceContextPipeline(
        retrieval_pipeline=retrieval, context_selector=selector)
    return pipeline, retrieval, selector


class TestDependencyInjection(unittest.TestCase):
    """Injected collaborators are used; nothing is reconstructed."""

    def test_injected_retrieval_pipeline_is_used(self):
        pipeline, retrieval, _ = make_pipeline()
        pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100))
        self.assertEqual(len(retrieval.calls), 1)

    def test_injected_context_selector_is_used(self):
        pipeline, _, selector = make_pipeline()
        pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100))
        self.assertEqual(len(selector.calls), 1)

    def test_missing_retrieval_pipeline_rejected(self):
        with self.assertRaises(DomainValidationError):
            EvidenceContextPipeline(
                retrieval_pipeline=None,
                context_selector=FakeContextSelector())
        with self.assertRaises(DomainValidationError):
            EvidenceContextPipeline(
                retrieval_pipeline="nope",
                context_selector=FakeContextSelector())

    def test_missing_context_selector_rejected(self):
        with self.assertRaises(DomainValidationError):
            EvidenceContextPipeline(
                retrieval_pipeline=FakeRetrievalPipeline(),
                context_selector=None)
        with self.assertRaises(DomainValidationError):
            EvidenceContextPipeline(
                retrieval_pipeline=FakeRetrievalPipeline(),
                context_selector=42)


class TestPropagation(unittest.TestCase):
    """Every caller parameter reaches the boundary that owns it."""

    def test_information_need_reaches_retrieval_pipeline(self):
        pipeline, retrieval, _ = make_pipeline()
        pipeline.select_context(
            "nxp filing deadline", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100))
        self.assertEqual(retrieval.calls[0][0], "nxp filing deadline")

    def test_tenant_reaches_retrieval_pipeline(self):
        pipeline, retrieval, _ = make_pipeline()
        pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100))
        self.assertIs(retrieval.calls[0][1]["tenant_id"], TENANT)

    def test_mode_reaches_retrieval_pipeline(self):
        for mode in ("semantic", "lexical", "hybrid"):
            pipeline, retrieval, _ = make_pipeline()
            pipeline.select_context(
                "need", tenant_id=TENANT, mode=mode,
                context_budget=EvidenceContextBudget(100))
            self.assertEqual(retrieval.calls[0][1]["mode"], mode)

    def test_invalid_mode_is_forwarded_not_converted(self):
        # Mode validation belongs to Phase 5.6 — this layer forwards
        # unchanged and must not silently convert or default it.
        pipeline, retrieval, _ = make_pipeline(
            retrieval_error=DomainValidationError("bad mode"))
        with self.assertRaises(DomainValidationError):
            pipeline.select_context(
                "need", tenant_id=TENANT, mode="bogus",
                context_budget=EvidenceContextBudget(100))

    def test_scope_reaches_retrieval_pipeline_unchanged(self):
        from xportra.domain.evidence_retrieval import (
            EvidenceRetrievalScope,
        )

        scope = EvidenceRetrievalScope(source_id="sonsa/cert-guide")
        pipeline, retrieval, _ = make_pipeline()
        pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100), scope=scope)
        self.assertIs(retrieval.calls[0][1]["scope"], scope)

    def test_scope_none_reaches_retrieval_pipeline(self):
        pipeline, retrieval, _ = make_pipeline()
        pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100))
        self.assertIsNone(retrieval.calls[0][1]["scope"])

    def test_top_k_reaches_retrieval_pipeline(self):
        pipeline, retrieval, _ = make_pipeline()
        pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100), top_k=7)
        self.assertEqual(retrieval.calls[0][1]["top_k"], 7)

    def test_default_top_k_is_forwarded(self):
        from xportra.domain.evidence_retrieval import DEFAULT_TOP_K

        pipeline, retrieval, _ = make_pipeline()
        pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100))
        self.assertEqual(retrieval.calls[0][1]["top_k"], DEFAULT_TOP_K)

    def test_candidate_pool_reaches_retrieval_pipeline(self):
        pipeline, retrieval, _ = make_pipeline()
        pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100), candidate_pool=9)
        self.assertEqual(
            retrieval.calls[0][1]["candidate_pool"], 9)

    def test_candidate_pool_none_reaches_retrieval_pipeline(self):
        pipeline, retrieval, _ = make_pipeline()
        pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100))
        self.assertIsNone(retrieval.calls[0][1]["candidate_pool"])

    def test_context_budget_reaches_context_selector(self):
        budget = EvidenceContextBudget(250)
        pipeline, _, selector = make_pipeline()
        pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=budget)
        self.assertIs(selector.calls[0]["budget"], budget)

    def test_tenant_reaches_context_selector(self):
        pipeline, _, selector = make_pipeline()
        pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100))
        self.assertIs(selector.calls[0]["tenant_id"], TENANT)


class TestTenantBoundary(unittest.TestCase):
    """Tenant is mandatory at the composition API boundary too."""

    def test_missing_tenant_rejected(self):
        pipeline, retrieval, selector = make_pipeline()
        with self.assertRaises(DomainValidationError):
            pipeline.select_context(
                "need", tenant_id=None, mode="hybrid",
                context_budget=EvidenceContextBudget(100))
        self.assertEqual(retrieval.calls, [])
        self.assertEqual(selector.calls, [])

    def test_non_tenant_context_rejected(self):
        pipeline, retrieval, selector = make_pipeline()
        with self.assertRaises(DomainValidationError):
            pipeline.select_context(
                "need", tenant_id="tenant-abc", mode="hybrid",
                context_budget=EvidenceContextBudget(100))
        self.assertEqual(retrieval.calls, [])
        self.assertEqual(selector.calls, [])


class TestComposition(unittest.TestCase):
    """Retrieval output becomes selector input; selector output is final."""

    def test_retrieval_output_becomes_selector_input(self):
        ranked = make_ranked(["alpha", "beta"])
        pipeline, _, selector = make_pipeline(ranked=ranked)
        pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100))
        self.assertIs(selector.calls[0]["ranked"], ranked)

    def test_selector_output_is_returned_exact(self):
        ranked = make_ranked(["alpha"])
        sentinel = EvidenceContextSelection(
            budget=EvidenceContextBudget(10),
            selected_items=(
                SelectedEvidence(
                    rank_position=1,
                    ranked=ranked[0],
                    character_count=len(ranked[0].evidence.content),
                ),
            ),
            used_budget=len(ranked[0].evidence.content),
            skipped_rank_positions=(),
        )
        pipeline, _, _ = make_pipeline(
            ranked=ranked, selection=sentinel)
        result = pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(10))
        self.assertIs(result, sentinel)

    def test_end_to_end_with_real_lower_boundaries(self):
        """Full composition: real 5.5 ranker output through the real
        5.7 selector, driven only by the orchestrator under test."""
        ranked = make_ranked(["abcdef", "gh", "ijklm"])
        retrieval = FakeRetrievalPipeline(ranked=ranked)
        pipeline = EvidenceContextPipeline(
            retrieval_pipeline=retrieval,
            context_selector=DeterministicContextSelector(),
        )
        selection = pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(8))
        # 6 + 2 = 8 chars; the 5-char third item does not fit.
        self.assertEqual(selection.used_budget, 8)
        self.assertEqual(
            [item.rank_position for item in selection.selected_items],
            [1, 2])
        self.assertEqual(
            selection.skipped_rank_positions, (3,))


class TestEmptyBehavior(unittest.TestCase):
    """Empty ranked evidence → successful empty selection."""

    def test_empty_ranked_evidence_produces_empty_selection(self):
        pipeline, retrieval, selector = make_pipeline(ranked=[])
        result = pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100))
        self.assertIsInstance(result, EvidenceContextSelection)
        self.assertEqual(result.selected_items, ())
        self.assertEqual(result.used_budget, 0)
        # The empty collection was still forwarded to the selector.
        self.assertEqual(len(selector.calls), 1)
        self.assertEqual(selector.calls[0]["ranked"], [])


class TestFailurePropagation(unittest.TestCase):
    """Failures propagate unchanged — never converted to empty success."""

    def test_retrieval_failure_propagates_identity(self):
        boom = RuntimeError("vector store unavailable")
        pipeline, retrieval, selector = make_pipeline(
            retrieval_error=boom)
        with self.assertRaises(RuntimeError) as ctx:
            pipeline.select_context(
                "need", tenant_id=TENANT, mode="hybrid",
                context_budget=EvidenceContextBudget(100))
        self.assertIs(ctx.exception, boom)
        self.assertEqual(selector.calls, [])

    def test_domain_retrieval_failure_propagates_identity(self):
        boom = DomainValidationError("bad query")
        pipeline, _, selector = make_pipeline(retrieval_error=boom)
        with self.assertRaises(DomainValidationError) as ctx:
            pipeline.select_context(
                "need", tenant_id=TENANT, mode="hybrid",
                context_budget=EvidenceContextBudget(100))
        self.assertIs(ctx.exception, boom)
        self.assertEqual(selector.calls, [])

    def test_context_selection_failure_propagates_identity(self):
        boom = DomainValidationError("cross-tenant evidence")
        pipeline, _, _ = make_pipeline(
            ranked=make_ranked(["alpha"]), selector_error=boom)
        with self.assertRaises(DomainValidationError) as ctx:
            pipeline.select_context(
                "need", tenant_id=TENANT, mode="hybrid",
                context_budget=EvidenceContextBudget(100))
        self.assertIs(ctx.exception, boom)

    def test_arbitrary_selector_failure_not_masked(self):
        boom = KeyError("integrity failure")
        pipeline, _, _ = make_pipeline(selector_error=boom)
        with self.assertRaises(KeyError) as ctx:
            pipeline.select_context(
                "need", tenant_id=TENANT, mode="hybrid",
                context_budget=EvidenceContextBudget(100))
        self.assertIs(ctx.exception, boom)


class TestIntegrity(unittest.TestCase):
    """Ranked evidence is passed through unmodified and in order."""

    def test_ranked_results_not_mutated(self):
        ranked = make_ranked(["alpha", "beta", "gamma"])
        snapshot = [
            (r.rank_position, r.evidence.content, r.semantic_score,
             tuple(sorted(r.retrieval_sources)), r.ranking_key)
            for r in ranked
        ]
        pipeline, _, _ = make_pipeline(ranked=ranked)
        pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100))
        self.assertEqual(
            [(r.rank_position, r.evidence.content, r.semantic_score,
              tuple(sorted(r.retrieval_sources)), r.ranking_key)
             for r in ranked],
            snapshot)
        self.assertEqual(len(ranked), 3)

    def test_ordering_unchanged_into_selector(self):
        ranked = make_ranked(["alpha", "beta", "gamma"])
        pipeline, _, selector = make_pipeline(ranked=ranked)
        pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100))
        self.assertEqual(
            selector.calls[0]["ranked"], ranked)
        self.assertEqual(
            [r.rank_position for r in selector.calls[0]["ranked"]],
            [1, 2, 3])

    def test_malformed_retrieval_output_rejected(self):
        pipeline, _, selector = make_pipeline(ranked="not a list")
        with self.assertRaises(DomainValidationError):
            pipeline.select_context(
                "need", tenant_id=TENANT, mode="hybrid",
                context_budget=EvidenceContextBudget(100))
        self.assertEqual(selector.calls, [])

    def test_non_ranked_items_rejected(self):
        pipeline, _, selector = make_pipeline(
            ranked=["not a ranked result"])
        with self.assertRaises(DomainValidationError):
            pipeline.select_context(
                "need", tenant_id=TENANT, mode="hybrid",
                context_budget=EvidenceContextBudget(100))
        self.assertEqual(selector.calls, [])

    def test_non_string_information_need_rejected(self):
        pipeline, retrieval, selector = make_pipeline()
        with self.assertRaises(DomainValidationError):
            pipeline.select_context(
                None, tenant_id=TENANT, mode="hybrid",
                context_budget=EvidenceContextBudget(100))
        self.assertEqual(retrieval.calls, [])
        self.assertEqual(selector.calls, [])

    def test_non_budget_object_rejected(self):
        pipeline, retrieval, selector = make_pipeline()
        with self.assertRaises(DomainValidationError):
            pipeline.select_context(
                "need", tenant_id=TENANT, mode="hybrid",
                context_budget=100)
        self.assertEqual(retrieval.calls, [])
        self.assertEqual(selector.calls, [])


class TestBudgetOwnership(unittest.TestCase):
    """The orchestrator performs no budget arithmetic of its own."""

    def test_selector_receives_authoritative_budget_object(self):
        budget = EvidenceContextBudget(64)
        pipeline, _, selector = make_pipeline(
            ranked=make_ranked(["a", "b"]))
        pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=budget)
        self.assertIs(selector.calls[0]["budget"], budget)

    def test_no_premature_truncation_before_selector(self):
        # A ranked set larger than the budget flows to the selector
        # intact — the orchestrator never pre-filters by budget.
        ranked = make_ranked(["x" * 50, "y" * 50, "z" * 50])
        pipeline, _, selector = make_pipeline(ranked=ranked)
        pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(60))
        self.assertEqual(len(selector.calls[0]["ranked"]), 3)


class TestFactory(unittest.TestCase):
    """build_evidence_context_pipeline wires the concrete pipeline."""

    def _make_providers(self):
        # Local fakes honoring the Phase 5.4 collaborator contracts
        # (EvidenceRetriever.retrieve / EvidenceLexicalIndex.find_lexical).
        class FakeSemanticRetriever:
            def retrieve(self, query, *, tenant_id, scope=None):
                return []

        class FakeLexicalIndex:
            def find_lexical(self, terms, *, tenant_id, top_k,
                             scope=None):
                return []

        return FakeSemanticRetriever(), FakeLexicalIndex()

    def test_factory_produces_working_pipeline(self):
        semantic, lexical = self._make_providers()
        pipeline = build_evidence_context_pipeline(
            semantic_retriever=semantic, lexical_index=lexical)
        self.assertIsInstance(pipeline, EvidenceContextPipeline)

    def test_factory_end_to_end_empty(self):
        semantic, lexical = self._make_providers()
        pipeline = build_evidence_context_pipeline(
            semantic_retriever=semantic, lexical_index=lexical)
        selection = pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100))
        self.assertIsInstance(selection, EvidenceContextSelection)
        self.assertEqual(selection.selected_items, ())

    def test_factory_accepts_explicit_selector(self):
        semantic, lexical = self._make_providers()
        selector = DeterministicContextSelector()
        pipeline = build_evidence_context_pipeline(
            semantic_retriever=semantic, lexical_index=lexical,
            context_selector=selector)
        self.assertIsInstance(pipeline, EvidenceContextPipeline)
        selection = pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100))
        self.assertEqual(selection.selected_items, ())


class TestPurity(unittest.TestCase):
    """Pure domain orchestration: no infrastructure, no lower-layer bypass."""

    def test_no_infrastructure_imports(self):
        import xportra.domain.evidence_context_pipeline as module

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
                     "transformers", "psycopg"}
        self.assertFalse(
            imported_roots & forbidden,
            f"forbidden import found: {imported_roots & forbidden}")
        self.assertTrue(
            imported_roots <= {"__future__", "typing"},
            f"unexpected absolute imports: {imported_roots}")

    def test_module_imports_stay_within_domain_boundary(self):
        # AST check: the orchestrator module imports only its own
        # sibling domain modules plus stdlib typing — never an
        # infrastructure SDK or a lower-layer internal directly.
        import xportra.domain.evidence_context_pipeline as module

        tree = ast.parse(inspect.getsource(module))
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(
                    alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
        allowed = {
            "errors",
            "evidence_context",
            "evidence_pipeline",
            "evidence_ranking",
            "evidence_retrieval",
            "__future__",
            "typing",
        }
        self.assertTrue(
            imported_modules <= allowed,
            f"unexpected imports: {imported_modules - allowed}")

    def test_no_network_or_llm_during_composition(self):
        # The whole composition runs with only in-memory fakes — any
        # network/LLM dependency would make this test impossible.
        pipeline, _, _ = make_pipeline(
            ranked=make_ranked(["alpha"]))
        result = pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100))
        self.assertIsInstance(result, EvidenceContextSelection)

    def test_orchestrator_does_not_call_retriever_or_ranker_directly(self):
        # The fakes expose only the boundary methods; if the
        # orchestrator bypassed the Phase 5.6 pipeline to call a
        # hybrid retriever or ranker, the recorded calls would not
        # match exactly one retrieve + one select call.
        pipeline, retrieval, selector = make_pipeline(
            ranked=make_ranked(["alpha"]))
        pipeline.select_context(
            "need", tenant_id=TENANT, mode="hybrid",
            context_budget=EvidenceContextBudget(100))
        self.assertEqual(len(retrieval.calls), 1)
        self.assertEqual(len(selector.calls), 1)


if __name__ == "__main__":
    unittest.main()
