"""Focused tests for PersistenceIntegrityError handling in the API boundary."""

import asyncio
import logging
import unittest
from unittest.mock import Mock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from xportra.api.errors import _handle_persistence_integrity, register_exception_handlers
from xportra.persistence.errors import PersistenceIntegrityError


def _make_cause(pgcode: str, constraint_name: str | None = None) -> Mock:
    """Build a mock psycopg IntegrityError with the given SQLSTATE and constraint."""
    cause = Mock()
    cause.pgcode = pgcode
    cause.diag = Mock()
    cause.diag.constraint_name = constraint_name
    return cause


async def _call_handler(exc: PersistenceIntegrityError):
    return await _handle_persistence_integrity(Mock(spec=Request), exc)


class PersistenceIntegrityErrorHandlerTests(unittest.TestCase):
    """Direct handler tests for logging, mapping, and client safety."""

    def test_unique_violation_maps_to_409(self):
        exc = PersistenceIntegrityError(
            "regulatory source creation",
            _make_cause("23505", "regulatory_sources_identity_key"),
        )
        response = asyncio.run(_call_handler(exc))
        self.assertEqual(response.status_code, 409)
        body = response.body.decode()
        self.assertIn("integrity_conflict", body)

    def test_foreign_key_violation_maps_to_400(self):
        exc = PersistenceIntegrityError(
            "regulatory source creation",
            _make_cause("23503", "regulatory_sources_authority_id_fkey"),
        )
        response = asyncio.run(_call_handler(exc))
        self.assertEqual(response.status_code, 400)
        body = response.body.decode()
        self.assertIn("integrity_violation", body)

    def test_not_null_violation_maps_to_400(self):
        exc = PersistenceIntegrityError(
            "regulatory source creation", _make_cause("23502", None)
        )
        response = asyncio.run(_call_handler(exc))
        self.assertEqual(response.status_code, 400)

    def test_check_violation_maps_to_400(self):
        exc = PersistenceIntegrityError(
            "regulatory source creation", _make_cause("23514", None)
        )
        response = asyncio.run(_call_handler(exc))
        self.assertEqual(response.status_code, 400)

    def test_unknown_integrity_error_maps_to_500(self):
        exc = PersistenceIntegrityError(
            "regulatory source creation", _make_cause("23505")
        )
        exc.cause.pgcode = "XX000"
        response = asyncio.run(_call_handler(exc))
        self.assertEqual(response.status_code, 500)
        body = response.body.decode()
        self.assertIn("internal_error", body)

    def test_client_response_leaks_no_database_details(self):
        exc = PersistenceIntegrityError(
            "regulatory source creation",
            _make_cause("23505", "regulatory_sources_identity_key"),
        )
        response = asyncio.run(_call_handler(exc))
        rendered = response.body.decode().lower()
        self.assertNotIn("postgresql", rendered)
        self.assertNotIn("sqlstate", rendered)
        self.assertNotIn("23505", rendered)
        self.assertNotIn("regulatory_sources_identity_key", rendered)
        self.assertNotIn("authority_id_fkey", rendered)
        self.assertNotIn("traceback", rendered)

    def test_logging_captures_diagnostics(self):
        records = []

        class CaptureHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        handler = CaptureHandler()
        logger = logging.getLogger("xportra.api.errors")
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
        try:
            exc = PersistenceIntegrityError(
                "regulatory source creation",
                _make_cause("23505", "regulatory_sources_identity_key"),
            )
            asyncio.run(_call_handler(exc))
        finally:
            logger.removeHandler(handler)

        self.assertGreaterEqual(len(records), 1)
        message = records[0].getMessage()
        self.assertIn("regulatory source creation", message)
        self.assertIn("23505", message)
        self.assertIn("regulatory_sources_identity_key", message)
        self.assertIn("Mock", message)

    def test_cause_attribute_preserves_original_exception(self):
        cause = _make_cause("23505", "regulatory_sources_identity_key")
        exc = PersistenceIntegrityError("regulatory source creation", cause)
        self.assertIs(exc.cause, cause)


class PersistenceIntegrityErrorAppTests(unittest.TestCase):
    """End-to-end tests through a minimal FastAPI app."""

    def _make_app(self) -> FastAPI:
        app = FastAPI()
        register_exception_handlers(app)

        @app.post("/test-unique")
        async def test_unique():
            raise PersistenceIntegrityError(
                "regulatory source creation",
                _make_cause("23505", "regulatory_sources_identity_key"),
            )

        @app.post("/test-fk")
        async def test_fk():
            raise PersistenceIntegrityError(
                "regulatory source creation",
                _make_cause("23503", "regulatory_sources_authority_id_fkey"),
            )

        @app.post("/test-unknown")
        async def test_unknown():
            exc = PersistenceIntegrityError(
                "regulatory source creation", _make_cause("XX000", None)
            )
            raise exc

        return app

    def test_unique_violation_returns_409_through_app(self):
        with TestClient(self._make_app(), raise_server_exceptions=False) as client:
            response = client.post("/test-unique")
        self.assertEqual(response.status_code, 409)
        body = response.json()
        self.assertEqual(body["error"]["code"], "integrity_conflict")

    def test_foreign_key_violation_returns_400_through_app(self):
        with TestClient(self._make_app(), raise_server_exceptions=False) as client:
            response = client.post("/test-fk")
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertEqual(body["error"]["code"], "integrity_violation")

    def test_unknown_integrity_returns_500_through_app(self):
        with TestClient(self._make_app(), raise_server_exceptions=False) as client:
            response = client.post("/test-unknown")
        self.assertEqual(response.status_code, 500)
        body = response.json()
        self.assertEqual(body["error"]["code"], "internal_error")


if __name__ == "__main__":
    unittest.main()
