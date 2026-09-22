from datetime import datetime, timezone
import unittest
from uuid import UUID

from xportra.domain.ingestion import (
    AcquisitionValidationError,
    SourceAcquisitionService,
)

SOURCE_ID = UUID("11111111-1111-1111-1111-111111111111")
AUTHORITY_ID = UUID("22222222-2222-2222-2222-222222222222")
SOURCE_URL = "https://www.example.gov.ng/regulations/seed-export-guidance.pdf"


class FakeSourceRepository:
    def __init__(self):
        self.rows = {
            str(SOURCE_ID): {
                "id": SOURCE_ID,
                "authority_id": AUTHORITY_ID,
                "jurisdiction": "NG",
                "title": "Seed Export Guidance",
                "version": "2026.01",
                "status": "active",
                "source_url": SOURCE_URL,
                "retrieval_timestamp": None,
                "supersedes_source_id": None,
                "superseded_by_source_id": None,
            }
        }

    def get(self, source_id):
        return self.rows.get(str(source_id))


class FakeArtifactRepository:
    def __init__(self):
        self.rows = []

    def create(self, **values):
        row = {
            "id": UUID("33333333-3333-3333-3333-333333333333"),
            "source_id": values["source_id"],
            "artifact_uri": values["artifact_uri"],
            "content_hash": values["content_hash"],
            "hash_algorithm": values["hash_algorithm"],
            "content_type": values["content_type"],
            "content_length": values["content_length"],
            "acquisition_channel": values["acquisition_channel"],
            "acquired_at": values["acquired_at"],
            "acquired_by": values["acquired_by"],
            "status": values["status"],
            "source_version": values["source_version"],
            "validation_notes": values["validation_notes"],
        }
        self.rows.append(row)
        return row

    def list_for_source(self, source_id):
        return [row for row in self.rows if row["source_id"] == source_id]


class IngestionFoundationTests(unittest.TestCase):
    def test_valid_acquisition_metadata_is_registered(self):
        service = SourceAcquisitionService(
            source_repository=FakeSourceRepository(),
            artifact_repository=FakeArtifactRepository(),
        )
        acquired = service.register_acquisition(
            source_id=SOURCE_ID,
            artifact_uri="https://example.gov.ng/storage/seed-guidance.pdf",
            acquisition_channel="http_download",
            source_version="2026.01",
            content_hash="abc123sha256",
            content_length=2451,
            content_type="application/pdf",
            acquired_by="system",
            validation_notes="Downloaded and structurally characterized.",
        )

        self.assertEqual(acquired["source_id"], SOURCE_ID)
        self.assertEqual(acquired["artifact_uri"], "https://example.gov.ng/storage/seed-guidance.pdf")
        self.assertEqual(acquired["acquisition_channel"], "http_download")
        self.assertEqual(acquired["hash_algorithm"], "sha256")
        self.assertEqual(acquired["status"], "validated")

    def test_incomplete_acquisition_metadata_is_rejected(self):
        service = SourceAcquisitionService(
            source_repository=FakeSourceRepository(),
            artifact_repository=FakeArtifactRepository(),
        )
        with self.assertRaises(AcquisitionValidationError):
            service.register_acquisition(
                source_id=SOURCE_ID,
                artifact_uri="",
                acquisition_channel="http_download",
                content_hash="abc123",
                content_length=0,
                content_type="application/pdf",
            )

    def test_historical_artifacts_are_not_overwritten(self):
        artifact_repository = FakeArtifactRepository()
        service = SourceAcquisitionService(
            source_repository=FakeSourceRepository(),
            artifact_repository=artifact_repository,
        )
        service.register_acquisition(
            source_id=SOURCE_ID,
            artifact_uri="https://example.gov.ng/seed-guidance-v1.pdf",
            acquisition_channel="http_download",
            source_version="2026.01",
            content_hash="hash-v1",
            content_length=10,
            content_type="application/pdf",
            acquired_by="system",
        )
        service.register_acquisition(
            source_id=SOURCE_ID,
            artifact_uri="https://example.gov.ng/seed-guidance-v2.pdf",
            acquisition_channel="http_download",
            source_version="2026.02",
            content_hash="hash-v2",
            content_length=12,
            content_type="application/pdf",
            acquired_by="system",
        )

        rows = artifact_repository.list_for_source(SOURCE_ID)
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["content_hash"] for row in rows}, {"hash-v1", "hash-v2"})

    def test_provenance_and_source_distinction_are_preserved(self):
        artifact_repository = FakeArtifactRepository()
        service = SourceAcquisitionService(
            source_repository=FakeSourceRepository(),
            artifact_repository=artifact_repository,
        )
        acquired = service.register_acquisition(
            source_id=SOURCE_ID,
            artifact_uri="https://example.gov.ng/seed-guidance.pdf",
            acquisition_channel="manual_upload",
            source_version="2026.01",
            content_hash="hash-provenance",
            content_length=900,
            content_type="application/pdf",
            acquired_by="operator@example.invalid",
            validation_notes="Uploaded to preserve provenance.",
        )

        self.assertEqual(acquired["source_id"], SOURCE_ID)
        self.assertEqual(acquired["acquired_by"], "operator@example.invalid")
        self.assertTrue(acquired["validation_notes"].startswith("Uploaded"))


if __name__ == "__main__":
    unittest.main()
