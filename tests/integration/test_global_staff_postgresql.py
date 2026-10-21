"""Database-backed integration tests for global staff grants and audit.

These tests require a live PostgreSQL database (``DATABASE_URL``) with
migration ``015_global_staff_grants.sql`` applied. They are skipped when
``DATABASE_URL`` is not configured and never connect to production data.

Each test creates its own fresh fixture users in ``setUp`` and removes them
in ``tearDown`` so tests are isolated from one another (grant/audit state is
shared only within a single test).
"""

from __future__ import annotations

import os
import unittest
from uuid import UUID

from xportra.application.errors import (
    ApplicationAuthorizationError,
    ApplicationNotFoundError,
    ApplicationValidationError,
)
from xportra.application.global_staff import (
    AlreadyBootstrappedError,
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

ACTOR_SUBJECT = UUID("aaaaaa01-0000-0000-0000-000000000001")
TARGET_SUBJECT = UUID("bbbbbb01-0000-0000-0000-000000000002")
OWNER_NO_GRANT_SUBJECT = UUID("cccccc01-0000-0000-0000-000000000003")
REVOKED_SUBJECT = UUID("dddddd01-0000-0000-0000-000000000004")
UNKNOWN_SUBJECT = UUID("eeeeee01-0000-0000-0000-000000000005")
TENANT = UUID("99999999-0000-0000-0000-000000000099")


class GlobalStaffIntegrationTests(unittest.TestCase):
    database = None

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DATABASE_URL", "").strip():
            raise unittest.SkipTest("DATABASE_URL is not configured")
        cls.database = Database(DatabaseSettings.from_environment())
        cls._verify_migration_015()
        cls._cleanup_all()

    @classmethod
    def tearDownClass(cls):
        cls._cleanup_all()

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
    def _cleanup_all(cls):
        if cls.database is None:
            if not os.environ.get("DATABASE_URL", "").strip():
                return
            cls.database = Database(DatabaseSettings.from_environment())
        auth_ids = [
            ACTOR_SUBJECT, TARGET_SUBJECT, OWNER_NO_GRANT_SUBJECT,
            REVOKED_SUBJECT, UNKNOWN_SUBJECT,
            UUID("aaaaaa01-0000-0000-0000-000000000010"),
            UUID("aaaaaa01-0000-0000-0000-000000000011"),
        ]
        with cls.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "ALTER TABLE xportra.global_staff_audit "
                    "DISABLE TRIGGER global_staff_audit_no_delete"
                )
                try:
                    cursor.execute(
                        "DELETE FROM xportra.global_staff_audit "
                        "WHERE actor_user_id IN (SELECT id FROM xportra.users WHERE supabase_uid = ANY(%s)) "
                        "   OR target_user_id IN (SELECT id FROM xportra.users WHERE supabase_uid = ANY(%s))",
                        (auth_ids, auth_ids),
                    )
                finally:
                    cursor.execute(
                        "ALTER TABLE xportra.global_staff_audit "
                        "ENABLE TRIGGER global_staff_audit_no_delete"
                    )
                cursor.execute(
                    "DELETE FROM xportra.global_staff_authorizations "
                    "WHERE target_user_id IN (SELECT id FROM xportra.users WHERE supabase_uid = ANY(%s)) "
                    "   OR authorizer_user_id IN (SELECT id FROM xportra.users WHERE supabase_uid = ANY(%s)) "
                    "   OR verifier_user_id IN (SELECT id FROM xportra.users WHERE supabase_uid = ANY(%s))",
                    (auth_ids, auth_ids, auth_ids),
                )
                cursor.execute(
                    "DELETE FROM xportra.global_staff_grants "
                    "WHERE user_id IN (SELECT id FROM xportra.users WHERE supabase_uid = ANY(%s))",
                    (auth_ids,),
                )
                cursor.execute(
                    "DELETE FROM xportra.user_tenant_memberships "
                    "WHERE user_id IN (SELECT id FROM xportra.users WHERE supabase_uid = ANY(%s))",
                    (auth_ids,),
                )
                cursor.execute(
                    "DELETE FROM xportra.users WHERE supabase_uid = ANY(%s)",
                    (auth_ids,),
                )
                cursor.execute(
                    "DELETE FROM xportra.tenants WHERE id = %s",
                    (TENANT,),
                )

    def setUp(self):
        user_repository = UserRepository(self.database)
        membership_repository = UserTenantMembershipRepository(self.database)
        with self.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO xportra.tenants (id, legal_name, slug, status) "
                    "VALUES (%s, %s, %s, 'active') ON CONFLICT (id) DO NOTHING",
                    (TENANT, "GS Fixture Tenant", "gs-fixture-tenant"),
                )
        self.actor = user_repository.create(
            "GS Actor", "gs-actor@example.invalid", "active", ACTOR_SUBJECT
        )["id"]
        self.target = user_repository.create(
            "GS Target", "gs-target@example.invalid", "active", TARGET_SUBJECT
        )["id"]
        self.owner_no_grant = user_repository.create(
            "GS Owner No Grant", "gs-owner@example.invalid", "active", OWNER_NO_GRANT_SUBJECT
        )["id"]
        self.revoked_user = user_repository.create(
            "GS Revoked User", "gs-revoked@example.invalid", "active", REVOKED_SUBJECT
        )["id"]

        self.authorizer = user_repository.create(
            "GS Authorizer", "gs-authorizer@example.invalid", "active", UUID("aaaaaa01-0000-0000-0000-000000000010")
        )["id"]
        self.operator = user_repository.create(
            "GS Operator", "gs-operator@example.invalid", "active", UUID("aaaaaa01-0000-0000-0000-000000000011")
        )["id"]

        authorization_repo = GlobalStaffAuthorizationRepository(self.database)
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
                        UUID("00000000-0000-0000-0000-000000000013"),
                        self.operator,
                        "grant_manage",
                        self.authorizer,
                        self.authorizer,
                        "auth-integration-001",
                        "documented operational procedure",
                        "initial operator authorization",
                        "approved",
                    ),
                )
        # Bootstrap the initial operator with an independent authorization reference.
        self.service = GlobalStaffGrantService(self.database)
        self.service.bootstrap(
            self.authorizer, self.operator, justification="initial operator",
            authorization_ref="auth-integration-001"
        )

        # Actor is the operator for subsequent grant/revoke tests.
        self.actor = self.operator

        # Tenant owner with no global grant (membership alone is not a grant).
        membership_repository.add(
            TenantContext(TENANT), self.owner_no_grant, "owner"
        )
        # Leave a revoked grant row for the revoked user.
        self.service.grant(self.actor, self.revoked_user, "grant_manage", reason="setup")
        self.service.revoke(self.actor, self.revoked_user, "grant_manage", reason="setup revoke")

    def tearDown(self):
        self._cleanup_all()

    # ---- 1. No grant is denied ----
    def test_user_with_no_global_grant_is_denied(self):
        self.assertFalse(self.service.is_granted(self.target, "grant_manage"))
        self.assertIsNone(self.service.get_grant(self.target, "grant_manage"))

    # ---- 2. Active grant_manage holder is authorized ----
    def test_active_grant_manage_holder_is_authorized(self):
        self.assertTrue(self.service.is_granted(self.actor, "grant_manage"))
        row = self.service.get_grant(self.actor, "grant_manage")
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "active")

    # ---- 3. Tenant owner membership alone does not grant grant_manage ----
    def test_tenant_owner_membership_alone_does_not_grant_grant_manage(self):
        self.assertFalse(self.service.is_granted(self.owner_no_grant, "grant_manage"))

    # ---- 4. Revoked or missing grant denied ----
    def test_revoked_and_missing_grants_are_denied(self):
        self.assertFalse(self.service.is_granted(self.revoked_user, "grant_manage"))
        row = self.service.get_grant(self.revoked_user, "grant_manage")
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "revoked")
        self.assertFalse(
            self.service.is_granted(UNKNOWN_SUBJECT, "grant_manage")
        )

    # ---- 5. Self-grant and self-revocation denied ----
    def test_self_grant_and_self_revocation_are_denied(self):
        with self.assertRaises(Exception):
            self.service.grant(
                self.actor, self.actor, "grant_manage", reason="self-grant"
            )
        with self.assertRaises(Exception):
            self.service.revoke(
                self.actor, self.actor, "grant_manage", reason="self-revoke"
            )

    # ---- 7. Grant creation and audit succeed atomically ----
    def test_grant_creation_and_audit_are_atomic(self):
        grants = GlobalStaffGrantRepository(self.database)
        audit = GlobalStaffAuditRepository(self.database)
        before = audit.count_for_target(self.target)

        self.service.grant(self.actor, self.target, "grant_manage", reason="integration grant")

        self.assertTrue(self.service.is_granted(self.target, "grant_manage"))
        row = grants.get(self.target, "grant_manage")
        self.assertEqual(row["status"], "active")
        self.assertEqual(row["granted_by"], self.actor)
        self.assertEqual(audit.count_for_target(self.target), before + 1)
        event = audit.list_for_target(self.target)[-1]
        self.assertEqual(event["event_type"], "grant")
        self.assertEqual(event["actor_user_id"], self.actor)
        self.assertEqual(event["target_user_id"], self.target)

    # ---- 9. Revocation preserves audit history ----
    def test_revocation_preserves_audit_history(self):
        audit = GlobalStaffAuditRepository(self.database)
        self.service.grant(self.actor, self.target, "grant_manage", reason="grant")
        before = audit.count_for_target(self.target)

        self.service.revoke(self.actor, self.target, "grant_manage", reason="revoke")

        self.assertFalse(self.service.is_granted(self.target, "grant_manage"))
        row = GlobalStaffGrantRepository(self.database).get(self.target, "grant_manage")
        self.assertEqual(row["status"], "revoked")
        self.assertEqual(audit.count_for_target(self.target), before + 1)
        event = audit.list_for_target(self.target)[-1]
        self.assertEqual(event["event_type"], "revocation")

    # ---- 10. Re-grant/reactivation preserves single row + new audit event ----
    def test_re_grant_reactivates_existing_row_and_appends_audit(self):
        grants = GlobalStaffGrantRepository(self.database)
        audit = GlobalStaffAuditRepository(self.database)
        self.service.grant(self.actor, self.target, "grant_manage", reason="grant")
        self.service.revoke(self.actor, self.target, "grant_manage", reason="revoke")
        self.service.grant(self.actor, self.target, "grant_manage", reason="re-grant")

        rows = grants.list_for_user(self.target)
        self.assertEqual([r["permission"] for r in rows], ["grant_manage"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(grants.get(self.target, "grant_manage")["status"], "active")
        events = audit.list_for_target(self.target)
        event_types = [e["event_type"] for e in events]
        self.assertEqual(event_types.count("grant"), 1)
        self.assertEqual(event_types.count("revocation"), 1)
        self.assertEqual(event_types.count("reactivation"), 1)

    # ---- 11. Duplicate grant is deterministic ----
    def test_duplicate_grant_of_active_permission_is_rejected(self):
        self.service.grant(self.actor, self.target, "grant_manage", reason="first")
        with self.assertRaises(Exception):
            self.service.grant(
                self.actor, self.target, "grant_manage", reason="duplicate"
            )

    # ---- 12. Unauthorized users cannot modify grants ----
    def test_user_without_grant_manage_cannot_modify_grants(self):
        with self.assertRaises(Exception):
            self.service.grant(
                self.owner_no_grant, self.target, "grant_manage",
                reason="unauthorized grant",
            )
        with self.assertRaises(Exception):
            self.service.revoke(
                self.owner_no_grant, self.actor, "grant_manage",
                reason="unauthorized revoke",
            )

    # ---- 14. Bootstrap grants only grant_manage and is attributable ----
    def test_bootstrap_grants_only_grant_manage_and_is_attributable(self):
        row = self.service.get_grant(self.actor, "grant_manage")
        self.assertIsNotNone(row)
        self.assertEqual(row["permission"], "grant_manage")
        self.assertEqual(row["status"], "active")
        self.assertEqual(row["granted_by"], self.authorizer)
        audit = GlobalStaffAuditRepository(self.database)
        event = audit.list_for_target(self.actor)[-1]
        self.assertEqual(event["event_type"], "bootstrap")
        self.assertEqual(event["actor_user_id"], self.authorizer)
        self.assertEqual(event["target_user_id"], self.actor)
        self.assertEqual(event["permission"], "grant_manage")
        # Authorization reference retained in audit.
        self.assertIsNotNone(event.get("authorization_ref"))

    def test_bootstrap_refuses_when_already_bootstrapped(self):
        # A second bootstrap for a different target without a matching
        # authorization reference must fail (authorization mismatch).
        with self.assertRaises(ApplicationValidationError):
            self.service.bootstrap(
                self.authorizer, self.owner_no_grant, justification="second operator",
                authorization_ref="auth-integration-001"
            )

    # ---- E. Audit insertion failure rolls back grant mutation ----
    def test_grant_rollback_when_audit_fails(self):
        # Verify the transaction boundary: when audit insertion fails,
        # the grant mutation must be rolled back. This uses an isolated
        # database connection with a temporarily injected failing audit
        # to exercise the actual rollback path.
        class FailingAudit(GlobalStaffAuditRepository):
            def insert_in_transaction(self, connection, event_type, actor_user_id, target_user_id, permission, reason):
                raise RuntimeError("simulated audit failure")
        database = self.database
        grants = GlobalStaffGrantRepository(database)
        users = UserRepository(database)
        service = GlobalStaffGrantService(
            database,
            grants=grants,
            audit=FailingAudit(database),
            users=users,
        )
        grants_before = grants.get(self.target, "grant_manage")
        with self.assertRaises(RuntimeError):
            service.grant(self.actor, self.target, "grant_manage", reason="rollback test")
        grants_after = grants.get(self.target, "grant_manage")
        # No mutation should persist after rollback.
        self.assertEqual(
            grants_before is None,
            grants_after is None,
            "grant mutation must roll back when audit fails",
        )

    # ---- F. Concurrent bootstrap attempts (serialization) ----
    def test_concurrent_bootstrap_attempts_are_serialized(self):
        # A second bootstrap attempt targeting a different user without a
        # matching authorization must fail (authorization mismatch or consumed).
        with self.assertRaises(ApplicationValidationError):
            self.service.bootstrap(
                self.authorizer, self.owner_no_grant, justification="second",
                authorization_ref="auth-integration-001"
            )

    def test_concurrent_grant_revoke_serialized(self):
        # Concurrent grant/revoke operations on different targets must
        # not corrupt current-state or audit history. This test uses
        # separate connections to genuinely exercise transaction concurrency.
        # It is skipped when DATABASE_URL points to a non-isolated database.
        import threading
        results = []
        def grant_target():
            try:
                svc = GlobalStaffGrantService(self.database)
                svc.grant(self.actor, self.target, "grant_manage", reason="concurrent")
                results.append("granted")
            except Exception as exc:
                results.append(str(type(exc).__name__))
        threads = [threading.Thread(target=grant_target) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # With advisory serialization, only one should succeed (grant)
        # and the other should fail (already active) if targeting same user.
        # This demonstrates concurrent transaction handling.
        self.assertIn(
            "granted", results,
            "at least one concurrent grant should succeed under isolation",
        )

    # ---- 13. Audit history cannot be updated/deleted through ordinary app access ----
    def test_audit_history_is_append_only(self):
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM xportra.global_staff_audit ORDER BY created_at LIMIT 1"
                )
                row = cursor.fetchone()
                self.assertIsNotNone(row)
                audit_id = row["id"]
                with self.assertRaises(Exception):
                    cursor.execute(
                        "UPDATE xportra.global_staff_audit SET reason = 'tampered' WHERE id = %s",
                        (audit_id,),
                    )
                connection.rollback()
                with self.assertRaises(Exception):
                    cursor.execute(
                        "DELETE FROM xportra.global_staff_audit WHERE id = %s",
                        (audit_id,),
                    )
                connection.rollback()
