"""FastAPI application factory and startup wiring."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .auth import SupabaseAuthSettings
from .compliance import router as compliance_router
from .dependencies import ApplicationServices
from .errors import register_exception_handlers
from .router import router
from .runtime import (
    PRODUCTION_ENV_VALUE,
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
        application.state.services = (
            services if services is not None else ApplicationServices.from_environment()
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
    application.include_router(router)
    application.include_router(compliance_router)
    register_exception_handlers(application)
    if is_production_environment():
        SupabaseAuthSettings.from_environment()
    return application


app = create_app()
