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

    Requires ``SUPABASE_JWT_SECRET`` and ``DATABASE_URL`` to be present
    and rejects ``APP_DEBUG`` enabled (or unparseable) so a production
    deployment can never boot with debug behavior or missing secrets.
    No connection is opened and no secret value is returned or logged.
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


__all__ = [
    "DEVELOPMENT_ENV_VALUE",
    "KNOWN_APP_ENVS",
    "PRODUCTION_ENV_VALUE",
    "ProductionConfigurationError",
    "TEST_ENV_VALUE",
    "current_app_env",
    "is_debug_enabled",
    "is_production_environment",
    "validate_app_env",
    "validate_production_environment",
]
