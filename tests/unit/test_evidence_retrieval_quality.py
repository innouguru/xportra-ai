"""Phase 5.2 — Retrieval Quality & Query Semantics tests.

Covers: query normalization, whitespace handling, invalid query
rejection, default/explicit top-k, query embedding invocation, embedding
configuration reuse, vector-to-index boundary, relevance-score ordering,
deterministic tie behavior, distinct document-version preservation,
duplicate/near-duplicate behavior, no-result behavior, tenant scope,
provider-type hiding, and fail-closed failure semantics (infrastructure
failures are never empty successful retrievals). Fakes only — no live
Qdrant server required.
"""

import unittest
from uuid import UUID

from xportra.domain.errors import DomainValidationError, VectorStoreError
from xportra.domain.evidence_indexing import EmbeddingModelConfig
from xportra.domain.evidence_retrieval import (
    DEFAULT_TOP_K,
    EvidenceRetrievalConfig,
    EvidenceRetrievalQuery,
    EvidenceRetrievalResult,
    EvidenceRetriever,
    VectorIndexEvidenceRetriever,
)
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TENANT = TenantContext(TENANT_ID)
OTHER_TENANT = TenantContext(OTHER_TENANT_ID)

DOC_V1 = UUID("11111111-1111-1111-1111-111111111111")
DOC_V2 = UUID("22222222-2222-2222-2222-222222222222")
DOC_OTHER = UUID("33333333-3333-3333-3333-333333333333")

CHUNK_1 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")
CHUNK_2 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2")
CHUNK_3 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3")
CHUNK_4 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa4")

MODEL = "test-embed-model"
DIMS = 4
EMBEDDING_CONFIG = EmbeddingModelConfig(
    model_identifier=MODEL, dimensions=DIMS)


def make_result(**overrides):
    base = dict(
        tenant_id=TENANT_ID,
        chunk_id=CHUNK_1,
        document_id=DOC_V1,
        chunk_index=0,
        content="Exporters must hold a valid certificate.",
        content_fingerprint="fp-cert",
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


class FakeProvider:
    """Deterministic embedding provider (protocol: ``embed(text)``)."""

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


class FakeIndex:
    """``EvidenceVectorIndex.find`` stand-in with controlled output.

    Returns results in the exact order supplied (an arbitrary /
    misbehaving provider), applies the top-k limit, and can fail or
    emit malformed output on demand.
    """

    def __init__(self, results=None, fail=False, raw_output=None):
        self.results = list(results or [])
        self.fail = fail
        self.raw_output = raw_output
        self.find_calls = []

    def find(self, query_vector, *, tenant_id, top_k, scope=None):
        self.find_calls.append((list(query_vector), tenant_id, top_k))
        if self.fail:
            raise RuntimeError("vector store down")
        if self.raw_output is not None:
            return self.raw_output
        return list(self.results[:top_k])


def make_service(index=None, provider=None, embedding_config=None):
    return VectorIndexEvidenceRetriever(
        vector_index=FakeIndex() if index is None else index,
        provider=FakeProvider() if provider is None else provider,
        embedding_config=(
            EMBEDDING_CONFIG if embedding_config is None
            else embedding_config),
    )


class TestQueryNormalization(unittest.TestCase):
    """Deterministic normalization only — never semantic rewriting."""

    def test_01_surrounding_whitespace_trimmed(self) -> None:
        query = EvidenceRetrievalQuery("   cocoa export rules   ")
        self.assertEqual(query.text, "cocoa export rules")

    def test_02_internal_whitespace_runs_collapsed(self) -> None:
        raw = "What   documents\tare\n\r required  for cocoa?"
        query = EvidenceRetrievalQuery(raw)
        self.assertEqual(query.text, "What documents are required for cocoa?")

    def test_03_case_punctuation_and_terminology_preserved(self) -> None:
        raw = 'What documents are required for exporting cocoa?\n' \
            ' (NAFDAC), WTO "quality" standards & phytosanitary-certificate.'
        expected = 'What documents are required for exporting cocoa? ' \
            '(NAFDAC), WTO "quality" standards & phytosanitary-certificate.'
        self.assertEqual(EvidenceRetrievalQuery(raw).text, expected)

    def test_04_normalization_applies_via_config_build_query(self) -> None:
        config = EvidenceRetrievalConfig()
        query = config.build_query("  Which   rules\tapply?  ")
        self.assertEqual(query.text, "Which rules apply?")
        self.assertEqual(query.top_k, DEFAULT_TOP_K)

    def test_05_normalized_text_is_what_gets_embedded(self) -> None:
        provider = FakeProvider()
        service = make_service(provider=provider)
        service.retrieve(
            EvidenceRetrievalQuery("  cocoa   export  rules  "),
            tenant_id=TENANT)
        self.assertEqual(provider.calls, ["cocoa export rules"])


class TestInvalidQueryRejection(unittest.TestCase):
    """Invalid information needs fail closed, at construction."""

    def test_01_empty_and_whitespace_only_rejected(self) -> None:
        for bad in ("", "   ", "\t\n", "\n \t\r\n"):
            with self.assertRaises(DomainValidationError):
                EvidenceRetrievalQuery(bad)
            with self.assertRaises(DomainValidationError):
                EvidenceRetrievalConfig().build_query(bad)

    def test_02_non_string_rejected(self) -> None:
        for bad in (None, 7, b"query", ["query"]):
            with self.assertRaises(DomainValidationError):
                EvidenceRetrievalQuery(bad)
            with self.assertRaises(DomainValidationError):
                EvidenceRetrievalConfig().build_query(bad)

    def test_03_retrieve_requires_query_object(self) -> None:
        provider = FakeProvider()
        service = make_service(provider=provider)
        for bad in ("raw text", {"text": "q"}, None, 7):
            with self.assertRaises(DomainValidationError):
                service.retrieve(bad, tenant_id=TENANT)
        self.assertEqual(provider.calls, [])


class TestRetrievalConfiguration(unittest.TestCase):
    """One configuration system; Phase 5.1 defaults are preserved."""

    def test_01_default_top_k_reuses_phase_51_constant(self) -> None:
        config = EvidenceRetrievalConfig()
        self.assertEqual(config.top_k, DEFAULT_TOP_K)
        self.assertEqual(DEFAULT_TOP_K, 5)
        self.assertEqual(
            EvidenceRetrievalQuery("q").top_k, config.top_k)

    def test_02_explicit_top_k_forwarded_to_index(self) -> None:
        config = EvidenceRetrievalConfig(top_k=1)
        index = FakeIndex(results=[
            make_result(chunk_id=CHUNK_1, score=0.9),
            make_result(chunk_id=CHUNK_2, score=0.5),
        ])
        service = make_service(index=index)
        results = service.retrieve(
            config.build_query("q"), tenant_id=TENANT)
        self.assertEqual(config.top_k, 1)
        self.assertEqual(index.find_calls[0][2], 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].chunk_id, CHUNK_1)

    def test_03_invalid_config_top_k_rejected(self) -> None:
        for bad in (0, -1, True, False, "5", 2.5, None):
            with self.assertRaises(DomainValidationError):
                EvidenceRetrievalConfig(top_k=bad)

    def test_04_config_carries_no_embedding_settings(self) -> None:
        self.assertEqual(
            set(EvidenceRetrievalConfig.__dataclass_fields__), {"top_k"})

    def test_05_tenant_not_duplicated_in_query_or_config(self) -> None:
        self.assertEqual(
            set(EvidenceRetrievalQuery.__dataclass_fields__),
            {"text", "top_k"})
        self.assertEqual(
            set(EvidenceRetrievalConfig.__dataclass_fields__), {"top_k"})


class TestEmbeddingBoundary(unittest.TestCase):
    """Information need → normalized query → provider → vector → find."""

    def test_01_embedding_provider_invoked_once_per_retrieve(self) -> None:
        provider = FakeProvider()
        service = make_service(provider=provider)
        service.retrieve(
            EvidenceRetrievalQuery("certificate rules"), tenant_id=TENANT)
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(provider.calls[0], "certificate rules")

    def test_02_vector_not_text_reaches_the_index(self) -> None:
        index = FakeIndex(results=[make_result()])
        service = make_service(index=index)
        service.retrieve(
            EvidenceRetrievalQuery("certificate rules"), tenant_id=TENANT)
        vector, _tenant, top_k = index.find_calls[0]
        self.assertEqual(vector, [1.0, 0.0, 0.0, 0.0])
        self.assertTrue(all(isinstance(v, float) for v in vector))
        self.assertNotIn("certificate", vector)

    def test_03_wrong_dimension_embedding_rejected_by_config(self) -> None:
        service = make_service(
            provider=FakeProvider(vector=[1.0, 0.0]),
            embedding_config=EMBEDDING_CONFIG)
        with self.assertRaises(DomainValidationError):
            service.retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT)

    def test_04_injected_embedding_config_governs_embedding(self) -> None:
        configured = EmbeddingModelConfig(
            model_identifier=MODEL, dimensions=DIMS)
        other = EmbeddingModelConfig(
            model_identifier="other-model", dimensions=DIMS + 4)
        provider = FakeProvider()  # emits DIMS-length vectors
        ok = make_service(provider=provider, embedding_config=configured)
        ok.retrieve(EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        mismatched = make_service(
            provider=provider, embedding_config=other)
        with self.assertRaises(DomainValidationError):
            mismatched.retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT)

    def test_05_retriever_requires_phase_43_embedding_config(self) -> None:
        for bad in (None, "config", {"dimensions": DIMS}):
            with self.assertRaises(DomainValidationError):
                VectorIndexEvidenceRetriever(
                    vector_index=FakeIndex(),
                    provider=FakeProvider(),
                    embedding_config=bad)


class TestOrderingContract(unittest.TestCase):
    """Descending score; ties deterministic; scores never modified."""

    def test_01_unsorted_provider_output_normalized_to_descending(
        self,
    ) -> None:
        index = FakeIndex(results=[
            make_result(chunk_id=CHUNK_1, score=0.4,
                        content_fingerprint="fp-1"),
            make_result(chunk_id=CHUNK_2, score=0.9,
                        content_fingerprint="fp-2"),
            make_result(chunk_id=CHUNK_3, score=0.7,
                        content_fingerprint="fp-3"),
        ])
        service = make_service(index=index)
        results = service.retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertEqual(
            [r.chunk_id for r in results],
            [CHUNK_2, CHUNK_3, CHUNK_1])
        self.assertEqual([r.score for r in results], [0.9, 0.7, 0.4])

    def test_02_ties_broken_by_chunk_id_regardless_of_provider_order(
        self,
    ) -> None:
        first_order = FakeIndex(results=[
            make_result(chunk_id=CHUNK_2, score=0.9,
                        content_fingerprint="fp-a"),
            make_result(chunk_id=CHUNK_1, score=0.9,
                        content_fingerprint="fp-b"),
        ])
        second_order = FakeIndex(results=[
            make_result(chunk_id=CHUNK_1, score=0.9,
                        content_fingerprint="fp-b"),
            make_result(chunk_id=CHUNK_2, score=0.9,
                        content_fingerprint="fp-a"),
        ])
        for index in (first_order, second_order):
            results = make_service(index=index).retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT)
            self.assertEqual(
                [r.chunk_id for r in results], [CHUNK_1, CHUNK_2])

    def test_03_scores_are_preserved_not_recomputed(self) -> None:
        index = FakeIndex(results=[
            make_result(chunk_id=CHUNK_1, score=0.123,
                        content_fingerprint="fp-x"),
            make_result(chunk_id=CHUNK_2, score=0.987,
                        content_fingerprint="fp-y"),
        ])
        results = make_service(index=index).retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertEqual([r.score for r in results], [0.987, 0.123])

    def test_04_ordering_deterministic_across_repeated_calls(self) -> None:
        index = FakeIndex(results=[
            make_result(chunk_id=CHUNK_3, score=0.5,
                        content_fingerprint="fp-3"),
            make_result(chunk_id=CHUNK_1, score=0.5,
                        content_fingerprint="fp-1"),
            make_result(chunk_id=CHUNK_2, score=0.9,
                        content_fingerprint="fp-2"),
        ])
        service = make_service(index=index)
        first = service.retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        second = service.retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertEqual(first, second)
        self.assertEqual(
            [r.chunk_id for r in first], [CHUNK_2, CHUNK_1, CHUNK_3])


class TestDuplicateAndVersionBehavior(unittest.TestCase):
    """Exact duplicates collapse; provenance-differing evidence never."""

    def test_01_same_document_same_fingerprint_collapsed(self) -> None:
        index = FakeIndex(results=[
            make_result(chunk_id=CHUNK_1, score=0.5),
            make_result(chunk_id=CHUNK_2, score=0.9),
        ])
        results = make_service(index=index).retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].chunk_id, CHUNK_2)
        self.assertEqual(results[0].score, 0.9)

    def test_02_best_ranked_duplicate_is_kept(self) -> None:
        index = FakeIndex(results=[
            make_result(chunk_id=CHUNK_1, score=0.2),
            make_result(chunk_id=CHUNK_2, score=0.9),
            make_result(chunk_id=CHUNK_3, score=0.5),
        ])
        results = make_service(index=index).retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].score, 0.9)

    def test_03_identical_text_from_different_documents_kept(self) -> None:
        index = FakeIndex(results=[
            make_result(chunk_id=CHUNK_1, document_id=DOC_V1, score=0.9),
            make_result(chunk_id=CHUNK_2, document_id=DOC_OTHER, score=0.8),
        ])
        results = make_service(index=index).retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertEqual(len(results), 2)
        self.assertEqual(
            {r.document_id for r in results}, {DOC_V1, DOC_OTHER})

    def test_04_distinct_document_versions_preserved(self) -> None:
        index = FakeIndex(results=[
            make_result(chunk_id=CHUNK_1, document_id=DOC_V1,
                        document_version="v1", score=0.9),
            make_result(chunk_id=CHUNK_2, document_id=DOC_V2,
                        document_version="v2", score=0.8),
        ])
        results = make_service(index=index).retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertEqual(len(results), 2)
        self.assertEqual(
            {r.document_version for r in results}, {"v1", "v2"})
        self.assertEqual({r.source_id for r in results},
                         {"sonsa/cert-guide"})

    def test_05_near_duplicates_kept_no_heuristic_collapse(self) -> None:
        index = FakeIndex(results=[
            make_result(chunk_id=CHUNK_1, score=0.9,
                        content="Hold a certificate.",
                        content_fingerprint="fp-cert"),
            make_result(chunk_id=CHUNK_2, score=0.8,
                        content="Hold a certificate now.",
                        content_fingerprint="fp-cert-near"),
        ])
        results = make_service(index=index).retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertEqual(len(results), 2)

    def test_06_collapse_may_yield_fewer_than_top_k(self) -> None:
        index = FakeIndex(results=[
            make_result(chunk_id=CHUNK_1, score=0.9),
            make_result(chunk_id=CHUNK_2, score=0.8),
            make_result(chunk_id=CHUNK_3, document_id=DOC_OTHER,
                        score=0.7),
        ])
        results = make_service(index=index).retrieve(
            EvidenceRetrievalConfig(top_k=3).build_query("q"),
            tenant_id=TENANT)
        self.assertEqual(len(results), 2)
        self.assertEqual(
            [r.document_id for r in results], [DOC_V1, DOC_OTHER])


class TestNoResultAndTenantScope(unittest.TestCase):
    """Empty means "no evidence"; tenant scope stays enforced."""

    def test_01_no_results_returns_empty_list(self) -> None:
        results = make_service().retrieve(
            EvidenceRetrievalQuery("nothing matches"), tenant_id=TENANT)
        self.assertEqual(results, [])

    def test_02_tenant_context_forwarded_to_find(self) -> None:
        index = FakeIndex(results=[make_result()])
        make_service(index=index).retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertEqual(index.find_calls[0][1], TENANT)

    def test_03_cross_tenant_result_fails_closed_not_empty(self) -> None:
        index = FakeIndex(results=[
            make_result(tenant_id=OTHER_TENANT_ID, score=0.9),
        ])
        with self.assertRaises(VectorStoreError) as ctx:
            make_service(index=index).retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertEqual(ctx.exception.operation, "evidence retrieval")
        self.assertIn("cross-tenant", str(ctx.exception.cause))

    def test_04_missing_tenant_context_rejected(self) -> None:
        service = make_service(index=FakeIndex(results=[make_result()]))
        for bad in (None, TENANT_ID, "tenant"):
            with self.assertRaises(DomainValidationError):
                service.retrieve(
                    EvidenceRetrievalQuery("q"), tenant_id=bad)


class TestProviderBoundaryHidden(unittest.TestCase):
    """Qdrant/provider concepts never surface above the adapter."""

    def test_01_domain_module_source_has_no_qdrant_import(self) -> None:
        import xportra.domain.evidence_retrieval as retrieval_mod
        source = open(retrieval_mod.__file__, encoding="utf-8").read()
        self.assertNotIn("qdrant_client", source)
        self.assertNotIn("qmodels", source)

    def test_02_results_are_domain_objects(self) -> None:
        index = FakeIndex(results=[make_result()])
        results = make_service(index=index).retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertIsInstance(results[0], EvidenceRetrievalResult)
        self.assertTrue(type(results[0]).__module__.startswith("xportra"))

    def test_03_domain_protocol_usable_without_adapter(self) -> None:
        service = make_service(index=FakeIndex(results=[make_result()]))
        self.assertIsInstance(service, EvidenceRetriever)
        self.assertIsInstance(service.retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT)[0],
            EvidenceRetrievalResult)


class TestFailureSemantics(unittest.TestCase):
    """Infrastructure failures raise — never an empty successful result."""

    def test_01_embedding_failure_raises_not_empty(self) -> None:
        failing = make_service(provider=FakeProvider(fail=True))
        with self.assertRaises(DomainValidationError) as ctx:
            failing.retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertIn("embedding provider failed", str(ctx.exception))
        # genuine "no evidence found" remains a distinct empty success
        self.assertEqual(
            make_service().retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT),
            [])

    def test_02_index_failure_raises_not_empty(self) -> None:
        failing = make_service(index=FakeIndex(fail=True))
        with self.assertRaises(VectorStoreError) as ctx:
            failing.retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertEqual(ctx.exception.operation, "evidence retrieval")
        self.assertIsInstance(ctx.exception.cause, RuntimeError)
        self.assertIn("vector store down", str(ctx.exception.cause))
        self.assertEqual(
            make_service().retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT),
            [])

    def test_03_malformed_container_raises_not_empty(self) -> None:
        broken = make_service(index=FakeIndex(raw_output={"oops": 1}))
        with self.assertRaises(DomainValidationError):
            broken.retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT)

    def test_04_malformed_result_item_raises_not_empty(self) -> None:
        broken = make_service(index=FakeIndex(results=["not-a-result"]))
        with self.assertRaises(DomainValidationError):
            broken.retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT)

    def test_05_invalid_configuration_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            EvidenceRetrievalConfig(top_k=0)
        with self.assertRaises(DomainValidationError):
            VectorIndexEvidenceRetriever(
                vector_index=FakeIndex(),
                provider=FakeProvider(),
                embedding_config="not-a-config")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()