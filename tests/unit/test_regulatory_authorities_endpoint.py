"""Focused endpoint tests for GET /regulatory/authorities.

The endpoint was missing from the deployed backend (production 404).
These tests verify the restored route: registration in the FastAPI
application, the AuthorityResponse contract, the established
GRANT_MANAGE authorization policy (fail-closed), the empty-collection
response, and error handling consistent with the existing API error
conventions. No live database is contacted.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import TestCase
from uuid import UUID

from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.api.dependencies import require_global_staff
from xportra.api.errors import PermissionDeniedError
from xportra.api.schemas import AuthorityResponse

ACTOR = UUID("aaaaaaaa-0000-0000-0000-000000000001")
AUTHORITY_ID = UUID("99999999-0000-0000-0000-000000000001")

NOW = datetime(2026, 10, 30, 12, 0, 0, tzinfo=timezone.utc)

AUTHORITY_ROW = {
    "id": AUTHORITY_ID,
    "name": "National Agency for Food and Drug Administration and Control",
    "jurisdiction": "NG",
    "authority_type": "government",
    "status": "active",
    "created_at": NOW,
    "updated_at": NOW,
}


class FakeAuthoritiesDatabase:
    """Connection double returning configured authority rows."""

    def __init__(self, rows=None, failure: Exception | None = None):
        self._rows = rows
        self._failure = failure

    def connection(self):
        db = self

        class Conn:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def cursor(self):
                class Cursor:
                    def __enter__(self):
                        return self

                    def __exit__(self, *args):
                        return False

                    def execute(self, statement, parameters=()):
                        pass

                    def fetchone(self):
                        return None

                    def fetchall(self):
                        if db._failure is not None:
                            raise db._failure
                        return list(db._rows or [])

                return Cursor()

        return Conn()

    def transaction(self):
        class Ctx:
            def __enter__(self):
                return None

            def __exit__(self, *args):
                return False

        return Ctx()


def build_app(database, staff_override=None):
    """Application with the global-staff dependency overridden.

    ``application.state.services`` is assigned inside the lifespan, so
    every request test runs inside ``with TestClient(...) as client``.
    """
    app = create_app(services=SimpleNamespace(database=database))
    app.dependency_overrides[require_global_staff] = (
        staff_override if staff_override is not None else (lambda: ACTOR)
    )
    return app


class AuthoritiesEndpointTests(TestCase):
    def test_no_authorities_yields_empty_success_not_production_404(self):
        # Registration is asserted behaviorally: when the route exists
        # an authorized request gets 200 []; when it is missing (the
        # deployed regression) the application answers 404.
        with TestClient(build_app(FakeAuthoritiesDatabase(rows=[]))) as client:
            response = client.get("/regulatory/authorities")
        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json())

    def test_authorized_staff_retrieve_authorities(self):
        with TestClient(build_app(FakeAuthoritiesDatabase(rows=[AUTHORITY_ROW]))) as client:
            response = client.get("/regulatory/authorities")
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(1, len(body))
        self.assertEqual(AUTHORITY_ID, UUID(body[0]["id"]))
        self.assertEqual(
            "National Agency for Food and Drug Administration and Control",
            body[0]["name"],
        )
        self.assertEqual("NG", body[0]["jurisdiction"])
        self.assertEqual("government", body[0]["authority_type"])
        self.assertEqual("active", body[0]["status"])

    def test_response_fields_match_authority_response(self):
        with TestClient(build_app(FakeAuthoritiesDatabase(rows=[AUTHORITY_ROW]))) as client:
            response = client.get("/regulatory/authorities")
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(
            set(AuthorityResponse.model_fields.keys()),
            set(body[0].keys()),
        )
        self.assertIn("created_at", body[0])
        self.assertIn("updated_at", body[0])

    def test_unauthorized_request_is_denied_fail_closed(self):
        app = build_app(FakeAuthoritiesDatabase(rows=[AUTHORITY_ROW]))

        def denied():
            raise PermissionDeniedError()

        app.dependency_overrides[require_global_staff] = denied
        with TestClient(app) as client:
            response = client.get("/regulatory/authorities")
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error"]["code"])

    def test_empty_authority_collection_returns_empty_success(self):
        with TestClient(build_app(FakeAuthoritiesDatabase(rows=[]))) as client:
            response = client.get("/regulatory/authorities")
        self.assertEqual(200, response.status_code)
        self.assertEqual([], response.json())

    def test_uninitialized_services_report_not_ready(self):
        with TestClient(build_app(None)) as client:
            response = client.get("/regulatory/authorities")
        self.assertEqual(503, response.status_code)
        self.assertEqual("application_not_ready", response.json()["error"]["code"])

    def test_repository_failure_yields_conservative_error(self):
        failing = FakeAuthoritiesDatabase(rows=None, failure=RuntimeError("stripe down"))
        app = build_app(failing)
        # The catch-all handler sits at ServerErrorMiddleware level, so
        # the TestClient must not re-raise the server exception here —
        # assert the production-consistent conservative response.
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get("/regulatory/authorities")
        self.assertEqual(500, response.status_code)
        self.assertEqual("internal_error", response.json()["error"]["code"])
