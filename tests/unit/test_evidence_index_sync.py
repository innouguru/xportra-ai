"""Phase 4.5 — Evidence Index Synchronization Boundary tests."""

import unittest
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from xportra.domain.errors import DomainValidationError, VectorStoreError
from xportra.domain.evidence_chunking import EvidenceChunkingService
from xportra.domain.evidence_corpus import content_fingerprint
from xportra.domain.evidence_index_sync import EvidenceIndexSyncService
from xportra.domain.evidence_indexing import (
    EmbeddingModelConfig,
    EvidenceIndexingService,
)
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
TENANT = TenantContext(TENANT_ID)

DOC_A = UUID("11111111-1111-1111-1111-111111111111")
DOC_B = UUID("22222222-2222-2222-2222-222222222222")

THREE_PARAGRAPHS = (
    "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
)


def make_document(
    *,
    content=THREE_PARAGRAPHS,
    tenant=TENANT_ID,
    doc_id=DOC_A,
    version="v1",
):
    return {
        "id": doc_id,
        "tenant_id": tenant,
        "title": "Evidence doc",
        "content": content,
        "source_type": "guidance",
        "source_id": "src/guide",
        "source_location": "https://example.test/guide",
        "document_version": version,
        "metadata": {},
    }


class FakeProvider:
    """Deterministic embedding provider (protocol: ``embed(text)``)."""

    def __init__(self, fail=False):
        self.fail = fail

    def embed(self, text):
        if self.fail:
            raise RuntimeError("provider down")
        return [float(len(text)), 1.0]


class FakeVectorIndex:
    """Tenant+chunk keyed stand-in for the EvidenceVectorIndex protocol."""

    def __init__(self, fail_on=None):
        self.points = {}
        self.upsert_calls = []
        self.fail_on = fail_on

    def upsert(self, chunk, *, tenant_id):
        self.upsert_calls.append(chunk)
        if self.fail_on is not None and len(self.upsert_calls) >= self.fail_on:
            raise RuntimeError("vector store down")
        self.points[(tenant_id.tenant_id, chunk["chunk_id"])] = chunk
        return chunk

    def get(self, *, tenant_id, chunk_id):
        return self.points.get((tenant_id.tenant_id, chunk_id))


class RecordingChunking:
    """Chunking-service fake recording invocations; delegating by default."""

    def __init__(self, chunks=None, error=None):
        self.calls = []
        self._chunks = chunks
        self._error = error

    def chunk(self, document, *, tenant_id):
        self.calls.append((document, tenant_id))
        if self._error is not None:
            raise self._error
        if self._chunks is not None:
            return self._chunks
        return EvidenceChunkingService().chunk(
            document, tenant_id=tenant_id)


class RecordingIndexing:
    """Indexing-service fake recording invocations; delegating by default."""

    def __init__(self, items=None, error=None, truncate=False):
        self.calls = []
        self.kwargs_calls = []
        self._items = items
        self._error = error
        self._truncate = truncate

    def index(self, chunks, *, tenant_id, provider, config):
        self.calls.append(list(chunks))
        self.kwargs_calls.append(
            {"tenant_id": tenant_id, "provider": provider, "config": config}
        )
        if self._error is not None:
            raise self._error
        if self._items is not None:
            return self._items
        result = EvidenceIndexingService().index(
            chunks, tenant_id=tenant_id, provider=provider, config=config)
        if self._truncate:
            return result[:-1]
        return result


def make_chunk(tenant=TENANT_ID, doc_id=DOC_A, index=0,
               content="Marker chunk."):
    return {
        "tenant_id": tenant,
        "chunk_id": uuid5(
            NAMESPACE_URL, f"xportra:sync-test:{tenant}:{doc_id}:{index}"),
        "document_id": doc_id,
        "chunk_index": index,
        "content": content,
        "content_fingerprint": content_fingerprint(content),
        "source_id": "src/guide",
        "source_type": "guidance",
        "source_location": "https://example.test/guide",
        "document_version": "v1",
    }


def make_indexable(tenant=TENANT_ID, doc_id=DOC_A, index=0):
    chunk = make_chunk(tenant=tenant, doc_id=doc_id, index=index)
    return {
        **chunk,
        "embedding_model": "fake-model",
        "embedding_dimensions": 2,
        "embedding_vector": [1.0, 0.0],
    }


def make_service(*, chunking=None, indexing=None, index=None,
                 provider=None, config=None):
    return EvidenceIndexSyncService(
        chunking=chunking if chunking is not None
        else EvidenceChunkingService(),
        indexing=indexing if indexing is not None
        else EvidenceIndexingService(),
        vector_index=index if index is not None else FakeVectorIndex(),
        provider=provider if provider is not None else FakeProvider(),
        embedding_config=config if config is not None
        else EmbeddingModelConfig("fake-model", 2),
    )


class TestSyncHappyPath(unittest.TestCase):
    def test_01_single_document_sync(self) -> None:
        report = make_service().sync(make_document(), tenant_id=TENANT)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["chunk_count"], 3)
        self.assertEqual(report["indexed_count"], 3)

    def test_02_multiple_chunks_report(self) -> None:
        report = make_service().sync(make_document(), tenant_id=TENANT)
        self.assertEqual(len(report["indexed_chunk_ids"]), 3)
        self.assertEqual(
            report["indexed_count"], report["chunk_count"])

    def test_03_report_shape(self) -> None:
        report = make_service().sync(make_document(), tenant_id=TENANT)
        for key in ("tenant_id", "document_id", "document_version",
                    "chunk_count", "indexed_count", "indexed_chunk_ids",
                    "status"):
            self.assertIn(key, report)

    def test_04_indexed_ids_match_persisted_points(self) -> None:
        index = FakeVectorIndex()
        report = make_service(index=index).sync(
            make_document(), tenant_id=TENANT)
        persisted = {chunk_id for (_t, chunk_id) in index.points}
        self.assertEqual(set(report["indexed_chunk_ids"]), persisted)

    def test_05_document_id_reported(self) -> None:
        report = make_service().sync(make_document(), tenant_id=TENANT)
        self.assertEqual(report["document_id"], DOC_A)

    def test_06_tenant_reported(self) -> None:
        report = make_service().sync(make_document(), tenant_id=TENANT)
        self.assertEqual(report["tenant_id"], TENANT_ID)


class TestBoundaryReuse(unittest.TestCase):
    def test_07_chunking_service_invoked(self) -> None:
        chunking = RecordingChunking()
        make_service(chunking=chunking).sync(
            make_document(), tenant_id=TENANT)
        self.assertEqual(len(chunking.calls), 1)

    def test_08_indexing_service_invoked(self) -> None:
        indexing = RecordingIndexing()
        make_service(indexing=indexing).sync(
            make_document(), tenant_id=TENANT)
        self.assertEqual(len(indexing.calls), 1)
        self.assertEqual(len(indexing.calls[0]), 3)

    def test_09_indexing_receives_provider_and_config(self) -> None:
        indexing = RecordingIndexing()
        provider = FakeProvider()
        config = EmbeddingModelConfig("fake-model", 2)
        make_service(indexing=indexing, provider=provider,
                     config=config).sync(make_document(), tenant_id=TENANT)
        call = indexing.kwargs_calls[0]
        self.assertIs(call["provider"], provider)
        self.assertIs(call["config"], config)
        self.assertEqual(call["tenant_id"], TENANT)

    def test_10_vector_index_invoked_per_chunk(self) -> None:
        index = FakeVectorIndex()
        make_service(index=index).sync(make_document(), tenant_id=TENANT)
        self.assertEqual(len(index.upsert_calls), 3)

    def test_11_no_duplicated_chunking_logic(self) -> None:
        direct = EvidenceChunkingService().chunk(
            make_document(), tenant_id=TENANT)
        report = make_service().sync(make_document(), tenant_id=TENANT)
        self.assertEqual(
            report["indexed_chunk_ids"],
            [c["chunk_id"] for c in direct],
        )

    def test_12_no_direct_qdrant_dependency(self) -> None:
        import inspect as _inspect

        import xportra.domain.evidence_index_sync as mod

        source = _inspect.getsource(mod).lower()
        self.assertNotIn("qdrant", source)
        report = make_service().sync(make_document(), tenant_id=TENANT)
        self.assertEqual(report["status"], "complete")


class TestTenantIsolation(unittest.TestCase):
    def test_13_invalid_tenant_rejected(self) -> None:
        svc = make_service()
        for bad in (None, "bad", TENANT_ID, 42):
            with self.assertRaises(DomainValidationError):
                svc.sync(make_document(), tenant_id=bad)

    def test_14_document_tenant_mismatch_rejected(self) -> None:
        svc = make_service()
        with self.assertRaises(DomainValidationError):
            svc.sync(make_document(tenant=OTHER_TENANT_ID), tenant_id=TENANT)

    def test_15_generated_chunk_tenant_mismatch_rejected(self) -> None:
        chunking = RecordingChunking(chunks=[make_chunk(tenant=OTHER_TENANT_ID)])
        svc = make_service(chunking=chunking)
        index = FakeVectorIndex()
        with self.assertRaises(DomainValidationError):
            svc.sync(make_document(), tenant_id=TENANT, )
        self.assertEqual(len(index.upsert_calls), 0)

    def test_16_generated_indexable_tenant_mismatch_rejected(self) -> None:
        chunking = RecordingChunking(chunks=[make_chunk()])
        indexing = RecordingIndexing(
            items=[make_indexable(tenant=OTHER_TENANT_ID)])
        index = FakeVectorIndex()
        svc = make_service(chunking=chunking, indexing=indexing, index=index)
        with self.assertRaises(DomainValidationError):
            svc.sync(make_document(), tenant_id=TENANT)
        self.assertEqual(len(index.upsert_calls), 0)


class TestDeterminism(unittest.TestCase):
    def test_17_repeated_sync_no_duplicate_points(self) -> None:
        index = FakeVectorIndex()
        svc = make_service(index=index)
        first = svc.sync(make_document(), tenant_id=TENANT)
        second = svc.sync(make_document(), tenant_id=TENANT)
        self.assertEqual(first["indexed_chunk_ids"],
                         second["indexed_chunk_ids"])
        self.assertEqual(len(index.points), first["chunk_count"])
        self.assertEqual(first["chunk_count"], 3)

    def test_18_stable_ids_across_service_instances(self) -> None:
        first = make_service(index=FakeVectorIndex()).sync(
            make_document(), tenant_id=TENANT)
        second = make_service(index=FakeVectorIndex()).sync(
            make_document(), tenant_id=TENANT)
        self.assertEqual(first, second)


class TestVersioning(unittest.TestCase):
    def test_19_version_preserved_in_report_and_points(self) -> None:
        index = FakeVectorIndex()
        report = make_service(index=index).sync(
            make_document(version="v2"), tenant_id=TENANT)
        self.assertEqual(report["document_version"], "v2")
        for point in index.points.values():
            self.assertEqual(point["document_version"], "v2")

    def test_20_versions_remain_distinguishable(self) -> None:
        # Phase 4.0 identity: each source version owns a distinct
        # document_id, so chunks/points never collide across versions.
        v1 = make_document(doc_id=DOC_A, version="v1")
        v2 = make_document(doc_id=DOC_B, version="v2")
        index = FakeVectorIndex()
        svc = make_service(index=index)
        r1 = svc.sync(v1, tenant_id=TENANT)
        r2 = svc.sync(v2, tenant_id=TENANT)
        self.assertEqual(r1["document_version"], "v1")
        self.assertEqual(r2["document_version"], "v2")
        self.assertNotEqual(r1["indexed_chunk_ids"],
                            r2["indexed_chunk_ids"])
        versions = {p["document_version"] for p in index.points.values()}
        self.assertEqual(versions, {"v1", "v2"})
        self.assertEqual(len(index.points), 6)


class TestFailureBehavior(unittest.TestCase):
    def test_21_chunking_failure_propagates(self) -> None:
        chunking = RecordingChunking(error=DomainValidationError("bad doc"))
        index = FakeVectorIndex()
        svc = make_service(chunking=chunking, index=index)
        with self.assertRaises(DomainValidationError):
            svc.sync(make_document(), tenant_id=TENANT)
        self.assertEqual(len(index.upsert_calls), 0)

    def test_22_embedding_failure_propagates(self) -> None:
        provider = FakeProvider(fail=True)
        index = FakeVectorIndex()
        svc = make_service(provider=provider, index=index)
        with self.assertRaises(RuntimeError):
            svc.sync(make_document(), tenant_id=TENANT)
        self.assertEqual(len(index.upsert_calls), 0)

    def test_23_vector_failure_reports_incomplete(self) -> None:
        index = FakeVectorIndex(fail_on=2)
        svc = make_service(index=index)
        with self.assertRaises(VectorStoreError):
            svc.sync(make_document(), tenant_id=TENANT)

    def test_24_partial_sync_no_false_success(self) -> None:
        indexing = RecordingIndexing(truncate=True)
        index = FakeVectorIndex()
        svc = make_service(indexing=indexing, index=index)
        with self.assertRaises(DomainValidationError):
            svc.sync(make_document(), tenant_id=TENANT)
        self.assertEqual(len(index.upsert_calls), 0)

    def test_25_vector_failure_preserves_prior_points(self) -> None:
        index = FakeVectorIndex(fail_on=2)
        svc = make_service(index=index)
        with self.assertRaises(VectorStoreError):
            svc.sync(make_document(), tenant_id=TENANT)
        self.assertEqual(len(index.points), 1)


class TestInvalidInput(unittest.TestCase):
    def test_26_malformed_document_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            make_service().sync("not-a-doc", tenant_id=TENANT)

    def test_27_missing_identity_rejected(self) -> None:
        doc = make_document()
        doc["id"] = "not-a-uuid"
        with self.assertRaises(DomainValidationError):
            make_service().sync(doc, tenant_id=TENANT)

    def test_28_empty_content_rejected(self) -> None:
        index = FakeVectorIndex()
        svc = make_service(index=index)
        with self.assertRaises(DomainValidationError):
            svc.sync(make_document(content="   "), tenant_id=TENANT)
        self.assertEqual(len(index.upsert_calls), 0)

    def test_29_invalid_provenance_rejected(self) -> None:
        doc = make_document()
        doc["source_id"] = ""
        with self.assertRaises(DomainValidationError):
            make_service().sync(doc, tenant_id=TENANT)

    def test_30_no_retrieval_api_introduced(self) -> None:
        public = {name for name in dir(EvidenceIndexSyncService)
                  if not name.startswith("_")}
        self.assertEqual(public, {"sync"})
        report = make_service().sync(make_document(), tenant_id=TENANT)
        self.assertEqual(report["status"], "complete")


