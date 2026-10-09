"""render-production-wiring — lifespan composition and liveness probe tests.

Covers the Render production wiring task without live credentials,
live network, or a live database:

- ``GET /health``: unauthenticated 200 with a minimal stable body,
  available in every environment (including production with docs
  disabled), touching neither configuration secrets nor services.
- Production composition, core-only: the application boots without
  RAG/storage configuration; ``/health`` serves; the core
  authenticated API stays available (anonymous production requests
  still 401 at the auth boundary, never 500/503-not-ready); the
  RAG/upload dependencies fail closed with the established 503
  codes; malformed optional configuration degrades instead of
  breaking boot; a missing database still fails boot.
- Production composition, fully configured (dead-endpoint values
  only — nothing routable, so success itself proves no startup
  connectivity): RAG, storage, and index-sync are all wired to the
  production implementations; the embedding model is not downloaded
  at composition; the application boots.

Only deterministic doubles and unroutable placeholder values are
used. No Qdrant, OpenRouter, Supabase, or PostgreSQL call is made.
"""

import os
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock

from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.api.dependencies import (
    ApplicationServices,
    get_evidence_upload_service,
    get_rag_service,
)
from xportra.api.errors import APIError
from xportra.api.runtime import (
    ProductionConfigurationError,
    validate_production_environment,
)
from xportra.domain.evidence_index_sync import EvidenceIndexSyncService
from xportra.domain.rag_application import RAGApplicationService
from xportra.infrastructure.evidence_storage import (
    SupabaseEvidenceObjectStore,
)
from xportra.infrastructure.rag_composition import (
    compose_rag_stack_from_environment,
)
from xportra.persistence.database import DatabaseConfigurationError

CORE_PRODUCTION_ENV = {
    "APP_ENV": "production",
    "APP_DEBUG": "false",
    "DATABASE_URL": "postgresql://localhost/xportra-wiring-test",
    "SUPABASE_JWT_SECRET": "wiring-test-jwt-secret",
    "SUPABASE_URL": "https://wiring-test.supabase.co",
}

OPTIONAL_CAPABILITY_VARS = (
    "VECTOR_STORE_URL",
    "VECTOR_STORE_COLLECTION",
    "LLM_API_KEY",
    "LLM_MODEL",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIMENSIONS",
    "SUPABASE_SERVICE_ROLE_KEY",
)

#: Deliberately unroutable placeholders. Composition succeeding
#: against these proves no connection is attempted at startup —
#: any connect/read would fail immediately and loudly.
FULL_CAPABILITY_ENV = {
    "VECTOR_STORE_URL": "http://127.0.0.1:1",
    "VECTOR_STORE_COLLECTION": "xportra-wiring-test",
    "EMBEDDING_MODEL": "wiring-test-embed-model",
    "EMBEDDING_DIMENSIONS": "384",
    "LLM_API_KEY": "wiring-test-llm-key",
    "LLM_MODEL": "wiring-test-llm-model",
    "SUPABASE_SERVICE_ROLE_KEY": "wiring-test-service-role-key",
}


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


def core_only_env(**overrides):
    """Production core configuration with every optional cleared."""
    env = dict(CORE_PRODUCTION_ENV)
    env.update({name: None for name in OPTIONAL_CAPABILITY_VARS})
    env.update(overrides)
    return env


def fake_request(services):
    """Minimal request double carrying the lifespan service container."""
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(services=services))
    )


class HealthEndpointTests(unittest.TestCase):
    def test_health_returns_200_with_stable_body(self):
        with patched_env(APP_ENV=None):
            with TestClient(create_app(
                    services=SimpleNamespace())) as client:
                response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_health_needs_no_authentication(self):
        # No Authorization header, no development-tenant header —
        # and the 200 (not 401/503) proves neither boundary runs.
        with patched_env(APP_ENV=None):
            with TestClient(create_app(
                    services=SimpleNamespace())) as client:
                response = client.get("/health")
        self.assertEqual(response.status_code, 200)

    def test_health_needs_no_database_configuration(self):
        # Production import without DATABASE_URL would refuse boot;
        # injected services plus a present secret isolate the probe
        # itself: SimpleNamespace carries no database, so any
        # database/config access would 500 instead of 200.
        with patched_env(APP_ENV="production",
                          SUPABASE_JWT_SECRET="wiring-test-jwt-secret",
                          DATABASE_URL=None):
            with TestClient(create_app(
                    services=SimpleNamespace())) as client:
                response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_health_stays_available_when_docs_are_disabled(self):
        # Production locks down /docs, /redoc, /openapi.json; the
        # liveness probe must not be locked down with them.
        with patched_env(APP_ENV="production",
                          SUPABASE_JWT_SECRET="wiring-test-jwt-secret"):
            with TestClient(create_app(
                    services=SimpleNamespace())) as client:
                health = client.get("/health")
                docs = client.get("/docs")
                schema = client.get("/openapi.json")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(docs.status_code, 404)
        self.assertEqual(schema.status_code, 404)

    def test_health_carries_security_headers(self):
        with patched_env(APP_ENV=None):
            with TestClient(create_app(
                    services=SimpleNamespace())) as client:
                response = client.get("/health")
        self.assertEqual(
            response.headers["x-content-type-options"], "nosniff")


class CoreOnlyCompositionTests(unittest.TestCase):
    def test_core_only_composition_leaves_optionals_unwired(self):
        with patched_env(**core_only_env()):
            services = (
                ApplicationServices.from_environment_with_capabilities()
            )
        self.assertIsNotNone(services.database)
        self.assertIsNotNone(services.result_store)
        self.assertIsNotNone(services.evidence)
        self.assertIsNone(services.rag)
        self.assertIsNone(services.evidence_storage)
        self.assertIsNone(services.evidence_index_sync)

    def test_core_only_app_boots_and_serves_health(self):
        with patched_env(**core_only_env()):
            app = create_app()
            with TestClient(app) as client:
                response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        services = app.state.services
        self.assertIsNone(services.rag)
        self.assertIsNone(services.evidence_storage)
        self.assertIsNone(services.evidence_index_sync)

    def test_core_only_core_api_stays_available(self):
        # Anonymous production requests must still reach the auth
        # boundary (401) — proving core routing works and the app
        # is not stuck in a not-ready state.
        with patched_env(**core_only_env()):
            with TestClient(create_app()) as client:
                response = client.post(
                    "/exporters", json={"legal_name": "Acme"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["error"]["code"], "authentication_required")

    def test_core_only_rag_route_fails_closed(self):
        with patched_env(**core_only_env()):
            services = (
                ApplicationServices.from_environment_with_capabilities()
            )
        with self.assertRaises(APIError) as raised:
            get_rag_service(fake_request(services))
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(raised.exception.code, "rag_not_configured")

    def test_core_only_upload_route_fails_closed(self):
        with patched_env(**core_only_env()):
            services = (
                ApplicationServices.from_environment_with_capabilities()
            )
        with self.assertRaises(APIError) as raised:
            get_evidence_upload_service(fake_request(services))
        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.code, "evidence_upload_not_configured")

    def test_malformed_optional_config_still_boots_core(self):
        # A broken optional (non-integer dimensions) degrades to
        # unwired — it must not break boot or core routes.
        with patched_env(**core_only_env(
                VECTOR_STORE_URL="http://127.0.0.1:1",
                VECTOR_STORE_COLLECTION="xportra-wiring-test",
                EMBEDDING_MODEL="wiring-test-embed-model",
                EMBEDDING_DIMENSIONS="not-an-integer",
                LLM_API_KEY="wiring-test-llm-key",
                LLM_MODEL="wiring-test-llm-model")):
            app = create_app()
            with TestClient(app) as client:
                response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(app.state.services.rag)
        self.assertIsNone(app.state.services.evidence_index_sync)

    def test_missing_database_still_fails_boot(self):
        with patched_env(**core_only_env(DATABASE_URL=None)):
            with self.assertRaises(DatabaseConfigurationError):
                ApplicationServices.from_environment_with_capabilities()


class FullyConfiguredCompositionTests(unittest.TestCase):
    def test_full_composition_wires_all_capabilities(self):
        with patched_env(**{**core_only_env(), **FULL_CAPABILITY_ENV}):
            services = (
                ApplicationServices.from_environment_with_capabilities()
            )
        self.assertIsInstance(services.rag, RAGApplicationService)
        self.assertIsInstance(
            services.evidence_storage, SupabaseEvidenceObjectStore)
        self.assertIsInstance(
            services.evidence_index_sync, EvidenceIndexSyncService)

    def test_embedding_model_not_downloaded_at_composition(self):
        with patched_env(**{**core_only_env(), **FULL_CAPABILITY_ENV}):
            composition = compose_rag_stack_from_environment()
        self.assertFalse(composition.embedding_provider.is_loaded)

    def test_composition_starts_no_background_threads(self):
        # The Qdrant client's default background version probe must
        # stay disabled: composition must start zero threads, so no
        # connectivity check can fire during startup.
        import qdrant_client.qdrant_remote as qdrant_remote

        started = []

        class RecordingThread:
            def __init__(self, *args, **kwargs):
                started.append((args, kwargs))

            def start(self):
                pass

        with patched_env(**{**core_only_env(), **FULL_CAPABILITY_ENV}):
            with mock.patch.object(
                    qdrant_remote, "Thread", RecordingThread):
                ApplicationServices.from_environment_with_capabilities()
        self.assertEqual(started, [])

    def test_fully_configured_app_boots_and_serves_health(self):
        with patched_env(**{**core_only_env(), **FULL_CAPABILITY_ENV}):
            app = create_app()
            with TestClient(app) as client:
                response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(app.state.services.rag)
        self.assertIsNotNone(app.state.services.evidence_storage)
        self.assertIsNotNone(app.state.services.evidence_index_sync)

    def test_partial_storage_without_qdrant_wires_storage_only(self):
        # Each capability is independent: storage needs only the
        # Supabase pair, while RAG/index-sync need the vector vars.
        with patched_env(**core_only_env(
                SUPABASE_SERVICE_ROLE_KEY="wiring-test-service-role-key")):
            services = (
                ApplicationServices.from_environment_with_capabilities()
            )
        self.assertIsInstance(
            services.evidence_storage, SupabaseEvidenceObjectStore)
        self.assertIsNone(services.rag)
        self.assertIsNone(services.evidence_index_sync)


class ProductionSupabaseUrlGateTests(unittest.TestCase):
    def test_production_validation_requires_supabase_url(self):
        with self.assertRaises(ProductionConfigurationError):
            validate_production_environment({
                "APP_ENV": "production",
                "SUPABASE_JWT_SECRET": "secret-value",
                "DATABASE_URL": "postgresql://localhost/x",
            })

    def test_production_validation_rejects_blank_supabase_url(self):
        with self.assertRaises(ProductionConfigurationError):
            validate_production_environment({
                "APP_ENV": "production",
                "SUPABASE_JWT_SECRET": "secret-value",
                "DATABASE_URL": "postgresql://localhost/x",
                "SUPABASE_URL": "   ",
            })

    def test_non_production_does_not_require_supabase_url(self):
        validate_production_environment({"APP_ENV": "development"})
        validate_production_environment({})

    def test_production_composed_path_requires_supabase_url(self):
        with patched_env(APP_ENV="production",
                          SUPABASE_JWT_SECRET="test-secret",
                          DATABASE_URL="postgresql://localhost/x",
                          SUPABASE_URL=None,
                          APP_DEBUG=None):
            with self.assertRaises(ProductionConfigurationError):
                create_app()


if __name__ == "__main__":
    unittest.main()
