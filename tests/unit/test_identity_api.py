"""Unit tests for the ``GET /me`` current-account identity endpoint.

These tests exercise the route handler with a fake database and a real
HS256-signed Supabase-style token, so they run without PostgreSQL and
without a live Supabase project. Database-backed membership behaviour is
covered by the existing integration test conventions (gated on
``DATABASE_URL``).
"""

import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import MagicMock
from uuid import UUID

import jwt
from fastapi.testclient import TestClient

from xportra.api.app import create_app

SECRET = "test-secret-jwt-secret"

USER_ID = UUID("11111111-1111-1111-1111-111111111111")
SUBJECT = UUID("33333333-3333-3333-3333-333333333333")
TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
OTHER_TENANT_ID = UUID("44444444-4444-4444-4444-444444444444")

EMAIL = "owner@example.test"
DISPLAY_NAME = "Jane Exporter"
ORG_NAME = "Acme Exporters Ltd"


def make_token(subject: UUID, email: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "email": email,
        "aud": "authenticated",
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "iat": int(now.timestamp()),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


class FakeDatabase:
    """In-memory connection double for repository read paths."""

    def __init__(self, user_row=None, memberships=()):
        self.user_row = user_row
        self.memberships = list(memberships)

    @contextmanager
    def connection(self):
        conn = MagicMock()
        cursor = MagicMock()
        conn.cursor.return_value.__enter__.return_value = cursor
        cursor.fetchone.return_value = self.user_row
        cursor.fetchall.return_value = self.memberships
        yield conn


def membership_row(tenant_id: UUID, role: str = "owner", legal_name: str = ORG_NAME):
    return {
        "id": UUID("99999999-9999-9999-9999-999999999999"),
        "tenant_id": tenant_id,
        "role": role,
        "status": "active",
        "tenant_legal_name": legal_name,
    }


def user_row():
    return {
        "id": USER_ID,
        "display_name": DISPLAY_NAME,
        "email": EMAIL,
        "status": "active",
        "supabase_uid": SUBJECT,
    }


def build_app(database):
    services = MagicMock()
    services.database = database
    app = create_app(services=services)
    return app


class TestIdentityApi(TestCase):
    def setUp(self):
        self._env = os.environ.get("SUPABASE_JWT_SECRET")
        os.environ["SUPABASE_JWT_SECRET"] = SECRET

    def tearDown(self):
        if self._env is None:
            os.environ.pop("SUPABASE_JWT_SECRET", None)
        else:
            os.environ["SUPABASE_JWT_SECRET"] = self._env

    def _client(self, database):
        return TestClient(build_app(database))

    def test_returns_identity_and_active_organization(self):
        database = FakeDatabase(
            user_row=user_row(),
            memberships=[membership_row(TENANT_ID)],
        )
        with self._client(database) as client:
            response = client.get(
                "/me",
                headers={"Authorization": f"Bearer {make_token(SUBJECT, EMAIL)}"},
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["user_id"] == str(USER_ID)
        assert body["display_name"] == DISPLAY_NAME
        assert body["email"] == EMAIL
        assert body["organization_id"] == str(TENANT_ID)
        assert body["organization_name"] == ORG_NAME
        assert body["role"] == "owner"

    def test_returns_identity_without_organization_when_no_membership(self):
        database = FakeDatabase(user_row=user_row(), memberships=[])
        with self._client(database) as client:
            response = client.get(
                "/me",
                headers={"Authorization": f"Bearer {make_token(SUBJECT, EMAIL)}"},
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["display_name"] == DISPLAY_NAME
        assert body["email"] == EMAIL
        assert body["organization_id"] is None
        assert body["organization_name"] is None
        assert body["role"] is None

    def test_does_not_pick_an_organization_with_multiple_memberships(self):
        database = FakeDatabase(
            user_row=user_row(),
            memberships=[
                membership_row(TENANT_ID, legal_name="Acme Exporters Ltd"),
                membership_row(OTHER_TENANT_ID, legal_name="Other Co Ltd"),
            ],
        )
        with self._client(database) as client:
            response = client.get(
                "/me",
                headers={"Authorization": f"Bearer {make_token(SUBJECT, EMAIL)}"},
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["organization_id"] is None
        assert body["organization_name"] is None

    def test_respects_explicit_tenant_selection(self):
        database = FakeDatabase(
            user_row=user_row(),
            memberships=[
                membership_row(TENANT_ID),
                membership_row(OTHER_TENANT_ID),
            ],
        )
        with self._client(database) as client:
            response = client.get(
                "/me",
                headers={
                    "Authorization": f"Bearer {make_token(SUBJECT, EMAIL)}",
                    "X-Xportra-Tenant-ID": str(OTHER_TENANT_ID),
                },
            )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["organization_id"] == str(OTHER_TENANT_ID)

    def test_rejects_tenant_selection_for_another_tenant(self):
        database = FakeDatabase(
            user_row=user_row(),
            memberships=[membership_row(TENANT_ID)],
        )
        with self._client(database) as client:
            response = client.get(
                "/me",
                headers={
                    "Authorization": f"Bearer {make_token(SUBJECT, EMAIL)}",
                    "X-Xportra-Tenant-ID": str(OTHER_TENANT_ID),
                },
            )
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "tenant_not_member"

    def test_returns_403_when_account_is_not_provisioned(self):
        database = FakeDatabase(user_row=None, memberships=[])
        with self._client(database) as client:
            response = client.get(
                "/me",
                headers={"Authorization": f"Bearer {make_token(SUBJECT, EMAIL)}"},
            )
        assert response.status_code == 403, response.text
        assert response.json()["error"]["code"] == "identity_not_provisioned"

    def test_returns_401_without_bearer_token(self):
        database = FakeDatabase(user_row=user_row(), memberships=[membership_row(TENANT_ID)])
        with self._client(database) as client:
            response = client.get("/me")
        assert response.status_code == 401, response.text

    def test_returns_401_with_malformed_token(self):
        database = FakeDatabase(user_row=user_row(), memberships=[membership_row(TENANT_ID)])
        with self._client(database) as client:
            response = client.get(
                "/me",
                headers={"Authorization": "Bearer not-a-real-token"},
            )
        assert response.status_code == 401, response.text

    def test_uses_application_email_not_jwt_email_when_db_email_differs(self):
        database = FakeDatabase(
            user_row={**user_row(), "email": "db@example.test"},
            memberships=[membership_row(TENANT_ID)],
        )
        with self._client(database) as client:
            response = client.get(
                "/me",
                headers={"Authorization": f"Bearer {make_token(SUBJECT, EMAIL)}"},
            )
        assert response.status_code == 200, response.text
        assert response.json()["email"] == "db@example.test"
