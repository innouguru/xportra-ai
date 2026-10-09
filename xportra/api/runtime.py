"""Production runtime environment boundary for the API layer.

Single home for the ``APP_ENV`` predicate and production startup
validation (Phase 10.1, R-10.1.1). Previously the production check was
inlined in several places with an implicit ``development`` default and
no startup pinning of the production configuration.

Trust model:

- ``development`` (default when unset/blank) and ``test`` keep the
  existing local behavior, including the isolated development-tenant
  pathway where already supported.
- ``production`` disables the development-tenant pathway, disables
  interactive API documentation, and requires explicit secrets with
  debug behavior off. Anything else is rejected as unknown.
- Production startup validation applies to the environment-composed
  application path (``create_app()`` without injected services).
  Explicitly injected service containers are the test/seam path and
  keep their existing behavior.
"""

import os
from collections.abc import Mapping
from urllib.parse import urlsplit

DEVELOPMENT_ENV_VALUE = "development"
TEST_ENV_VALUE = "test"
PRODUCTION_ENV_VALUE = "production"

KNOWN_APP_ENVS = frozenset(
    {DEVELOPMENT_ENV_VALUE, TEST_ENV_VALUE, PRODUCTION_ENV_VALUE}
)

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off", ""})


class ProductionConfigurationError(ValueError):
    """The runtime environment is misconfigured for production."""


#: Environment variable naming additional browser origins
#: allowed to call the API (comma-separated, no spaces
#: required). Optional everywhere; never a secret.
CORS_ALLOWED_ORIGINS_ENV = "CORS_ALLOWED_ORIGINS"

#: Local Vite development origins always permitted outside
#: production. Both loopback spellings are listed because
#: browsers treat `localhost` and `127.0.0.1` as distinct
#: origins even when they resolve to the same server.
LOCAL_DEVELOPMENT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)

#: Exact HTTP surface of the API boundary (GET + POST only).
CORS_ALLOWED_METHODS = ("GET", "POST")

#: Exact request headers the frontend sends: JSON bodies
#: plus the two authentication mechanisms (Bearer token,
#: development-tenant header). Nothing uses cookies, so
#: credentialed CORS is never enabled.
CORS_ALLOWED_HEADERS = (
    "Content-Type",
    "Authorization",
    "X-Development-Tenant-ID",
)

#: CORS preflight cache lifetime, in seconds.
CORS_PREFLIGHT_MAX_AGE = 600


def current_app_env(
    environment: Mapping[str, str] | None = None,
) -> str:
    """Return the normalized ``APP_ENV`` value (default ``development``)."""
    values = os.environ if environment is None else environment
    raw = values.get("APP_ENV", "")
    if not isinstance(raw, str) or not raw.strip():
        return DEVELOPMENT_ENV_VALUE
    return raw.strip().lower()


def is_production_environment(
    environment: Mapping[str, str] | None = None,
) -> bool:
    """True only when ``APP_ENV`` is explicitly ``production``."""
    return current_app_env(environment) == PRODUCTION_ENV_VALUE


def validate_app_env(
    environment: Mapping[str, str] | None = None,
) -> str:
    """Fail fast on unknown ``APP_ENV`` values; return the normalized value."""
    env = current_app_env(environment)
    if env not in KNOWN_APP_ENVS:
        raise ProductionConfigurationError(
            f"APP_ENV {env!r} is not a known environment"
        )
    return env


def is_debug_enabled(
    environment: Mapping[str, str] | None = None,
) -> bool:
    """Interpret the ``APP_DEBUG`` knob (unset/blank means off)."""
    values = os.environ if environment is None else environment
    raw = values.get("APP_DEBUG", "")
    if not isinstance(raw, str):
        return False
    return raw.strip().lower() in _TRUE_VALUES


def validate_production_environment(
    environment: Mapping[str, str] | None = None,
) -> None:
    """Pin down the required production configuration at startup.

    Requires ``SUPABASE_JWT_SECRET``, ``DATABASE_URL``, and
    ``SUPABASE_URL`` to be present and rejects ``APP_DEBUG`` enabled
    (or unparseable) so a production deployment can never boot with
    debug behavior, missing secrets, or unverifiable token issuers
    (``SUPABASE_URL`` pins the ``<url>/auth/v1`` issuer check in
    ``SupabaseTokenVerifier``). Also validates any configured CORS
    origins so a wildcard or malformed origin can never reach a
    running server. No connection is opened and no secret value is
    returned or logged.
    """
    values = os.environ if environment is None else environment
    env = validate_app_env(values)
    if env != PRODUCTION_ENV_VALUE:
        return
    secret = values.get("SUPABASE_JWT_SECRET", "")
    if not isinstance(secret, str) or not secret.strip():
        raise ProductionConfigurationError(
            "SUPABASE_JWT_SECRET is required in production"
        )
    dsn = values.get("DATABASE_URL", "")
    if not isinstance(dsn, str) or not dsn.strip():
        raise ProductionConfigurationError(
            "DATABASE_URL is required in production"
        )
    url = values.get("SUPABASE_URL", "")
    if not isinstance(url, str) or not url.strip():
        raise ProductionConfigurationError(
            "SUPABASE_URL is required in production"
        )
    raw_debug = values.get("APP_DEBUG", "")
    normalized = (
        raw_debug.strip().lower()
        if isinstance(raw_debug, str)
        else ""
    )
    if normalized not in _FALSE_VALUES:
        raise ProductionConfigurationError(
            "APP_DEBUG must be false (or unset) in production"
        )
    cors_allowed_origins(values)


def _parse_cors_origin(raw_value: str) -> str:
    """Normalize one configured origin or fail fast.

    Only explicit ``http(s)://host[:port]`` origins are
    accepted — no wildcards, userinfo, paths, queries, or
    fragments. Misconfiguration raises instead of silently
    permitting arbitrary origins.
    """
    value = raw_value.strip().rstrip("/")
    if not value or "*" in value:
        raise ProductionConfigurationError(
            "CORS origins must be explicit http(s) origins; "
            "wildcards are forbidden"
        )
    try:
        parts = urlsplit(value)
    except ValueError as cause:
        raise ProductionConfigurationError(
            f"CORS origin {raw_value.strip()!r} is malformed"
        ) from cause
    if parts.scheme not in ("http", "https"):
        raise ProductionConfigurationError(
            f"CORS origin {raw_value.strip()!r} must use http or https"
        )
    if not parts.hostname or "@" in parts.netloc:
        raise ProductionConfigurationError(
            f"CORS origin {raw_value.strip()!r} must be a bare host"
        )
    if parts.path not in ("", "/") or parts.query or parts.fragment:
        raise ProductionConfigurationError(
            f"CORS origin {raw_value.strip()!r} must not carry a path"
        )
    host = parts.hostname.lower()
    port = f":{parts.port}" if parts.port is not None else ""
    return f"{parts.scheme}://{host}{port}"


def _parse_cors_origins(raw: object) -> tuple[str, ...]:
    """Split, normalize, and de-duplicate a raw origins value."""
    if not isinstance(raw, str):
        raise ProductionConfigurationError(
            "CORS origins must be a comma-separated string"
        )
    origins: list[str] = []
    for piece in raw.split(","):
        if not piece.strip():
            continue
        origin = _parse_cors_origin(piece)
        if origin not in origins:
            origins.append(origin)
    return tuple(origins)


def cors_allowed_origins(
    environment: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Resolve the explicit browser-origin allowlist.

    Production uses only ``CORS_ALLOWED_ORIGINS`` and fails
    closed (no origins) when it is unset — browser access
    is enabled solely by explicit configuration, never by
    default. Development and test always permit the local
    Vite origins and additionally honor ``CORS_ALLOWED_ORIGINS``
    entries. Wildcards and malformed values raise in every
    environment so typos fail fast instead of widening access.
    """
    values = os.environ if environment is None else environment
    configured = _parse_cors_origins(
        values.get(CORS_ALLOWED_ORIGINS_ENV, ""))
    if is_production_environment(values):
        return configured
    return LOCAL_DEVELOPMENT_CORS_ORIGINS + tuple(
        origin for origin in configured
        if origin not in LOCAL_DEVELOPMENT_CORS_ORIGINS
    )


__all__ = [
    "CORS_ALLOWED_HEADERS",
    "CORS_ALLOWED_METHODS",
    "CORS_ALLOWED_ORIGINS_ENV",
    "CORS_PREFLIGHT_MAX_AGE",
    "DEVELOPMENT_ENV_VALUE",
    "KNOWN_APP_ENVS",
    "LOCAL_DEVELOPMENT_CORS_ORIGINS",
    "PRODUCTION_ENV_VALUE",
    "ProductionConfigurationError",
    "TEST_ENV_VALUE",
    "cors_allowed_origins",
    "current_app_env",
    "is_debug_enabled",
    "is_production_environment",
    "validate_app_env",
    "validate_production_environment",
]
