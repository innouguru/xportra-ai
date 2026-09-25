"""Errors and HTTP exception handlers for the API boundary."""

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from xportra.application.errors import (
    ApplicationAuthenticationError,
    ApplicationAuthorizationError,
    ApplicationError,
    ApplicationNotFoundError,
    ApplicationValidationError,
    InfrastructureError,
    InvalidTransitionError,
    StaleAnalysisError,
    TenantMismatchError,
    TerminalWorkflowError,
    WorkflowNotReadyError,
)
from xportra.domain.answer_validation import AnswerValidationError
from xportra.domain.errors import (
    DomainNotFoundError,
    DomainPersistenceError,
    DomainValidationError,
    LLMProviderError,
    VectorStoreError,
)

from .runtime import is_production_environment

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
    application.add_exception_handler(StaleAnalysisError, _handle_application_error)
    application.add_exception_handler(WorkflowNotReadyError, _handle_application_error)
    application.add_exception_handler(ApplicationError, _handle_application_error)
    application.add_exception_handler(DomainNotFoundError, _handle_not_found)
    application.add_exception_handler(AnswerValidationError, _handle_answer_validation)
    application.add_exception_handler(LLMProviderError, _handle_llm_provider)
    application.add_exception_handler(VectorStoreError, _handle_vector_store)
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


#: Phase 8.2 mapping from application-error type to
#: (HTTP status, response code). Dispatched by exception
#: type — never by parsing messages. Subclasses are
#: registered explicitly (e.g. ``StaleAnalysisError``
#: before ``WorkflowNotReadyError``) so the stable
#: sub-category survives handler lookup.
_APPLICATION_ERROR_STATUS = (
    (ApplicationAuthenticationError, 401, "authentication_failed"),
    (ApplicationAuthorizationError, 403, "permission_denied"),
    (TenantMismatchError, 403, "tenant_mismatch"),
    (ApplicationNotFoundError, 404, "not_found"),
    (ApplicationValidationError, 400, "invalid_input"),
    (StaleAnalysisError, 409, "stale_analysis"),
    (WorkflowNotReadyError, 409, "not_ready"),
    (TerminalWorkflowError, 409, "terminal_workflow"),
    (InvalidTransitionError, 409, "invalid_transition"),
    (InfrastructureError, 503, "infrastructure_failure"),
)


async def _handle_application_error(
    _request: Request, exc: ApplicationError
) -> JSONResponse:
    """Map application errors to stable HTTP responses.

    Only identifiers, states, and reason codes travel in
    the body — application details by construction carry
    no prompts, secrets, provider internals, or tracebacks.
    Readiness reasons ride in ``details`` so a future
    frontend can render them without new calls.

    Production safety (Phase 10.1): 5xx responses carry no
    dynamic detail. ``InfrastructureError`` details derive
    from stringified driver/provider exceptions, which can
    embed table/constraint names, SQL fragments, or endpoint
    URLs — safe for local diagnostics, not for production
    clients. The stable ``code`` is always preserved so
    legitimate clients keep their error semantics.
    """
    status_code, code = 500, "application_error"
    for error_type, mapped_status, mapped_code in (
        _APPLICATION_ERROR_STATUS
    ):
        if isinstance(exc, error_type):
            status_code, code = mapped_status, mapped_code
            break
    headers = (
        {"WWW-Authenticate": "Bearer"}
        if status_code == 401 else None
    )
    if status_code >= 500 and is_production_environment():
        return JSONResponse(
            status_code=status_code,
            content={
                "error": {
                    "code": code,
                    "message": code.replace("_", " "),
                }
            },
            headers=headers,
        )
    content: dict[str, Any] = {
        "error": {
            "code": code,
            "message": exc.detail or code.replace("_", " "),
        }
    }
    reasons = getattr(exc, "reasons", ())
    if reasons:
        content["error"]["details"] = {
            "reasons": [
                {"code": reason_code, "detail": reason_detail}
                for reason_code, reason_detail in reasons
            ]
        }
    return JSONResponse(
        status_code=status_code, content=content, headers=headers
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


async def _handle_answer_validation(
    _request: Request, _exc: AnswerValidationError
) -> JSONResponse:
    """Citation-integrity failures stay distinguishable from provider failures.

    Registered alongside (and more specific than) the generic domain
    handler, so ``AnswerValidationError`` — a ``DomainValidationError``
    subclass — maps here via MRO lookup instead of collapsing into
    ``domain_validation_error``. No trace, answer text, or provenance
    internals leak into the response.
    """
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "citation_integrity_error",
                "message": "The generated answer failed citation validation",
            }
        },
    )


async def _handle_llm_provider(
    _request: Request, _exc: LLMProviderError
) -> JSONResponse:
    """Operational LLM failures never become successful empty answers."""
    return JSONResponse(
        status_code=502,
        content={
            "error": {
                "code": "llm_provider_error",
                "message": "Answer generation is temporarily unavailable",
            }
        },
    )


async def _handle_vector_store(
    _request: Request, _exc: VectorStoreError
) -> JSONResponse:
    """Operational retrieval failures never become successful empty answers."""
    return JSONResponse(
        status_code=502,
        content={
            "error": {
                "code": "vector_store_error",
                "message": "Evidence retrieval is temporarily unavailable",
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
