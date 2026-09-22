"""Focused unit tests for Phase 3.5 — ComplianceDecisionSummaryService.

Covers the deterministic decision-summary representation boundary:
Applicability → Risk → Action → Summary.
"""

import copy
import json
import re
import unittest
from pathlib import Path
from uuid import UUID

from xportra.domain.ingestion import (
    ApplicabilityContext,
    ApplicabilityToRiskIntegration,
    ComplianceActionRecommendationService,
    ComplianceApplicabilityService,
    ComplianceDecisionSummaryService,
    ComplianceRiskService,
    ComplianceSummaryValidationError,
    RiskToActionIntegration,
)

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "xportra" / "domain" / "ingestion.py"
)
ALLOWED_RISK_STATES = {"high", "medium", "low", "unknown"}
ALLOWED_ACTION_TYPES = {
    "address_requirement",
    "no_action_required",
    "provide_missing_evidence",
    "review_requirement",
}


def _req_id(index: int) -> UUID:
    """Deterministic requirement identifier for ordering assertions."""
    return UUID(f"11111111-1111-1111-1111-{str(index).zfill(12)}")


class ComplianceDecisionSummaryTests(unittest.TestCase):
    """Test Phase 3.5 compliance decision summary boundary."""

    def setUp(self) -> None:
        self.tenant_id = TENANT_ID
        self.summary = ComplianceDecisionSummaryService()
        self.risk_service = ComplianceRiskService()
        self.risk_integration = ApplicabilityToRiskIntegration()
        self.action_service = ComplianceActionRecommendationService()
        self.action_integration = RiskToActionIntegration()
        self.applicability_service = ComplianceApplicabilityService()
        self.context = ApplicabilityContext(
            tenant_id=self.tenant_id,
            destination_country="ng",
            commodity="cocoa",
            actor_role="exporter",
        )

    def _case(
        self,
        requirement_id: UUID,
        applicability: str = "applicable",
        assessment: str = "unknown",
        assessment_reason: str = "assessment not yet performed",
        evidence: list | None = None,
        text: str = "Test requirement",
        context_fingerprint: str = "fp-abc123",
        tenant_id: UUID | None = None,
    ) -> dict:
        """Create an existing-shape compliance case for testing."""
        return {
            "tenant_id": tenant_id or self.tenant_id,
            "context": {"destination_country": "ng", "commodity": "cocoa"},
            "context_fingerprint": context_fingerprint,
            "requirement": {
                "id": requirement_id,
                "text": text,
                "type": "documentation",
            },
            "applicability": {"outcome": applicability, "reason": "determined"},
            "assessment": {"outcome": assessment, "reason": assessment_reason},
            "evidence": evidence if evidence is not None else [],
        }

    def _report(self, entries: list[tuple[int, str]]) -> dict:
        """Create an applicability report in the real service output shape."""
        results = []
        for index, outcome in entries:
            req_id = _req_id(index)
            results.append(
                {
                    "id": req_id,
                    "tenant_id": self.tenant_id,
                    "requirement_id": req_id,
                    "context_fingerprint": "fp-abc123",
                    "outcome": outcome,
                    "reason": f"test reason for {outcome}",
                    "context": {},
                    "status": "evaluated",
                }
            )

        return {
            "tenant_id": self.tenant_id,
            "context_fingerprint": "fp-abc123",
            "total_requirements": len(results),
            "applicable_count": sum(1 for _, o in entries if o == "applicable"),
            "not_applicable_count": sum(
                1 for _, o in entries if o == "not_applicable"
            ),
            "unknown_count": sum(1 for _, o in entries if o == "unknown"),
            "results": results,
            "status": "determined",
        }

    @staticmethod
    def _ids(rows: list[dict]) -> list[str]:
        return [str(row["requirement_id"]) for row in rows]

    @staticmethod
    def _kinds(unknown_states: list[dict]) -> set[str]:
        return {entry["kind"] for entry in unknown_states}

    def _row(self, summary: dict, requirement_id: UUID) -> dict:
        for row in summary["requirements"]:
            if row["requirement_id"] == requirement_id:
                return row
        raise AssertionError(f"requirement {requirement_id} not present in summary")

    def _fingerprint(self, summary: dict) -> str:
        return json.dumps(summary, sort_keys=True, default=str)

    # Test 1: Complete applicable case
    def test_complete_applicable_case(self) -> None:
        """One applicable, satisfied, evidenced requirement yields a full row."""
        req = _req_id(1)
        cases = [
            self._case(
                req,
                assessment="satisfied",
                assessment_reason="required evidence present",
                evidence=[{"id": "e-1", "type": "certificate"}],
            )
        ]

        summary = self.summary.summarize(cases, tenant_id=self.tenant_id)

        self.assertEqual(summary["status"], "decision_summary")
        self.assertEqual(summary["applicability"]["total_requirements"], 1)
        self.assertEqual(summary["applicability"]["applicable_count"], 1)
        self.assertEqual(summary["applicability"]["unknown_count"], 0)
        self.assertEqual(summary["risk"]["classified_count"], 1)
        self.assertEqual(summary["risk"]["by_state"], {"low": 1})
        self.assertEqual(summary["actions"]["recommendation_count"], 1)
        self.assertEqual(summary["actions"]["by_type"], {"no_action_required": 1})

        row = self._row(summary, req)
        self.assertEqual(row["applicability_outcome"], "applicable")
        self.assertEqual(row["assessment_outcome"], "satisfied")
        self.assertTrue(row["evidence_present"])
        self.assertEqual(row["risk_state"], "low")
        self.assertEqual(row["action_type"], "no_action_required")
        self.assertEqual(summary["unknown_states"], [])

    # Test 2: Mixed applicable / not-applicable requirements
    def test_mixed_applicable_and_not_applicable(self) -> None:
        """Not-applicable requirements are represented but not classified."""
        applicable = _req_id(1)
        excluded = _req_id(2)
        cases = [
            self._case(applicable, assessment="satisfied", evidence=[{"id": "e-1"}]),
            self._case(excluded, applicability="not_applicable"),
        ]

        summary = self.summary.summarize(cases, tenant_id=self.tenant_id)

        self.assertEqual(summary["applicability"]["total_requirements"], 2)
        self.assertEqual(summary["applicability"]["applicable_count"], 1)
        self.assertEqual(summary["applicability"]["not_applicable_count"], 1)
        self.assertEqual(summary["risk"]["classified_count"], 1)
        self.assertEqual(summary["actions"]["recommendation_count"], 1)

        row = self._row(summary, excluded)
        self.assertEqual(row["applicability_outcome"], "not_applicable")
        self.assertIsNone(row["risk_state"])
        self.assertIsNone(row["action_type"])
        self.assertEqual(summary["unknown_states"], [])

    # Test 3: Unknown applicability
    def test_unknown_applicability_preserved(self) -> None:
        """Unknown applicability stays unknown and is never risk-classified."""
        req = _req_id(1)
        cases = [self._case(req, applicability="unknown")]

        summary = self.summary.summarize(cases, tenant_id=self.tenant_id)

        self.assertEqual(summary["applicability"]["unknown_count"], 1)
        self.assertEqual(summary["risk"]["classified_count"], 0)
        self.assertEqual(summary["risk"]["by_state"], {})

        row = self._row(summary, req)
        self.assertEqual(row["applicability_outcome"], "unknown")
        self.assertIsNone(row["risk_state"])

        # Existing action logic reviews unknown applicability; it is not rewritten.
        self.assertEqual(row["action_type"], "review_requirement")
        kinds = self._kinds(summary["unknown_states"])
        self.assertEqual(kinds, {"applicability_unknown"})
        self.assertEqual(
            [
                entry["reason"]
                for entry in summary["unknown_states"]
                if entry["kind"] == "applicability_unknown"
            ],
            ["determined"],
        )

    # Test 4: Unknown assessment
    def test_unknown_assessment_preserved(self) -> None:
        """Unknown assessment with evidence present stays unknown, not negative."""
        req = _req_id(1)
        cases = [
            self._case(
                req,
                assessment="unknown",
                assessment_reason="assessment inconclusive",
                evidence=[{"id": "e-1"}],
            )
        ]

        summary = self.summary.summarize(cases, tenant_id=self.tenant_id)

        row = self._row(summary, req)
        self.assertEqual(row["assessment_outcome"], "unknown")
        self.assertEqual(row["assessment_reason"], "assessment inconclusive")
        self.assertTrue(row["evidence_present"])
        self.assertEqual(row["risk_state"], "unknown")
        self.assertEqual(row["action_type"], "review_requirement")
        self.assertEqual(summary["risk"]["by_state"], {"unknown": 1})
        self.assertEqual(
            self._kinds(summary["unknown_states"]),
            {"assessment_unknown", "risk_unknown"},
        )

    # Test 5: Missing evidence
    def test_missing_evidence_distinguishable(self) -> None:
        """Absent evidence yields medium risk and is reported as missing."""
        req = _req_id(1)
        cases = [self._case(req, assessment_reason="required evidence absent")]

        summary = self.summary.summarize(cases, tenant_id=self.tenant_id)

        row = self._row(summary, req)
        self.assertFalse(row["evidence_present"])
        self.assertEqual(row["assessment_outcome"], "unknown")
        self.assertEqual(row["risk_state"], "medium")
        self.assertEqual(row["action_type"], "provide_missing_evidence")
        self.assertEqual(
            self._kinds(summary["unknown_states"]),
            {"assessment_unknown", "missing_evidence"},
        )

    # Test 6: High-risk case
    def test_high_risk_case(self) -> None:
        """Not-satisfied assessment yields high risk and an address action."""
        req = _req_id(1)
        cases = [
            self._case(
                req,
                assessment="not_satisfied",
                assessment_reason="required evidence absent",
                evidence=[{"id": "e-1"}],
            )
        ]

        summary = self.summary.summarize(cases, tenant_id=self.tenant_id)

        row = self._row(summary, req)
        self.assertEqual(row["risk_state"], "high")
        self.assertEqual(row["action_type"], "address_requirement")
        self.assertEqual(summary["risk"]["by_state"], {"high": 1})
        self.assertEqual(summary["actions"]["by_type"], {"address_requirement": 1})
        self.assertEqual(summary["unknown_states"], [])

    # Test 7: Medium-risk case
    def test_medium_risk_case(self) -> None:
        """Medium risk comes from existing missing-evidence logic, not a new rule."""
        req = _req_id(1)
        cases = [
            self._case(
                req,
                assessment="unknown",
                assessment_reason="required evidence absent",
                evidence=[{"id": "e-1"}],
            )
        ]

        summary = self.summary.summarize(cases, tenant_id=self.tenant_id)

        row = self._row(summary, req)
        self.assertEqual(row["risk_state"], "medium")
        self.assertEqual(row["action_type"], "provide_missing_evidence")
        self.assertEqual(summary["risk"]["by_state"], {"medium": 1})
        # Evidence presence is recorded on the row, but the existing services
        # treat the "required evidence absent" reason as missing evidence
        # (that is exactly why this row is medium/provide_missing_evidence),
        # so the summary reports the same uncertainty instead of hiding it.
        self.assertTrue(row["evidence_present"])
        self.assertEqual(
            self._kinds(summary["unknown_states"]),
            {"assessment_unknown", "missing_evidence"},
        )

    # Test 8: Low-risk case
    def test_low_risk_case(self) -> None:
        """Satisfied assessment yields low risk even without stored evidence."""
        req = _req_id(1)
        cases = [
            self._case(
                req,
                assessment="satisfied",
                assessment_reason="required evidence present",
            )
        ]

        summary = self.summary.summarize(cases, tenant_id=self.tenant_id)

        row = self._row(summary, req)
        self.assertEqual(row["risk_state"], "low")
        self.assertEqual(row["action_type"], "no_action_required")
        self.assertFalse(row["evidence_present"])
        self.assertEqual(summary["unknown_states"], [])

    # Test 9: Recommended actions preserved
    def test_recommended_actions_preserved(self) -> None:
        """Actions are exactly the existing service output, never rewritten."""
        cases = [
            self._case(_req_id(1), assessment="not_satisfied", evidence=[{"id": "e"}],
                       assessment_reason="evidence contradicts requirement"),
            self._case(_req_id(2), assessment="satisfied", evidence=[{"id": "e"}]),
            self._case(_req_id(3), assessment_reason="required evidence absent"),
            self._case(_req_id(4), applicability="unknown"),
            self._case(_req_id(5), applicability="not_applicable"),
        ]

        summary = self.summary.summarize(cases, tenant_id=self.tenant_id)
        expected = self.action_service.recommend(cases, tenant_id=self.tenant_id)
        expected = sorted(expected, key=lambda a: str(a["requirement_id"]))
        expected_via_integration = self.action_integration.recommend_from_risk(
            cases, tenant_id=self.tenant_id
        )
        expected_via_integration = sorted(
            expected_via_integration, key=lambda a: str(a["requirement_id"])
        )

        self.assertEqual(summary["actions"]["results"], expected)
        self.assertEqual(summary["actions"]["results"], expected_via_integration)
        self.assertEqual(
            self._ids(summary["actions"]["results"]), self._ids(expected)
        )
        self.assertEqual(summary["actions"]["recommendation_count"], len(expected))
        self.assertEqual(
            summary["actions"]["by_type"],
            {"address_requirement": 1, "no_action_required": 1,
             "provide_missing_evidence": 1, "review_requirement": 1},
        )

    # Test 10: Multiple requirements retain deterministic ordering
    def test_multiple_requirements_deterministic_ordering(self) -> None:
        """Every section is ordered by requirement id regardless of input order."""
        ordered_ids = [_req_id(i) for i in (1, 2, 3, 4)]
        cases = [
            self._case(_req_id(4), assessment_reason="required evidence absent"),
            self._case(_req_id(2), assessment="satisfied", evidence=[{"id": "e"}]),
            self._case(_req_id(3), applicability="not_applicable"),
            self._case(_req_id(1), assessment="not_satisfied",
                       assessment_reason="evidence contradicts requirement"),
        ]
        expected_ids = [str(req_id) for req_id in ordered_ids]
        # Requirement 3 is not_applicable, so existing semantics exclude it from
        # risk classification and action recommendation.
        applicable_ids = [str(_req_id(i)) for i in (1, 2, 4)]

        summary = self.summary.summarize(cases, tenant_id=self.tenant_id)

        self.assertEqual(self._ids(summary["requirements"]), expected_ids)
        self.assertEqual(self._ids(summary["risk"]["results"]), applicable_ids)
        self.assertEqual(self._ids(summary["actions"]["results"]), applicable_ids)
        self.assertEqual(
            self._ids(summary["applicability"]["results"]), expected_ids
        )

        # A different input order produces the identical structure.
        shuffled = self.summary.summarize(
            list(reversed(cases)), tenant_id=self.tenant_id
        )
        self.assertEqual(self._fingerprint(shuffled), self._fingerprint(summary))

    # Test 11: Tenant identity preserved
    def test_tenant_identity_preserved(self) -> None:
        """Summary carries the tenant and rejects cross-tenant input."""
        cases = [
            self._case(_req_id(1), assessment="satisfied", evidence=[{"id": "e"}])
        ]

        summary = self.summary.summarize(cases, tenant_id=self.tenant_id)

        self.assertEqual(summary["tenant_id"], self.tenant_id)
        for row in summary["requirements"]:
            self.assertEqual(row["requirement_id"], _req_id(1))

        # A case owned by another tenant cannot be summarized for this tenant.
        foreign = self._case(_req_id(2), tenant_id=OTHER_TENANT_ID)
        with self.assertRaises(ComplianceSummaryValidationError):
            self.summary.summarize([foreign], tenant_id=self.tenant_id)

        # A report owned by another tenant is rejected too.
        foreign_report = self._report([(1, "applicable")])
        foreign_report["tenant_id"] = OTHER_TENANT_ID
        with self.assertRaises(ComplianceSummaryValidationError):
            self.summary.summarize_from_applicability(
                foreign_report, tenant_id=self.tenant_id
            )

        # Summaries for different tenants never share state.
        other = self.summary.summarize(
            [self._case(_req_id(3), tenant_id=OTHER_TENANT_ID)],
            tenant_id=OTHER_TENANT_ID,
        )
        self.assertEqual(other["tenant_id"], OTHER_TENANT_ID)
        self.assertNotEqual(other["requirements"], summary["requirements"])

    # Test 12: Deterministic identical-input output
    def test_deterministic_identical_input(self) -> None:
        """Independent instances produce byte-identical summaries."""
        cases = [
            self._case(_req_id(1), assessment="not_satisfied",
                       assessment_reason="evidence contradicts requirement"),
            self._case(_req_id(2), assessment_reason="required evidence absent"),
            self._case(_req_id(3), applicability="unknown"),
        ]

        first = self.summary.summarize(cases, tenant_id=self.tenant_id)
        second = ComplianceDecisionSummaryService().summarize(
            copy.deepcopy(cases), tenant_id=self.tenant_id
        )
        third = self.summary.summarize(cases, tenant_id=self.tenant_id)

        self.assertEqual(self._fingerprint(first), self._fingerprint(second))
        self.assertEqual(self._fingerprint(second), self._fingerprint(third))
        self.assertEqual(first, second)
        self.assertEqual(first, third)

    # Test 13: Empty-input behavior
    def test_empty_input_behavior(self) -> None:
        """An empty case set yields an explicit empty summary, not an error."""
        summary = self.summary.summarize([], tenant_id=self.tenant_id)

        self.assertEqual(summary["tenant_id"], self.tenant_id)
        self.assertEqual(summary["status"], "decision_summary")
        self.assertIsNone(summary["context_fingerprint"])
        self.assertEqual(summary["applicability"]["total_requirements"], 0)
        self.assertEqual(summary["applicability"]["applicable_count"], 0)
        self.assertEqual(summary["applicability"]["not_applicable_count"], 0)
        self.assertEqual(summary["applicability"]["unknown_count"], 0)
        self.assertEqual(summary["applicability"]["results"], [])
        self.assertEqual(summary["risk"]["classified_count"], 0)
        self.assertEqual(summary["risk"]["by_state"], {})
        self.assertEqual(summary["risk"]["results"], [])
        self.assertEqual(summary["actions"]["recommendation_count"], 0)
        self.assertEqual(summary["actions"]["by_type"], {})
        self.assertEqual(summary["actions"]["results"], [])
        self.assertEqual(summary["unknown_states"], [])
        self.assertEqual(summary["requirements"], [])

    # Test 14: Existing risk/action services remain unchanged
    def test_existing_services_remain_unchanged(self) -> None:
        """The boundary adds no rules and introduces no new states or actions."""
        source = MODULE_PATH.read_text(encoding="utf-8")
        risk_body = source.split("class ComplianceRiskService:", 1)[1].split(
            "class ComplianceActionRecommendationService:", 1
        )[0]
        action_body = source.split(
            "class ComplianceActionRecommendationService:", 1
        )[1].split("class RiskToActionIntegration:", 1)[0]

        # Existing services are unaware of the new summary boundary.
        self.assertNotIn("ComplianceDecisionSummaryService", risk_body)
        self.assertNotIn("ComplianceDecisionSummaryService", action_body)

        # No invented risk states or action types exist in the source of truth.
        states = set(re.findall(r'state = "([a-z_]+)"', risk_body))
        self.assertTrue(states)
        self.assertTrue(states.issubset(ALLOWED_RISK_STATES))
        action_types = set(re.findall(r'action_type = "([a-z_]+)"', action_body))
        self.assertEqual(action_types, ALLOWED_ACTION_TYPES)

        # Behaviour is unchanged before and after summarizing.
        cases = [
            self._case(
                _req_id(1),
                assessment="not_satisfied",
                assessment_reason="evidence contradicts requirement",
                evidence=[{"id": "e"}],
            )
        ]
        risk_before = self.risk_service.classify(cases, tenant_id=self.tenant_id)
        actions_before = self.action_service.recommend(cases, tenant_id=self.tenant_id)

        summary = self.summary.summarize(cases, tenant_id=self.tenant_id)

        self.assertEqual(
            self.risk_service.classify(cases, tenant_id=self.tenant_id), risk_before
        )
        self.assertEqual(
            self.action_service.recommend(cases, tenant_id=self.tenant_id), actions_before
        )
        self.assertEqual(summary["risk"]["results"], risk_before)
        self.assertEqual(summary["actions"]["results"], actions_before)

    # Test 15: End-to-end Applicability → Risk → Action → Summary flow
    def test_end_to_end_real_services_flow(self) -> None:
        """Real services drive the flow; the summary only joins their outputs."""
        requirements = [
            {
                "id": _req_id(1),
                "requirement_text": "Cocoa exports to Nigeria must be registered.",
                "actor": "exporter",
            },
            {
                "id": _req_id(2),
                "requirement_text": "Coffee exports to Ghana must file monthly returns.",
                "actor": "exporter",
            },
        ]
        report = self.applicability_service.determine(requirements, self.context)

        self.assertEqual(report["applicable_count"], 1)
        self.assertEqual(report["not_applicable_count"], 1)

        # Phase 3.3 and Phase 3.4 stages read the real report shape.
        classified = self.risk_integration.classify_from_applicability(
            report, tenant_id=self.tenant_id
        )
        self.assertEqual(len(classified), 1)
        self.assertEqual(classified[0]["state"], "medium")

        pipeline = self.action_integration.full_pipeline(
            report, tenant_id=self.tenant_id
        )
        self.assertEqual(len(pipeline["risk_results"]), 1)
        self.assertEqual(
            [action["action_type"] for action in pipeline["action_recommendations"]],
            ["provide_missing_evidence"],
        )

        # Phase 3.5 summary over the same real report.
        summary = self.summary.summarize_from_applicability(
            report, tenant_id=self.tenant_id
        )

        self.assertEqual(summary["tenant_id"], self.tenant_id)
        self.assertEqual(summary["status"], "decision_summary")
        self.assertEqual(summary["context_fingerprint"], report["context_fingerprint"])
        self.assertEqual(
            summary["applicability"]["applicable_count"],
            report["applicable_count"],
        )
        self.assertEqual(
            summary["applicability"]["not_applicable_count"],
            report["not_applicable_count"],
        )
        self.assertEqual(
            summary["applicability"]["unknown_count"], report["unknown_count"]
        )
        self.assertEqual(
            summary["risk"]["classified_count"], report["applicable_count"]
        )
        self.assertEqual(summary["risk"]["by_state"], {"medium": 1})
        self.assertEqual(
            summary["actions"]["by_type"], {"provide_missing_evidence": 1}
        )

        applicable_row = self._row(summary, _req_id(1))
        excluded_row = self._row(summary, _req_id(2))
        self.assertEqual(applicable_row["applicability_outcome"], "applicable")
        self.assertEqual(applicable_row["risk_state"], "medium")
        self.assertEqual(applicable_row["action_type"], "provide_missing_evidence")
        # A report carries no assessment or evidence; nothing is invented.
        self.assertIsNone(applicable_row["assessment_outcome"])
        self.assertIsNone(applicable_row["evidence_present"])
        self.assertEqual(excluded_row["applicability_outcome"], "not_applicable")
        self.assertIsNone(excluded_row["risk_state"])
        self.assertIsNone(excluded_row["action_type"])
        self.assertEqual(summary["unknown_states"], [])

        # Summarizing equivalent hand-built cases agrees on states and actions.
        equivalent = self.summary.summarize(
            [
                self._case(_req_id(1)),
                self._case(_req_id(2), applicability="not_applicable"),
            ],
            tenant_id=self.tenant_id,
        )
        self.assertEqual(
            [
                (row["requirement_id"], row["risk_state"])
                for row in equivalent["requirements"]
            ],
            [
                (row["requirement_id"], row["risk_state"])
                for row in summary["requirements"]
            ],
        )
        self.assertEqual(
            [
                (row["requirement_id"], row["action_type"])
                for row in equivalent["requirements"]
            ],
            [
                (row["requirement_id"], row["action_type"])
                for row in summary["requirements"]
            ],
        )

        # Deterministic across repeated calls.
        again = self.summary.summarize_from_applicability(
            report, tenant_id=self.tenant_id
        )
        self.assertEqual(self._fingerprint(again), self._fingerprint(summary))

    # Test 16: Input validation
    def test_input_validation(self) -> None:
        """Invalid input is rejected through the existing validation error type."""
        with self.assertRaises(ComplianceSummaryValidationError):
            self.summary.summarize("not a list", tenant_id=self.tenant_id)

        with self.assertRaises(ComplianceSummaryValidationError):
            self.summary.summarize([], tenant_id="not-a-uuid")

        with self.assertRaises(ComplianceSummaryValidationError):
            self.summary.summarize_from_applicability(
                "not a dict", tenant_id=self.tenant_id
            )

        with self.assertRaises(ComplianceSummaryValidationError):
            self.summary.summarize_from_applicability(
                self._report([(1, "applicable")]), tenant_id="not-a-uuid"
            )

        with self.assertRaises(ComplianceSummaryValidationError):
            self.summary.summarize(
                [{"tenant_id": self.tenant_id}], tenant_id=self.tenant_id
            )

if __name__ == "__main__":
    unittest.main()
