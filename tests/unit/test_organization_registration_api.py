import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import UUID

from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.api.auth import AuthenticatedIdentity
from xportra.api.dependencies import get_authenticated_identity
from xportra.application.errors import ApplicationValidationError
from xportra.application.organization_registration import (
    OrganizationAlreadyRegisteredError,
    OrganizationRegistrationService,
)

IDENTITY_ID = UUID("33333333-3333-3333-3333-333333333333")
TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
USER_ID = UUID("11111111-1111-1111-1111-111111111111")


class FakeRegistrationService:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.arguments = None

    def register(self, **arguments):
        self.arguments = arguments
        if self.error is not None:
            raise self.error
        return self.result


class OrganizationRegistrationServiceTests(unittest.TestCase):
    def test_country_code_rejects_non_ascii_letters(self):
        class Store:
            called = False

            def provision(self, **_arguments):
                self.called = True
                raise AssertionError("invalid country code reached persistence")

        store = Store()
        service = OrganizationRegistrationService(store)

        with self.assertRaises(ApplicationValidationError):
            service.register(
                supabase_uid=IDENTITY_ID,
                identity_email="owner@example.test",
                organization_name="Acme",
                organization_type="exporter",
                country_code="éé",
            )

        self.assertFalse(store.called)


class OrganizationRegistrationApiTests(unittest.TestCase):
    def setUp(self):
        self.service = FakeRegistrationService(
            SimpleNamespace(
                organization_id=TENANT_ID,
                organization_slug="acme-1234",
                organization_name="Acme",
                user_id=USER_ID,
                role="owner",
                membership_status="active",
            )
        )
        self.app = create_app(
            services=SimpleNamespace(
                organization_registration=self.service
            )
        )
        self.app.dependency_overrides[get_authenticated_identity] = (
            lambda: AuthenticatedIdentity(
                subject=IDENTITY_ID,
                email="owner@example.test",
            )
        )

    def tearDown(self):
        self.app.dependency_overrides.clear()

    def test_registration_uses_verified_identity_and_returns_identifiers(self):
        with patch.dict(os.environ, {"APP_ENV": "test"}):
            with TestClient(self.app) as client:
                response = client.post(
                    "/organizations",
                    json={
                        "organization_name": "Acme",
                        "organization_type": "exporter",
                        "country_code": "NG",
                        "contact_name": "Owner",
                    },
                )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.json(),
            {
                "organization_id": str(TENANT_ID),
                "organization_slug": "acme-1234",
                "organization_name": "Acme",
                "user_id": str(USER_ID),
                "role": "owner",
                "membership_status": "active",
            },
        )
        self.assertEqual(
            self.service.arguments,
            {
                "supabase_uid": IDENTITY_ID,
                "identity_email": "owner@example.test",
                "organization_name": "Acme",
                "organization_type": "exporter",
                "country_code": "NG",
                "region": None,
                "contact_name": "Owner",
                "contact_email": None,
            },
        )

    def test_registration_rejects_client_supplied_identity_or_role(self):
        with patch.dict(os.environ, {"APP_ENV": "test"}):
            with TestClient(self.app) as client:
                response = client.post(
                    "/organizations",
                    json={
                        "organization_name": "Acme",
                        "organization_type": "exporter",
                        "country_code": "NG",
                        "tenant_id": str(TENANT_ID),
                        "supabase_uid": str(IDENTITY_ID),
                        "role": "owner",
                    },
                )

        self.assertEqual(response.status_code, 422)
        self.assertIsNone(self.service.arguments)

    def test_existing_membership_maps_to_conflict(self):
        self.service.error = OrganizationAlreadyRegisteredError(
            "already registered"
        )

        with patch.dict(os.environ, {"APP_ENV": "test"}):
            with TestClient(self.app) as client:
                response = client.post(
                    "/organizations",
                    json={
                        "organization_name": "Acme",
                        "organization_type": "exporter",
                        "country_code": "NG",
                    },
                )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json()["error"]["code"],
            "organization_already_registered",
        )


if __name__ == "__main__":
    unittest.main()
