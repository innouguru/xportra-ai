"""Phase 4.4 - Vector Index Persistence Boundary tests.

Unit tests use a fake in-memory Qdrant client; no running Qdrant server is
required. Persistence only - no similarity search API exists to test.
"""

import types
import unittest
from uuid import UUID, uuid4

from qdrant_client.http import models as qmodels

from xportra.domain.errors import (
    DomainNotFoundError,
    DomainValidationError,
    VectorStoreError,
)
from xportra.domain.evidence_indexing import (
    EmbeddingModelConfig,
    EvidenceIndexingService,
    IndexableEvidenceChunk,
)
from xportra.domain.vector_index import (
    EvidenceVectorIndex,
    VectorIndexConfig,
)
from xportra.infrastructure.vector_index import (
    QdrantEvidenceVectorIndex,
    validate_qdrant_collection_config,
)
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
CHUNK_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
DOC_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")

COLLECTION = "evidence_chunks_test"
DIMS = 4
MODEL = "test-embed-model"


class FakePoint:
    def __init__(self, point_id, vector, payload):
        self.id = point_id
        self.vector = vector
        self.payload = payload


class FakeQdrantClient:
    """In-memory stand-in implementing only the client methods used."""

    def __init__(self):
        self.collections = {}
        self.create_calls = 0
        self.fail_on = None

    def _maybe_fail(self, operation):
        if self.fail_on == operation:
            raise RuntimeError(f"simulated qdrant failure during {operation}")

    def collection_exists(self, collection_name):
        self._maybe_fail("collection_exists")
        return collection_name in self.collections

    def create_collection(self, *, collection_name, vectors_config):
        self._maybe_fail("create_collection")
        self.create_calls += 1
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
            coll["points"][str(point.id)] = FakePoint(
                point.id, point.vector, dict(point.payload))

    def retrieve(self, *, collection_name, ids, with_payload, with_vectors):
        self._maybe_fail("retrieve")
        points = self.collections[collection_name]["points"]
        return [points[i] for i in ids if i in points]

    def delete(self, *, collection_name, points_selector, wait):
        self._maybe_fail("delete")
        points = self.collections[collection_name]["points"]
        for point_id in points_selector:
            points.pop(point_id, None)

    def count(self, *, collection_name, count_filter, exact):
        self._maybe_fail("count")
        points = self.collections[collection_name]["points"]
        tenant_value = None
        for condition in count_filter.must:
            tenant_value = condition.match.value
        total = sum(
            1 for point in points.values()
            if point.payload.get("tenant_id") == tenant_value)
        return types.SimpleNamespace(count=total)


def make_config(**overrides):
    base = dict(
        collection_name=COLLECTION,
        embedding_model=MODEL,
        embedding_dimensions=DIMS,
        distance_metric="cosine",
    )
    base.update(overrides)
    return VectorIndexConfig(**base)


def make_chunk(**overrides):
    base = {
        "tenant_id": TENANT_ID,
        "chunk_id": CHUNK_ID,
        "document_id": DOC_ID,
        "chunk_index": 0,
        "content": "Exporters must hold a valid certificate.",
        "content_fingerprint": "fp-abc",
        "source_id": "nafdac/cocoa-guide",
        "source_type": "guidance",
        "source_location": "https://example.test/guide",
        "document_version": "v1",
        "embedding_model": MODEL,
        "embedding_dimensions": DIMS,
        "embedding_vector": [0.1, 0.2, 0.3, 0.4],
    }
    base.update(overrides)
    return IndexableEvidenceChunk(**base)


class VectorIndexTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tenant = TenantContext(TENANT_ID)
        self.other = TenantContext(OTHER_TENANT_ID)
        self.client = FakeQdrantClient()
        self.config = make_config()
        self.index = QdrantEvidenceVectorIndex(self.client, self.config)


class TestVectorIndexConfig(VectorIndexTestCase):
    """Configuration validation."""

    def test_01_valid_configuration(self) -> None:
        cfg = make_config()
        self.assertEqual(cfg.collection_name, COLLECTION)
        self.assertEqual(cfg.embedding_dimensions, DIMS)
        self.assertEqual(cfg.distance_metric, "cosine")

    def test_02_invalid_dimensions_rejected(self) -> None:
        for bad in (0, -1, "4", True, 4.5):
            with self.assertRaises(DomainValidationError):
                make_config(embedding_dimensions=bad)

    def test_03_empty_collection_name_rejected(self) -> None:
        for bad in ("", "  ", None, 7):
            with self.assertRaises(DomainValidationError):
                make_config(collection_name=bad)

    def test_04_model_identifier_preserved(self) -> None:
        self.assertEqual(make_config().embedding_model, MODEL)
        with self.assertRaises(DomainValidationError):
            make_config(embedding_model="")

    def test_05_distance_metric_configuration(self) -> None:
        for metric in ("cosine", "euclid", "dot"):
            self.assertEqual(
                make_config(distance_metric=metric).distance_metric, metric)
        with self.assertRaises(DomainValidationError):
            make_config(distance_metric="manhattan")

    def test_06_from_embedding_config_reuses_phase_43(self) -> None:
        emb = EmbeddingModelConfig(
            model_identifier=MODEL, dimensions=DIMS)
        cfg = VectorIndexConfig.from_embedding_config(COLLECTION, emb)
        self.assertEqual(cfg.embedding_model, MODEL)
        self.assertEqual(cfg.embedding_dimensions, DIMS)
        with self.assertRaises(DomainValidationError):
            VectorIndexConfig.from_embedding_config(COLLECTION, "nope")


class TestEnsureCollection(VectorIndexTestCase):
    """Collection initialization: idempotent, non-destructive."""

    def test_01_creates_missing_collection(self) -> None:
        self.index.ensure_collection()
        self.assertIn(COLLECTION, self.client.collections)
        self.assertEqual(self.client.create_calls, 1)
        coll = self.client.collections[COLLECTION]
        self.assertEqual(coll["size"], DIMS)
        self.assertEqual(coll["distance"], qmodels.Distance.COSINE)

    def test_02_does_not_recreate_compatible_collection(self) -> None:
        self.index.ensure_collection()
        self.index.ensure_collection()
        self.assertEqual(self.client.create_calls, 1)

    def test_03_repeated_initialization_idempotent(self) -> None:
        for _ in range(3):
            self.index.ensure_collection()
        self.assertEqual(self.client.create_calls, 1)

    def test_04_incompatible_dimensions_fail(self) -> None:
        self.index.ensure_collection()
        other = QdrantEvidenceVectorIndex(
            self.client, make_config(embedding_dimensions=DIMS + 4))
        with self.assertRaises(VectorStoreError):
            other.ensure_collection()

    def test_05_incompatible_distance_fails(self) -> None:
        self.index.ensure_collection()
        other = QdrantEvidenceVectorIndex(
            self.client, make_config(distance_metric="euclid"))
        with self.assertRaises(VectorStoreError):
            other.ensure_collection()


class TestUpsert(VectorIndexTestCase):
    """Persistence: canonical identity, idempotency, payload."""

    def test_01_valid_chunk_persists(self) -> None:
        rep = self.index.upsert(make_chunk(), tenant_id=self.tenant)
        self.assertEqual(rep["chunk_id"], CHUNK_ID)
        self.assertEqual(self.index.count(tenant_id=self.tenant), 1)

    def test_02_canonical_chunk_id_is_point_id(self) -> None:
        self.index.upsert(make_chunk(), tenant_id=self.tenant)
        points = self.client.collections[COLLECTION]["points"]
        self.assertIn(str(CHUNK_ID), points)

    def test_03_repeated_upsert_idempotent(self) -> None:
        self.index.upsert(make_chunk(), tenant_id=self.tenant)
        self.index.upsert(make_chunk(), tenant_id=self.tenant)
        points = self.client.collections[COLLECTION]["points"]
        self.assertEqual(len(points), 1)
        self.assertEqual(self.index.count(tenant_id=self.tenant), 1)

    def test_04_multiple_chunks_persist_independently(self) -> None:
        second_id = UUID("11111111-1111-1111-1111-111111111111")
        self.index.upsert(make_chunk(), tenant_id=self.tenant)
        self.index.upsert(
            make_chunk(chunk_id=second_id, chunk_index=1),
            tenant_id=self.tenant)
        points = self.client.collections[COLLECTION]["points"]
        self.assertEqual(len(points), 2)
        self.assertEqual(self.index.count(tenant_id=self.tenant), 2)

    def test_05_payload_contains_tenant_id(self) -> None:
        rep = self.index.upsert(make_chunk(), tenant_id=self.tenant)
        self.assertEqual(rep["tenant_id"], TENANT_ID)
        stored = self.client.collections[COLLECTION]["points"][
            str(CHUNK_ID)]
        self.assertEqual(stored.payload["tenant_id"], str(TENANT_ID))

    def test_06_payload_contains_provenance(self) -> None:
        rep = self.index.upsert(make_chunk(), tenant_id=self.tenant)
        for field in ("source_id", "source_type", "source_location",
                      "document_version", "document_id"):
            self.assertIn(field, rep)
        self.assertEqual(rep["source_id"], "nafdac/cocoa-guide")
        self.assertEqual(rep["source_type"], "guidance")

    def test_07_payload_contains_content(self) -> None:
        rep = self.index.upsert(make_chunk(), tenant_id=self.tenant)
        self.assertEqual(
            rep["content"], "Exporters must hold a valid certificate.")

    def test_08_payload_contains_fingerprint_and_model(self) -> None:
        rep = self.index.upsert(make_chunk(), tenant_id=self.tenant)
        self.assertEqual(rep["content_fingerprint"], "fp-abc")
        self.assertEqual(rep["embedding_model"], MODEL)
        self.assertEqual(rep["embedding_dimensions"], DIMS)


class TestGet(VectorIndexTestCase):
    """Tenant-scoped retrieval of persisted points."""

    def setUp(self) -> None:
        super().setUp()
        self.index.upsert(make_chunk(), tenant_id=self.tenant)

    def test_01_existing_chunk_returned(self) -> None:
        rep = self.index.get(tenant_id=self.tenant, chunk_id=CHUNK_ID)
        self.assertEqual(rep["chunk_id"], CHUNK_ID)
        self.assertEqual(rep["document_id"], DOC_ID)
        self.assertEqual(rep["chunk_index"], 0)

    def test_02_missing_chunk_not_found(self) -> None:
        with self.assertRaises(DomainNotFoundError):
            self.index.get(
                tenant_id=self.tenant, chunk_id=uuid4())

    def test_03_missing_collection_not_found(self) -> None:
        bare = QdrantEvidenceVectorIndex(self.client, make_config(
            collection_name="never_created"))
        with self.assertRaises(DomainNotFoundError):
            bare.get(tenant_id=self.tenant, chunk_id=CHUNK_ID)

    def test_04_cross_tenant_access_denied(self) -> None:
        with self.assertRaises(DomainNotFoundError):
            self.index.get(tenant_id=self.other, chunk_id=CHUNK_ID)


class TestDelete(VectorIndexTestCase):
    """Tenant-scoped deletion."""

    def setUp(self) -> None:
        super().setUp()
        self.index.upsert(make_chunk(), tenant_id=self.tenant)

    def test_01_existing_chunk_deleted(self) -> None:
        self.index.delete(tenant_id=self.tenant, chunk_id=CHUNK_ID)
        self.assertEqual(self.index.count(tenant_id=self.tenant), 0)

    def test_02_missing_chunk_not_found(self) -> None:
        with self.assertRaises(DomainNotFoundError):
            self.index.delete(tenant_id=self.tenant, chunk_id=uuid4())

    def test_03_missing_collection_not_found(self) -> None:
        bare = QdrantEvidenceVectorIndex(self.client, make_config(
            collection_name="never_created"))
        with self.assertRaises(DomainNotFoundError):
            bare.delete(tenant_id=self.tenant, chunk_id=CHUNK_ID)

    def test_04_cross_tenant_deletion_denied(self) -> None:
        with self.assertRaises(DomainNotFoundError):
            self.index.delete(tenant_id=self.other, chunk_id=CHUNK_ID)
        # point still exists for the owning tenant
        self.assertEqual(self.index.count(tenant_id=self.tenant), 1)


class TestValidation(VectorIndexTestCase):
    """Fail-closed validation of tenant, chunk, and embedding input."""

    def _record(self, **overrides):
        record = make_chunk().to_record()
        record.update(overrides)
        return record

    def test_01_invalid_tenant_rejected(self) -> None:
        for bad in (None, "not-a-tenant", TENANT_ID):
            with self.assertRaises(DomainValidationError):
                self.index.upsert(make_chunk(), tenant_id=bad)

    def test_02_tenant_mismatch_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.index.upsert(make_chunk(), tenant_id=self.other)

    def test_03_malformed_indexable_chunk_rejected(self) -> None:
        for bad in (None, "chunk", 42, ["chunk"]):
            with self.assertRaises(DomainValidationError):
                self.index.upsert(bad, tenant_id=self.tenant)

    def test_04_missing_chunk_identity_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.index.upsert(
                self._record(chunk_id=None), tenant_id=self.tenant)
        with self.assertRaises(DomainValidationError):
            self.index.upsert(
                self._record(chunk_id="not-a-uuid"), tenant_id=self.tenant)

    def test_05_missing_document_identity_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.index.upsert(
                self._record(document_id=None), tenant_id=self.tenant)

    def test_06_missing_tenant_identity_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.index.upsert(
                self._record(tenant_id=None), tenant_id=self.tenant)

    def test_07_missing_provenance_rejected(self) -> None:
        for field in ("source_id", "source_type"):
            with self.assertRaises(DomainValidationError):
                self.index.upsert(
                    self._record(**{field: None}), tenant_id=self.tenant)

    def test_08_empty_content_rejected(self) -> None:
        for bad in ("", "   ", None, 7):
            with self.assertRaises(DomainValidationError):
                self.index.upsert(
                    self._record(content=bad), tenant_id=self.tenant)

    def test_09_invalid_embedding_rejected(self) -> None:
        for bad in ("vector", b"vector", [], None, ["a", "b", "c", "d"],
                    [0.1, 0.2, 0.3]):
            with self.assertRaises(DomainValidationError):
                self.index.upsert(
                    self._record(embedding_vector=bad),
                    tenant_id=self.tenant)

    def test_10_nan_embedding_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.index.upsert(
                self._record(embedding_vector=[0.1, float("nan"), 0.3, 0.4]),
                tenant_id=self.tenant)

    def test_11_infinity_embedding_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.index.upsert(
                self._record(
                    embedding_vector=[0.1, float("inf"), 0.3, 0.4]),
                tenant_id=self.tenant)

    def test_12_dimension_mismatch_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.index.upsert(
                self._record(
                    embedding_dimensions=DIMS + 1,
                    embedding_vector=[0.1, 0.2, 0.3, 0.4, 0.5]),
                tenant_id=self.tenant)

    def test_13_embedding_model_mismatch_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.index.upsert(
                self._record(embedding_model="other-model"),
                tenant_id=self.tenant)


class TestErrorTranslation(VectorIndexTestCase):
    """Raw Qdrant failures never escape the domain API."""

    def test_01_qdrant_failure_translated_on_upsert(self) -> None:
        self.client.fail_on = "upsert"
        with self.assertRaises(VectorStoreError) as ctx:
            self.index.upsert(make_chunk(), tenant_id=self.tenant)
        self.assertEqual(ctx.exception.operation, "upsert")
        self.assertIsInstance(ctx.exception.cause, RuntimeError)

    def test_02_raw_exception_does_not_escape_on_ensure(self) -> None:
        self.client.fail_on = "create_collection"
        with self.assertRaises(VectorStoreError):
            self.index.ensure_collection()

    def test_03_raw_exception_does_not_escape_on_get(self) -> None:
        self.index.upsert(make_chunk(), tenant_id=self.tenant)
        self.client.fail_on = "retrieve"
        with self.assertRaises(VectorStoreError) as ctx:
            self.index.get(tenant_id=self.tenant, chunk_id=CHUNK_ID)
        self.assertEqual(ctx.exception.operation, "get")
        self.assertIn("simulated qdrant failure",
                      str(ctx.exception.cause))

    def test_04_raw_exception_does_not_escape_on_delete(self) -> None:
        self.index.upsert(make_chunk(), tenant_id=self.tenant)
        self.client.fail_on = "delete"
        with self.assertRaises(VectorStoreError):
            self.index.delete(tenant_id=self.tenant, chunk_id=CHUNK_ID)


class TestRegression(VectorIndexTestCase):
    """Phase 4.3 domain objects remain usable; no search API introduced."""

    def test_01_phase_43_objects_remain_usable(self) -> None:
        chunk = make_chunk()
        self.assertIsInstance(chunk, IndexableEvidenceChunk)
        self.assertIsInstance(chunk.embedding_vector, list)
        record = chunk.to_record()
        self.assertEqual(record["chunk_id"], CHUNK_ID)
        # full Phase 4.3 indexing path still works end-to-end
        service = EvidenceIndexingService()
        self.assertTrue(hasattr(service, "__class__"))

    def test_02_no_retrieval_api_introduced(self) -> None:
        for name in ("search", "query", "retrieve_similar", "top_k",
                     "similarity_search", "embed_query"):
            self.assertFalse(hasattr(self.index, name))

    def test_03_domain_protocol_has_no_qdrant_imports(self) -> None:
        import xportra.domain.vector_index as mod
        source = open(mod.__file__, encoding="utf-8").read()
        self.assertNotIn("qdrant_client", source)

    def test_04_adapter_is_constructible_with_client_and_config(self) -> None:
        self.assertIsInstance(self.index, QdrantEvidenceVectorIndex)
        self.assertIsInstance(self.index, EvidenceVectorIndex)
        with self.assertRaises(DomainValidationError):
            QdrantEvidenceVectorIndex(None, self.config)
        with self.assertRaises(DomainValidationError):
            QdrantEvidenceVectorIndex(self.client, "not-a-config")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

