"""FastAPI application factory and startup wiring."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from .auth import SupabaseAuthSettings
from .compliance import router as compliance_router
from .dependencies import ApplicationServices
from .errors import register_exception_handlers
from .router import router


def create_app(services: ApplicationServices | None = None) -> FastAPI:
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
    )
    application.include_router(router)
    application.include_router(compliance_router)
    register_exception_handlers(application)
    if os.environ.get("APP_ENV", "development").lower() == "production":
        SupabaseAuthSettings.from_environment()
    return application


app = create_app()
