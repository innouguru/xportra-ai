# Database Architecture & Schema Design — Xportra AI (Phase 1.2)

> Design-only database architecture for the approved Phase 1.1 domain model.
> No migrations, ORM models, database code, APIs, or application logic are introduced here.

## 1. Database architecture

### 1.1 Database technology

Use PostgreSQL as the project database engine, consistent with the approved Phase 0 technology baseline.

### 1.2 Schema and namespace strategy

Use a single PostgreSQL database with a dedicated application schema, for example `xportra`.

Rationale:
- keeps tenant-owned and shared/reference data logically separated without introducing an unnecessary multi-database architecture
- preserves simplicity for the current project stage
- keeps future database expansion manageable without locking the design into a provider-specific pattern

All application tables are created under the `xportra` schema, with table names kept in lowercase snake_case.

### 1.3 Tenant-isolation strategy

Tenant isolation is a first-class database concern.

- every tenant-owned table carries `tenant_id`
- tenant-owned rows must never be shared across tenants
- relational integrity enforces that a tenant-owned row cannot reference a row from another tenant
- association rows also carry `tenant_id` where the relationship is tenant-specific
- shared/reference tables remain tenant-neutral and are referenced by ID only

For tenant-owned tables, the recommended pattern is a composite foreign key:

- `tenant_id` + `id` on the child table referencing the parent table’s `tenant_id` and `id`

This makes cross-tenant references structurally impossible without a DB-level violation.

### 1.4 Shared/reference-data strategy

The following are shared/reference tables:

- `authorities`
- `regulatory_sources`
- any future canonical requirement catalog tables, if approved later

These tables are shared across tenants for reading, but tenant-owned records reference them by foreign key only. Shared records are never duplicated into tenant-owned tables as a substitute for proper reference keys.

### 1.5 Primary-key strategy

Use UUID primary keys for all core business tables.

Reasoning:
- stable identifiers across replication, external references, and future imports
- easier to correlate documents, sources, and provenance records
- safer than incremental integer IDs when cross-system references are introduced later

Use `UUID` or `UUIDv7`-style semantics if the project later adopts a database version that supports it; otherwise use standard UUID generation with a strong convention.

### 1.6 Foreign-key strategy

- all tenant-owned rows reference their owning tenant via `tenant_id`
- all tenant-owned child tables reference parent tenant-owned records using composite keys `(tenant_id, parent_id)`
- shared tables are referenced by ID without tenant scoping
- each tenant-owned row references shared records by shared ID only, never by a copied duplicate copy of the authority or source content

This preserves both referential integrity and tenant isolation.

### 1.7 Indexing strategy

Apply indexes only where the expected access patterns justify them:

- lookup by tenant and status
- lookup by tenant and owner IDs (exporter, product, destination)
- lookup by source and authority
- lookup by effective date and active-status filters
- lookup by created_at / updated_at for audit windows

Avoid speculative indexes on every column.

### 1.8 Uniqueness strategy

Use uniqueness strategically:

- `tenants.slug` unique
- `users.email` unique when local identity records exist
- `user_tenant_memberships` unique by `(tenant_id, user_id)`
- `exporters` unique by `(tenant_id, registration_number)` when registration number is present and meaningful
- `destination_markets` unique by `(tenant_id, country_code)`
- `regulatory_sources` unique by `(authority_id, version, effective_date)` or a unique publication identifier if one exists
- `requirements` unique by `(tenant_id, requirement_code)` when tenant-local; otherwise global requirement-code uniqueness may be enforced for shared catalog records

### 1.9 Timestamp strategy

Use consistent timestamp columns in UTC with `timestamptz`:

- `created_at`
- `updated_at`
- `deleted_at` for soft-deletion / archival flows

For historical state, maintain `effective_from` and `effective_to` on rows whose validity changes over time.

### 1.10 Deletion and archival strategy

Do not hard-delete operational business records.

Instead:
- use `status` values such as `active`, `inactive`, `superseded`, `archived`, `withdrawn`, `revoked`
- use `deleted_at` only when a record is intentionally removed from active workflows
- preserve the row for audit and provenance

This matches the approved domain model and prevents silent loss of regulatory and provenance history.

### 1.11 Transaction boundaries

The most important transaction boundaries are:

- creating a user membership and enforce tenant assignment in one transaction
- creating a requirement applicability record for an exporter/product/destination combination in one transaction
- creating evidence and linking it to requirements in one transaction
- updating a source or requirement lifecycle to `superseded` or `withdrawn` while also preserving historical records in the same transaction boundary

This keeps domain invariants consistent.

## 2. Canonical schema

### 2.1 Shared/reference tables

#### 2.1.1 `authorities`

Purpose: authoritative bodies or recognized regulatory institutions.

Columns:
- `id` UUID PK
- `name` TEXT NOT NULL
- `jurisdiction` TEXT NOT NULL
- `authority_type` TEXT NOT NULL CHECK (`authority_type` IN ('government','international','industry','other'))
- `status` TEXT NOT NULL CHECK (`status` IN ('active','historical','archived'))
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
- unique `(name, jurisdiction)`
- index on `(status, jurisdiction)`

#### 2.1.2 `regulatory_sources`

Purpose: a concrete publication, rule, notice, standard, or guidance document.

Columns:
- `id` UUID PK
- `authority_id` UUID NOT NULL FK -> `authorities.id`
- `jurisdiction` TEXT NOT NULL
- `title` TEXT NOT NULL
- `publication_date` DATE NULL
- `effective_date` DATE NULL
- `version` TEXT NULL
- `status` TEXT NOT NULL CHECK (`status` IN ('draft','active','superseded','withdrawn','archived'))
- `source_url` TEXT NULL
- `retrieval_timestamp` TIMESTAMPTZ NULL
- `supersedes_source_id` UUID NULL FK -> `regulatory_sources.id`
- `superseded_by_source_id` UUID NULL FK -> `regulatory_sources.id`
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
- unique `(authority_id, title, version, effective_date)` where version is present
- check: `supersedes_source_id` is not equal to `id`
- check: `superseded_by_source_id` is not equal to `id`
- check: if `superseded_by_source_id` is set, `status` cannot be `active`
- index on `(authority_id, status, effective_date)`
- index on `(status, effective_date)`

### 2.2 Tenant-owned tables

#### 2.2.1 `tenants`

Purpose: organizational owner boundary.

Columns:
- `id` UUID PK
- `legal_name` TEXT NOT NULL
- `slug` TEXT NOT NULL UNIQUE
- `status` TEXT NOT NULL CHECK (`status` IN ('active','suspended','archived'))
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

#### 2.2.2 `users`

Purpose: human actor identity record without embedding external identity provider internals.

Columns:
- `id` UUID PK
- `display_name` TEXT NOT NULL
- `email` TEXT NULL
- `status` TEXT NOT NULL CHECK (`status` IN ('active','invited','disabled','deleted'))
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
- unique `(email)` when email is present
- index on `(status)`

#### 2.2.3 `user_tenant_memberships`

Purpose: many-to-many mapping between users and tenants with tenant-scoped role assignment.

Columns:
- `id` UUID PK
- `tenant_id` UUID NOT NULL FK -> `tenants.id` ON DELETE CASCADE
- `user_id` UUID NOT NULL FK -> `users.id` ON DELETE CASCADE
- `role` TEXT NOT NULL
- `status` TEXT NOT NULL CHECK (`status` IN ('active','revoked','archived'))
- `added_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `removed_at` TIMESTAMPTZ NULL
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
- unique `(tenant_id, user_id)`
- check: `removed_at IS NULL OR removed_at >= added_at`
- index on `(tenant_id, status)`
- index on `(user_id, status)`

#### 2.2.4 `exporters`

Purpose: the exporter entity whose compliance position is being evaluated.

Columns:
- `id` UUID PK
- `tenant_id` UUID NOT NULL FK -> `tenants.id` ON DELETE RESTRICT
- `legal_name` TEXT NOT NULL
- `trading_name` TEXT NULL
- `registration_number` TEXT NULL
- `country_of_registration` TEXT NULL
- `status` TEXT NOT NULL CHECK (`status` IN ('active','inactive','archived'))
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
- unique `(tenant_id, registration_number)` where registration_number is not null
- index on `(tenant_id, status)`
- index on `(tenant_id, legal_name)`

#### 2.2.5 `products`

Purpose: exported commodity or item profile.

Columns:
- `id` UUID PK
- `tenant_id` UUID NOT NULL FK -> `tenants.id` ON DELETE RESTRICT
- `exporter_id` UUID NOT NULL FK -> `exporters.id` ON DELETE RESTRICT
- `product_name` TEXT NOT NULL
- `commodity_code` TEXT NULL
- `description` TEXT NULL
- `status` TEXT NOT NULL CHECK (`status` IN ('active','inactive','archived'))
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
- unique `(tenant_id, exporter_id, product_name)`
- composite FK `(tenant_id, exporter_id)` -> `(exporters.tenant_id, exporters.id)`
- index on `(tenant_id, exporter_id, status)`
- index on `(tenant_id, product_name)`

#### 2.2.6 `destination_markets`

Purpose: target destination market or country context.

Columns:
- `id` UUID PK
- `tenant_id` UUID NOT NULL FK -> `tenants.id` ON DELETE RESTRICT
- `country_code` TEXT NOT NULL
- `market_name` TEXT NOT NULL
- `regulatory_context` TEXT NULL
- `status` TEXT NOT NULL CHECK (`status` IN ('active','archived'))
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
- unique `(tenant_id, country_code)`
- index on `(tenant_id, status)`

### 2.3 Compliance and provenance tables

#### 2.3.1 `requirements`

Purpose: requirement definition or rule statement.

Columns:
- `id` UUID PK
- `tenant_id` UUID NULL
- `requirement_code` TEXT NOT NULL
- `title` TEXT NOT NULL
- `description` TEXT NOT NULL
- `applicability_logic_ref` TEXT NULL
- `status` TEXT NOT NULL CHECK (`status` IN ('draft','active','superseded','archived'))
- `effective_date` DATE NULL
- `version` TEXT NULL
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
- `tenant_id` is nullable only as a provisional placeholder for a deferred architectural decision; it is not a canonical decision that requirement records are global or tenant-local.
- if the project later approves tenant-local requirements, then `tenant_id` becomes NOT NULL and a tenant FK is enforced.
- if the project later approves shared canonical requirements, then `tenant_id` remains NULL and the requirement is treated as platform-shared, with a separate approval model.
- unique `(tenant_id, requirement_code, version)` when tenant-local
- index on `(status, effective_date)`
- index on `(tenant_id, status)`

Important: the requirement-tenancy model is explicitly deferred. The nullable `tenant_id` above is a temporary representation only and must not be read as a resolved architecture decision.

#### 2.3.2 `requirement_sources`

Purpose: links a requirement to one or more source records.

Columns:
- `id` UUID PK
- `tenant_id` UUID NULL
- `requirement_id` UUID NOT NULL FK -> `requirements.id` ON DELETE CASCADE
- `source_id` UUID NOT NULL FK -> `regulatory_sources.id` ON DELETE RESTRICT
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
- unique `(requirement_id, source_id)`
- if tenant-local requirement, `tenant_id` must equal the owning requirement tenant
- index on `(requirement_id, source_id)`
- index on `(source_id)`

#### 2.3.3 `requirement_applicability`

Purpose: explicit determination that a requirement applies to a particular exporter, product, and destination context.

Columns:
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `requirement_id` UUID NOT NULL
- `exporter_id` UUID NOT NULL
- `product_id` UUID NOT NULL
- `destination_id` UUID NOT NULL
- `applicability_status` TEXT NOT NULL CHECK (`applicability_status` IN ('required','not_required','unknown','inactive'))
- `reason_summary` TEXT NULL
- `effective_from` TIMESTAMPTZ NOT NULL
- `effective_to` TIMESTAMPTZ NULL
- `version` TEXT NULL
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
- composite FK `(tenant_id, requirement_id)` -> `(requirements.tenant_id, requirements.id)` if `tenant_id` is not null on requirement
- composite FK `(tenant_id, exporter_id)` -> `(exporters.tenant_id, exporters.id)`
- composite FK `(tenant_id, product_id)` -> `(products.tenant_id, products.id)`
- composite FK `(tenant_id, destination_id)` -> `(destination_markets.tenant_id, destination_markets.id)`
- unique `(tenant_id, requirement_id, exporter_id, product_id, destination_id)`
- check: `effective_to IS NULL OR effective_to >= effective_from`
- index on `(tenant_id, exporter_id, product_id, destination_id, applicability_status)`
- index on `(tenant_id, requirement_id, effective_from)`

#### 2.3.4 `compliance_evidence`

Purpose: evidence or supporting document associated with a requirement or compliance decision.

Columns:
- `id` UUID PK
- `tenant_id` UUID NOT NULL FK -> `tenants.id` ON DELETE RESTRICT
- `source_id` UUID NULL FK -> `regulatory_sources.id` ON DELETE RESTRICT
- `document_title` TEXT NOT NULL
- `document_type` TEXT NOT NULL
- `file_reference_or_uri` TEXT NOT NULL
- `content_hash` TEXT NULL
- `status` TEXT NOT NULL CHECK (`status` IN ('uploaded','reviewed','accepted','rejected','archived'))
- `uploaded_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
- index on `(tenant_id, source_id, status)`
- index on `(tenant_id, uploaded_at)`

#### 2.3.5 `evidence_requirements`

Purpose: explicit link between evidence and requirement.

Columns:
- `id` UUID PK
- `tenant_id` UUID NOT NULL
- `evidence_id` UUID NOT NULL FK -> `compliance_evidence.id` ON DELETE CASCADE
- `requirement_id` UUID NOT NULL FK -> `requirements.id` ON DELETE CASCADE
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
- unique `(tenant_id, evidence_id, requirement_id)`
- composite FK `(tenant_id, evidence_id)` -> `(compliance_evidence.tenant_id, compliance_evidence.id)`
- composite FK `(tenant_id, requirement_id)` -> `(requirements.tenant_id, requirements.id)` when requirement is tenant-scoped
- index on `(tenant_id, evidence_id)`
- index on `(tenant_id, requirement_id)`

#### 2.3.6 `certification_permit_licenses`

Purpose: formal approval or certification relevant to export compliance.

Columns:
- `id` UUID PK
- `tenant_id` UUID NOT NULL FK -> `tenants.id` ON DELETE RESTRICT
- `exporter_id` UUID NOT NULL FK -> `exporters.id` ON DELETE RESTRICT
- `issuing_authority_id` UUID NOT NULL FK -> `authorities.id` ON DELETE RESTRICT
- `title` TEXT NOT NULL
- `issue_date` DATE NULL
- `expiry_date` DATE NULL
- `status` TEXT NOT NULL CHECK (`status` IN ('issued','active','expired','revoked','archived'))
- `document_reference` TEXT NULL
- `created_at` TIMESTAMPTZ NOT NULL DEFAULT now()
- `updated_at` TIMESTAMPTZ NOT NULL DEFAULT now()

Constraints:
- composite FK `(tenant_id, exporter_id)` -> `(exporters.tenant_id, exporters.id)`
- index on `(tenant_id, exporter_id, status)`
- index on `(tenant_id, issuing_authority_id)`

## 3. Tenant isolation design

### 3.1 Tenant representation

`tenant_id` is represented as a UUID on every tenant-owned table and is always non-null.

### 3.2 How tenant ownership is enforced

- each tenant-owned record belongs to exactly one tenant
- child rows use composite foreign keys to ensure the same tenant owns both parent and child
- access-control logic and data access patterns rely on `tenant_id` as the boundary key, not only application logic

### 3.3 Prevention of cross-tenant references

This is enforced primarily through composite foreign keys and a strict rule that any tenant-owned child row must reference a parent row with the same `tenant_id`.

### 3.4 Tenant-scoped uniqueness

Examples:
- `tenants.slug` unique globally
- `exporters` unique per tenant by registration number when applicable
- `products` unique per tenant and exporter
- `destination_markets` unique per tenant and country
- `user_tenant_memberships` unique per `(tenant_id, user_id)`

### 3.5 Shared/reference records

Shared reference tables (`authorities`, `regulatory_sources`) are not tenant-owned. They may be read by many tenants, but tenant-owned tables reference them by ID only and do not duplicate their content.

### 3.6 Phase 0 architecture alignment

This architecture preserves the Phase 0 isolation principles:
- danger is handled at the data boundary, not left to API filtering alone
- shared regulatory metadata remains separately governed from tenant-specific applicability decisions
- tenant scoping is explicit and not inferred from business assumptions

## 4. Referential integrity and relationship mapping

### 4.1 Required behavior

- `ON DELETE RESTRICT` for tenant deletion when tenant-owned records exist
- `ON DELETE CASCADE` for association tables and clearly subordinate relationships
- `ON DELETE RESTRICT` for shared reference records to avoid accidental deletion of still-referenced source records
- `ON UPDATE` for IDs should be `NO ACTION` by default unless a DB engine-specific issue requires a different stable behavior; UUID keys should not be updated during normal operations

### 4.2 Relationship notes

- `user_tenant_memberships` links users to tenants and should be the authoritative association table; user rows themselves are not tenant-owned
- `requirement_applicability` is a tenant-scoped junction-like record that must remain tied to one exporter/product/destination context
- tenant-owned records referencing shared records must not copy source metadata into the tenant-owned row as a substitute for the foreign key
- provenance records should be treated as historical metadata rather than rewritten business state

## 5. Requirements and compliance data design

The schema is designed to support:

- source attribution via `requirement_sources` and `source_id` on evidence
- version/freshness tracking via `regulatory_sources.version`, `effective_date`, `status`, `publication_date`, `retrieval_timestamp`, and `supersedes_source_id`
- applicability context via `requirement_applicability`
- evidence traceability via `compliance_evidence` and `evidence_requirements`
- historical records via status fields and soft deletion instead of hard deletes

The schema is intentionally not designed for vector embeddings or retrieval tables. Those remain deferred to later phases.

## 6. Constraints and invariants mapped to enforcement location

### 6.1 Database constraint

These are best enforced in the database:
- `tenant_id` uniqueness and composite FKs for tenant ownership
- `status` enum or check constraints
- date ordering such as `effective_to >= effective_from`
- uniqueness on natural business keys
- `requirement_applicability` uniqueness per context

### 6.2 Database policy / trigger pattern

These are best handled by database policies or triggers where necessary:
- ensure `tenant_id` is consistent across linked rows in compound foreign keys
- enforce soft-delete behavior or archival transitions in a standardized way
- prevent source deactivation from silently leaving active requirement links without review

### 6.3 Application/domain logic

These should remain application-controlled:
- whether a requirement is `required` vs `not_required` under a given exporter/product/destination rule
- whether a source is authoritative enough to be used as primary legal guidance in a specific context
- business explanation text and reason summaries

### 6.4 Deferred workflow logic

These remain deferred because they are not purely structural:
- automatic supersession workflows
- regulatory review approval flows
- human override and exception handling
- cross-border regulatory interpretation workflows

## 7. Indexing plan aligned to real access patterns

At minimum, the initial schema should include indexes on:

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

These support the actual expected operations without speculative indexing on low-value fields.

## 8. Normalization and denormalization

### 8.1 Normalized structures

Keep these normalized:
- authority metadata
- regulatory source metadata
- requirement definition metadata
- exporter and product core data
- applicability records as separate data points rather than recomputing them inline
- evidence and requirement linkage as explicit tables

### 8.2 Deliberate denormalization

Only minimal denormalization should be used where it materially improves query performance without duplicating legal or regulatory truth.

Acceptable examples:
- cached human-readable display labels for source status or country code if later required
- summary counters for active records if there is a demonstrated need

These should be introduced only when justified by actual performance requirements.

### 8.3 Fields that must not be duplicated

- authority identity should not be copied into every requirement row without a foreign-key relationship
- source version and status metadata should not be duplicated into operational applicability records as a substitute for source linkage
- legal jurisdiction should be carried by the source or authority table, not pasted into every business record

## 9. Migration strategy (architectural level)

This migration strategy is design-only and is intentionally kept minimal; it does not create migration files.

### 9.1 Migration ordering

1. Create shared/reference tables first (`authorities`, `regulatory_sources`)
2. Create tenant boundary tables (`tenants`, `users`, `user_tenant_memberships`)
3. Create exporter/product and destination tables
4. Create requirement tables and source-link tables
5. Create applicability tables
6. Create evidence and certification tables
7. Add constraints, indexes, and trigger-based policies after baseline tables exist

### 9.2 Dependency ordering

- `regulatory_sources` depends on `authorities`
- `user_tenant_memberships` depends on `tenants` and `users`
- `products` depends on `exporters`
- `requirement_sources` depends on `requirements` and `regulatory_sources`
- `requirement_applicability` depends on `requirements`, `exporters`, `products`, and `destination_markets`
- `compliance_evidence` depends on `regulatory_sources` and `tenants`
- `evidence_requirements` depends on `compliance_evidence` and `requirements`
- `certification_permit_licenses` depends on `tenants`, `exporters`, and `authorities`

### 9.3 Reference-data initialization

- load baseline authorities before source records
- load initial regulatory source catalog after authority seed data exists
- keep all reference data versioned and reviewable
- do not seed tenant-owned records during the initial migration beyond the required reference catalog

### 9.4 Future schema-change strategy

- add new tables only when they correspond to approved domain changes
- preserve historical rows when lifecycle states change
- use additive migrations rather than rewriting existing core tables unless a genuine contradiction is identified
- avoid changing shared/reference data structures in a way that invalidates provenance or legal status metadata

### 9.5 Rollback expectations

- database rollback is expected only at the migration boundary, not as a way to remove business history
- archival and soft-delete states should protect provenance even when a rollback is required
- if a rollback is necessary, the database schema should revert in reverse dependency order, not by deleting historical rows that may be integral to audit continuity

## 10. Future compatibility without premature RAG design

This schema supports future expansion without committing to vector search or retrieval internals.

It is compatible with later work in:
- document ingestion
- source versioning
- requirement extraction
- evidence linking
- citations
- audit history
- changing regulatory requirements

This is achieved by separating:
- canonical records
- source records
- provenance metadata
- requirement applicability logic
- evidence linkage

The schema remains intentionally free of vector-embedding tables, chunk tables, or retrieval-specific storage structures.

## 11. Decisions intentionally deferred

The following are intentionally deferred and remain outside this phase:

- exact role permission taxonomy beyond the minimum membership model
- whether all requirement data is global or tenant-local
- exact commodity classification taxonomy and HS/coding integration
- any document chunking, embedding, or retrieval-persistence design
- exact business workflows for review, approval, and exception handling
- any external auth-provider identity mapping beyond a minimal local user record

These are deferred because they are not necessary to define the production-grade relational architecture for the approved domain model.
