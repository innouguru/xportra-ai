"""Focused unit tests for the operator global staff bootstrap CLI.

Covers the production confirmation gate (refusal without or with a
mismatched confirmation before any database use; proceeds only with
an exact match), self-bootstrap refusal, UUID validation, and the
success report through a scripted database double. Live-database
coverage stays in tests/integration by convention.
"""

from __future__ import annotations

import io
import unittest
from contextlib import nullcontext, redirect_stderr, redirect_stdout
from uuid import UUID, uuid4

from xportra.dev.global_staff_bootstrap import main
from xportra.persistence.database import Database, DatabaseSettings

AUTH_REF = "XPA-GSA-INIT-001"
TARGET_ID = UUID("20000000-0000-0000-0000-000000000001")
ACTOR_ID = UUID("20000000-0000-0000-0000-000000000002")
GRANT_ID = UUID("20000000-0000-0000-0000-000000000003")

BASE_ARGS = [
    "--authorization-ref", AUTH_REF,
    "--target-user-id", str(TARGET_ID),
    "--actor-user-id", str(ACTOR_ID),
    "--justification", "initial operator bootstrap",
]

LOCAL_ENV = {"DATABASE_URL": "postgresql://localhost/xportra_test"}
PRODUCTION_ENV = {
    "APP_ENV": "production",
    "DATABASE_URL": "postgresql://localhost/xportra_test",
}


def active_user_row():
    return {"id": TARGET_ID, "status": "active"}


def approved_authorization_row():
    return {
        "id": uuid4(),
        "target_user_id": TARGET_ID,
        "permission": "grant_manage",
        "status": "approved",
    }


def grant_row():
    return {
        "id": GRANT_ID,
        "user_id": TARGET_ID,
        "permission": "grant_manage",
        "status": "active",
        "granted_by": ACTOR_ID,
        "granted_at": "2026-10-28 00:00:00+00",
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

    def execute(self, statement, parameters=None):
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


def success_routes():
    return [
        ("SELECT * FROM xportra.users WHERE id", "one", active_user_row()),
        ("pg_advisory_xact_lock", "one", {"locked": True}),
        (
            "FROM xportra.global_staff_authorizations WHERE authorization_ref",
            "one",
            approved_authorization_row(),
        ),
        ("UPDATE xportra.global_staff_authorizations", "one",
         {"status": "consumed"}),
        ("SELECT 1 FROM xportra.global_staff_grants", "one", None),
        ("INSERT INTO xportra.global_staff_grants", "one", grant_row()),
        ("INSERT INTO xportra.global_staff_audit", "one", {"id": uuid4()}),
    ]


def exploding_database():
    def exploding_factory(*_args, **_kwargs):
        raise AssertionError("database must not be touched")

    return Database(
        DatabaseSettings("postgresql://localhost/x"), exploding_factory
    )


def statements_of(cursor):
    return [statement for statement, _ in cursor.statements]


class ProductionGuardTests(unittest.TestCase):
    def test_production_without_confirmation_refuses_before_database_use(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(BASE_ARGS, PRODUCTION_ENV, exploding_database())
        self.assertEqual(code, 2)
        self.assertIn("production-confirmation", stderr.getvalue())

    def test_production_with_mismatched_confirmation_refuses(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(
                BASE_ARGS + ["--production-confirmation", "XPA-GSA-INIT-002"],
                PRODUCTION_ENV,
                exploding_database(),
            )
        self.assertEqual(code, 2)
        self.assertIn("production-confirmation", stderr.getvalue())

    def test_production_with_blank_confirmation_refuses(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(
                BASE_ARGS + ["--production-confirmation", "   "],
                PRODUCTION_ENV,
                exploding_database(),
            )
        self.assertEqual(code, 2)

    def test_production_with_matching_confirmation_proceeds(self):
        database, cursor = scripted_database(success_routes())
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(
                BASE_ARGS + ["--production-confirmation", AUTH_REF],
                PRODUCTION_ENV,
                database,
            )
        self.assertEqual(code, 0)
        output = buffer.getvalue()
        self.assertIn(str(GRANT_ID), output)
        self.assertIn("grant_manage", output)
        self.assertIn("active", output)
        self.assertNotIn("postgresql://", output)
        self.assertTrue(
            any(
                "INSERT INTO xportra.global_staff_grants" in statement
                for statement in statements_of(cursor)
            )
        )
        self.assertTrue(
            any(
                "INSERT INTO xportra.global_staff_audit" in statement
                for statement in statements_of(cursor)
            )
        )


class EntrypointTests(unittest.TestCase):
    def test_non_production_runs_without_confirmation(self):
        database, cursor = scripted_database(success_routes())
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(BASE_ARGS, LOCAL_ENV, database)
        self.assertEqual(code, 0)
        self.assertIn(str(GRANT_ID), buffer.getvalue())
        self.assertTrue(
            any(
                "INSERT INTO xportra.global_staff_grants" in statement
                for statement in statements_of(cursor)
            )
        )

    def test_self_bootstrap_is_refused_before_database_use(self):
        args = [
            "--authorization-ref", AUTH_REF,
            "--target-user-id", str(ACTOR_ID),
            "--actor-user-id", str(ACTOR_ID),
            "--justification", "self bootstrap attempt",
        ]
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(args, LOCAL_ENV, exploding_database())
        self.assertEqual(code, 2)
        self.assertIn("must differ", stderr.getvalue())

    def test_invalid_target_uuid_is_rejected(self):
        args = [
            "--authorization-ref", AUTH_REF,
            "--target-user-id", "not-a-uuid",
            "--actor-user-id", str(ACTOR_ID),
            "--justification", "invalid target",
        ]
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(args, LOCAL_ENV, exploding_database())
        self.assertEqual(code, 2)
        self.assertIn("--target-user-id must be a UUID", stderr.getvalue())

    def test_invalid_actor_uuid_is_rejected(self):
        args = [
            "--authorization-ref", AUTH_REF,
            "--target-user-id", str(TARGET_ID),
            "--actor-user-id", "not-a-uuid",
            "--justification", "invalid actor",
        ]
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(args, LOCAL_ENV, exploding_database())
        self.assertEqual(code, 2)
        self.assertIn("--actor-user-id must be a UUID", stderr.getvalue())

    def test_missing_database_url_is_refused(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(BASE_ARGS, {}, exploding_database())
        self.assertEqual(code, 2)
        self.assertIn("DATABASE_URL", stderr.getvalue())

    def test_bootstrap_service_failure_reports_error(self):
        routes = [
            ("SELECT * FROM xportra.users WHERE id", "one", active_user_row()),
            ("pg_advisory_xact_lock", "one", {"locked": True}),
            (
                "FROM xportra.global_staff_authorizations WHERE authorization_ref",
                "one",
                None,
            ),
        ]
        database, _cursor = scripted_database(routes)
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = main(BASE_ARGS, LOCAL_ENV, database)
        self.assertEqual(code, 1)
        self.assertIn("cannot bootstrap", stderr.getvalue())


class SslDsnPassthroughTests(unittest.TestCase):
    """The documented production TLS path: verbatim DSN passthrough.

    The deployment doc tells operators to configure TLS entirely inside
    ``DATABASE_URL`` (``sslmode=verify-full`` plus ``sslrootcert``, or
    the libpq ``PGSSLROOTCERT`` variable) because ``Database`` passes
    the DSN verbatim to psycopg/libpq. These tests pin that behavior
    with a capturing connection factory — no real connection, no
    production host, no credentials.
    """

    SSL_DSN = (
        "postgresql://xportra_app@db.example.supabase.co:5432/postgres"
        "?sslmode=verify-full&sslrootcert=C%3A/certs/prod-ca-2021.crt"
    )

    def _run_with_captured_dsn(self, dsn):
        captured = {}
        cursor = ScriptedCursor(success_routes())
        connection = ScriptedConnection(cursor)

        def factory(conninfo, **_kwargs):
            captured["conninfo"] = conninfo
            return connection

        database = Database(DatabaseSettings(dsn), factory)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(
                BASE_ARGS + ["--production-confirmation", AUTH_REF],
                {"APP_ENV": "production", "DATABASE_URL": dsn},
                database,
            )
        return code, captured, buffer.getvalue()

    def test_ssl_parameters_reach_the_connection_factory_verbatim(self):
        code, captured, output = self._run_with_captured_dsn(self.SSL_DSN)
        self.assertEqual(code, 0)
        self.assertEqual(captured["conninfo"], self.SSL_DSN)
        self.assertIn("sslmode=verify-full", captured["conninfo"])
        self.assertIn("sslrootcert=", captured["conninfo"])

    def test_ssl_run_output_contains_no_dsn_or_ssl_material(self):
        code, _captured, output = self._run_with_captured_dsn(self.SSL_DSN)
        self.assertEqual(code, 0)
        self.assertNotIn("postgresql://", output)
        self.assertNotIn("sslmode", output)
        self.assertNotIn("sslrootcert", output)
        self.assertNotIn("xportra_app", output)


if __name__ == "__main__":
    unittest.main()
