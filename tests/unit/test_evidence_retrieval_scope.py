"""Phase 5.3 — Evidence Scope & Metadata Filtering tests.

Covers: empty scope, single/multiple metadata filters, AND semantics,
source/document/version/source-type filtering (the canonical indexed
dimensions), unsupported-filter rejection, tenant isolation with and
without optional filters, attempted cross-tenant scope, provider filter
translation, out-of-scope provider results, malformed metadata,
provenance after filtering, no-matching-evidence, and the distinction
between no results and provider/integrity failure. Fakes only — no
live Qdrant server required.
"""

import types
import unittest
from uuid import UUID

from xportra.domain.errors import DomainValidationError, VectorStoreError
from xportra.domain.evidence_indexing import EmbeddingModelConfig
from xportra.domain.evidence_retrieval import (
    EvidenceRetrievalQuery,
    EvidenceRetrievalResult,
    EvidenceRetrievalScope,
    EvidenceRetriever,
    VectorIndexEvidenceRetriever,
)
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TENANT = TenantContext(TENANT_ID)
OTHER_TENANT = TenantContext(OTHER_TENANT_ID)

DOC_A = UUID("11111111-1111-1111-1111-111111111111")
DOC_B = UUID("22222222-2222-2222-2222-222222222222")
DOC_C = UUID("33333333-3333-3333-3333-333333333333")

CHUNK_1 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1")
CHUNK_2 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2")
CHUNK_3 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3")
CHUNK_4 = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa4")

SRC_A = "sonsa/cert-guide"
SRC_B = "nafdac/cocoa-regulation"

COLLECTION = "evidence_chunks_scope_test"
DIMS = 4
MODEL = "test-embed-model"
EMBEDDING_CONFIG = EmbeddingModelConfig(
    model_identifier=MODEL, dimensions=DIMS)
QUERY_VECTOR = [1.0, 0.0, 0.0, 0.0]


def make_result(**overrides):
    base = dict(
        tenant_id=TENANT_ID,
        chunk_id=CHUNK_1,
        document_id=DOC_A,
        chunk_index=0,
        content="Exporters must hold a valid certificate.",
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


def seed_results():
    """Tenant-A evidence from two sources plus a tenant-B look-alike
    that satisfies the SRC_A scope (tenant check must still win)."""
    r1 = make_result(chunk_id=CHUNK_1, score=0.9,
                     content_fingerprint="fp-1")
    r2 = make_result(chunk_id=CHUNK_2, chunk_index=1, score=0.7,
                     content_fingerprint="fp-2")
    r3 = make_result(chunk_id=CHUNK_3, document_id=DOC_B, source_id=SRC_B,
                     source_type="regulation", document_version="v2",
                     score=0.8, content_fingerprint="fp-3")
    r4 = make_result(tenant_id=OTHER_TENANT_ID, chunk_id=CHUNK_4,
                     document_id=DOC_C, score=0.95,
                     content_fingerprint="fp-4")
    return [r1, r2, r3, r4]


def cosine(a, b):
    num = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    return num / (na * nb)


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


class FakeIndex:
    """``EvidenceVectorIndex.find`` stand-in honoring tenant + scope.

    Flags simulate misbehaving providers: ``ignore_tenant`` skips the
    tenant filter, ``ignore_scope`` skips the scope filter — the
    service's defense-in-depth re-checks must then catch results.
    """

    def __init__(self, results=None, fail=False, raw_output=None,
                 ignore_tenant=False, ignore_scope=False):
        self.results = list(results if results is not None
                            else seed_results())
        self.fail = fail
        self.raw_output = raw_output
        self.ignore_tenant = ignore_tenant
        self.ignore_scope = ignore_scope
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


def make_service(index=None, provider=None, embedding_config=None):
    return VectorIndexEvidenceRetriever(
        vector_index=FakeIndex() if index is None else index,
        provider=FakeProvider() if provider is None else provider,
        embedding_config=(
            EMBEDDING_CONFIG if embedding_config is None
            else embedding_config),
    )


class FakeQdrantClient:
    """In-memory Qdrant stand-in that honors ``query_filter.must``."""

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
        must = list(query_filter.must)
        self.last_query = types.SimpleNamespace(
            query=list(query), limit=limit,
            must=[(c.key, c.match.value) for c in must])
        coll = self.collections[collection_name]
        scored = []
        for point in coll["points"].values():
            if not self.ignore_filter and not all(
                    point.payload.get(c.key) == c.match.value
                    for c in must):
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
        chunk_id=CHUNK_1,
        document_id=DOC_A,
        chunk_index=0,
        content="Exporters must hold a valid certificate.",
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
        from xportra.domain.vector_index import VectorIndexConfig
        from xportra.infrastructure.vector_index import (
            QdrantEvidenceVectorIndex,
        )
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
        self.adapter_cls = QdrantEvidenceVectorIndex

    def seed(self, record):
        return self.index.upsert(record, tenant_id=self.tenant)


class TestScopeContract(unittest.TestCase):
    """The scope value object: supported dimensions, validation, AND."""

    def test_01_default_scope_empty(self) -> None:
        scope = EvidenceRetrievalScope()
        self.assertTrue(scope.is_empty)
        self.assertEqual(scope.items(), ())

    def test_02_only_canonical_dimensions_exist(self) -> None:
        self.assertEqual(
            set(EvidenceRetrievalScope.__dataclass_fields__),
            {"source_id", "source_type", "document_id",
             "document_version"})

    def test_03_unsupported_dimensions_rejected(self) -> None:
        for kwargs in (
            {"tenant_id": OTHER_TENANT_ID},
            {"jurisdiction": "NG"},
            {"commodity": "cocoa"},
            {"filters": {}},
            {"chunk_id": CHUNK_1},
            {"metadata": {}},
        ):
            with self.assertRaises(TypeError):
                EvidenceRetrievalScope(**kwargs)

    def test_04_invalid_values_rejected(self) -> None:
        for bad in ("", "   ", 7, b"src", ["src"]):
            with self.assertRaises(DomainValidationError):
                EvidenceRetrievalScope(source_id=bad)
        for bad in ("blog", 7, ["guidance"]):
            with self.assertRaises(DomainValidationError):
                EvidenceRetrievalScope(source_type=bad)
        for bad in ("not-a-uuid", 7):
            with self.assertRaises(DomainValidationError):
                EvidenceRetrievalScope(document_id=bad)
        for bad in ("", "   ", 7):
            with self.assertRaises(DomainValidationError):
                EvidenceRetrievalScope(document_version=bad)

    def test_05_values_trimmed(self) -> None:
        scope = EvidenceRetrievalScope(
            source_id="  src/a  ", document_version=" v2 ")
        self.assertEqual(scope.source_id, "src/a")
        self.assertEqual(scope.document_version, "v2")

    def test_06_accepts_uses_conjunctive_exact_equality(self) -> None:
        r1 = seed_results()[0]
        r3 = seed_results()[2]
        self.assertTrue(EvidenceRetrievalScope().accepts(r1))
        self.assertTrue(
            EvidenceRetrievalScope(source_id=SRC_A).accepts(r1))
        self.assertFalse(
            EvidenceRetrievalScope(source_id=SRC_A).accepts(r3))
        both = EvidenceRetrievalScope(
            source_id=SRC_A, source_type="guidance")
        self.assertTrue(both.accepts(r1))
        # AND, not OR: matches source but not type → rejected
        self.assertFalse(
            EvidenceRetrievalScope(
                source_id=SRC_A, source_type="regulation").accepts(r1))


class TestEmptyScope(AdapterTestCase):
    """Empty scope means tenant constraint only — never all tenants."""

    def test_01_service_without_scope_is_tenant_only(self) -> None:
        index = FakeIndex()
        results = make_service(index=index).retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertEqual(len(results), 3)
        self.assertTrue(
            all(r.tenant_id == TENANT_ID for r in results))
        passed_scope = index.find_calls[0][3]
        self.assertIsInstance(passed_scope, EvidenceRetrievalScope)
        self.assertTrue(passed_scope.is_empty)

    def test_02_explicit_none_scope_equals_empty_scope(self) -> None:
        results = make_service().retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT, scope=None)
        self.assertEqual(len(results), 3)

    def test_03_adapter_empty_scope_sends_tenant_condition_only(
        self,
    ) -> None:
        self.seed(make_index_record())
        self.index.upsert(
            make_index_record(
                tenant_id=OTHER_TENANT_ID, chunk_id=CHUNK_4,
                document_id=DOC_C),
            tenant_id=self.other)
        results = self.index.find(
            QUERY_VECTOR, tenant_id=self.tenant, top_k=10)
        must = self.client.last_query.must
        self.assertEqual(len(must), 1)
        self.assertEqual(must[0], ("tenant_id", str(TENANT_ID)))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].tenant_id, TENANT_ID)


class TestSingleFilter(AdapterTestCase):
    """One supplied filter restricts exactly that canonical dimension."""

    def test_01_source_id_filter(self) -> None:
        results = make_service().retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT,
            scope=EvidenceRetrievalScope(source_id=SRC_A))
        self.assertEqual(len(results), 2)
        self.assertTrue(
            all(r.source_id == SRC_A for r in results))

    def test_02_document_id_filter(self) -> None:
        results = make_service().retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT,
            scope=EvidenceRetrievalScope(document_id=DOC_B))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].document_id, DOC_B)
        self.assertEqual(results[0].chunk_id, CHUNK_3)

    def test_03_document_version_filter(self) -> None:
        results = make_service().retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT,
            scope=EvidenceRetrievalScope(document_version="v2"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].document_version, "v2")

    def test_04_adapter_source_id_filter(self) -> None:
        self.seed(make_index_record())
        self.seed(make_index_record(
            chunk_id=CHUNK_3, document_id=DOC_B, source_id=SRC_B,
            source_type="regulation", document_version="v2"))
        results = self.index.find(
            QUERY_VECTOR, tenant_id=self.tenant, top_k=10,
            scope=EvidenceRetrievalScope(source_id=SRC_A))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source_id, SRC_A)
        self.assertIn(("source_id", SRC_A), self.client.last_query.must)


class TestMultipleFiltersAndSemantics(AdapterTestCase):
    """Multiple supplied filters are conjunctive (AND), never OR."""

    def test_01_source_plus_type_is_and_not_or(self) -> None:
        results = make_service().retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT,
            scope=EvidenceRetrievalScope(
                source_id=SRC_A, source_type="regulation"))
        self.assertEqual(results, [])

    def test_02_document_plus_version_is_and(self) -> None:
        mismatched = make_service().retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT,
            scope=EvidenceRetrievalScope(
                document_id=DOC_A, document_version="v2"))
        self.assertEqual(mismatched, [])
        matched = make_service().retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT,
            scope=EvidenceRetrievalScope(
                document_id=DOC_A, document_version="v1"))
        self.assertEqual(len(matched), 2)

    def test_03_three_filters_all_must_hold(self) -> None:
        results = make_service().retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT,
            scope=EvidenceRetrievalScope(
                source_id=SRC_B, source_type="regulation",
                document_version="v2"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].chunk_id, CHUNK_3)

    def test_04_adapter_conditions_are_additive(self) -> None:
        self.seed(make_index_record())
        self.seed(make_index_record(
            chunk_id=CHUNK_3, document_id=DOC_B, source_id=SRC_B,
            source_type="regulation", document_version="v2"))
        results = self.index.find(
            QUERY_VECTOR, tenant_id=self.tenant, top_k=10,
            scope=EvidenceRetrievalScope(
                source_id=SRC_B, source_type="regulation"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source_id, SRC_B)


class TestSourceTypeAndVersionFiltering(AdapterTestCase):
    """Source-type and version dimensions end-to-end (domain + adapter)."""

    def test_01_source_type_filtering_domain(self) -> None:
        regulation = make_service().retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT,
            scope=EvidenceRetrievalScope(source_type="regulation"))
        self.assertEqual([r.chunk_id for r in regulation], [CHUNK_3])
        guidance = make_service().retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT,
            scope=EvidenceRetrievalScope(source_type="guidance"))
        self.assertEqual(
            [r.chunk_id for r in guidance], [CHUNK_1, CHUNK_2])

    def test_02_source_type_filtering_adapter(self) -> None:
        self.seed(make_index_record())
        self.seed(make_index_record(
            chunk_id=CHUNK_3, document_id=DOC_B, source_id=SRC_B,
            source_type="regulation", document_version="v2"))
        results = self.index.find(
            QUERY_VECTOR, tenant_id=self.tenant, top_k=10,
            scope=EvidenceRetrievalScope(source_type="regulation"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source_type, "regulation")

    def test_03_document_version_filtering_adapter(self) -> None:
        self.seed(make_index_record())
        self.seed(make_index_record(
            chunk_id=CHUNK_3, document_id=DOC_B, source_id=SRC_B,
            source_type="regulation", document_version="v2"))
        results = self.index.find(
            QUERY_VECTOR, tenant_id=self.tenant, top_k=10,
            scope=EvidenceRetrievalScope(document_version="v2"))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].document_version, "v2")

    def test_04_document_id_filtering_adapter(self) -> None:
        self.seed(make_index_record())
        self.seed(make_index_record(
            chunk_id=CHUNK_3, document_id=DOC_B, source_id=SRC_B,
            source_type="regulation", document_version="v2"))
        results = self.index.find(
            QUERY_VECTOR, tenant_id=self.tenant, top_k=10,
            scope=EvidenceRetrievalScope(document_id=DOC_B))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].document_id, DOC_B)


class TestTenantIsolationWithScope(unittest.TestCase):
    """Scope never replaces or weakens tenant isolation."""

    def test_01_no_optional_filters_still_tenant_scoped(self) -> None:
        results = make_service().retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT)
        self.assertEqual(len(results), 3)
        self.assertTrue(
            all(r.tenant_id == TENANT_ID for r in results))

    def test_02_optional_filters_keep_tenant_scope(self) -> None:
        results = make_service().retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT,
            scope=EvidenceRetrievalScope(source_id=SRC_A))
        # tenant-B evidence shares SRC_A but must never appear
        self.assertEqual(
            [r.chunk_id for r in results], [CHUNK_1, CHUNK_2])
        self.assertTrue(
            all(r.tenant_id == TENANT_ID for r in results))

    def test_03_broken_provider_tenant_filter_still_fails_closed(
        self,
    ) -> None:
        index = FakeIndex(ignore_tenant=True)
        with self.assertRaises(VectorStoreError) as ctx:
            make_service(index=index).retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT,
                scope=EvidenceRetrievalScope(source_id=SRC_A))
        self.assertEqual(ctx.exception.operation, "evidence retrieval")
        self.assertIn("cross-tenant", str(ctx.exception.cause))

    def test_04_cross_tenant_scope_cannot_be_expressed(self) -> None:
        with self.assertRaises(TypeError):
            EvidenceRetrievalScope(tenant_id=OTHER_TENANT_ID)
        self.assertNotIn(
            "tenant_id", EvidenceRetrievalScope.__dataclass_fields__)
        # identical scope, different execution tenant → that tenant's data
        other_results = make_service().retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=OTHER_TENANT,
            scope=EvidenceRetrievalScope(source_id=SRC_A))
        self.assertEqual([r.chunk_id for r in other_results], [CHUNK_4])
        self.assertTrue(
            all(r.tenant_id == OTHER_TENANT_ID for r in other_results))


class TestProviderTranslation(AdapterTestCase):
    """Domain scope → provider filter expression (AND, canonical keys)."""

    def test_01_tenant_condition_is_always_first(self) -> None:
        self.seed(make_index_record())
        self.index.find(
            QUERY_VECTOR, tenant_id=self.tenant, top_k=5,
            scope=EvidenceRetrievalScope(source_id=SRC_A))
        must = self.client.last_query.must
        self.assertEqual(must[0], ("tenant_id", str(TENANT_ID)))
        self.assertEqual(must[1], ("source_id", SRC_A))

    def test_02_full_scope_translated_with_payload_encoding(self) -> None:
        self.seed(make_index_record())
        self.index.find(
            QUERY_VECTOR, tenant_id=self.tenant, top_k=5,
            scope=EvidenceRetrievalScope(
                source_id=SRC_A, source_type="guidance",
                document_id=DOC_A, document_version="v1"))
        self.assertEqual(self.client.last_query.must, [
            ("tenant_id", str(TENANT_ID)),
            ("source_id", SRC_A),
            ("source_type", "guidance"),
            ("document_id", str(DOC_A)),
            ("document_version", "v1"),
        ])

    def test_03_domain_modules_contain_no_provider_types(self) -> None:
        import xportra.domain.evidence_retrieval as retrieval_mod
        import xportra.domain.vector_index as index_mod
        for module in (retrieval_mod, index_mod):
            source = open(module.__file__, encoding="utf-8").read()
            self.assertNotIn("qdrant_client", source)
            self.assertNotIn("qmodels", source)

    def test_04_items_are_canonical_and_ordered(self) -> None:
        scope = EvidenceRetrievalScope(
            document_version="v1", source_type="guidance",
            source_id=SRC_A, document_id=DOC_A)
        self.assertEqual(scope.items(), (
            ("source_id", SRC_A),
            ("source_type", "guidance"),
            ("document_id", DOC_A),
            ("document_version", "v1"),
        ))
        self.assertFalse(scope.is_empty)


class TestScopeIntegrity(AdapterTestCase):
    """Out-of-scope provider results fail closed — never silent."""

    def test_01_service_rejects_out_of_scope_result(self) -> None:
        index = FakeIndex(ignore_scope=True)
        with self.assertRaises(VectorStoreError) as ctx:
            make_service(index=index).retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT,
                scope=EvidenceRetrievalScope(source_id=SRC_A))
        self.assertEqual(ctx.exception.operation, "evidence retrieval")
        self.assertIn("scope", str(ctx.exception.cause))

    def test_02_adapter_rejects_out_of_scope_result(self) -> None:
        client = FakeQdrantClient(ignore_filter=True)
        index = self.adapter_cls(client, self.config)
        index.upsert(
            make_index_record(source_id=SRC_B, source_type="regulation"),
            tenant_id=self.tenant)
        with self.assertRaises(VectorStoreError) as ctx:
            index.find(
                QUERY_VECTOR, tenant_id=self.tenant, top_k=5,
                scope=EvidenceRetrievalScope(source_id=SRC_A))
        self.assertEqual(ctx.exception.operation, "find")
        self.assertIn("scope", str(ctx.exception.cause))

    def test_03_malformed_metadata_with_active_scope_fails_closed(
        self,
    ) -> None:
        bad = make_result(source_id=7)
        index = FakeIndex(results=[bad], ignore_scope=True)
        with self.assertRaises(VectorStoreError) as ctx:
            make_service(index=index).retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT,
                scope=EvidenceRetrievalScope(source_id=SRC_A))
        self.assertIn("scope", str(ctx.exception.cause))

    def test_04_adapter_malformed_payload_fails_closed(self) -> None:
        self.seed(make_index_record())
        point = self.client.collections[COLLECTION]["points"][
            str(CHUNK_1)]
        point.payload["source_type"] = "blog"
        with self.assertRaises(VectorStoreError) as ctx:
            self.index.find(QUERY_VECTOR, tenant_id=self.tenant, top_k=5)
        self.assertEqual(ctx.exception.operation, "find")


class TestProvenanceAfterFiltering(AdapterTestCase):
    """Filtering never strips provenance from returned evidence."""

    PROVENANCE_FIELDS = (
        "tenant_id", "chunk_id", "document_id", "chunk_index",
        "content", "content_fingerprint", "source_id", "source_type",
        "source_location", "document_version", "embedding_model",
        "embedding_dimensions", "score",
    )

    def test_01_filtered_domain_result_is_complete(self) -> None:
        results = make_service().retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT,
            scope=EvidenceRetrievalScope(source_id=SRC_A))
        result = results[0]
        self.assertIsInstance(result, EvidenceRetrievalResult)
        self.assertEqual(
            set(result.to_record()), set(self.PROVENANCE_FIELDS))
        self.assertEqual(result.chunk_id, CHUNK_1)
        self.assertEqual(result.document_id, DOC_A)
        self.assertEqual(result.content_fingerprint, "fp-1")
        self.assertEqual(result.source_id, SRC_A)
        self.assertEqual(result.source_type, "guidance")
        self.assertEqual(
            result.source_location, "https://example.test/guide")
        self.assertEqual(result.document_version, "v1")
        self.assertEqual(result.embedding_model, MODEL)
        self.assertEqual(result.embedding_dimensions, DIMS)
        self.assertEqual(result.tenant_id, TENANT_ID)

    def test_02_filtered_adapter_result_is_complete(self) -> None:
        record = make_index_record()
        self.seed(record)
        results = self.index.find(
            QUERY_VECTOR, tenant_id=self.tenant, top_k=5,
            scope=EvidenceRetrievalScope(source_id=SRC_A))
        result = results[0]
        for field in self.PROVENANCE_FIELDS:
            if field == "score":
                continue
            self.assertEqual(getattr(result, field), record[field])


class TestNoResultsVersusFailure(unittest.TestCase):
    """Empty means "no matching evidence" — never a masked failure."""

    def test_01_non_matching_scope_returns_empty(self) -> None:
        results = make_service().retrieve(
            EvidenceRetrievalQuery("q"), tenant_id=TENANT,
            scope=EvidenceRetrievalScope(source_id="no/such-source"))
        self.assertEqual(results, [])

    def test_02_provider_failure_is_not_empty_success(self) -> None:
        failing = make_service(index=FakeIndex(fail=True))
        with self.assertRaises(VectorStoreError):
            failing.retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT,
                scope=EvidenceRetrievalScope(source_id=SRC_A))
        self.assertEqual(
            make_service().retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT,
                scope=EvidenceRetrievalScope(source_id="no/such-source")),
            [])

    def test_03_integrity_violation_is_not_empty_success(self) -> None:
        broken = make_service(index=FakeIndex(ignore_scope=True))
        with self.assertRaises(VectorStoreError):
            broken.retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT,
                scope=EvidenceRetrievalScope(source_id=SRC_A))
        self.assertEqual(
            make_service().retrieve(
                EvidenceRetrievalQuery("q"), tenant_id=TENANT,
                scope=EvidenceRetrievalScope(source_id="no/such-source")),
            [])


class TestCompatibility(AdapterTestCase):
    """Phase 5.1/5.2 calls remain valid without any scope."""

    def test_01_retrieve_without_scope_still_works(self) -> None:
        results = make_service().retrieve(
            EvidenceRetrievalQuery("certificate"), tenant_id=TENANT)
        self.assertEqual(len(results), 3)

    def test_02_protocol_scope_parameter_is_optional(self) -> None:
        import inspect
        sig = inspect.signature(EvidenceRetriever.retrieve)
        self.assertIn("scope", sig.parameters)
        self.assertIsNone(sig.parameters["scope"].default)
        self.assertIsInstance(make_service(), EvidenceRetriever)

    def test_03_adapter_find_without_scope_still_works(self) -> None:
        self.seed(make_index_record())
        results = self.index.find(
            QUERY_VECTOR, tenant_id=self.tenant, top_k=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].chunk_id, CHUNK_1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()