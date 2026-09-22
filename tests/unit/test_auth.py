from datetime import datetime, timedelta, timezone
import unittest
from uuid import UUID

import jwt as pyjwt

from xportra.api.auth import (
    AuthConfigurationError,
    AuthenticatedIdentity,
    MemberContext,
    SupabaseAuthSettings,
    SupabaseTokenVerifier,
    TenantMembershipResolver,
)
from xportra.api.errors import APIError, AuthenticationError
from xportra.persistence.tenant import TenantContext

TEST_SECRET = "phase-1-9-unit-test-jwt-secret-0123456789abcdef"
TEST_AUDIENCE = "authenticated"
TEST_URL = "https://example.supabase.co"
SUBJECT_A = UUID("aaaaaaa1-0000-0000-0000-000000000001")
TENANT_A = UUID("11111111-1111-1111-1111-111111111111")
TENANT_B = UUID("22222222-2222-2222-2222-222222222222")
ISSUER = TEST_URL + "/auth/v1"


def make_token(
    secret=TEST_SECRET,
    subject=SUBJECT_A,
    audience=TEST_AUDIENCE,
    issuer=ISSUER,
    **overrides,
):
    now = datetime.now(timezone.utc)
    payload = {
        "aud": audience,
        "role": "authenticated",
        "sub": str(subject),
        "email": "user-a@example.invalid",
        "iat": now,
        "exp": now + timedelta(hours=1),
        "iss": issuer,
    }
    payload.update(overrides)
    return pyjwt.encode(payload, secret, algorithm="HS256")


def settings(url=TEST_URL):
    return SupabaseAuthSettings(
        jwt_secret=TEST_SECRET,
        audience=TEST_AUDIENCE,
        supabase_url=url,
    )


class SupabaseAuthSettingsTests(unittest.TestCase):
    def test_settings_require_jwt_secret(self):
        with self.assertRaises(AuthConfigurationError):
            SupabaseAuthSettings.from_environment({})

    def test_settings_read_environment_values(self):
        configured = SupabaseAuthSettings.from_environment(
            {
                "SUPABASE_JWT_SECRET": "secret-value",
                "SUPABASE_JWT_AUDIENCE": "custom-audience",
                "SUPABASE_URL": "https://proj.supabase.co",
            }
        )
        self.assertEqual(configured.jwt_secret, "secret-value")
        self.assertEqual(configured.audience, "custom-audience")
        self.assertEqual(configured.supabase_url, "https://proj.supabase.co")

    def test_settings_defaults_audience_and_url(self):
        configured = SupabaseAuthSettings.from_environment(
            {"SUPABASE_JWT_SECRET": "secret-value"}
        )
        self.assertEqual(configured.audience, "authenticated")
        self.assertIsNone(configured.supabase_url)


class SupabaseTokenVerifierTests(unittest.TestCase):
    def test_valid_token_yields_authenticated_identity(self):
        verifier = SupabaseTokenVerifier(settings())
        identity = verifier.verify(make_token())
        self.assertEqual(identity, AuthenticatedIdentity(SUBJECT_A, "user-a@example.invalid"))
        self.assertEqual(identity.subject, SUBJECT_A)

    def test_malformed_token_is_rejected(self):
        verifier = SupabaseTokenVerifier(settings())
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify("not.a.jwt")
        self.assertEqual(raised.exception.code, "invalid_token")
        self.assertEqual(raised.exception.status_code, 401)

    def test_invalid_signature_is_rejected(self):
        verifier = SupabaseTokenVerifier(settings())
        wrong = make_token(secret="different-secret-value-that-is-long-enough")
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify(wrong)
        self.assertEqual(raised.exception.code, "invalid_token")

    def test_expired_token_is_rejected(self):
        verifier = SupabaseTokenVerifier(settings())
        expired = make_token(
            iat=datetime.now(timezone.utc) - timedelta(hours=2),
            exp=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify(expired)
        self.assertEqual(raised.exception.code, "expired_token")

    def test_wrong_audience_is_rejected(self):
        verifier = SupabaseTokenVerifier(settings())
        token = make_token(audience="another-audience")
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify(token)
        self.assertEqual(raised.exception.code, "invalid_token")

    def test_missing_subject_is_rejected(self):
        verifier = SupabaseTokenVerifier(settings())
        token = pyjwt.encode(
            {
                "aud": TEST_AUDIENCE,
                "exp": datetime.now(timezone.utc) + timedelta(hours=1),
                "iss": ISSUER,
            },
            TEST_SECRET,
            algorithm="HS256",
        )
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify(token)
        self.assertEqual(raised.exception.code, "invalid_token")

    def test_non_uuid_subject_is_rejected(self):
        verifier = SupabaseTokenVerifier(settings())
        token = make_token(subject="not-a-uuid")
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify(token)
        self.assertEqual(raised.exception.code, "invalid_token")

    def test_token_without_expiration_is_rejected(self):
        token = pyjwt.encode(
            {
                "aud": TEST_AUDIENCE,
                "sub": str(SUBJECT_A),
                "iss": ISSUER,
            },
            TEST_SECRET,
            algorithm="HS256",
        )
        with self.assertRaises(AuthenticationError) as raised:
            SupabaseTokenVerifier(settings()).verify(token)
        self.assertEqual(raised.exception.code, "invalid_token")

    def test_issuer_is_verified_when_url_is_configured(self):
        verifier = SupabaseTokenVerifier(settings())
        token = make_token(issuer="https://unrelated.supabase.co/auth/v1")
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify(token)
        self.assertEqual(raised.exception.code, "invalid_token")

    def test_issuer_is_not_required_when_url_is_missing(self):
        verifier = SupabaseTokenVerifier(
            SupabaseAuthSettings(jwt_secret=TEST_SECRET, audience=TEST_AUDIENCE)
        )
        identity = verifier.verify(make_token(issuer="https://unrelated.supabase.co/auth/v1"))
        self.assertEqual(identity.subject, SUBJECT_A)

    def test_error_messages_never_contain_token_or_secret(self):
        verifier = SupabaseTokenVerifier(settings())
        secret_secret = "super-secret-value-42-abcdefghijklmnopqrstuvwxyz"
        token = make_token(secret=secret_secret, audience="wrong")
        for call in (
            lambda: verifier.verify("garbage.token.value"),
            lambda: verifier.verify(token),
            lambda: verifier.verify(make_token(exp=datetime.now(timezone.utc) - timedelta(minutes=1))),
        ):
            try:
                call()
                self.fail("expected AuthenticationError")
            except AuthenticationError as raised:
                message = str(raised)
                self.assertNotIn("garbage.token.value", message)
                self.assertNotIn(token, message)
                self.assertNotIn(secret_secret, message)
                self.assertNotIn(TEST_SECRET, message)


class FakeUserRepository:
    def __init__(self, user=None):
        self.user = user
        self.lookups = []

    def get_by_supabase_uid(self, supabase_uid):
        self.lookups.append(supabase_uid)
        return self.user


class FakeMembershipRepository:
    def __init__(self, memberships=None):
        self.memberships = memberships or []
        self.calls = []

    def list_active_for_user(self, user_id):
        self.calls.append(user_id)
        return self.memberships


def active_membership(tenant_id, role="member"):
    return {"id": UUID(int=0), "tenant_id": tenant_id, "role": role, "status": "active"}


class TenantMembershipResolverTests(unittest.TestCase):
    def identity(self, subject=SUBJECT_A):
        return AuthenticatedIdentity(subject=subject)

    def resolver(self, user=None, memberships=None):
        return TenantMembershipResolver(
            FakeUserRepository(user),
            FakeMembershipRepository(memberships),
        )

    def test_identity_without_local_user_has_no_membership(self):
        with self.assertRaises(APIError) as raised:
            self.resolver().resolve(self.identity())
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.code, "tenant_membership_required")

    def test_user_without_active_membership_is_rejected(self):
        with self.assertRaises(APIError) as raised:
            self.resolver(user={"id": UUID(int=1)}, memberships=[]).resolve(self.identity())
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.code, "tenant_membership_required")

    def test_single_membership_resolves_without_selection(self):
        resolver = self.resolver(
            user={"id": UUID(int=1)},
            memberships=[active_membership(TENANT_A)],
        )
        context = resolver.resolve(self.identity())
        self.assertEqual(context, TenantContext(TENANT_A))

    def test_single_membership_matches_requested_tenant(self):
        resolver = self.resolver(
            user={"id": UUID(int=1)},
            memberships=[active_membership(TENANT_A)],
        )
        context = resolver.resolve(self.identity(), requested_tenant_id=TENANT_A)
        self.assertEqual(context, TenantContext(TENANT_A))

    def test_requesting_unrelated_tenant_is_rejected(self):
        resolver = self.resolver(
            user={"id": UUID(int=1)},
            memberships=[active_membership(TENANT_A)],
        )
        with self.assertRaises(APIError) as raised:
            resolver.resolve(self.identity(), requested_tenant_id=TENANT_B)
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(raised.exception.code, "tenant_not_member")

    def test_multi_membership_requires_explicit_selection(self):
        resolver = self.resolver(
            user={"id": UUID(int=1)},
            memberships=[active_membership(TENANT_A), active_membership(TENANT_B)],
        )
        with self.assertRaises(APIError) as raised:
            resolver.resolve(self.identity())
        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.code, "tenant_selection_required")

    def test_multi_membership_resolves_selected_tenant(self):
        resolver = self.resolver(
            user={"id": UUID(int=1)},
            memberships=[active_membership(TENANT_A), active_membership(TENANT_B)],
        )
        context = resolver.resolve(self.identity(), requested_tenant_id=TENANT_B)
        self.assertEqual(context, TenantContext(TENANT_B))

    def test_resolved_tenant_context_matches_verified_membership(self):
        resolver = self.resolver(
            user={"id": UUID(int=1)},
            memberships=[active_membership(TENANT_B)],
        )
        context = resolver.resolve(self.identity(), requested_tenant_id=TENANT_B)
        self.assertEqual(context.tenant_id, TENANT_B)

    def test_membership_errors_never_leak_identity_or_tenant_information(self):
        with self.assertRaises(APIError) as raised:
            self.resolver(user=None).resolve(self.identity())
        self.assertNotIn(str(SUBJECT_A), str(raised.exception))
        self.assertNotIn("secret", str(raised.exception))


if __name__ == "__main__":
    unittest.main()