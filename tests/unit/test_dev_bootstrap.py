"""Focused tests for the local-development bootstrap.

Covers first-run creation, rerun idempotency, the
tenant/membership relationship, the owner role, no
duplicate memberships, production refusal, unchanged
tenant isolation (only the three identity tables are
ever touched, always with the development keys), and
the new natural-key repository lookups. The scripted
database double stands in for Postgres; live-database
coverage stays in tests/integration by convention.
"""

import io
import unittest
from contextlib import nullcontext, redirect_stdout
from uuid import UUID

from psycopg.errors import UniqueViolation

from xportra.api.authorization import OWNER_ROLE
from xportra.dev.bootstrap import (
    DEV_ROLE,
    DEV_TENANT_SLUG,
    DEV_USER_EMAIL,
    DevBootstrapError,
    bootstrap_development_environment,
    main,
)
from xportra.persistence.database import Database, DatabaseSettings
from xportra.persistence.errors import PersistenceIntegrityError
from xportra.persistence.repositories import (
    TenantRepository,
    UserRepository,
)
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("10000000-0000-0000-0000-000000000001")
USER_ID = UUID("10000000-0000-0000-0000-000000000002")
OTHER_TENANT_ID = UUID("10000000-0000-0000-0000-000000000009")
SUBJECT_UID = UUID("10000000-0000-0000-0000-000000000003")
OTHER_UID = UUID("10000000-0000-0000-0000-000000000004")

ENV = {"DATABASE_URL": "postgresql://localhost/xportra_test"}


def tenant_row(status="active"):
    return {
        "id": TENANT_ID,
        "legal_name": "Local Development Tenant",
        "slug": DEV_TENANT_SLUG,
        "status": status,
    }


def user_row(status="active", supabase_uid=None):
    return {
        "id": USER_ID,
        "display_name": "Local Developer",
        "email": DEV_USER_EMAIL,
        "status": status,
        "supabase_uid": supabase_uid,
    }


def membership_row(status="active", role="owner"):
    return {
        "id": UUID("10000000-0000-0000-0000-000000000005"),
        "tenant_id": TENANT_ID,
        "user_id": USER_ID,
        "role": role,
        "status": status,
    }


class ScriptedCursor:
    """Answer statements from a route table, recording everything."""

    def __init__(self, routes):
        self.routes = list(routes)
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, parameters):
        self.statements.append((statement, parameters))
        for key, kind, payload in self.routes:
            if key in statement:
                if isinstance(payload, BaseException):
                    raise payload
                if kind == "one":
                    self._pending = payload
                else:
                    self._pending = list(payload)
                return
        raise AssertionError(f"unexpected statement: {statement[:80]}")

    def fetchone(self):
        return self._pending

    def fetchall(self):
        pending = self._pending
        return pending if isinstance(pending, list) else (
            [pending] if pending is not None else []
        )


class ScriptedConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def cursor(self):
        return self.cursor_value

    def transaction(self):
        return nullcontext()


def scripted_database(routes):
    cursor = ScriptedCursor(routes)
    connection = ScriptedConnection(cursor)

    def factory(*_args, **_kwargs):
        return connection

    return Database(DatabaseSettings("postgresql://test"), factory), cursor


def first_run_routes():
    return [
        ("FROM xportra.tenants WHERE slug", "one", None),
        ("INSERT INTO xportra.tenants", "one", tenant_row()),
        ("FROM xportra.users WHERE email", "one", None),
        ("INSERT INTO xportra.users", "one", user_row()),
        ("FROM xportra.user_tenant_memberships", "all", []),
        (
            "INSERT INTO xportra.user_tenant_memberships",
            "one",
            membership_row(),
        ),
    ]


def second_run_routes():
    return [
        ("FROM xportra.tenants WHERE slug", "one", tenant_row()),
        ("FROM xportra.users WHERE email", "one", user_row()),
        (
            "FROM xportra.user_tenant_memberships",
            "all",
            [membership_row()],
        ),
    ]


def statements_of(cursor):
    return [statement for statement, _ in cursor.statements]


class BootstrapCreationTests(unittest.TestCase):
    def test_first_run_creates_tenant_user_and_membership(self):
        database, cursor = scripted_database(first_run_routes())
        report = bootstrap_development_environment(database)

        self.assertTrue(report["tenant"]["created"])
        self.assertTrue(report["user"]["created"])
        self.assertTrue(report["membership"]["created"])
        self.assertEqual(report["tenant"]["id"], TENANT_ID)
        self.assertEqual(report["tenant"]["slug"], DEV_TENANT_SLUG)
        self.assertEqual(report["user"]["id"], USER_ID)
        self.assertEqual(report["user"]["email"], DEV_USER_EMAIL)
        self.assertEqual(report["membership"]["role"], "owner")
        self.assertEqual(report["membership"]["status"], "active")

    def test_membership_links_developer_to_tenant(self):
        database, cursor = scripted_database(first_run_routes())
        bootstrap_development_environment(database)

        inserts = {
            statement.split("INTO ")[1].split(" ")[0]: parameters
            for statement, parameters in cursor.statements
            if statement.lstrip().startswith("INSERT")
        }
        self.assertEqual(
            inserts["xportra.user_tenant_memberships"],
            (TENANT_ID, USER_ID, "owner", "active"),
        )

    def test_development_role_is_the_api_owner_role(self):
        self.assertEqual(DEV_ROLE, OWNER_ROLE)
        self.assertEqual(DEV_ROLE, "owner")

    def test_only_identity_tables_are_touched(self):
        database, cursor = scripted_database(first_run_routes())
        bootstrap_development_environment(database)

        allowed = {
            "xportra.tenants",
            "xportra.users",
            "xportra.user_tenant_memberships",
        }
        for statement in statements_of(cursor):
            touched = {t for t in allowed if t in statement}
            self.assertTrue(touched, statement)
        for statement, parameters in cursor.statements:
            flat = " ".join(str(part) for part in parameters)
            self.assertNotIn(str(OTHER_TENANT_ID), flat)


class BootstrapIdempotencyTests(unittest.TestCase):
    def test_second_run_creates_nothing(self):
        database, cursor = scripted_database(second_run_routes())
        report = bootstrap_development_environment(database)

        self.assertFalse(report["tenant"]["created"])
        self.assertFalse(report["user"]["created"])
        self.assertFalse(report["membership"]["created"])
        self.assertEqual(report["tenant"]["id"], TENANT_ID)
        for statement in statements_of(cursor):
            self.assertFalse(
                statement.lstrip().startswith("INSERT"), statement
            )

    def test_no_duplicate_membership_on_rerun(self):
        database, cursor = scripted_database(second_run_routes())
        first = bootstrap_development_environment(database)
        second = bootstrap_development_environment(database)

        self.assertEqual(first["membership"], second["membership"])
        inserts = [
            s for s in statements_of(cursor)
            if "INSERT INTO xportra.user_tenant_memberships" in s
        ]
        self.assertEqual(inserts, [])


class BootstrapConflictTests(unittest.TestCase):
    def test_suspended_tenant_is_refused(self):
        routes = [("FROM xportra.tenants WHERE slug", "one",
                   tenant_row(status="suspended"))]
        database, cursor = scripted_database(routes)
        with self.assertRaises(DevBootstrapError):
            bootstrap_development_environment(database)
        self.assertEqual(len(cursor.statements), 1)

    def test_revoked_membership_is_refused_not_duplicated(self):
        routes = [
            ("FROM xportra.tenants WHERE slug", "one", tenant_row()),
            ("FROM xportra.users WHERE email", "one", user_row()),
            ("FROM xportra.user_tenant_memberships", "all",
             [membership_row(status="revoked")]),
        ]
        database, cursor = scripted_database(routes)
        with self.assertRaises(DevBootstrapError):
            bootstrap_development_environment(database)
        for statement in statements_of(cursor):
            self.assertNotIn("INSERT", statement)

    def test_wrong_role_membership_is_refused(self):
        routes = [
            ("FROM xportra.tenants WHERE slug", "one", tenant_row()),
            ("FROM xportra.users WHERE email", "one", user_row()),
            ("FROM xportra.user_tenant_memberships", "all",
             [membership_row(role="member")]),
        ]
        database, _cursor = scripted_database(routes)
        with self.assertRaises(DevBootstrapError):
            bootstrap_development_environment(database)

    def test_conflicting_supabase_link_is_refused(self):
        routes = [
            ("FROM xportra.tenants WHERE slug", "one", tenant_row()),
            ("FROM xportra.users WHERE email", "one",
             user_row(supabase_uid=OTHER_UID)),
        ]
        database, cursor = scripted_database(routes)
        with self.assertRaises(DevBootstrapError):
            bootstrap_development_environment(
                database, supabase_uid=SUBJECT_UID
            )
        for statement in statements_of(cursor):
            self.assertNotIn("UPDATE", statement)

    def test_supabase_uid_can_be_linked_when_unset(self):
        linked = user_row(supabase_uid=SUBJECT_UID)
        routes = [
            ("FROM xportra.tenants WHERE slug", "one", tenant_row()),
            ("FROM xportra.users WHERE email", "one", user_row()),
            ("UPDATE xportra.users", "one", linked),
            ("FROM xportra.user_tenant_memberships", "all",
             [membership_row()]),
        ]
        database, cursor = scripted_database(routes)
        report = bootstrap_development_environment(
            database, supabase_uid=SUBJECT_UID
        )
        self.assertTrue(report["user"]["supabase_uid_linked"])
        self.assertEqual(report["user"]["supabase_uid"], SUBJECT_UID)
        updates = [s for s in statements_of(cursor) if "UPDATE" in s]
        self.assertEqual(len(updates), 1)


class BootstrapEntrypointTests(unittest.TestCase):
    def test_production_is_refused_before_any_database_use(self):
        def exploding_factory(*_args, **_kwargs):
            raise AssertionError("database must not be touched")

        database = Database(
            DatabaseSettings("postgresql://localhost/x"), exploding_factory
        )
        code = main(
            [], {"APP_ENV": "production",
                 "DATABASE_URL": "postgresql://localhost/x"},
            database,
        )
        self.assertEqual(code, 2)

    def test_missing_database_url_is_refused(self):
        self.assertEqual(main([], {}), 2)

    def test_invalid_supabase_uid_is_rejected(self):
        database, _cursor = scripted_database(first_run_routes())
        self.assertEqual(
            main(["--supabase-uid", "not-a-uuid"], ENV, database), 2
        )

    def test_main_reports_created_records_without_secrets(self):
        database, _cursor = scripted_database(first_run_routes())
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main([], ENV, database)
        output = buffer.getvalue()
        self.assertEqual(code, 0)
        self.assertIn(str(TENANT_ID), output)
        self.assertIn(str(USER_ID), output)
        self.assertIn("owner", output)
        self.assertIn("created", output)
        self.assertNotIn("postgresql://", output)
        self.assertNotIn("secret", output.lower())

    def test_main_reports_existing_records_on_rerun(self):
        database, _cursor = scripted_database(second_run_routes())
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main([], ENV, database)
        self.assertEqual(code, 0)
        self.assertIn("already existed", buffer.getvalue())


class NaturalKeyRepositoryTests(unittest.TestCase):
    def test_get_by_slug_binds_slug(self):
        from tests.unit.test_persistence import FakeCursor, database_with

        cursor = FakeCursor({"id": TENANT_ID})
        database, _connection = database_with(cursor)
        row = TenantRepository(database).get_by_slug(DEV_TENANT_SLUG)
        self.assertEqual(row, {"id": TENANT_ID})
        statement, parameters = cursor.statements[0]
        self.assertIn("WHERE slug = %s", statement)
        self.assertEqual(parameters, (DEV_TENANT_SLUG,))

    def test_get_by_email_binds_email(self):
        from tests.unit.test_persistence import FakeCursor, database_with

        cursor = FakeCursor({"id": USER_ID})
        database, _connection = database_with(cursor)
        row = UserRepository(database).get_by_email(DEV_USER_EMAIL)
        self.assertEqual(row, {"id": USER_ID})
        statement, parameters = cursor.statements[0]
        self.assertIn("WHERE email = %s", statement)
        self.assertEqual(parameters, (DEV_USER_EMAIL,))

    def test_set_supabase_uid_updates_one_user(self):
        from tests.unit.test_persistence import FakeCursor, database_with

        cursor = FakeCursor({"id": USER_ID, "supabase_uid": SUBJECT_UID})
        database, _connection = database_with(cursor)
        row = UserRepository(database).set_supabase_uid(USER_ID, SUBJECT_UID)
        self.assertEqual(row["supabase_uid"], SUBJECT_UID)
        statement, parameters = cursor.statements[0]
        self.assertIn("UPDATE xportra.users", statement)
        self.assertEqual(parameters, (SUBJECT_UID, USER_ID))

    def test_set_supabase_uid_conflict_stays_integrity_error(self):
        from psycopg.errors import UniqueViolation

        from tests.unit.test_persistence import FakeCursor, database_with

        cursor = FakeCursor(error=UniqueViolation("duplicate"))
        database, _connection = database_with(cursor)
        with self.assertRaises(PersistenceIntegrityError):
            UserRepository(database).set_supabase_uid(USER_ID, SUBJECT_UID)


if __name__ == "__main__":
    unittest.main()
