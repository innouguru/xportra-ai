import unittest
from uuid import UUID

from xportra.domain.ingestion import (
    ComplianceCaseService,
    ComplianceCaseValidationError,
    EvidenceRecord,
)

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
REQUIREMENT_ID = UUID("11111111-1111-1111-1111-111111111111")
APPLICABILITY_ID = UUID("22222222-2222-2222-2222-222222222222")
ASSESSMENT_ID = UUID("33333333-3333-3333-3333-333333333333")
EVIDENCE_ID = UUID("44444444-4444-4444-4444-444444444444")


class ComplianceCaseTests(unittest.TestCase):
    def setUp(self):
        self.applicability = {
            "id": APPLICABILITY_ID,
            "tenant_id": TENANT_ID,
            "requirement_id": REQUIREMENT_ID,
            "context_fingerprint": "context-hash",
            "outcome": "applicable",
            "reason": "matched destination",
            "created_at": "2026-09-21T10:00:00Z",
            "status": "evaluated",
        }
        self.requirement = {
            "id": REQUIREMENT_ID,
            "normalized_document_id": UUID("55555555-5555-5555-5555-555555555555"),
            "artifact_id": UUID("66666666-6666-6666-6666-666666666666"),
            "source_id": UUID("77777777-7777-7777-7777-777777777777"),
            "requirement_text": "Exporters shall submit a certificate.",
            "requirement_type": "documentation",
            "source_location": {"section_order": 2, "heading": "Documents"},
        }
        self.evidence = EvidenceRecord(
            tenant_id=TENANT_ID,
            evidence_id=EVIDENCE_ID,
            evidence_type="certificate",
            reference="vault://certificate-1",
            requirement_id=REQUIREMENT_ID,
            status="accepted",
            metadata={"supports_requirement": True},
        )
        self.assessment = {
            "id": ASSESSMENT_ID,
            "tenant_id": TENANT_ID,
            "requirement_id": REQUIREMENT_ID,
            "applicability_result_id": APPLICABILITY_ID,
            "evidence_ids": [EVIDENCE_ID],
            "evidence_id": EVIDENCE_ID,
            "outcome": "satisfied",
            "reason": "required evidence present",
            "created_at": "2026-09-21T10:01:00Z",
            "status": "assessed",
        }

    def test_complete_case_aggregation_preserves_links(self):
        case = ComplianceCaseService().build(
            self.applicability,
            self.requirement,
            self.assessment,
            [self.evidence],
            regulatory_source={"id": self.requirement["source_id"], "title": "Export Rules"},
            document_metadata={"document_title": "Export Regulation", "version": "2026.1"},
        )

        self.assertEqual(case["tenant_id"], TENANT_ID)
        self.assertEqual(case["requirement"]["id"], REQUIREMENT_ID)
        self.assertEqual(case["applicability"]["outcome"], "applicable")
        self.assertEqual(case["assessment"]["outcome"], "satisfied")
        self.assertEqual(case["evidence"][0]["evidence_id"], EVIDENCE_ID)
        self.assertEqual(case["regulatory_source"]["title"], "Export Rules")
        self.assertEqual(case["document_metadata"]["version"], "2026.1")

    def test_not_satisfied_and_unknown_assessment_states_are_preserved(self):
        not_satisfied = ComplianceCaseService().build(
            self.applicability,
            self.requirement,
            {**self.assessment, "outcome": "not_satisfied", "reason": "evidence rejected"},
            [self.evidence],
        )
        unknown = ComplianceCaseService().build(
            self.applicability,
            self.requirement,
            {**self.assessment, "outcome": "unknown", "reason": "evidence insufficient"},
            [self.evidence],
        )

        self.assertEqual(not_satisfied["assessment"]["outcome"], "not_satisfied")
        self.assertEqual(unknown["assessment"]["outcome"], "unknown")

    def test_unknown_or_non_applicable_context_does_not_become_satisfied(self):
        unknown_case = ComplianceCaseService().build(
            {**self.applicability, "outcome": "unknown"},
            self.requirement,
            self.assessment,
            [self.evidence],
        )
        not_applicable_case = ComplianceCaseService().build(
            {**self.applicability, "outcome": "not_applicable"},
            self.requirement,
            None,
            [],
        )

        self.assertEqual(unknown_case["applicability"]["outcome"], "unknown")
        self.assertEqual(unknown_case["assessment"]["outcome"], "unknown")
        self.assertEqual(not_applicable_case["applicability"]["outcome"], "not_applicable")
        self.assertEqual(not_applicable_case["assessment"]["outcome"], "unknown")

    def test_missing_evidence_is_visible_as_empty_references(self):
        case = ComplianceCaseService().build(self.applicability, self.requirement, None, [])

        self.assertEqual(case["evidence"], [])
        self.assertEqual(case["assessment"]["outcome"], "unknown")

    def test_tenant_isolation_rejects_other_tenant_records(self):
        with self.assertRaises(ComplianceCaseValidationError):
            ComplianceCaseService().build(
                self.applicability,
                self.requirement,
                self.assessment,
                [EvidenceRecord(
                    tenant_id=OTHER_TENANT_ID,
                    evidence_id=EVIDENCE_ID,
                    evidence_type="certificate",
                    reference="vault://other-tenant",
                )],
            )

    def test_provenance_and_output_are_deterministic(self):
        service = ComplianceCaseService()
        first = service.build(self.applicability, self.requirement, self.assessment, [self.evidence])
        second = service.build(self.applicability, self.requirement, self.assessment, [self.evidence])

        self.assertEqual(first, second)
        self.assertEqual(first["provenance"], {
            "assessment_id": ASSESSMENT_ID,
            "applicability_result_id": APPLICABILITY_ID,
            "requirement_id": REQUIREMENT_ID,
            "normalized_document_id": self.requirement["normalized_document_id"],
            "artifact_id": self.requirement["artifact_id"],
            "source_id": self.requirement["source_id"],
        })

    def test_mismatched_requirement_or_invalid_input_is_rejected(self):
        with self.assertRaises(ComplianceCaseValidationError):
            ComplianceCaseService().build(self.applicability, {**self.requirement, "id": OTHER_TENANT_ID}, None, [])

        with self.assertRaises(ComplianceCaseValidationError):
            ComplianceCaseService().build({}, self.requirement, None, [])


if __name__ == "__main__":
    unittest.main()
