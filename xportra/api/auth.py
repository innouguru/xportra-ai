"""Supabase Auth verification and tenant-identity resolution.

This module lives at the API/application boundary. It verifies Supabase Auth
access tokens using the Supabase project JWT secret (HS256 legacy tokens) or
the project's trusted JWKS endpoint (ES256 tokens from the asymmetric
signing-keys system), represents the authenticated identity, and resolves
the tenant context from the authenticated user's existing membership data.
Raw JWTs, HTTP headers, and request objects are never passed into domain
services; only the immutable ``TenantContext`` crosses the boundary.

Algorithm/key separation (R-10.9.3): the ``alg`` value read from the
*unverified* token header is used only to select a verification path, and
each path is pinned to its own key type — HS256 verifies exclusively with
the shared secret, ES256 exclusively with EC public keys resolved from the
trusted JWKS by ``kid``. Keys are never used across algorithms, and no
remote URL is ever taken from token content: the JWKS endpoint derives
solely from the configured ``SUPABASE_URL``.
"""

import json
import logging
import os
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import httpx
import jwt as pyjwt
from jwt.algorithms import ECAlgorithm

from xportra.persistence.repositories import (
    UserRepository,
    UserTenantMembershipRepository,
)
from xportra.persistence.tenant import TenantContext

from .errors import APIError, AuthenticationError

DEVELOPMENT_TENANT_HEADER = "X-Development-Tenant-ID"
TENANT_SELECTION_HEADER = "X-Xportra-Tenant-ID"

ACCESS_TOKEN_ISSUER_SUFFIX = "/auth/v1"

#: JWKS document path served by Supabase Auth for asymmetric signing keys.
JWKS_PATH_SUFFIX = "/auth/v1/.well-known/jwks.json"

#: How long a fetched JWKS key set is trusted before refresh. Bounded so
#: provider key rotation propagates; matches the documented Supabase edge
#: cache lifetime for the JWKS document.
JWKS_CACHE_TTL_SECONDS = 600.0

#: Network budget for one JWKS fetch. Verification fails closed on timeout.
JWKS_FETCH_TIMEOUT_SECONDS = 10.0

#: Server-side algorithm allowlist. No other ``alg`` is honored, whatever
#: an unverified token header claims.
SUPPORTED_ALGORITHMS = frozenset({"HS256", "ES256"})

#: The only elliptic curve accepted for ES256 verification keys. Supabase
#: asymmetric signing keys use NIST P-256.
ES256_CURVE = "P-256"

logger = logging.getLogger(__name__)


class AuthConfigurationError(ValueError):
    """Supabase authentication configuration is missing or incomplete."""


@dataclass(frozen=True, slots=True)
class SupabaseAuthSettings:
    jwt_secret: str
    audience: str = "authenticated"
    supabase_url: str | None = None
    jwks_cache_ttl_seconds: float = JWKS_CACHE_TTL_SECONDS

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "SupabaseAuthSettings":
        values = os.environ if environment is None else environment
        secret = values.get("SUPABASE_JWT_SECRET", "").strip()
        if not secret:
            raise AuthConfigurationError("SUPABASE_JWT_SECRET is required")
        audience = values.get("SUPABASE_JWT_AUDIENCE", "").strip() or "authenticated"
        url = values.get("SUPABASE_URL", "").strip() or None
        return cls(jwt_secret=secret, audience=audience, supabase_url=url)

    @property
    def jwks_url(self) -> str | None:
        """Trusted JWKS endpoint derived from ``SUPABASE_URL``.

        ``None`` when no project URL is configured; ES256 verification
        then has no trust root and fails closed. The URL never comes
        from token content.
        """
        if self.supabase_url is None:
            return None
        return self.supabase_url.rstrip("/") + JWKS_PATH_SUFFIX


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    subject: UUID
    email: str | None = None


@dataclass(frozen=True, slots=True)
class MemberContext:
    """Authenticated tenant context plus the membership role resolved server-side."""

    tenant: TenantContext
    role: str

    def __post_init__(self) -> None:
        if not isinstance(self.tenant, TenantContext):
            raise TypeError("tenant must be a TenantContext")
        if not isinstance(self.role, str) or not self.role.strip():
            raise ValueError("role must be a non-empty string")


class _JwksError(Exception):
    """Supabase JWKS keys are unavailable or unsuitable.

    Internal only: the verifier maps every instance to a generic
    ``invalid_token`` error without surfacing details, URLs, or key
    material.
    """


class _JwksKeyNotFound(_JwksError):
    """No cached or freshly fetched key matches the token's ``kid``."""


class _JwksUnavailable(_JwksError):
    """The JWKS document could not be fetched or parsed."""


def _fetch_jwks_document(url: str) -> dict[str, Any]:
    """Retrieve one JWKS document from the trusted endpoint."""
    response = httpx.get(url, timeout=JWKS_FETCH_TIMEOUT_SECONDS)
    response.raise_for_status()
    document = response.json()
    if not isinstance(document, dict):
        raise _JwksUnavailable()
    return document


def _parse_jwks_keys(document: Mapping[str, Any]) -> dict[str, Any]:
    """Index usable ES256 verification keys by ``kid``.

    Only NIST P-256 EC public keys are accepted. Symmetric (``oct``),
    RSA, wrong-curve, wrong-algorithm, or unparseable entries are
    skipped so they can never verify a token; a wholly malformed
    document fails the load.
    """
    if not isinstance(document, dict):
        raise _JwksUnavailable()
    entries = document.get("keys")
    if not isinstance(entries, list):
        raise _JwksUnavailable()
    keys: dict[str, Any] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        kid = entry.get("kid")
        if not isinstance(kid, str) or not kid:
            continue
        if entry.get("kty") != "EC":
            continue
        if entry.get("crv") != ES256_CURVE:
            continue
        entry_algorithm = entry.get("alg")
        if entry_algorithm is not None and entry_algorithm != "ES256":
            continue
        try:
            keys[kid] = ECAlgorithm.from_jwk(json.dumps(entry))
        except Exception:
            continue
    return keys


class JwksKeyStore:
    """Bounded cache of trusted Supabase JWKS verification keys.

    Keys come exclusively from the configured JWKS endpoint (fetched
    with ``httpx``); token content never selects keys, algorithms, or
    URLs. An unknown ``kid`` triggers at most one refresh before the
    lookup fails, so provider key rotation is tolerated while an
    unrecognized key still fails closed.
    """

    def __init__(
        self,
        jwks_url: str,
        *,
        cache_ttl_seconds: float = JWKS_CACHE_TTL_SECONDS,
        fetcher: Callable[[str], Mapping[str, Any]] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if not isinstance(jwks_url, str) or not jwks_url.strip():
            raise ValueError("jwks_url must be a non-empty string")
        if float(cache_ttl_seconds) <= 0:
            raise ValueError("cache_ttl_seconds must be positive")
        self._url = jwks_url
        self._ttl = float(cache_ttl_seconds)
        self._fetcher = fetcher or _fetch_jwks_document
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._keys: dict[str, Any] = {}
        self._expires_at = 0.0

    def get_key(self, kid: str) -> Any:
        """Return the cached EC public key for ``kid`` or raise."""
        with self._lock:
            keys = self._keys if self._clock() < self._expires_at else self._refresh_locked()
            if kid in keys:
                return keys[kid]
            # Controlled single refresh for rotation tolerance: a newly
            # rotated provider key verifies; a still-unknown key fails.
            keys = self._refresh_locked()
            if kid in keys:
                return keys[kid]
            raise _JwksKeyNotFound()

    def _refresh_locked(self) -> dict[str, Any]:
        try:
            document = self._fetcher(self._url)
            keys = _parse_jwks_keys(document)
        except _JwksError:
            raise
        except Exception as cause:
            # The endpoint URL carries only the (non-secret) project
            # reference; tokens, keys, and response bodies never log.
            logger.warning("Supabase JWKS refresh failed for %s", self._url)
            raise _JwksUnavailable() from cause
        self._keys = keys
        self._expires_at = self._clock() + self._ttl
        return keys


_JWKS_STORES: dict[tuple[str, float], JwksKeyStore] = {}
_JWKS_STORES_LOCK = threading.Lock()


def get_shared_jwks_store(
    jwks_url: str,
    cache_ttl_seconds: float = JWKS_CACHE_TTL_SECONDS,
) -> JwksKeyStore:
    """Return the process-wide JWKS cache for one endpoint.

    Request-scoped verifiers share this so the bounded cache is
    effective across requests. Tests should inject an explicit
    ``JwksKeyStore`` instead to stay hermetic.
    """
    key = (jwks_url, float(cache_ttl_seconds))
    with _JWKS_STORES_LOCK:
        store = _JWKS_STORES.get(key)
        if store is None:
            store = JwksKeyStore(jwks_url, cache_ttl_seconds=cache_ttl_seconds)
            _JWKS_STORES[key] = store
        return store


class SupabaseTokenVerifier:
    """Verify a Supabase Auth access token and extract the authenticated identity."""

    def __init__(
        self,
        settings: SupabaseAuthSettings,
        *,
        jwks_store: JwksKeyStore | None = None,
    ) -> None:
        self._settings = settings
        self._jwks_store = jwks_store

    def verify(self, token: str) -> AuthenticatedIdentity:
        try:
            header = pyjwt.get_unverified_header(token)
        except pyjwt.InvalidTokenError as cause:
            raise AuthenticationError(
                "invalid_token", "The access token is invalid"
            ) from cause
        algorithm = header.get("alg")
        if algorithm not in SUPPORTED_ALGORITHMS:
            raise AuthenticationError(
                "invalid_token", "The access token is invalid"
            )
        if algorithm == "HS256":
            # Legacy path: the shared secret only. JWKS keys are never
            # consulted here, so an ES256-shaped token cannot pass and
            # no network call is made for HS256 tokens.
            payload = self._verify_hs256(token)
        else:
            # ES256 path: JWKS-resolved EC keys only. The symmetric
            # secret is never consulted here.
            payload = self._verify_es256(token, header)
        if self._settings.supabase_url is not None:
            expected_issuer = (
                self._settings.supabase_url.rstrip("/") + ACCESS_TOKEN_ISSUER_SUFFIX
            )
            if payload.get("iss") != expected_issuer:
                raise AuthenticationError(
                    "invalid_token", "The access token is invalid"
                )
        return AuthenticatedIdentity(
            subject=self._subject(payload),
            email=payload.get("email"),
        )

    def _verify_hs256(self, token: str) -> dict[str, Any]:
        try:
            payload = pyjwt.decode(
                token,
                key=self._settings.jwt_secret,
                algorithms=["HS256"],
                audience=self._settings.audience,
                options={"require": ["exp", "sub"]},
            )
        except pyjwt.ExpiredSignatureError as cause:
            raise AuthenticationError(
                "expired_token", "The access token has expired"
            ) from cause
        except pyjwt.InvalidTokenError as cause:
            raise AuthenticationError(
                "invalid_token", "The access token is invalid"
            ) from cause
        return payload

    def _verify_es256(self, token: str, header: Mapping[str, Any]) -> dict[str, Any]:
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise AuthenticationError(
                "invalid_token", "The access token is invalid"
            )
        jwks_url = self._settings.jwks_url
        if jwks_url is None:
            # No trust root is configured; fail closed rather than
            # verifying against an unconfigured source.
            raise AuthenticationError(
                "invalid_token", "The access token is invalid"
            )
        store = self._jwks_store or get_shared_jwks_store(
            jwks_url, self._settings.jwks_cache_ttl_seconds
        )
        try:
            key = store.get_key(kid)
        except _JwksError as cause:
            raise AuthenticationError(
                "invalid_token", "The access token is invalid"
            ) from cause
        try:
            payload = pyjwt.decode(
                token,
                key=key,
                algorithms=["ES256"],
                audience=self._settings.audience,
                options={"require": ["exp", "sub"]},
            )
        except pyjwt.ExpiredSignatureError as cause:
            raise AuthenticationError(
                "expired_token", "The access token has expired"
            ) from cause
        except pyjwt.InvalidTokenError as cause:
            raise AuthenticationError(
                "invalid_token", "The access token is invalid"
            ) from cause
        return payload

    @staticmethod
    def _subject(payload: dict[str, Any]) -> UUID:
        try:
            return UUID(str(payload.get("sub")))
        except (ValueError, TypeError) as cause:
            raise AuthenticationError(
                "invalid_token",
                "The access token does not carry a valid user subject",
            ) from cause


class TenantMembershipResolver:
    """Resolve the authenticated user's ``TenantContext`` from membership data."""

    def __init__(
        self,
        users: UserRepository,
        memberships: UserTenantMembershipRepository,
    ) -> None:
        self._users = users
        self._memberships = memberships

    def resolve(
        self,
        identity: AuthenticatedIdentity,
        requested_tenant_id: UUID | None = None,
    ) -> TenantContext:
        return self.resolve_member(identity, requested_tenant_id).tenant

    def resolve_member(
        self,
        identity: AuthenticatedIdentity,
        requested_tenant_id: UUID | None = None,
    ) -> MemberContext:
        user = self._users.get_by_supabase_uid(identity.subject)
        active = (
            self._memberships.list_active_for_user(user["id"])
            if user is not None
            else []
        )
        if not active:
            raise APIError(
                403,
                "tenant_membership_required",
                "The authenticated user has no active tenant membership",
            )
        selected = self._select_membership(active, requested_tenant_id)
        role = selected.get("role")
        if not isinstance(role, str) or not role.strip():
            raise APIError(
                403,
                "tenant_membership_required",
                "The authenticated user has no usable tenant membership role",
            )
        return MemberContext(TenantContext(selected["tenant_id"]), role)

    @staticmethod
    def _select_membership(
        memberships: list[dict[str, Any]],
        requested_tenant_id: UUID | None,
    ) -> dict[str, Any]:
        if requested_tenant_id is None:
            if len(memberships) == 1:
                return memberships[0]
            raise APIError(
                400,
                "tenant_selection_required",
                "The authenticated user belongs to multiple tenants; select one",
            )
        for membership in memberships:
            if membership["tenant_id"] == requested_tenant_id:
                return membership
        raise APIError(
            403,
            "tenant_not_member",
            "The authenticated user is not a member of the requested tenant",
        )