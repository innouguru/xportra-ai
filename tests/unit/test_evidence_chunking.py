"""Phase 4.2 - Evidence Chunking Boundary tests."""

import unittest
from uuid import UUID

from xportra.domain.errors import DomainValidationError
from xportra.domain.evidence_chunking import (
    MAX_CHUNK_CHARACTERS,
    EvidenceChunkingService,
    stable_chunk_id,
)
from xportra.domain.evidence_corpus import EvidenceDocument
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


class TestEvidenceChunking(unittest.TestCase):
    def setUp(self) -> None:
        self.tenant = TenantContext(TENANT_ID)
        self.other = TenantContext(OTHER_TENANT_ID)
        self.service = EvidenceChunkingService()

    def _document(self, content=None, **kw):
        values = {
            "title": "NAFDAC cocoa guidance",
            "source_type": "guidance",
            "source_id": "nafdac/cocoa-guide",
            "source_location": "https://example.test/guide",
            "document_version": "v1",
        }
        values.update(kw)
        document = EvidenceDocument.create(
            self.tenant, content=content or "First paragraph.\n\nSecond paragraph.",
            **values,
        )
        return document

    # 01 valid document produces chunks
    def test_01_valid_document_produces_chunks(self) -> None:
        chunks = self.service.chunk(self._document(), tenant_id=self.tenant)
        self.assertTrue(chunks)
        self.assertEqual(chunks[0]["document_id"],
                         self._document().to_record()["id"])

    # 02 single short document -> single chunk
    def test_02_single_short_document_single_chunk(self) -> None:
        chunks = self.service.chunk(
            self._document(content="Only one short paragraph."),
            tenant_id=self.tenant,
        )
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["chunk_index"], 0)
        self.assertEqual(chunks[0]["content"], "Only one short paragraph.")

    # 03 multiple paragraphs produce deterministic chunks
    def test_03_multiple_paragraphs_deterministic(self) -> None:
        content = "Para one.\n\nPara two.\n\nPara three."
        chunks = self.service.chunk(
            self._document(content=content), tenant_id=self.tenant)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(
            [c["content"] for c in chunks],
            ["Para one.", "Para two.", "Para three."],
        )

    # 04 oversized paragraph splits deterministically
    def test_04_oversized_paragraph_splits(self) -> None:
        content = "word " * 300
        chunks = self.service.chunk(
            self._document(content=content), tenant_id=self.tenant)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk["content"]), MAX_CHUNK_CHARACTERS)

    # 05 no empty chunks
    def test_05_no_empty_chunks(self) -> None:
        content = "Real text.\n\n   \n\nMore real text."
        chunks = self.service.chunk(
            self._document(content=content), tenant_id=self.tenant)
        self.assertEqual(len(chunks), 2)
        for chunk in chunks:
            self.assertTrue(chunk["content"].strip())

    # 06 chunk order preserved
    def test_06_chunk_order_preserved(self) -> None:
        chunks = self.service.chunk(self._document(), tenant_id=self.tenant)
        self.assertEqual(
            [c["chunk_index"] for c in chunks], [0, 1])
        self.assertEqual(chunks[0]["content"], "First paragraph.")
        self.assertEqual(chunks[1]["content"], "Second paragraph.")

    # 07 chunk content preserved exactly (exact substring + offsets)
    def test_07_chunk_content_exact_substring(self) -> None:
        content = "Alpha paragraph.\n\nBeta paragraph, longer text."
        chunks = self.service.chunk(
            self._document(content=content), tenant_id=self.tenant)
        for chunk in chunks:
            self.assertEqual(
                content[chunk["start_offset"]:chunk["end_offset"]],
                chunk["content"],
            )

    # 08 document ID preserved
    def test_08_document_id_preserved(self) -> None:
        record = self._document().to_record()
        chunks = self.service.chunk(record, tenant_id=self.tenant)
        for chunk in chunks:
            self.assertEqual(chunk["document_id"], record["id"])

    # 09 tenant ID preserved
    def test_09_tenant_id_preserved(self) -> None:
        chunks = self.service.chunk(self._document(), tenant_id=self.tenant)
        for chunk in chunks:
            self.assertEqual(chunk["tenant_id"], TENANT_ID)

    # 10 source ID preserved
    def test_10_source_id_preserved(self) -> None:
        chunks = self.service.chunk(self._document(), tenant_id=self.tenant)
        for chunk in chunks:
            self.assertEqual(chunk["source_id"], "nafdac/cocoa-guide")

    # 11 source type preserved
    def test_11_source_type_preserved(self) -> None:
        chunks = self.service.chunk(self._document(), tenant_id=self.tenant)
        for chunk in chunks:
            self.assertEqual(chunk["source_type"], "guidance")

    # 12 source location preserved
    def test_12_source_location_preserved(self) -> None:
        chunks = self.service.chunk(self._document(), tenant_id=self.tenant)
        for chunk in chunks:
            self.assertEqual(chunk["source_location"],
                             "https://example.test/guide")

    # 13 document version preserved
    def test_13_document_version_preserved(self) -> None:
        chunks = self.service.chunk(self._document(), tenant_id=self.tenant)
        for chunk in chunks:
            self.assertEqual(chunk["document_version"], "v1")

    # 14 deterministic chunk IDs
    def test_14_deterministic_chunk_ids(self) -> None:
        record = self._document().to_record()
        chunks = self.service.chunk(record, tenant_id=self.tenant)
        for chunk in chunks:
            self.assertEqual(
                chunk["chunk_id"],
                stable_chunk_id(
                    TENANT_ID,
                    record["id"],
                    chunk["chunk_index"],
                    chunk["content_fingerprint"],
                ),
            )

    # 15 identical document -> identical chunks
    def test_15_identical_document_identical_chunks(self) -> None:
        first = self.service.chunk(self._document(), tenant_id=self.tenant)
        second = self.service.chunk(self._document(), tenant_id=self.tenant)
        self.assertEqual(first, second)

    # 16 changed content -> changed chunk identity
    def test_16_changed_content_changes_identity(self) -> None:
        before = self.service.chunk(
            self._document(content="Original paragraph."),
            tenant_id=self.tenant,
        )
        after = self.service.chunk(
            self._document(content="Changed paragraph."),
            tenant_id=self.tenant,
        )
        self.assertNotEqual(
            before[0]["chunk_id"], after[0]["chunk_id"])
        self.assertNotEqual(
            before[0]["content_fingerprint"],
            after[0]["content_fingerprint"],
        )

    # 17 invalid tenant rejected
    def test_17_invalid_tenant_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.chunk(self._document(), tenant_id="bad")

    # 18 tenant mismatch rejected
    def test_18_tenant_mismatch_rejected(self) -> None:
        record = dict(self._document().to_record())
        record["tenant_id"] = OTHER_TENANT_ID
        with self.assertRaises(DomainValidationError):
            self.service.chunk(record, tenant_id=self.tenant)

    # 19 malformed document rejected
    def test_19_malformed_document_rejected(self) -> None:
        for bad in ("not-a-dict", None, 42, []):
            with self.assertRaises(DomainValidationError):
                self.service.chunk(bad, tenant_id=self.tenant)

    # 20 missing content rejected
    def test_20_missing_content_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.chunk(
                self._document(content="   "), tenant_id=self.tenant)

    # 21 unsupported source type rejected
    def test_21_unsupported_source_type_rejected(self) -> None:
        record = dict(self._document().to_record())
        record["source_type"] = "REGULATION"
        with self.assertRaises(DomainValidationError):
            self.service.chunk(record, tenant_id=self.tenant)

    # 22 missing document identity rejected
    def test_22_missing_document_identity_rejected(self) -> None:
        record = dict(self._document().to_record())
        del record["id"]
        with self.assertRaises(DomainValidationError):
            self.service.chunk(record, tenant_id=self.tenant)

    # 23 no inferred provenance
    def test_23_no_inferred_provenance(self) -> None:
        chunks = self.service.chunk(self._document(), tenant_id=self.tenant)
        for chunk in chunks:
            self.assertNotIn("section", chunk)
            self.assertNotIn("heading", chunk)
            self.assertNotIn("authority", chunk)
            self.assertNotIn("page_number", chunk)
            self.assertEqual(chunk["source_location"],
                             "https://example.test/guide")

    # 24 no generated/summarized content
    def test_24_no_generated_content(self) -> None:
        content = "Original sentence one. Original sentence two.\n\nPara B."
        chunks = self.service.chunk(
            self._document(content=content), tenant_id=self.tenant)
        for chunk in chunks:
            self.assertIn(chunk["content"], content)

    # 25 end-to-end document -> chunks (via ingestion-created record)
    def test_25_end_to_end_document_to_chunks(self) -> None:
        document = self._document(
            content="Certificate guidance one.\n\nCertificate guidance two.")
        record = document.to_record()
        chunks = self.service.chunk(record, tenant_id=self.tenant)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(
            [c["content"] for c in chunks],
            ["Certificate guidance one.", "Certificate guidance two."],
        )
        for chunk in chunks:
            self.assertEqual(chunk["document_id"], record["id"])
            self.assertEqual(chunk["tenant_id"], TENANT_ID)
            self.assertEqual(chunk["source_id"], "nafdac/cocoa-guide")
