import os
import unittest
from uuid import UUID

from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.api.dependencies import (
    ApplicationServices,
    get_services,
)
from xportra.domain.services import (
    DestinationMarketService,
    ExporterService,
    ProductService,
)
from xportra.persistence.database import Database, DatabaseSettings
from xportra.persistence.repositories import (
    ComplianceEvidenceRepository,
    DestinationMarketRepository,
    EvidenceRequirementRepository,
    ExporterRepository,
    ProductRepository,
    RequirementRepository,
    TenantRepository,
)
from xportra.persistence.tenant import TenantContext

TENANT_A_SLUG = "phase-1-8-api-a"
TENANT_B_SLUG = "phase-1-8-api-b"
GLOBAL_REQUIREMENT_CODE = "P18-API-GLOBAL"
TENANT_B_REQUIREMENT_CODE = "P18-API-TENANT-B"
AUTHORITY_ID = UUID("00000000-0000-0000-0000-000000000001")


class ExplodingExporterService:
    def create(self, *_args, **_kwargs):
        raise RuntimeError("postgresql://secret SQL failed")


class ExplodingApplicationServices:
    exporters = ExplodingExporterService()


class APIPostgreSQLIntegrationTests(unittest.TestCase):
    database = None
    tenant_a = None
    tenant_b = None
    exporter_a = None
    exporter_b = None
    product_a = None
    destination_a = None
    requirement_global = None
    requirement_tenant_b = None

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DATABASE_URL", "").strip():
            raise unittest.SkipTest("DATABASE_URL is not configured")
        cls.database = Database(DatabaseSettings.from_environment())
        cls._cleanup()
        tenant_repository = TenantRepository(cls.database)
        tenant_a_row = tenant_repository.create(
            "Phase 1.8 API Tenant A", TENANT_A_SLUG
        )
        tenant_b_row = tenant_repository.create(
            "Phase 1.8 API Tenant B", TENANT_B_SLUG
        )
        cls.tenant_a = TenantContext(tenant_a_row["id"])
        cls.tenant_b = TenantContext(tenant_b_row["id"])

        exporter_service = ExporterService(ExporterRepository(cls.database))
        cls.exporter_a = exporter_service.create(
            cls.tenant_a,
            "Phase 1.8 API Exporter A",
            registration_number="P18-API-A",
        )
        cls.exporter_b = exporter_service.create(
            cls.tenant_b,
            "Phase 1.8 API Exporter B",
            registration_number="P18-API-B",
        )
        cls.product_a = ProductService(
            ExporterRepository(cls.database), ProductRepository(cls.database)
        ).create(cls.tenant_a, cls.exporter_a["id"], "Phase 1.8 API Product A")
        cls.destination_a = DestinationMarketService(
            DestinationMarketRepository(cls.database)
        ).register(cls.tenant_a, "P18", "Phase 1.8 API Market")
        requirement_repository = RequirementRepository(cls.database)
        cls.requirement_global = requirement_repository.create(
            None,
            GLOBAL_REQUIREMENT_CODE,
            "Phase 1.8 API Global Requirement",
            "API integration requirement",
            status="active",
        )
        cls.requirement_tenant_b = requirement_repository.create(
            cls.tenant_b,
            TENANT_B_REQUIREMENT_CODE,
            "Phase 1.8 API Tenant B Requirement",
            "API integration requirement",
            status="active",
        )

    @classmethod
    def tearDownClass(cls):
        cls._cleanup()

    @classmethod
    def _cleanup(cls):
        if cls.database is None:
            if not os.environ.get("DATABASE_URL", "").strip():
                return
            cls.database = Database(DatabaseSettings.from_environment())
        with cls.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM xportra.tenants WHERE slug IN (%s, %s)",
                    (TENANT_A_SLUG, TENANT_B_SLUG),
                )
                tenant_ids = [row["id"] for row in cursor.fetchall()]
                if tenant_ids:
                    cursor.execute(
                        "DELETE FROM xportra.requirement_applicability WHERE tenant_id = ANY(%s)",
                        (tenant_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.compliance_evidence WHERE tenant_id = ANY(%s)",
                        (tenant_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.certification_permit_licenses WHERE tenant_id = ANY(%s)",
                        (tenant_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.products WHERE tenant_id = ANY(%s)",
                        (tenant_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.exporters WHERE tenant_id = ANY(%s)",
                        (tenant_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.destination_markets WHERE tenant_id = ANY(%s)",
                        (tenant_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.requirements WHERE tenant_id = ANY(%s)",
                        (tenant_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.tenants WHERE id = ANY(%s)",
                        (tenant_ids,),
                    )
                cursor.execute(
                    "DELETE FROM xportra.requirements WHERE requirement_code IN (%s, %s)",
                    (GLOBAL_REQUIREMENT_CODE, TENANT_B_REQUIREMENT_CODE),
                )

    def client(self):
        services = ApplicationServices.from_environment()
        return TestClient(create_app(services=services))

    def test_valid_api_requests_reach_service_backed_resources(self):
        with self.client() as client:
            headers = {"X-Development-Tenant-ID": str(self.tenant_a.tenant_id)}
            created = client.post(
                "/exporters",
                headers=headers,
                json={
                    "legal_name": "Phase 1.8 API Created Exporter",
                    "registration_number": "P18-API-CREATED",
                },
            )
            self.assertEqual(created.status_code, 201, created.text)
            exporter_id = created.json()["id"]
            retrieved = client.get(
                f"/exporters/{exporter_id}", headers=headers
            )
            self.assertEqual(retrieved.status_code, 200, retrieved.text)
            self.assertEqual(retrieved.json()["tenant_id"], str(self.tenant_a.tenant_id))

            product = client.post(
                "/products",
                headers=headers,
                json={
                    "exporter_id": exporter_id,
                    "product_name": "Phase 1.8 API Created Product",
                },
            )
            self.assertEqual(product.status_code, 201, product.text)
            destination = client.post(
                "/destination-markets",
                headers=headers,
                json={
                    "country_code": "P18C",
                    "market_name": "Phase 1.8 API Created Market",
                },
            )
            self.assertEqual(destination.status_code, 201, destination.text)
            certificate = client.post(
                "/certifications-permits-licenses",
                headers=headers,
                json={
                    "exporter_id": exporter_id,
                    "issuing_authority_id": str(AUTHORITY_ID),
                    "title": "Phase 1.8 API Permit",
                },
            )
            self.assertEqual(certificate.status_code, 201, certificate.text)

    def test_tenant_isolation_and_cross_tenant_relationships(self):
        with self.client() as client:
            headers_a = {"X-Development-Tenant-ID": str(self.tenant_a.tenant_id)}
            headers_b = {"X-Development-Tenant-ID": str(self.tenant_b.tenant_id)}
            own_exporter = client.get(
                f"/exporters/{self.exporter_a['id']}", headers=headers_a
            )
            other_exporter = client.get(
                f"/exporters/{self.exporter_b['id']}", headers=headers_a
            )
            cross_tenant_product = client.post(
                "/products",
                headers=headers_a,
                json={
                    "exporter_id": str(self.exporter_b["id"]),
                    "product_name": "Invalid Cross Tenant Product",
                },
            )
            cross_tenant_certificate = client.post(
                "/certifications-permits-licenses",
                headers=headers_a,
                json={
                    "exporter_id": str(self.exporter_b["id"]),
                    "issuing_authority_id": str(AUTHORITY_ID),
                    "title": "Invalid Cross Tenant Certificate",
                },
            )
            evidence = client.post(
                "/compliance-evidence",
                headers=headers_a,
                json={
                    "document_title": "Phase 1.8 API Evidence",
                    "document_type": "test",
                    "file_reference_or_uri": "test://phase-1-8/api-evidence",
                },
            )
            self.assertEqual(evidence.status_code, 201, evidence.text)
            evidence_id = evidence.json()["id"]
            other_tenant_evidence = client.get(
                f"/compliance-evidence/{evidence_id}", headers=headers_b
            )
            cross_tenant_requirement = client.post(
                f"/compliance-evidence/{evidence_id}/requirements",
                headers=headers_a,
                json={"requirement_id": str(self.requirement_tenant_b["id"])},
            )

        self.assertEqual(own_exporter.status_code, 200)
        self.assertEqual(other_exporter.status_code, 404)
        self.assertEqual(cross_tenant_product.status_code, 404)
        self.assertEqual(cross_tenant_certificate.status_code, 404)
        self.assertEqual(other_tenant_evidence.status_code, 404)
        self.assertEqual(cross_tenant_requirement.status_code, 404)

    def test_api_error_mapping_for_not_found_domain_and_integrity_failures(self):
        with self.client() as client:
            headers = {"X-Development-Tenant-ID": str(self.tenant_a.tenant_id)}
            missing = client.get(
                f"/exporters/{UUID('99999999-9999-9999-9999-999999999999')}",
                headers=headers,
            )
            invalid_dates = client.post(
                "/certifications-permits-licenses",
                headers=headers,
                json={
                    "exporter_id": str(self.exporter_a["id"]),
                    "issuing_authority_id": str(AUTHORITY_ID),
                    "title": "Invalid Date Window",
                    "issue_date": "2026-12-31",
                    "expiry_date": "2026-01-01",
                },
            )
            duplicate = client.post(
                "/exporters",
                headers=headers,
                json={
                    "legal_name": "Phase 1.8 API Duplicate",
                    "registration_number": "P18-API-A",
                },
            )

        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["error"]["code"], "resource_not_found")
        self.assertEqual(invalid_dates.status_code, 409)
        self.assertEqual(
            invalid_dates.json()["error"]["code"], "domain_validation_error"
        )
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.json()["error"]["code"], "integrity_error")
        rendered = (missing.text + invalid_dates.text + duplicate.text).lower()
        self.assertNotIn("postgresql", rendered)
        self.assertNotIn("sql", rendered)
        self.assertNotIn("duplicate", rendered)

    def test_malformed_and_missing_request_fields_are_rejected(self):
        with self.client() as client:
            missing_tenant = client.post(
                "/exporters", json={"legal_name": "No Tenant"}
            )
            missing_field = client.post(
                "/exporters",
                headers={"X-Development-Tenant-ID": str(self.tenant_a.tenant_id)},
                json={},
            )
            malformed = client.post(
                "/exporters",
                headers={"X-Development-Tenant-ID": str(self.tenant_a.tenant_id)},
                content="{",
            )

        self.assertEqual(missing_tenant.status_code, 401)
        self.assertEqual(
            missing_tenant.json()["error"]["code"], "authentication_required"
        )
        self.assertEqual(missing_field.status_code, 422)
        self.assertEqual(malformed.status_code, 422)

    def test_evidence_multi_write_operation_is_atomic_through_api(self):
        with self.client() as client:
            headers = {"X-Development-Tenant-ID": str(self.tenant_a.tenant_id)}
            title = "phase-1-8-api-atomic"
            before = self._count_evidence(title)
            duplicate_requirements = client.post(
                "/compliance-evidence/with-requirements",
                headers=headers,
                json={
                    "document_title": title,
                    "document_type": "test",
                    "file_reference_or_uri": "test://phase-1-8/atomic",
                    "requirement_ids": [
                        str(self.requirement_global["id"]),
                        str(self.requirement_global["id"]),
                    ],
                },
            )
            after_failure = self._count_evidence(title)
            valid = client.post(
                "/compliance-evidence/with-requirements",
                headers=headers,
                json={
                    "document_title": title,
                    "document_type": "test",
                    "file_reference_or_uri": "test://phase-1-8/atomic-valid",
                    "requirement_ids": [str(self.requirement_global["id"])],
                },
            )
            after_success = self._count_evidence(title)
            links = self._count_evidence_links(title)

        self.assertEqual(duplicate_requirements.status_code, 409)
        self.assertEqual(after_failure, before)
        self.assertEqual(valid.status_code, 201, valid.text)
        self.assertEqual(after_success, before + 1)
        self.assertEqual(links, 1)

    def test_unexpected_internal_error_is_generic(self):
        application = create_app(services=ApplicationServices.from_environment())
        application.dependency_overrides[get_services] = lambda: ExplodingApplicationServices()
        try:
            with TestClient(
                application, raise_server_exceptions=False
            ) as client:
                response = client.post(
                    "/exporters",
                    headers={
                        "X-Development-Tenant-ID": str(self.tenant_a.tenant_id)
                    },
                    json={"legal_name": "Unexpected"},
                )
        finally:
            application.dependency_overrides.clear()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "internal_error")
        self.assertNotIn("postgresql", response.text.lower())
        self.assertNotIn("sql", response.text.lower())
        self.assertNotIn("secret", response.text.lower())

    def _count_evidence(self, title):
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*) AS count
                    FROM xportra.compliance_evidence
                    WHERE tenant_id = %s AND document_title = %s
                    """,
                    (self.tenant_a.tenant_id, title),
                )
                return cursor.fetchone()["count"]

    def _count_evidence_links(self, title):
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT count(*) AS count
                    FROM xportra.evidence_requirements er
                    JOIN xportra.compliance_evidence ce
                      ON ce.id = er.evidence_id
                    WHERE ce.tenant_id = %s AND ce.document_title = %s
                    """,
                    (self.tenant_a.tenant_id, title),
                )
                return cursor.fetchone()["count"]


if __name__ == "__main__":
    unittest.main()
