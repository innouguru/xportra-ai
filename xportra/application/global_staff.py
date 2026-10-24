"""Global staff grant and audit use cases (Phase 4D.10 Task 2).

Server-side, fail-closed permission grants for designated Xportra staff,
independent of tenant membership. Grant, revocation, and bootstrap
mutations are recorded atomically with an append-only audit event in the
same database transaction; if the audit record cannot be persisted, the
grant-state change is rolled back.

Actor identity always comes from the verified authenticated identity
(resolved server-side through ``users.supabase_uid``), never from an
untrusted caller field. The initial permission is ``grant_manage`` only.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from xportra.application.errors import (
    ApplicationAuthorizationError,
    ApplicationError,
    ApplicationNotFoundError,
    ApplicationValidationError,
)
from xportra.persistence.database import Database
from xportra.persistence.repositories import (
    GlobalStaffAuditRepository,
    GlobalStaffAuthorizationRepository,
    GlobalStaffGrantRepository,
    UserRepository,
)

GRANT_MANAGE = "grant_manage"
STAGE_A_VERIFY = "stage_a_verify"
STAGE_B_APPROVE = "stage_b_approve"

#: Explicitly defined global staff permissions. Initially only
#: ``grant_manage`` is approved; every other name is rejected at the
#: service and database level (least privilege, controlled expansion).
_GLOBAL_STAFF_PERMISSIONS = frozenset({GRANT_MANAGE, STAGE_A_VERIFY, STAGE_B_APPROVE})


class AlreadyBootstrappedError(ApplicationError):
    """The system already has a ``grant_manage`` holder; bootstrap refused."""

    category = "already_bootstrapped"


class GlobalStaffGrantService:
    def __init__(
        self,
        database: Database,
        *,
        grants: GlobalStaffGrantRepository | None = None,
        audit: GlobalStaffAuditRepository | None = None,
        authorizations: GlobalStaffAuthorizationRepository | None = None,
        users: UserRepository | None = None,
    ) -> None:
        self._database = database
        self._grants = grants or GlobalStaffGrantRepository(database)
        self._audit = audit or GlobalStaffAuditRepository(database)
        self._authorizations = authorizations or GlobalStaffAuthorizationRepository(database)
        self._users = users or UserRepository(database)

    # ---------------------------------------------------------------- queries

    def is_granted(self, user_id: UUID, permission: str) -> bool:
        """Return whether the user currently holds an active grant."""
        self._require_valid_permission(permission)
        row = self._grants.get_active(user_id, permission)
        return row is not None

    def get_grant(self, user_id: UUID, permission: str) -> dict[str, Any] | None:
        """Return the current-state grant row, or None when absent."""
        self._require_valid_permission(permission)
        return self._grants.get(user_id, permission)

    # ---------------------------------------------------------------- mutations

    def grant(
        self,
        actor_user_id: UUID,
        target_user_id: UUID,
        permission: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Grant (or re-grant/reactivate) ``permission`` to the target user.

        The actor must hold an active ``grant_manage`` grant. Ordinary
        self-grant of ``grant_manage`` is denied. The grant-state mutation
        and the audit insert commit atomically.
        """
        self._require_valid_permission(permission)
        self._deny_self_managed(actor_user_id, target_user_id, permission, "grant")
        self._require_actor_can_manage(actor_user_id)
        self._require_active_user(target_user_id)

        with self._database.transaction() as connection:
            row = self._grants.lock_in_transaction(
                connection, target_user_id, permission
            )
            if row is not None and row["status"] == "active":
                raise ApplicationValidationError(
                    "target user already holds an active grant for this permission"
                )
            if row is not None and row["status"] == "revoked":
                grant_row = self._grants.reactivate_in_transaction(
                    connection, target_user_id, permission, actor_user_id, reason
                )
                event_type = "reactivation"
            else:
                grant_row = self._grants.insert_in_transaction(
                    connection, target_user_id, permission, actor_user_id, reason
                )
                event_type = "grant"
            self._audit.insert_in_transaction(
                connection,
                event_type,
                actor_user_id,
                target_user_id,
                permission,
                reason,
            )
        return grant_row

    def revoke(
        self,
        actor_user_id: UUID,
        target_user_id: UUID,
        permission: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Revoke the target user's active ``permission`` grant.

        The actor must hold an active ``grant_manage`` grant. Ordinary
        self-revocation of the actor's own ``grant_manage`` is denied.
        Revocation UPDATEs the existing row and appends an audit event;
        historical audit records are never deleted.
        """
        self._require_valid_permission(permission)
        self._deny_self_managed(actor_user_id, target_user_id, permission, "revoke")
        self._require_actor_can_manage(actor_user_id)
        self._require_active_user(target_user_id)

        with self._database.transaction() as connection:
            row = self._grants.lock_in_transaction(
                connection, target_user_id, permission
            )
            if row is None:
                raise ApplicationNotFoundError(
                    "no grant found for the target user and permission"
                )
            if row["status"] == "revoked":
                raise ApplicationValidationError(
                    "the target user's grant is already revoked"
                )
            grant_row = self._grants.revoke_in_transaction(
                connection, target_user_id, permission, actor_user_id, reason
            )
            self._audit.insert_in_transaction(
                connection,
                "revocation",
                actor_user_id,
                target_user_id,
                permission,
                reason,
            )
        return grant_row

    def bootstrap(
        self,
        actor_user_id: UUID,
        target_user_id: UUID,
        justification: str,
        authorization_ref: str | None = None,
    ) -> dict[str, Any]:
        """Bootstrap the initial ``grant_manage`` operator.

        Controlled, attributable, least-privilege, and safe to retry:
        only ``grant_manage`` is provisioned, the actor and target must be
        active users, the event is attributed to the actual actor, and the
        grant plus audit record commit atomically (fail closed).

        Idempotent: re-running after successful bootstrap returns the
        existing grant without creating a duplicate. If a ``grant_manage``
        row already exists for a different user, bootstrap fails closed.
        """
        self._require_active_user(actor_user_id)
        self._require_active_user(target_user_id)
        self._deny_self_managed(actor_user_id, target_user_id, GRANT_MANAGE, "bootstrap")

        permission = GRANT_MANAGE
        with self._database.transaction() as connection:
            # Serialize bootstrap attempts across connections for this permission.
            if hasattr(connection, "cursor"):
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT pg_advisory_xact_lock(hashtext(%s)::bigint)",
                        (f"global_staff_{permission}",),
                    )
            # Verify independent authorization reference (fail closed).
            authorization_row = None
            if authorization_ref is not None:
                authorization_row = self._authorizations.get_by_ref(authorization_ref)
            if authorization_row is None:
                raise ApplicationValidationError(
                    "bootstrap requires a valid, independently verified authorization reference; authorization missing, revoked, expired, or already consumed"
                )
            # Verify authorization matches target and permission scope.
            if authorization_row.get("target_user_id") != target_user_id or authorization_row.get("permission") != permission:
                raise ApplicationValidationError(
                    "authorization reference does not match the requested target user or permission scope"
                )
            if authorization_row.get("status") not in ("approved",):
                raise ApplicationValidationError(
                    "authorization reference is not in an approved state"
                )
            # Consume authorization within the same transaction.
            auth_consumed = self._authorizations.consume_in_transaction(
                connection, authorization_row["id"], actor_user_id
            )
            if auth_consumed is None:
                raise ApplicationValidationError(
                    "authorization has already been consumed or is no longer valid"
                )
            authorization_ref_for_audit = authorization_ref
            if self._grants.exists_any_in_transaction(connection, permission):
                existing = self._grants.get_active(target_user_id, permission)
                if existing is not None:
                    return existing
                raise AlreadyBootstrappedError(
                    "a grant_manage holder already exists; bootstrap refused"
                )
            grant_row = self._grants.insert_in_transaction(
                connection, target_user_id, permission, actor_user_id, justification
            )
            self._audit.insert_in_transaction(
                connection,
                "bootstrap",
                actor_user_id,
                target_user_id,
                permission,
                justification,
                authorization_ref=authorization_ref_for_audit,
            )
        return grant_row

    # ---------------------------------------------------------------- internals

    def _require_valid_permission(self, permission: str) -> None:
        if permission not in _GLOBAL_STAFF_PERMISSIONS:
            raise ApplicationValidationError(
                f"{permission} is not a defined global staff permission"
            )

    def _require_actor_can_manage(self, actor_user_id: UUID) -> None:
        if not self.is_granted(actor_user_id, GRANT_MANAGE):
            raise ApplicationAuthorizationError(
                "the actor does not hold an active grant_manage grant"
            )

    def _require_active_user(self, user_id: UUID) -> None:
        row = self._users.get(user_id)
        if row is None:
            raise ApplicationNotFoundError("user not found")
        if row.get("status") != "active":
            raise ApplicationValidationError("user is not active")

    @staticmethod
    def _deny_self_managed(
        actor_user_id: UUID,
        target_user_id: UUID,
        permission: str,
        operation: str,
    ) -> None:
        """Ordinary self-grant and self-revocation of grant_manage are denied."""
        if actor_user_id == target_user_id and permission == GRANT_MANAGE:
            raise ApplicationAuthorizationError(
                f"ordinary self-{operation} of grant_manage is not permitted"
            )


__all__ = [
    "AlreadyBootstrappedError",
    "GRANT_MANAGE",
    "STAGE_A_VERIFY",
    "STAGE_B_APPROVE",
    "GlobalStaffGrantService",
]
