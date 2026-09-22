# Phase 1.4 — Database Access & Persistence Layer

> Minimal PostgreSQL persistence infrastructure for the approved Phase 1
> schema. No API, authentication flow, authorization system, domain decision
> logic, ingestion, retrieval, RAG, vector, or deployment functionality is
> included.

## Technology

Phase 1.4 uses `psycopg` 3 as a direct PostgreSQL driver, declared in
`pyproject.toml` as `psycopg[binary]>=3.2,<4`. This is the smallest
production-appropriate mechanism compatible with the existing PostgreSQL
baseline and avoids introducing an ORM or persistence framework. The choice is
recorded in `docs/decisions/ADR-0004-psycopg-persistence-boundary.md`.

## Connection and transaction architecture

- `xportra.persistence.database.DatabaseSettings` reads `DATABASE_URL` from
  the established environment configuration and rejects an empty value.
- `xportra.persistence.database.Database` opens a short-lived connection per
  operation and exposes an explicit transaction context for writes.
- Connection cleanup is handled by context managers.
- Successful writes commit when the transaction and connection scopes exit.
- Exceptions leave the transaction uncommitted and cause rollback during
  connection cleanup.
- No credentials are logged or stored in source code.

The implementation intentionally does not add connection pooling because no
application runtime or measured concurrency requirement exists yet.

## Tenant context and isolation

`TenantContext` is an immutable UUID-bearing value object. Tenant-owned
repository methods require it explicitly and bind its UUID in every query.
Reads cannot retrieve another tenant's record through the repository methods.
Writes cannot substitute a caller-provided tenant ID because the tenant ID is
obtained from the context object and composite foreign keys remain enforced by
PostgreSQL.

Global/reference repositories do not accept tenant context for:

- `Authority`
- `RegulatorySource`
- `User`

`Tenant` is the explicit organization-boundary operation. Membership and all
other tenant-owned records require `TenantContext`.

Requirement tenancy remains deferred. `RequirementRepository` and
`RequirementSourceRepository` accept either an explicit `TenantContext` or an
explicit `None`, matching the nullable Phase 1 schema representation. They do
not choose whether requirements are globally shared or tenant-local.

## Persistence operations

Implemented repositories cover the approved entities and association tables:

- Tenant
- User
- UserTenantMembership
- Exporter
- Product
- DestinationMarket
- Authority
- RegulatorySource
- Requirement
- RequirementSource
- RequirementApplicability
- ComplianceEvidence
- EvidenceRequirement
- CertificationPermitLicense

Operations are intentionally limited to creation, retrieval, listing where
needed for references/associations, and link creation. Business workflows,
state transitions, authorization, and compliance logic remain outside this
boundary.

## Error handling

All SQL is parameterized. Database integrity violations from writes are
converted to `PersistenceIntegrityError` with the original `psycopg` exception
retained as `__cause__`. This gives callers a stable persistence exception
without hiding the constraint failure. Other database errors propagate
unchanged.

## Testing

Completed without a live PostgreSQL database:

- `python -m unittest tests.unit.test_persistence -v`
- 5 tests passed
- persistence package compilation passed with `python -m compileall -q xportra`

The unit tests use connection/cursor fakes only to verify configuration
validation, parameterized tenant scoping, transaction cleanup, and integrity
error propagation. They do not claim PostgreSQL behavior.

Still requires a legitimate PostgreSQL environment:

- connection establishment against `DATABASE_URL`
- migration application before persistence use
- actual transaction commit/rollback behavior
- catalog and foreign-key enforcement
- live cross-tenant rejection behavior
- live constraint and seed-data behavior

Phase 1.3's PostgreSQL execution gap remains an environment/deployment
validation concern and is not reopened by Phase 1.4.

## Scope confirmation

No API, authentication flow, authorization/role system, RAG, vector database,
embedding, document ingestion, retrieval, LLM functionality, background
worker, deployment infrastructure, or new domain entity was added.
