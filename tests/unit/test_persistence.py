from contextlib import nullcontext
import unittest
from uuid import UUID

from psycopg.errors import UniqueViolation

from xportra.persistence.database import Database, DatabaseConfigurationError, DatabaseSettings
from xportra.persistence.errors import PersistenceIntegrityError
from xportra.persistence.repositories import ExporterRepository, TenantRepository
from xportra.persistence.tenant import TenantContext


class FakeCursor:
    def __init__(self, row=None, error=None):
        self.row = row
        self.error = error
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, parameters):
        self.statements.append((statement, parameters))
        if self.error is not None:
            raise self.error

    def fetchone(self):
        return self.row

    def fetchall(self):
        return [self.row] if self.row is not None else []


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.closed = False
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_args):
        self.closed = True
        if exc_type is None:
            self.committed = True
        else:
            self.rolled_back = True
        return False

    def cursor(self):
        return self.cursor_value

    def transaction(self):
        return nullcontext()


def database_with(cursor):
    connection = FakeConnection(cursor)

    def factory(*_args, **_kwargs):
        return connection

    return Database(DatabaseSettings("postgresql://test"), factory), connection


class PersistenceTests(unittest.TestCase):
    def test_database_settings_requires_database_url(self):
        with self.assertRaises(DatabaseConfigurationError):
            DatabaseSettings.from_environment({})

    def test_tenant_context_requires_uuid(self):
        with self.assertRaises(TypeError):
            TenantContext("tenant")

    def test_tenant_repository_write_uses_transaction_and_parameters(self):
        cursor = FakeCursor({"id": UUID("00000000-0000-0000-0000-000000000001")})
        database, connection = database_with(cursor)

        TenantRepository(database).create("Acme Exports", "acme")

        self.assertTrue(connection.closed)
        self.assertTrue(connection.committed)
        self.assertEqual(cursor.statements[0][1], ("Acme Exports", "acme", "active"))
        self.assertIn("%s", cursor.statements[0][0])

    def test_tenant_scoped_read_binds_context_before_record_id(self):
        cursor = FakeCursor({"id": "exporter"})
        database, _connection = database_with(cursor)
        tenant = TenantContext(UUID("00000000-0000-0000-0000-000000000010"))
        exporter_id = UUID("00000000-0000-0000-0000-000000000011")

        ExporterRepository(database).get(tenant, exporter_id)

        self.assertEqual(cursor.statements[0][1], (tenant.tenant_id, exporter_id))
        self.assertIn("tenant_id = %s", cursor.statements[0][0])

    def test_integrity_failure_preserves_database_cause(self):
        cause = UniqueViolation("duplicate")
        cursor = FakeCursor(error=cause)
        database, connection = database_with(cursor)

        with self.assertRaises(PersistenceIntegrityError) as error:
            TenantRepository(database).create("Acme Exports", "acme")

        self.assertIs(error.exception.__cause__, cause)
        self.assertEqual(error.exception.operation, "tenant creation")
        self.assertTrue(connection.closed)
        self.assertTrue(connection.rolled_back)


if __name__ == "__main__":
    unittest.main()
