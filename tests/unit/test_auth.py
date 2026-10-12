from datetime import datetime, timedelta, timezone
import base64
import json
import unittest
from uuid import UUID

import jwt as pyjwt
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from xportra.api.auth import (
    AuthConfigurationError,
    AuthenticatedIdentity,
    JwksKeyStore,
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


EC_KID_A = "phase-10-9-test-ec-key-a"
EC_KID_B = "phase-10-9-test-ec-key-b"
EC_KID_UNKNOWN = "phase-10-9-test-ec-key-unknown"


def make_ec_key():
    """Generate a fresh P-256 private key. Test-only; never persisted."""
    return ec.generate_private_key(ec.SECP256R1())


def ec_public_jwks_entry(private_key, kid, **overrides):
    entry = json.loads(ECAlgorithm.to_jwk(private_key.public_key()))
    entry.update({"kid": kid, "alg": "ES256", "use": "sig"})
    entry.update(overrides)
    return entry


def make_es256_token(private_key, kid, issuer=ISSUER, **overrides):
    now = datetime.now(timezone.utc)
    payload = {
        "aud": TEST_AUDIENCE,
        "role": "authenticated",
        "sub": str(SUBJECT_A),
        "email": "user-a@example.invalid",
        "iat": now,
        "exp": now + timedelta(hours=1),
        "iss": issuer,
    }
    payload.update(overrides)
    return pyjwt.encode(payload, private_key, algorithm="ES256", headers={"kid": kid})


class FakeClock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def recording_fetcher(script, calls):
    """Build a JWKS fetcher replaying ``script`` items (document or error)."""
    state = {"index": 0}

    def fetch(url):
        calls.append(url)
        item = script[min(state["index"], len(script) - 1)]
        state["index"] += 1
        if isinstance(item, Exception):
            raise item
        return item

    return fetch


def es_settings(url=TEST_URL, ttl_seconds=600.0):
    return SupabaseAuthSettings(
        jwt_secret=TEST_SECRET,
        audience=TEST_AUDIENCE,
        supabase_url=url,
        jwks_cache_ttl_seconds=ttl_seconds,
    )


def es_verifier(script, settings=None, clock=None):
    calls: list = []
    store = JwksKeyStore(
        (settings or es_settings()).jwks_url or TEST_URL,
        cache_ttl_seconds=(settings or es_settings()).jwks_cache_ttl_seconds,
        fetcher=recording_fetcher(script, calls),
        clock=clock,
    )
    verifier = SupabaseTokenVerifier(settings or es_settings(), jwks_store=store)
    return verifier, calls


class Es256VerificationTests(unittest.TestCase):
    def test_valid_es256_token_is_accepted(self):
        private_key = make_ec_key()
        document = {"keys": [ec_public_jwks_entry(private_key, EC_KID_A)]}
        verifier, _ = es_verifier([document])
        identity = verifier.verify(make_es256_token(private_key, EC_KID_A))
        self.assertEqual(identity, AuthenticatedIdentity(SUBJECT_A, "user-a@example.invalid"))

    def test_tampered_es256_signature_is_rejected(self):
        private_key = make_ec_key()
        document = {"keys": [ec_public_jwks_entry(private_key, EC_KID_A)]}
        verifier, _ = es_verifier([document])
        token = make_es256_token(private_key, EC_KID_A)
        head, payload, signature = token.split(".")
        tampered = signature[:-1] + ("A" if signature[-1] != "A" else "B")
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify(head + "." + payload + "." + tampered)
        self.assertEqual(raised.exception.code, "invalid_token")

    def test_es256_token_from_another_key_is_rejected(self):
        signing_key = make_ec_key()
        other_key = make_ec_key()
        document = {"keys": [ec_public_jwks_entry(other_key, EC_KID_A)]}
        verifier, _ = es_verifier([document])
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify(make_es256_token(signing_key, EC_KID_A))
        self.assertEqual(raised.exception.code, "invalid_token")

    def test_expired_es256_token_is_rejected(self):
        private_key = make_ec_key()
        document = {"keys": [ec_public_jwks_entry(private_key, EC_KID_A)]}
        verifier, _ = es_verifier([document])
        token = make_es256_token(
            private_key,
            EC_KID_A,
            iat=datetime.now(timezone.utc) - timedelta(hours=2),
            exp=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify(token)
        self.assertEqual(raised.exception.code, "expired_token")

    def test_es256_wrong_audience_issuer_and_subject_are_rejected(self):
        private_key = make_ec_key()
        document = {"keys": [ec_public_jwks_entry(private_key, EC_KID_A)]}
        cases = [
            make_es256_token(private_key, EC_KID_A, aud="another-audience"),
            make_es256_token(
                private_key, EC_KID_A, issuer="https://unrelated.supabase.co/auth/v1"
            ),
            make_es256_token(private_key, EC_KID_A, sub="not-a-uuid"),
        ]
        for token in cases:
            verifier, _ = es_verifier([document])
            with self.subTest(token=token[:20]):
                with self.assertRaises(AuthenticationError) as raised:
                    verifier.verify(token)
                self.assertEqual(raised.exception.code, "invalid_token")

    def test_es256_without_configured_project_url_fails_closed(self):
        private_key = make_ec_key()
        document = {"keys": [ec_public_jwks_entry(private_key, EC_KID_A)]}
        locked = SupabaseAuthSettings(jwt_secret=TEST_SECRET, audience=TEST_AUDIENCE)
        self.assertIsNone(locked.jwks_url)
        store = JwksKeyStore(
            TEST_URL, fetcher=recording_fetcher([document], [])
        )
        with self.assertRaises(AuthenticationError) as raised:
            SupabaseTokenVerifier(locked, jwks_store=store).verify(
                make_es256_token(private_key, EC_KID_A)
            )
        self.assertEqual(raised.exception.code, "invalid_token")

    def test_es256_missing_kid_is_rejected(self):
        private_key = make_ec_key()
        document = {"keys": [ec_public_jwks_entry(private_key, EC_KID_A)]}
        verifier, _ = es_verifier([document])
        now = datetime.now(timezone.utc)
        token = pyjwt.encode(
            {
                "aud": TEST_AUDIENCE,
                "sub": str(SUBJECT_A),
                "iat": now,
                "exp": now + timedelta(hours=1),
                "iss": ISSUER,
            },
            private_key,
            algorithm="ES256",
        )
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify(token)
        self.assertEqual(raised.exception.code, "invalid_token")


class JwksCacheAndRotationTests(unittest.TestCase):
    def test_unknown_kid_refreshes_once_then_rejects(self):
        key_a = make_ec_key()
        document = {"keys": [ec_public_jwks_entry(key_a, EC_KID_A)]}
        verifier, calls = es_verifier([document, document])
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify(make_es256_token(make_ec_key(), EC_KID_UNKNOWN))
        self.assertEqual(raised.exception.code, "invalid_token")
        self.assertEqual(len(calls), 2)

    def test_rotated_key_arriving_on_refresh_is_accepted(self):
        key_a, key_b = make_ec_key(), make_ec_key()
        before = {"keys": [ec_public_jwks_entry(key_a, EC_KID_A)]}
        after = {"keys": [ec_public_jwks_entry(key_b, EC_KID_B)]}
        verifier, calls = es_verifier([before, after])
        identity = verifier.verify(make_es256_token(key_b, EC_KID_B))
        self.assertEqual(identity.subject, SUBJECT_A)
        self.assertEqual(len(calls), 2)

    def test_jwks_outage_with_no_cache_fails_closed(self):
        verifier, calls = es_verifier([RuntimeError("simulated JWKS outage")])
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify(make_es256_token(make_ec_key(), EC_KID_A))
        self.assertEqual(raised.exception.code, "invalid_token")
        self.assertTrue(calls)

    def test_malformed_jwks_document_fails_closed(self):
        verifier, _ = es_verifier([{"unexpected": "shape"}])
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify(make_es256_token(make_ec_key(), EC_KID_A))
        self.assertEqual(raised.exception.code, "invalid_token")

    def test_cached_keys_are_bounded_by_ttl(self):
        clock = FakeClock()
        private_key = make_ec_key()
        document = {"keys": [ec_public_jwks_entry(private_key, EC_KID_A)]}
        verifier, calls = es_verifier([document], clock=clock)
        verifier.verify(make_es256_token(private_key, EC_KID_A))
        verifier.verify(make_es256_token(private_key, EC_KID_A))
        self.assertEqual(len(calls), 1)
        clock.advance(601.0)
        verifier.verify(make_es256_token(private_key, EC_KID_A))
        self.assertEqual(len(calls), 2)

    def test_fresh_cache_tolerates_a_transient_outage(self):
        clock = FakeClock()
        private_key = make_ec_key()
        calls: list = []
        store = JwksKeyStore(
            TEST_URL,
            fetcher=recording_fetcher(
                [{"keys": [ec_public_jwks_entry(private_key, EC_KID_A)]}], calls
            ),
            clock=clock,
        )
        verifier = SupabaseTokenVerifier(es_settings(), jwks_store=store)
        verifier.verify(make_es256_token(private_key, EC_KID_A))
        store._fetcher = recording_fetcher([RuntimeError("outage")], calls)
        verifier.verify(make_es256_token(private_key, EC_KID_A))
        self.assertEqual(len(calls), 1)

    def test_expired_cache_with_outage_fails_closed(self):
        clock = FakeClock()
        private_key = make_ec_key()
        calls: list = []
        store = JwksKeyStore(
            TEST_URL,
            fetcher=recording_fetcher(
                [{"keys": [ec_public_jwks_entry(private_key, EC_KID_A)]}], calls
            ),
            clock=clock,
        )
        verifier = SupabaseTokenVerifier(es_settings(), jwks_store=store)
        verifier.verify(make_es256_token(private_key, EC_KID_A))
        clock.advance(601.0)
        store._fetcher = recording_fetcher([RuntimeError("outage")], calls)
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify(make_es256_token(private_key, EC_KID_A))
        self.assertEqual(raised.exception.code, "invalid_token")

    def test_removed_key_stops_verifying_after_cache_expiry(self):
        clock = FakeClock()
        key_a, key_b = make_ec_key(), make_ec_key()
        calls: list = []
        store = JwksKeyStore(
            TEST_URL,
            fetcher=recording_fetcher(
                [
                    {
                        "keys": [
                            ec_public_jwks_entry(key_a, EC_KID_A),
                            ec_public_jwks_entry(key_b, EC_KID_B),
                        ]
                    }
                ],
                calls,
            ),
            clock=clock,
        )
        verifier = SupabaseTokenVerifier(es_settings(), jwks_store=store)
        verifier.verify(make_es256_token(key_b, EC_KID_B))
        clock.advance(601.0)
        store._fetcher = recording_fetcher(
            [{"keys": [ec_public_jwks_entry(key_a, EC_KID_A)]}], calls
        )
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify(make_es256_token(key_b, EC_KID_B))
        self.assertEqual(raised.exception.code, "invalid_token")


class AlgorithmConfusionTests(unittest.TestCase):
    def test_unsupported_algorithms_are_rejected(self):
        private_key = make_ec_key()
        document = {"keys": [ec_public_jwks_entry(private_key, EC_KID_A)]}
        header = {"alg": "RS256", "typ": "JWT"}

        def segment(value):
            return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

        forged = segment(header) + "." + segment({"aud": TEST_AUDIENCE}) + "." + "AA"
        none_token = segment({"alg": "none"}) + "." + segment({"aud": TEST_AUDIENCE}) + "."
        for token in (forged, none_token):
            verifier, _ = es_verifier([document])
            with self.subTest(token=token[:24]):
                with self.assertRaises(AuthenticationError) as raised:
                    verifier.verify(token)
                self.assertEqual(raised.exception.code, "invalid_token")

    def test_hs256_ignores_jwks_keys_and_uses_only_the_secret(self):
        private_key = make_ec_key()
        document = {"keys": [ec_public_jwks_entry(private_key, EC_KID_A)]}
        verifier, calls = es_verifier([document, document])
        # A valid HS256 token verifies without any JWKS involvement.
        identity = verifier.verify(make_token())
        self.assertEqual(identity.subject, SUBJECT_A)
        self.assertEqual(calls, [])
        # An HS256 token with the wrong secret is rejected even though
        # JWKS keys are available: the HS256 path never consults them.
        wrong = make_token(secret="different-secret-value-that-is-long-enough")
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify(wrong)
        self.assertEqual(raised.exception.code, "invalid_token")
        self.assertEqual(calls, [])

    def test_non_ec_jwks_entries_never_verify(self):
        signing_key = make_ec_key()
        document = {
            "keys": [
                {
                    "kty": "oct",
                    "kid": EC_KID_A,
                    "alg": "HS256",
                    "k": "dGVzdC1zeW1tZXRyaWMtc2VjcmV0LXZhbHVl",
                },
                {
                    "kty": "EC",
                    "kid": "wrong-curve-key",
                    "alg": "ES256",
                    "crv": "P-999",
                    "x": "AA",
                    "y": "BB",
                },
                {
                    "kty": "EC",
                    "kid": "wrong-alg-key",
                    "alg": "RS256",
                    "crv": "P-256",
                    "x": "AA",
                    "y": "BB",
                },
            ]
        }
        token = make_es256_token(signing_key, EC_KID_A)
        verifier, _ = es_verifier([document, document])
        with self.assertRaises(AuthenticationError) as raised:
            verifier.verify(token)
        self.assertEqual(raised.exception.code, "invalid_token")

    def test_hs256_path_makes_no_jwks_call(self):
        def forbidden_fetcher(url):
            raise AssertionError("HS256 verification must not fetch JWKS")

        store = JwksKeyStore(TEST_URL, fetcher=forbidden_fetcher)
        verifier = SupabaseTokenVerifier(settings(), jwks_store=store)
        identity = verifier.verify(make_token())
        self.assertEqual(identity.subject, SUBJECT_A)

    def test_es256_failures_never_expose_sensitive_material(self):
        private_key = make_ec_key()
        kid = "sensitive-kid-probe-value"
        document = {"keys": [ec_public_jwks_entry(private_key, EC_KID_A)]}
        token = make_es256_token(private_key, kid)
        verifier, _ = es_verifier([document, document])
        try:
            verifier.verify(token)
            self.fail("expected AuthenticationError")
        except AuthenticationError as raised:
            message = str(raised)
            self.assertNotIn(token, message)
            self.assertNotIn(kid, message)
            self.assertNotIn(TEST_SECRET, message)
            self.assertIsNone(raised.details)


if __name__ == "__main__":
    unittest.main()