"""Phase 4.3 - Evidence Embedding/Indexing Boundary tests."""

import math
import unittest
from uuid import UUID

from xportra.domain.errors import DomainValidationError
from xportra.domain.evidence_indexing import (
    EmbeddingModelConfig,
    EvidenceIndexingService,
)
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
DOC_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
CHUNK_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")


class FakeProvider:
    """Deterministic offline embedding stand-in (no network/API)."""

    def __init__(self, dimensions=3, fail=False, malformed=None):
        self.calls = []
        self.dimensions = dimensions
        self.fail = fail
        self.malformed = malformed

    def embed(self, text):
        self.calls.append(text)
        if self.fail:
            raise RuntimeError("provider down")
        if self.malformed is not None:
            return self.malformed
        return [1.0, 0.5, -0.25][: self.dimensions]


class TestEvidenceIndexing(unittest.TestCase):
    def setUp(self) -> None:
        self.config = EmbeddingModelConfig(
            model_identifier="test-model-1", dimensions=3)
        self.provider = FakeProvider()
        self.service = EvidenceIndexingService()
        self.tenant = TenantContext(TENANT_ID)
        self.other = TenantContext(OTHER_TENANT_ID)

    def _chunk(self, **kw):
        base = {
            "tenant_id": TENANT_ID,
            "chunk_id": CHUNK_ID,
            "document_id": DOC_ID,
            "chunk_index": 0,
            "content": "Exporters must hold a valid certificate.",
            "content_fingerprint": "fp-1",
            "source_id": "nafdac/cocoa-guide",
            "source_type": "guidance",
            "source_location": "https://example.test/guide",
            "document_version": "v1",
        }
        base.update(kw)
        return base

    # 01 valid chunk indexing
    def test_01_valid_chunk_indexed(self) -> None:
        rows = self.service.index(
            [self._chunk()], tenant_id=self.tenant,
            provider=self.provider, config=self.config)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["embedding_model"], "test-model-1")
        self.assertEqual(rows[0]["embedding_vector"], [1.0, 0.5, -0.25])

    # 02 multiple chunks
    def test_02_multiple_chunks(self) -> None:
        second = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
        rows = self.service.index(
            [self._chunk(), self._chunk(chunk_id=second, chunk_index=1)],
            tenant_id=self.tenant, provider=self.provider,
            config=self.config)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["chunk_index"], 1)

    # 03 deterministic provider interaction
    def test_03_provider_receives_exact_content(self) -> None:
        self.service.index([self._chunk()], tenant_id=self.tenant,
                           provider=self.provider, config=self.config)
        self.assertEqual(self.provider.calls,
                         ["Exporters must hold a valid certificate."])

    # 04 embedding dimension validation
    def test_04_dimension_mismatch_rejected(self) -> None:
        provider = FakeProvider(dimensions=2)
        with self.assertRaises(DomainValidationError):
            self.service.index([self._chunk()], tenant_id=self.tenant,
                               provider=provider, config=self.config)

    # 05 inconsistent dimensions across calls rejected
    def test_05_inconsistent_dimensions_rejected(self) -> None:
        class WobblyProvider:
            def __init__(self):
                self.n = 0

            def embed(self, text):
                self.n += 1
                return [0.1, 0.2] if self.n == 1 else [0.1, 0.2, 0.3]
        with self.assertRaises(DomainValidationError):
            self.service.index([self._chunk(), self._chunk()],
                               tenant_id=self.tenant,
                               provider=WobblyProvider(),
                               config=self.config)

    # 06 empty embeddings rejected
    def test_06_empty_embedding_rejected(self) -> None:
        provider = FakeProvider(malformed=[])
        with self.assertRaises(DomainValidationError):
            self.service.index([self._chunk()], tenant_id=self.tenant,
                               provider=provider, config=self.config)

    # 07 non-finite values rejected
    def test_07_non_finite_rejected(self) -> None:
        for bad in ([float("nan"), 1.0], [1.0, float("inf"), 0.0]):
            provider = FakeProvider(malformed=bad)
            with self.assertRaises(DomainValidationError):
                self.service.index([self._chunk()], tenant_id=self.tenant,
                                   provider=provider, config=self.config)

    # 08 malformed embedding types rejected
    def test_08_malformed_embedding_rejected(self) -> None:
        for bad in ("not-a-vector", {"a": 1}, [1.0, "x", 0.5], 42, set()):
            provider = FakeProvider(malformed=bad)
            with self.assertRaises(DomainValidationError):
                self.service.index([self._chunk()], tenant_id=self.tenant,
                                   provider=provider, config=self.config)

    # 09 malformed chunks rejected (no silent skipping)
    def test_09_malformed_chunk_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.index(
                [self._chunk(), "not-a-dict"], tenant_id=self.tenant,
                provider=self.provider, config=self.config)

    # 10 missing chunk identity rejected
    def test_10_missing_identity_rejected(self) -> None:
        for kw in ({"chunk_id": None}, {"chunk_id": "str-id"},
                   {"document_id": None}, {"document_id": 7}):
            with self.assertRaises(DomainValidationError):
                self.service.index([self._chunk(**kw)],
                                   tenant_id=self.tenant,
                                   provider=self.provider,
                                   config=self.config)

    # 11 tenant mismatch rejected
    def test_11_tenant_mismatch_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.index(
                [self._chunk(tenant_id=OTHER_TENANT_ID)],
                tenant_id=self.tenant, provider=self.provider,
                config=self.config)

    # 12 invalid tenant context rejected
    def test_12_invalid_tenant_rejected(self) -> None:
        for bad in ("bad", None, TENANT_ID):
            with self.assertRaises(DomainValidationError):
                self.service.index([self._chunk()], tenant_id=bad,
                                   provider=self.provider,
                                   config=self.config)

    # 13 provenance preserved
    def test_13_provenance_preserved(self) -> None:
        row = self.service.index([self._chunk()], tenant_id=self.tenant,
                                 provider=self.provider,
                                 config=self.config)[0]
        self.assertEqual(row["source_id"], "nafdac/cocoa-guide")
        self.assertEqual(row["source_type"], "guidance")
        self.assertEqual(row["source_location"], "https://example.test/guide")
        self.assertEqual(row["document_version"], "v1")
        self.assertEqual(row["document_id"], DOC_ID)

    # 14 content preserved exactly
    def test_14_content_preserved(self) -> None:
        text = "  Padded clause  "
        row = self.service.index(
            [self._chunk(content=text)], tenant_id=self.tenant,
            provider=self.provider, config=self.config)[0]
        self.assertEqual(row["content"], text)

    # 15 content fingerprint preserved
    def test_15_fingerprint_preserved(self) -> None:
        row = self.service.index([self._chunk(content_fingerprint="fp-x")],
                                 tenant_id=self.tenant,
                                 provider=self.provider,
                                 config=self.config)[0]
        self.assertEqual(row["content_fingerprint"], "fp-x")

    # 16 chunk identity is canonical (no new identity)
    def test_16_chunk_id_canonical(self) -> None:
        row = self.service.index([self._chunk()], tenant_id=self.tenant,
                                 provider=self.provider,
                                 config=self.config)[0]
        self.assertEqual(row["chunk_id"], CHUNK_ID)
        self.assertNotIn("index_id", row)
        self.assertNotIn("embedding_id", row)

    # 17 provider failure fails closed
    def test_17_provider_failure(self) -> None:
        provider = FakeProvider(fail=True)
        with self.assertRaises(DomainValidationError):
            self.service.index([self._chunk()], tenant_id=self.tenant,
                               provider=provider, config=self.config)

    # 18 different chunks -> different embeddings preserved per chunk
    def test_18_per_chunk_embeddings(self) -> None:
        class VarProvider:
            def __init__(self):
                self.seen = []
            def embed(self, text):
                self.seen.append(text)
                return [float(len(text)), 0.0, 1.0]
        provider = VarProvider()
        rows = self.service.index(
            [self._chunk(), self._chunk(chunk_index=1, content="Short.")],
            tenant_id=self.tenant, provider=provider, config=self.config)
        self.assertEqual(rows[0]["embedding_vector"], [40.0, 0.0, 1.0])
        self.assertEqual(rows[1]["embedding_vector"], [6.0, 0.0, 1.0])

    # 19 empty input -> empty output (deterministic)
    def test_19_empty_input(self) -> None:
        self.assertEqual(self.service.index(
            [], tenant_id=self.tenant, provider=self.provider,
            config=self.config), [])

    # 20 malformed containers rejected
    def test_20_malformed_container_rejected(self) -> None:
        for bad in ("not-a-list", None, 42):
            with self.assertRaises(DomainValidationError):
                self.service.index(bad, tenant_id=self.tenant,
                                   provider=self.provider,
                                   config=self.config)

    # 21 stable index representation
    def test_21_stable_representation(self) -> None:
        first = self.service.index([self._chunk()], tenant_id=self.tenant,
                                   provider=self.provider,
                                   config=self.config)
        second = self.service.index([self._chunk()], tenant_id=self.tenant,
                                    provider=self.provider,
                                    config=self.config)
        self.assertEqual(first, second)

    # 22 model identifier preserved
    def test_22_model_identifier_preserved(self) -> None:
        config = EmbeddingModelConfig(
            model_identifier="alt-model-9", dimensions=3)
        row = self.service.index([self._chunk()], tenant_id=self.tenant,
                                 provider=self.provider, config=config)[0]
        self.assertEqual(row["embedding_model"], "alt-model-9")
        self.assertEqual(row["embedding_dimensions"], 3)

    # 23 config validation
    def test_23_config_validation(self) -> None:
        with self.assertRaises(DomainValidationError):
            EmbeddingModelConfig(model_identifier="  ", dimensions=3)
        with self.assertRaises(DomainValidationError):
            EmbeddingModelConfig(model_identifier="m", dimensions=0)
        with self.assertRaises(DomainValidationError):
            EmbeddingModelConfig(model_identifier="m", dimensions=-4)
        with self.assertRaises(DomainValidationError):
            EmbeddingModelConfig(model_identifier="m", dimensions=True)

    # 24 service requires provider + config
    def test_24_service_requires_provider_and_config(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.index([self._chunk()], tenant_id=self.tenant,
                               provider=None, config=self.config)
        with self.assertRaises(DomainValidationError):
            self.service.index([self._chunk()], tenant_id=self.tenant,
                               provider=self.provider, config=None)

    # 25 end-to-end chunking -> indexing traceability
    def test_25_end_to_end_with_chunking(self) -> None:
        from xportra.domain.evidence_chunking import EvidenceChunkingService
        tenant = TenantContext(TENANT_ID)
        document = {
            "tenant_id": TENANT_ID, "id": DOC_ID,
            "title": "Guide", "content": "Paragraph one.\n\nParagraph two.",
            "source_type": "guidance", "source_id": "s1",
            "source_location": "https://example.test/s1",
            "document_version": "v1", "status": "active",
        }
        chunks = EvidenceChunkingService().chunk(
            document, tenant_id=tenant)
        self.assertGreaterEqual(len(chunks), 1)
        rows = self.service.index(chunks, tenant_id=tenant,
                                  provider=self.provider,
                                  config=self.config)
        self.assertEqual(len(rows), len(chunks))
        for chunk, row in zip(chunks, rows):
            self.assertEqual(chunk["chunk_id"], row["chunk_id"])
            self.assertEqual(chunk["content"], row["content"])
            self.assertEqual(chunk["content_fingerprint"],
                             row["content_fingerprint"])

    # 26 content/missing-field rejection set
    def test_26_missing_fields_rejected(self) -> None:
        for kw in ({"content": "  "}, {"content": None},
                   {"content_fingerprint": None},
                   {"source_id": "  "}, {"source_type": "unknown"},
                   {"chunk_index": -1}, {"chunk_index": "0"},
                   {"document_version": 9}):
            with self.assertRaises(DomainValidationError):
                self.service.index([self._chunk(**kw)],
                                   tenant_id=self.tenant,
                                   provider=self.provider,
                                   config=self.config)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

