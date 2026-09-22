"""Phase 3.6 - Compliance Case Readiness / Evidence Coverage tests.

Covers the ComplianceCaseReadinessService boundary: readiness states,
evidence-gap semantics, unknown handling, tenant isolation, determinism,
and integration with the existing Phase 3.5 decision summary.
"""

import copy
import json
import unittest
from uuid import UUID

from xportra.domain.ingestion import (
    ApplicabilityContext,
    ComplianceActionRecommendationService,
    ComplianceApplicabilityService,
    ComplianceCaseReadinessService,
    ComplianceDecisionSummaryService,
    ComplianceRiskService,
    ComplianceSummaryValidationError,
)

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
REQ_A = UUID("11111111-1111-1111-1111-00000000000a")
REQ_B = UUID("11111111-1111-1111-1111-00000000000b")
REQ_C = UUID("11111111-1111-1111-1111-00000000000c")
REQ_D = UUID("11111111-1111-1111-1111-00000000000d")


class TestComplianceCaseReadiness(unittest.TestCase):
    """Focused Phase 3.6 readiness boundary tests."""

    def setUp(self) -> None:
        self.service = ComplianceCaseReadinessService()
        self.tenant_id = TENANT_ID

    def _make_case(
        self,
        requirement_id: UUID,
        *,
        applicability: str = "applicable",
        assessment: str = "unknown",
        evidence: list | None = None,
        applicability_reason: str = "determined",
        assessment_reason: str = "assessment not yet performed",
    ) -> dict:
        """Build a compliance case using the existing pipeline case shape."""
        return {
            "tenant_id": self.tenant_id,
            "requirement": {
                "id": requirement_id,
                "text": f"Requirement {str(requirement_id)[-12:]}",
                "type": "documentation",
            },
            "applicability": {
                "outcome": applicability,
                "reason": applicability_reason,
            },
            "assessment": {
                "outcome": assessment,
                "reason": assessment_reason,
            },
            "evidence": evidence if evidence is not None else [],
        }

    # Test 1: fully known case -> ready
    def test_fully_known_case_is_ready(self) -> None:
        """Applicable, assessed, evidenced, and risk-classified -> ready."""
        case = self._make_case(
            REQ_A,
            assessment="satisfied",
            assessment_reason="assessment completed",
            evidence=[{"id": "ev-1"}],
        )

        report = self.service.assess([case], tenant_id=self.tenant_id)

        self.assertEqual(report["readiness_state"], "ready")
        self.assertEqual(report["required_information"], 4)
        self.assertEqual(report["known_information"], 4)
        self.assertEqual(report["missing_information"], 0)
        self.assertEqual(report["gaps"], [])

    # Test 2: partially known case -> partially_ready
    def test_partially_known_case_is_partially_ready(self) -> None:
        """Known applicability with unknown assessment -> partially_ready."""
        case = self._make_case(REQ_A)  # unknown assessment, no evidence

        report = self.service.assess([case], tenant_id=self.tenant_id)

        self.assertEqual(report["readiness_state"], "partially_ready")
        self.assertEqual(report["required_information"], 4)
        self.assertEqual(report["known_information"], 2)
        self.assertEqual(report["missing_information"], 2)

    # Test 3: insufficient/unknown case -> not_ready
    def test_insufficient_unknown_case_is_not_ready(self) -> None:
        """Unknown applicability means the applicable set is incomplete."""
        case = self._make_case(REQ_A, applicability="unknown")

        report = self.service.assess([case], tenant_id=self.tenant_id)

        self.assertEqual(report["readiness_state"], "not_ready")

    # Test 4: unknown applicability
    def test_unknown_applicability_gap(self) -> None:
        """Unknown applicability is reported as an applicability gap."""
        case = self._make_case(
            REQ_A,
            applicability="unknown",
            applicability_reason="insufficient context data",
        )

        report = self.service.assess([case], tenant_id=self.tenant_id)

        kinds = [gap["kind"] for gap in report["gaps"]]
        self.assertEqual(kinds, ["applicability_unknown"])
        self.assertEqual(
            report["unknown_applicability_requirements"], [REQ_A]
        )
        gap = report["gaps"][0]
        self.assertEqual(gap["reason"], "insufficient context data")
        # Unknown applicability is never inferred as applicable.
        view = report["requirements"][0]
        self.assertEqual(view["applicability_outcome"], "unknown")
        self.assertIsNone(view["risk_state"])
        # The existing Phase 3.0 action service recommends review_requirement
        # for unknown applicability; readiness preserves that action unchanged.
        self.assertEqual(view["action_type"], "review_requirement")

    # Test 5: unknown assessment
    def test_unknown_assessment_gap(self) -> None:
        """Unknown assessment is reported as an assessment gap."""
        case = self._make_case(
            REQ_A,
            evidence=[{"id": "ev-1"}],  # evidence present: no evidence gap
        )

        report = self.service.assess([case], tenant_id=self.tenant_id)

        kinds = [gap["kind"] for gap in report["gaps"]]
        self.assertIn("assessment_unknown", kinds)
        self.assertNotIn("missing_evidence", kinds)
        self.assertEqual(
            report["unknown_assessment_requirements"], [REQ_A]
        )

    # Test 6: missing evidence
    def test_missing_evidence_gap(self) -> None:
        """Unknown assessment without evidence is reported as missing evidence."""
        case = self._make_case(REQ_A)  # unknown assessment, empty evidence

        report = self.service.assess([case], tenant_id=self.tenant_id)

        kinds = [gap["kind"] for gap in report["gaps"]]
        self.assertIn("missing_evidence", kinds)
        self.assertEqual(report["missing_evidence_requirements"], [REQ_A])
        view = report["requirements"][0]
        self.assertFalse(view["evidence_present"])

    # Test 7: unknown risk
    def test_unknown_risk_gap(self) -> None:
        """Unknown assessment with evidence present leaves risk unknown."""
        case = self._make_case(
            REQ_A,
            evidence=[{"id": "ev-1"}],
        )

        report = self.service.assess([case], tenant_id=self.tenant_id)

        kinds = [gap["kind"] for gap in report["gaps"]]
        self.assertIn("risk_unknown", kinds)
        self.assertEqual(report["unknown_risk_requirements"], [REQ_A])
        view = report["requirements"][0]
        self.assertEqual(view["risk_state"], "unknown")

    # Test 8: multiple simultaneous gaps
    def test_multiple_simultaneous_gaps(self) -> None:
        """Applicability, assessment, evidence, and risk gaps coexist."""
        unknown_applicability = self._make_case(
            REQ_A, applicability="unknown"
        )
        # Unknown assessment with no evidence: assessment + evidence gaps
        # (existing risk service classifies this as medium, not unknown).
        unknown_assessment = self._make_case(REQ_B)
        # Unknown assessment with evidence present: assessment + risk gaps
        # (existing risk service classifies this as unknown state).
        unknown_risk = self._make_case(
            REQ_C,
            assessment_reason="awaiting assessor review",
            evidence=[{"id": "ev-3"}],
        )
        known = self._make_case(
            REQ_D,
            assessment="satisfied",
            assessment_reason="assessment completed",
            evidence=[{"id": "ev-2"}],
        )

        report = self.service.assess(
            [unknown_applicability, unknown_assessment, unknown_risk, known],
            tenant_id=self.tenant_id,
        )

        kinds = {gap["kind"] for gap in report["gaps"]}
        self.assertEqual(
            kinds,
            {
                "applicability_unknown",
                "assessment_unknown",
                "missing_evidence",
                "risk_unknown",
            },
        )
        self.assertEqual(report["readiness_state"], "not_ready")

    # Test 9: no false inference from missing facts
    def test_no_false_inference_from_missing_facts(self) -> None:
        """Missing facts are never promoted to known or negative decisions."""
        unknown = self._make_case(REQ_A, applicability="unknown")
        not_applicable = self._make_case(REQ_B, applicability="not_applicable")
        satisfied_no_evidence = self._make_case(
            REQ_C,
            assessment="satisfied",
            assessment_reason="assessment completed",
            evidence=[],  # evidence absent but assessment is known
        )

        report = self.service.assess(
            [unknown, not_applicable, satisfied_no_evidence],
            tenant_id=self.tenant_id,
        )

        # Unknown applicability is not inferred as applicable or not_applicable.
        views = {v["requirement_id"]: v for v in report["requirements"]}
        self.assertEqual(
            views[REQ_A]["applicability_outcome"], "unknown"
        )
        self.assertIsNone(views[REQ_A]["risk_state"])
        # Not-applicable stays not_applicable and requires no further info.
        self.assertEqual(
            views[REQ_B]["applicability_outcome"], "not_applicable"
        )
        # A satisfied assessment with no evidence is NOT reported as missing
        # evidence: existing services consult evidence only for unknown
        # assessments, so no extra evidence rule is invented here.
        self.assertNotIn(
            "missing_evidence",
            [gap["kind"] for gap in report["gaps"]],
        )
        self.assertEqual(views[REQ_C]["risk_state"], "low")

    # Test 10: deterministic requirement ordering
    def test_deterministic_requirement_ordering(self) -> None:
        """Requirement views and section lists follow stable ID ordering."""
        cases = [
            self._make_case(REQ_C),
            self._make_case(REQ_A),
            self._make_case(REQ_B, applicability="not_applicable"),
        ]

        first = self.service.assess(cases, tenant_id=self.tenant_id)
        reversed_input = self.service.assess(
            list(reversed(cases)), tenant_id=self.tenant_id
        )

        expected_order = [str(REQ_A), str(REQ_B), str(REQ_C)]
        self.assertEqual(
            [str(v["requirement_id"]) for v in first["requirements"]],
            expected_order,
        )
        self.assertEqual(
            [str(v["requirement_id"]) for v in reversed_input["requirements"]],
            expected_order,
        )

    # Test 11: deterministic gap ordering
    def test_deterministic_gap_ordering(self) -> None:
        """Gaps are ordered by requirement ID, then by gap kind."""
        cases = [
            self._make_case(REQ_C, applicability="unknown"),
            self._make_case(REQ_A),  # assessment unknown, no evidence
            self._make_case(REQ_B, assessment_reason="awaiting review",
                            evidence=[{"id": "ev-1"}]),
        ]

        report = self.service.assess(cases, tenant_id=self.tenant_id)

        observed = [
            (str(gap["requirement_id"]), gap["kind"]) for gap in report["gaps"]
        ]
        expected = [
            (str(REQ_A), "assessment_unknown"),
            (str(REQ_A), "missing_evidence"),
            (str(REQ_B), "assessment_unknown"),
            (str(REQ_B), "risk_unknown"),
            (str(REQ_C), "applicability_unknown"),
        ]
        self.assertEqual(observed, expected)

        reversed_input = self.service.assess(
            list(reversed(cases)), tenant_id=self.tenant_id
        )
        self.assertEqual(
            [(str(g["requirement_id"]), g["kind"]) for g in reversed_input["gaps"]],
            expected,
        )

    # Test 12: identical input produces identical output
    def test_identical_input_produces_identical_output(self) -> None:
        """The same cases always produce the exact same readiness report."""
        cases = [
            self._make_case(REQ_A),
            self._make_case(
                REQ_B,
                assessment="satisfied",
                assessment_reason="assessment completed",
                evidence=[{"id": "ev-1"}],
            ),
            self._make_case(REQ_C, applicability="unknown"),
        ]

        first = self.service.assess(list(cases), tenant_id=self.tenant_id)
        second = self.service.assess(list(cases), tenant_id=self.tenant_id)

        self.assertEqual(first, second)

    # Test 13: tenant identity preserved
    def test_tenant_identity_preserved(self) -> None:
        """The report carries the requesting tenant identity."""
        case = self._make_case(REQ_A)

        report = self.service.assess([case], tenant_id=self.tenant_id)

        self.assertEqual(report["tenant_id"], self.tenant_id)
        self.assertEqual(report["status"], "readiness_report")

    # Test 14: invalid tenant rejected
    def test_invalid_tenant_rejected(self) -> None:
        """Non-UUID tenants and cross-tenant cases are rejected."""
        case = self._make_case(REQ_A)

        with self.assertRaises(ComplianceSummaryValidationError):
            self.service.assess([case], tenant_id="not-a-uuid")

        with self.assertRaises(ComplianceSummaryValidationError):
            self.service.assess([case], tenant_id=OTHER_TENANT_ID)

    # Test 15: empty input handled deterministically
    def test_empty_input_handled_deterministically(self) -> None:
        """No cases is a deterministic not_ready report with zero counts."""
        first = self.service.assess([], tenant_id=self.tenant_id)
        second = self.service.assess([], tenant_id=self.tenant_id)

        self.assertEqual(first, second)
        self.assertEqual(first["readiness_state"], "not_ready")
        self.assertEqual(first["required_information"], 0)
        self.assertEqual(first["known_information"], 0)
        self.assertEqual(first["missing_information"], 0)
        self.assertEqual(first["gaps"], [])
        self.assertEqual(first["requirements"], [])

    # Test 16: ready case can still contain high risk
    def test_ready_case_can_still_contain_high_risk(self) -> None:
        """Readiness is information sufficiency, not compliance."""
        case = self._make_case(
            REQ_A,
            assessment="not_satisfied",
            assessment_reason="assessment indicates breach",
            evidence=[{"id": "ev-1"}],
        )

        report = self.service.assess([case], tenant_id=self.tenant_id)

        # All required information is known, so the case is ready...
        self.assertEqual(report["readiness_state"], "ready")
        self.assertEqual(report["gaps"], [])
        self.assertEqual(report["required_information"], 4)
        self.assertEqual(report["known_information"], 4)
        # ...even though the risk classification is high and the action is
        # remediation rather than information gathering.
        self.assertEqual(report["requirements"][0]["risk_state"], "high")
        self.assertEqual(report["requirements"][0]["action_type"], "address_requirement")
        self.assertEqual(report["actions_requiring_evidence"], [])
        self.assertIn("not a compliance verdict", report["readiness_not_compliance"])

    # Test 17: not-ready case is not labelled non-compliant
    def test_not_ready_case_is_not_labelled_non_compliant(self) -> None:
        """not_ready means insufficient information, never a verdict."""
        case = self._make_case(
            REQ_A,
            applicability="unknown",
            applicability_reason="destination information insufficient; insufficient context",
        )

        report = self.service.assess([case], tenant_id=self.tenant_id)

        self.assertEqual(report["readiness_state"], "not_ready")
        # No compliance verdict fields exist on the report.
        self.assertNotIn("compliance_state", report)
        self.assertNotIn("verdict", report)
        self.assertNotIn("compliant", report)
        self.assertIn("not a compliance verdict", report["readiness_not_compliance"])
        # Unknown stays unknown: nothing is inferred as satisfied/unsatisfied.
        self.assertEqual(report["requirements"][0]["applicability_outcome"], "unknown")
        self.assertEqual(report["requirements"][0]["assessment_outcome"], "unknown")
        self.assertNotIn(
            "satisfied",
            [row["assessment_outcome"] for row in report["requirements"]],
        )

    # Test 18: existing decision summary remains unchanged
    def test_existing_decision_summary_remains_unchanged(self) -> None:
        """Readiness consumes the summary inputs without mutating or diverging."""
        cases = [
            self._make_case(REQ_A),
            self._make_case(REQ_B, applicability="not_applicable"),
        ]
        frozen = copy.deepcopy(cases)
        before = ComplianceDecisionSummaryService().summarize(
            copy.deepcopy(cases), tenant_id=self.tenant_id
        )

        self.service.assess(cases, tenant_id=self.tenant_id)

        # assess() must not mutate the supplied cases.
        self.assertEqual(cases, frozen)
        # The Phase 3.5 summary over the same cases is unaffected.
        after = ComplianceDecisionSummaryService().summarize(
            copy.deepcopy(cases), tenant_id=self.tenant_id
        )
        self.assertEqual(before, after)

    # Test 19: existing risk/action semantics remain unchanged
    def test_existing_risk_and_action_semantics_unchanged(self) -> None:
        """Readiness consumes risk/action outputs; it does not recompute them."""
        cases = [
            self._make_case(REQ_A),
            self._make_case(
                REQ_B,
                applicability="unknown",
                applicability_reason="commodity information insufficient; insufficient context",
            ),
            self._make_case(
                REQ_C,
                applicability="not_applicable",
                applicability_reason="commodity mismatch; destination mismatch",
            ),
        ]

        report = self.service.assess(cases, tenant_id=self.tenant_id)

        direct_risk = ComplianceRiskService().classify(
            copy.deepcopy(cases), tenant_id=self.tenant_id
        )
        direct_actions = ComplianceActionRecommendationService().recommend(
            copy.deepcopy(cases), tenant_id=self.tenant_id
        )
        risk_by_id = {
            str(result["requirement_id"]): result["state"] for result in direct_risk
        }
        action_by_id = {
            str(action["requirement_id"]): action["action_type"]
            for action in direct_actions
        }
        for row in report["requirements"]:
            self.assertEqual(
                row["risk_state"], risk_by_id.get(str(row["requirement_id"]))
            )
            self.assertEqual(
                row["action_type"], action_by_id.get(str(row["requirement_id"]))
            )

    # Test 20: end-to-end integration with the existing Phase 3.5 summary
    def test_end_to_end_with_phase_3_5_summary(self) -> None:
        """Real applicability -> report -> cases -> Phase 3.5 summary + readiness."""
        context = ApplicabilityContext(
            tenant_id=self.tenant_id,
            destination_country="ng",
            commodity="cocoa",
            actor_role="exporter",
        )
        requirements = [
            {
                "id": REQ_A,
                "requirement_text": "Exporters of cocoa to Nigeria must register.",
                "actor": "exporter",
            },
            {
                "id": REQ_B,
                "requirement_text": "Coffee exporters to Ghana must file returns.",
                "actor": "exporter",
            },
            {
                "id": REQ_C,
                "requirement_text": "Producers must maintain records.",
                "actor": "producer",
            },
        ]
        report = ComplianceApplicabilityService().determine(requirements, context)
        outcomes = {
            result["requirement_id"]: result["outcome"] for result in report["results"]
        }
        self.assertEqual(outcomes[REQ_A], "applicable")
        self.assertEqual(outcomes[REQ_B], "not_applicable")
        self.assertEqual(outcomes[REQ_C], "unknown")

        texts = {req["id"]: req["requirement_text"] for req in requirements}
        cases = [
            {
                "tenant_id": self.tenant_id,
                "context_fingerprint": report["context_fingerprint"],
                "requirement": {
                    "id": result["requirement_id"],
                    "text": texts[result["requirement_id"]],
                    "type": "documentation",
                },
                "applicability": {
                    "outcome": result["outcome"],
                    "reason": result["reason"],
                },
                "assessment": {
                    "outcome": "unknown",
                    "reason": "assessment not yet performed",
                },
                "evidence": [],
            }
            for result in report["results"]
        ]

        readiness = self.service.assess(cases, tenant_id=self.tenant_id)
        self.assertEqual(readiness["readiness_state"], "not_ready")
        self.assertEqual(readiness["tenant_id"], self.tenant_id)
        self.assertEqual(
            readiness["context_fingerprint"], report["context_fingerprint"]
        )
        self.assertEqual(readiness["unknown_applicability_requirements"], [REQ_C])
        self.assertEqual(readiness["unknown_assessment_requirements"], [REQ_A])
        self.assertEqual(readiness["missing_evidence_requirements"], [REQ_A])
        self.assertEqual(readiness["required_information"], 6)
        self.assertEqual(readiness["known_information"], 3)
        self.assertEqual(readiness["missing_information"], 3)
        self.assertEqual(
            [a["requirement_id"] for a in readiness["actions_requiring_evidence"]],
            [REQ_A, REQ_C],
        )
        self.assertEqual(
            [a["action_type"] for a in readiness["actions_requiring_evidence"]],
            ["provide_missing_evidence", "review_requirement"],
        )

        # Consistency with the Phase 3.5 decision summary on the same input.
        summary = ComplianceDecisionSummaryService().summarize(
            cases, tenant_id=self.tenant_id
        )
        self.assertEqual(summary["tenant_id"], readiness["tenant_id"])
        self.assertEqual(
            summary["context_fingerprint"], readiness["context_fingerprint"]
        )
        self.assertEqual(
            {gap["kind"] for gap in readiness["gaps"]},
            {entry["kind"] for entry in summary["unknown_states"]},
        )


if __name__ == "__main__":
    unittest.main()
