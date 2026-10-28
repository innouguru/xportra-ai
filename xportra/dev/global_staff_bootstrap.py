"""Operator-provisioned initial global staff grant bootstrap.

LOCAL DEVELOPMENT AND OPERATOR USE ONLY. This module invokes
``GlobalStaffGrantService.bootstrap()`` to provision the initial
``grant_manage`` global staff grant using an approved authorization
reference. It is the operator-facing entry point for the initial
grant and is never exposed as a public API endpoint.

Safety properties (all enforced, all tested):

- Refuses to run when ``APP_ENV=production`` — before opening any
  database connection. Production bootstrap requires a separately
  authorized operator to execute this same procedure against the
  production database after the production runtime-role decision is
  resolved.
- Requires an explicit ``--authorization-ref`` that matches an
  approved, unconsumed authorization record in
  ``xportra.global_staff_authorizations``. Missing, revoked, expired,
  already-consumed, or mismatched references fail closed.
- Requires explicit ``--target-user-id`` and ``--actor-user-id``.
  Identities are never hardcoded and never inferred from email or
  tenant membership.
- Prevents the target user from bootstrapping their own grant
  (self-bootstrap is denied by the service).
- Preserves single-use authorization consumption: the authorization
  record is consumed atomically within the same transaction as grant
  creation and audit insertion.
- Preserves atomic grant creation and audit insertion: if audit
  insertion fails, the entire transaction rolls back.
- Prints identifiers and status only. Never prints database DSN,
  tokens, JWT secrets, credentials, or authorization evidence.
- Does not bypass the application service: grant and audit records
  are created exclusively through ``GlobalStaffGrantService.bootstrap``.
- Never inserts into ``xportra.global_staff_grants`` or
  ``xportra.global_staff_audit`` directly.

Usage (development/local only):

    DATABASE_URL=postgresql://xportra_app@localhost:5432/xportra_test \
    python -m xportra.dev.global_staff_bootstrap \
        --authorization-ref XPA-GSA-INIT-001 \
        --target-user-id <target-user-uuid> \
        --actor-user-id <operator-user-uuid> \
        --justification "initial operator bootstrap"

The authorization record itself must be created out-of-band (by an
independent authorizer and verifier) before this script is run. This
script consumes the authorization; it does not create it.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from xportra.application.global_staff import (
    AlreadyBootstrappedError,
    GlobalStaffGrantService,
    GRANT_MANAGE,
)
from xportra.application.errors import (
    ApplicationAuthorizationError,
    ApplicationError,
    ApplicationValidationError,
)
from xportra.persistence.database import (
    Database,
    DatabaseConfigurationError,
    DatabaseSettings,
)

#: Bootstrap is limited to the initial ``grant_manage`` permission.
BOOTSTRAP_PERMISSION = GRANT_MANAGE


class GlobalStaffBootstrapError(Exception):
    """The initial global staff grant cannot be provisioned safely."""


def bootstrap_global_staff_grant(
    database: Database,
    *,
    authorization_ref: str,
    target_user_id: UUID,
    actor_user_id: UUID,
    justification: str,
) -> dict[str, Any]:
    """Provision the initial ``grant_manage`` global staff grant.

    Validates and consumes the approved authorization reference,
    then atomically creates the grant and linked audit record through
    ``GlobalStaffGrantService.bootstrap``. Fail-closed: missing,
    revoked, expired, already-consumed, or mismatched authorization
    references are rejected before any state change.

    Returns the grant row on success. Raises
    ``GlobalStaffBootstrapError`` on any failure.
    """
    service = GlobalStaffGrantService(database)
    try:
        grant_row = service.bootstrap(
            actor_user_id=actor_user_id,
            target_user_id=target_user_id,
            justification=justification,
            authorization_ref=authorization_ref,
        )
    except ApplicationAuthorizationError as cause:
        raise GlobalStaffBootstrapError(str(cause)) from cause
    except ApplicationValidationError as cause:
        raise GlobalStaffBootstrapError(str(cause)) from cause
    except ApplicationError as cause:
        raise GlobalStaffBootstrapError(str(cause)) from cause
    return {
        "grant_id": grant_row["id"],
        "user_id": grant_row["user_id"],
        "permission": grant_row["permission"],
        "status": grant_row["status"],
        "granted_by": grant_row["granted_by"],
        "granted_at": str(grant_row["granted_at"]),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provision the initial grant_manage global staff "
        "grant using an approved authorization reference "
        "(local/operator use only; never production).",
    )
    parser.add_argument(
        "--authorization-ref",
        required=True,
        help="Approved, non-empty authorization reference (e.g. "
        "XPA-GSA-INIT-001). Must match an approved, unconsumed "
        "record in xportra.global_staff_authorizations.",
    )
    parser.add_argument(
        "--target-user-id",
        required=True,
        help="Internal application user UUID (xportra.users.id) of "
        "the target receiving the grant_manage grant. Never the "
        "same as --actor-user-id.",
    )
    parser.add_argument(
        "--actor-user-id",
        required=True,
        help="Internal application user UUID (xportra.users.id) of "
        "the operator executing bootstrap. Must differ from "
        "--target-user-id.",
    )
    parser.add_argument(
        "--justification",
        required=True,
        help="Justification recorded on the grant and audit event.",
    )
    return parser


def _is_production(values: Mapping[str, str]) -> bool:
    """Local APP_ENV check, deliberately not imported from xportra.api.

    ``xportra.api`` package init composes the FastAPI app as a side
    effect, so this utility reads ``APP_ENV`` directly instead of
    importing the runtime predicate. The rule is identical: only
    explicit ``production`` refuses; anything else proceeds to
    database config.
    """
    raw = values.get("APP_ENV", "")
    return isinstance(raw, str) and raw.strip().lower() == "production"


def main(
    argv: list[str] | None = None,
    environment: Mapping[str, str] | None = None,
    database: Database | None = None,
) -> int:
    """CLI entry point. Returns a process exit code.

    ``database`` is a test seam; the CLI always builds it from
    ``DATABASE_URL`` when omitted.
    """
    args = build_parser().parse_args(argv)
    values = os.environ if environment is None else environment

    if _is_production(values):
        print(
            "refusing to bootstrap global staff grant: "
            "APP_ENV=production. This utility is local/operator use "
            "only. Production bootstrap requires a separately "
            "authorized operator to execute this procedure against "
            "the production database after the runtime-role decision "
            "is resolved.",
            file=sys.stderr,
        )
        return 2

    try:
        settings = DatabaseSettings.from_environment(values)
    except DatabaseConfigurationError as cause:
        print(f"cannot bootstrap: {cause}", file=sys.stderr)
        return 2

    try:
        target_user_id = UUID(str(args.target_user_id).strip())
    except (ValueError, TypeError, AttributeError):
        print(
            "cannot bootstrap: --target-user-id must be a UUID",
            file=sys.stderr,
        )
        return 2

    try:
        actor_user_id = UUID(str(args.actor_user_id).strip())
    except (ValueError, TypeError, AttributeError):
        print(
            "cannot bootstrap: --actor-user-id must be a UUID",
            file=sys.stderr,
        )
        return 2

    if actor_user_id == target_user_id:
        print(
            "cannot bootstrap: --actor-user-id and --target-user-id "
            "must differ (self-bootstrap is denied)",
            file=sys.stderr,
        )
        return 2

    try:
        report = bootstrap_global_staff_grant(
            database if database is not None else Database(settings),
            authorization_ref=args.authorization_ref,
            target_user_id=target_user_id,
            actor_user_id=actor_user_id,
            justification=args.justification,
        )
    except GlobalStaffBootstrapError as cause:
        print(f"cannot bootstrap: {cause}", file=sys.stderr)
        return 1

    print_report(report)
    return 0


def print_report(report: dict[str, Any]) -> None:
    """Print identifiers and status. No secrets, ever."""
    print("Xportra initial global staff grant bootstrap")
    print(f"Grant ID: {report['grant_id']}")
    print(f"Target user ID: {report['user_id']}")
    print(f"Permission: {report['permission']}")
    print(f"Status: {report['status']}")
    print(f"Granted by: {report['granted_by']}")
    print(f"Granted at: {report['granted_at']}")
    print("")
    print("The authorization reference has been consumed atomically "
          "with grant creation and audit insertion. It cannot be "
          "reused. See xportra.global_staff_audit for the linked "
          "audit event.")


if __name__ == "__main__":
    raise SystemExit(main())
