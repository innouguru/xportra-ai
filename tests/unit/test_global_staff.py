"""Unit tests for the global staff grant and audit service (no database).

These tests exercise the service's validation and orchestration logic
using fakes, so they run without PostgreSQL. Database-backed grant and
audit behaviour is covered by
``tests/integration/test_global_staff_postgresql.py`` (skipped when
``DATABASE_URL`` is not configured).
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest import TestCase
from uuid import UUID

from xportra.application.errors import (
    ApplicationAuthorizationError,
    ApplicationNotFoundError,
    ApplicationValidationError,
)
from xportra.application.global_staff import (
    AlreadyBootstrappedError,
    GRANT_MANAGE,
    GlobalStaffGrantService,
)
from xportra.persistence.database import Database

ACTOR = UUID("aaaaaaaa-0000-0000-0000-000000000001")
TARGET = UUID("bbbbbbbb-0000-0000-0000-000000000002")
OTHER = UUID("cccccccc-0000-0000-0000-000000000003")


class FakeDatabase(Database):
    """In-memory transaction double that records commit/rollback."""

    def __init__(self) -> None:
        # Database.__init__ requires settings; we only use the context
        # manager interface here.
        super().__init__(  # type: ignore[arg-type]
            object(),  # type: ignore[arg-type]
            connection_factory=object(),  # type: ignore[arg-type]
        )
        self.committed = False
        self.rolled_back = False

    @contextmanager
    def transaction(self):  # type: ignore[override]
        try:
            yield object()
            self.committed = True
        except Exception:
            self.rolled_back = True
            raise


class FakeGrantRow(dict):
    def __init__(self, **values):
        super().__init__(values)


class FakeGrants:
    def __init__(self) -> None:
        self.active: dict[tuple[UUID, str], FakeGrantRow] = {}
        self.revoked: dict[tuple[UUID, str], FakeGrantRow] = {}
        self.insert_calls = 0
        self.reactivate_calls = 0
        self.revoke_calls = 0
        self.lock_calls = 0
        self.exists_any_calls = 0
        self.fail_insert = False

    def get_active(self, user_id: UUID, permission: str):
        return self.active.get((user_id, permission))

    def get(self, user_id: UUID, permission: str):
        return self.active.get((user_id, permission)) or self.revoked.get(
            (user_id, permission)
        )

    def lock_in_transaction(self, connection, user_id: UUID, permission: str):
        self.lock_calls += 1
        return self.active.get((user_id, permission)) or self.revoked.get(
            (user_id, permission)
        )

    def insert_in_transaction(self, connection, user_id, permission, granted_by, reason):
        self.insert_calls += 1
        if self.fail_insert:
            raise RuntimeError("simulated audit/grant insert failure")
        row = FakeGrantRow(
            id=UUID("00000000-0000-0000-0000-000000000009"),
            user_id=user_id,
            permission=permission,
            status="active",
            granted_by=granted_by,
        )
        self.active[(user_id, permission)] = row
        return row

    def reactivate_in_transaction(self, connection, user_id, permission, granted_by, reason):
        self.reactivate_calls += 1
        row = FakeGrantRow(
            id=UUID("00000000-0000-0000-0000-000000000008"),
            user_id=user_id,
            permission=permission,
            status="active",
            granted_by=granted_by,
        )
        self.active[(user_id, permission)] = row
        self.revoked.pop((user_id, permission), None)
        return row

    def revoke_in_transaction(self, connection, user_id, permission, revoked_by, reason):
        self.revoke_calls += 1
        row = FakeGrantRow(
            id=UUID("00000000-0000-0000-0000-000000000007"),
            user_id=user_id,
            permission=permission,
            status="revoked",
            revoked_by=revoked_by,
        )
        self.revoked[(user_id, permission)] = row
        self.active.pop((user_id, permission), None)
        return row

    def exists_any_in_transaction(self, connection, permission: str) -> bool:
        self.exists_any_calls += 1
        return bool(self.active or self.revoked)


class FakeAuthorizations:
    def __init__(self) -> None:
        self.authorizations = {}
        self.consumed = set()

    def get_by_ref(self, authorization_ref: str):
        auth = self.authorizations.get(authorization_ref)
        if auth is None:
            return None
        # Return as a dict mimicking repository row
        return {
            "id": auth.get("id", UUID("00000000-0000-0000-0000-000000000012")),
            "target_user_id": auth.get("target_user_id"),
            "permission": auth.get("permission"),
            "status": auth.get("status", "approved"),
        }

    def consume_in_transaction(self, connection, authorization_id, consumed_by):
        self.consumed.add(str(authorization_id))
        return {"id": authorization_id, "status": "consumed"}


class FakeAudit:
    def __init__(self) -> None:
        self.events = []
        self.insert_calls = 0
        self.fail_insert = False

    def insert_in_transaction(
        self, connection, event_type, actor_user_id, target_user_id, permission, reason, authorization_ref=None
    ):
        self.insert_calls += 1
        if self.fail_insert:
            raise RuntimeError("simulated audit insert failure")
        event = FakeGrantRow(
            event_type=event_type,
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            permission=permission,
            reason=reason,
            authorization_ref=authorization_ref,
        )
        self.events.append(event)
        return event


class FakeUsers:
    def __init__(self, active=None) -> None:
        self.active = set(active or ())

    def get(self, user_id: UUID):
        if user_id not in self.active:
            return None
        return {"id": user_id, "status": "active"}


class ServiceFactory:
    def __init__(self, *, fail_audit=False, fail_grant=False, active=None) -> None:
        self.database = FakeDatabase()
        self.grants = FakeGrants()
        self.grants.fail_insert = fail_grant
        self.audit = FakeAudit()
        self.audit.fail_insert = fail_audit
        self.users = FakeUsers(active)
        self.authorizations = FakeAuthorizations()

    def service(self) -> GlobalStaffGrantService:
        # Pre-authorize bootstrap for the target so tests can call bootstrap.
        self.authorizations.authorizations["auth-001"] = {
            "id": UUID("00000000-0000-0000-0000-000000000012"),
            "target_user_id": TARGET,
            "permission": GRANT_MANAGE,
            "status": "approved",
        }
        return GlobalStaffGrantService(
            self.database,
            grants=self.grants,
            audit=self.audit,
            authorizations=self.authorizations,
            users=self.users,
        )


class GlobalStaffPermissionTests(TestCase):
    def test_global_staff_permissions(self):
        from xportra.application.global_staff import (
            GRANT_MANAGE,
            STAGE_A_VERIFY,
            STAGE_B_APPROVE,
            _GLOBAL_STAFF_PERMISSIONS,
        )

        self.assertEqual(
            _GLOBAL_STAFF_PERMISSIONS,
            frozenset({GRANT_MANAGE, STAGE_A_VERIFY, STAGE_B_APPROVE}),
        )
        self.assertEqual(GRANT_MANAGE, "grant_manage")
        self.assertEqual(STAGE_A_VERIFY, "stage_a_verify")
        self.assertEqual(STAGE_B_APPROVE, "stage_b_approve")

    def test_invalid_permission_is_rejected(self):
        factory = ServiceFactory(active={ACTOR, TARGET})
        service = factory.service()
        with self.assertRaises(ApplicationValidationError):
            service._require_valid_permission("source_admin")
        # stage_b_approve was approved by migration 028; it must be
        # accepted as a defined permission (not an invalid one).
        self.assertIsNone(
            service._require_valid_permission("stage_b_approve")
        )
        with self.assertRaises(ApplicationValidationError):
            service._require_valid_permission("anything_else")

    def test_self_grant_of_grant_manage_is_denied(self):
        factory = ServiceFactory(active={ACTOR, TARGET})
        service = factory.service()
        with self.assertRaises(ApplicationAuthorizationError) as raised:
            service._deny_self_managed(ACTOR, ACTOR, GRANT_MANAGE, "grant")
        self.assertIn("self-grant", str(raised.exception))

    def test_self_revoke_of_grant_manage_is_denied(self):
        factory = ServiceFactory(active={ACTOR, TARGET})
        service = factory.service()
        with self.assertRaises(ApplicationAuthorizationError) as raised:
            service._deny_self_managed(ACTOR, ACTOR, GRANT_MANAGE, "revoke")
        self.assertIn("self-revoke", str(raised.exception))

    def test_granting_grant_manage_to_another_user_is_not_self_managed(self):
        factory = ServiceFactory(active={ACTOR, TARGET})
        service = factory.service()
        # Must not raise: actor differs from target.
        service._deny_self_managed(ACTOR, TARGET, GRANT_MANAGE, "grant")


class GlobalStaffGrantOrchestrationTests(TestCase):
    def test_grant_creates_state_and_audit_atomically(self):
        factory = ServiceFactory(active={ACTOR, TARGET})
        service = factory.service()
        # Actor holds grant_manage so the actor-authorization pre-check passes.
        factory.grants.active[(ACTOR, GRANT_MANAGE)] = FakeGrantRow(
            status="active", user_id=ACTOR, permission=GRANT_MANAGE
        )

        grant_row = service.grant(ACTOR, TARGET, GRANT_MANAGE, reason="initial grant")

        self.assertEqual(factory.database.committed, True)
        self.assertEqual(factory.database.rolled_back, False)
        self.assertEqual(factory.grants.insert_calls, 1)
        self.assertEqual(factory.audit.insert_calls, 1)
        event = factory.audit.events[0]
        self.assertEqual(event["event_type"], "grant")
        self.assertEqual(event["actor_user_id"], ACTOR)
        self.assertEqual(event["target_user_id"], TARGET)
        self.assertEqual(event["permission"], GRANT_MANAGE)
        self.assertEqual(grant_row["user_id"], TARGET)
        self.assertEqual(grant_row["status"], "active")

    def test_reactivating_a_revoked_grant_keeps_one_row_and_appends_audit(self):
        factory = ServiceFactory(active={ACTOR, TARGET})
        service = factory.service()
        factory.grants.active[(ACTOR, GRANT_MANAGE)] = FakeGrantRow(
            status="active", user_id=ACTOR, permission=GRANT_MANAGE
        )

        service.grant(ACTOR, TARGET, GRANT_MANAGE, reason="initial grant")
        service.revoke(ACTOR, TARGET, GRANT_MANAGE, reason="first revoke")
        grant_row = service.grant(ACTOR, TARGET, GRANT_MANAGE, reason="re-grant")

        self.assertEqual(factory.grants.reactivate_calls, 1)
        self.assertEqual(factory.grants.revoke_calls, 1)
        # One active row for (target, permission) after reactivation.
        target_rows = [r for r in factory.grants.active.values()
                       if r["user_id"] == TARGET]
        self.assertEqual(len(target_rows), 1)
        self.assertEqual(grant_row["status"], "active")
        event_types = [e["event_type"] for e in factory.audit.events]
        self.assertEqual(event_types.count("grant"), 1)
        self.assertEqual(event_types.count("revocation"), 1)
        self.assertEqual(event_types.count("reactivation"), 1)

    def test_audit_insert_failure_rolls_back_state_mutation(self):
        factory = ServiceFactory(
            active={ACTOR, TARGET}, fail_audit=True
        )
        service = factory.service()
        factory.grants.active[(ACTOR, GRANT_MANAGE)] = FakeGrantRow(
            status="active", user_id=ACTOR, permission=GRANT_MANAGE
        )

        with self.assertRaises(RuntimeError):
            service.grant(ACTOR, TARGET, GRANT_MANAGE, reason="should roll back")

        self.assertEqual(factory.database.committed, False)
        self.assertEqual(factory.database.rolled_back, True)
        self.assertEqual(factory.grants.insert_calls, 1)
        self.assertEqual(factory.audit.insert_calls, 1)

    def test_grant_requires_actor_to_hold_grant_manage(self):
        factory = ServiceFactory(active={ACTOR, TARGET})
        service = factory.service()
        # No actor grant row: is_granted returns False.
        with self.assertRaises(ApplicationAuthorizationError):
            service.grant(ACTOR, TARGET, GRANT_MANAGE, reason="unauthorized actor")
        self.assertEqual(factory.database.committed, False)

    def test_bootstrap_grants_only_grant_manage_and_is_attributable(self):
        factory = ServiceFactory(active={ACTOR, TARGET})
        service = factory.service()
        grant_row = service.bootstrap(ACTOR, TARGET, justification="owner bootstrap", authorization_ref="auth-001")

        self.assertEqual(grant_row["user_id"], TARGET)
        self.assertEqual(grant_row["permission"], GRANT_MANAGE)
        self.assertEqual(grant_row["status"], "active")
        self.assertEqual(factory.audit.insert_calls, 1)
        event = factory.audit.events[0]
        self.assertEqual(event["event_type"], "bootstrap")
        self.assertEqual(event["actor_user_id"], ACTOR)
        self.assertEqual(event["target_user_id"], TARGET)
        self.assertEqual(event["permission"], GRANT_MANAGE)
        self.assertEqual(factory.database.committed, True)

    def test_bootstrap_is_idempotent_for_same_target(self):
        factory = ServiceFactory(active={ACTOR, TARGET})
        service = factory.service()
        service.bootstrap(ACTOR, TARGET, justification="first", authorization_ref="auth-001")
        first_event_count = len(factory.audit.events)
        # Re-run: target already holds active grant_manage -> no-op.
        grant_row = service.bootstrap(ACTOR, TARGET, justification="second", authorization_ref="auth-001")

        self.assertEqual(grant_row["user_id"], TARGET)
        self.assertEqual(len(factory.audit.events), first_event_count)
        self.assertEqual(factory.grants.insert_calls, 1)
        self.assertEqual(factory.database.committed, True)

    def test_bootstrap_refuses_when_holder_exists_for_another_user(self):
        factory = ServiceFactory(active={ACTOR, TARGET, OTHER})
        service = factory.service()
        service.bootstrap(ACTOR, TARGET, justification="first", authorization_ref="auth-001")
        # A different authorization reference is required for a different target;
        # without it, authorization mismatch is rejected before duplicate check.
        with self.assertRaises(ApplicationValidationError):
            service.bootstrap(ACTOR, OTHER, justification="second operator", authorization_ref="auth-001")
        self.assertEqual(factory.grants.insert_calls, 1)

    def test_revoke_requires_actor_to_hold_grant_manage(self):
        factory = ServiceFactory(active={ACTOR, TARGET})
        service = factory.service()
        with self.assertRaises(ApplicationAuthorizationError):
            service.revoke(ACTOR, TARGET, GRANT_MANAGE, reason="unauthorized")
        self.assertEqual(factory.database.committed, False)

    def test_revoke_not_found_when_no_grant_exists(self):
        factory = ServiceFactory(active={ACTOR, TARGET})
        service = factory.service()
        factory.grants.active[(ACTOR, GRANT_MANAGE)] = FakeGrantRow(
            status="active", user_id=ACTOR, permission=GRANT_MANAGE
        )
        with self.assertRaises(ApplicationNotFoundError):
            service.revoke(ACTOR, TARGET, GRANT_MANAGE, reason="nothing to revoke")
        self.assertEqual(factory.database.committed, False)
