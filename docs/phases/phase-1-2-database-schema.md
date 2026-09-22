# Phase 1.2 — Database Architecture & Schema Design

> Design-only schema proposal for the approved Phase 1.1 domain model.
> No implementation code, migrations, ORM models, APIs, or application logic are introduced.

## Objective

Translate the approved Phase 1.1 domain model into a production-grade relational database architecture that preserves tenant isolation, source provenance, and regulatory traceability without prematurely designing the retrieval or vector layer.

## Explicitly deferred decisions

The following Phase 1.1 decision remains intentionally deferred and is not resolved by this Phase 1.2 schema:

- whether canonical requirements are global or tenant-local

This design therefore uses a provisional nullable `tenant_id` representation on requirements to avoid silently locking the architecture. That representation is not a canonical decision; it is a placeholder to preserve schema flexibility until the requirement-tenancy decision is explicitly approved elsewhere.

## Database architecture decisions

- Database engine: PostgreSQL, per the approved Phase 0 architecture.
- Schema strategy: single application schema named `xportra` with lowercase snake_case table names.
- Tenant isolation: tenant-owned tables carry `tenant_id`; child rows use composite foreign keys to enforce cross-tenant prevention.
- Shared/reference-data strategy: `authorities` and `regulatory_sources` remain shared/reference tables.
- Primary-key strategy: UUID keys for core business tables.
- Foreign-key strategy: tenant-owned tables reference their data with composite `tenant_id + id` keys where needed.
- Indexing strategy: target actual lookup patterns only, especially tenant + status, exporter/product/destination filters, and source/requirement effective-date queries.
- Timestamp strategy: UTC `timestamptz` for created/updated timestamps and effective-date metadata.
- Deletion/archival strategy: soft delete and lifecycle status rather than hard delete for operational records.
- Transaction boundaries: require transactional writes for membership, applicability, evidence linkage, and supersession updates.

## Canonical tables

### Shared/reference tables

- `authorities`
- `regulatory_sources`

### Tenant-owned tables

- `tenants`
- `users`
- `user_tenant_memberships`
- `exporters`
- `products`
- `destination_markets`
- `requirements`
- `requirement_sources`
- `requirement_applicability`
- `compliance_evidence`
- `evidence_requirements`
- `certification_permit_licenses`

## Mandatory schema concerns

### Tenant isolation

- every tenant-owned table includes `tenant_id`
- tenant-owned rows cannot reference a record with a different `tenant_id`
- shared/reference data is not duplicated into tenant-owned tables
- `user_tenant_memberships` is the authority for user-to-tenant membership and carries tenant-scoped role assignment

### Referential integrity

- `tenant_id` and parent IDs are enforced through composite foreign keys where necessary
- `ON DELETE RESTRICT` is used for high-integrity parent references
- `ON DELETE CASCADE` is used for subordinate association tables
- `ON UPDATE NO ACTION` is the default expectation for UUID keys to avoid accidental identifier churn

### Provenance and auditability

- `regulatory_sources` includes publication date, effective date, status, source URL, retrieval timestamp, and supersession fields
- `requirements` carries status and effective-date metadata
- `requirement_applicability` carries effective-from and effective-to windows
- `compliance_evidence` tracks status, timestamps, and source links
- `deleted_at` and lifecycle status preserve historical integrity without losing auditability

## Important constraints and invariants

### Enforced in database

- tenant-scope uniqueness and composite foreign keys
- check constraints for allowed lifecycle statuses
- date ordering rules
- uniqueness on natural business keys where meaningful
- no orphaned association rows after delete events

### Enforced in application/domain logic

- whether a requirement is `required` or `not_required` in a given exporter/product/destination context
- whether a source is legally authoritative enough to be treated as a primary authority in a specific jurisdiction
- the reasoning summary behind an applicability decision
- approval and exception workflows

### Deferred workflow logic

- source review and approval queue
- automatic supersession workflows
- human override paths
- regulator-specific interpretation rules

## Indexes aligned to real access patterns

- `tenants(slug)`
- `user_tenant_memberships(tenant_id, user_id)`
- `exporters(tenant_id, status)`
- `products(tenant_id, exporter_id, status)`
- `destination_markets(tenant_id, country_code)`
- `regulatory_sources(authority_id, status, effective_date)`
- `requirements(tenant_id, status, effective_date)`
- `requirement_applicability(tenant_id, exporter_id, product_id, destination_id, applicability_status)`
- `requirement_applicability(tenant_id, requirement_id, effective_from)`
- `compliance_evidence(tenant_id, source_id, status)`
- `certification_permit_licenses(tenant_id, exporter_id, status)`

## Normalization decisions

- normalize authority, source, and requirement metadata
- normalize tenant ownership and applicability context
- keep evidence and applicability as separate explicit records rather than duplicating legal truth
- avoid duplicating authority/source metadata inside every tenant-owned row

## Future compatibility

This schema supports future phases without prematurely designing vector embeddings or retrieval tables. It allows later additions for:

- document ingestion
- source versioning
- requirement extraction
- evidence linking and citation history
- evolving regulatory requirements
- audit traceability

## Phase 1.2 status

This database architecture is ready to guide the next design phase, but it remains a design-only artifact. No implementation should begin until Phase 1.3 is explicitly approved and scoped.
