"""Secure CORS boundary for local frontend <-> API development.

Covers the explicit CORS configuration boundary without changing
product behavior:

- development/test default origins (local Vite on both loopback
  spellings, never a wildcard),
- successful OPTIONS preflight from an allowed origin,
- CORS headers on allowed-origin requests,
- disallowed origins receiving no permissive CORS headers,
- production using only explicit configuration with wildcards
  and malformed values rejected at startup,
- authentication still enforced with an allowed origin present,
- Phase 10.1 guarantees (security headers, dev-header rejection)
  intact alongside CORS.

Only the service container is faked. All API boundary code under
test is real. No live Supabase or browser dependencies are used.
"""

import os
import unittest
from contextlib import contextmanager
from types import SimpleNamespace

from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.api.runtime import (
    CORS_ALLOWED_HEADERS,
    CORS_ALLOWED_METHODS,
    LOCAL_DEVELOPMENT_CORS_ORIGINS,
    ProductionConfigurationError,
    cors_allowed_origins,
    validate_production_environment,
)

LOCALHOST_ORIGIN = "http://localhost:5173"
LOOPBACK_ORIGIN = "http://127.0.0.1:5173"
FOREIGN_ORIGIN = "https://evil.example"
START_PATH = "/compliance/workflows/start"


@contextmanager
def patched_env(**values):
    """Temporarily set (or clear with None) environment variables."""
    previous = {name: os.environ.get(name) for name in values}
    try:
        for name, value in values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def preflight(client, path, origin, method="POST"):
    return client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        },
    )


class CorsConfigurationTests(unittest.TestCase):
    def test_development_defaults_to_local_vite_origins(self):
        with patched_env(APP_ENV=None, CORS_ALLOWED_ORIGINS=None):
            origins = cors_allowed_origins()
        self.assertEqual(
            origins, (LOCALHOST_ORIGIN, LOOPBACK_ORIGIN))
        self.assertEqual(
            tuple(LOCAL_DEVELOPMENT_CORS_ORIGINS),
            (LOCALHOST_ORIGIN, LOOPBACK_ORIGIN))
        for origin in origins:
            self.assertNotIn("*", origin)

    def test_test_environment_uses_development_defaults(self):
        with patched_env(APP_ENV="test", CORS_ALLOWED_ORIGINS=None):
            self.assertEqual(
                cors_allowed_origins(),
                (LOCALHOST_ORIGIN, LOOPBACK_ORIGIN))

    def test_development_extras_are_added_without_duplicates(self):
        with patched_env(
            APP_ENV="development",
            CORS_ALLOWED_ORIGINS=(
                "https://staging.example.com, http://localhost:5173/"),
        ):
            origins = cors_allowed_origins()
        self.assertEqual(
            origins,
            (LOCALHOST_ORIGIN, LOOPBACK_ORIGIN,
             "https://staging.example.com"))

    def test_wildcards_rejected_in_every_environment(self):
        for env in ("development", "test", "production"):
            for raw in ("*", "https://*.example.com",
                        "https://app.example.com, *"):
                with self.subTest(env=env, raw=raw):
                    with self.assertRaises(ProductionConfigurationError):
                        cors_allowed_origins({
                            "APP_ENV": env,
                            "CORS_ALLOWED_ORIGINS": raw,
                        })

    def test_malformed_origins_rejected(self):
        for raw in ("not-a-url", "ftp://files.example.com",
                    "https://user@app.example.com",
                    "https://app.example.com/dashboard"):
            with self.subTest(raw=raw):
                with self.assertRaises(ProductionConfigurationError):
                    cors_allowed_origins({
                        "APP_ENV": "development",
                        "CORS_ALLOWED_ORIGINS": raw,
                    })

    def test_production_fails_closed_without_configuration(self):
        with patched_env(APP_ENV="production",
                         CORS_ALLOWED_ORIGINS=None):
            self.assertEqual(cors_allowed_origins(), ())

    def test_production_uses_only_explicit_configuration(self):
        origins = cors_allowed_origins({
            "APP_ENV": "production",
            "CORS_ALLOWED_ORIGINS":
                "https://app.example.com,https://admin.example.com",
        })
        self.assertEqual(
            origins,
            ("https://app.example.com", "https://admin.example.com"))

    def test_production_startup_validates_configured_origins(self):
        with self.assertRaises(ProductionConfigurationError):
            validate_production_environment({
                "APP_ENV": "production",
                "SUPABASE_JWT_SECRET": "secret-value",
                "DATABASE_URL": "postgresql://localhost/x",
                "CORS_ALLOWED_ORIGINS": "*",
            })
        with self.assertRaises(ProductionConfigurationError):
            validate_production_environment({
                "APP_ENV": "production",
                "SUPABASE_JWT_SECRET": "secret-value",
                "DATABASE_URL": "postgresql://localhost/x",
                "CORS_ALLOWED_ORIGINS": "https://app.example.com/path",
            })
        # Explicit valid origins still boot.
        validate_production_environment({
            "APP_ENV": "production",
            "SUPABASE_JWT_SECRET": "secret-value",
            "DATABASE_URL": "postgresql://localhost/x",
            "SUPABASE_URL": "https://proj.supabase.co",
            "CORS_ALLOWED_ORIGINS": "https://app.example.com",
        })

    def test_allowed_methods_and_headers_match_the_api_surface(self):
        self.assertEqual(tuple(CORS_ALLOWED_METHODS), ("GET", "POST"))
        for header in ("Content-Type", "Authorization",
                       "X-Development-Tenant-ID"):
            self.assertIn(header, CORS_ALLOWED_HEADERS)


class CorsPreflightTests(unittest.TestCase):
    def test_allowed_origin_preflight_succeeds(self):
        with patched_env(APP_ENV=None, CORS_ALLOWED_ORIGINS=None):
            with TestClient(create_app(
                    services=SimpleNamespace())) as client:
                for origin in (LOCALHOST_ORIGIN, LOOPBACK_ORIGIN):
                    with self.subTest(origin=origin):
                        response = preflight(
                            client, START_PATH, origin)
                        self.assertEqual(response.status_code, 200)
                        self.assertEqual(
                            response.headers.get(
                                "access-control-allow-origin"),
                            origin)
                        allow_methods = response.headers.get(
                            "access-control-allow-methods", "")
                        self.assertIn("POST", allow_methods)
                        allow_headers = response.headers.get(
                            "access-control-allow-headers", "")
                        self.assertIn("Authorization", allow_headers)

    def test_disallowed_origin_gets_no_permissive_headers(self):
        with patched_env(APP_ENV=None, CORS_ALLOWED_ORIGINS=None):
            with TestClient(create_app(
                    services=SimpleNamespace())) as client:
                response = preflight(
                    client, START_PATH, FOREIGN_ORIGIN)
        self.assertEqual(response.status_code, 400)
        self.assertIsNone(
            response.headers.get("access-control-allow-origin"))

    def test_allowed_origin_request_carries_cors_headers(self):
        with patched_env(APP_ENV=None, CORS_ALLOWED_ORIGINS=None):
            with TestClient(create_app(
                    services=SimpleNamespace())) as client:
                response = client.get(
                    "/openapi.json",
                    headers={"Origin": LOCALHOST_ORIGIN},
                )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            LOCALHOST_ORIGIN)

    def test_disallowed_origin_request_carries_no_cors_headers(self):
        with patched_env(APP_ENV=None, CORS_ALLOWED_ORIGINS=None):
            with TestClient(create_app(
                    services=SimpleNamespace())) as client:
                response = client.get(
                    "/openapi.json",
                    headers={"Origin": FOREIGN_ORIGIN},
                )
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(
            response.headers.get("access-control-allow-origin"))

    def test_cors_does_not_bypass_authentication(self):
        # An allowed origin with no credentials must still fail
        # closed at the existing auth boundary.
        with patched_env(APP_ENV=None, CORS_ALLOWED_ORIGINS=None):
            with TestClient(create_app(
                    services=SimpleNamespace())) as client:
                response = client.post(
                    START_PATH,
                    headers={"Origin": LOCALHOST_ORIGIN},
                    json={"case_id":
                          "cccccccc-cccc-cccc-cccc-cccccccccccc"},
                )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            LOCALHOST_ORIGIN)

    def test_production_uses_configured_origins(self):
        with patched_env(APP_ENV="production",
                         SUPABASE_JWT_SECRET="test-secret",
                         CORS_ALLOWED_ORIGINS="https://app.example.com"):
            with TestClient(create_app(
                    services=SimpleNamespace())) as client:
                configured = preflight(
                    client, START_PATH, "https://app.example.com")
                self.assertEqual(configured.status_code, 200)
                self.assertEqual(
                    configured.headers.get(
                        "access-control-allow-origin"),
                    "https://app.example.com")
                local = preflight(
                    client, START_PATH, LOCALHOST_ORIGIN)
                self.assertIsNone(
                    local.headers.get("access-control-allow-origin"))

    def test_security_headers_survive_alongside_cors(self):
        with patched_env(APP_ENV=None, CORS_ALLOWED_ORIGINS=None):
            with TestClient(create_app(
                    services=SimpleNamespace())) as client:
                response = client.get(
                    "/openapi.json",
                    headers={"Origin": LOCALHOST_ORIGIN},
                )
        self.assertEqual(
            response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(
            response.headers["referrer-policy"], "no-referrer")

    def test_production_dev_header_still_rejected_with_cors(self):
        with patched_env(APP_ENV="production",
                         SUPABASE_JWT_SECRET="test-secret",
                         CORS_ALLOWED_ORIGINS="https://app.example.com"):
            with TestClient(create_app(
                    services=SimpleNamespace())) as client:
                response = client.post(
                    "/exporters",
                    headers={
                        "Origin": "https://app.example.com",
                        "X-Development-Tenant-ID":
                            "11111111-1111-1111-1111-111111111111",
                    },
                    json={"legal_name": "Acme"},
                )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"],
                         "development_tenant_context_disabled")


if __name__ == "__main__":
    unittest.main()
