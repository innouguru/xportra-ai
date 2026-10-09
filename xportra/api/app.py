"""FastAPI application factory and startup wiring."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .auth import SupabaseAuthSettings
from .compliance import router as compliance_router
from .conversations import router as conversations_router
from .dependencies import ApplicationServices
from .errors import register_exception_handlers
from .evidence_uploads import router as evidence_uploads_router
from .health import router as health_router
from .router import router
from .runtime import (
    CORS_ALLOWED_HEADERS,
    CORS_ALLOWED_METHODS,
    CORS_PREFLIGHT_MAX_AGE,
    PRODUCTION_ENV_VALUE,
    cors_allowed_origins,
    is_production_environment,
    validate_app_env,
    validate_production_environment,
)


class SecurityHeadersMiddleware:
    """Minimal baseline response headers for the JSON API surface.

    Pure ASGI middleware: sets ``X-Content-Type-Options: nosniff``,
    ``X-Frame-Options: DENY``, and ``Referrer-Policy: no-referrer`` on
    HTTP responses without touching bodies or status codes, and never
    overwrites a header the application already set.
    """

    HEADERS = (
        (b"x-content-type-options", b"nosniff"),
        (b"x-frame-options", b"DENY"),
        (b"referrer-policy", b"no-referrer"),
    )

    def __init__(self, app) -> None:
        self._app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        async def send_with_headers(message) -> None:
            if message["type"] == "http.response.start":
                existing = {
                    name.lower()
                    for name, _ in message.get("headers", [])
                }
                message["headers"] = [
                    *message.get("headers", []),
                    *(
                        (name, value)
                        for name, value in self.HEADERS
                        if name.lower() not in existing
                    ),
                ]
            await send(message)

        await self._app(scope, receive, send_with_headers)


def create_app(services: ApplicationServices | None = None) -> FastAPI:
    app_env = validate_app_env()
    production = app_env == PRODUCTION_ENV_VALUE
    if production and services is None:
        validate_production_environment()

    @asynccontextmanager
    async def lifespan(application) -> AsyncIterator[None]:
        # Production lifespan composition (render-production-wiring):
        # the database-backed base stays required while the RAG,
        # storage, and index-sync capabilities are each composed
        # independently — missing optionals degrade to the existing
        # per-route 503s without failing boot or touching unrelated
        # core routes, and no external call is made at startup.
        application.state.services = (
            services if services is not None
            else ApplicationServices.from_environment_with_capabilities()
        )
        yield

    application = FastAPI(
        title="Xportra AI API",
        version="0.1.0",
        lifespan=lifespan,
        # Interactive documentation and the raw OpenAPI schema are a
        # development/test aid only; production serves no docs surface.
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
        # Traceback-in-response debug mode is never enabled; production
        # additionally pins APP_DEBUG off at startup (see runtime).
        debug=False,
    )
    application.add_middleware(SecurityHeadersMiddleware)
    # Explicit CORS boundary (outermost, so preflight
    # short-circuits before routing, auth, or error
    # handling). Origins come solely from
    # ``cors_allowed_origins()`` — local Vite origins in
    # development/test, explicit configuration only in
    # production, wildcards forbidden everywhere. CORS
    # declares which browser origins may read responses;
    # it changes nothing about authentication or tenant
    # isolation, and credentialed requests stay disabled
    # (no cookies are used; auth rides on headers).
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_allowed_origins()),
        allow_credentials=False,
        allow_methods=list(CORS_ALLOWED_METHODS),
        allow_headers=list(CORS_ALLOWED_HEADERS),
        max_age=CORS_PREFLIGHT_MAX_AGE,
    )
    application.include_router(router)
    application.include_router(compliance_router)
    application.include_router(conversations_router)
    application.include_router(evidence_uploads_router)
    # Liveness probe: unauthenticated and dependency-free by
    # construction (see xportra.api.health) — safe to probe while
    # downstream services are unavailable.
    application.include_router(health_router)
    register_exception_handlers(application)
    if is_production_environment():
        SupabaseAuthSettings.from_environment()
    return application


app = create_app()
