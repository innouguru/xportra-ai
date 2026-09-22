import unittest
from uuid import UUID

from xportra.domain.ingestion import (
    ApplicabilityContext,
    RegulatoryRequirementApplicabilityService,
    RegulatoryRequirementApplicabilityValidationError,
)

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
REQUIREMENT_ID = UUID("11111111-1111-1111-1111-111111111111")
ARTIFACT_ID = UUID("22222222-2222-2222-2222-222222222222")
SOURCE_ID = UUID("33333333-3333-3333-3333-333333333333")


class FakeApplicabilityRepository:
    def __init__(self):
        self.rows = {}

    def get_by_identity(self, tenant_id, requirement_id, context_fingerprint):
        return self.rows.get((tenant_id, requirement_id, context_fingerprint))

    def create(self, **values):
        row = {"id": UUID("44444444-4444-4444-4444-444444444444"), **values}
        key = (values["tenant_id"], values["requirement_id"], values["context_fingerprint"])
        self.rows[key] = row
        return row


class RegulatoryApplicabilityTests(unittest.TestCase):
    def setUp(self):
        self.requirement = {
            "id": REQUIREMENT_ID,
            "artifact_id": ARTIFACT_ID,
            "source_id": SOURCE_ID,
            "requirement_text": "Exporters shall submit certificates for exports to Nigeria.",
            "requirement_type": "documentation",
            "actor": "Exporters",
            "condition_metadata": {"condition": "for exports to Nigeria"},
        }
        self.context = ApplicabilityContext(
            tenant_id=TENANT_ID,
            exporter_id=UUID("55555555-5555-5555-5555-555555555555"),
            exporter_name="Acme Exporters",
            origin_country="NG",
            destination_country="NG",
            commodity="sesame",
            product_category="agricultural product",
            actor_role="exporter",
        )

    def test_matching_destination_and_actor_is_applicable(self):
        result = RegulatoryRequirementApplicabilityService().evaluate(self.requirement, self.context)

        self.assertEqual(result["outcome"], "applicable")
        self.assertIn("matched destination", result["reason"])
        self.assertIn("explicit actor", result["reason"])

    def test_destination_mismatch_is_not_applicable(self):
        context = ApplicabilityContext(
            tenant_id=TENANT_ID,
            exporter_id=self.context.exporter_id,
            exporter_name="Acme Exporters",
            origin_country="NG",
            destination_country="GH",
            commodity="sesame",
            actor_role="exporter",
        )

        result = RegulatoryRequirementApplicabilityService().evaluate(self.requirement, context)

        self.assertEqual(result["outcome"], "not_applicable")
        self.assertIn("destination mismatch", result["reason"])

    def test_unknown_destination_is_unknown(self):
        context = ApplicabilityContext(
            tenant_id=TENANT_ID,
            exporter_id=self.context.exporter_id,
            exporter_name="Acme Exporters",
            origin_country="NG",
            commodity="sesame",
            actor_role="exporter",
        )

        result = RegulatoryRequirementApplicabilityService().evaluate(self.requirement, context)

        self.assertEqual(result["outcome"], "unknown")
        self.assertIn("destination", result["reason"])

    def test_commodity_mismatch_is_not_applicable(self):
        requirement = {**self.requirement, "requirement_text": "Exporters shall label cocoa shipments."}
        context = ApplicabilityContext(
            tenant_id=TENANT_ID,
            exporter_id=self.context.exporter_id,
            exporter_name="Acme Exporters",
            destination_country="NG",
            commodity="sesame",
            actor_role="exporter",
        )

        result = RegulatoryRequirementApplicabilityService().evaluate(requirement, context)

        self.assertEqual(result["outcome"], "not_applicable")
        self.assertIn("commodity mismatch", result["reason"])

    def test_missing_context_is_unknown(self):
        context = ApplicabilityContext(tenant_id=TENANT_ID)
        result = RegulatoryRequirementApplicabilityService().evaluate(self.requirement, context)

        self.assertEqual(result["outcome"], "unknown")
        self.assertIn("insufficient context", result["reason"])

    def test_actor_mismatch_is_not_inferred_as_applicability(self):
        requirement = {**self.requirement, "actor": "Importers", "requirement_text": "Importers shall submit certificates."}
        result = RegulatoryRequirementApplicabilityService().evaluate(requirement, self.context)

        self.assertEqual(result["outcome"], "unknown")
        self.assertIn("actor", result["reason"])

    def test_threshold_is_evaluated_only_when_explicit_fact_exists(self):
        requirement = {
            **self.requirement,
            "requirement_text": "Exporters must ship at least 10 tonnes to Nigeria.",
            "condition_metadata": {"threshold": "at least 10 tonnes"},
        }
        below = ApplicabilityContext(
            tenant_id=TENANT_ID,
            destination_country="NG",
            commodity="sesame",
            business_characteristics={"shipment_quantity_tonnes": 5},
            actor_role="exporter",
        )
        unknown = ApplicabilityContext(tenant_id=TENANT_ID, destination_country="NG", actor_role="exporter")

        self.assertEqual(
            RegulatoryRequirementApplicabilityService().evaluate(requirement, below)["outcome"],
            "not_applicable",
        )
        self.assertEqual(
            RegulatoryRequirementApplicabilityService().evaluate(requirement, unknown)["outcome"],
            "unknown",
        )

    def test_explanation_and_identity_are_deterministic(self):
        service = RegulatoryRequirementApplicabilityService()
        first = service.evaluate(self.requirement, self.context)
        second = service.evaluate(self.requirement, self.context)

        self.assertEqual(first, second)
        self.assertEqual(first["tenant_id"], TENANT_ID)
        self.assertEqual(first["requirement_id"], REQUIREMENT_ID)
        self.assertNotIn("compliant", first["reason"].lower())

    def test_repeated_persistence_is_idempotent_and_tenant_scoped(self):
        repository = FakeApplicabilityRepository()
        service = RegulatoryRequirementApplicabilityService(repository=repository)
        first = service.evaluate_and_persist(self.requirement, self.context)
        second = service.evaluate_and_persist(self.requirement, self.context)

        self.assertEqual(first, second)
        self.assertEqual(len(repository.rows), 1)
        self.assertEqual(first["tenant_id"], TENANT_ID)

    def test_tenant_is_required(self):
        with self.assertRaises(RegulatoryRequirementApplicabilityValidationError):
            ApplicabilityContext()


if __name__ == "__main__":
    unittest.main()
