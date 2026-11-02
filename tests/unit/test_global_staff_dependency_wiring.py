"""Regression tests for the global-staff dependency wiring.

``Depends(require_global_staff)`` (the factory) instead of
``Depends(require_global_staff())`` (the checker) silently disabled the
JWT and grant checks: ``actor_id`` arrived as a function object and
registration failed with HTTP 500. Existing endpoint tests hid this by
overriding the dependency, so these tests deliberately use **no
overrides** and exercise the real checker.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from fastapi.testclient import TestClient

from xportra.api import dependencies
from xportra.api.app import create_app

STAFF_ROUTES = (
    ("GET", "/regulatory/authorities"),
    ("GET", "/regulatory/sources"),
    ("POST", "/regulatory/sources"),
)


def _client() -> TestClient:
    app = create_app(services=SimpleNamespace(database=SimpleNamespace()))
    return TestClient(app)


class GlobalStaffDependencyWiringTests(TestCase):
    def test_dependencies_are_checkers_not_factories(self):
        for name in (
            "global_staff_dependency",
            "stage_a_dependency",
            "stage_b_dependency",
        ):
            dependency = getattr(dependencies, name)
            self.assertEqual("dependency", dependency.__name__, name)

    def test_staff_routes_reject_missing_token_without_overrides(self):
        with _client() as client:
            for method, path in STAFF_ROUTES:
                response = client.request(
                    method, path, json={} if method == "POST" else None
                )
                self.assertEqual(
                    401, response.status_code, f"{method} {path}"
                )


class IntakeServiceStorageIsLazyTests(TestCase):
    def test_constructing_intake_service_does_not_require_storage_config(self):
        import os
        from unittest.mock import patch

        from xportra.application.regulatory_source_intake_service import (
            RegulatorySourceIntakeService,
        )

        with patch.dict(os.environ, {}, clear=True):
            # Must not raise EvidenceStorageConfigurationError: source
            # registration is metadata-only.
            RegulatorySourceIntakeService(SimpleNamespace())
