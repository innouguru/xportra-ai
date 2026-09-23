"""Phase 3.7 - Evidence Requirement / Retrieval Contract Boundary tests."""

import copy
import json
import unittest
from uuid import UUID

from xportra.domain.ingestion import (
    ApplicabilityContext,
    ComplianceApplicabilityService,
    ComplianceCaseReadinessService,
    ComplianceDecisionSummaryService,
    ComplianceSummaryValidationError,
    EvidenceRequirementPlanService,
)

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
REQ_A = UUID("11111111-1111-1111-1111-00000000000a")
REQ_B = UUID("11111111-1111-1111-1111-00000000000b")
REQ_C = UUID("11111111-1111-1111-1111-00000000000c")


class TestEvidenceRequirementPlan(unittest.TestCase):
    def setUp(self) -> None:
        self.readiness = ComplianceCaseReadinessService()
        self.service = EvidenceRequirementPlanService()
        self.tenant_id = TENANT_ID

    def _make_case(self, rid, **kw) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "requirement": {
                "id": rid,
                "text": f"Requirement {str(rid)[-12:]}",
                "type": "documentation",
            },
            "applicability": {
                "outcome": kw.get("applicability", "applicable"),
                "reason": kw.get("applicability_reason", "determined"),
            },
            "assessment": {
                "outcome": kw.get("assessment", "unknown"),
                "reason": kw.get(
                    "assessment_reason", "assessment not yet performed"
                ),
            },
            "evidence": kw.get("evidence", []),
        }

    def _plan_for_cases(self, cases) -> dict:
        rep = self.readiness.assess(cases, tenant_id=self.tenant_id)
        return self.service.plan(rep, tenant_id=self.tenant_id)

    def _rep_for_cases(self, cases) -> dict:
        return self.readiness.assess(cases, tenant_id=self.tenant_id)

    def test_01_ready_case_empty_plan(self) -> None:
        case = self._make_case(
            REQ_A, assessment="satisfied",
            assessment_reason="assessment completed",
            evidence=[{"id": "ev-1"}],
        )
        rep = self._rep_for_cases([case])
        self.assertEqual(rep["readiness_state"], "ready")
        plan = self.service.plan(rep, tenant_id=self.tenant_id)
        self.assertEqual(plan["status"], "evidence_requirement_plan")
        self.assertEqual(plan["required_count"], 0)
        self.assertEqual(plan["items"], [])
        self.assertEqual(plan["readiness_state"], "ready")

    def test_02_missing_evidence(self) -> None:
        rep = self._rep_for_cases([self._make_case(REQ_A)])
        self.assertIn(REQ_A, rep["missing_evidence_requirements"])
        plan = self.service.plan(rep, tenant_id=self.tenant_id)
        kinds = {(i["requirement_id"], i["gap_kind"]) for i in plan["items"]}
        self.assertIn((REQ_A, "missing_evidence"), kinds)
        item = next(i for i in plan["items"] if i["gap_kind"] == "missing_evidence")
        self.assertEqual(item["status"], "required")
        self.assertEqual(item["tenant_id"], self.tenant_id)

    def test_03_unknown_assessment(self) -> None:
        rep = self._rep_for_cases(
            [self._make_case(REQ_A, evidence=[{"id": "ev-1"}])]
        )
        self.assertIn(REQ_A, rep["unknown_assessment_requirements"])
        plan = self.service.plan(rep, tenant_id=self.tenant_id)
        kinds = {(i["requirement_id"], i["gap_kind"]) for i in plan["items"]}
        self.assertIn((REQ_A, "assessment_unknown"), kinds)

    def test_04_unknown_applicability(self) -> None:
        rep = self._rep_for_cases(
            [self._make_case(REQ_A, applicability="unknown")]
        )
        self.assertEqual(rep["readiness_state"], "not_ready")
        plan = self.service.plan(rep, tenant_id=self.tenant_id)
        kinds = {(i["requirement_id"], i["gap_kind"]) for i in plan["items"]}
        self.assertIn((REQ_A, "applicability_unknown"), kinds)

    def test_05_unknown_risk(self) -> None:
        rep = self._rep_for_cases(
            [self._make_case(REQ_A, evidence=[{"id": "ev-1"}])]
        )
        self.assertIn(REQ_A, rep["unknown_risk_requirements"])
        plan = self.service.plan(rep, tenant_id=self.tenant_id)
        kinds = {(i["requirement_id"], i["gap_kind"]) for i in plan["items"]}
        self.assertIn((REQ_A, "risk_unknown"), kinds)

    def test_06_multiple_gaps(self) -> None:
        rep = self._rep_for_cases(
            [self._make_case(REQ_A),
             self._make_case(REQ_B, applicability="unknown")]
        )
        plan = self.service.plan(rep, tenant_id=self.tenant_id)
        self.assertEqual(plan["required_count"], len(plan["items"]))
        self.assertGreaterEqual(len(plan["items"]), 3)
        self.assertEqual(plan["required_count"], len(rep["gaps"]))

    def test_07_deterministic_ids(self) -> None:
        plan = self._plan_for_cases(
            [self._make_case(REQ_A),
             self._make_case(REQ_B, applicability="unknown")]
        )
        for item in plan["items"]:
            exp = f"{item['requirement_id']}:{item['gap_kind']}"
            self.assertEqual(item["evidence_requirement_id"], exp)
        ids = [i["evidence_requirement_id"] for i in plan["items"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_08_deterministic_ordering(self) -> None:
        plan = self._plan_for_cases(
            [self._make_case(REQ_C),
             self._make_case(REQ_A),
             self._make_case(REQ_B, applicability="unknown")]
        )
        keys = [(str(i["requirement_id"]), i["gap_kind"],
                 i["evidence_requirement_id"]) for i in plan["items"]]
        self.assertEqual(keys, sorted(keys))

    def test_09_identical_input_identical_plan(self) -> None:
        rep = self._rep_for_cases(
            [self._make_case(REQ_A),
             self._make_case(REQ_B, applicability="unknown")]
        )
        first = self.service.plan(copy.deepcopy(rep), tenant_id=self.tenant_id)
        second = self.service.plan(copy.deepcopy(rep), tenant_id=self.tenant_id)
        self.assertEqual(
            json.dumps(first, sort_keys=True, default=str),
            json.dumps(second, sort_keys=True, default=str),
        )

    def test_10_tenant_preserved(self) -> None:
        plan = self._plan_for_cases([self._make_case(REQ_A)])
        self.assertEqual(plan["tenant_id"], self.tenant_id)
        for item in plan["items"]:
            self.assertEqual(item["tenant_id"], self.tenant_id)

    def test_11_invalid_tenant_rejected(self) -> None:
        rep = self._rep_for_cases([self._make_case(REQ_A)])
        with self.assertRaises(ComplianceSummaryValidationError):
            self.service.plan(rep, tenant_id=OTHER_TENANT_ID)
        with self.assertRaises(ComplianceSummaryValidationError):
            self.service.plan("bad", tenant_id=self.tenant_id)
        with self.assertRaises(ComplianceSummaryValidationError):
            self.service.plan(rep, tenant_id="bad")
        with self.assertRaises(ComplianceSummaryValidationError):
            self.service.plan({"status": "decision_summary"},
                              tenant_id=self.tenant_id)

    def test_12_no_false_inference(self) -> None:
        ok_case = self._make_case(
            REQ_A, assessment="satisfied",
            assessment_reason="assessment completed",
            evidence=[{"id": "ev-1"}],
        )
        na_case = self._make_case(REQ_B, applicability="not_applicable")
        plan = self._plan_for_cases([ok_case, na_case])
        self.assertEqual(plan["items"], [])
        self.assertEqual(plan["required_count"], 0)

    def test_13_gap_kind_preserved(self) -> None:
        rep = self._rep_for_cases(
            [self._make_case(REQ_A),
             self._make_case(REQ_B, applicability="unknown")]
        )
        plan = self.service.plan(rep, tenant_id=self.tenant_id)
        self.assertEqual(
            {(g["requirement_id"], g["kind"]) for g in rep["gaps"]},
            {(i["requirement_id"], i["gap_kind"]) for i in plan["items"]},
        )

    def test_14_requirement_id_preserved(self) -> None:
        plan = self._plan_for_cases(
            [self._make_case(REQ_A), self._make_case(REQ_B)]
        )
        ids = {i["requirement_id"] for i in plan["items"]}
        self.assertIn(REQ_A, ids)
        self.assertIn(REQ_B, ids)

    def test_15_action_signal_preserved(self) -> None:
        rep = self._rep_for_cases(
            [self._make_case(REQ_A),
             self._make_case(REQ_B, applicability="unknown")]
        )
        expected = {str(a["requirement_id"]): a["action_type"]
                    for a in rep["actions_requiring_evidence"]}
        plan = self.service.plan(rep, tenant_id=self.tenant_id)
        self.assertTrue(expected)
        for item in plan["items"]:
            self.assertEqual(item["triggering_action"],
                             expected.get(str(item["requirement_id"])))


    def test_16_empty_input(self) -> None:
        rep = self._rep_for_cases([])
        self.assertEqual(rep["readiness_state"], "not_ready")
        first = self.service.plan(rep, tenant_id=self.tenant_id)
        second = self.service.plan(copy.deepcopy(rep), tenant_id=self.tenant_id)
        self.assertEqual(first["items"], [])
        self.assertEqual(first["required_count"], 0)
        self.assertEqual(first["status"], "evidence_requirement_plan")
        self.assertEqual(
            json.dumps(first, sort_keys=True, default=str),
            json.dumps(second, sort_keys=True, default=str),
        )

    def test_17_no_verdict(self) -> None:
        plan = self._plan_for_cases([self._make_case(REQ_A)])
        # No compliance verdict fields exist on the plan.
        self.assertNotIn("compliance_state", plan)
        self.assertNotIn("verdict", plan)
        self.assertNotIn("compliant", plan)
        # The boundary states its non-verdict nature explicitly.
        self.assertIn("neither compliance nor non-compliance",
                      plan["plan_not_verdict"])
        self.assertIn("retrieval_boundary", plan)

    def test_18_readiness_unchanged(self) -> None:
        rep = self._rep_for_cases(
            [self._make_case(REQ_A), self._make_case(REQ_B)]
        )
        snap = copy.deepcopy(rep)
        self.service.plan(rep, tenant_id=self.tenant_id)
        self.assertEqual(rep, snap)

    def test_19_summary_unchanged(self) -> None:
        cases = [self._make_case(REQ_A), self._make_case(REQ_B)]
        before = ComplianceDecisionSummaryService().summarize(
            copy.deepcopy(cases), tenant_id=self.tenant_id)
        rep = self._rep_for_cases(cases)
        self.service.plan(rep, tenant_id=self.tenant_id)
        after = ComplianceDecisionSummaryService().summarize(
            copy.deepcopy(cases), tenant_id=self.tenant_id)
        self.assertEqual(before, after)

    def test_20_end_to_end(self) -> None:
        ctx = ApplicabilityContext(
            tenant_id=self.tenant_id, destination_country="ng",
            commodity="cocoa", actor_role="exporter",
        )
        reqs = [
            {"id": REQ_A,
             "requirement_text": "Exporters of cocoa to Nigeria must register.",
             "actor": "exporter"},
            {"id": REQ_B,
             "requirement_text": "Coffee exporters to Ghana must file returns.",
             "actor": "exporter"},
            {"id": REQ_C, "requirement_text": "Producers must maintain records.",
             "actor": "producer"},
        ]
        det = ComplianceApplicabilityService().determine(reqs, ctx)
        texts = {r["id"]: r["requirement_text"] for r in reqs}
        cases = [{
            "tenant_id": self.tenant_id,
            "context_fingerprint": det["context_fingerprint"],
            "requirement": {"id": x["requirement_id"],
                            "text": texts[x["requirement_id"]],
                            "type": "documentation"},
            "applicability": {"outcome": x["outcome"], "reason": x["reason"]},
            "assessment": {"outcome": "unknown",
                           "reason": "assessment not yet performed"},
            "evidence": [],
        } for x in det["results"]]
        rep = self.readiness.assess(cases, tenant_id=self.tenant_id)
        plan = self.service.plan(rep, tenant_id=self.tenant_id)
        self.assertEqual(plan["tenant_id"], self.tenant_id)
        self.assertEqual(plan["context_fingerprint"], rep["context_fingerprint"])
        self.assertEqual(plan["readiness_state"], rep["readiness_state"])
        self.assertEqual(plan["required_count"], len(rep["gaps"]))
        self.assertEqual(
            {(i["requirement_id"], i["gap_kind"]) for i in plan["items"]},
            {(g["requirement_id"], g["kind"]) for g in rep["gaps"]},
        )


if __name__ == "__main__":
    unittest.main()


