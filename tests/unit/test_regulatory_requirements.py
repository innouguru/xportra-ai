import unittest
from uuid import UUID

from xportra.domain.ingestion import (
    RegulatoryRequirementExtractionError,
    RegulatoryRequirementExtractionService,
)

ARTIFACT_ID = UUID("11111111-2222-3333-4444-555555555555")
SOURCE_ID = UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
DOCUMENT_ID = UUID("99999999-8888-7777-6666-555555555555")


class FakeRequirementRepository:
    def __init__(self):
        self.rows = {}

    def list_for_document(self, document_id):
        return list(self.rows.get(str(document_id), {}).values())

    def create(self, **values):
        row = {"id": values["id"], **values}
        self.rows.setdefault(str(values["normalized_document_id"]), {})[str(row["id"])] = row
        return row


class RegulatoryRequirementExtractionTests(unittest.TestCase):
    def setUp(self):
        self.document = {
            "id": DOCUMENT_ID,
            "artifact_id": ARTIFACT_ID,
            "source_id": SOURCE_ID,
            "normalized_content": {
                "structure": [
                    {
                        "order": 0,
                        "heading": "Export obligations",
                        "level": 2,
                        "parent_index": None,
                        "text": (
                            "Exporters shall submit a phytosanitary certificate. "
                            "Exporters must not ship untreated seed."
                        ),
                    },
                    {
                        "order": 1,
                        "heading": "Records and inspections",
                        "level": 2,
                        "parent_index": None,
                        "text": (
                            "The exporter must keep records for at least five years. "
                            "The authority may inspect consignments when risk indicators are present. "
                            "The authority publishes an annual report. "
                            "Exporters should use approved packaging."
                        ),
                    },
                ]
            },
        }

    def test_extracts_obligation_prohibition_documentation_and_inspection(self):
        records = RegulatoryRequirementExtractionService().extract(self.document)
        types = [record["requirement_type"] for record in records]

        self.assertEqual(types, ["documentation", "prohibition", "recordkeeping", "inspection"])

    def test_extracts_threshold_and_explicit_actor(self):
        records = RegulatoryRequirementExtractionService().extract(self.document)
        record = records[2]

        self.assertEqual(record["actor"], "The exporter")
        self.assertEqual(record["requirement_type"], "recordkeeping")
        self.assertEqual(record["condition_metadata"], {"threshold": "at least five years"})

    def test_rejects_descriptive_and_ambiguous_statements(self):
        records = RegulatoryRequirementExtractionService().extract(self.document)
        wording = [record["requirement_text"] for record in records]

        self.assertFalse(any("annual report" in text for text in wording))
        self.assertFalse(any("approved packaging" in text for text in wording))

    def test_preserves_source_location_and_provenance(self):
        record = RegulatoryRequirementExtractionService().extract(self.document)[0]

        self.assertEqual(record["normalized_document_id"], DOCUMENT_ID)
        self.assertEqual(record["artifact_id"], ARTIFACT_ID)
        self.assertEqual(record["source_id"], SOURCE_ID)
        self.assertEqual(record["source_location"], {"section_order": 0, "heading": "Export obligations"})
        self.assertEqual(record["position"], 0)

    def test_deterministic_identity_and_no_applicability_inference(self):
        service = RegulatoryRequirementExtractionService()
        first = service.extract(self.document)
        second = service.extract(self.document)

        self.assertEqual(first, second)
        self.assertTrue(all("applies_to_exporter" not in record for record in first))
        self.assertTrue(all("applies_to_commodity" not in record for record in first))
        self.assertTrue(all("applies_to_destination" not in record for record in first))
        self.assertTrue(all(record["id"] is not None for record in first))

    def test_repeated_processing_is_idempotent(self):
        repository = FakeRequirementRepository()
        service = RegulatoryRequirementExtractionService(repository=repository)

        first = service.process(self.document)
        second = service.process(self.document)

        self.assertEqual(first, second)
        self.assertEqual(len(repository.list_for_document(DOCUMENT_ID)), 4)

    def test_empty_or_invalid_document_is_rejected(self):
        with self.assertRaises(RegulatoryRequirementExtractionError):
            RegulatoryRequirementExtractionService().extract({})

        empty_document = {
            "id": DOCUMENT_ID,
            "artifact_id": ARTIFACT_ID,
            "source_id": SOURCE_ID,
            "normalized_content": {"structure": []},
        }
        self.assertEqual(RegulatoryRequirementExtractionService().extract(empty_document), [])

    def test_explicit_condition_is_preserved(self):
        document = {**self.document}
        document["normalized_content"] = {
            "structure": [{
                "order": 0,
                "heading": "Notifications",
                "level": 2,
                "parent_index": None,
                "text": "Exporters shall notify the authority if the shipment is delayed.",
            }]
        }

        record = RegulatoryRequirementExtractionService().extract(document)[0]

        self.assertEqual(record["requirement_type"], "notification")
        self.assertEqual(record["condition_metadata"], {"condition": "if the shipment is delayed"})

    def test_extracts_threshold_and_procedure_types(self):
        document = {**self.document}
        document["normalized_content"] = {
            "structure": [{
                "order": 0,
                "heading": "Controls",
                "level": 2,
                "parent_index": None,
                "text": (
                    "The shipment quantity must be at least 20 kilograms. "
                    "Exporters must follow the inspection procedure."
                ),
            }]
        }

        records = RegulatoryRequirementExtractionService().extract(document)

        self.assertEqual([record["requirement_type"] for record in records], ["threshold", "procedure"])
        self.assertEqual(records[0]["condition_metadata"], {"threshold": "at least 20 kilograms"})


if __name__ == "__main__":
    unittest.main()
