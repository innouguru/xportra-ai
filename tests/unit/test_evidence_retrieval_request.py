"""Phase 3.8 - Evidence Retrieval Boundary tests."""

import copy
import json
import unittest
from uuid import UUID

from xportra.domain.ingestion import (
    ComplianceCaseReadinessService,
    ComplianceSummaryValidationError,
    EvidenceRequirementPlanService,
    EvidenceRetrievalRequestService,
)

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
REQ_A = UUID("11111111-1111-1111-1111-00000000000a")
REQ_B = UUID("11111111-1111-1111-1111-00000000000b")
REQ_C = UUID("11111111-1111-1111-1111-00000000000c")


class TestEvidenceRetrievalRequest(unittest.TestCase):
    def setUp(self) -> None:
        self.readiness = ComplianceCaseReadinessService()
        self.planner = EvidenceRequirementPlanService()
        self.service = EvidenceRetrievalRequestService()
        self.tenant_id = TENANT_ID

    def _make_case(self, rid, **kw) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "requirement": {
                "id": rid,
                "text": kw.get("text", f"Requirement {str(rid)[-12:]}"),
                "type": "documentation",
            },
            "applicability": {
                "outcome": kw.get("applicability", "applicable"),
                "reason": kw.get("applicability_reason", "determined"),
            },
            "assessment": {
                "outcome": kw.get("assessment", "unknown"),
                "reason": kw.get(
                    "assessment_reason", "assessment not yet performed"),
            },
            "evidence": kw.get("evidence", []),
        }

    def _plan_for_cases(self, cases) -> dict:
        rep = self.readiness.assess(cases, tenant_id=self.tenant_id)
        return self.planner.plan(rep, tenant_id=self.tenant_id)

    def _req_for_cases(self, cases) -> dict:
        return self.service.build(
            self._plan_for_cases(cases), tenant_id=self.tenant_id)

    def test_01_empty_plan_zero_requests(self) -> None:
        ok_case = self._make_case(
            REQ_A, assessment="satisfied",
            assessment_reason="assessment completed",
            evidence=[{"id": "ev-1"}],
        )
        plan = self._plan_for_cases([ok_case])
        self.assertEqual(plan["items"], [])
        out = self.service.build(plan, tenant_id=self.tenant_id)
        self.assertEqual(out["status"], "evidence_retrieval_request")
        self.assertEqual(out["request_count"], 0)
        self.assertEqual(out["requests"], [])

    def test_02_missing_evidence_one_request(self) -> None:
        out = self._req_for_cases([self._make_case(REQ_A)])
        kinds = {(r["requirement_id"], r["gap_kind"]) for r in out["requests"]}
        self.assertIn((REQ_A, "missing_evidence"), kinds)

    def test_03_unknown_applicability(self) -> None:
        out = self._req_for_cases(
            [self._make_case(REQ_A, applicability="unknown")])
        kinds = {(r["requirement_id"], r["gap_kind"]) for r in out["requests"]}
        self.assertIn((REQ_A, "applicability_unknown"), kinds)

    def test_04_unknown_assessment(self) -> None:
        out = self._req_for_cases(
            [self._make_case(REQ_A, evidence=[{"id": "ev-1"}])])
        kinds = {(r["requirement_id"], r["gap_kind"]) for r in out["requests"]}
        self.assertIn((REQ_A, "assessment_unknown"), kinds)

    def test_05_unknown_risk(self) -> None:
        out = self._req_for_cases(
            [self._make_case(REQ_A, evidence=[{"id": "ev-1"}])])
        kinds = {(r["requirement_id"], r["gap_kind"]) for r in out["requests"]}
        self.assertIn((REQ_A, "risk_unknown"), kinds)

    def test_06_multiple_requirements(self) -> None:
        plan = self._plan_for_cases(
            [self._make_case(REQ_A),
             self._make_case(REQ_B, applicability="unknown")])
        out = self.service.build(plan, tenant_id=self.tenant_id)
        self.assertEqual(out["request_count"], len(out["requests"]))
        self.assertEqual(out["request_count"], len(plan["items"]))
        self.assertGreaterEqual(len(out["requests"]), 3)

    def test_07_evidence_requirement_id_preserved(self) -> None:
        plan = self._plan_for_cases([self._make_case(REQ_A)])
        out = self.service.build(plan, tenant_id=self.tenant_id)
        self.assertEqual(
            {r["evidence_requirement_id"] for r in out["requests"]},
            {i["evidence_requirement_id"] for i in plan["items"]})

    def test_08_requirement_id_preserved(self) -> None:
        out = self._req_for_cases(
            [self._make_case(REQ_A), self._make_case(REQ_B)])
        ids = {r["requirement_id"] for r in out["requests"]}
        self.assertIn(REQ_A, ids)
        self.assertIn(REQ_B, ids)

    def test_09_gap_kind_preserved(self) -> None:
        plan = self._plan_for_cases([self._make_case(REQ_A)])
        out = self.service.build(plan, tenant_id=self.tenant_id)
        self.assertEqual(
            {(i["requirement_id"], i["gap_kind"]) for i in plan["items"]},
            {(r["requirement_id"], r["gap_kind"]) for r in out["requests"]})

    def test_10_priority_preserved(self) -> None:
        plan = self._plan_for_cases(
            [self._make_case(REQ_A), self._make_case(REQ_B)])
        out = self.service.build(plan, tenant_id=self.tenant_id)
        by_id = {i["evidence_requirement_id"]: i for i in plan["items"]}
        for r in out["requests"]:
            self.assertEqual(r["priority"],
                             by_id[r["evidence_requirement_id"]]["priority"])

    def test_11_status_preserved(self) -> None:
        plan = self._plan_for_cases([self._make_case(REQ_A)])
        out = self.service.build(plan, tenant_id=self.tenant_id)
        by_id = {i["evidence_requirement_id"]: i for i in plan["items"]}
        for r in out["requests"]:
            self.assertEqual(r["status"],
                             by_id[r["evidence_requirement_id"]]["status"])
            self.assertEqual(r["status"], "required")

    def test_12_deterministic_identity(self) -> None:
        out = self._req_for_cases([self._make_case(REQ_A)])
        for r in out["requests"]:
            self.assertEqual(r["evidence_requirement_id"],
                             f"{r['requirement_id']}:{r['gap_kind']}")
        ids = [r["evidence_requirement_id"] for r in out["requests"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_13_identical_input_identical_output(self) -> None:
        plan = self._plan_for_cases(
            [self._make_case(REQ_A),
             self._make_case(REQ_B, applicability="unknown")])
        first = self.service.build(copy.deepcopy(plan),
                                   tenant_id=self.tenant_id)
        second = self.service.build(copy.deepcopy(plan),
                                    tenant_id=self.tenant_id)
        self.assertEqual(
            json.dumps(first, sort_keys=True, default=str),
            json.dumps(second, sort_keys=True, default=str))

    def test_14_deterministic_ordering(self) -> None:
        out = self._req_for_cases(
            [self._make_case(REQ_C),
             self._make_case(REQ_A),
             self._make_case(REQ_B, applicability="unknown")])
        keys = [(str(r["requirement_id"]), r["gap_kind"],
                 str(r["evidence_requirement_id"])) for r in out["requests"]]
        self.assertEqual(keys, sorted(keys))

    def test_15_query_from_plan_info(self) -> None:
        plan = self._plan_for_cases(
            [self._make_case(REQ_A, text="  Phytosanitary certificate  ")])
        out = self.service.build(plan, tenant_id=self.tenant_id)
        item = next(r for r in out["requests"]
                    if r["requirement_id"] == REQ_A)
        self.assertEqual(item["query"], "Phytosanitary certificate")

    def test_16_no_fact_inference_in_query(self) -> None:
        out = self._req_for_cases(
            [self._make_case(REQ_A, text="Phytosanitary certificate")])
        item = next(r for r in out["requests"]
                    if r["requirement_id"] == REQ_A)
        lowered = item["query"].lower()
        for invented in ("exporter x", "nigerian authorities",
                         "issued", "2026", "date y"):
            self.assertNotIn(invented, lowered)
        rep = self.readiness.assess(
            [self._make_case(REQ_A, text="Phytosanitary certificate")],
            tenant_id=self.tenant_id)
        plan = self.planner.plan(rep, tenant_id=self.tenant_id)
        expected = next(i for i in plan["items"]
                        if i["requirement_id"] == REQ_A)["requirement"].strip()
        self.assertEqual(item["query"], expected)

    def test_17_scope_deterministic(self) -> None:
        out = self._req_for_cases(
            [self._make_case(REQ_A), self._make_case(REQ_B)])
        for r in out["requests"]:
            self.assertEqual(r["retrieval_scope"], "requirement_evidence")

    def test_18_tenant_preserved(self) -> None:
        plan = self._plan_for_cases([self._make_case(REQ_A)])
        out = self.service.build(plan, tenant_id=self.tenant_id)
        self.assertEqual(out["tenant_id"], self.tenant_id)
        for r in out["requests"]:
            self.assertEqual(r["tenant_id"], self.tenant_id)

    def test_19_invalid_cross_tenant_rejected(self) -> None:
        plan = self._plan_for_cases([self._make_case(REQ_A)])
        with self.assertRaises(ComplianceSummaryValidationError):
            self.service.build(plan, tenant_id=OTHER_TENANT_ID)
        with self.assertRaises(ComplianceSummaryValidationError):
            self.service.build("bad", tenant_id=self.tenant_id)
        with self.assertRaises(ComplianceSummaryValidationError):
            self.service.build(plan, tenant_id="bad")
        with self.assertRaises(ComplianceSummaryValidationError):
            self.service.build({"status": "readiness_report"},
                               tenant_id=self.tenant_id)

    def test_21_non_dict_item_rejected(self) -> None:
        plan = self._plan_for_cases([self._make_case(REQ_A)])
        bad = copy.deepcopy(plan)
        bad["items"].append("not-a-dict")
        with self.assertRaises(ComplianceSummaryValidationError):
            self.service.build(bad, tenant_id=self.tenant_id)

    def test_22_missing_field_rejected(self) -> None:
        plan = self._plan_for_cases([self._make_case(REQ_A)])
        for field in ("requirement_id", "evidence_requirement_id",
                      "gap_kind"):
            bad = copy.deepcopy(plan)
            del bad["items"][0][field]
            with self.assertRaises(ComplianceSummaryValidationError):
                self.service.build(bad, tenant_id=self.tenant_id)

    def test_23_malformed_gap_kind_rejected(self) -> None:
        plan = self._plan_for_cases([self._make_case(REQ_A)])
        for gap in ("missing", "", None, 123, "MISSING_EVIDENCE"):
            bad = copy.deepcopy(plan)
            bad["items"][0]["gap_kind"] = gap
            bad["items"][0]["evidence_requirement_id"] = (
                f"{bad['items'][0]['requirement_id']}:{gap}")
            with self.assertRaises(ComplianceSummaryValidationError):
                self.service.build(bad, tenant_id=self.tenant_id)

    def test_24_malformed_identity_rejected(self) -> None:
        plan = self._plan_for_cases([self._make_case(REQ_A)])
        bad = copy.deepcopy(plan)
        bad["items"][0]["evidence_requirement_id"] = "tampered-id"
        with self.assertRaises(ComplianceSummaryValidationError):
            self.service.build(bad, tenant_id=self.tenant_id)
        bad = copy.deepcopy(plan)
        bad["items"][0]["evidence_requirement_id"] = 12345
        with self.assertRaises(ComplianceSummaryValidationError):
            self.service.build(bad, tenant_id=self.tenant_id)

    def test_25_cross_tenant_item_rejected(self) -> None:
        plan = self._plan_for_cases([self._make_case(REQ_A)])
        bad = copy.deepcopy(plan)
        bad["items"][0]["tenant_id"] = OTHER_TENANT_ID
        with self.assertRaises(ComplianceSummaryValidationError):
            self.service.build(bad, tenant_id=self.tenant_id)

    def test_20_end_to_end_and_unchanged(self) -> None:
        plan = self._plan_for_cases(
            [self._make_case(REQ_A),
             self._make_case(REQ_B, applicability="unknown")])
        snap = copy.deepcopy(plan)
        out = self.service.build(plan, tenant_id=self.tenant_id)
        self.assertEqual(plan, snap)
        self.assertEqual(out["tenant_id"], self.tenant_id)
        self.assertEqual(out["context_fingerprint"],
                         plan["context_fingerprint"])
        self.assertEqual(out["readiness_state"], plan["readiness_state"])
        self.assertEqual(out["request_count"], len(plan["items"]))
        again = self._plan_for_cases(
            [self._make_case(REQ_A),
             self._make_case(REQ_B, applicability="unknown")])
        self.assertEqual(plan, again)


if __name__ == "__main__":
    unittest.main()



