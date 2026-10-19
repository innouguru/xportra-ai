"""Atomic persistence boundary for organization registration."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from xportra.persistence.database import Database

RegistrationStatus = Literal[
    "created",
    "already_member",
    "identity_conflict",
]


@dataclass(frozen=True, slots=True)
class OrganizationRegistrationOutcome:
    status: RegistrationStatus
    tenant_id: UUID | None = None
    tenant_slug: str | None = None
    tenant_name: str | None = None
    user_id: UUID | None = None
    role: str | None = None
    membership_status: str | None = None


class OrganizationRegistrationStore:
    """Provision one tenant, user mapping, and owner membership atomically."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def provision(
        self,
        *,
        supabase_uid: UUID,
        email: str | None,
        display_name: str,
        legal_name: str,
        slug: str,
        organization_type: str | None = None,
        country_code: str | None = None,
        region: str | None = None,
        role: str = "owner",
    ) -> OrganizationRegistrationOutcome:
        with self._database.transaction() as connection:
            with connection.cursor() as cursor:
                if self._has_active_membership(cursor, supabase_uid):
                    return OrganizationRegistrationOutcome(
                        status="already_member"
                    )

                cursor.execute(
                    """
                    INSERT INTO xportra.users
                        (supabase_uid, display_name, email, status)
                    VALUES (%s, %s, %s, 'active')
                    ON CONFLICT DO NOTHING
                    RETURNING id
                    """,
                    (supabase_uid, display_name, email),
                )
                user = cursor.fetchone()
                if user is None:
                    cursor.execute(
                        """
                        SELECT id
                        FROM xportra.users
                        WHERE supabase_uid = %s
                        FOR UPDATE
                        """,
                        (supabase_uid,),
                    )
                    user = cursor.fetchone()
                    if user is None:
                        return OrganizationRegistrationOutcome(
                            status="identity_conflict"
                        )
                    if self._has_active_membership(cursor, supabase_uid):
                        return OrganizationRegistrationOutcome(
                            status="already_member"
                        )

                user_id = user["id"]
                cursor.execute(
                    """
                    INSERT INTO xportra.tenants
                        (
                            legal_name,
                            slug,
                            status,
                            organization_type,
                            country_code,
                            region
                        )
                    VALUES (%s, %s, 'active', %s, %s, %s)
                    RETURNING id, slug, legal_name
                    """,
                    (
                        legal_name,
                        slug,
                        organization_type,
                        country_code,
                        region,
                    ),
                )
                tenant = cursor.fetchone()
                if tenant is None:
                    raise RuntimeError(
                        "organization tenant insert returned no row"
                    )

                cursor.execute(
                    """
                    INSERT INTO xportra.user_tenant_memberships
                        (tenant_id, user_id, role, status)
                    VALUES (%s, %s, %s, 'active')
                    RETURNING role, status
                    """,
                    (tenant["id"], user_id, role),
                )
                membership = cursor.fetchone()
                if membership is None:
                    raise RuntimeError(
                        "organization membership insert returned no row"
                    )

                return OrganizationRegistrationOutcome(
                    status="created",
                    tenant_id=tenant["id"],
                    tenant_slug=tenant["slug"],
                    tenant_name=tenant["legal_name"],
                    user_id=user_id,
                    role=membership["role"],
                    membership_status=membership["status"],
                )

    @staticmethod
    def _has_active_membership(cursor, supabase_uid: UUID) -> bool:
        cursor.execute(
            """
            SELECT m.tenant_id
            FROM xportra.users AS u
            JOIN xportra.user_tenant_memberships AS m
                ON m.user_id = u.id
            WHERE u.supabase_uid = %s
                AND m.status = 'active'
            LIMIT 1
            FOR UPDATE OF u
            """,
            (supabase_uid,),
        )
        return cursor.fetchone() is not None


__all__ = [
    "OrganizationRegistrationOutcome",
    "OrganizationRegistrationStore",
]
