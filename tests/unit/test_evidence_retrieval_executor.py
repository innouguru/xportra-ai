"""Phase 3.9 - Evidence Retrieval Execution Boundary tests."""

import copy
import json
import unittest
from uuid import UUID

from xportra.domain.ingestion import (
    ComplianceCaseReadinessService,
    ComplianceSummaryValidationError,
    EvidenceRequirementPlanService,
    EvidenceRetrievalExecutor,
    EvidenceRetrievalRequestService,
    EvidenceRetrievalResultBuilder,
    NoOpEvidenceRetrievalExecutor,
)

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
REQ_A = UUID("11111111-1111-1111-1111-00000000000a")
REQ_B = UUID("11111111-1111-1111-1111-00000000000b")


class TestEvidenceRetrievalExecutor(unittest.TestCase):
    def setUp(self) -> None:
        self.readiness = ComplianceCaseReadinessService()
        self.planner = EvidenceRequirementPlanService()
        self.requests = EvidenceRetrievalRequestService()
        self.builder = EvidenceRetrievalResultBuilder()
        self.noop = NoOpEvidenceRetrievalExecutor()
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
                "reason": "determined",
            },
            "assessment": {
                "outcome": kw.get("assessment", "unknown"),
                "reason": "assessment not yet performed",
            },
            "evidence": kw.get("evidence", []),
        }

    def _request(self, rid=REQ_A, **kw) -> dict:
        cases = [self._make_case(rid, **kw)]
        rep = self.readiness.assess(cases, tenant_id=self.tenant_id)
        plan = self.planner.plan(rep, tenant_id=self.tenant_id)
        built = self.requests.build(plan, tenant_id=self.tenant_id)
        return built["requests"][0]

    def test_01_valid_request_accepted(self) -> None:
        req = self._request()
        out = self.noop.execute(req, tenant_id=self.tenant_id)
        self.assertEqual(out["result_status"], "retrieval_result")

    def test_02_malformed_request_rejected(self) -> None:
        with self.assertRaises(ComplianceSummaryValidationError):
            self.noop.execute("bad", tenant_id=self.tenant_id)

    def test_03_invalid_tenant_rejected(self) -> None:
        req = self._request()
        with self.assertRaises(ComplianceSummaryValidationError):
            self.noop.execute(req, tenant_id="bad")

    def test_04_cross_tenant_rejected(self) -> None:
        req = self._request()
        with self.assertRaises(ComplianceSummaryValidationError):
            self.noop.execute(req, tenant_id=OTHER_TENANT_ID)

    def test_05_invalid_gap_kind_rejected(self) -> None:
        req = self._request()
        bad = copy.deepcopy(req)
        bad["gap_kind"] = "missing"
        with self.assertRaises(ComplianceSummaryValidationError):
            self.noop.execute(bad, tenant_id=self.tenant_id)

    def test_06_missing_er_identity_rejected(self) -> None:
        req = self._request()
        bad = copy.deepcopy(req)
        del bad["evidence_requirement_id"]
        with self.assertRaises(ComplianceSummaryValidationError):
            self.noop.execute(bad, tenant_id=self.tenant_id)

    def test_07_missing_requirement_id_rejected(self) -> None:
        req = self._request()
        bad = copy.deepcopy(req)
        del bad["requirement_id"]
        with self.assertRaises(ComplianceSummaryValidationError):
            self.noop.execute(bad, tenant_id=self.tenant_id)

    def test_08_missing_query_rejected(self) -> None:
        req = self._request()
        bad = copy.deepcopy(req)
        del bad["query"]
        with self.assertRaises(ComplianceSummaryValidationError):
            self.noop.execute(bad, tenant_id=self.tenant_id)

    def test_09_missing_scope_rejected(self) -> None:
        req = self._request()
        bad = copy.deepcopy(req)
        del bad["retrieval_scope"]
        with self.assertRaises(ComplianceSummaryValidationError):
            self.noop.execute(bad, tenant_id=self.tenant_id)

    def test_10_missing_status_rejected(self) -> None:
        req = self._request()
        bad = copy.deepcopy(req)
        del bad["status"]
        with self.assertRaises(ComplianceSummaryValidationError):
            self.noop.execute(bad, tenant_id=self.tenant_id)

    def test_11_missing_priority_rejected(self) -> None:
        req = self._request()
        bad = copy.deepcopy(req)
        del bad["priority"]
        with self.assertRaises(ComplianceSummaryValidationError):
            self.noop.execute(bad, tenant_id=self.tenant_id)

    def test_12_noop_empty_results(self) -> None:
        out = self.noop.execute(self._request(), tenant_id=self.tenant_id)
        self.assertEqual(out["results"], [])
        self.assertEqual(out["result_count"], 0)

    def test_13_noop_not_executed(self) -> None:
        out = self.noop.execute(self._request(), tenant_id=self.tenant_id)
        self.assertFalse(out["retrieval_executed"])

    def test_14_empty_not_verdict(self) -> None:
        out = self.noop.execute(self._request(), tenant_id=self.tenant_id)
        self.assertEqual(out["result_count"], 0)
        self.assertNotIn("compliant", out)
        self.assertNotIn("verdict", out)
        self.assertIn("result_not_verdict", out)
        self.assertIn("empty_result_meaning", out)

    def test_15_tenant_preserved(self) -> None:
        out = self.noop.execute(self._request(), tenant_id=self.tenant_id)
        self.assertEqual(out["tenant_id"], self.tenant_id)

    def test_16_er_identity_preserved(self) -> None:
        req = self._request()
        out = self.noop.execute(req, tenant_id=self.tenant_id)
        self.assertEqual(out["evidence_requirement_id"],
                         req["evidence_requirement_id"])

    def test_17_requirement_id_preserved(self) -> None:
        req = self._request()
        out = self.noop.execute(req, tenant_id=self.tenant_id)
        self.assertEqual(out["requirement_id"], req["requirement_id"])

    def test_18_gap_kind_preserved(self) -> None:
        req = self._request()
        out = self.noop.execute(req, tenant_id=self.tenant_id)
        self.assertEqual(out["gap_kind"], req["gap_kind"])

    def test_19_deterministic(self) -> None:
        req = self._request()
        first = self.noop.execute(copy.deepcopy(req),
                                  tenant_id=self.tenant_id)
        second = self.noop.execute(copy.deepcopy(req),
                                   tenant_id=self.tenant_id)
        self.assertEqual(
            json.dumps(first, sort_keys=True, default=str),
            json.dumps(second, sort_keys=True, default=str))

    def test_20_end_to_end(self) -> None:
        cases = [self._make_case(REQ_A), self._make_case(REQ_B)]
        rep = self.readiness.assess(cases, tenant_id=self.tenant_id)
        plan = self.planner.plan(rep, tenant_id=self.tenant_id)
        built = self.requests.build(plan, tenant_id=self.tenant_id)
        outs = [self.noop.execute(r, tenant_id=self.tenant_id)
                for r in built["requests"]]
        self.assertEqual(len(outs), built["request_count"])
        for req, out in zip(built["requests"], outs):
            self.assertEqual(out["evidence_requirement_id"],
                             req["evidence_requirement_id"])
            self.assertEqual(out["result_count"], 0)


if __name__ == "__main__":
    unittest.main()


