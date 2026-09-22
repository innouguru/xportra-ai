import unittest
from uuid import UUID

from xportra.domain.ingestion import (
    ComplianceRiskService,
    ComplianceSummaryValidationError,
)

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


def make_case(
    requirement_id,
    applicability_outcome,
    assessment_outcome="unknown",
    reason="evidence insufficient",
    evidence=None,
):
    return {
        "id": UUID(requirement_id.replace("1", "2")),
        "tenant_id": TENANT_ID,
        "requirement": {
            "id": UUID(requirement_id),
            "text": "Exporters shall submit evidence.",
            "type": "documentation",
        },
        "applicability": {
            "id": UUID(requirement_id.replace("1", "3")),
            "outcome": applicability_outcome,
            "reason": "matched destination" if applicability_outcome == "applicable" else "insufficient context",
        },
        "assessment": {
            "id": UUID(requirement_id.replace("1", "4")) if assessment_outcome else None,
            "outcome": assessment_outcome,
            "reason": reason,
        },
        "evidence": evidence or [],
        "regulatory_source": {"id": UUID("77777777-7777-7777-7777-777777777777"), "title": "Export Rules"},
        "document_metadata": {"id": UUID("66666666-6666-6666-6666-666666666666"), "version": "2026.1"},
        "provenance": {"source_id": UUID("77777777-7777-7777-7777-777777777777")},
    }


class ComplianceRiskTests(unittest.TestCase):
    def setUp(self):
        self.cases = [
            make_case("11111111-1111-1111-1111-111111111111", "applicable", "satisfied", "required evidence present", [{"evidence_id": UUID("aaaaaaaa-1111-1111-1111-111111111111")}]),
            make_case("11111111-2222-2222-2222-222222222222", "applicable", "not_satisfied", "evidence rejected"),
            make_case("11111111-3333-3333-3333-333333333333", "applicable", "unknown", "required evidence absent"),
            make_case("11111111-4444-4444-4444-444444444444", "unknown", "unknown", "requirement cannot yet be assessed"),
            make_case("11111111-5555-5555-5555-555555555555", "not_applicable", "unknown", "requirement cannot yet be assessed"),
        ]

    def test_satisfied_low(self):
        service = ComplianceRiskService()
        summary = service.classify(self.cases, tenant_id=TENANT_ID)
        satisfied = [r for r in summary if r["requirement_id"] == UUID("11111111-1111-1111-1111-111111111111")][0]
        self.assertEqual(satisfied["state"], "low")
        self.assertIn("explanation", satisfied)

    def test_not_satisfied_high(self):
        service = ComplianceRiskService()
        summary = service.classify(self.cases, tenant_id=TENANT_ID)
        not_satisfied = [r for r in summary if r["requirement_id"] == UUID("11111111-2222-2222-2222-222222222222")][0]
        self.assertEqual(not_satisfied["state"], "high")
        self.assertEqual(not_satisfied["explanation"], "not_satisfied assessment")

    def test_unknown_missing_evidence_medium(self):
        service = ComplianceRiskService()
        summary = service.classify(self.cases, tenant_id=TENANT_ID)
        unknown_missing = [r for r in summary if r["requirement_id"] == UUID("11111111-3333-3333-3333-333333333333")][0]
        self.assertEqual(unknown_missing["state"], "medium")
        self.assertEqual(unknown_missing["explanation"], "unknown with missing required evidence")

    def test_unknown_no_sufficient_evidence_unknown(self):
        """unknown with evidence present but assessment still unknown → unknown."""
        case_with_evidence = {
            "id": UUID("12345678-1234-5678-1234-567812345678"),
            "tenant_id": TENANT_ID,
            "requirement": {"id": UUID("12345678-1234-5678-1234-567812345678"), "text": "Test", "type": "documentation"},
            "applicability": {"id": UUID("87654321-8765-4321-8765-432187654321"), "outcome": "applicable", "reason": "matched destination"},
            "assessment": {"id": UUID("11111111-1111-1111-1111-111111111111"), "outcome": "unknown", "reason": "evidence insufficient but present"},
            "evidence": [{"evidence_id": UUID("aaaaaaaa-1111-1111-1111-111111111111")}],
            "regulatory_source": {"id": UUID("77777777-7777-7777-7777-777777777777"), "title": "Export Rules"},
            "document_metadata": {"id": UUID("66666666-6666-6666-6666-666666666666"), "version": "2026.1"},
            "provenance": {"source_id": UUID("77777777-7777-7777-7777-777777777777")},
        }
        service = ComplianceRiskService()
        summary = service.classify([case_with_evidence], tenant_id=TENANT_ID)
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["state"], "unknown")
        self.assertEqual(summary[0]["explanation"], "unknown without sufficient evidence")

    def test_not_applicable_excluded(self):
        service = ComplianceRiskService()
        summary = service.classify(self.cases, tenant_id=TENANT_ID)
        not_applicable_ids = {r["requirement_id"] for r in summary}
        self.assertNotIn(UUID("11111111-5555-5555-5555-555555555555"), not_applicable_ids)

    def test_explanation_is_deterministic(self):
        service = ComplianceRiskService()
        first = service.classify(self.cases, tenant_id=TENANT_ID)
        second = service.classify(list(reversed(self.cases)), tenant_id=TENANT_ID)

        self.assertEqual(
            sorted(first, key=lambda r: str(r["requirement_id"])),
            sorted(second, key=lambda r: str(r["requirement_id"])),
        )
        for item in first:
            self.assertIn("explanation", item)

    def test_provenance_preserved(self):
        service = ComplianceRiskService()
        summary = service.classify(self.cases, tenant_id=TENANT_ID)
        for item in summary:
            self.assertIn("provenance", item)
            self.assertIn("regulatory_source", item)
            self.assertIn("document_metadata", item)

    def test_tenant_isolation_rejects_other_tenant_case(self):
        other = {**self.cases[0], "tenant_id": OTHER_TENANT_ID}

        with self.assertRaises(ComplianceSummaryValidationError):
            ComplianceRiskService().classify([self.cases[0], other], tenant_id=TENANT_ID)

    def test_empty_case_set_is_deterministic(self):
        expected = []

        self.assertEqual(ComplianceRiskService().classify([], tenant_id=TENANT_ID), expected)

    def test_applicable_only_classified_not_applicable_omitted(self):
        service = ComplianceRiskService()
        cases_with_only_not_applicable = [
            make_case("11111111-5555-5555-5555-555555555555", "not_applicable", "unknown"),
        ]
        summary = service.classify(cases_with_only_not_applicable, tenant_id=TENANT_ID)
        self.assertEqual(len(summary), 0)

    def test_missing_evidence_detection_reason(self):
        """Verify that missing evidence is detected by reason and empty evidence list."""
        # Case with explicit "required evidence absent" reason + no evidence
        case_missing = {
            "id": UUID("12345678-1234-5678-1234-567812345678"),
            "tenant_id": TENANT_ID,
            "requirement": {"id": UUID("12345678-1234-5678-1234-567812345678"), "text": "Test", "type": "documentation"},
            "applicability": {"id": UUID("87654321-8765-4321-8765-432187654321"), "outcome": "applicable", "reason": "matched destination"},
            "assessment": {"id": UUID("11111111-1111-1111-1111-111111111111"), "outcome": "unknown", "reason": "required evidence absent"},
            "evidence": [],
            "regulatory_source": {"id": UUID("77777777-7777-7777-7777-777777777777"), "title": "Export Rules"},
            "document_metadata": {"id": UUID("66666666-6666-6666-6666-666666666666"), "version": "2026.1"},
            "provenance": {"source_id": UUID("77777777-7777-7777-7777-777777777777")},
        }
        service = ComplianceRiskService()
        summary = service.classify([case_missing], tenant_id=TENANT_ID)
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["state"], "medium")
        self.assertEqual(summary[0]["explanation"], "unknown with missing required evidence")


if __name__ == "__main__":
    unittest.main()