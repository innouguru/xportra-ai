from contextlib import nullcontext
import unittest
from uuid import UUID

from xportra.persistence.database import Database, DatabaseSettings
from xportra.persistence.organization_registration import (
    OrganizationRegistrationStore,
)

USER_ID = UUID("11111111-1111-1111-1111-111111111111")
TENANT_ID = UUID("22222222-2222-2222-2222-222222222222")
SUPABASE_UID = UUID("33333333-3333-3333-3333-333333333333")


class FakeCursor:
    def __init__(self, responses):
        self.responses = list(responses)
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, statement, parameters):
        self.statements.append((statement, parameters))

    def fetchone(self):
        if not self.responses:
            raise AssertionError("unexpected fetchone")
        return self.responses.pop(0)


class FakeConnection:
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


def registration_store(responses):
    cursor = FakeCursor(responses)
    connection = FakeConnection(cursor)
    database = Database(
        DatabaseSettings("postgresql://registration-test"),
        lambda *_args, **_kwargs: connection,
    )
    return OrganizationRegistrationStore(database), cursor


class OrganizationRegistrationPersistenceTests(unittest.TestCase):
    def test_provision_creates_tenant_user_mapping_and_owner_atomically(self):
        store, cursor = registration_store(
            [
                None,
                {"id": USER_ID},
                {
                    "id": TENANT_ID,
                    "slug": "acme-1234",
                    "legal_name": "Acme",
                },
                {"role": "owner", "status": "active"},
            ]
        )

        result = store.provision(
            supabase_uid=SUPABASE_UID,
            email="owner@example.test",
            display_name="Owner",
            legal_name="Acme",
            slug="acme-1234",
            organization_type="exporter",
            country_code="NG",
            region="Lagos",
            role="owner",
        )

        self.assertEqual(result.status, "created")
        self.assertEqual(result.tenant_id, TENANT_ID)
        self.assertEqual(result.tenant_slug, "acme-1234")
        self.assertEqual(result.tenant_name, "Acme")
        self.assertEqual(result.user_id, USER_ID)
        self.assertEqual(result.role, "owner")
        self.assertEqual(result.membership_status, "active")
        self.assertEqual(len(cursor.statements), 4)
        self.assertEqual(
            cursor.statements[1][1],
            (SUPABASE_UID, "Owner", "owner@example.test"),
        )
        self.assertEqual(
            cursor.statements[2][1],
            ("Acme", "acme-1234", "exporter", "NG", "Lagos"),
        )
        self.assertEqual(
            cursor.statements[3][1], (TENANT_ID, USER_ID, "owner")
        )
        self.assertIn("FOR UPDATE OF u", cursor.statements[0][0])
        self.assertIn("ON CONFLICT DO NOTHING", cursor.statements[1][0])

    def test_existing_active_member_is_rejected_before_any_write(self):
        store, cursor = registration_store([{"tenant_id": TENANT_ID}])

        result = store.provision(
            supabase_uid=SUPABASE_UID,
            email="owner@example.test",
            display_name="Owner",
            legal_name="Acme",
            slug="acme-1234",
        )

        self.assertEqual(result.status, "already_member")
        self.assertEqual(len(cursor.statements), 1)

    def test_email_owned_by_another_identity_is_reported_as_conflict(self):
        store, cursor = registration_store([None, None, None])

        result = store.provision(
            supabase_uid=SUPABASE_UID,
            email="owner@example.test",
            display_name="Owner",
            legal_name="Acme",
            slug="acme-1234",
        )

        self.assertEqual(result.status, "identity_conflict")
        self.assertEqual(len(cursor.statements), 3)
        self.assertIn("WHERE supabase_uid = %s", cursor.statements[2][0])
        self.assertIn("FOR UPDATE", cursor.statements[2][0])

    def test_concurrent_registration_rechecks_membership_after_user_lock(self):
        store, cursor = registration_store(
            [
                None,
                None,
                {"id": USER_ID},
                {"tenant_id": TENANT_ID},
            ]
        )

        result = store.provision(
            supabase_uid=SUPABASE_UID,
            email="owner@example.test",
            display_name="Owner",
            legal_name="Acme",
            slug="acme-1234",
        )

        self.assertEqual(result.status, "already_member")
        self.assertEqual(len(cursor.statements), 4)
        self.assertIn("FOR UPDATE", cursor.statements[2][0])
        self.assertIn("FOR UPDATE OF u", cursor.statements[3][0])


if __name__ == "__main__":
    unittest.main()
