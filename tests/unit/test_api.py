from datetime import datetime, timezone
import json
import os
import unittest
from uuid import UUID

from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.api.auth import MemberContext
from xportra.api.dependencies import get_member_context
from xportra.domain.errors import (
    DomainNotFoundError,
    DomainPersistenceError,
    DomainValidationError,
)
from xportra.persistence.errors import PersistenceIntegrityError
from xportra.persistence.tenant import TenantContext

TENANT_A = TenantContext(UUID("11111111-1111-1111-1111-111111111111"))
TENANT_B = TenantContext(UUID("22222222-2222-2222-2222-222222222222"))
EXPORTER_A_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
EXPORTER_B_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
PRODUCT_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
DESTINATION_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
EVIDENCE_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")
CERTIFICATE_ID = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
REQUIREMENT_ID = UUID("12121212-1212-1212-1212-121212121212")
AUTHORITY_ID = UUID("00000000-0000-0000-0000-000000000001")
TENANT_HEADER_A = {"X-Development-Tenant-ID": str(TENANT_A.tenant_id)}
TENANT_HEADER_B = {"X-Development-Tenant-ID": str(TENANT_B.tenant_id)}
CREATED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)


def exporter_row(tenant=TENANT_A, exporter_id=EXPORTER_A_ID):
    return {
        "id": exporter_id,
        "tenant_id": tenant.tenant_id,
        "legal_name": "Test Exporter",
        "trading_name": None,
        "registration_number": "TEST-1",
        "country_of_registration": "NG",
        "status": "active",
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }


def product_row(tenant=TENANT_A, product_id=PRODUCT_ID):
    return {
        "id": product_id,
        "tenant_id": tenant.tenant_id,
        "exporter_id": EXPORTER_A_ID,
        "product_name": "Test Product",
        "commodity_code": None,
        "description": None,
        "status": "active",
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }


def destination_row(tenant=TENANT_A, destination_id=DESTINATION_ID):
    return {
        "id": destination_id,
        "tenant_id": tenant.tenant_id,
        "country_code": "CA",
        "market_name": "Test Market",
        "regulatory_context": None,
        "status": "active",
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }


def evidence_row(tenant=TENANT_A, evidence_id=EVIDENCE_ID):
    return {
        "id": evidence_id,
        "tenant_id": tenant.tenant_id,
        "source_id": None,
        "document_title": "Test Evidence",
        "document_type": "test",
        "file_reference_or_uri": "test://evidence",
        "content_hash": None,
        "status": "uploaded",
        "uploaded_at": CREATED_AT,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }


def certificate_row(tenant=TENANT_A, certificate_id=CERTIFICATE_ID):
    return {
        "id": certificate_id,
        "tenant_id": tenant.tenant_id,
        "exporter_id": EXPORTER_A_ID,
        "issuing_authority_id": AUTHORITY_ID,
        "title": "Test Certificate",
        "issue_date": None,
        "expiry_date": None,
        "status": "issued",
        "document_reference": None,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }


class FakeExporterService:
    def __init__(self, create_error=None):
        self.create_error = create_error
        self.create_calls = []
        self.get_calls = []

    def create(self, tenant, **values):
        self.create_calls.append((tenant, values))
        if self.create_error is not None:
            raise self.create_error
        return exporter_row(tenant)

    def get(self, tenant, exporter_id):
        self.get_calls.append((tenant, exporter_id))
        if tenant == TENANT_A and exporter_id == EXPORTER_A_ID:
            return exporter_row(tenant, exporter_id)
        return None


class FakeProductService:
    def __init__(self):
        self.create_calls = []
        self.get_calls = []

    def create(self, tenant, exporter_id, **values):
        self.create_calls.append((tenant, exporter_id, values))
        if exporter_id == EXPORTER_B_ID:
            raise DomainNotFoundError("exporter was not found for tenant")
        return product_row(tenant)

    def get(self, tenant, product_id):
        self.get_calls.append((tenant, product_id))
        if tenant == TENANT_A and product_id == PRODUCT_ID:
            return product_row(tenant, product_id)
        return None


class FakeDestinationService:
    def __init__(self):
        self.create_calls = []
        self.register_calls = []
        self.get_calls = []

    def register(self, tenant, **values):
        self.create_calls.append((tenant, values))
        self.register_calls.append((tenant, values))
        return destination_row(tenant)

    def get(self, tenant, destination_id):
        self.get_calls.append((tenant, destination_id))
        if tenant == TENANT_A and destination_id == DESTINATION_ID:
            return destination_row(tenant, destination_id)
        return None


class FakeEvidenceService:
    def __init__(self, create_error=None, validation_error=False):
        self.create_error = create_error
        self.validation_error = validation_error
        self.record_calls = []
        self.with_requirements_calls = []
        self.get_calls = []
        self.associate_calls = []

    def record(self, tenant, **values):
        self.record_calls.append((tenant, values))
        if self.create_error is not None:
            raise self.create_error
        return evidence_row(tenant)

    def record_with_requirements(self, tenant, requirement_ids, **values):
        self.with_requirements_calls.append((tenant, requirement_ids, values))
        if self.validation_error:
            raise DomainValidationError("domain rule violation")
        if self.create_error is not None:
            raise self.create_error
        return evidence_row(tenant)

    def get(self, tenant, evidence_id):
        self.get_calls.append((tenant, evidence_id))
        if tenant == TENANT_A and evidence_id == EVIDENCE_ID:
            return evidence_row(tenant, evidence_id)
        return None

    def associate_requirement(self, tenant, evidence_id, requirement_id):
        self.associate_calls.append((tenant, evidence_id, requirement_id))
        if tenant == TENANT_A and requirement_id == REQUIREMENT_ID:
            return {
                "id": UUID("13131313-1313-1313-1313-131313131313"),
                "tenant_id": tenant.tenant_id,
                "evidence_id": evidence_id,
                "requirement_id": requirement_id,
                "created_at": CREATED_AT,
            }
        raise DomainNotFoundError("requirement was not found for tenant")


class FakeCertificationService:
    def __init__(self):
        self.create_calls = []
        self.get_calls = []

    def record(self, tenant, **values):
        self.create_calls.append((tenant, values))
        if values.get("exporter_id") == EXPORTER_B_ID:
            raise DomainNotFoundError("exporter was not found for tenant")
        return certificate_row(tenant)

    def get(self, tenant, certificate_id):
        self.get_calls.append((tenant, certificate_id))
        if tenant == TENANT_A and certificate_id == CERTIFICATE_ID:
            return certificate_row(tenant, certificate_id)
        return None


class FakeApplicationServices:
    def __init__(self, exporter_error=None, evidence_error=None, evidence_validation=False):
        self.exporters = FakeExporterService(exporter_error)
        self.products = FakeProductService()
        self.destinations = FakeDestinationService()
        self.evidence = FakeEvidenceService(evidence_error, evidence_validation)
        self.certifications = FakeCertificationService()


def client_for(services=None, raise_server_exceptions=True):
    return TestClient(
        create_app(services=services or FakeApplicationServices()),
        raise_server_exceptions=raise_server_exceptions,
    )


class APIUnitTests(unittest.TestCase):
    def test_valid_request_reaches_exporter_service_with_tenant_context(self):
        services = FakeApplicationServices()
        with client_for(services) as client:
            response = client.post(
                "/exporters",
                headers=TENANT_HEADER_A,
                json={"legal_name": "Acme Exports", "registration_number": "ACME-1"},
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["id"], str(EXPORTER_A_ID))
        self.assertEqual(services.exporters.create_calls[0][0], TENANT_A)
        self.assertEqual(
            services.exporters.create_calls[0][1]["legal_name"], "Acme Exports"
        )

    def test_all_resource_routes_call_application_services(self):
        services = FakeApplicationServices()
        with client_for(services) as client:
            exporter = client.post(
                "/exporters", headers=TENANT_HEADER_A, json={"legal_name": "Acme"}
            )
            product = client.post(
                "/products",
                headers=TENANT_HEADER_A,
                json={"exporter_id": str(EXPORTER_A_ID), "product_name": "Cocoa"},
            )
            destination = client.post(
                "/destination-markets",
                headers=TENANT_HEADER_A,
                json={"country_code": "CA", "market_name": "Canada"},
            )
            evidence = client.post(
                "/compliance-evidence/with-requirements",
                headers=TENANT_HEADER_A,
                json={
                    "document_title": "Evidence",
                    "document_type": "test",
                    "file_reference_or_uri": "test://evidence",
                    "requirement_ids": [str(REQUIREMENT_ID)],
                },
            )
            association = client.post(
                f"/compliance-evidence/{EVIDENCE_ID}/requirements",
                headers=TENANT_HEADER_A,
                json={"requirement_id": str(REQUIREMENT_ID)},
            )
            certificate = client.post(
                "/certifications-permits-licenses",
                headers=TENANT_HEADER_A,
                json={
                    "exporter_id": str(EXPORTER_A_ID),
                    "issuing_authority_id": str(AUTHORITY_ID),
                    "title": "Permit",
                },
            )
            self.assertEqual(exporter.status_code, 201)
            self.assertEqual(product.status_code, 201)
            self.assertEqual(destination.status_code, 201)
            self.assertEqual(evidence.status_code, 201)
            self.assertEqual(association.status_code, 201)
            self.assertEqual(certificate.status_code, 201)

        self.assertEqual(len(services.exporters.create_calls), 1)
        self.assertEqual(len(services.products.create_calls), 1)
        self.assertEqual(len(services.destinations.register_calls), 1)
        self.assertEqual(len(services.evidence.with_requirements_calls), 1)
        self.assertEqual(len(services.evidence.associate_calls), 1)
        self.assertEqual(len(services.certifications.create_calls), 1)
        self.assertEqual(
            services.evidence.with_requirements_calls[0][1], [REQUIREMENT_ID]
        )

    def test_request_validation_rejects_malformed_missing_and_unknown_fields(self):
        with client_for() as client:
            missing_header = client.post(
                "/exporters", json={"legal_name": "Acme"}
            )
            invalid_tenant = client.post(
                "/exporters",
                headers={"X-Development-Tenant-ID": "not-a-uuid"},
                json={"legal_name": "Acme"},
            )
            missing_field = client.post(
                "/exporters", headers=TENANT_HEADER_A, json={}
            )
            unknown_field = client.post(
                "/exporters",
                headers=TENANT_HEADER_A,
                json={"legal_name": "Acme", "tenant_id": str(TENANT_B.tenant_id)},
            )
            malformed_json = client.post(
                "/exporters",
                headers=TENANT_HEADER_A,
                content="{",
            )
            invalid_path = client.get(
                "/exporters/not-a-uuid", headers=TENANT_HEADER_A
            )
            invalid_date = client.post(
                "/certifications-permits-licenses",
                headers=TENANT_HEADER_A,
                json={
                    "exporter_id": str(EXPORTER_A_ID),
                    "issuing_authority_id": str(AUTHORITY_ID),
                    "title": "Permit",
                    "issue_date": "not-a-date",
                },
            )

        self.assertEqual(missing_header.status_code, 401)
        self.assertEqual(
            missing_header.json()["error"]["code"], "authentication_required"
        )
        self.assertEqual(invalid_tenant.status_code, 422)
        self.assertEqual(missing_field.status_code, 422)
        self.assertEqual(unknown_field.status_code, 422)
        self.assertEqual(invalid_path.status_code, 422)
        self.assertEqual(invalid_date.status_code, 422)
        self.assertEqual(malformed_json.status_code, 422)

    def test_tenant_isolation_and_cross_tenant_relationships_are_rejected(self):
        services = FakeApplicationServices()
        with client_for(services) as client:
            own = client.get(
                f"/exporters/{EXPORTER_A_ID}", headers=TENANT_HEADER_A
            )
            other = client.get(
                f"/exporters/{EXPORTER_B_ID}", headers=TENANT_HEADER_A
            )
            cross_product = client.post(
                "/products",
                headers=TENANT_HEADER_A,
                json={"exporter_id": str(EXPORTER_B_ID), "product_name": "Invalid"},
            )
            cross_association = client.post(
                f"/compliance-evidence/{EVIDENCE_ID}/requirements",
                headers=TENANT_HEADER_A,
                json={"requirement_id": str(UUID("99999999-9999-9999-9999-999999999999"))},
            )
            cross_certificate = client.post(
                "/certifications-permits-licenses",
                headers=TENANT_HEADER_A,
                json={
                    "exporter_id": str(EXPORTER_B_ID),
                    "issuing_authority_id": str(AUTHORITY_ID),
                    "title": "Invalid",
                },
            )

        self.assertEqual(own.status_code, 200)
        self.assertEqual(other.status_code, 404)
        self.assertEqual(cross_product.status_code, 404)
        self.assertEqual(cross_association.status_code, 404)
        self.assertEqual(cross_certificate.status_code, 404)
        self.assertEqual(services.products.create_calls[0][0], TENANT_A)
        self.assertEqual(services.certifications.create_calls[0][0], TENANT_A)

    def test_error_mapping_does_not_leak_internal_details(self):
        integrity_cause = PersistenceIntegrityError(
            "exporter creation", Exception("duplicate SQL")
        )
        services = FakeApplicationServices(
            exporter_error=DomainPersistenceError("exporter creation", integrity_cause)
        )
        with client_for(services, raise_server_exceptions=False) as client:
            integrity = client.post(
                "/exporters",
                headers=TENANT_HEADER_A,
                json={"legal_name": "Duplicate"},
            )
            not_found = client.get(
                f"/exporters/{UUID('99999999-9999-9999-9999-999999999999')}",
                headers=TENANT_HEADER_A,
            )
            services.evidence.validation_error = True
            domain = client.post(
                "/compliance-evidence/with-requirements",
                headers=TENANT_HEADER_A,
                json={
                    "document_title": "Evidence",
                    "document_type": "test",
                    "file_reference_or_uri": "test://evidence",
                    "requirement_ids": [str(REQUIREMENT_ID)],
                },
            )
            services.exporters.create_error = RuntimeError(
                "postgresql://secret SQL failed"
            )
            unexpected = client.post(
                "/exporters",
                headers=TENANT_HEADER_A,
                json={"legal_name": "Unexpected"},
            )

        self.assertEqual(integrity.status_code, 409)
        self.assertEqual(integrity.json()["error"]["code"], "integrity_error")
        self.assertEqual(not_found.status_code, 404)
        self.assertEqual(domain.status_code, 409)
        self.assertEqual(unexpected.status_code, 500)
        rendered = json.dumps(
            [integrity.json(), not_found.json(), domain.json(), unexpected.json()]
        ).lower()
        self.assertNotIn("postgresql", rendered)
        self.assertNotIn("sql", rendered)
        self.assertNotIn("duplicate", rendered)

    def test_evidence_route_uses_atomic_service_operation(self):
        services = FakeApplicationServices()
        with client_for(services) as client:
            response = client.post(
                "/compliance-evidence/with-requirements",
                headers=TENANT_HEADER_A,
                json={
                    "document_title": "Evidence",
                    "document_type": "test",
                    "file_reference_or_uri": "test://evidence",
                    "requirement_ids": [str(REQUIREMENT_ID)],
                },
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(services.evidence.with_requirements_calls), 1)
        self.assertFalse(hasattr(services.evidence, "repository"))

    def test_development_tenant_context_is_disabled_in_production(self):
        previous = os.environ.get("APP_ENV")
        previous_secret = os.environ.get("SUPABASE_JWT_SECRET")
        os.environ["APP_ENV"] = "production"
        os.environ["SUPABASE_JWT_SECRET"] = "phase-test-jwt-secret-0123456789abcdef"
        try:
            with client_for() as client:
                response = client.post(
                    "/exporters",
                    headers=TENANT_HEADER_A,
                    json={"legal_name": "Acme"},
                )
                missing_auth = client.post(
                    "/exporters", json={"legal_name": "Acme"}
                )
        finally:
            if previous is None:
                os.environ.pop("APP_ENV", None)
            else:
                os.environ["APP_ENV"] = previous
            if previous_secret is None:
                os.environ.pop("SUPABASE_JWT_SECRET", None)
            else:
                os.environ["SUPABASE_JWT_SECRET"] = previous_secret
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json()["error"]["code"], "development_tenant_context_disabled"
        )
        self.assertEqual(missing_auth.status_code, 401)
        self.assertEqual(
            missing_auth.json()["error"]["code"], "authentication_required"
        )

    def test_missing_credentials_are_rejected_without_development_fallback(self):
        services = FakeApplicationServices()
        with client_for(services) as client:
            response = client.post(
                "/exporters", json={"legal_name": "Acme"}
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "authentication_required")
        self.assertEqual(
            response.headers.get("www-authenticate"), "Bearer"
        )
        self.assertEqual(len(services.exporters.create_calls), 0)

    def test_malformed_and_invalid_tokens_are_rejected(self):
        previous_secret = os.environ.get("SUPABASE_JWT_SECRET")
        os.environ["SUPABASE_JWT_SECRET"] = "phase-unit-test-jwt-secret-0123456789"
        try:
            with client_for() as client:
                malformed = client.post(
                    "/exporters",
                    headers={"Authorization": "Bearer not.a.jwt"},
                    json={"legal_name": "Acme"},
                )
                wrong_scheme = client.post(
                    "/exporters",
                    headers={"Authorization": "Basic dXNwbDpz"},
                    json={"legal_name": "Acme"},
                )
        finally:
            if previous_secret is None:
                os.environ.pop("SUPABASE_JWT_SECRET", None)
            else:
                os.environ["SUPABASE_JWT_SECRET"] = previous_secret
        self.assertEqual(malformed.status_code, 401)
        self.assertEqual(malformed.json()["error"]["code"], "invalid_token")
        self.assertEqual(wrong_scheme.status_code, 401)
        self.assertEqual(wrong_scheme.json()["error"]["code"], "invalid_token")

    def test_authentication_error_responses_do_not_leak_credentials(self):
        previous_secret = os.environ.get("SUPABASE_JWT_SECRET")
        secret = "phase-unit-test-jwt-secret-0123456789"
        token = "bearer-token-value-that-must-not-leak"
        os.environ["SUPABASE_JWT_SECRET"] = secret
        try:
            with client_for() as client:
                response = client.post(
                    "/exporters",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"legal_name": "Acme"},
                )
        finally:
            if previous_secret is None:
                os.environ.pop("SUPABASE_JWT_SECRET", None)
            else:
                os.environ["SUPABASE_JWT_SECRET"] = previous_secret
        rendered = response.text.lower()
        self.assertEqual(response.status_code, 401)
        self.assertNotIn(token, rendered)
        self.assertNotIn(secret, rendered)
        self.assertNotIn("jwt", rendered)


if __name__ == "__main__":
    unittest.main()
