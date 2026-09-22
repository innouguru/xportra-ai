# ADR-0004: Thin psycopg persistence boundary

- Status: Accepted
- Date: 2026-09-19
- Scope: Phase 1.4 database access and persistence

## Context

The Phase 1 database schema is implemented as PostgreSQL migrations, but the
repository had no application package, database driver, ORM, session boundary,
or persistence conventions. Phase 1.4 requires safe application access without
introducing a large framework or resolving deferred domain decisions.

## Decision

Use `psycopg` 3 as the direct PostgreSQL driver and keep SQL in a small
repository layer under `xportra.persistence`.

- `DatabaseSettings` reads `DATABASE_URL` from the established environment
  configuration and rejects missing configuration.
- `Database` opens short-lived connections and scopes writes to explicit
  transactions.
- `TenantContext` is required by tenant-owned repository operations.
- Repository queries bind tenant IDs as SQL parameters and preserve the
  database's composite foreign-key enforcement.
- Integrity failures are surfaced as `PersistenceIntegrityError` with the
  original database exception retained as the cause.
- No ORM, connection pool, API, authorization system, or domain service layer
  is introduced in this phase.

The dependency is declared in `pyproject.toml` as `psycopg[binary]>=3.2,<4`.

## Consequences

This keeps the persistence boundary small, explicit, PostgreSQL-compatible,
and easy to replace later if an approved requirement justifies another access
mechanism. Connection pooling, live PostgreSQL integration tests, and deployment
configuration remain environment concerns and are not invented here.

Requirement tenancy remains deferred. Requirement repositories accept either an
explicit tenant context or an explicit `None` for the existing global/local
placeholder and do not establish a final requirement ownership model.
