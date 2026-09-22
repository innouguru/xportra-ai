"""Connection and transaction boundary for PostgreSQL persistence."""

from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
import os
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row


class DatabaseConfigurationError(ValueError):
    """Raised when required database configuration is missing."""


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    dsn: str

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "DatabaseSettings":
        values = os.environ if environment is None else environment
        dsn = values.get("DATABASE_URL", "").strip()
        if not dsn:
            raise DatabaseConfigurationError("DATABASE_URL is required")
        return cls(dsn=dsn)


ConnectionFactory = Callable[..., Connection]


class Database:
    """Open short-lived connections and scope each operation to a transaction."""

    def __init__(
        self,
        settings: DatabaseSettings,
        connection_factory: ConnectionFactory = psycopg.connect,
    ) -> None:
        self._settings = settings
        self._connection_factory = connection_factory

    @contextmanager
    def connection(self) -> Iterator[Connection[Any]]:
        with self._connection_factory(
            self._settings.dsn,
            row_factory=dict_row,
        ) as connection:
            yield connection

    @contextmanager
    def transaction(self) -> Iterator[Connection[Any]]:
        with self.connection() as connection:
            with connection.transaction():
                yield connection