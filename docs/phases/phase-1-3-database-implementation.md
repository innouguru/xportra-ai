# Phase 1.3 — Database Implementation & Initial Migration

> PostgreSQL implementation of the approved Phase 1.2 schema.
> No ORM, API, application service, RAG, vector, embedding, chunking, or
> retrieval implementation is included.

## Implementation

The deterministic SQL migration is:

- `migrations/001_initial_schema.sql`
- `migrations/001_initial_schema.down.sql`

The migration creates the dedicated `xportra` schema and the 14 approved
Phase 1.2 tables:

- shared/reference: `authorities`, `regulatory_sources`
- tenant boundary: `tenants`, `users`, `user_tenant_memberships`
- tenant-owned: `exporters`, `products`, `destination_markets`,
  `requirements`, `requirement_sources`, `requirement_applicability`,
  `compliance_evidence`, `evidence_requirements`,
  `certification_permit_licenses`

It also creates the approved primary keys, foreign keys, composite
tenant-aware foreign keys, tenant-scoped uniqueness, lifecycle checks,
timestamps, update timestamp triggers, and Phase 1.2 indexes.

## Deferred requirement tenancy

`requirements.tenant_id` remains nullable. The migration does not decide
whether requirements are global or tenant-local.

Because a nullable requirement owner cannot be represented by one composite
foreign key for both possible future models, the migration uses a regular
requirement foreign key plus `xportra.enforce_requirement_tenant_consistency()`
for requirement associations. Tenant-local requirements must match the
association tenant; shared requirements remain usable without selecting a
final tenancy model. This preserves the Phase 1.2 deferral while retaining
database-level consistency enforcement.

All other tenant-owned parent/child relationships use composite foreign keys
such as `(tenant_id, exporter_id)` to prevent cross-tenant references.

## Reference data

The up migration deterministically seeds only the six Nigerian government
authorities already named by the approved architecture:

- NAFDAC
- Nigeria Customs Service
- Nigerian Export Promotion Council
- Standards Organisation of Nigeria
- Federal Ministry of Agriculture and Food Security
- Nigeria Agricultural Quarantine Service

No regulatory source records or tenant-owned records are seeded.

## Rollback

The down migration drops the dedicated `xportra` schema with its dependent
objects in one transaction. It does not drop `pgcrypto`, because the extension
may be shared by other database objects and was not owned exclusively by this
migration.

## Validation

### Static validation completed locally

- migration file diagnostics: no errors reported
- structural check: all 14 approved tables present
- structural check: no destructive statement in the up migration
- structural check: no vector, embedding, chunk, retrieval-table, API, or
  application-service objects present
- repository check at Phase 1.3 completion: no Python files outside `.venv`

### Live Supabase development/test validation — passed

The Supabase project is being used only as the Xportra development/test
database. No production configuration or paid add-on was enabled.

- pre-migration inspection: `xportra` schema absent; zero existing Xportra
  objects; no unrelated objects were touched
- migration: `001_initial_schema.sql` applied successfully
- schema: `xportra` exists and contains exactly 14 expected tables
- unintended tables: none
- constraints: catalog reported 14 primary keys, 13 unique constraints,
  17 check constraints, and 26 foreign keys
- composite tenant-aware foreign keys: 6 present
- indexes: all 25 migration-defined named indexes present; PostgreSQL reports
  52 total catalog indexes including primary-key and unique-constraint indexes
- triggers: all 15 expected non-internal triggers present
- seed data: six authorities present with the six deterministic IDs; six total
  rows and six distinct IDs remained after repeating the exact seed statement
- same-tenant relationship: passed
- cross-tenant product reference: rejected by `ForeignKeyViolation`
- duplicate tenant registration: rejected by `UniqueViolation`
- invalid exporter status: rejected by `CheckViolation`
- invalid product parent: rejected by `ForeignKeyViolation`
- invalid membership user: rejected by `ForeignKeyViolation`
- invalid membership date window: rejected by `CheckViolation`
- temporary validation records: removed by transaction rollback
- rollback: `001_initial_schema.down.sql` succeeded; `xportra` was removed
- re-migration: up migration succeeded again and recreated 14 tables

### Migration correction discovered during live validation

The first live application correctly failed because the approved composite
foreign key from `requirement_applicability` to `(products.tenant_id,
products.id)` lacked a matching unique key on `products`. PostgreSQL rolled the
failed transaction back completely. The migration was corrected with the
minimal required `UNIQUE (tenant_id, id)` constraint on `products`, then the
up migration, catalog validation, rollback, and re-migration all passed.

Requirement tenancy remains explicitly deferred; live validation did not
require choosing global versus tenant-local requirements.
