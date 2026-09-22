# Domain Model — Xportra AI (Phase 1.1)

> Canonical domain model for the production export-compliance intelligence platform.
> This document defines the domain concepts, relationships, invariants, and tenant boundaries that will guide later database design and implementation.
> No database tables, migrations, ORM models, or application code are introduced here.

## 1. Canonical domain concepts

### 1.1 Tenant

- Purpose: organizational boundary for production usage.
- Key attributes:
  - tenant_id
  - legal_name
  - slug
  - status
  - created_at
  - updated_at
- Identifiers: tenant_id (system-generated), slug (business key, unique within the platform)
- Relationships:
  - one tenant owns many users via membership records
  - one tenant owns many exporters
  - one tenant owns many compliance records and evidence records
- Lifecycle: active, suspended, archived
- Ownership: tenant-owned and isolated by default

### 1.2 User

- Purpose: human actor with access to the tenant workspace.
- Key attributes:
  - user_id
  - display_name
  - email
  - status
  - created_at
  - updated_at
- Identifiers: user_id
- Relationships:
  - many-to-many with tenant via membership
  - one user may have many role assignments within a tenant
- Lifecycle: active, invited, disabled, deleted
- Ownership: not tenant-owned as a global identity; authorization is tenant-scoped

### 1.3 UserTenantMembership

- Purpose: resolves the many-to-many relationship between user and tenant and carries tenant-scoped role assignments.
- Key attributes:
  - membership_id
  - tenant_id
  - user_id
  - role
  - status
  - added_at
  - removed_at
- Identifiers: membership_id
- Relationships:
  - many-to-one with Tenant
  - many-to-one with User
- Lifecycle: active, revoked, archived
- Ownership: tenant-owned

### 1.4 Exporter

- Purpose: the exporting entity whose compliance position is being evaluated.
- Key attributes:
  - exporter_id
  - tenant_id
  - legal_name
  - trading_name
  - registration_number
  - country_of_registration
  - status
  - created_at
  - updated_at
- Identifiers: exporter_id; tenant-level business keys may exist if needed later
- Relationships:
  - many-to-one with Tenant
  - one exporter owns many product profiles
  - one exporter owns many compliance cases or requirement analyses
  - one exporter may hold many permits/certificates
- Lifecycle: active, inactive, archived
- Ownership: tenant-owned

### 1.5 Product

- Purpose: the exportable commodity or product profile associated with a business or transaction.
- Key attributes:
  - product_id
  - tenant_id
  - exporter_id
  - product_name
  - commodity_code
  - description
  - product_status
  - created_at
  - updated_at
- Identifiers: product_id
- Relationships:
  - many-to-one with Exporter
  - many-to-many with destination markets through requirement applicability context or product-market records
  - one product may be linked to many requirements and evidence items
- Lifecycle: active, inactive, archived
- Ownership: tenant-owned

### 1.6 DestinationMarket

- Purpose: the target market or destination country for a shipment or export plan.
- Key attributes:
  - destination_id
  - tenant_id
  - country_code
  - market_name
  - regulatory_context
  - status
  - created_at
  - updated_at
- Identifiers: destination_id; country_code is a natural business key when scoped to tenant context
- Relationships:
  - many-to-one with Tenant
  - many requirement applicability records reference destination market
- Lifecycle: active, archived
- Ownership: tenant-owned

### 1.7 Authority

- Purpose: the governing or recognized source authority that issues or publishes a regulation or guidance.
- Key attributes:
  - authority_id
  - authority_name
  - jurisdiction
  - authority_type
  - status
  - created_at
  - updated_at
- Identifiers: authority_id
- Relationships:
  - one authority has many regulatory sources
  - one authority may govern many requirements
- Lifecycle: active, historical, archived
- Ownership: globally shared/reference data, with tenant-facing references only

### 1.8 RegulatorySource

- Purpose: the specific publication, standard, notice, regulation, or source document behind a rule or guidance.
- Key attributes:
  - source_id
  - authority_id
  - jurisdiction
  - title
  - publication_date
  - effective_date
  - version
  - status
  - source_url
  - retrieval_timestamp
  - supersedes_source_id
  - superseded_by_source_id
- Identifiers: source_id
- Relationships:
  - many-to-one with Authority
  - one source may be superseded by another source
  - a source may support many requirements or extracted requirement statements
- Lifecycle: draft, active, superseded, withdrawn, archived
- Ownership: globally shared/reference data, with tenant-specific references to source evidence unless the tenant owns a custom local copy

### 1.9 Requirement

- Purpose: the actionable export-compliance requirement that may apply to an exporter, product, or destination.
- Key attributes:
  - requirement_id
  - tenant_id (optional if globally shared canonical rules are introduced later)
  - requirement_code
  - title
  - description
  - applicability_logic_ref
  - status
  - effective_date
  - version
  - created_at
  - updated_at
- Identifiers: requirement_id; requirement_code where defined by the project
- Relationships:
  - many-to-one with Tenant if tenant-scoped requirements are introduced
  - many-to-one with Authority or RegulatorySource via requirement-to-source links
  - many requirement applicability records link to a requirement
- Lifecycle: draft, active, superseded, archived
- Ownership: tenant-owned if user-curated or local; shared/reference if canonical and project-wide

### 1.10 RequirementApplicability

- Purpose: explicit determination of whether a requirement is relevant to a given exporter/product/destination context.
- Key attributes:
  - applicability_id
  - requirement_id
  - exporter_id
  - product_id
  - destination_id
  - applicability_status
  - reason_summary
  - effective_from
  - effective_to
  - version
  - created_at
  - updated_at
- Identifiers: applicability_id
- Relationships:
  - many-to-one with Requirement
  - many-to-one with Exporter
  - many-to-one with Product
  - many-to-one with DestinationMarket
- Lifecycle: active, inactive, superseded, archived
- Ownership: tenant-owned

### 1.11 ComplianceEvidence

- Purpose: a document or artifact supporting a requirement, applicability decision, or compliance claim.
- Key attributes:
  - evidence_id
  - tenant_id
  - source_id
  - document_title
  - document_type
  - file_reference_or_uri
  - hash
  - status
  - uploaded_at
  - created_at
  - updated_at
- Identifiers: evidence_id
- Relationships:
  - many-to-one with Tenant
  - many-to-one with RegulatorySource when the evidence is sourced from an authority
  - many-to-many with Requirement via a requirement-evidence association
- Lifecycle: uploaded, reviewed, accepted, rejected, archived
- Ownership: tenant-owned for uploaded evidence; shared/reference when copied from an authority source

### 1.12 CertificationPermitLicense

- Purpose: a formal approval, license, permit, or certification relevant to export compliance.
- Key attributes:
  - certificate_id
  - tenant_id
  - exporter_id
  - title
  - issuing_authority_id
  - issue_date
  - expiry_date
  - status
  - document_reference
- Identifiers: certificate_id
- Relationships:
  - many-to-one with Exporter
  - many-to-one with Authority
  - may relate to applicable requirements or evidentiary records
- Lifecycle: issued, active, expired, revoked, archived
- Ownership: tenant-owned

## 2. Domain relationships and cardinality

### 2.1 One-to-one

- User-to-primary tenant membership is not a true one-to-one by design; a user may belong to multiple tenants; a tenant may have many users.
- A source document may have a single current version record, but the model should treat versioning as separate historical records rather than forcing a strict 1:1 identity assumption.

### 2.2 One-to-many

- Tenant -> UserTenantMembership
- Tenant -> Exporter
- Tenant -> DestinationMarket
- Authority -> RegulatorySource
- Exporter -> Product
- Exporter -> CertificationPermitLicense
- Requirement -> RequirementApplicability
- Source -> ComplianceEvidence (when evidence is sourced from that source)

### 2.3 Many-to-many

- User <-> Tenant via UserTenantMembership
- Requirement <-> Evidence via explicit association entity
- Product <-> DestinationMarket via applicability context or product-market mapping if a market-specific product matrix is required

### 2.4 Association entities to prefer

The following should be explicit association records rather than implicit array fields:

- UserTenantMembership
- RequirementApplicability
- RequirementEvidenceLink
- ProductMarketContext (if market-specific product relationships become necessary)

These association records make status changes, effective dates, provenance, and supersession explicit without overloading the primary domain entity.

## 3. Compliance domain design

This model is intentionally not tightly coupled to vector search or RAG. It aims to represent the compliance domain through explicit concepts and traceable relationships.

### 3.1 Required concepts

- Exporter: the regulated business entity
- Product/commodity: the goods being exported
- Destination country/market: the target jurisdiction for the export
- Requirement: the rule, condition, or compliance expectation
- Authority: the governing body or recognized source of authority
- RegulatorySource: actual publication or source document backing the requirement
- ComplianceEvidence: uploaded or source-backed documents supporting a claim or determination
- CertificationPermitLicense: a formal approval artifact relevant to the exporter
- RequirementApplicability: the rule stating when a requirement applies in context
- Provenance and versioning: every requirement and source should carry versioning and supersession metadata

### 3.2 Explicitly not required yet

The following are intentionally deferred because they represent implementation detail or product decision-making rather than core domain structure:

- vector index objects
- chunk or embedding records as canonical domain entities
- retrieval pipeline objects
- RAG prompt assembly models
- user-facing dossier objects that are specific to a workflow layer

These may be introduced later when the architecture is prepared for retrieval and reasoning stages.

## 4. Tenant and access boundaries

### 4.1 Tenant-owned entities

- Tenant
- UserTenantMembership
- Exporter
- Product
- DestinationMarket
- RequirementApplicability
- ComplianceEvidence
- CertificationPermitLicense
- Tenant-specific requirement records or custom local rules if introduced later

### 4.2 Shared/reference entities

- Authority
- RegulatorySource
- Canonical requirements if the project later establishes platform-wide authoritative requirements without tenant overrides

### 4.3 Required isolation rules

- Tenant-scoped records must never be visible to another tenant.
- Shared authority and source records may be read by many tenants, but their legal and provenance metadata must remain centrally managed.
- Access control must be enforced at the tenant boundary even when the same regulatory source is shared.
- Requirement applicability must remain tenant-scoped to preserve exporter-specific context and avoid cross-tenant leakage.

## 5. Identity and users

The minimum model needed is:

- Tenant: organization boundary
- User: system identity for human actors
- UserTenantMembership: tenant-scoped role assignment
- Role: a tenant-scoped authorization concept or enumerated permission set

This keeps the model independent from any external auth provider while still supporting multi-tenant access control. The project should not duplicate the auth provider’s internal identity model unless a later requirement specifically demands it.

## 6. Auditability and provenance

The following objects require metadata for auditability and traceability:

- RegulatorySource
- Requirement
- RequirementApplicability
- ComplianceEvidence
- CertificationPermitLicense
- Exporter and Product updates when they materially change compliance context

Required metadata:

- created_at
- updated_at
- created_by_user_id where actor is known
- updated_by_user_id where actor is known
- provenance source reference
- source version reference
- status / archival state
- soft delete or archival flag instead of hard deletion for operational records

### 6.1 Business data vs audit metadata

Business data includes:

- exporter name, product details, destination market, requirement definitions, evidence descriptions

Audit metadata includes:

- who created or changed the record
- when it changed
- which source or document version was used
- whether it was superseded, withdrawn, or archived

These must remain separate concerns so business records can evolve without losing the audit trail.

## 7. State machines

### 7.1 Exporter

- States: active, inactive, archived
- Valid transitions: active -> inactive -> archived; active -> archived; inactive -> active
- Invalid transitions: archived -> active without reactivation approval

### 7.2 Product

- States: active, inactive, archived
- Valid transitions: active -> inactive -> archived; inactive -> active

### 7.3 Requirement

- States: draft, active, superseded, archived
- Valid transitions: draft -> active -> superseded -> archived; active -> archived
- Invalid transitions: active -> draft without explicit reversion logic

### 7.4 RegulatorySource

- States: draft, active, superseded, withdrawn, archived
- Valid transitions: draft -> active -> superseded -> archived; active -> withdrawn
- Invalid transitions: any state to active without lifecycle review

### 7.5 ComplianceEvidence

- States: uploaded, reviewed, accepted, rejected, archived
- Valid transitions: uploaded -> reviewed -> accepted/rejected -> archived

## 8. Domain invariants

1. A requirement must not be treated as valid or current without a status and effective-date model.
2. A source must not be silently treated as equivalent to a primary legal authority when its authority tier is lower.
3. Requirement applicability must always be bound to a specific context: exporter, product, destination, and/or requirement; no requirement is globally “applicable” without context.
4. Evidence must be traceable to its source or originating document.
5. A tenant must never access another tenant’s exporter, product, evidence, or applicability records.
6. A deleted or archived record must preserve provenance and status history.
7. A superseded source or requirement must not silently remain current in business logic.
8. Any decision or recommendation generated from the system must be traceable to either a requirement, a source, and/or evidence.

## 9. Normalization boundaries

### 9.1 Normalize

- Authority names and jurisdiction data
- Country and destination market references
- Status enums and lifecycle states
- Source/version references and supersession links
- Common requirement categories or taxonomies if introduced later

### 9.2 Keep denormalized only when justified

- Short business summaries on requirement applicability
- Human-readable reason summaries
- Exporter-facing labels and display names

### 9.3 Fields that should not be duplicated

- source authority identity should not be copied into every requirement row without a reference key
- source version metadata should not be duplicated in operational business summaries without explicit provenance links
- tenant ownership and authorization metadata should not be embedded inside unrelated business data without access-control rules

### 9.4 Controlled vocabularies

These should be enum or lookup-based rather than free text:

- status
- authority type
- requirement status
- applicability status
- evidence type
- lifecycle state
- destination market state

## 10. Future RAG compatibility

This model is intentionally compatible with future retrieval and reasoning without designing for vector search yet.

It supports:

- authoritative compliance sources
- document ingestion and versioning
- extracted requirements or requirement statements
- lineage from source to requirement to evidence
- retrieval by authority, jurisdiction, source status, date range, and exporter context
- citations and evidence traceability
- future changes in regulations through supersession and effective dates

These capabilities are supported by explicit artifacts and provenance metadata, not by embedding the retrieval system directly into the domain model.

## 11. Decisions intentionally deferred

The following are intentionally deferred for later design approval:

- exact tenant authorization model beyond the minimum user/tenant/membership pattern
- whether requirement records are tenant-local or global canonical rules
- the precise taxonomy for product classifications and HS codes
- the exact evidence ingestion model for OCR, extracted text, and source-document versioning
- whether all regulatory material is stored as source records only or also as normalized requirement records
- any LLM or vector-specific persistence details

These items are deferred because they depend on later implementation scope and should not be guessed before Phase 1 requirements are approved.
