import logging
import os
import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt as pyjwt
from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.api.dependencies import ApplicationServices
from xportra.persistence.database import Database, DatabaseSettings
from xportra.persistence.repositories import (
    ExporterRepository,
    RequirementRepository,
    TenantRepository,
    UserRepository,
    UserTenantMembershipRepository,
)
from xportra.persistence.tenant import TenantContext

TEST_JWT_SECRET = "phase-1-9-integration-test-jwt-secret"
TEST_AUDIENCE = "authenticated"
TEST_SUPABASE_URL = "https://phase-1-9-test.supabase.co"
TEST_ISSUER = TEST_SUPABASE_URL + "/auth/v1"

TENANT_A_SLUG = "phase-1-9-auth-a"
TENANT_B_SLUG = "phase-1-9-auth-b"
SUSPENDED_SLUG = "phase-1-9-auth-suspended"
GLOBAL_REQUIREMENT_CODE = "P19-AUTH-GLOBAL"

SUBJECT_A = UUID("aaaaaa01-0000-0000-0000-000000000001")
SUBJECT_B = UUID("bbbbbb01-0000-0000-0000-000000000002")
SUBJECT_MULTI = UUID("cccccc01-0000-0000-0000-000000000003")
SUBJECT_NONE = UUID("dddddd01-0000-0000-0000-000000000004")
SUBJECT_UNKNOWN = UUID("eeeeee01-0000-0000-0000-000000000005")
SUBJECT_SUSPENDED = UUID("ffffffff-0000-0000-0000-000000000001")

AUTHORITY_ID = UUID("00000000-0000-0000-0000-000000000001")


def make_token(
    subject,
    secret=TEST_JWT_SECRET,
    exp_delta=None,
    audience=TEST_AUDIENCE,
    issuer=TEST_ISSUER,
    **overrides,
):
    now = datetime.now(timezone.utc)
    if exp_delta is None:
        exp_delta = timedelta(hours=1)
    payload = {
        "aud": audience,
        "role": "authenticated",
        "sub": str(subject),
        "email": f"{subject}@example.invalid",
        "iat": now,
        "exp": now + exp_delta,
        "iss": issuer,
    }
    payload.update(overrides)
    return pyjwt.encode(payload, secret, algorithm="HS256")


def auth_headers(subject, **kwargs):
    return {"Authorization": f"Bearer {make_token(subject, **kwargs)}"}


class LogCaptureHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(self.format(record))


class AuthenticatedTenantIntegrationTests(unittest.TestCase):
    database = None
    tenant_a = None
    tenant_b = None
    exporter_b_id = None
    requirement_global_id = None
    _saved_env = {}

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DATABASE_URL", "").strip():
            raise unittest.SkipTest("DATABASE_URL is not configured")
        cls._apply_test_auth_config()
        cls.database = Database(DatabaseSettings.from_environment())
        cls._cleanup()
        cls._verify_migration_002()

        tenant_repository = TenantRepository(cls.database)
        tenant_a = tenant_repository.create("Phase 1.9 Auth Tenant A", TENANT_A_SLUG)
        tenant_b = tenant_repository.create("Phase 1.9 Auth Tenant B", TENANT_B_SLUG)
        suspended = tenant_repository.create(
            "Phase 1.9 Auth Suspended Tenant", SUSPENDED_SLUG, "suspended"
        )
        cls.tenant_a = tenant_a["id"]
        cls.tenant_b = tenant_b["id"]

        user_repository = UserRepository(cls.database)
        membership_repository = UserTenantMembershipRepository(cls.database)
        user_a = user_repository.create(
            "Phase 1.9 User A", "phase-1-9-a@example.invalid", "active", SUBJECT_A
        )
        user_b = user_repository.create(
            "Phase 1.9 User B", "phase-1-9-b@example.invalid", "active", SUBJECT_B
        )
        user_multi = user_repository.create(
            "Phase 1.9 User Multi", "phase-1-9-multi@example.invalid", "active", SUBJECT_MULTI
        )
        user_none = user_repository.create(
            "Phase 1.9 User None", "phase-1-9-none@example.invalid", "active", SUBJECT_NONE
        )
        user_suspended = user_repository.create(
            "Phase 1.9 User Suspended",
            "phase-1-9-suspended@example.invalid",
            "active",
            SUBJECT_SUSPENDED,
        )
        membership_repository.add(TenantContext(tenant_a["id"]), user_a["id"], "owner")
        membership_repository.add(TenantContext(tenant_b["id"]), user_b["id"], "member")
        membership_repository.add(TenantContext(tenant_a["id"]), user_multi["id"], "member")
        membership_repository.add(TenantContext(tenant_b["id"]), user_multi["id"], "member")
        membership_repository.add(TenantContext(suspended["id"]), user_suspended["id"], "member")
        membership_repository.add(
            TenantContext(tenant_a["id"]), user_none["id"], "member", "revoked"
        )

        cls.exporter_b_id = ExporterRepository(cls.database).create(
            TenantContext(tenant_b["id"]), "Phase 1.9 Exporter B", registration_number="P19-B"
        )["id"]
        cls.requirement_global_id = RequirementRepository(cls.database).create(
            None,
            GLOBAL_REQUIREMENT_CODE,
            "Phase 1.9 Global Requirement",
            "Authenticated integration requirement",
            status="active",
        )["id"]

    @classmethod
    def tearDownClass(cls):
        cls._cleanup()
        cls._restore_test_auth_config()

    @classmethod
    def _apply_test_auth_config(cls):
        for name in ("SUPABASE_JWT_SECRET", "SUPABASE_JWT_AUDIENCE", "SUPABASE_URL"):
            cls._saved_env[name] = os.environ.get(name)
        os.environ["SUPABASE_JWT_SECRET"] = TEST_JWT_SECRET
        os.environ["SUPABASE_JWT_AUDIENCE"] = TEST_AUDIENCE
        os.environ["SUPABASE_URL"] = TEST_SUPABASE_URL

    @classmethod
    def _restore_test_auth_config(cls):
        for name, value in cls._saved_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    @classmethod
    def _verify_migration_002(cls):
        with cls.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'xportra' AND table_name = 'users' "
                    "AND column_name = 'supabase_uid'"
                )
                if cursor.fetchone() is None:
                    raise RuntimeError(
                        "migrations/002_add_supabase_auth_identity.sql must be applied "
                        "before running Phase 1.9 integration tests"
                    )

    @classmethod
    def _cleanup(cls):
        if cls.database is None:
            if not os.environ.get("DATABASE_URL", "").strip():
                return
            cls.database = Database(DatabaseSettings.from_environment())
        slugs = (TENANT_A_SLUG, TENANT_B_SLUG, SUSPENDED_SLUG)
        with cls.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM xportra.tenants WHERE slug = ANY(%s)",
                    (list(slugs),),
                )
                tenant_ids = [row["id"] for row in cursor.fetchall()]
                if tenant_ids:
                    cursor.execute(
                        "DELETE FROM xportra.evidence_requirements WHERE tenant_id = ANY(%s)",
                        (tenant_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.requirement_applicability WHERE tenant_id = ANY(%s)",
                        (tenant_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.compliance_evidence WHERE tenant_id = ANY(%s)",
                        (tenant_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.certification_permit_licenses WHERE tenant_id = ANY(%s)",
                        (tenant_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.products WHERE tenant_id = ANY(%s)",
                        (tenant_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.destination_markets WHERE tenant_id = ANY(%s)",
                        (tenant_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.exporters WHERE tenant_id = ANY(%s)",
                        (tenant_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.requirements WHERE tenant_id = ANY(%s)",
                        (tenant_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.user_tenant_memberships WHERE tenant_id = ANY(%s)",
                        (tenant_ids,),
                    )
                    cursor.execute(
                        "DELETE FROM xportra.tenants WHERE id = ANY(%s)",
                        (tenant_ids,),
                    )
                cursor.execute(
                    "DELETE FROM xportra.users WHERE supabase_uid = ANY(%s)",
                    (
                        [
                            SUBJECT_A,
                            SUBJECT_B,
                            SUBJECT_MULTI,
                            SUBJECT_NONE,
                            SUBJECT_UNKNOWN,
                            SUBJECT_SUSPENDED,
                        ],
                    ),
                )
                cursor.execute(
                    "DELETE FROM xportra.requirements WHERE requirement_code = %s",
                    (GLOBAL_REQUIREMENT_CODE,),
                )

    def client(self):
        return TestClient(create_app(services=ApplicationServices.from_environment()))

    def test_valid_token_operates_within_membership_tenant(self):
        with self.client() as client:
            created = client.post(
                "/exporters",
                headers=auth_headers(SUBJECT_A),
                json={"legal_name": "Phase 1.9 Authenticated Exporter", "registration_number": "P19-AUTH-A"},
            )
            self.assertEqual(created.status_code, 201, created.text)
            exported = created.json()
            self.assertEqual(exported["tenant_id"], str(self.tenant_a))
            retrieved = client.get(
                f"/exporters/{exported['id']}", headers=auth_headers(SUBJECT_A)
            )
            self.assertEqual(retrieved.status_code, 200, retrieved.text)
            self.assertEqual(retrieved.json()["tenant_id"], str(self.tenant_a))

    def test_missing_credentials_are_rejected(self):
        with self.client() as client:
            response = client.post("/exporters", json={"legal_name": "No Credentials"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "authentication_required")
        self.assertEqual(response.headers.get("www-authenticate"), "Bearer")

    def test_malformed_and_invalid_credentials_are_rejected(self):
        with self.client() as client:
            malformed = client.post(
                "/exporters",
                headers={"Authorization": "Bearer not.a.jwt"},
                json={"legal_name": "Malformed"},
            )
            wrong_scheme = client.post(
                "/exporters",
                headers={"Authorization": "Basic dXNwbDpz"},
                json={"legal_name": "Wrong Scheme"},
            )
            expired = client.post(
                "/exporters",
                headers=auth_headers(SUBJECT_A, exp_delta=-timedelta(hours=1)),
                json={"legal_name": "Expired"},
            )
            wrong_audience = client.post(
                "/exporters",
                headers=auth_headers(SUBJECT_A, audience="another-audience"),
                json={"legal_name": "Wrong Audience"},
            )
            wrong_secret = client.post(
                "/exporters",
                headers={"Authorization": f"Bearer {make_token(SUBJECT_A, secret='different-secret-that-is-long-enough')}"},
                json={"legal_name": "Wrong Secret"},
            )
        self.assertEqual(malformed.status_code, 401)
        self.assertEqual(malformed.json()["error"]["code"], "invalid_token")
        self.assertEqual(wrong_scheme.status_code, 401)
        self.assertEqual(wrong_scheme.json()["error"]["code"], "invalid_token")
        self.assertEqual(expired.status_code, 401)
        self.assertEqual(expired.json()["error"]["code"], "expired_token")
        self.assertEqual(wrong_audience.status_code, 401)
        self.assertEqual(wrong_audience.json()["error"]["code"], "invalid_token")
        self.assertEqual(wrong_secret.status_code, 401)
        self.assertEqual(wrong_secret.json()["error"]["code"], "invalid_token")

    def test_authenticated_user_without_valid_membership_is_rejected(self):
        with self.client() as client:
            no_membership = client.post(
                "/exporters",
                headers=auth_headers(SUBJECT_NONE),
                json={"legal_name": "Revoked Only"},
            )
            unknown = client.post(
                "/exporters",
                headers=auth_headers(SUBJECT_UNKNOWN),
                json={"legal_name": "Unknown Identity"},
            )
            suspended_tenant = client.post(
                "/exporters",
                headers=auth_headers(SUBJECT_SUSPENDED),
                json={"legal_name": "Suspended Tenant Member"},
            )
        for response in (no_membership, unknown, suspended_tenant):
            self.assertEqual(response.status_code, 403)
            self.assertEqual(
                response.json()["error"]["code"], "tenant_membership_required"
            )

    def test_client_supplied_tenant_cannot_bypass_membership(self):
        with self.client() as client:
            response = client.post(
                "/exporters",
                headers={
                    **auth_headers(SUBJECT_A),
                    "X-Xportra-Tenant-ID": str(self.tenant_b),
                },
                json={"legal_name": "Bypass Attempt"},
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "tenant_not_member")

    def test_multi_membership_requires_explicit_selection(self):
        with self.client() as client:
            no_selection = client.post(
                "/exporters",
                headers=auth_headers(SUBJECT_MULTI),
                json={"legal_name": "Ambiguous"},
            )
            in_a = client.post(
                "/exporters",
                headers={
                    **auth_headers(SUBJECT_MULTI),
                    "X-Xportra-Tenant-ID": str(self.tenant_a),
                },
                json={"legal_name": "Phase 1.9 Multi Tenant A", "registration_number": "P19-MULTI-A"},
            )
            in_b = client.post(
                "/exporters",
                headers={
                    **auth_headers(SUBJECT_MULTI),
                    "X-Xportra-Tenant-ID": str(self.tenant_b),
                },
                json={"legal_name": "Phase 1.9 Multi Tenant B", "registration_number": "P19-MULTI-B"},
            )
        self.assertEqual(no_selection.status_code, 400)
        self.assertEqual(no_selection.json()["error"]["code"], "tenant_selection_required")
        self.assertEqual(in_a.status_code, 201, in_a.text)
        self.assertEqual(in_a.json()["tenant_id"], str(self.tenant_a))
        self.assertEqual(in_b.status_code, 201, in_b.text)
        self.assertEqual(in_b.json()["tenant_id"], str(self.tenant_b))

    def test_tenant_isolation_between_authenticated_users(self):
        with self.client() as client:
            created = client.post(
                "/exporters",
                headers=auth_headers(SUBJECT_A),
                json={"legal_name": "Phase 1.9 Isolation Exporter A", "registration_number": "P19-ISO-A"},
            )
            self.assertEqual(created.status_code, 201, created.text)
            exporter_a_id = created.json()["id"]

            own = client.get(f"/exporters/{exporter_a_id}", headers=auth_headers(SUBJECT_A))
            other = client.get(
                f"/exporters/{exporter_a_id}",
                headers={
                    **auth_headers(SUBJECT_B),
                    "X-Xportra-Tenant-ID": str(self.tenant_b),
                },
            )
            role_hop = client.get(
                f"/exporters/{exporter_a_id}",
                headers={
                    **auth_headers(SUBJECT_B),
                    "X-Xportra-Tenant-ID": str(self.tenant_a),
                },
            )
            cross_product = client.post(
                "/products",
                headers=auth_headers(SUBJECT_A),
                json={
                    "exporter_id": str(self.exporter_b_id),
                    "product_name": "Cross Tenant Product",
                },
            )
            cross_certificate = client.post(
                "/certifications-permits-licenses",
                headers=auth_headers(SUBJECT_A),
                json={
                    "exporter_id": str(self.exporter_b_id),
                    "issuing_authority_id": str(AUTHORITY_ID),
                    "title": "Cross Tenant Certificate",
                },
            )
            other_tenant_exporter = client.get(
                f"/exporters/{self.exporter_b_id}",
                headers={
                    **auth_headers(SUBJECT_A),
                    "X-Xportra-Tenant-ID": str(self.tenant_a),
                },
            )
        self.assertEqual(own.status_code, 200)
        self.assertEqual(other.status_code, 404)
        self.assertEqual(role_hop.status_code, 403)
        self.assertEqual(role_hop.json()["error"]["code"], "tenant_not_member")
        self.assertEqual(cross_product.status_code, 404)
        self.assertEqual(cross_certificate.status_code, 404)
        self.assertEqual(other_tenant_exporter.status_code, 404)

    def test_evidence_with_requirements_uses_membership_context(self):
        with self.client() as client:
            response = client.post(
                "/compliance-evidence/with-requirements",
                headers=auth_headers(SUBJECT_A),
                json={
                    "document_title": "Phase 1.9 Authenticated Evidence",
                    "document_type": "test",
                    "file_reference_or_uri": "test://phase-1-9/evidence",
                    "requirement_ids": [str(self.requirement_global_id)],
                },
            )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["tenant_id"], str(self.tenant_a))

    def test_development_header_remains_isolated_non_production_pathway(self):
        headers = {"X-Development-Tenant-ID": str(self.tenant_a)}
        with self.client() as client:
            response = client.post(
                "/exporters",
                headers=headers,
                json={"legal_name": "Phase 1.9 Dev Pathway Exporter"},
            )
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["tenant_id"], str(self.tenant_a))

    def test_production_blocks_development_header_and_requires_authentication(self):
        previous = os.environ.get("APP_ENV")
        os.environ["APP_ENV"] = "production"
        try:
            with self.client() as client:
                dev_header = client.post(
                    "/exporters",
                    headers={"X-Development-Tenant-ID": str(self.tenant_a)},
                    json={"legal_name": "Production Dev Header"},
                )
                no_credentials = client.post(
                    "/exporters", json={"legal_name": "Production No Auth"}
                )
                authenticated = client.post(
                    "/exporters",
                    headers=auth_headers(SUBJECT_A),
                    json={"legal_name": "Phase 1.9 Production Auth", "registration_number": "P19-PROD"},
                )
        finally:
            if previous is None:
                os.environ.pop("APP_ENV", None)
            else:
                os.environ["APP_ENV"] = previous
        self.assertEqual(dev_header.status_code, 503)
        self.assertEqual(
            dev_header.json()["error"]["code"], "development_tenant_context_disabled"
        )
        self.assertEqual(no_credentials.status_code, 401)
        self.assertEqual(no_credentials.json()["error"]["code"], "authentication_required")
        self.assertEqual(authenticated.status_code, 201, authenticated.text)

    def test_credentials_and_secrets_never_appear_in_responses_or_logs(self):
        handler = LogCaptureHandler()
        logger = logging.getLogger("xportra.api")
        logger.addHandler(handler)
        try:
            with self.client() as client:
                malformed = client.post(
                    "/exporters",
                    headers={"Authorization": "Bearer leaked-token-value"},
                    json={"legal_name": "Malformed"},
                )
                membership = client.post(
                    "/exporters",
                    headers=auth_headers(SUBJECT_NONE),
                    json={"legal_name": "No Membership"},
                )
                forbidden = client.post(
                    "/exporters",
                    headers={
                        **auth_headers(SUBJECT_A),
                        "X-Xportra-Tenant-ID": str(self.tenant_b),
                    },
                    json={"legal_name": "Forbidden"},
                )
        finally:
            logger.removeHandler(handler)
        rendered = (malformed.text + membership.text + forbidden.text).lower()
        for forbidden_value in (
            "leaked-token-value",
            TEST_JWT_SECRET,
            "postgres",
            "sql",
            "supabase",
            "service_role",
            str(SUBJECT_A),
        ):
            self.assertNotIn(forbidden_value.lower(), rendered)
        for record in handler.records:
            self.assertNotIn("leaked-token-value", record.lower())
            self.assertNotIn(TEST_JWT_SECRET, record.lower())

    def test_zzz_cleanup_leaves_no_test_tenants_or_users(self):
        self._cleanup()
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) AS count FROM xportra.tenants WHERE slug = ANY(%s)",
                    ([TENANT_A_SLUG, TENANT_B_SLUG, SUSPENDED_SLUG],),
                )
                tenants_left = cursor.fetchone()["count"]
                cursor.execute(
                    "SELECT count(*) AS count FROM xportra.users WHERE supabase_uid = ANY(%s)",
                    (
                        [
                            SUBJECT_A,
                            SUBJECT_B,
                            SUBJECT_MULTI,
                            SUBJECT_NONE,
                            SUBJECT_UNKNOWN,
                            SUBJECT_SUSPENDED,
                        ],
                    ),
                )
                users_left = cursor.fetchone()["count"]
        self.assertEqual(tenants_left, 0)
        self.assertEqual(users_left, 0)


if __name__ == "__main__":
    unittest.main()