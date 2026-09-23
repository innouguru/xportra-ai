"""Domain-level errors exposed above persistence."""

from typing import NoReturn

from xportra.persistence.errors import PersistenceIntegrityError


class DomainError(RuntimeError):
    """Base error for domain/application service failures."""


class DomainValidationError(DomainError, ValueError):
    """The requested operation violates a domain-level precondition."""


class DomainNotFoundError(DomainError):
    """A required tenant-scoped or shared record was not found."""


class DomainPersistenceError(DomainError):
    """A persistence failure translated at the domain boundary."""

    def __init__(self, operation: str, cause: PersistenceIntegrityError) -> None:
        super().__init__(f"domain operation failed during {operation}")
        self.operation = operation
        self.cause = cause


class VectorStoreError(DomainError):
    """A vector-store failure translated at the infrastructure boundary.

    Mirrors the ``DomainPersistenceError`` operation/cause convention so
    raw vector-database exceptions never escape through the domain API.
    """

    def __init__(self, operation: str, cause: BaseException) -> None:
        super().__init__(f"vector index operation failed during {operation}")
        self.operation = operation
        self.cause = cause


class LLMProviderError(DomainError):
    """An LLM provider failure translated at the infrastructure boundary.

    Mirrors the ``VectorStoreError`` operation/cause convention so raw
    provider/HTTP/SDK exceptions never escape through the domain API.
    Network, authentication, timeout, and rate-limit failures raise this
    — they are never converted into an empty answer or ``None``.
    """

    def __init__(self, operation: str, cause: BaseException) -> None:
        super().__init__(f"LLM provider operation failed during {operation}")
        self.operation = operation
        self.cause = cause


def require_tenant_context(context: object) -> NoReturn | None:
    """Validate that a service operation received explicit tenant context."""
    from xportra.persistence.tenant import TenantContext

    if not isinstance(context, TenantContext):
        raise DomainValidationError("explicit TenantContext is required")
    return None
