"""Application error taxonomy for the use-case boundary.

Categories the future HTTP API will map to responses.
This taxonomy carries no HTTP status codes, no request
objects, and no serialization details — mapping is a
Phase 8 API concern.

Ownership rules:

- ``ApplicationAuthenticationError`` /
  ``ApplicationAuthorizationError`` are raised at the API
  boundary by the existing Phase 1 verification and
  authorization policy. Use cases never fabricate them;
  they propagate them untouched when re-raised through
  orchestration.
- ``TenantMismatchError`` is raised by use cases from a
  deterministic record-vs-context comparison — never by
  parsing domain messages.
- ``WorkflowNotReadyError`` / ``StaleAnalysisError`` are
  built from the structured 7.3 readiness result the use
  case computed itself — never by parsing messages.
- ``TerminalWorkflowError`` comes from the explicit 7.5
  ``is_closed`` predicate checked before mutating calls.
- ``InvalidTransitionError`` wraps any other domain
  validation failure from an orchestrated operation,
  preserving the domain message as ``detail`` and the
  original error as ``cause``.
- ``ApplicationNotFoundError`` wraps domain not-found
  failures and empty reads.
- ``ApplicationValidationError`` covers malformed
  application inputs (including malformed workflow
  records) before any domain call.
- ``InfrastructureError`` wraps provider, retrieval,
  persistence, and other I/O failures. ``detail`` is the
  operational message with no tracebacks, prompts, or
  credentials — domain and infrastructure messages by
  construction carry only identities and operational
  states.
"""

from __future__ import annotations


class ApplicationError(Exception):
    """Base error for the application boundary."""

    category = "application_error"

    def __init__(self, detail: str = "", *,
                 cause: BaseException | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        if cause is not None:
            self.__cause__ = cause


class ApplicationAuthenticationError(ApplicationError):
    """No authenticated actor (raised at the API boundary)."""

    category = "authentication_failed"


class ApplicationAuthorizationError(ApplicationError):
    """Actor lacks the required role (raised at the API boundary)."""

    category = "authorization_failed"


class TenantMismatchError(ApplicationError):
    """Record tenant differs from the effective context tenant."""

    category = "tenant_mismatch"


class ApplicationValidationError(ApplicationError):
    """Malformed application input (never a domain verdict)."""

    category = "invalid_input"


class ApplicationNotFoundError(ApplicationError):
    """Referenced workflow/case/evidence/package identity unknown."""

    category = "not_found"


class InvalidTransitionError(ApplicationError):
    """Orchestrated domain operation rejected the transition."""

    category = "invalid_transition"


class WorkflowNotReadyError(ApplicationError):
    """Finalization readiness gate reports not ready."""

    category = "not_ready"

    def __init__(self, detail: str = "", *,
                 reasons: tuple[tuple[str, str], ...] = (),
                 cause: BaseException | None = None) -> None:
        super().__init__(detail, cause=cause)
        self.reasons = reasons


class StaleAnalysisError(WorkflowNotReadyError):
    """Not-ready because the analysis no longer matches."""

    category = "stale_analysis"


class TerminalWorkflowError(ApplicationError):
    """Mutating operation attempted on a closed workflow."""

    category = "terminal_workflow"


class InfrastructureError(ApplicationError):
    """Provider, retrieval, persistence, or other I/O failure."""

    category = "infrastructure_failure"


def sanitized_detail(cause: BaseException) -> str:
    """One-line operational detail without internals."""
    name = type(cause).__name__
    message = str(cause).replace("\n", " ").strip()
    if len(message) > 300:
        message = message[:297] + "..."
    return f"{name}: {message}" if message else name


__all__ = [
    "ApplicationAuthenticationError",
    "ApplicationAuthorizationError",
    "ApplicationError",
    "ApplicationNotFoundError",
    "ApplicationValidationError",
    "InfrastructureError",
    "InvalidTransitionError",
    "StaleAnalysisError",
    "TenantMismatchError",
    "TerminalWorkflowError",
    "WorkflowNotReadyError",
    "sanitized_detail",
]
