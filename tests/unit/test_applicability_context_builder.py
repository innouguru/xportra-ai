"""Focused unit tests for Phase 3.2 — ApplicabilityContextBuilder."""

import unittest
from uuid import uuid4

from xportra.domain.ingestion import (
    ApplicabilityContext,
    ApplicabilityContextBuilder,
    ComplianceApplicabilityService,
    ComplianceSummaryValidationError,
)


class ApplicabilityContextBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.builder = ApplicabilityContextBuilder()
        self.tenant_id = uuid4()

    def _exporter(self, **overrides) -> dict:
        data = {
            "id": uuid4(),
            "legal_name": "Test Exporter Ltd",
            "trading_name": "TestEx",
            "country_of_registration": "ng",
        }
        data.update(overrides)
        return data

    def _product(self, **overrides) -> dict:
        data = {
            "id": uuid4(),
            "exporter_id": uuid4(),
            "product_name": "Cocoa Beans",
            "commodity_code": "cocoa",
            "description": "Raw cocoa beans for processing",
        }
        data.update(overrides)
        return data

    def _destination(self, **overrides) -> dict:
        data = {
            "id": uuid4(),
            "country_code": "gb",
            "market_name": "United Kingdom",
        }
        data.update(overrides)
        return data

    # 1. Complete export-case context translated correctly
    def test_complete_context(self) -> None:
        exporter = self._exporter()
        product = self._product()
        destination = self._destination()

        context = self.builder.build(
            tenant_id=self.tenant_id,
            exporter=exporter,
            product=product,
            destination=destination,
        )

        self.assertEqual(context.tenant_id, self.tenant_id)
        self.assertEqual(context.exporter_id, exporter["id"])
        self.assertEqual(context.exporter_name, "Test Exporter Ltd")
        self.assertEqual(context.origin_country, "ng")
        self.assertEqual(context.destination_country, "gb")
        self.assertEqual(context.commodity, "cocoa")
        self.assertEqual(context.product_category, "Raw cocoa beans for processing")
        self.assertEqual(context.actor_role, "exporter")

    # 2. Missing optional/known facts remain unknown
    def test_missing_product_fields(self) -> None:
        product = {"id": uuid4(), "exporter_id": uuid4()}
        context = self.builder.build(
            tenant_id=self.tenant_id,
            product=product,
        )

        self.assertIsNone(context.commodity)
        self.assertIsNone(context.product_category)

    def test_missing_exporter_fields(self) -> None:
        exporter = {"id": uuid4()}
        context = self.builder.build(
            tenant_id=self.tenant_id,
            exporter=exporter,
        )

        self.assertIsNone(context.exporter_name)
        self.assertIsNone(context.origin_country)

    def test_missing_destination(self) -> None:
        context = self.builder.build(
            tenant_id=self.tenant_id,
        )

        self.assertIsNone(context.destination_country)

    def test_all_optional_missing(self) -> None:
        context = self.builder.build(tenant_id=self.tenant_id)

        self.assertEqual(context.tenant_id, self.tenant_id)
        self.assertIsNone(context.exporter_id)
        self.assertIsNone(context.exporter_name)
        self.assertIsNone(context.origin_country)
        self.assertIsNone(context.destination_country)
        self.assertIsNone(context.commodity)
        self.assertIsNone(context.product_category)
        self.assertIsNone(context.business_characteristics)
        self.assertEqual(context.actor_role, "exporter")

    # 3. Tenant identity preserved
    def test_tenant_identity_preserved(self) -> None:
        context = self.builder.build(tenant_id=self.tenant_id)
        self.assertEqual(context.tenant_id, self.tenant_id)

    def test_tenant_isolation(self) -> None:
        tenant_a = uuid4()
        tenant_b = uuid4()
        context_a = self.builder.build(tenant_id=tenant_a)
        context_b = self.builder.build(tenant_id=tenant_b)

        self.assertNotEqual(context_a.tenant_id, context_b.tenant_id)

    # 4. Product/commodity information preserved
    def test_commodity_preserved(self) -> None:
        product = self._product(commodity_code="sesame")
        context = self.builder.build(
            tenant_id=self.tenant_id,
            product=product,
        )

        self.assertEqual(context.commodity, "sesame")

    # 5. Destination information preserved
    def test_destination_preserved(self) -> None:
        destination = self._destination(country_code="gh")
        context = self.builder.build(
            tenant_id=self.tenant_id,
            destination=destination,
        )

        self.assertEqual(context.destination_country, "gh")

    # 6. Deterministic repeated construction
    def test_deterministic_construction(self) -> None:
        exporter = self._exporter()
        product = self._product()
        destination = self._destination()

        first = self.builder.build(
            tenant_id=self.tenant_id,
            exporter=exporter,
            product=product,
            destination=destination,
        )
        second = self.builder.build(
            tenant_id=self.tenant_id,
            exporter=exporter,
            product=product,
            destination=destination,
        )

        self.assertEqual(first.tenant_id, second.tenant_id)
        self.assertEqual(first.exporter_id, second.exporter_id)
        self.assertEqual(first.exporter_name, second.exporter_name)
        self.assertEqual(first.origin_country, second.origin_country)
        self.assertEqual(first.destination_country, second.destination_country)
        self.assertEqual(first.commodity, second.commodity)
        self.assertEqual(first.product_category, second.product_category)
        self.assertEqual(first.actor_role, second.actor_role)

    # 7. Resulting context consumed by ComplianceApplicabilityService
    def test_context_consumed_by_applicability_service(self) -> None:
        exporter = self._exporter()
        product = self._product()
        destination = self._destination()

        context = self.builder.build(
            tenant_id=self.tenant_id,
            exporter=exporter,
            product=product,
            destination=destination,
        )

        requirement = {
            "id": str(uuid4()),
            "requirement_text": "All cocoa exports to Nigeria require phytosanitary certification",
            "actor": "exporter",
        }

        service = ComplianceApplicabilityService()
        result = service.determine([requirement], context)

        self.assertEqual(result["tenant_id"], self.tenant_id)
        self.assertEqual(result["total_requirements"], 1)

    # 8. Invalid/incomplete domain input
    def test_invalid_tenant_id_raises(self) -> None:
        with self.assertRaises(ComplianceSummaryValidationError):
            self.builder.build(tenant_id="not-a-uuid")

    def test_none_exporter_product_destination(self) -> None:
        """All domain inputs can be None; only tenant_id is required."""
        context = self.builder.build(
            tenant_id=self.tenant_id,
            exporter=None,
            product=None,
            destination=None,
        )

        self.assertEqual(context.tenant_id, self.tenant_id)
        self.assertIsNone(context.exporter_id)
        self.assertIsNone(context.exporter_name)
        self.assertIsNone(context.origin_country)
        self.assertIsNone(context.destination_country)
        self.assertIsNone(context.commodity)
        self.assertIsNone(context.product_category)

    def test_actor_role_override(self) -> None:
        context = self.builder.build(
            tenant_id=self.tenant_id,
            actor_role="importer",
        )

        self.assertEqual(context.actor_role, "importer")

    def test_business_characteristics_preserved(self) -> None:
        characteristics = {"shipment_quantity_tonnes": 50}
        context = self.builder.build(
            tenant_id=self.tenant_id,
            business_characteristics=characteristics,
        )

        self.assertEqual(context.business_characteristics, characteristics)

    def test_exporter_name_falls_back_to_trading_name(self) -> None:
        exporter = {"id": uuid4(), "trading_name": "TradeCo"}
        context = self.builder.build(
            tenant_id=self.tenant_id,
            exporter=exporter,
        )

        self.assertEqual(context.exporter_name, "TradeCo")

    def test_exporter_name_uses_legal_name_over_trading_name(self) -> None:
        exporter = {
            "id": uuid4(),
            "legal_name": "Legal Corp",
            "trading_name": "TradeCo",
        }
        context = self.builder.build(
            tenant_id=self.tenant_id,
            exporter=exporter,
        )

        self.assertEqual(context.exporter_name, "Legal Corp")


if __name__ == "__main__":
    unittest.main()