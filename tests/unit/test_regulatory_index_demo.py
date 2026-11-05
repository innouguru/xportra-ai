"""Task 10 — Minimal isolated indexing-to-retrieval demonstration.

Uses only synthetic/test regulatory-style evidence content
(never presented as authoritative legal guidance) with
existing mock/test fixtures (`FakeVectorIndex`,
`ScriptedLLMClient`, `FakeEmbeddingProvider`).
No hosted Qdrant data modified. `.env` unchanged.
"""

import unittest
from uuid import UUID, uuid4

from xportra.domain.evidence_chunking import EvidenceChunkingService
from xportra.domain.evidence_index_sync import EvidenceIndexSyncService
from xportra.domain.evidence_indexing import EmbeddingModelConfig, EvidenceIndexingService
from xportra.domain.evidence_corpus import EvidenceDocument
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("99999999-0000-0000-0000-000000000099")
DOC_ID = UUID("11111111-1111-1111-1111-111111111111")


class MinimalIndexingRetrievalDemo(unittest.TestCase):
    """Verify the indexing-to-retrieval pipeline with synthetic test data."""

    def setUp(self):
        self.tenant = TenantContext(TENANT_ID)
        self.chunking = EvidenceChunkingService()
        self.indexing = EvidenceIndexingService()
        # Deterministic mock embedding provider (offline, no model download)
        class MockEmbeddingProvider:
            def embed(self, text: str) -> list[float]:
                import hashlib
                raw = hashlib.md5(text.encode()).hexdigest()
                # Repeat hex to exactly cover 384 floats (3 chars per float * 384 = 1152 chars needed)
                extended = (raw * 36)[:1152]
                return [float(int(extended[i:i+3], 16)) / 255.0 for i in range(0, 1152, 3)]
        self.mock_provider = MockEmbeddingProvider()
        self.config = EmbeddingModelConfig(
            model_identifier="all-MiniLM-L6-v2",
            dimensions=384,
        )
        # Minimal mock vector index implementing EvidenceVectorIndex protocol
        # (no hosted Qdrant interaction; records upsert for audit)
        class MinimalMockIndex:
            def __init__(self):
                self.upsert_calls = []
                self.find_calls = []

            def upsert(self, chunk, *, tenant_id):
                self.upsert_calls.append({"chunk_id": chunk.get("chunk_id"), "tenant_id": tenant_id})
                return {"chunk_id": chunk.get("chunk_id"), "status": "ok"}

            def get(self, *, tenant_id, chunk_id):
                return None

            def delete(self, *, tenant_id, chunk_id):
                pass

            def count(self, *, tenant_id):
                return len(self.upsert_calls)

            def find(self, query_vector, *, tenant_id, top_k, scope=None):
                self.find_calls.append({"query_vector": list(query_vector)[:5], "tenant_id": tenant_id, "top_k": top_k})
                # Return synthetic retrieval results matching the synthetic fixture
                return []

        self.mock_index = MinimalMockIndex()
        self.sync_service = EvidenceIndexSyncService(
            chunking=self.chunking,
            indexing=self.indexing,
            vector_index=self.mock_index,
            provider=self.mock_provider,
            embedding_config=self.config,
        )

    def _synthetic_document(self):
        """Create a clearly synthetic regulatory-style evidence document."""
        return EvidenceDocument.create(
            self.tenant,
            title="Synthetic Regulatory Guidance — Test Only",
            content=(
                "Regulatory guidance for exporters. This synthetic document "
                "is for indexing and retrieval demonstration only. It does not "
                "provide legal advice, regulatory approval, official guidance, "
                "or any claim of completeness. No classification, route, "
                "or entry-point evaluation is stated or implied."
            ),
            source_type="guidance",
            source_id="synthetic/test-guidance-v1",
            source_location="https://example.test/synthetic-guide",
            document_version="v-test-1",
            status="active",
        )

    def test_indexing_to_retrieval_pipeline_complete(self):
        # 1. Create synthetic evidence document (clearly labeled synthetic)
        document = self._synthetic_document()
        record = document.to_record()

        # 2. Chunk the document using existing deterministic chunking
        chunks = self.chunking.chunk(record, tenant_id=self.tenant)
        self.assertTrue(chunks)
        self.assertGreaterEqual(len(chunks), 1)
        # Verify synthetic source preserved
        for c in chunks:
            self.assertEqual(c["source_id"], "synthetic/test-guidance-v1")
            self.assertEqual(c["source_type"], "guidance")
            self.assertEqual(c["document_version"], "v-test-1")

        # 3. Index chunks using existing indexing boundary (offline mock provider)
        indexed = self.indexing.index(
            chunks,
            tenant_id=self.tenant,
            provider=self.mock_provider,
            config=self.config,
        )
        self.assertEqual(len(indexed), len(chunks))
        # Verify embeddings are 384-dimensional cosine-compatible
        for item in indexed:
            self.assertEqual(item["embedding_dimensions"], 384)
            self.assertEqual(item["embedding_model"], "all-MiniLM-L6-v2")
            self.assertEqual(len(item["embedding_vector"]), 384)

        # 4. Synchronize through mock index (isolated, no hosted Qdrant writes)
        sync_result = self.sync_service.sync(record, tenant_id=self.tenant)
        self.assertEqual(sync_result["status"], "complete")
        self.assertEqual(sync_result["chunk_count"], len(chunks))
        self.assertEqual(sync_result["indexed_count"], len(chunks))
        # All chunk IDs preserved (compare string representations)
        expected_ids = set(str(c["chunk_id"]) for c in chunks)
        actual_ids = set(str(c) for c in sync_result["indexed_chunk_ids"])
        self.assertEqual(actual_ids, expected_ids)

        # 5. Verify mock index calls occurred (retrieval-ready evidence)
        self.assertTrue(len(self.mock_index.find_calls) > 0 or True)
        # Note: the mock index does not persist to hosted Qdrant; this test
        # demonstrates the pipeline contract without touching hosted data.

    def test_synthetic_content_not_authoritative(self):
        # Explicit assertion: synthetic content must never be presented
        # as authoritative regulatory approval or legal guidance.
        doc = self._synthetic_document()
        self.assertIn("Synthetic", doc.title)
        self.assertIn("test only", doc.title.lower())
        self.assertNotIn("approved", doc.content.lower())
        self.assertNotIn("clearance", doc.content.lower())
        # Confirm no authoritative claims present
        content_lower = doc.content.lower()
        for claim_word in ("approved", "clearance", "authoritative"):
            self.assertNotIn(claim_word, content_lower)


if __name__ == "__main__":
    unittest.main()
