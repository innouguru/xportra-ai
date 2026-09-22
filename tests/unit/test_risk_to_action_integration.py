"""Focused unit tests for Phase 3.4 — RiskToActionIntegration."""

import unittest
from uuid import UUID, uuid4

from xportra.domain.ingestion import (
    ApplicabilityContext,
    ApplicabilityToRiskIntegration,
    ComplianceActionRecommendationService,
    ComplianceApplicabilityService,
    ComplianceRiskService,
    ComplianceSummaryValidationError,
)
from xportra.domain.ingestion import RiskToActionIntegration

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

class RiskToActionIntegrationTests(unittest.TestCase):
    """Test Phase 3.4 risk-to-action integration boundary."""

    def setUp(self) -> None:
        self.tenant_id = TENANT_ID
        self.integration = RiskToActionIntegration()
        self.risk_integration = ApplicabilityToRiskIntegration()
        self.applicability_service = ComplianceApplicabilityService()
        self.context = ApplicabilityContext(
            tenant_id=self.tenant_id,
            destination_country="ng",
            commodity="cocoa",
            actor_role="exporter",
        )

    def _make_applicable_report(self, outcomes: list[tuple[str, str]]) -> dict:
        """Create an applicability report with specified outcomes.
        
        Args:
            outcomes: List of (requirement_text, expected_outcome) tuples
            
        Returns:
            Mock applicability report structure
        """
        results = []
        for i, (text, outcome) in enumerate(outcomes):
            req_id = UUID(f"11111111-1111-1111-1111-{str(i).zfill(12)}")
            result = {
                "id": uuid4(),
                "tenant_id": self.tenant_id,
                "requirement_id": req_id,
                "context_fingerprint": "abc123",
                "outcome": outcome,
                "reason": f"test reason for {outcome}",
                "context": {},
                "status": "evaluated",
                "requirement": {
                    "id": req_id,
                    "text": text,
                    "type": "documentation",
                },
            }
            results.append(result)

        return {
            "tenant_id": self.tenant_id,
            "context_fingerprint": "abc123",
            "total_requirements": len(results),
            "applicable_count": sum(1 for _, o in outcomes if o == "applicable"),
            "not_applicable_count": sum(1 for _, o in outcomes if o == "not_applicable"),
            "unknown_count": sum(1 for _, o in outcomes if o == "unknown"),
            "results": results,
            "status": "determined",
        }

    def _make_risk_case(
        self,
        requirement_id: UUID,
        assessment: str = "unknown",
        evidence=None,
    ) -> dict:
        """Create a risk-classified case for testing."""
        return {
            "tenant_id": self.tenant_id,
            "context": {"destination_country": "ng", "commodity": "cocoa"},
            "context_fingerprint": "test123",
            "requirement": {
                "id": requirement_id,
                "text": "Test requirement",
                "type": "documentation",
            },
            "applicability": {
                "outcome": "applicable",
                "reason": "matched destination",
            },
            "assessment": {
                "outcome": assessment,
                "reason": "test assessment reason",
            },
            "evidence": evidence or [],
        }

    # Test 1: High-risk produces address_requirement action
    def test_high_risk_provides_address_requirement(self) -> None:
        """High-risk (not_satisfied) should recommend addressing the requirement."""
        req_id = UUID("11111111-1111-1111-1111-111111111111")
        case = self._make_risk_case(req_id, assessment="not_satisfied")

        recommendations = self.integration.recommend_from_risk(
            [case], tenant_id=self.tenant_id
        )

        self.assertEqual(len(recommendations), 1)
        self.assertEqual(recommendations[0]["action_type"], "address_requirement")
        self.assertEqual(
            recommendations[0]["explanation"],
            "assessment not_satisfied; address requirement"
        )
        self.assertEqual(recommendations[0]["risk_state"], "high")

    # Test 2: Medium-risk (missing evidence) produces provide_missing_evidence
    def test_medium_risk_provides_provide_evidence_action(self) -> None:
        """Medium-risk (unknown + missing evidence) should recommend providing evidence."""
        req_id = UUID("22222222-2222-2222-2222-222222222222")
        case = self._make_risk_case(req_id, assessment="unknown", evidence=[])

        recommendations = self.integration.recommend_from_risk(
            [case], tenant_id=self.tenant_id
        )

        self.assertEqual(len(recommendations), 1)
        self.assertEqual(recommendations[0]["action_type"], "provide_missing_evidence")
        self.assertIn("provide missing evidence", recommendations[0]["explanation"])
        self.assertEqual(recommendations[0]["risk_state"], "medium")

    # Test 3: Low-risk (satisfied) produces no_action_required
    def test_low_risk_produces_no_action(self) -> None:
        """Low-risk (satisfied) should not create unnecessary escalation."""
        req_id = UUID("33333333-3333-3333-3333-333333333333")
        case = self._make_risk_case(req_id, assessment="satisfied", evidence=[{"id": uuid4()}])

        recommendations = self.integration.recommend_from_risk(
            [case], tenant_id=self.tenant_id
        )

        self.assertEqual(len(recommendations), 1)
        self.assertEqual(recommendations[0]["action_type"], "no_action_required")
        self.assertEqual(
            recommendations[0]["explanation"],
            "assessment satisfied; no action required"
        )

    # Test 4: Unknown/insufficient state handled per existing semantics
    def test_unknown_state_handled_correctly(self) -> None:
        """Unknown assessment without missing evidence should recommend review."""
        req_id = UUID("44444444-4444-4444-4444-444444444444")
        # Create case with unknown assessment but WITH some evidence
        case = self._make_risk_case(
            req_id,
            assessment="unknown",
            evidence=[{"id": uuid4(), "type": "partial"}]
        )

        recommendations = self.integration.recommend_from_risk(
            [case], tenant_id=self.tenant_id
        )

        self.assertEqual(len(recommendations), 1)
        self.assertEqual(recommendations[0]["action_type"], "review_requirement")
        self.assertIn("review requirement", recommendations[0]["explanation"])

    # Test 5: Multiple conditions produce deterministic output
    def test_multiple_conditions_deterministic_output(self) -> None:
        """Multiple compliance conditions should produce deterministic actions."""
        # Create cases with different assessments and appropriate evidence
        case1 = self._make_risk_case(
            UUID("11111111-1111-1111-1111-000000000001"),
            assessment="not_satisfied"
        )
        case2 = self._make_risk_case(
            UUID("11111111-1111-1111-1111-000000000002"),
            assessment="satisfied",
            evidence=[{"id": uuid4(), "type": "document"}]
        )
        case3 = self._make_risk_case(
            UUID("11111111-1111-1111-1111-000000000003"),
            assessment="unknown",
            evidence=[{"id": uuid4(), "type": "partial"}]  # Has some evidence → review_requirement
        )
        cases = [case1, case2, case3]
        recommendations1 = self.integration.recommend_from_risk(
            cases, tenant_id=self.tenant_id
        )
        recommendations2 = self.integration.recommend_from_risk(
            cases, tenant_id=self.tenant_id
        )

        # Deterministic: identical input → identical output
        self.assertEqual(recommendations1, recommendations2)

        # Should have 3 recommendations (all applicable)
        self.assertEqual(len(recommendations1), 3)

        # Actions should be ordered by requirement ID (deterministic ordering)
        action_types = [r["action_type"] for r in recommendations1]
        self.assertIn("address_requirement", action_types)
        self.assertIn("no_action_required", action_types)
        self.assertIn("review_requirement", action_types)

    # Test 6: Tenant identity preserved
    def test_tenant_identity_preserved(self) -> None:
        """Tenant ID must be preserved throughout integration."""
        req_id = UUID("55555555-5555-5555-5555-555555555555")
        case = self._make_risk_case(req_id)

        recommendations = self.integration.recommend_from_risk(
            [case], tenant_id=self.tenant_id
        )

        self.assertEqual(recommendations[0]["tenant_id"], self.tenant_id)

    # Test 7: Identical input produces identical actions
    def test_identical_input_identical_actions(self) -> None:
        """Determinism: same input must always produce same output."""
        req_id = UUID("66666666-6666-6666-6666-666666666666")
        case = self._make_risk_case(req_id, assessment="unknown", evidence=[])

        # Run 3 times with identical input
        results = [
            self.integration.recommend_from_risk([case], tenant_id=self.tenant_id)
            for _ in range(3)
        ]

        # All must be identical
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])

    # Test 8: Existing ActionRecommendationService behavior unchanged
    def test_existing_action_service_unchanged(self) -> None:
        """Verify we're reusing existing logic, not duplicating it."""
        original_service = ComplianceActionRecommendationService()
        integration_service = RiskToActionIntegration(action_service=original_service)

        req_id = UUID("77777777-7777-7777-7777-777777777777")
        case = self._make_risk_case(req_id, assessment="not_satisfied")

        # Get result through integration
        integration_result = integration_service.recommend_from_risk(
            [case], tenant_id=self.tenant_id
        )

        # Get result directly from action service
        direct_result = original_service.recommend(
            [case], tenant_id=self.tenant_id
        )

        # Results must be identical - proving we're just wrapping
        self.assertEqual(integration_result, direct_result)

    # Test 9: Existing RiskService behavior unchanged
    def test_existing_risk_service_unchanged(self) -> None:
        """Existing risk service must remain unchanged after integration."""
        risk_service = ComplianceRiskService()
        
        req_id = UUID("88888888-8888-8888-8888-888888888888")
        case = self._make_risk_case(req_id, assessment="not_satisfied")

        # Direct classification still works
        classified = risk_service.classify([case], tenant_id=self.tenant_id)
        self.assertEqual(len(classified), 1)
        self.assertEqual(classified[0]["state"], "high")

    # Test 10: End-to-end pipeline (Applicability → Risk → Action)
    def test_end_to_end_pipeline(self) -> None:
        """Complete deterministic flow: Applicability → Risk → Action."""
        report = self._make_applicable_report([
            ("Cocoa exports require phytosanitary certificate", "applicable"),
            ("Wheat exports require inspection", "not_applicable"),
            ("Sesame exports require analysis", "unknown"),
            ("Exporters must maintain records", "applicable"),
        ])

        # Run full pipeline
        result = self.integration.full_pipeline(
            report, tenant_id=self.tenant_id
        )

        # Verify structure
        self.assertIn("risk_results", result)
        self.assertIn("action_recommendations", result)
        self.assertIn("pipeline_metadata", result)

        # Verify metadata
        meta = result["pipeline_metadata"]
        self.assertEqual(meta["tenant_id"], self.tenant_id)
        self.assertEqual(meta["status"], "complete")
        self.assertGreater(meta["total_risk_classified"], 0)

        # Verify risk results exist (from Phase 3.3)
        risk_results = result["risk_results"]
        self.assertIsInstance(risk_results, list)
        # Only applicable requirements should be risk-classified
        self.assertEqual(len(risk_results), 2)  # 2 applicable out of 4

        # Verify action recommendations exist (Phase 3.4)
        actions = result["action_recommendations"]
        self.assertIsInstance(actions, list)
        self.assertGreater(len(actions), 0)

        # All applicable requirements should have actions
        for action in actions:
            self.assertEqual(action["tenant_id"], self.tenant_id)
            self.assertIn("action_type", action)
            self.assertIn("explanation", action)
            self.assertIn("risk_state", action)

    # Additional edge case tests
    def test_empty_risk_list(self) -> None:
        """Empty risk list should return empty recommendations."""
        recommendations = self.integration.recommend_from_risk(
            [], tenant_id=self.tenant_id
        )
        self.assertEqual(recommendations, [])

    def test_invalid_input_not_list(self) -> None:
        """Non-list input should raise validation error."""
        with self.assertRaises(ComplianceSummaryValidationError):
            self.integration.recommend_from_risk(
                "not a list", tenant_id=self.tenant_id
            )

    def test_invalid_tenant_id(self) -> None:
        """Non-UUID tenant_id should raise validation error."""
        case = self._make_risk_case(UUID("99999999-9999-9999-9999-999999999999"))

        with self.assertRaises(ComplianceSummaryValidationError):
            self.integration.recommend_from_risk(
                [case], tenant_id="not-a-uuid"
            )

    def test_not_applicable_excluded_from_actions(self) -> None:
        """Not-applicable requirements should not generate actions."""
        req_id = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
        case = self._make_risk_case(req_id)
        case["applicability"]["outcome"] = "not_applicable"

        recommendations = self.integration.recommend_from_risk(
            [case], tenant_id=self.tenant_id
        )

        # Not-applicable should be excluded
        self.assertEqual(len(recommendations), 0)

    def test_full_pipeline_with_all_applicable(self) -> None:
        """Full pipeline where all requirements are applicable."""
        report = self._make_applicable_report([
            ("Requirement 1", "applicable"),
            ("Requirement 2", "applicable"),
            ("Requirement 3", "applicable"),
        ])

        result = self.integration.full_pipeline(
            report, tenant_id=self.tenant_id
        )

        # All 3 should be risk-classified
        self.assertEqual(result["pipeline_metadata"]["total_risk_classified"], 3)
        # All 3 should have action recommendations
        self.assertEqual(result["pipeline_metadata"]["total_actions"], 3)

        # All should have medium risk (unknown assessment + no evidence)
        for r in result["risk_results"]:
            self.assertEqual(r["state"], "medium")

        # All should recommend providing missing evidence
        for action in result["action_recommendations"]:
            self.assertEqual(action["action_type"], "provide_missing_evidence")

if __name__ == "__main__":
    unittest.main()