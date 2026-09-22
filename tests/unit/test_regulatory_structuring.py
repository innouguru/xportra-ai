import unittest
from datetime import date
from uuid import UUID

from xportra.domain.ingestion import (
    RegulatoryMetadataExtractionError,
    RegulatoryMetadataExtractionService,
)

ARTIFACT_ID = UUID("11111111-2222-3333-4444-555555555555")
SOURCE_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
NORMALIZED_ID = UUID("99999999-8888-7777-6666-555555555555")


class FakeMetadataRepository:
    def __init__(self):
        self.rows = {}

    def get_by_document(self, document_id):
        return self.rows.get(str(document_id))

    def create(self, **values):
        row = {"id": UUID("12345678-1234-1234-1234-123456789012"), **values}
        self.rows[str(values["normalized_document_id"])] = row
        return row


class RegulatoryStructuringTests(unittest.TestCase):
    def setUp(self):
        self.document = {
            "id": NORMALIZED_ID,
            "artifact_id": ARTIFACT_ID,
            "source_id": SOURCE_ID,
            "document_title": "Plant Export Regulation 2026",
            "normalized_text": "Plant Export Regulation 2026\n\nScope\nApplies to seed exports.",
            "normalized_content": {
                "mime_type": "text/markdown",
                "title": "Plant Export Regulation 2026",
                "authority": "National Plant Protection Organization",
                "document_type": "Regulation",
                "publication_date": "2026-01-15",
                "effective_date": "2026-02-01",
                "reference": "NPP/REG/2026/01",
                "version": "2026.1",
                "jurisdiction": "NG",
                "language": "en",
                "structure": [
                    {"kind": "heading", "text": "Plant Export Regulation 2026", "level": 1},
                    {"kind": "heading", "text": "Scope", "level": 2},
                    {"kind": "section", "text": "Applies to seed exports.", "level": 2},
                    {"kind": "heading", "text": "Records", "level": 2},
                    {"kind": "heading", "text": "Retention", "level": 3},
                    {"kind": "section", "text": "Keep records for five years.", "level": 3},
                ],
            },
        }

    def test_extracts_metadata_and_title(self):
        result = RegulatoryMetadataExtractionService().extract(self.document)

        self.assertEqual(result["document_title"], "Plant Export Regulation 2026")
        self.assertEqual(result["document_type"], "regulation")
        self.assertEqual(result["publication_date"], date(2026, 1, 15))
        self.assertEqual(result["effective_date"], date(2026, 2, 1))
        self.assertEqual(result["reference_identifier"], "NPP/REG/2026/01")
        self.assertEqual(result["version"], "2026.1")
        self.assertEqual(result["jurisdiction"], "NG")
        self.assertEqual(result["language"], "en")

    def test_preserves_authority_source_and_provenance(self):
        result = RegulatoryMetadataExtractionService().extract(self.document)

        self.assertEqual(result["authority_name"], "National Plant Protection Organization")
        self.assertEqual(result["normalized_document_id"], NORMALIZED_ID)
        self.assertEqual(result["artifact_id"], ARTIFACT_ID)
        self.assertEqual(result["source_id"], SOURCE_ID)

    def test_unknown_metadata_remains_null(self):
        document = {**self.document, "normalized_content": {"structure": []}}
        result = RegulatoryMetadataExtractionService().extract(document)

        self.assertIsNone(result["document_type"])
        self.assertIsNone(result["publication_date"])
        self.assertIsNone(result["effective_date"])
        self.assertIsNone(result["reference_identifier"])
        self.assertIsNone(result["authority_name"])
        self.assertEqual(result["classification"], "unknown")

    def test_section_hierarchy_preserves_parent_child_order(self):
        result = RegulatoryMetadataExtractionService().extract(self.document)
        sections = result["sections"]

        self.assertEqual([section["heading"] for section in sections], [
            "Scope", "Records", "Retention",
        ])
        self.assertEqual(sections[0]["parent_index"], None)
        self.assertEqual(sections[2]["parent_index"], 1)
        self.assertEqual([section["order"] for section in sections], [0, 1, 2])

    def test_classification_is_conservative(self):
        document = {**self.document}
        content = {**self.document["normalized_content"], "document_type": "internal memo"}
        document["normalized_content"] = content

        result = RegulatoryMetadataExtractionService().extract(document)

        self.assertEqual(result["classification"], "unknown")

    def test_extraction_is_deterministic(self):
        service = RegulatoryMetadataExtractionService()
        first = service.extract(self.document)
        second = service.extract(self.document)

        self.assertEqual(first, second)

    def test_persistence_and_repeated_processing_are_idempotent(self):
        repository = FakeMetadataRepository()
        service = RegulatoryMetadataExtractionService(repository=repository)

        first = service.process(self.document)
        second = service.process(self.document)

        self.assertEqual(first, second)
        self.assertEqual(len(repository.rows), 1)

    def test_missing_normalized_document_identity_is_rejected(self):
        document = {key: value for key, value in self.document.items() if key != "id"}

        with self.assertRaises(RegulatoryMetadataExtractionError):
            RegulatoryMetadataExtractionService().extract(document)

    def test_invalid_explicit_date_is_rejected(self):
        document = {**self.document}
        content = {**self.document["normalized_content"], "publication_date": "not-a-date"}
        document["normalized_content"] = content

        with self.assertRaises(RegulatoryMetadataExtractionError):
            RegulatoryMetadataExtractionService().extract(document)


if __name__ == "__main__":
    unittest.main()
