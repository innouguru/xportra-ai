"""Focused unit tests for Phase 3.3 — ApplicabilityToRiskIntegration."""

import unittest
from uuid import UUID, uuid4

from xportra.domain.ingestion import (
    ApplicabilityContext,
    ApplicabilityToRiskIntegration,
    ComplianceApplicabilityService,
    ComplianceRiskService,
    ComplianceSummaryValidationError,
)

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")

class ApplicabilityToRiskIntegrationTests(unittest.TestCase):
    """Test Phase 3.3 applicability-to-risk integration boundary."""

    def setUp(self) -> None:
        self.tenant_id = TENANT_ID
        self.integration = ApplicabilityToRiskIntegration()
        self.applicability_service = ComplianceApplicabilityService()
        self.context = ApplicabilityContext(
            tenant_id=self.tenant_id,
            destination_country="ng",
            commodity="cocoa",
            actor_role="exporter",
        )

    def _make_requirement(self, text: str, req_id: str | None = None) -> dict:
        return {
            "id": UUID(req_id) if req_id else uuid4(),
            "requirement_text": text,
            "actor": "exporter",
        }

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

    # Test 1: Applicable requirements reach risk classification
    def test_applicable_requirements_classified(self) -> None:
        """Applicable requirements should be classified by risk service."""
        report = self._make_applicable_report([
            ("Exporters shall submit documentation", "applicable"),
        ])
        
        result = self.integration.classify_from_applicability(
            report, tenant_id=self.tenant_id
        )
        
        self.assertEqual(len(result), 1)
        # unknown assessment + empty evidence → medium risk (existing risk service behavior)
        self.assertEqual(result[0]["state"], "medium")
        self.assertEqual(result[0]["explanation"], "unknown with missing required evidence")

    # Test 2: Not-applicable requirements don't create compliance risk
    def test_not_applicable_excluded_from_risk(self) -> None:
        """Not-applicable requirements should be excluded from risk classification."""
        report = self._make_applicable_report([
            ("Wheat exports require inspection", "not_applicable"),
        ])
        
        result = self.integration.classify_from_applicability(
            report, tenant_id=self.tenant_id
        )
        
        # Risk service excludes not_applicable cases
        self.assertEqual(len(result), 0)

    # Test 3: Unknown applicability preserved
    def test_unknown_applicability_preserved(self) -> None:
        """Unknown applicability should be preserved, not treated as applicable."""
        report = self._make_applicable_report([
            ("Sesame exports require analysis", "unknown"),
        ])
        
        result = self.integration.classify_from_applicability(
            report, tenant_id=self.tenant_id
        )
        
        # Risk service only classifies 'applicable' outcomes
        # Unknown applicability cases are excluded from risk classification
        self.assertEqual(len(result), 0)

    # Test 4: Multiple outcomes aggregated correctly
    def test_multiple_outcomes_aggregated(self) -> None:
        """Mixed applicability outcomes should be handled correctly."""
        report = self._make_applicable_report([
            ("Cocoa exports need certification", "applicable"),
            ("Wheat exports need inspection", "not_applicable"),
            ("Sesame needs analysis", "unknown"),
            ("Cocoa quality control required", "applicable"),
        ])
        
        result = self.integration.classify_from_applicability(
            report, tenant_id=self.tenant_id
        )
        
        # Only applicable requirements should be classified
        self.assertEqual(len(result), 2)
        requirement_ids = {r["requirement_id"] for r in result}
        
        # Verify the two applicable ones are present
        applicable_ids = [
            r["requirement_id"] 
            for r in report["results"] 
            if r["outcome"] == "applicable"
        ]
        for req_id in applicable_ids:
            self.assertIn(req_id, requirement_ids)

    # Test 5: Tenant identity preserved
    def test_tenant_identity_preserved(self) -> None:
        """Tenant ID must be preserved and validated."""
        report = self._make_applicable_report([
            ("Exporters shall submit documentation", "applicable"),
        ])
        report["tenant_id"] = OTHER_TENANT_ID
        
        # Should raise error when tenant_id doesn't match report
        with self.assertRaises(ComplianceSummaryValidationError):
            self.integration.classify_from_applicability(
                report, tenant_id=self.tenant_id
            )

    # Test 6: Deterministic output
    def test_deterministic_output(self) -> None:
        """Identical input should produce identical output."""
        report = self._make_applicable_report([
            ("Exporters shall submit documentation", "applicable"),
        ])
        
        result1 = self.integration.classify_from_applicability(
            report, tenant_id=self.tenant_id
        )
        result2 = self.integration.classify_from_applicability(
            report, tenant_id=self.tenant_id
        )
        
        self.assertEqual(result1, result2)

    # Test 7: Existing ComplianceRiskService behavior unchanged
    def test_existing_risk_service_unchanged(self) -> None:
        """Existing risk service behavior should remain unchanged."""
        # This test verifies we're reusing existing logic, not duplicating it
        from xportra.domain.ingestion import ComplianceRiskService
        
        original_service = ComplianceRiskService()
        integration_service = ApplicabilityToRiskIntegration(risk_service=original_service)
        
        report = self._make_applicable_report([
            ("Export documentation required", "applicable"),
        ])
        
        # Get result through integration
        integration_result = integration_service.classify_from_applicability(
            report, tenant_id=self.tenant_id
        )
        
        # Build cases directly and classify
        cases = integration_service._build_cases(report, self.tenant_id)
        direct_result = original_service.classify(cases, tenant_id=self.tenant_id)
        
        # Results should be identical - proving we're just wrapping, not changing
        self.assertEqual(integration_result, direct_result)

    # Test 8: Existing action recommendation unchanged
    def test_action_recommendation_unchanged(self) -> None:
        """Phase 3.0 action recommendation should work with integrated output."""
        from xportra.domain.ingestion import ComplianceActionRecommendationService
        
        action_service = ComplianceActionRecommendationService()
        report = self._make_applicable_report([
            ("Export documentation required", "applicable"),
        ])
        
        # Get risk classification through integration
        risk_result = self.integration.classify_from_applicability(
            report, tenant_id=self.tenant_id
        )
        
        # Action service should still work normally
        # (this test mainly ensures no import/syntax errors)
        self.assertIsInstance(risk_result, list)

    # Additional edge case tests
    def test_empty_report(self) -> None:
        """Empty applicability report should return empty risk list."""
        report = {
            "tenant_id": self.tenant_id,
            "context_fingerprint": "empty",
            "total_requirements": 0,
            "applicable_count": 0,
            "not_applicable_count": 0,
            "unknown_count": 0,
            "results": [],
            "status": "determined",
        }
        
        result = self.integration.classify_from_applicability(
            report, tenant_id=self.tenant_id
        )
        
        self.assertEqual(result, [])

    def test_invalid_report_type(self) -> None:
        """Non-dict report should raise validation error."""
        with self.assertRaises(ComplianceSummaryValidationError):
            self.integration.classify_from_applicability(
                "not a dict", tenant_id=self.tenant_id
            )

    def test_invalid_tenant_id(self) -> None:
        """Non-UUID tenant_id should raise validation error."""
        report = self._make_applicable_report([])
        
        with self.assertRaises(ComplianceSummaryValidationError):
            self.integration.classify_from_applicability(
                report, tenant_id="not-a-uuid"
            )

    def test_all_not_applicable(self) -> None:
        """All not-applicable requirements should produce empty risk list."""
        report = self._make_applicable_report([
            ("Requirement 1", "not_applicable"),
            ("Requirement 2", "not_applicable"),
            ("Requirement 3", "not_applicable"),
        ])
        
        result = self.integration.classify_from_applicability(
            report, tenant_id=self.tenant_id
        )
        
        self.assertEqual(len(result), 0)

    def test_all_unknown(self) -> None:
        """All unknown applicability should produce empty risk list."""
        report = self._make_applicable_report([
            ("Requirement 1", "unknown"),
            ("Requirement 2", "unknown"),
        ])
        
        result = self.integration.classify_from_applicability(
            report, tenant_id=self.tenant_id
        )
        
        self.assertEqual(len(result), 0)

    def test_mixed_real_world_scenario(self) -> None:
        """Real-world mixed scenario: cocoa export to Nigeria."""
        report = self._make_applicable_report([
            ("Cocoa exports to Nigeria require phytosanitary certificate", "applicable"),
            ("Wheat exports to Ghana require inspection", "not_applicable"),
            ("Sesame exports require laboratory analysis", "unknown"),
            ("All exporters must maintain records", "applicable"),
            ("Coffee shipments need origin certification", "not_applicable"),
            ("Maize exports require quality testing", "unknown"),
        ])
        
        result = self.integration.classify_from_applicability(
            report, tenant_id=self.tenant_id
        )
        
        # Should only classify the 2 applicable requirements
        self.assertEqual(len(result), 2)
        
# All should have medium state (unknown assessment + missing evidence)
        for r in result:
            self.assertEqual(r["state"], "medium")
            self.assertEqual(r["explanation"], "unknown with missing required evidence")
if __name__ == "__main__":
    unittest.main()