"""Phase 5.4 — Hybrid Retrieval Boundary tests.

Covers lexical tokenization/matching semantics, the three retrieval
modes, candidate merging and provenance, per-path score preservation,
tenant/scope enforcement on both paths, fail-closed failure behavior
(no degraded hybrid mode), determinism, provenance preservation, and the
Qdrant lexical translation with domain-rule verification. Fakes only —
no live Qdrant server required.
"""

import dataclasses
import types
import unittest
from uuid import UUID

from qdrant_client.http import models as qmodels

from xportra.domain.errors import DomainValidationError, VectorStoreError
from xportra.domain.evidence_hybrid import (
    ComposedHybridEvidenceRetriever,
    HybridEvidenceRetriever,
    HybridRetrievalCandidate,
    lexical_matches,
    lexical_relevance_score,
    lexical_terms,
    lexical_tokens,
)
from xportra.domain.evidence_indexing import EmbeddingModelConfig
from xportra.domain.evidence_retrieval import (
    EvidenceRetrievalQuery,
    EvidenceRetrievalResult,
    EvidenceRetrievalScope,
    VectorIndexEvidenceRetriever,
)
from xportra.domain.vector_index import VectorIndexConfig
from xportra.infrastructure.vector_index import QdrantEvidenceVectorIndex
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TENANT = TenantContext(TENANT_ID)
OTHER_TENANT = TenantContext(OTHER_TENANT_ID)

DOC_A = UUID("11111111-1111-1111-1111-111111111111")
DOC_B = UUID("22222222-2222-2222-2222-222222222222")
DOC_A_V2 = UUID("33333333-3333-3333-3333-333333333333")

CHUNK_1 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")
CHUNK_2 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2")
CHUNK_3 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3")
CHUNK_4 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa4")
CHUNK_5 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa5")

SRC_A = "sonsa/cert-guide"
SRC_B = "nafdac/cocoa-regulation"
MODEL = "test-embed-model"
DIMS = 4
EMBEDDING_CONFIG = EmbeddingModelConfig(
    model_identifier=MODEL, dimensions=DIMS)
QUERY_VECTOR = [1.0, 0.0, 0.0, 0.0]


def make_result(**overrides):
    base = dict(
        tenant_id=TENANT_ID,
        chunk_id=CHUNK_1,
        document_id=DOC_A,
        chunk_index=0,
        content="Exporters must file Form NXP for cocoa exports.",
        content_fingerprint="fp-1",
        source_id=SRC_A,
        source_type="guidance",
        source_location="https://example.test/guide",
        document_version="v1",
        embedding_model=MODEL,
        embedding_dimensions=DIMS,
        score=0.9,
    )
    base.update(overrides)
    return EvidenceRetrievalResult(**base)


def semantic_results():
    return [
        make_result(chunk_id=CHUNK_1, score=0.9,
                    content="Exporters must file Form NXP.",
                    content_fingerprint="fp-1"),
        make_result(chunk_id=CHUNK_2, chunk_index=1, score=0.7,
                    content="Inspection requirements apply.",
                    content_fingerprint="fp-2"),
        make_result(chunk_id=CHUNK_3, document_id=DOC_B, source_id=SRC_B,
                    source_type="regulation", score=0.5,
                    content="SONCAP applies to regulated products.",
                    content_fingerprint="fp-3"),
    ]


def lexical_results():
    return [
        # CHUNK_1 also appears in the semantic path (merge case)
        make_result(chunk_id=CHUNK_1, content="Form NXP form.",
                    content_fingerprint="fp-1", score=0.0),
        make_result(chunk_id=CHUNK_4, document_id=DOC_A, chunk_index=2,
                    content="Section 4.2 lists NAFDAC forms.",
                    content_fingerprint="fp-4", score=0.0),
    ]


class FakeProvider:
    def __init__(self, fail=False, vector=None):
        self.fail = fail
        self.vector = vector
        self.calls = []

    def embed(self, text):
        self.calls.append(text)
        if self.fail:
            raise RuntimeError("provider down")
        if self.vector is not None:
            return list(self.vector)
        return [1.0, 0.0, 0.0, 0.0]


class FakeVectorIndex:
    """EvidenceVectorIndex double (Phase 5.1/5.2 semantics)."""

    def __init__(self, results=None, fail=False, ignore_tenant=False,
                 ignore_scope=False, raw_output=None):
        self.results = list(results if results is not None
                            else semantic_results())
        self.fail = fail
        self.ignore_tenant = ignore_tenant
        self.ignore_scope = ignore_scope
        self.raw_output = raw_output
        self.find_calls = []

    def find(self, query_vector, *, tenant_id, top_k, scope=None):
        self.find_calls.append(
            (list(query_vector), tenant_id, top_k, scope))
        if self.fail:
            raise RuntimeError("vector store down")
        if self.raw_output is not None:
            return self.raw_output
        selected = []
        for result in self.results:
            if not self.ignore_tenant and (
                    result.tenant_id != tenant_id.tenant_id):
                continue
            if (scope is not None and not self.ignore_scope
                    and not scope.accepts(result)):
                continue
            selected.append(result)
        return list(selected[:top_k])


class FakeLexicalIndex:
    """EvidenceLexicalIndex double honoring the Phase 5.4 contract."""

    def __init__(self, results=None, fail=False, ignore_tenant=False,
                 ignore_scope=False, raw_output=None, honor_terms=True):
        self.results = list(results if results is not None
                            else lexical_results())
        self.fail = fail
        self.ignore_tenant = ignore_tenant
        self.ignore_scope = ignore_scope
        self.raw_output = raw_output
        self.honor_terms = honor_terms
        self.find_calls = []

    def find_lexical(self, terms, *, tenant_id, top_k, scope=None):
        self.find_calls.append((tuple(terms), tenant_id, top_k, scope))
        if self.fail:
            raise RuntimeError("lexical store down")
        if self.raw_output is not None:
            return self.raw_output
        selected = []
        for result in self.results:
            if not self.ignore_tenant and (
                    result.tenant_id != tenant_id.tenant_id):
                continue
            if (scope is not None and not self.ignore_scope
                    and not scope.accepts(result)):
                continue
            if self.honor_terms and not lexical_matches(
                    result.content, tuple(terms)):
                continue
            selected.append(dataclasses.replace(
                result,
                score=lexical_relevance_score(
                    result.content, tuple(terms))))
        selected.sort(key=lambda item: (-item.score, item.chunk_id))
        return list(selected[:top_k])


class RecordingSemanticRetriever:
    """EvidenceRetriever double for dispatch and failure tests."""

    def __init__(self, results=None, error=None):
        self.results = list(results if results is not None else [])
        self.error = error
        self.calls = []

    def retrieve(self, query, *, tenant_id, scope=None):
        self.calls.append((query, tenant_id, scope))
        if self.error is not None:
            raise self.error
        return list(self.results)


def make_semantic_retriever(index=None, provider=None):
    return VectorIndexEvidenceRetriever(
        vector_index=FakeVectorIndex() if index is None else index,
        provider=FakeProvider() if provider is None else provider,
        embedding_config=EMBEDDING_CONFIG,
    )


def make_hybrid(semantic_retriever=None, lexical_index=None):
    return ComposedHybridEvidenceRetriever(
        semantic_retriever=(
            make_semantic_retriever() if semantic_retriever is None
            else semantic_retriever),
        lexical_index=(
            FakeLexicalIndex() if lexical_index is None
            else lexical_index),
    )


class TestLexicalTokenization(unittest.TestCase):
    """Deterministic, conservative lexical tokenization."""

    def test_01_basic_terms_lowercased_and_split(self) -> None:
        self.assertEqual(lexical_terms("Form NXP"), ("form", "nxp"))
        self.assertEqual(
            lexical_terms("SONCAP certificate"),
            ("soncap", "certificate"))

    def test_02_punctuation_is_a_separator(self) -> None:
        self.assertEqual(
            lexical_terms("HS code 1801."), ("hs", "code", "1801"))
        self.assertEqual(lexical_terms("Section 4.2"),
                         ("section", "4", "2"))
        self.assertEqual(lexical_terms('"NAFDAC", (cocoa)'),
                         ("nafdac", "cocoa"))

    def test_03_duplicates_removed_first_occurrence_order(self) -> None:
        self.assertEqual(
            lexical_terms("NXP nxp Form"), ("nxp", "form"))

    def test_04_unicode_alphanumerics_preserved(self) -> None:
        self.assertEqual(
            lexical_terms("Café SONCAP"), ("café", "soncap"))

    def test_05_non_alphanumeric_text_yields_no_terms(self) -> None:
        for text in ("", "   ", "!!! ??? ...", "---"):
            self.assertEqual(lexical_terms(text), ())

    def test_06_raw_tokens_keep_duplicates(self) -> None:
        self.assertEqual(lexical_tokens("NXP NXP"), ("nxp", "nxp"))
        self.assertEqual(lexical_terms("NXP NXP"), ("nxp",))


class TestLexicalMatching(unittest.TestCase):
    """Exact whole-token AND matching — no prefix or substring rules."""

    def test_01_all_terms_present_as_whole_tokens(self) -> None:
        content = "Exporters must file Form NXP for cocoa."
        self.assertTrue(lexical_matches(content, ("form", "nxp")))
        self.assertTrue(lexical_matches(content, ("nxp",)))

    def test_02_no_partial_token_matching(self) -> None:
        self.assertFalse(lexical_matches("SONCAPX applies", ("soncap",)))
        self.assertFalse(lexical_matches("HS 18012.", ("1801",)))

    def test_03_and_semantics(self) -> None:
        content = "Form NXP only."
        self.assertTrue(lexical_matches(content, ("form", "nxp")))
        self.assertFalse(lexical_matches(content, ("form", "soncap")))
        self.assertFalse(lexical_matches(content, ()))

    def test_04_lexical_relevance_counts_occurrences(self) -> None:
        self.assertEqual(
            lexical_relevance_score("NXP form NXP.", ("nxp", "form")),
            3.0)
        self.assertEqual(
            lexical_relevance_score("NXP only.", ("nxp", "form")), 1.0)
        self.assertEqual(
            lexical_relevance_score("nothing here", ("nxp",)), 0.0)
        self.assertEqual(lexical_relevance_score("anything", ()), 0.0)


class TestCandidateModel(unittest.TestCase):
    """Candidate provenance is explicit and self-consistent."""

    def test_01_valid_candidate_shapes(self) -> None:
        semantic = HybridRetrievalCandidate(
            evidence=make_result(),
            semantic_score=0.9,
            lexical_score=None,
            retrieval_sources={"semantic"},
        )
        self.assertEqual(semantic.source_labels(), ("semantic",))
        self.assertFalse(semantic.is_hybrid)
        self.assertIsInstance(semantic.retrieval_sources, frozenset)
        lexical = HybridRetrievalCandidate(
            evidence=make_result(),
            semantic_score=None,
            lexical_score=2.0,
            retrieval_sources=frozenset({"lexical"}),
        )
        self.assertEqual(lexical.source_labels(), ("lexical",))
        both = HybridRetrievalCandidate(
            evidence=make_result(),
            semantic_score=0.9,
            lexical_score=2.0,
            retrieval_sources=frozenset({"semantic", "lexical"}),
        )
        self.assertTrue(both.is_hybrid)
        self.assertEqual(both.source_labels(), ("lexical", "semantic"))

    def test_02_inconsistent_provenance_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            HybridRetrievalCandidate(
                evidence=make_result(), semantic_score=None,
                lexical_score=None,
                retrieval_sources=frozenset({"semantic"}))
        with self.assertRaises(DomainValidationError):
            HybridRetrievalCandidate(
                evidence=make_result(), semantic_score=0.5,
                lexical_score=None,
                retrieval_sources=frozenset({"lexical"}))

    def test_03_invalid_scores_and_evidence_rejected(self) -> None:
        for bad in (float("nan"), float("inf"), True, "0.5"):
            with self.assertRaises(DomainValidationError):
                HybridRetrievalCandidate(
                    evidence=make_result(), semantic_score=bad,
                    lexical_score=None,
                    retrieval_sources=frozenset({"semantic"}))
        with self.assertRaises(DomainValidationError):
            HybridRetrievalCandidate(
                evidence="not-a-result", semantic_score=None,
                lexical_score=1.0,
                retrieval_sources=frozenset({"lexical"}))

    def test_04_malformed_sources_rejected(self) -> None:
        for bad in (set(), frozenset(), frozenset({"other"}), []):
            with self.assertRaises(DomainValidationError):
                HybridRetrievalCandidate(
                    evidence=make_result(), semantic_score=None,
                    lexical_score=1.0, retrieval_sources=bad)


class TestSemanticMode(unittest.TestCase):
    """Semantic mode keeps the Phase 5.1/5.2 path intact."""

    def test_01_semantic_mode_returns_semantic_candidates(self) -> None:
        candidates = make_hybrid().retrieve_candidates(
            EvidenceRetrievalQuery("certificate"), tenant_id=TENANT,
            mode="semantic")
        self.assertEqual(len(candidates), 3)
        for candidate in candidates:
            self.assertIsInstance(candidate, HybridRetrievalCandidate)
            self.assertEqual(candidate.retrieval_sources,
                             frozenset({"semantic"}))
            self.assertIsNotNone(candidate.semantic_score)
            self.assertIsNone(candidate.lexical_score)
        self.assertEqual(
            [c.evidence.chunk_id for c in candidates],
            [CHUNK_1, CHUNK_2, CHUNK_3])
        self.assertEqual(
            [c.semantic_score for c in candidates], [0.9, 0.7, 0.5])

    def test_02_semantic_mode_never_calls_the_lexical_index(self) -> None:
        lexical = FakeLexicalIndex()
        semantic = RecordingSemanticRetriever(results=semantic_results())
        hybrid = make_hybrid(
            semantic_retriever=semantic, lexical_index=lexical)
        hybrid.retrieve_candidates(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT, mode="semantic")
        self.assertEqual(lexical.find_calls, [])
        self.assertEqual(len(semantic.calls), 1)
        _query, tenant, scope = semantic.calls[0]
        self.assertEqual(tenant, TENANT)
        self.assertTrue(scope.is_empty)

    def test_03_semantic_path_still_embeds_the_query(self) -> None:
        provider = FakeProvider()
        hybrid = make_hybrid(
            semantic_retriever=make_semantic_retriever(provider=provider))
        hybrid.retrieve_candidates(
            EvidenceRetrievalQuery("certificate"), tenant_id=TENANT,
            mode="semantic")
        self.assertEqual(provider.calls, ["certificate"])


class TestLexicalMode(unittest.TestCase):
    """Lexical mode: exact term retrieval, no embedding involved."""

    def test_01_terms_derived_from_normalized_query(self) -> None:
        lexical = FakeLexicalIndex()
        hybrid = make_hybrid(lexical_index=lexical)
        hybrid.retrieve_candidates(
            EvidenceRetrievalQuery("  Form   NXP  "), tenant_id=TENANT,
            mode="lexical")
        terms, tenant, top_k, scope = lexical.find_calls[0]
        self.assertEqual(terms, ("form", "nxp"))
        self.assertEqual(tenant, TENANT)
        self.assertEqual(top_k, 5)
        self.assertTrue(scope.is_empty)

    def test_02_lexical_mode_does_not_call_the_semantic_path(self) -> None:
        semantic = RecordingSemanticRetriever(results=semantic_results())
        hybrid = make_hybrid(
            semantic_retriever=semantic, lexical_index=FakeLexicalIndex())
        hybrid.retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="lexical")
        self.assertEqual(semantic.calls, [])

    def test_03_lexical_mode_does_not_embed(self) -> None:
        provider = FakeProvider()
        hybrid = make_hybrid(
            semantic_retriever=make_semantic_retriever(provider=provider))
        hybrid.retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="lexical")
        self.assertEqual(provider.calls, [])

    def test_04_lexical_scores_preserved_and_ordered(self) -> None:
        lexical = FakeLexicalIndex(results=[
            make_result(chunk_id=CHUNK_1, score=0.0,
                        content="Form NXP.",
                        content_fingerprint="fp-1"),
            make_result(chunk_id=CHUNK_4, score=0.0,
                        content="Form NXP form NXP.",
                        content_fingerprint="fp-4"),
        ])
        candidates = make_hybrid(lexical_index=lexical).retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="lexical")
        self.assertEqual(
            [c.evidence.chunk_id for c in candidates], [CHUNK_4, CHUNK_1])
        self.assertEqual(
            [c.lexical_score for c in candidates], [4.0, 2.0])
        self.assertTrue(
            all(c.semantic_score is None for c in candidates))

    def test_05_exact_term_retrieval_only(self) -> None:
        lexical = FakeLexicalIndex(results=[
            make_result(chunk_id=CHUNK_1, score=0.0,
                        content="Form NXP is required.",
                        content_fingerprint="fp-1"),
            make_result(chunk_id=CHUNK_2, score=0.0,
                        content="Form NXPX is different.",
                        content_fingerprint="fp-2"),
        ])
        candidates = make_hybrid(lexical_index=lexical).retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="lexical")
        # CHUNK_2 contains "nxpx" — not the whole token "nxp"
        self.assertEqual(
            [c.evidence.chunk_id for c in candidates], [CHUNK_1])


class TestHybridMode(unittest.TestCase):
    """Hybrid mode: union of both paths, explicit provenance."""

    def test_01_hybrid_runs_both_paths(self) -> None:
        semantic = RecordingSemanticRetriever(results=semantic_results())
        lexical = FakeLexicalIndex()
        candidates = make_hybrid(
            semantic_retriever=semantic, lexical_index=lexical
        ).retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="hybrid")
        self.assertEqual(len(semantic.calls), 1)
        self.assertEqual(len(lexical.find_calls), 1)
        self.assertTrue(candidates)

    def test_02_candidate_in_both_paths_is_merged(self) -> None:
        candidates = make_hybrid().retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="hybrid")
        merged = next(
            c for c in candidates if c.evidence.chunk_id == CHUNK_1)
        self.assertTrue(merged.is_hybrid)
        self.assertEqual(merged.retrieval_sources,
                         frozenset({"semantic", "lexical"}))
        self.assertEqual(merged.semantic_score, 0.9)
        self.assertEqual(merged.lexical_score, 3.0)
        self.assertEqual(merged.source_labels(), ("lexical", "semantic"))

    def test_03_no_chunk_returned_twice(self) -> None:
        candidates = make_hybrid().retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="hybrid")
        chunk_ids = [c.evidence.chunk_id for c in candidates]
        self.assertEqual(len(chunk_ids), len(set(chunk_ids)))
        self.assertEqual(
            sorted(chunk_ids), sorted([CHUNK_1, CHUNK_2, CHUNK_3]))

    def test_04_union_is_bounded_per_path(self) -> None:
        lexical = FakeLexicalIndex(results=[
            make_result(chunk_id=CHUNK_1, score=0.0,
                        content="Form NXP.", content_fingerprint="fp-1"),
            make_result(chunk_id=CHUNK_4, score=0.0,
                        content="Form NXP.", content_fingerprint="fp-4"),
        ])
        candidates = make_hybrid(lexical_index=lexical).retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP", top_k=1),
            tenant_id=TENANT, mode="hybrid")
        self.assertLessEqual(len(candidates), 2)

    def test_05_scores_are_preserved_separately_not_fused(self) -> None:
        candidates = make_hybrid().retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="hybrid")
        merged = next(
            c for c in candidates if c.evidence.chunk_id == CHUNK_1)
        self.assertEqual(merged.semantic_score, 0.9)
        self.assertEqual(merged.lexical_score, 3.0)
        for name in ("combined_score", "fused_score", "weighted_score",
                     "final_score", "normalized_score"):
            self.assertFalse(hasattr(merged, name))

    def test_06_deterministic_ordering_semantic_then_lexical(self) -> None:
        lexical = FakeLexicalIndex(results=[
            make_result(chunk_id=CHUNK_4, score=0.0,
                        content="Form NXP.", content_fingerprint="fp-4"),
            make_result(chunk_id=CHUNK_1, score=0.0,
                        content="Form NXP form.",
                        content_fingerprint="fp-1"),
        ])
        candidates = make_hybrid(lexical_index=lexical).retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="hybrid")
        self.assertEqual(
            [c.evidence.chunk_id for c in candidates],
            [CHUNK_1, CHUNK_2, CHUNK_3, CHUNK_4])
        self.assertIsNone(candidates[-1].semantic_score)


class TestTenantAndScopeEnforcement(unittest.TestCase):
    """Both paths preserve the Phase 5.1/5.3 invariants."""

    def test_01_lexical_mode_tenant_isolation(self) -> None:
        lexical = FakeLexicalIndex(results=lexical_results() + [
            make_result(tenant_id=OTHER_TENANT_ID, chunk_id=CHUNK_5,
                        content="Form NXP.", content_fingerprint="fp-5"),
        ])
        candidates = make_hybrid(lexical_index=lexical).retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="lexical")
        self.assertTrue(candidates)
        self.assertTrue(all(
            c.evidence.tenant_id == TENANT_ID for c in candidates))
        self.assertNotIn(
            CHUNK_5, [c.evidence.chunk_id for c in candidates])

    def test_02_hybrid_mode_tenant_isolation(self) -> None:
        lexical = FakeLexicalIndex(results=lexical_results() + [
            make_result(tenant_id=OTHER_TENANT_ID, chunk_id=CHUNK_5,
                        content="Form NXP.", content_fingerprint="fp-5"),
        ])
        candidates = make_hybrid(lexical_index=lexical).retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="hybrid")
        self.assertTrue(all(
            c.evidence.tenant_id == TENANT_ID for c in candidates))

    def test_03_lexical_mode_scope_filtering(self) -> None:
        lexical = FakeLexicalIndex(results=lexical_results() + [
            make_result(chunk_id=CHUNK_5, source_id=SRC_B,
                        source_type="regulation", content="Form NXP.",
                        content_fingerprint="fp-5"),
        ])
        scope = EvidenceRetrievalScope(source_id=SRC_A)
        candidates = make_hybrid(lexical_index=lexical).retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="lexical", scope=scope)
        self.assertTrue(candidates)
        self.assertTrue(all(
            c.evidence.source_id == SRC_A for c in candidates))
        self.assertNotIn(
            CHUNK_5, [c.evidence.chunk_id for c in candidates])
        self.assertEqual(lexical.find_calls[0][3], scope)

    def test_04_hybrid_scope_filtering_covers_merged_results(self) -> None:
        scope = EvidenceRetrievalScope(source_type="guidance")
        candidates = make_hybrid().retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="hybrid", scope=scope)
        self.assertTrue(candidates)
        self.assertTrue(all(
            c.evidence.source_type == "guidance" for c in candidates))
        self.assertNotIn(
            CHUNK_3, [c.evidence.chunk_id for c in candidates])

    def test_05_lexical_cross_tenant_result_fails_closed(self) -> None:
        lexical = FakeLexicalIndex(ignore_tenant=True, results=[
            make_result(tenant_id=OTHER_TENANT_ID, chunk_id=CHUNK_5,
                        content="Form NXP.", content_fingerprint="fp-5"),
        ])
        with self.assertRaises(VectorStoreError) as ctx:
            make_hybrid(lexical_index=lexical).retrieve_candidates(
                EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
                mode="lexical")
        self.assertEqual(ctx.exception.operation, "evidence retrieval")
        self.assertIn("cross-tenant", str(ctx.exception.cause))

    def test_06_lexical_scope_violation_fails_closed(self) -> None:
        lexical = FakeLexicalIndex(ignore_scope=True, results=[
            make_result(chunk_id=CHUNK_5, source_id=SRC_B,
                        source_type="regulation", content="Form NXP.",
                        content_fingerprint="fp-5"),
        ])
        with self.assertRaises(VectorStoreError) as ctx:
            make_hybrid(lexical_index=lexical).retrieve_candidates(
                EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
                mode="lexical",
                scope=EvidenceRetrievalScope(source_id=SRC_A))
        self.assertIn("scope", str(ctx.exception.cause))

    def test_07_semantic_scope_violation_fails_closed(self) -> None:
        semantic = RecordingSemanticRetriever(results=[
            make_result(chunk_id=CHUNK_5, source_id=SRC_B,
                        source_type="regulation"),
        ])
        with self.assertRaises(VectorStoreError) as ctx:
            make_hybrid(semantic_retriever=semantic).retrieve_candidates(
                EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
                mode="semantic",
                scope=EvidenceRetrievalScope(source_id=SRC_A))
        self.assertIn("scope", str(ctx.exception.cause))
        self.assertIn("semantic path", str(ctx.exception.cause))


class TestFailureSemantics(unittest.TestCase):
    """Fail closed — no degraded mode, never a masked empty result."""

    def test_01_semantic_failure_raises(self) -> None:
        semantic = RecordingSemanticRetriever(
            error=VectorStoreError(
                "evidence retrieval", RuntimeError("vector store down")))
        with self.assertRaises(VectorStoreError):
            make_hybrid(semantic_retriever=semantic).retrieve_candidates(
                EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
                mode="semantic")

    def test_02_lexical_failure_is_not_empty_success(self) -> None:
        with self.assertRaises(VectorStoreError) as ctx:
            make_hybrid(
                lexical_index=FakeLexicalIndex(fail=True)
            ).retrieve_candidates(
                EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
                mode="lexical")
        self.assertEqual(
            ctx.exception.operation,
            "hybrid evidence retrieval (lexical path)")
        self.assertIsInstance(ctx.exception.cause, RuntimeError)
        self.assertIn("lexical store down", str(ctx.exception.cause))
        # genuine "no lexical matches" stays a distinct empty result
        self.assertEqual(
            make_hybrid(
                lexical_index=FakeLexicalIndex(results=[])
            ).retrieve_candidates(
                EvidenceRetrievalQuery("NAFDAC SONCAP"), tenant_id=TENANT,
                mode="lexical"),
            [])

    def test_03_hybrid_partial_failure_semantic_ok_lexical_fails(
        self,
    ) -> None:
        with self.assertRaises(VectorStoreError):
            make_hybrid(
                lexical_index=FakeLexicalIndex(fail=True)
            ).retrieve_candidates(
                EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
                mode="hybrid")

    def test_04_hybrid_partial_failure_lexical_ok_semantic_fails(
        self,
    ) -> None:
        semantic = RecordingSemanticRetriever(
            error=VectorStoreError(
                "evidence retrieval", RuntimeError("vector store down")))
        with self.assertRaises(VectorStoreError):
            make_hybrid(semantic_retriever=semantic).retrieve_candidates(
                EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
                mode="hybrid")

    def test_05_empty_lexical_terms_rejected(self) -> None:
        hybrid = make_hybrid()
        for mode in ("lexical", "hybrid"):
            with self.assertRaises(DomainValidationError) as ctx:
                hybrid.retrieve_candidates(
                    EvidenceRetrievalQuery("!!!"), tenant_id=TENANT,
                    mode=mode)
            self.assertIn("lexical query", str(ctx.exception))
        # semantic retrieval is unaffected by punctuation-only queries
        candidates = hybrid.retrieve_candidates(
            EvidenceRetrievalQuery("!!!"), tenant_id=TENANT,
            mode="semantic")
        self.assertEqual(len(candidates), 3)

    def test_06_invalid_mode_scope_tenant_and_query_rejected(self) -> None:
        hybrid = make_hybrid()
        with self.assertRaises(DomainValidationError):
            hybrid.retrieve_candidates(
                EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
                mode="fuzzy")
        with self.assertRaises(DomainValidationError):
            hybrid.retrieve_candidates(
                EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
                mode="hybrid", scope={"source_id": SRC_A})
        for bad_tenant in (None, TENANT_ID, "tenant"):
            with self.assertRaises(DomainValidationError):
                hybrid.retrieve_candidates(
                    EvidenceRetrievalQuery("Form NXP"),
                    tenant_id=bad_tenant, mode="hybrid")
        with self.assertRaises(DomainValidationError):
            hybrid.retrieve_candidates(
                "Form NXP", tenant_id=TENANT, mode="hybrid")

    def test_07_no_results_from_both_paths_returns_empty(self) -> None:
        semantic = RecordingSemanticRetriever(results=[])
        lexical = FakeLexicalIndex(results=[])
        self.assertEqual(
            make_hybrid(
                semantic_retriever=semantic, lexical_index=lexical
            ).retrieve_candidates(
                EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
                mode="hybrid"),
            [])


class TestDeterminismAndProvenance(unittest.TestCase):
    """Deterministic output; complete evidence provenance preserved."""

    def test_01_repeated_hybrid_calls_are_identical(self) -> None:
        hybrid = make_hybrid()
        first = hybrid.retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="hybrid")
        second = hybrid.retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="hybrid")
        self.assertEqual(first, second)

    def test_02_merged_candidate_preserves_full_provenance(self) -> None:
        candidates = make_hybrid().retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="hybrid")
        merged = next(
            c for c in candidates if c.evidence.chunk_id == CHUNK_1)
        evidence = merged.evidence
        self.assertIsInstance(evidence, EvidenceRetrievalResult)
        self.assertEqual(len(evidence.to_record()), 13)
        self.assertEqual(evidence.tenant_id, TENANT_ID)
        self.assertEqual(evidence.document_id, DOC_A)
        self.assertEqual(evidence.content_fingerprint, "fp-1")
        self.assertEqual(evidence.source_id, SRC_A)
        self.assertEqual(evidence.source_type, "guidance")
        self.assertEqual(evidence.document_version, "v1")
        self.assertEqual(evidence.embedding_model, MODEL)
        self.assertEqual(evidence.embedding_dimensions, DIMS)

    def test_03_distinct_document_versions_not_collapsed(self) -> None:
        semantic = RecordingSemanticRetriever(results=[
            make_result(chunk_id=CHUNK_1, document_id=DOC_A,
                        document_version="v1", content_fingerprint="fp-1"),
        ])
        lexical = FakeLexicalIndex(results=[
            make_result(chunk_id=CHUNK_5, document_id=DOC_A_V2,
                        document_version="v2", content_fingerprint="fp-1",
                        content="Form NXP."),
        ])
        candidates = make_hybrid(
            semantic_retriever=semantic, lexical_index=lexical
        ).retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="hybrid")
        self.assertEqual(len(candidates), 2)
        self.assertEqual(
            {c.evidence.document_version for c in candidates},
            {"v1", "v2"})

    def test_04_phase_52_dedup_applies_across_paths(self) -> None:
        semantic = RecordingSemanticRetriever(results=[
            make_result(chunk_id=CHUNK_1, document_id=DOC_A,
                        content_fingerprint="fp-1"),
        ])
        lexical = FakeLexicalIndex(results=[
            make_result(chunk_id=CHUNK_5, document_id=DOC_A,
                        content_fingerprint="fp-1", content="Form NXP."),
        ])
        candidates = make_hybrid(
            semantic_retriever=semantic, lexical_index=lexical
        ).retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="hybrid")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].evidence.chunk_id, CHUNK_1)

    def test_05_lexical_only_candidate_carries_lexical_score(self) -> None:
        lexical = FakeLexicalIndex(results=[
            make_result(chunk_id=CHUNK_4, content="Form NXP.",
                        content_fingerprint="fp-4", score=0.0),
        ])
        candidates = make_hybrid(lexical_index=lexical).retrieve_candidates(
            EvidenceRetrievalQuery("Form NXP"), tenant_id=TENANT,
            mode="lexical")
        candidate = candidates[0]
        self.assertIsNone(candidate.semantic_score)
        self.assertEqual(candidate.lexical_score, 2.0)
        self.assertEqual(candidate.evidence.score, 2.0)

    def test_06_constructed_retriever_satisfies_hybrid_protocol(self) -> None:
        self.assertIsInstance(make_hybrid(), HybridEvidenceRetriever)
        self.assertIsInstance(make_hybrid(), ComposedHybridEvidenceRetriever)


def _provider_prefix_match(content, text):
    """Simulate the provider's full-text token *prefix* matching."""
    tokens = list(lexical_tokens(str(content)))
    return all(
        any(token.startswith(query_token) for token in tokens)
        for query_token in text.split()
    )


class FakeQdrantClient:
    """Filter-honoring Qdrant double with Qdrant-like full-text semantics.

    The simulated full-text condition uses token prefix matching, like
    the provider's full-text index, so tests can prove that the adapter
    narrows provider over-matches to the domain's exact whole-token rule.
    """

    def __init__(self, ignore_filter=False):
        self.collections = {}
        self.ignore_filter = ignore_filter
        self.fail_on = None
        self.last_scroll = None
        self.payload_index_calls = []

    def _maybe_fail(self, operation):
        if self.fail_on == operation:
            raise RuntimeError(f"simulated qdrant failure during {operation}")

    def collection_exists(self, collection_name):
        self._maybe_fail("collection_exists")
        return collection_name in self.collections

    def create_collection(self, *, collection_name, vectors_config):
        self._maybe_fail("create_collection")
        self.collections[collection_name] = {
            "size": vectors_config.size,
            "distance": vectors_config.distance,
            "points": {},
            "payload_schema": {},
        }

    def get_collection(self, collection_name):
        self._maybe_fail("get_collection")
        coll = self.collections[collection_name]
        return types.SimpleNamespace(
            config=types.SimpleNamespace(
                params=types.SimpleNamespace(
                    vectors=types.SimpleNamespace(
                        size=coll["size"], distance=coll["distance"]))),
            payload_schema=dict(coll["payload_schema"]),
        )

    def upsert(self, *, collection_name, points, wait):
        self._maybe_fail("upsert")
        coll = self.collections[collection_name]
        for point in points:
            coll["points"][str(point.id)] = types.SimpleNamespace(
                id=point.id, vector=point.vector, payload=dict(point.payload))

    def create_payload_index(self, *, collection_name, field_name,
                             field_schema, wait=True):
        self._maybe_fail("create_payload_index")
        self.payload_index_calls.append((field_name, field_schema))
        self.collections[collection_name]["payload_schema"][field_name] = (
            types.SimpleNamespace(
                data_type=types.SimpleNamespace(value="text")))

    def scroll(self, *, collection_name, scroll_filter, limit,
               with_payload, with_vectors):
        self._maybe_fail("scroll")
        must = list(scroll_filter.must)
        self.last_scroll = types.SimpleNamespace(
            must=[
                (
                    condition.key,
                    getattr(condition.match, "text",
                            getattr(condition.match, "value", None)),
                )
                for condition in must
            ],
            limit=limit,
        )
        coll = self.collections[collection_name]
        selected = []
        for point in coll["points"].values():
            if not self.ignore_filter and not self._matches(
                    point.payload, must):
                continue
            selected.append(point)
        return (
            [
                types.SimpleNamespace(id=p.id, payload=dict(p.payload))
                for p in selected[:limit]
            ],
            None,
        )

    @staticmethod
    def _matches(payload, must):
        for condition in must:
            if isinstance(condition.match, qmodels.MatchText):
                if not _provider_prefix_match(
                        payload.get(condition.key, ""),
                        condition.match.text):
                    return False
                continue
            if payload.get(condition.key) != condition.match.value:
                return False
        return True


def make_index_record(**overrides):
    base = dict(
        tenant_id=TENANT_ID,
        chunk_id=CHUNK_1,
        document_id=DOC_A,
        chunk_index=0,
        content="Exporters must file Form NXP.",
        content_fingerprint="fp-1",
        source_id=SRC_A,
        source_type="guidance",
        source_location="https://example.test/guide",
        document_version="v1",
        embedding_model=MODEL,
        embedding_dimensions=DIMS,
        embedding_vector=[1.0, 0.0, 0.0, 0.0],
    )
    base.update(overrides)
    return base


class AdapterTestCase(unittest.TestCase):
    """Shared setup: Qdrant adapter over the filter-honoring fake."""

    def setUp(self) -> None:
        self.tenant = TENANT
        self.other = OTHER_TENANT
        self.client = FakeQdrantClient()
        self.config = VectorIndexConfig(
            collection_name="evidence_chunks_hybrid_test",
            embedding_model=MODEL,
            embedding_dimensions=DIMS,
            distance_metric="cosine",
        )
        self.index = QdrantEvidenceVectorIndex(self.client, self.config)

    def seed(self, record):
        return self.index.upsert(record, tenant_id=self.tenant)


class TestQdrantLexicalTranslation(AdapterTestCase):
    """Domain lexical semantics → provider filter → verified results."""

    def test_01_scroll_filter_has_tenant_scope_and_text(self) -> None:
        self.seed(make_index_record())
        self.index.find_lexical(
            ("form", "nxp"), tenant_id=self.tenant, top_k=5,
            scope=EvidenceRetrievalScope(source_id=SRC_A))
        must = self.client.last_scroll.must
        self.assertEqual(must[0], ("tenant_id", str(TENANT_ID)))
        self.assertEqual(must[1], ("source_id", SRC_A))
        self.assertEqual(must[2], ("content", "form nxp"))
        self.assertEqual(self.client.last_scroll.limit, 5)

    def test_02_content_text_index_provisioned_once(self) -> None:
        self.seed(make_index_record())
        self.index.find_lexical(("form",), tenant_id=self.tenant, top_k=5)
        self.index.find_lexical(("form",), tenant_id=self.tenant, top_k=5)
        self.assertEqual(len(self.client.payload_index_calls), 1)
        field_name, field_schema = self.client.payload_index_calls[0]
        self.assertEqual(field_name, "content")
        self.assertEqual(str(field_schema.type.value), "text")
        self.assertEqual(str(field_schema.tokenizer.value), "word")
        self.assertTrue(field_schema.lowercase)

    def test_03_provider_prefix_overmatch_is_narrowed(self) -> None:
        self.seed(make_index_record(content="Formx NXP required."))
        # provider prefix-matches "form" against "formx"; domain does not
        self.assertEqual(
            self.index.find_lexical(
                ("form",), tenant_id=self.tenant, top_k=5),
            [])
        self.assertEqual(
            len(self.index.find_lexical(
                ("nxp",), tenant_id=self.tenant, top_k=5)),
            1)

    def test_04_lexical_score_is_domain_term_occurrences(self) -> None:
        self.seed(make_index_record(content="Form NXP. Form NXP form."))
        results = self.index.find_lexical(
            ("form", "nxp"), tenant_id=self.tenant, top_k=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].score, 5.0)
        self.assertIsInstance(results[0], EvidenceRetrievalResult)

    def test_05_deterministic_ordering_relevance_then_chunk_id(
        self,
    ) -> None:
        self.seed(make_index_record(
            chunk_id=CHUNK_1, content="Form NXP.",
            content_fingerprint="fp-1"))
        self.seed(make_index_record(
            chunk_id=CHUNK_2, chunk_index=1, content="Form NXP form NXP.",
            content_fingerprint="fp-2"))
        results = self.index.find_lexical(
            ("form", "nxp"), tenant_id=self.tenant, top_k=5)
        self.assertEqual(
            [r.chunk_id for r in results], [CHUNK_2, CHUNK_1])
        self.assertEqual([r.score for r in results], [4.0, 2.0])

    def test_07_raw_qdrant_failure_translated(self) -> None:
        self.seed(make_index_record())
        self.client.fail_on = "scroll"
        with self.assertRaises(VectorStoreError) as ctx:
            self.index.find_lexical(
                ("form",), tenant_id=self.tenant, top_k=5)
        self.assertEqual(ctx.exception.operation, "find_lexical")
        self.assertIsInstance(ctx.exception.cause, RuntimeError)

    def test_08_tenant_and_scope_violations_fail_closed(self) -> None:
        client = FakeQdrantClient(ignore_filter=True)
        index = QdrantEvidenceVectorIndex(client, self.config)
        index.upsert(
            make_index_record(
                tenant_id=OTHER_TENANT_ID, chunk_id=CHUNK_5,
                document_id=DOC_B, content="Form NXP."),
            tenant_id=self.other)
        with self.assertRaises(VectorStoreError) as ctx:
            index.find_lexical(("form",), tenant_id=self.tenant, top_k=5)
        self.assertEqual(ctx.exception.operation, "find_lexical")
        self.assertIn("cross-tenant", str(ctx.exception.cause))

        client2 = FakeQdrantClient(ignore_filter=True)
        index2 = QdrantEvidenceVectorIndex(client2, self.config)
        index2.upsert(
            make_index_record(
                source_id=SRC_B, source_type="regulation",
                content="Form NXP."),
            tenant_id=self.tenant)
        with self.assertRaises(VectorStoreError) as scope_ctx:
            index2.find_lexical(
                ("form",), tenant_id=self.tenant, top_k=5,
                scope=EvidenceRetrievalScope(source_id=SRC_A))
        self.assertIn("scope", str(scope_ctx.exception.cause))

    def test_09_invalid_lexical_input_rejected(self) -> None:
        for bad in ((), ("Form",), ("nxp", "nxp"), ("n xp",), (7,),
                    "form", None, ["form", 7]):
            with self.assertRaises(DomainValidationError):
                self.index.find_lexical(
                    bad, tenant_id=self.tenant, top_k=5)
        for bad_top_k in (0, -1, True, "5"):
            with self.assertRaises(DomainValidationError):
                self.index.find_lexical(
                    ("form",), tenant_id=self.tenant, top_k=bad_top_k)
        for bad_tenant in (None, TENANT_ID):
            with self.assertRaises(DomainValidationError):
                self.index.find_lexical(
                    ("form",), tenant_id=bad_tenant, top_k=5)
        with self.assertRaises(DomainValidationError):
            self.index.find_lexical(
                ("form",), tenant_id=self.tenant, top_k=5,
                scope="not-a-scope")

    def test_10_malformed_payload_fails_closed(self) -> None:
        self.seed(make_index_record())
        point = self.client.collections[
            self.config.collection_name]["points"][str(CHUNK_1)]
        point.payload["source_type"] = "blog"
        with self.assertRaises(VectorStoreError) as ctx:
            self.index.find_lexical(
                ("form",), tenant_id=self.tenant, top_k=5)
        self.assertEqual(ctx.exception.operation, "find_lexical")
        # an empty stored content is rejected even when the provider
        # filter cannot exclude it
        client = FakeQdrantClient(ignore_filter=True)
        index = QdrantEvidenceVectorIndex(client, self.config)
        index.upsert(make_index_record(), tenant_id=self.tenant)
        client.collections[self.config.collection_name][
            "points"][str(CHUNK_1)].payload["content"] = ""
        with self.assertRaises(VectorStoreError) as empty_ctx:
            index.find_lexical(("form",), tenant_id=self.tenant, top_k=5)
        self.assertEqual(
            empty_ctx.exception.operation, "find_lexical")

    def test_11_provider_applies_tenant_and_scope_conditions(self) -> None:
        self.seed(make_index_record(
            chunk_id=CHUNK_1, content="Form NXP."))
        self.index.upsert(
            make_index_record(
                tenant_id=OTHER_TENANT_ID, chunk_id=CHUNK_5,
                document_id=DOC_B, content="Form NXP."),
            tenant_id=self.other)
        self.seed(make_index_record(
            chunk_id=CHUNK_2, chunk_index=1, source_id=SRC_B,
            source_type="regulation", content="Form NXP.",
            content_fingerprint="fp-2"))
        tenant_only = self.index.find_lexical(
            ("form",), tenant_id=self.tenant, top_k=10)
        self.assertEqual(
            [r.chunk_id for r in tenant_only], [CHUNK_1, CHUNK_2])
        scoped = self.index.find_lexical(
            ("form",), tenant_id=self.tenant, top_k=10,
            scope=EvidenceRetrievalScope(source_id=SRC_A))
        self.assertEqual([r.chunk_id for r in scoped], [CHUNK_1])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()