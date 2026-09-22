import unittest
from uuid import UUID

from xportra.domain import (
    ComplianceActionRecommendationService,
    ComplianceSummaryValidationError,
)

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
SOURCE_ID = UUID("77777777-7777-7777-7777-777777777777")
DOCUMENT_ID = UUID("66666666-6666-6666-6666-666666666666")
EXPORTER_ID = UUID("99999999-9999-9999-9999-999999999999")


def make_case(
    requirement_id: str,
    applicability_outcome: str,
    assessment_outcome: str = "unknown",
    reason: str = "evidence insufficient",
    evidence=None,
):
    return {
        "id": UUID(requirement_id.replace("1", "2")),
        "tenant_id": TENANT_ID,
        "context": {
            "exporter_id": EXPORTER_ID,
            "destination_country": "Ghana",
            "commodity": "cocoa",
        },
        "context_fingerprint": f"context-{requirement_id}",
        "requirement": {
            "id": UUID(requirement_id),
            "text": "Exporters shall submit evidence.",
            "type": "documentation",
        },
        "applicability": {
            "id": UUID(requirement_id.replace("1", "3")),
            "outcome": applicability_outcome,
            "reason": (
                "matched destination"
                if applicability_outcome == "applicable"
                else "insufficient context"
            ),
        },
        "assessment": {
            "id": UUID(requirement_id.replace("1", "4")),
            "outcome": assessment_outcome,
            "reason": reason,
        },
        "evidence": evidence or [],
        "regulatory_source": {"id": SOURCE_ID, "title": "Export Rules"},
        "document_metadata": {"id": DOCUMENT_ID, "version": "2026.1"},
        "provenance": {
            "source_id": SOURCE_ID,
            "normalized_document_id": DOCUMENT_ID,
            "requirement_id": UUID(requirement_id),
        },
    }


class ComplianceActionRecommendationTests(unittest.TestCase):
    def test_not_satisfied_maps_to_address_requirement(self):
        case = make_case(
            "11111111-1111-1111-1111-111111111111",
            "applicable",
            "not_satisfied",
            "evidence rejected",
        )

        recommendation = ComplianceActionRecommendationService().recommend([case], tenant_id=TENANT_ID)[0]

        self.assertEqual(recommendation["action_type"], "address_requirement")
        self.assertEqual(recommendation["explanation"], "assessment not_satisfied; address requirement")
        self.assertEqual(recommendation["risk_state"], "high")
        self.assertEqual(recommendation["tenant_id"], TENANT_ID)
        self.assertEqual(recommendation["context_fingerprint"], case["context_fingerprint"])

    def test_missing_evidence_maps_to_provide_missing_evidence(self):
        case = make_case(
            "11111111-2222-2222-2222-222222222222",
            "applicable",
            "unknown",
            "required evidence absent",
            [],
        )

        recommendation = ComplianceActionRecommendationService().recommend([case], tenant_id=TENANT_ID)[0]

        self.assertEqual(recommendation["action_type"], "provide_missing_evidence")
        self.assertEqual(
            recommendation["explanation"],
            "assessment unknown with missing required evidence; provide missing evidence",
        )
        self.assertEqual(recommendation["risk_state"], "medium")

    def test_unknown_maps_to_review_requirement(self):
        case = make_case(
            "11111111-3333-3333-3333-333333333333",
            "applicable",
            "unknown",
            "evidence insufficient but present",
            [{"evidence_id": UUID("aaaaaaaa-1111-1111-1111-111111111111")}],
        )

        recommendation = ComplianceActionRecommendationService().recommend([case], tenant_id=TENANT_ID)[0]

        self.assertEqual(recommendation["action_type"], "review_requirement")
        self.assertEqual(
            recommendation["explanation"],
            "assessment unknown without sufficient evidence; review requirement",
        )
        self.assertEqual(recommendation["risk_state"], "unknown")

    def test_satisfied_maps_to_no_action_required(self):
        case = make_case(
            "11111111-4444-4444-4444-444444444444",
            "applicable",
            "satisfied",
            "required evidence present",
            [{"evidence_id": UUID("aaaaaaaa-4444-4444-4444-444444444444")}],
        )

        recommendation = ComplianceActionRecommendationService().recommend([case], tenant_id=TENANT_ID)[0]

        self.assertEqual(recommendation["action_type"], "no_action_required")
        self.assertEqual(recommendation["explanation"], "assessment satisfied; no action required")
        self.assertEqual(recommendation["risk_state"], "low")

    def test_not_applicable_excluded(self):
        case = make_case(
            "11111111-5555-5555-5555-555555555555",
            "not_applicable",
            "unknown",
            "requirement cannot yet be assessed",
        )

        recommendations = ComplianceActionRecommendationService().recommend([case], tenant_id=TENANT_ID)

        self.assertEqual(recommendations, [])

    def test_explanation_is_deterministic(self):
        case = make_case(
            "11111111-6666-6666-6666-666666666666",
            "applicable",
            "unknown",
            "required evidence absent",
            [],
        )
        service = ComplianceActionRecommendationService()

        first = service.recommend([case], tenant_id=TENANT_ID)[0]
        second = service.recommend([case], tenant_id=TENANT_ID)[0]

        self.assertEqual(first["explanation"], second["explanation"])
        self.assertEqual(
            first["explanation"],
            "assessment unknown with missing required evidence; provide missing evidence",
        )

    def test_provenance_preserved(self):
        case = make_case(
            "11111111-7777-7777-7777-777777777777",
            "applicable",
            "not_satisfied",
            "evidence rejected",
        )

        recommendation = ComplianceActionRecommendationService().recommend([case], tenant_id=TENANT_ID)[0]

        self.assertEqual(recommendation["regulatory_source"]["title"], "Export Rules")
        self.assertEqual(recommendation["document_metadata"]["version"], "2026.1")
        self.assertEqual(recommendation["provenance"]["source_id"], SOURCE_ID)

    def test_tenant_isolation_rejects_other_tenant_case(self):
        case = make_case(
            "11111111-8888-8888-8888-888888888888",
            "applicable",
            "not_satisfied",
            "evidence rejected",
        )
        other = {**case, "tenant_id": OTHER_TENANT_ID}

        with self.assertRaises(ComplianceSummaryValidationError):
            ComplianceActionRecommendationService().recommend([case, other], tenant_id=TENANT_ID)

    def test_repeated_output_is_deterministic(self):
        cases = [
            make_case(
                "11111111-1111-1111-1111-111111111111",
                "applicable",
                "satisfied",
                "required evidence present",
                [{"evidence_id": UUID("aaaaaaaa-1111-1111-1111-111111111111")}],
            ),
            make_case(
                "11111111-2222-2222-2222-222222222222",
                "applicable",
                "not_satisfied",
                "evidence rejected",
            ),
            make_case(
                "11111111-3333-3333-3333-333333333333",
                "applicable",
                "unknown",
                "required evidence absent",
                [],
            ),
        ]
        service = ComplianceActionRecommendationService()

        first = service.recommend(cases, tenant_id=TENANT_ID)
        second = service.recommend(list(reversed(cases)), tenant_id=TENANT_ID)

        self.assertEqual(first, second)

    def test_empty_case_set(self):
        self.assertEqual(
            ComplianceActionRecommendationService().recommend([], tenant_id=TENANT_ID),
            [],
        )


if __name__ == "__main__":
    unittest.main()
