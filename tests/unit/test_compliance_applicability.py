"""Focused unit tests for Phase 3.1 — ComplianceApplicabilityService."""

import unittest
from uuid import uuid4

from xportra.domain.ingestion import (
    ApplicabilityContext,
    ComplianceApplicabilityService,
    ComplianceSummaryValidationError,
    RegulatoryRequirementApplicabilityService,
    context_fingerprint,
)


class ComplianceApplicabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tenant_id = uuid4()
        self.service = ComplianceApplicabilityService()
        self.context = ApplicabilityContext(
            tenant_id=self.tenant_id,
            destination_country="ng",
            commodity="cocoa",
            actor_role="exporter",
        )

    def _requirement(self, text: str, actor: str | None = None) -> dict:
        return {
            "id": str(uuid4()),
            "requirement_text": text,
            "actor": actor,
        }

    # 1. Clearly applicable requirement
    def test_clearly_applicable(self) -> None:
        req = self._requirement(
            "All cocoa exports to Nigeria require phytosanitary certification",
            actor="exporter",
        )
        result = self.service.determine([req], self.context)

        self.assertEqual(result["total_requirements"], 1)
        self.assertEqual(result["applicable_count"], 1)
        self.assertEqual(result["not_applicable_count"], 0)
        self.assertEqual(result["unknown_count"], 0)
        self.assertEqual(result["results"][0]["outcome"], "applicable")

    # 2. Clearly non-applicable requirement
    def test_clearly_not_applicable(self) -> None:
        req = self._requirement(
            "All wheat exports to Ghana require inspection",
            actor="exporter",
        )
        result = self.service.determine([req], self.context)

        self.assertEqual(result["total_requirements"], 1)
        self.assertEqual(result["applicable_count"], 0)
        self.assertEqual(result["not_applicable_count"], 1)
        self.assertEqual(result["unknown_count"], 0)
        self.assertEqual(result["results"][0]["outcome"], "not_applicable")

    # 3. Insufficient information / indeterminate applicability
    def test_insufficient_information(self) -> None:
        # When destination is known but commodity is missing,
        # and the requirement mentions a specific commodity,
        # the outcome is "unknown" because we can't determine if it applies.
        req = self._requirement(
            "All sesame exports require laboratory analysis",
            actor="exporter",
        )
        # Context has destination but no commodity
        context_no_commodity = ApplicabilityContext(
            tenant_id=self.tenant_id,
            destination_country="ng",
            actor_role="exporter",
        )
        result = self.service.determine([req], context_no_commodity)

        self.assertEqual(result["total_requirements"], 1)
        self.assertEqual(result["unknown_count"], 1)
        self.assertEqual(result["results"][0]["outcome"], "unknown")

    # 4. Multiple requirements evaluated independently
    def test_multiple_requirements_independent(self) -> None:
        req_applicable = self._requirement(
            "All cocoa exports to Nigeria require phytosanitary certification",
            actor="exporter",
        )
        req_not_applicable = self._requirement(
            "All wheat exports to Ghana require inspection",
            actor="exporter",
        )
        # This req mentions "sesame" (commodity mismatch with cocoa context)
        # so it becomes not_applicable, not unknown
        req_commodity_mismatch = self._requirement(
            "All sesame exports require laboratory analysis",
            actor="exporter",
        )
        result = self.service.determine(
            [req_applicable, req_not_applicable, req_commodity_mismatch],
            self.context,
        )

        self.assertEqual(result["total_requirements"], 3)
        self.assertEqual(result["applicable_count"], 1)
        # Both mismatching requirements are not_applicable
        self.assertEqual(result["not_applicable_count"], 2)
        outcomes = {r["outcome"] for r in result["results"]}
        self.assertEqual(outcomes, {"applicable", "not_applicable"})

    # 5. Deterministic repeated evaluation
    def test_deterministic_repeated_evaluation(self) -> None:
        req = self._requirement(
            "All cocoa exports to Nigeria require phytosanitary certification",
            actor="exporter",
        )
        first = self.service.determine([req], self.context)
        second = self.service.determine([req], self.context)

        self.assertEqual(first["results"][0]["outcome"], second["results"][0]["outcome"])
        self.assertEqual(first["context_fingerprint"], second["context_fingerprint"])

    # 6. Interaction with Phase 2.x/3.0 domain outputs
    def test_context_fingerprint_matches_applicability_service(self) -> None:
        expected = RegulatoryRequirementApplicabilityService.context_fingerprint(
            self.context
        )
        actual = context_fingerprint(self.context)
        self.assertEqual(expected, actual)

    # 7. Invalid or incomplete input handling
    def test_empty_requirements_raises(self) -> None:
        with self.assertRaises(ComplianceSummaryValidationError):
            self.service.determine([], self.context)

    def test_invalid_context_raises(self) -> None:
        with self.assertRaises(ComplianceSummaryValidationError):
            self.service.determine([self._requirement("test")], {"not": "a context"})

    def test_tenant_isolation(self) -> None:
        """Results are scoped to the correct tenant."""
        req = self._requirement(
            "All cocoa exports to Nigeria require phytosanitary certification",
            actor="exporter",
        )
        result = self.service.determine([req], self.context)
        self.assertEqual(result["tenant_id"], self.tenant_id)

    def test_status_field(self) -> None:
        req = self._requirement(
            "All cocoa exports to Nigeria require phytosanitary certification",
            actor="exporter",
        )
        result = self.service.determine([req], self.context)
        self.assertEqual(result["status"], "determined")

    def test_counts_sum_to_total(self) -> None:
        req1 = self._requirement(
            "All cocoa exports to Nigeria require phytosanitary certification",
            actor="exporter",
        )
        req2 = self._requirement(
            "All wheat exports to Ghana require inspection",
            actor="exporter",
        )
        result = self.service.determine([req1, req2], self.context)
        self.assertEqual(
            result["applicable_count"]
            + result["not_applicable_count"]
            + result["unknown_count"],
            result["total_requirements"],
        )


if __name__ == "__main__":
    unittest.main()