import unittest
from uuid import UUID

from xportra.domain.ingestion import (
    EvidenceRecord,
    RequirementAssessmentService,
    RequirementAssessmentValidationError,
)

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
REQUIREMENT_ID = UUID("11111111-1111-1111-1111-111111111111")
APPLICABILITY_ID = UUID("22222222-2222-2222-2222-222222222222")
EVIDENCE_ID = UUID("33333333-3333-3333-3333-333333333333")


class FakeAssessmentRepository:
    def __init__(self):
        self.rows = {}

    def get_by_identity(self, tenant_id, requirement_id, applicability_id, evidence_fingerprint):
        return self.rows.get((tenant_id, requirement_id, applicability_id, evidence_fingerprint))

    def create(self, **values):
        row = {"id": UUID("44444444-4444-4444-4444-444444444444"), **values}
        key = (values["tenant_id"], values["requirement_id"], values["applicability_result_id"], values["evidence_fingerprint"])
        self.rows[key] = row
        return row


class ComplianceAssessmentTests(unittest.TestCase):
    def setUp(self):
        self.applicable_result = {
            "id": APPLICABILITY_ID,
            "tenant_id": TENANT_ID,
            "requirement_id": REQUIREMENT_ID,
            "outcome": "applicable",
            "context_fingerprint": "context-hash",
        }
        self.evidence = EvidenceRecord(
            tenant_id=TENANT_ID,
            evidence_id=EVIDENCE_ID,
            evidence_type="certificate",
            reference="vault://certificate-1",
            requirement_id=REQUIREMENT_ID,
            status="accepted",
            metadata={"supports_requirement": True},
        )

    def test_satisfied_requires_explicit_link_and_support(self):
        result = RequirementAssessmentService().assess(self.applicable_result, [self.evidence])

        self.assertEqual(result["outcome"], "satisfied")
        self.assertEqual(result["evidence_id"], EVIDENCE_ID)
        self.assertIn("required evidence present", result["reason"])

    def test_category_match_alone_does_not_satisfy(self):
        evidence = EvidenceRecord(
            tenant_id=TENANT_ID,
            evidence_id=EVIDENCE_ID,
            evidence_type="certificate",
            reference="vault://certificate-1",
            status="accepted",
        )

        result = RequirementAssessmentService().assess(self.applicable_result, [evidence])

        self.assertEqual(result["outcome"], "unknown")
        self.assertIn("evidence insufficient", result["reason"])

    def test_missing_evidence_is_unknown(self):
        result = RequirementAssessmentService().assess(self.applicable_result, [])

        self.assertEqual(result["outcome"], "unknown")
        self.assertIn("required evidence absent", result["reason"])

    def test_rejected_linked_evidence_is_not_satisfied(self):
        evidence = EvidenceRecord(
            tenant_id=TENANT_ID,
            evidence_id=EVIDENCE_ID,
            evidence_type="certificate",
            reference="vault://certificate-1",
            requirement_id=REQUIREMENT_ID,
            status="rejected",
            metadata={"supports_requirement": True},
        )

        result = RequirementAssessmentService().assess(self.applicable_result, [evidence])

        self.assertEqual(result["outcome"], "not_satisfied")
        self.assertIn("evidence rejected", result["reason"])

    def test_non_applicable_requirement_cannot_be_assessed(self):
        result = RequirementAssessmentService().assess(
            {**self.applicable_result, "outcome": "unknown"}, [self.evidence]
        )

        self.assertEqual(result["outcome"], "unknown")
        self.assertIn("cannot yet be assessed", result["reason"])

    def test_tenant_mismatch_is_rejected(self):
        evidence = EvidenceRecord(
            tenant_id=OTHER_TENANT_ID,
            evidence_id=EVIDENCE_ID,
            evidence_type="certificate",
            reference="vault://certificate-1",
            requirement_id=REQUIREMENT_ID,
            status="accepted",
            metadata={"supports_requirement": True},
        )

        with self.assertRaises(RequirementAssessmentValidationError):
            RequirementAssessmentService().assess(self.applicable_result, [evidence])

    def test_deterministic_explanation_and_idempotency(self):
        repository = FakeAssessmentRepository()
        service = RequirementAssessmentService(repository=repository)

        first = service.assess_and_persist(self.applicable_result, [self.evidence])
        second = service.assess_and_persist(self.applicable_result, [self.evidence])

        self.assertEqual(first, second)
        self.assertEqual(first["reason"], "required evidence present")
        self.assertEqual(len(repository.rows), 1)

    def test_invalid_applicability_result_is_rejected(self):
        with self.assertRaises(RequirementAssessmentValidationError):
            RequirementAssessmentService().assess({}, [])


if __name__ == "__main__":
    unittest.main()
