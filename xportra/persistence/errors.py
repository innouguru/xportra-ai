"""Persistence-layer exception types."""

from psycopg.errors import IntegrityError


class PersistenceIntegrityError(RuntimeError):
    """An operation violated a database integrity constraint."""

    def __init__(self, operation: str, cause: IntegrityError) -> None:
        super().__init__(f"database integrity failure during {operation}")
        self.operation = operation
        self.cause = cause