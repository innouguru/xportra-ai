import unittest
from uuid import UUID

from xportra.domain.ingestion import (
    ArtifactParseError,
    ArtifactParsingService,
    ArtifactNormalizationService,
    ArtifactNormalizationError,
)

ARTIFACT_ID = UUID("11111111-2222-3333-4444-555555555555")
SOURCE_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


class FakeNormalizationRepository:
    def __init__(self):
        self.rows = {}

    def get_by_artifact(self, artifact_id):
        return self.rows.get(str(artifact_id))

    def create(self, **values):
        row = {
            "id": UUID("12345678-1234-1234-1234-123456789012"),
            "artifact_id": values["artifact_id"],
            "source_id": values["source_id"],
            "document_title": values["document_title"],
            "normalized_text": values["normalized_text"],
            "normalized_content": values["normalized_content"],
            "content_type": values["content_type"],
            "parser_name": values["parser_name"],
            "status": values["status"],
            "normalized_at": values["normalized_at"],
            "created_at": values["created_at"],
            "updated_at": values["updated_at"],
        }
        self.rows[str(values["artifact_id"])] = row
        return row


class ParsingNormalizationTests(unittest.TestCase):
    def test_plain_text_artifact_parses_and_keeps_structure(self):
        service = ArtifactParsingService()
        document = service.parse(
            artifact_id=ARTIFACT_ID,
            content_type="text/plain",
            raw_content="Regulation Title\n\nThis is the first paragraph.\n\nThis is the second paragraph.",
        )

        self.assertEqual(document["document_title"], "Regulation Title")
        self.assertIn("first paragraph", document["normalized_text"].lower())
        self.assertIn("section", document["normalized_content"]["structure"][0]["kind"])

    def test_markdown_artifact_parses_as_document_sections(self):
        service = ArtifactParsingService()
        document = service.parse(
            artifact_id=ARTIFACT_ID,
            content_type="text/markdown",
            raw_content="# Seed Export Guidance\n\n## Scope\nThis is guidance.\n\n## Requirements\nFollow the rule.",
        )

        self.assertEqual(document["document_title"], "Seed Export Guidance")
        self.assertGreater(len(document["normalized_content"]["structure"]), 1)
        self.assertIn("Scope", document["normalized_content"]["structure"][1]["text"])

    def test_json_artifact_parses_as_structured_text(self):
        service = ArtifactParsingService()
        document = service.parse(
            artifact_id=ARTIFACT_ID,
            content_type="application/json",
            raw_content='{"title": "Customs Notice", "sections": [{"heading": "Overview", "body": "Import compliance applies."}]}',
        )

        self.assertEqual(document["document_title"], "Customs Notice")
        self.assertIn("Import compliance applies.", document["normalized_text"])

    def test_unsupported_artifact_type_is_rejected(self):
        service = ArtifactParsingService()
        with self.assertRaises(ArtifactParseError):
            service.parse(
                artifact_id=ARTIFACT_ID,
                content_type="application/pdf",
                raw_content=b"%PDF-1.4 not handled here",
            )

    def test_malformed_json_is_rejected(self):
        service = ArtifactParsingService()
        with self.assertRaises(ArtifactParseError):
            service.parse(
                artifact_id=ARTIFACT_ID,
                content_type="application/json",
                raw_content='{"title": "Broken"',
            )

    def test_empty_text_is_rejected(self):
        service = ArtifactParsingService()
        with self.assertRaises(ArtifactParseError):
            service.parse(
                artifact_id=ARTIFACT_ID,
                content_type="text/plain",
                raw_content="   \n\n   ",
            )

    def test_normalization_is_deterministic(self):
        repository = FakeNormalizationRepository()
        service = ArtifactNormalizationService(repository=repository)
        first = service.normalize(
            artifact_id=ARTIFACT_ID,
            source_id=SOURCE_ID,
            content_type="text/plain",
            raw_content="Policy Title\n\nFollow the rules.",
        )
        second = service.normalize(
            artifact_id=ARTIFACT_ID,
            source_id=SOURCE_ID,
            content_type="text/plain",
            raw_content="Policy Title\n\nFollow the rules.",
        )

        self.assertEqual(first["normalized_text"], second["normalized_text"])
        self.assertEqual(first["document_title"], second["document_title"])
        self.assertEqual(first["id"], second["id"])

    def test_provenance_is_preserved_in_normalized_record(self):
        repository = FakeNormalizationRepository()
        service = ArtifactNormalizationService(repository=repository)
        normalized = service.normalize(
            artifact_id=ARTIFACT_ID,
            source_id=SOURCE_ID,
            content_type="text/plain",
            raw_content="Document Title\n\nPlain guidance.",
        )

        self.assertEqual(normalized["artifact_id"], ARTIFACT_ID)
        self.assertEqual(normalized["source_id"], SOURCE_ID)
        self.assertEqual(normalized["status"], "normalized")
        self.assertIn("Plain guidance", normalized["normalized_text"])

    def test_repeated_processing_is_idempotent_per_artifact(self):
        repository = FakeNormalizationRepository()
        service = ArtifactNormalizationService(repository=repository)
        first = service.normalize(
            artifact_id=ARTIFACT_ID,
            source_id=SOURCE_ID,
            content_type="text/plain",
            raw_content="Notice\n\nOne paragraph.",
        )
        second = service.normalize(
            artifact_id=ARTIFACT_ID,
            source_id=SOURCE_ID,
            content_type="text/plain",
            raw_content="Notice\n\nOne paragraph.",
        )

        self.assertEqual(len(repository.rows), 1)
        self.assertEqual(first["id"], second["id"])


if __name__ == "__main__":
    unittest.main()
