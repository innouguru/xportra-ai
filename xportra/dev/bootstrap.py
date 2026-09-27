"""Local-development tenant/user/membership bootstrap.

LOCAL DEVELOPMENT ONLY. This module provisions one stable
development tenant, one development user, and one active
owner membership in the database pointed to by
``DATABASE_URL`` so the existing frontend/backend can be
run and manually tested locally.

Safety properties (all enforced, all tested):

- Refuses to run when ``APP_ENV=production`` — before
  opening any database connection.
- Creates nothing new on repeat runs: existing records
  are found by their natural unique keys (tenant slug,
  user email, membership pair) and reported as-is.
- Changes no authorization rule, no tenant-isolation
  rule, and no request handling. It only inserts the
  rows the existing rules already expect.
- Prints identifiers and roles only. Never prints the
  database DSN, tokens, JWT secrets, or credentials.
- Does not fake authentication: the development user
  carries no Supabase identity unless the operator
  explicitly links a real one with ``--supabase-uid``.

Two local auth paths (see ``docs/local-development.md``):

- ``X-Development-Tenant-ID`` header (or the Session
  page dev field): works with the bootstrapped tenant
  row immediately; no Supabase project needed. Rejected
  in production by the existing Phase 10.1 boundary.
- Bearer token: requires a real Supabase Auth user.
  Create one in the Supabase dashboard, then rerun
  ``python -m xportra.dev.bootstrap --supabase-uid
  <auth-user-uuid>`` to link it to the development
  user row. This script never mints tokens.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from xportra.persistence.database import (
    Database,
    DatabaseConfigurationError,
    DatabaseSettings,
)
from xportra.persistence.errors import PersistenceIntegrityError
from xportra.persistence.repositories import (
    TenantRepository,
    UserRepository,
    UserTenantMembershipRepository,
)
from xportra.persistence.tenant import TenantContext

#: Natural unique keys for the development records. Slugs,
#: names, and the reserved example email below are
#: identifiers, not secrets.
DEV_TENANT_SLUG = "local-development"
DEV_TENANT_NAME = "Local Development Tenant"
DEV_USER_EMAIL = "local-developer@xportra.local"
DEV_USER_NAME = "Local Developer"

#: Development membership role. Must equal the API
#: ``OWNER_ROLE`` ("owner") so the local developer can
#: exercise owner-gated flows; asserted by tests without
#: importing HTTP-layer code here.
DEV_ROLE = "owner"


class DevBootstrapError(Exception):
    """The development records cannot be established safely."""


def bootstrap_development_environment(
    database: Database,
    *,
    supabase_uid: UUID | None = None,
) -> dict[str, Any]:
    """Ensure the development tenant, user, and membership exist.

    Idempotent: reruns return the existing rows. Returns a
    report of ``{"tenant": ..., "user": ..., "membership":
    ...}`` where each entry carries its identifiers plus a
    ``created`` flag. Raises ``DevBootstrapError`` on any
    conflicting pre-existing state instead of overwriting
    it.
    """
    tenants = TenantRepository(database)
    users = UserRepository(database)
    memberships = UserTenantMembershipRepository(database)

    tenant, tenant_created = _ensure_tenant(tenants)
    user, user_created, uid_linked = _ensure_user(
        users, supabase_uid=supabase_uid
    )
    membership, membership_created = _ensure_membership(
        memberships, tenant, user
    )
    return {
        "tenant": {
            "id": tenant["id"],
            "slug": tenant["slug"],
            "status": tenant["status"],
            "created": tenant_created,
        },
        "user": {
            "id": user["id"],
            "email": user["email"],
            "status": user["status"],
            "supabase_uid": user.get("supabase_uid"),
            "created": user_created,
            "supabase_uid_linked": uid_linked,
        },
        "membership": {
            "role": membership["role"],
            "status": membership["status"],
            "created": membership_created,
        },
    }


def _ensure_tenant(tenants: TenantRepository) -> tuple[dict, bool]:
    existing = tenants.get_by_slug(DEV_TENANT_SLUG)
    if existing is not None:
        if existing.get("status") != "active":
            raise DevBootstrapError(
                f"development tenant {existing.get('id')} exists "
                f"with status {existing.get('status')!r}; refusing "
                "to reuse a non-active tenant"
            )
        return dict(existing), False
    try:
        created = tenants.create(DEV_TENANT_NAME, DEV_TENANT_SLUG, "active")
    except PersistenceIntegrityError as cause:
        raise DevBootstrapError(
            "development tenant could not be created; "
            "rerun the bootstrap to adopt the existing row"
        ) from cause
    return dict(created), True


def _ensure_user(
    users: UserRepository, *, supabase_uid: UUID | None
) -> tuple[dict, bool, bool]:
    existing = users.get_by_email(DEV_USER_EMAIL)
    if existing is None:
        try:
            created = users.create(
                DEV_USER_NAME, DEV_USER_EMAIL, "active", supabase_uid
            )
        except PersistenceIntegrityError as cause:
            raise DevBootstrapError(
                "development user could not be created; "
                "rerun the bootstrap to adopt the existing row"
            ) from cause
        return dict(created), True, supabase_uid is not None
    if existing.get("status") != "active":
        raise DevBootstrapError(
            f"development user {existing.get('id')} exists "
            f"with status {existing.get('status')!r}; refusing "
            "to reuse a non-active user"
        )
    current_uid = existing.get("supabase_uid")
    if supabase_uid is None or current_uid == supabase_uid:
        return dict(existing), False, False
    if current_uid is not None:
        raise DevBootstrapError(
            f"development user {existing.get('id')} is already "
            "linked to a different Supabase identity; refusing "
            "to overwrite the link"
        )
    try:
        linked = users.set_supabase_uid(existing["id"], supabase_uid)
    except PersistenceIntegrityError as cause:
        raise DevBootstrapError(
            "that Supabase identity is already linked to a "
            "different user; refusing to duplicate the link"
        ) from cause
    if linked is None:
        raise DevBootstrapError("development user vanished during linking")
    return dict(linked), False, True


def _ensure_membership(
    memberships: UserTenantMembershipRepository,
    tenant: dict,
    user: dict,
) -> tuple[dict, bool]:
    context = TenantContext(tenant["id"])
    for row in memberships.list_for_tenant(context):
        if row.get("user_id") != user["id"]:
            continue
        if row.get("status") != "active":
            raise DevBootstrapError(
                "a non-active membership already exists between "
                "the development tenant and user; refusing to "
                "duplicate or silently reactivate it"
            )
        if row.get("role") != DEV_ROLE:
            raise DevBootstrapError(
                "the existing development membership carries "
                f"role {row.get('role')!r}; refusing to silently "
                "change it"
            )
        return dict(row), False
    try:
        created = memberships.add(context, user["id"], DEV_ROLE, "active")
    except PersistenceIntegrityError:
        for row in memberships.list_for_tenant(context):
            if row.get("user_id") == user["id"] and row.get(
                "status"
            ) == "active":
                return dict(row), False
        raise DevBootstrapError(
            "development membership could not be created; "
            "rerun the bootstrap to adopt the existing row"
        )
    return dict(created), True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Provision the local-development tenant, user, "
        "and owner membership (never run in production)."
    )
    parser.add_argument(
        "--supabase-uid",
        default=None,
        help="Link an existing real Supabase Auth user UUID to the "
        "development user. Never mints tokens.",
    )
    return parser


def _is_production(values: Mapping[str, str]) -> bool:
    """Local APP_ENV check, deliberately not imported.

    ``xportra.api`` package init composes the FastAPI app
    as a side effect, so the bootstrap reads ``APP_ENV``
    directly instead of importing the runtime predicate.
    The rule is identical: only explicit ``production``
    refuses; anything else proceeds to database config.
    """
    raw = values.get("APP_ENV", "")
    return isinstance(raw, str) and raw.strip().lower() == "production"


def main(
    argv: list[str] | None = None,
    environment: Mapping[str, str] | None = None,
    database: Database | None = None,
) -> int:
    """CLI entry point. Returns a process exit code.

    ``database`` is a test seam; the CLI always builds it
    from ``DATABASE_URL`` when omitted.
    """
    args = build_parser().parse_args(argv)
    values = os.environ if environment is None else environment

    if _is_production(values):
        print(
            "refusing to bootstrap: APP_ENV=production. This "
            "utility is local-development only.",
            file=sys.stderr,
        )
        return 2
    try:
        settings = DatabaseSettings.from_environment(values)
    except DatabaseConfigurationError as cause:
        print(f"cannot bootstrap: {cause}", file=sys.stderr)
        return 2

    supabase_uid: UUID | None = None
    if args.supabase_uid is not None:
        try:
            supabase_uid = UUID(str(args.supabase_uid).strip())
        except (ValueError, TypeError, AttributeError):
            print(
                "cannot bootstrap: --supabase-uid must be a UUID",
                file=sys.stderr,
            )
            return 2

    try:
        report = bootstrap_development_environment(
            database if database is not None else Database(settings),
            supabase_uid=supabase_uid,
        )
    except DevBootstrapError as cause:
        print(f"cannot bootstrap: {cause}", file=sys.stderr)
        return 1
    print_report(report)
    return 0


def print_report(report: dict[str, Any]) -> None:
    """Print identifiers and next steps. No secrets, ever."""
    tenant = report["tenant"]
    user = report["user"]
    membership = report["membership"]

    def state(created: bool) -> str:
        return "created" if created else "already existed"

    print("Xportra local development bootstrap")
    print(f"Tenant ID: {tenant['id']} ({state(tenant['created'])})")
    print(f"Tenant slug: {tenant['slug']}")
    print(f"User ID: {user['id']} ({state(user['created'])})")
    print(f"Membership role: {membership['role']} "
          f"({state(membership['created'])})")
    if user.get("supabase_uid") is not None:
        linked = "linked just now" if user.get(
            "supabase_uid_linked") else "already linked"
        print(f"Supabase identity: {user['supabase_uid']} ({linked})")
    else:
        print("Supabase identity: not linked")
    print("")
    print("Local use (development only, never production):")
    print(f"- Frontend Session page: paste {tenant['id']} into "
          "the Development tenant ID field.")
    print(f"- API header: X-Development-Tenant-ID: {tenant['id']}")
    print("- Bearer tokens: create a real user in the Supabase "
          "dashboard, then rerun with --supabase-uid <auth-user-uuid> "
          "to link it. This script never mints tokens.")


if __name__ == "__main__":
    raise SystemExit(main())
