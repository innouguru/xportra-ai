"""Phase 5.1 — Evidence Retrieval Boundary tests.

Unit tests use fakes for the embedding provider / vector index and an
in-memory fake Qdrant client; no running Qdrant server is required.
Covers: successful retrieval, top-k behavior, empty/no-result retrieval,
tenant isolation, invalid query handling, invalid top-k handling,
provenance preservation, document/version metadata, provider-response
translation, and retrieval through the domain abstraction.
"""

import dataclasses
import math
import types
import unittest
from uuid import UUID

from xportra.domain.errors import DomainValidationError, VectorStoreError
from xportra.domain.evidence_indexing import EmbeddingModelConfig
from xportra.domain.evidence_retrieval import (
    DEFAULT_TOP_K,
    EvidenceRetrievalQuery,
    EvidenceRetrievalResult,
    EvidenceRetriever,
    VectorIndexEvidenceRetriever,
)
from xportra.domain.vector_index import EvidenceVectorIndex, VectorIndexConfig
from xportra.infrastructure.vector_index import QdrantEvidenceVectorIndex
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TENANT = TenantContext(TENANT_ID)
OTHER_TENANT = TenantContext(OTHER_TENANT_ID)

CHUNK_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
CHUNK_ID_2 = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
OTHER_CHUNK_ID = UUID("33333333-3333-3333-3333-333333333333")
DOC_ID = UUID("11111111-1111-1111-1111-111111111111")
DOC_ID_2 = UUID("22222222-2222-2222-2222-222222222222")

COLLECTION = "evidence_chunks_retrieval_test"
DIMS = 4
MODEL = "test-embed-model"
EMBEDDING_CONFIG = EmbeddingModelConfig(model_identifier=MODEL, dimensions=DIMS)

BASE_RESULT = dict(
    tenant_id=TENANT_ID,
    chunk_id=CHUNK_ID,
    document_id=DOC_ID,
    chunk_index=0,
    content="Exporters must hold a valid phytosanitary certificate.",
    content_fingerprint="fp-abc",
    source_id="sonsa/phito-guide",
    source_type="guidance",
    source_location="https://example.test/guide",
    document_version="v1",
    embedding_model=MODEL,
    embedding_dimensions=DIMS,
    score=0.9,
)


def make_result(**overrides):
    fields = dict(BASE_RESULT)
    fields.update(overrides)
    return EvidenceRetrievalResult(**fields)


def base_record(**overrides):
    record = dict(BASE_RESULT)
    record.update(overrides)
    return record


def cosine(a, b):
    num = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return num / (na * nb)


def seed_entries():
    """Two tenant-A chunks plus one tenant-B look-alike (same direction).

    Fingerprints differ for differing content, matching the Phase 4
    invariant that ``content_fingerprint = sha256(content)``.
    """
    a_best = make_result(
        chunk_id=CHUNK_ID, chunk_index=0, content="certificate rules",
        score=0.0)
    a_second = make_result(
        chunk_id=CHUNK_ID_2, chunk_index=1, content="inspection rules",
        content_fingerprint="fp-inspection-rules",
        score=0.0)
    b_twin = make_result(
        tenant_id=OTHER_TENANT_ID, chunk_id=OTHER_CHUNK_ID,
        document_id=DOC_ID_2, content="certificate rules", score=0.0)
    return [
        ([1.0, 0.0, 0.0, 0.0], a_best),
        ([0.0, 1.0, 0.0, 0.0], a_second),
        ([1.0, 0.0, 0.0, 0.0], b_twin),
    ]


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


class FakeVectorIndex:
    """In-memory ``EvidenceVectorIndex.find`` stand-in (tenant-filtered)."""

    def __init__(self, entries=None, fail=False, ignore_tenant=False,
                 return_raw=False, limit_honored=True):
        self.entries = list(entries or [])
        self.fail = fail
        self.ignore_tenant = ignore_tenant
        self.return_raw = return_raw
        self.limit_honored = limit_honored
        self.find_calls = []

    def find(self, query_vector, *, tenant_id, top_k, scope=None):
        self.find_calls.append((list(query_vector), tenant_id, top_k))
        if self.fail:
            raise RuntimeError("vector store down")
        matches = []
        for vector, result in self.entries:
            if (not self.ignore_tenant
                    and result.tenant_id != tenant_id.tenant_id):
                continue
            matches.append((cosine(query_vector, vector), result))
        matches.sort(key=lambda item: (-item[0], str(item[1].chunk_id)))
        selected = matches if not self.limit_honored else matches[:top_k]
        if self.return_raw:
            return [result.to_record() for _, result in selected]
        return [dataclasses.replace(result, score=score)
                for score, result in selected]


class FakeQdrantClient:
    """In-memory Qdrant stand-in implementing only the methods used."""

    def __init__(self, ignore_filter=False):
        self.collections = {}
        self.ignore_filter = ignore_filter
        self.fail_on = None
        self.last_query = None

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
        }

    def get_collection(self, collection_name):
        self._maybe_fail("get_collection")
        coll = self.collections[collection_name]
        return types.SimpleNamespace(
            config=types.SimpleNamespace(
                params=types.SimpleNamespace(
                    vectors=types.SimpleNamespace(
                        size=coll["size"], distance=coll["distance"])))
        )

    def upsert(self, *, collection_name, points, wait):
        self._maybe_fail("upsert")
        coll = self.collections[collection_name]
        for point in points:
            coll["points"][str(point.id)] = types.SimpleNamespace(
                id=point.id, vector=point.vector, payload=dict(point.payload))

    def query_points(self, *, collection_name, query, limit, query_filter,
                     with_payload, with_vectors):
        self._maybe_fail("query_points")
        tenant_value = None
        for condition in query_filter.must:
            tenant_value = condition.match.value
        self.last_query = types.SimpleNamespace(
            collection_name=collection_name, query=list(query), limit=limit,
            tenant_filter=tenant_value)
        coll = self.collections[collection_name]
        scored = []
        for point in coll["points"].values():
            if not self.ignore_filter and (
                    point.payload.get("tenant_id") != tenant_value):
                continue
            scored.append((cosine(query, point.vector), point))
        scored.sort(key=lambda item: (-item[0], str(item[1].id)))
        return types.SimpleNamespace(points=[
            types.SimpleNamespace(
                id=point.id, score=score, payload=dict(point.payload))
            for score, point in scored[:limit]
        ])


def make_index_record(**overrides):
    base = dict(
        tenant_id=TENANT_ID,
        chunk_id=CHUNK_ID,
        document_id=DOC_ID,
        chunk_index=0,
        content="Exporters must hold a valid phytosanitary certificate.",
        content_fingerprint="fp-abc",
        source_id="sonsa/phito-guide",
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
    """Shared setup: Qdrant adapter over the in-memory fake client."""

    def setUp(self) -> None:
        self.tenant = TENANT
        self.other = OTHER_TENANT
        self.client = FakeQdrantClient()
        self.config = VectorIndexConfig(
            collection_name=COLLECTION,
            embedding_model=MODEL,
            embedding_dimensions=DIMS,
            distance_metric="cosine",
        )
        self.index = QdrantEvidenceVectorIndex(self.client, self.config)

    def seed(self, record):
        return self.index.upsert(record, tenant_id=self.tenant)


def make_service(index=None, provider=None, config=None):
    return VectorIndexEvidenceRetriever(
        vector_index=FakeVectorIndex() if index is None else index,
        provider=FakeProvider() if provider is None else provider,
        embedding_config=EMBEDDING_CONFIG if config is None else config,
    )


class TestEvidenceRetrievalQuery(unittest.TestCase):
    """Query value-object validation (empty query / invalid top-k)."""

    def test_01_valid_query_accepted_and_stripped(self) -> None:
        query = EvidenceRetrievalQuery("  cocoa export rules  ")
        self.assertEqual(query.text, "cocoa export rules")
        self.assertEqual(query.top_k, DEFAULT_TOP_K)
        self.assertEqual(DEFAULT_TOP_K, 5)

    def test_02_explicit_top_k_preserved(self) -> None:
        self.assertEqual(
            EvidenceRetrievalQuery("q", top_k=3).top_k, 3)

    def test_03_empty_text_rejected(self) -> None:
        for bad in ("", "   ", "\t\n"):
            with self.assertRaises(DomainValidationError):
                EvidenceRetrievalQuery(bad)

    def test_04_non_string_text_rejected(self) -> None:
        for bad in (None, 7, b"x", ["q"]):
            with self.assertRaises(DomainValidationError):
                EvidenceRetrievalQuery(bad)

    def test_05_invalid_top_k_rejected(self) -> None:
        for bad in (0, -1, True, False, "5", 2.5, None):
            with self.assertRaises(DomainValidationError):
                EvidenceRetrievalQuery("q", top_k=bad)

    def test_06_positive_top_k_accepted(self) -> None:
        for good in (1, 5, 100):
            self.assertEqual(
                EvidenceRetrievalQuery("q", top_k=good).top_k, good)

    def test_07_query_is_immutable(self) -> None:
        query = EvidenceRetrievalQuery("q")
        with self.assertRaises(dataclasses.FrozenInstanceError):
            query.text = "other"


class TestEvidenceRetrievalResultModel(unittest.TestCase):
    """Explicit retrieval-result domain model (fail closed)."""

    def test_01_from_record_valid_types(self) -> None:
        result = EvidenceRetrievalResult.from_record(base_record())
        self.assertIsInstance(result, EvidenceRetrievalResult)
        self.assertIsInstance(result.tenant_id, UUID)
        self.assertIsInstance(result.chunk_id, UUID)
        self.assertIsInstance(result.document_id, UUID)
        self.assertIsInstance(result.score, float)

    def test_02_roundtrip_preserves_all_fields(self) -> None:
        original = make_result(score=0.42)
        record = original.to_record()
        self.assertEqual(len(record), 13)
        self.assertEqual(
            EvidenceRetrievalResult.from_record(record), original)

    def test_03_invalid_score_rejected(self) -> None:
        for bad in (None, "0.9", True, float("nan"), float("inf")):
            with self.assertRaises(DomainValidationError):
                EvidenceRetrievalResult.from_record(base_record(score=bad))

    def test_04_malformed_identity_rejected(self) -> None:
        for bad in (None, "not-a-uuid", 7):
            with self.assertRaises(DomainValidationError):
                EvidenceRetrievalResult.from_record(
                    base_record(chunk_id=bad))
            with self.assertRaises(DomainValidationError):
                EvidenceRetrievalResult.from_record(
                    base_record(tenant_id=bad))
            with self.assertRaises(DomainValidationError):
                EvidenceRetrievalResult.from_record(
                    base_record(document_id=bad))
        with self.assertRaises(DomainValidationError):
            EvidenceRetrievalResult.from_record("not-a-dict")

    def test_05_invalid_provenance_fields_rejected(self) -> None:
        bad_fields = {
            "source_type": "blog",
            "content": "",
            "content_fingerprint": "",
            "source_id": "",
            "chunk_index": -1,
            "embedding_model": "",
            "embedding_dimensions": 0,
            "document_version": 7,
            "source_location": 7,
        }
        for field, value in bad_fields.items():
            with self.assertRaises(DomainValidationError):
                EvidenceRetrievalResult.from_record(
                    base_record(**{field: value}))


class TestSuccessfulRetrieval(unittest.TestCase):
    """Successful retrieval through the domain service."""

    def setUp(self) -> None:
        self.index = FakeVectorIndex(entries=seed_entries())
        self.provider = FakeProvider()
        self.service = make_service(index=self.index, provider=self.provider)

    def test_01_successful_retrieval(self) -> None:
        results = self.service.retrieve(
            EvidenceRetrievalQuery("certificate"), tenant_id=TENANT)
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], EvidenceRetrievalResult)
        self.assertEqual(results[0].chunk_id, CHUNK_ID)
        self.assertEqual(results[0].content, "certificate rules")

    def test_02_provider_and_index_receive_expected_arguments(self) -> None:
        self.service.retrieve(
            EvidenceRetrievalQuery("certificate", top_k=1),
            tenant_id=TENANT)
        self.assertEqual(self.provider.calls, ["certificate"])
        vector, tenant, top_k = self.index.find_calls[0]
        self.assertEqual(vector, [1.0, 0.0, 0.0, 0.0])
        self.assertEqual(tenant, TENANT)
        self.assertEqual(top_k, 1)

    def test_03_results_ranked_best_first_with_finite_scores(self) -> None:
        results = self.service.retrieve(
            EvidenceRetrievalQuery("certificate"), tenant_id=TENANT)
        scores = [r.score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))
        for score in scores:
            self.assertTrue(math.isfinite(score))
        self.assertAlmostEqual(results[0].score, 1.0)

    def test_04_service_satisfies_evidence_retriever_protocol(self) -> None:
        self.assertIsInstance(self.service, EvidenceRetriever)


class TestTopKBehavior(unittest.TestCase):
    """Configurable top-k semantics."""

    def setUp(self) -> None:
        self.index = FakeVectorIndex(entries=seed_entries())
        self.service = make_service(index=self.index)

    def test_01_top_k_one_returns_single_best(self) -> None:
        results = self.service.retrieve(
            EvidenceRetrievalQuery("certificate", top_k=1),
            tenant_id=TENANT)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].chunk_id, CHUNK_ID)

    def test_02_top_k_forwarded_to_index(self) -> None:
        self.service.retrieve(
            EvidenceRetrievalQuery("q", top_k=2), tenant_id=TENANT)
        self.assertEqual(self.index.find_calls[0][2], 2)

    def test_03_top_k_larger_than_available_returns_all(self) -> None:
        results = self.service.retrieve(
            EvidenceRetrievalQuery("certificate", top_k=50),
            tenant_id=TENANT)
        self.assertEqual(len(results), 2)

    def test_04_default_top_k_used_when_unspecified(self) -> None:
        self.service.retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertEqual(self.index.find_calls[0][2], DEFAULT_TOP_K)

    def test_05_index_returning_more_than_top_k_fails_closed(self) -> None:
        index = FakeVectorIndex(entries=seed_entries(), limit_honored=False)
        service = make_service(index=index)
        with self.assertRaises(DomainValidationError):
            service.retrieve(
                EvidenceRetrievalQuery("certificate", top_k=1),
                tenant_id=TENANT)


class TestEmptyResults(AdapterTestCase):
    """Empty/no-result retrieval is a normal, deterministic outcome."""

    def test_01_no_matching_evidence_returns_empty(self) -> None:
        entries = [e for e in seed_entries()
                   if e[1].tenant_id == OTHER_TENANT_ID]
        service = make_service(index=FakeVectorIndex(entries=entries))
        self.assertEqual(
            service.retrieve(
                EvidenceRetrievalQuery("certificate"), tenant_id=TENANT),
            [])

    def test_02_empty_index_returns_empty(self) -> None:
        service = make_service()
        self.assertEqual(
            service.retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT),
            [])

    def test_03_nonexistent_tenant_returns_empty_from_adapter(self) -> None:
        self.seed(make_index_record())
        results = self.index.find(
            [1.0, 0.0, 0.0, 0.0], tenant_id=self.other, top_k=5)
        self.assertEqual(results, [])

    def test_04_missing_collection_returns_empty_from_adapter(self) -> None:
        results = self.index.find(
            [1.0, 0.0, 0.0, 0.0], tenant_id=self.tenant, top_k=5)
        self.assertEqual(results, [])


class TestTenantIsolation(AdapterTestCase):
    """Cross-tenant retrieval cannot occur at any layer."""

    def test_01_tenant_a_never_sees_tenant_b(self) -> None:
        service = make_service(index=FakeVectorIndex(entries=seed_entries()))
        results_a = service.retrieve(
            EvidenceRetrievalQuery("certificate"), tenant_id=TENANT)
        self.assertEqual(len(results_a), 2)
        self.assertTrue(
            all(r.tenant_id == TENANT_ID for r in results_a))
        results_b = service.retrieve(
            EvidenceRetrievalQuery("certificate"), tenant_id=OTHER_TENANT)
        self.assertEqual(len(results_b), 1)
        self.assertTrue(
            all(r.tenant_id == OTHER_TENANT_ID for r in results_b))

    def test_02_cross_tenant_result_from_index_fails_closed(self) -> None:
        service = make_service(
            index=FakeVectorIndex(entries=seed_entries(),
                                  ignore_tenant=True))
        with self.assertRaises(VectorStoreError) as ctx:
            service.retrieve(
                EvidenceRetrievalQuery("certificate"), tenant_id=TENANT)
        self.assertEqual(ctx.exception.operation, "evidence retrieval")
        self.assertIn("cross-tenant", str(ctx.exception.cause))

    def test_03_invalid_tenant_context_rejected(self) -> None:
        service = make_service(index=FakeVectorIndex(entries=seed_entries()))
        for bad in (None, TENANT_ID, "not-a-tenant", "aaaaaaaa"):
            with self.assertRaises(DomainValidationError):
                service.retrieve(
                    EvidenceRetrievalQuery("q"), tenant_id=bad)

    def test_04_adapter_applies_mandatory_tenant_filter(self) -> None:
        self.seed(make_index_record())
        self.index.upsert(
            make_index_record(
                tenant_id=OTHER_TENANT_ID,
                chunk_id=OTHER_CHUNK_ID,
                document_id=DOC_ID_2),
            tenant_id=self.other)
        results = self.index.find(
            [1.0, 0.0, 0.0, 0.0], tenant_id=self.tenant, top_k=10)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].tenant_id, TENANT_ID)
        self.assertEqual(results[0].chunk_id, CHUNK_ID)
        self.assertEqual(
            self.client.last_query.tenant_filter, str(TENANT_ID))

    def test_05_adapter_fails_closed_despite_broken_provider_filter(
        self,
    ) -> None:
        client = FakeQdrantClient(ignore_filter=True)
        index = QdrantEvidenceVectorIndex(client, self.config)
        index.upsert(
            make_index_record(
                tenant_id=OTHER_TENANT_ID,
                chunk_id=OTHER_CHUNK_ID,
                document_id=DOC_ID_2),
            tenant_id=self.other)
        with self.assertRaises(VectorStoreError) as ctx:
            index.find(
                [1.0, 0.0, 0.0, 0.0], tenant_id=self.tenant, top_k=5)
        self.assertEqual(ctx.exception.operation, "find")
        self.assertIn("cross-tenant", str(ctx.exception.cause))


class TestInvalidQueryHandling(unittest.TestCase):
    """Invalid queries and provider/index failures fail closed."""

    def setUp(self) -> None:
        self.index = FakeVectorIndex(entries=seed_entries())
        self.service = make_service(index=self.index)

    def test_01_retrieve_requires_query_object(self) -> None:
        for bad in ("certificate", {"text": "q"}, None, 7):
            with self.assertRaises(DomainValidationError):
                self.service.retrieve(bad, tenant_id=TENANT)
        self.assertEqual(len(self.index.find_calls), 0)

    def test_02_provider_failure_fails_closed(self) -> None:
        index = FakeVectorIndex(entries=seed_entries())
        service = make_service(index=index, provider=FakeProvider(fail=True))
        with self.assertRaises(DomainValidationError) as ctx:
            service.retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertIn("embedding provider failed", str(ctx.exception))
        self.assertEqual(len(index.find_calls), 0)

    def test_03_wrong_dimension_provider_output_rejected(self) -> None:
        service = make_service(
            index=self.index, provider=FakeProvider(vector=[1.0, 0.0]))
        with self.assertRaises(DomainValidationError):
            service.retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertEqual(len(self.index.find_calls), 0)

    def test_04_index_failure_translated_to_vector_store_error(self) -> None:
        service = make_service(index=FakeVectorIndex(fail=True))
        with self.assertRaises(VectorStoreError) as ctx:
            service.retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertEqual(ctx.exception.operation, "evidence retrieval")
        self.assertIsInstance(ctx.exception.cause, RuntimeError)
        self.assertIn("vector store down", str(ctx.exception.cause))

    def test_05_index_returning_raw_dicts_fails_closed(self) -> None:
        service = make_service(
            index=FakeVectorIndex(entries=seed_entries(), return_raw=True))
        with self.assertRaises(DomainValidationError):
            service.retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT)


class TestInvalidTopKHandling(AdapterTestCase):
    """The adapter independently rejects invalid top-k and query vectors."""

    def test_01_invalid_top_k_rejected(self) -> None:
        for bad in (0, -1, True, False, "5", 2.5, None):
            with self.assertRaises(DomainValidationError):
                self.index.find(
                    [1.0, 0.0, 0.0, 0.0],
                    tenant_id=self.tenant,
                    top_k=bad)

    def test_02_malformed_query_vector_rejected(self) -> None:
        for bad in ("vector", b"vector", [], None, ["a", "b", "c", "d"],
                    [0.1, 0.2], [float("nan"), 0.0, 0.0, 0.0],
                    [float("inf"), 0.0, 0.0, 0.0], [True, 0, 0, 0]):
            with self.assertRaises(DomainValidationError):
                self.index.find(bad, tenant_id=self.tenant, top_k=5)

    def test_03_invalid_tenant_context_rejected(self) -> None:
        for bad in (None, TENANT_ID, "not-a-tenant"):
            with self.assertRaises(DomainValidationError):
                self.index.find(
                    [1.0, 0.0, 0.0, 0.0], tenant_id=bad, top_k=5)


class TestProvenancePreservation(AdapterTestCase):
    """Results retain full Phase 4 provenance — never text + score alone."""

    PROVENANCE_FIELDS = (
        "tenant_id", "chunk_id", "document_id", "chunk_index",
        "content", "content_fingerprint", "source_id", "source_type",
        "source_location", "document_version", "embedding_model",
        "embedding_dimensions", "score",
    )

    def test_01_provenance_preserved_through_domain_retrieval(self) -> None:
        service = make_service(index=FakeVectorIndex(entries=seed_entries()))
        results = service.retrieve(
            EvidenceRetrievalQuery("certificate"), tenant_id=TENANT)
        best = results[0]
        self.assertEqual(best.tenant_id, TENANT_ID)
        self.assertEqual(best.chunk_id, CHUNK_ID)
        self.assertEqual(best.document_id, DOC_ID)
        self.assertEqual(best.chunk_index, 0)
        self.assertEqual(best.content_fingerprint, "fp-abc")
        self.assertEqual(best.source_id, "sonsa/phito-guide")
        self.assertEqual(best.source_type, "guidance")
        self.assertEqual(best.source_location, "https://example.test/guide")
        self.assertEqual(best.embedding_model, MODEL)
        self.assertEqual(best.embedding_dimensions, DIMS)

    def test_02_result_is_more_than_text_and_score(self) -> None:
        results = make_service(
            index=FakeVectorIndex(entries=seed_entries())).retrieve(
                EvidenceRetrievalQuery("certificate"), tenant_id=TENANT)
        record = results[0].to_record()
        self.assertEqual(len(record), 13)
        for field in self.PROVENANCE_FIELDS:
            self.assertIn(field, record)

    def test_03_adapter_roundtrip_preserves_provenance(self) -> None:
        record = make_index_record()
        self.seed(record)
        results = self.index.find(
            [1.0, 0.0, 0.0, 0.0], tenant_id=self.tenant, top_k=5)
        result = results[0]
        for field in self.PROVENANCE_FIELDS:
            if field == "score":
                continue
            self.assertEqual(getattr(result, field), record[field])


class TestDocumentVersionMetadata(AdapterTestCase):
    """Document/version metadata required for provenance is preserved."""

    def test_01_document_version_preserved_through_retrieval(self) -> None:
        service = make_service(index=FakeVectorIndex(entries=seed_entries()))
        results = service.retrieve(
            EvidenceRetrievalQuery("certificate"), tenant_id=TENANT)
        self.assertTrue(results)
        for result in results:
            self.assertEqual(result.document_version, "v1")

    def test_02_versions_distinguishable_in_adapter(self) -> None:
        self.seed(make_index_record())
        self.seed(make_index_record(
            chunk_id=CHUNK_ID_2, chunk_index=1, document_version="v2"))
        results = self.index.find(
            [1.0, 0.0, 0.0, 0.0], tenant_id=self.tenant, top_k=10)
        self.assertEqual(len(results), 2)
        self.assertEqual(
            {r.document_version for r in results}, {"v1", "v2"})
        self.assertNotEqual(results[0].chunk_id, results[1].chunk_id)


class TestProviderResponseTranslation(AdapterTestCase):
    """Qdrant response → domain EvidenceRetrievalResult translation."""

    def test_01_translated_to_domain_types(self) -> None:
        self.seed(make_index_record())
        results = self.index.find(
            [1.0, 0.0, 0.0, 0.0], tenant_id=self.tenant, top_k=5)
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertIsInstance(result, EvidenceRetrievalResult)
        self.assertTrue(type(result).__module__.startswith("xportra"))
        self.assertIsInstance(result.score, float)
        self.assertIsInstance(result.tenant_id, UUID)
        self.assertIsInstance(result.chunk_id, UUID)
        self.assertIsInstance(result.document_id, UUID)
        self.assertNotIn(
            "embedding_vector", result.to_record())

    def test_02_results_ordered_best_score_first(self) -> None:
        self.seed(make_index_record(embedding_vector=[1.0, 0.0, 0.0, 0.0]))
        self.seed(make_index_record(
            chunk_id=CHUNK_ID_2, chunk_index=1,
            embedding_vector=[0.6, 0.8, 0.0, 0.0]))
        self.seed(make_index_record(
            chunk_id=OTHER_CHUNK_ID, chunk_index=2,
            embedding_vector=[0.0, 1.0, 0.0, 0.0]))
        results = self.index.find(
            [1.0, 0.0, 0.0, 0.0], tenant_id=self.tenant, top_k=10)
        self.assertEqual(len(results), 3)
        scores = [r.score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(len(set(scores)), 3)
        self.assertEqual(results[0].chunk_id, CHUNK_ID)

    def test_03_malformed_persisted_payload_fails_closed(self) -> None:
        self.seed(make_index_record())
        point = self.client.collections[COLLECTION]["points"][
            str(CHUNK_ID)]
        point.payload.pop("content")
        with self.assertRaises(VectorStoreError) as ctx:
            self.index.find(
                [1.0, 0.0, 0.0, 0.0], tenant_id=self.tenant, top_k=5)
        self.assertEqual(ctx.exception.operation, "find")

    def test_04_raw_qdrant_failure_never_escapes(self) -> None:
        self.seed(make_index_record())
        self.client.fail_on = "query_points"
        with self.assertRaises(VectorStoreError) as ctx:
            self.index.find(
                [1.0, 0.0, 0.0, 0.0], tenant_id=self.tenant, top_k=5)
        self.assertEqual(ctx.exception.operation, "find")
        self.assertIsInstance(ctx.exception.cause, RuntimeError)
        self.assertIn("simulated qdrant failure", str(ctx.exception.cause))


class TestDomainAbstraction(unittest.TestCase):
    """Callers use the domain contract — never Qdrant directly."""

    def test_01_domain_modules_have_no_qdrant_imports(self) -> None:
        import xportra.domain.evidence_retrieval as retrieval_mod
        import xportra.domain.vector_index as index_mod
        for module in (retrieval_mod, index_mod):
            source = open(module.__file__, encoding="utf-8").read()
            self.assertNotIn("qdrant_client", source)

    def test_02_protocols_expose_retrieval_operations(self) -> None:
        index_methods = set(EvidenceVectorIndex.__protocol_attrs__)
        self.assertEqual(
            index_methods,
            {"upsert", "get", "delete", "count", "find"},
        )
        self.assertEqual(
            set(EvidenceRetriever.__protocol_attrs__), {"retrieve"})

    def test_03_retrieval_through_protocol_abstraction(self) -> None:
        # application-style: typed against the domain contract only;
        # the fake index proves no Qdrant type is involved
        retriever: EvidenceRetriever = make_service(
            index=FakeVectorIndex(entries=seed_entries()))
        results = retriever.retrieve(
            EvidenceRetrievalQuery("certificate"), tenant_id=TENANT)
        self.assertEqual(len(results), 2)
        self.assertIsInstance(results[0], EvidenceRetrievalResult)


class TestDeterminism(unittest.TestCase):
    """Identical tenant + query + configuration → identical results."""

    def setUp(self) -> None:
        self.index = FakeVectorIndex(entries=seed_entries())
        self.service = make_service(index=self.index)

    def test_01_identical_requests_return_identical_results(self) -> None:
        first = self.service.retrieve(
            EvidenceRetrievalQuery("certificate", top_k=2),
            tenant_id=TENANT)
        second = self.service.retrieve(
            EvidenceRetrievalQuery("certificate", top_k=2),
            tenant_id=TENANT)
        self.assertEqual(first, second)

    def test_02_repeat_retrieval_does_not_mutate_index_state(self) -> None:
        self.service.retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.service.retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertEqual(len(self.index.entries), 3)
        self.assertEqual(len(self.index.find_calls), 2)

    def test_03_identical_requests_reach_the_index_identically(self) -> None:
        for _ in range(2):
            self.service.retrieve(
                EvidenceRetrievalQuery("q", top_k=3), tenant_id=TENANT)
        first_call, second_call = self.index.find_calls
        self.assertEqual(first_call, second_call)


class TestConstructorValidation(unittest.TestCase):
    """Fail-closed constructor, mirroring EvidenceIndexSyncService."""

    def test_01_missing_vector_index_rejected(self) -> None:
        for bad in (None, object(), "index", 7):
            with self.assertRaises(DomainValidationError):
                VectorIndexEvidenceRetriever(
                    vector_index=bad,
                    provider=FakeProvider(),
                    embedding_config=EMBEDDING_CONFIG)

    def test_02_missing_provider_rejected(self) -> None:
        for bad in (None, object(), "provider"):
            with self.assertRaises(DomainValidationError):
                VectorIndexEvidenceRetriever(
                    vector_index=FakeVectorIndex(),
                    provider=bad,
                    embedding_config=EMBEDDING_CONFIG)

    def test_03_missing_embedding_config_rejected(self) -> None:
        for bad in (None, "config", {"model_identifier": MODEL}):
            with self.assertRaises(DomainValidationError):
                VectorIndexEvidenceRetriever(
                    vector_index=FakeVectorIndex(),
                    provider=FakeProvider(),
                    embedding_config=bad)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()