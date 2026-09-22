"""Errors and HTTP exception handlers for the API boundary."""

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from xportra.domain.errors import (
    DomainNotFoundError,
    DomainPersistenceError,
    DomainValidationError,
)

logger = logging.getLogger(__name__)


class APIError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class AuthenticationError(APIError):
    """Missing, invalid, or expired authentication credentials."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(401, code, message)


class PermissionDeniedError(APIError):
    """The authenticated member may not perform the requested operation."""

    def __init__(self) -> None:
        super().__init__(
            403,
            "permission_denied",
            "The authenticated member is not authorized for this operation",
        )


def register_exception_handlers(application) -> None:
    application.add_exception_handler(APIError, _handle_api_error)
    application.add_exception_handler(AuthenticationError, _handle_authentication_error)
    application.add_exception_handler(RequestValidationError, _handle_validation_error)
    application.add_exception_handler(DomainNotFoundError, _handle_not_found)
    application.add_exception_handler(DomainValidationError, _handle_domain_validation)
    application.add_exception_handler(DomainPersistenceError, _handle_persistence)
    application.add_exception_handler(Exception, _handle_unexpected_error)


async def _handle_authentication_error(
    _request: Request, exc: AuthenticationError
) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={
            "error": {"code": exc.code, "message": exc.message}
        },
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _handle_api_error(_request: Request, exc: APIError) -> JSONResponse:
    content: dict[str, Any] = {
        "error": {"code": exc.code, "message": exc.message}
    }
    if exc.details is not None:
        content["error"]["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content=content)


async def _handle_validation_error(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {
            "location": [str(part) for part in error.get("loc", ())],
            "type": error.get("type", "validation_error"),
            "message": error.get("msg", "Invalid request"),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "details": details,
            }
        },
    )


async def _handle_not_found(
    _request: Request, _exc: DomainNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "code": "resource_not_found",
                "message": "Resource was not found for the active tenant",
            }
        },
    )


async def _handle_domain_validation(
    _request: Request, _exc: DomainValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "domain_validation_error",
                "message": "The request violates a domain rule",
            }
        },
    )


async def _handle_persistence(
    _request: Request, _exc: DomainPersistenceError
) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "integrity_error",
                "message": "The operation violated a data integrity constraint",
            }
        },
    )


async def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled API exception",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An unexpected internal error occurred",
            }
        },
    )
