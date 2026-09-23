"""Opt-in live Qdrant smoke test for the Phase 5.14 composition root.

GATED: runs only when ``QDRANT_URL`` is set. Never part of the
normal unit suite, never requires production credentials, and never
weakens the deterministic tests. Uses a uniquely-named throwaway
collection that is deleted afterwards; does not touch Docker or any
production collection.
"""

import os
import unittest
import uuid

QDRANT_URL = os.environ.get("QDRANT_URL", "").strip()


@unittest.skipIf(
    not QDRANT_URL, "QDRANT_URL is not configured (opt-in live smoke test)"
)
class RAGQdrantSmokeTests(unittest.TestCase):
    def test_live_collection_lifecycle(self):
        from qdrant_client import QdrantClient

        from xportra.domain.evidence_indexing import EmbeddingModelConfig
        from xportra.domain.vector_index import VectorIndexConfig
        from xportra.infrastructure.vector_index import (
            QdrantEvidenceVectorIndex,
        )
        from xportra.persistence.tenant import TenantContext

        collection = f"xportra-smoke-{uuid.uuid4().hex[:8]}"
        embedding = EmbeddingModelConfig(
            model_identifier="smoke-test-model", dimensions=3
        )
        index = QdrantEvidenceVectorIndex(
            QdrantClient(url=QDRANT_URL),
            VectorIndexConfig.from_embedding_config(
                collection, embedding
            ),
        )
        tenant = TenantContext(uuid.uuid4())
        try:
            index.ensure_collection()
            self.assertEqual(
                index.count(tenant_id=tenant),
                0,
            )
        finally:
            try:
                index._client.delete_collection(collection)
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
