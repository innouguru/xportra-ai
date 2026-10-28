"""Focused database-backed integration tests for global staff bootstrap.

These tests require a live PostgreSQL database (``DATABASE_URL``) with
migration ``015_global_staff_grants.sql`` applied. They are skipped when
``DATABASE_URL`` is not configured and never connect to production data.

These tests exercise the bootstrap path as the dedicated
``xportra_app`` runtime role. Because the append-only audit trigger on
``xportra.global_staff_audit`` blocks UPDATE and DELETE for non-owner
roles, each test uses completely unique fixture identities (emails,
supabase UUIDs, internal user IDs) so rows never conflict across tests.
Only deletable rows (grants, authorizations, memberships) are cleaned up
between tests; users and tenants are left in place with unique identities
that do not conflict.
"""

from __future__ import annotations

import os
import unittest
from uuid import UUID, uuid4

from xportra.application.errors import (
    ApplicationAuthorizationError,
    ApplicationValidationError,
)
from xportra.application.global_staff import (
    GRANT_MANAGE,
    GlobalStaffGrantService,
)
from xportra.persistence.database import Database, DatabaseSettings
from xportra.persistence.repositories import (
    GlobalStaffAuditRepository,
    GlobalStaffAuthorizationRepository,
    GlobalStaffGrantRepository,
    UserRepository,
    UserTenantMembershipRepository,
)
from xportra.persistence.tenant import TenantContext


class FailingAuditRepository(GlobalStaffAuditRepository):
    """Audit repository whose insert always raises, to test rollback."""

    def insert_in_transaction(
        self,
        connection,
        event_type,
        actor_user_id,
        target_user_id,
        permission,
        reason,
        authorization_ref=None,
    ):
        raise RuntimeError("simulated audit insert failure")


class GlobalStaffBootstrapIntegrationTests(unittest.TestCase):
    database = None

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DATABASE_URL", "").strip():
            raise unittest.SkipTest("DATABASE_URL is not configured")
        cls.database = Database(DatabaseSettings.from_environment())
        cls._verify_migration_015()
        # Create a shared fixture tenant (unique slug, idempotent).
        cls.tenant_id = UUID("99999999-0000-0000-0000-000000000099")
        with cls.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO xportra.tenants (id, legal_name, slug, status) "
                    "VALUES (%s, %s, %s, 'active') ON CONFLICT (id) DO NOTHING",
                    (cls.tenant_id, "GSB Focus Tenant", "gsb-focus-tenant"),
                )

    @classmethod
    def tearDownClass(cls):
        cls._cleanup_grants_and_authorizations()

    @classmethod
    def _verify_migration_015(cls):
        with cls.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'xportra'
                      AND table_name IN ('global_staff_grants', 'global_staff_audit')
                    """
                )
                tables = {row["table_name"] for row in cursor.fetchall()}
                if tables != {"global_staff_grants", "global_staff_audit"}:
                    raise RuntimeError(
                        "migrations/015_global_staff_grants.sql must be applied "
                        "before running global staff integration tests"
                    )

    @classmethod
    def _cleanup_grants_and_authorizations(cls):
        """Remove grant and authorization rows created by these tests.

        Users and tenants are not deleted: ``global_staff_audit`` has
        RESTRICT foreign keys on actor/target user IDs and an append-only
        trigger blocking DELETE, so users referenced by audit rows cannot
        be removed by ``xportra_app``. Unique per-test identities prevent
        cross-test conflicts.
        """
        with cls.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM xportra.global_staff_grants
                    WHERE user_id IN (
                        SELECT id FROM xportra.users
                        WHERE email LIKE 'gsb-focus-%@xportra.test'
                    )
                    """
                )
                cursor.execute(
                    """
                    DELETE FROM xportra.global_staff_authorizations
                    WHERE target_user_id IN (
                        SELECT id FROM xportra.users
                        WHERE email LIKE 'gsb-focus-%@xportra.test'
                    )
                       OR authorizer_user_id IN (
                        SELECT id FROM xportra.users
                        WHERE email LIKE 'gsb-focus-%@xportra.test'
                    )
                       OR verifier_user_id IN (
                        SELECT id FROM xportra.users
                        WHERE email LIKE 'gsb-focus-%@xportra.test'
                    )
                    """
                )
                cursor.execute(
                    """
                    DELETE FROM xportra.user_tenant_memberships
                    WHERE user_id IN (
                        SELECT id FROM xportra.users
                        WHERE email LIKE 'gsb-focus-%@xportra.test'
                    )
                    """
                )

    def setUp(self):
        user_repository = UserRepository(self.database)
        membership_repository = UserTenantMembershipRepository(self.database)

        # Unique identities per test to avoid cross-test conflicts.
        actor_email = f"gsb-focus-actor-{uuid4().hex[:8]}@xportra.test"
        target_email = f"gsb-focus-target-{uuid4().hex[:8]}@xportra.test"
        actor_uid = uuid4()
        target_uid = uuid4()

        self.actor = user_repository.create(
            "GSB Focus Actor", actor_email, "active", actor_uid,
        )["id"]
        self.target = user_repository.create(
            "GSB Focus Target", target_email, "active", target_uid,
        )["id"]

        context = TenantContext(self.tenant_id)
        membership_repository.add(context, self.actor, "owner")
        membership_repository.add(context, self.target, "owner")

        # Create an approved, unconsumed authorization record for the target.
        self.authorization_ref = f"gsb-focus-auth-{uuid4().hex[:8]}"
        self.authorization_repo = GlobalStaffAuthorizationRepository(
            self.database
        )
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO xportra.global_staff_authorizations
                    (id, target_user_id, permission, authorizer_user_id, verifier_user_id,
                     authorization_ref, verification_method, justification, status,
                     approved_at, verified_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
                    """,
                    (
                        uuid4(),
                        self.target,
                        GRANT_MANAGE,
                        self.actor,
                        self.actor,
                        self.authorization_ref,
                        "documented operational procedure",
                        "initial operator authorization",
                        "approved",
                    ),
                )
        self.service = GlobalStaffGrantService(self.database)

    def tearDown(self):
        self._cleanup_grants_and_authorizations()

    # ---- 1. Bootstrap succeeds: consumes authorization, creates grant + audit ----
    def test_bootstrap_consumes_authorization_creates_grant_and_audit(self):
        grant_row = self.service.bootstrap(
            self.actor, self.target,
            justification="initial operator bootstrap",
            authorization_ref=self.authorization_ref,
        )
        self.assertEqual(grant_row["user_id"], self.target)
        self.assertEqual(grant_row["permission"], GRANT_MANAGE)
        self.assertEqual(grant_row["status"], "active")

        # Authorization consumed
        auth_row = self.authorization_repo.get_by_ref(self.authorization_ref)
        self.assertIsNotNone(auth_row)
        self.assertEqual(auth_row["status"], "consumed")
        self.assertIsNotNone(auth_row["consumed_at"])
        self.assertEqual(auth_row["consumed_by"], self.actor)

        # Audit event created with authorization_ref linkage
        audit = GlobalStaffAuditRepository(self.database)
        events = audit.list_for_target(self.target)
        bootstrap_events = [e for e in events if e["event_type"] == "bootstrap"]
        self.assertEqual(len(bootstrap_events), 1)
        self.assertEqual(bootstrap_events[0]["actor_user_id"], self.actor)
        self.assertEqual(bootstrap_events[0]["target_user_id"], self.target)
        self.assertEqual(bootstrap_events[0]["permission"], GRANT_MANAGE)
        self.assertEqual(
            bootstrap_events[0]["authorization_ref"], self.authorization_ref
        )

    # ---- 2. Invalid authorization ref is rejected ----
    def test_bootstrap_rejects_invalid_authorization_ref(self):
        with self.assertRaises(ApplicationValidationError):
            self.service.bootstrap(
                self.actor, self.target,
                justification="invalid ref",
                authorization_ref="gsb-focus-does-not-exist",
            )
        # No grant created
        grants = GlobalStaffGrantRepository(self.database)
        self.assertIsNone(grants.get_active(self.target, GRANT_MANAGE))

    # ---- 3. Mismatched target is rejected ----
    def test_bootstrap_rejects_mismatched_target(self):
        # Create a second target user so _require_active_user passes,
        # then verify the authorization ref (bound to self.target) is rejected.
        other_user = UserRepository(self.database).create(
            "GSB Other", f"gsb-focus-other-{uuid4().hex[:8]}@xportra.test",
            "active", uuid4(),
        )["id"]
        with self.assertRaises(ApplicationValidationError):
            self.service.bootstrap(
                self.actor, other_user,
                justification="mismatched target",
                authorization_ref=self.authorization_ref,
            )

    # ---- 4. Already-consumed authorization is rejected ----
    def test_bootstrap_rejects_already_consumed_authorization(self):
        self.service.bootstrap(
            self.actor, self.target,
            justification="first bootstrap",
            authorization_ref=self.authorization_ref,
        )
        # Second bootstrap with same consumed ref must fail
        with self.assertRaises(ApplicationValidationError):
            self.service.bootstrap(
                self.actor, self.target,
                justification="second bootstrap",
                authorization_ref=self.authorization_ref,
            )

    # ---- 5. Self-bootstrap is denied ----
    def test_bootstrap_denies_self_bootstrap(self):
        with self.assertRaises(ApplicationAuthorizationError):
            self.service.bootstrap(
                self.actor, self.actor,
                justification="self-bootstrap attempt",
                authorization_ref=self.authorization_ref,
            )

    # ---- 6. Audit insert failure rolls back grant mutation ----
    def test_bootstrap_audit_failure_rolls_back_grant(self):
        failing_audit = FailingAuditRepository(self.database)
        service = GlobalStaffGrantService(
            self.database,
            grants=GlobalStaffGrantRepository(self.database),
            audit=failing_audit,
            authorizations=self.authorization_repo,
            users=UserRepository(self.database),
        )
        grants_before = GlobalStaffGrantRepository(self.database).get(
            self.target, GRANT_MANAGE
        )
        with self.assertRaises(RuntimeError):
            service.bootstrap(
                self.actor, self.target,
                justification="rollback test",
                authorization_ref=self.authorization_ref,
            )
        # Authorization was consumed before audit failed, so the transaction
        # rolled back — consumption is part of the same transaction. The auth
        # should still be approved (not consumed).
        auth_row = self.authorization_repo.get_by_ref(self.authorization_ref)
        self.assertEqual(auth_row["status"], "approved")
        self.assertIsNone(auth_row["consumed_at"])
        # No grant created
        grants_after = GlobalStaffGrantRepository(self.database).get(
            self.target, GRANT_MANAGE
        )
        self.assertEqual(grants_before is None, grants_after is None)

    # ---- 7. Inactive target is rejected ----
    def test_bootstrap_requires_active_target(self):
        inactive_target = UserRepository(self.database).create(
            "GSB Inactive", f"gsb-focus-inactive-{uuid4().hex[:8]}@xportra.test",
            "disabled", uuid4(),
        )["id"]
        with self.assertRaises(ApplicationValidationError):
            self.service.bootstrap(
                self.actor, inactive_target,
                justification="inactive target",
                authorization_ref=self.authorization_ref,
            )


if __name__ == "__main__":
    unittest.main()
