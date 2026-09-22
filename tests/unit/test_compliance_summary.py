import unittest
from uuid import UUID

from xportra.domain.ingestion import (
    ComplianceSummaryService,
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


class ComplianceSummaryTests(unittest.TestCase):
    def setUp(self):
        self.cases = [
            make_case("11111111-1111-1111-1111-111111111111", "applicable", "satisfied", "required evidence present", [{"evidence_id": UUID("aaaaaaaa-1111-1111-1111-111111111111")}]),
            make_case("11111111-2222-2222-2222-222222222222", "applicable", "not_satisfied", "evidence rejected"),
            make_case("11111111-3333-3333-3333-333333333333", "applicable", "unknown", "required evidence absent"),
            make_case("11111111-4444-4444-4444-444444444444", "unknown", "unknown", "requirement cannot yet be assessed"),
            make_case("11111111-5555-5555-5555-555555555555", "not_applicable", "unknown", "requirement cannot yet be assessed"),
        ]

    def test_counts_and_outcomes_are_preserved(self):
        summary = ComplianceSummaryService().summarize(self.cases, tenant_id=TENANT_ID)

        self.assertEqual(summary["total_applicable_requirements"], 3)
        self.assertEqual(summary["satisfied_requirements"], 1)
        self.assertEqual(summary["not_satisfied_requirements"], 1)
        self.assertEqual(summary["unknown_requirements"], 2)
        self.assertEqual(summary["requirements_missing_evidence"], 1)
        self.assertEqual(summary["requirements_requiring_review"], 2)

    def test_non_applicable_is_excluded_and_unknown_applicability_requires_review(self):
        summary = ComplianceSummaryService().summarize(self.cases, tenant_id=TENANT_ID)
        affected_ids = {item["requirement_id"] for item in summary["affected_requirements"]}

        self.assertNotIn(UUID("11111111-5555-5555-5555-555555555555"), affected_ids)
        self.assertIn(UUID("11111111-4444-4444-4444-444444444444"), affected_ids)

    def test_missing_evidence_and_provenance_are_exposed(self):
        summary = ComplianceSummaryService().summarize(self.cases, tenant_id=TENANT_ID)
        missing = summary["missing_evidence_requirements"]

        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["requirement_id"], UUID("11111111-3333-3333-3333-333333333333"))
        self.assertEqual(missing[0]["regulatory_source"]["title"], "Export Rules")
        self.assertEqual(missing[0]["document_metadata"]["version"], "2026.1")

    def test_empty_case_set_is_deterministic(self):
        expected = {
            "tenant_id": TENANT_ID,
            "total_cases": 0,
            "total_applicable_requirements": 0,
            "satisfied_requirements": 0,
            "not_satisfied_requirements": 0,
            "unknown_requirements": 0,
            "requirements_missing_evidence": 0,
            "requirements_requiring_review": 0,
            "affected_requirements": [],
            "missing_evidence_requirements": [],
            "status": "summary",
        }

        self.assertEqual(ComplianceSummaryService().summarize([], tenant_id=TENANT_ID), expected)

    def test_tenant_isolation_rejects_other_tenant_case(self):
        other = {**self.cases[0], "tenant_id": OTHER_TENANT_ID}

        with self.assertRaises(ComplianceSummaryValidationError):
            ComplianceSummaryService().summarize([self.cases[0], other], tenant_id=TENANT_ID)

    def test_repeated_output_is_deterministic(self):
        service = ComplianceSummaryService()
        first = service.summarize(self.cases, tenant_id=TENANT_ID)
        second = service.summarize(list(reversed(self.cases)), tenant_id=TENANT_ID)

        self.assertEqual(first, second)
        self.assertNotIn("score", first)
        self.assertNotIn("recommendations", first)
        self.assertNotIn("priority", first)

    def test_invalid_case_or_tenant_is_rejected(self):
        with self.assertRaises(ComplianceSummaryValidationError):
            ComplianceSummaryService().summarize([{}], tenant_id=TENANT_ID)

        with self.assertRaises(ComplianceSummaryValidationError):
            ComplianceSummaryService().summarize([], tenant_id=None)


if __name__ == "__main__":
    unittest.main()
