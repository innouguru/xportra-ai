# Phase 1.5 — Persistence Integration & Domain Integrity Tests

> Live integration validation of the Phase 1.4 persistence layer against the
> Supabase PostgreSQL development/test database. No production environment,
> API, authentication, authorization, RAG, vector, ingestion, or new domain
> entity was introduced.

## Environment

- Database: Xportra Supabase PostgreSQL development/test project
- Connection: existing `DATABASE_URL` through `DatabaseSettings`
- Driver: existing `psycopg` 3 persistence layer
- Migration state: Phase 1.3 schema already applied and validated
- Production impact: none; no production database or unrelated Supabase object
  was accessed or modified

## Integration-test architecture

`tests/integration/test_persistence_postgresql.py` uses the existing
repositories and `Database` transaction/connection boundaries. The suite:

- creates two dedicated test tenants through `TenantRepository`
- creates users, memberships, exporters, products, destinations, a global
  test requirement, and evidence through the existing repositories
- verifies tenant-scoped retrieval and association operations
- uses real PostgreSQL savepoints/transactions for expected failures
- uses deterministic test slugs and a fixed requirement code for cleanup
- removes only its own records in `tearDownClass`
- verifies cleanup with a separate read-only query after the test run

No schema reset, migration, destructive project-wide operation, or unrelated
record deletion is used.

## Tests implemented and executed

Command:

```powershell
$line = Get-Content '.env' | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1
$env:DATABASE_URL = $line.Substring(13).Trim()
.venv\Scripts\python.exe -m unittest tests.integration.test_persistence_postgresql -v
```

Result: **6 tests passed** against Supabase PostgreSQL.

### Tenant isolation

- Tenant A created and retrieved its own exporter.
- Tenant B created and retrieved its own exporter.
- Tenant A could not retrieve Tenant B's exporter through the tenant-scoped
  repository.
- A product using Tenant A with Tenant B's exporter was rejected by the live
  composite foreign key and surfaced as `PersistenceIntegrityError`.
- Omitting the tenant argument from a tenant-scoped repository operation raised
  `TypeError`.

### Referential integrity and associations

- Same-tenant exporter/product/destination relationships succeeded.
- Requirement applicability creation succeeded for the existing deferred
  global/local placeholder representation.
- Evidence-to-requirement association creation and retrieval succeeded.
- A product referencing a nonexistent exporter was rejected.
- The original PostgreSQL `IntegrityError` remained available as the wrapped
  exception cause.

### Constraint behavior

- Duplicate tenant-scoped exporter registration was rejected.
- Missing required exporter name was rejected.
- Invalid exporter status was rejected.
- Invalid applicability date window was rejected.
- Invalid foreign-key references were rejected.
- No integrity failure was silently swallowed.

### Transaction and connection behavior

- A successful explicit transaction committed and was observable afterward.
- A transaction containing a valid insert followed by an invalid insert rolled
  back the earlier insert.
- A failed transaction did not poison a subsequent connection or repository
  operation.
- Connection context cleanup closed connections after use.
- `SELECT 1` succeeded through a subsequent connection.

The current repository boundary exposes create, retrieve, list, and association
operations. It does not expose update methods, so no update test was invented.
Database update-trigger behavior was validated separately during Phase 1.3
catalog validation.

## Cleanup result

Post-test read-only checks reported:

- Phase 1.5 tenants remaining: `0`
- Phase 1.5 users remaining: `0`
- Phase 1.5 requirements remaining: `0`

No unrelated data was deleted.

## Unit and static validation

- Existing unit suite: 5 tests passed.
- Integration suite: 6 tests passed against live Supabase PostgreSQL.
- Persistence/test package compilation passed.
- No credentials were printed or written to test output.

## Deferred decisions and remaining limitations

Requirement tenancy remains explicitly deferred. The integration suite uses a
nullable/global placeholder requirement and does not decide whether canonical
requirements are global or tenant-local.

Role/permission design, commodity taxonomy, evidence ingestion workflow,
retrieval/vector persistence, and document chunking/embedding remain deferred.
Phase 1.5 does not add or resolve any of them.

The Supabase project is a development/test environment only. No production
hardening or deployment configuration was introduced.
