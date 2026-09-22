# Phase 1.1 — Domain Model Definition

> This document records the approved canonical domain model for Phase 1.1.
> It is a design artifact only; no implementation work, migrations, ORM models, or code are introduced.

## Objective

Define the minimal production-grade domain model needed for Xportra AI to support export-compliance intelligence for Nigerian agricultural exporters, without prematurely coupling the design to retrieval, vector search, or implementation details.

## Canonical domain concepts

### Core business entities

1. Tenant
2. User
3. UserTenantMembership
4. Exporter
5. Product
6. DestinationMarket
7. Authority
8. RegulatorySource
9. Requirement
10. RequirementApplicability
11. ComplianceEvidence
12. CertificationPermitLicense

## Relationship summary

### One-to-many

- Tenant -> Exporter
- Tenant -> Product
- Tenant -> DestinationMarket
- Tenant -> ComplianceEvidence
- Tenant -> CertificationPermitLicense
- Authority -> RegulatorySource
- Exporter -> Product
- Exporter -> CertificationPermitLicense
- Requirement -> RequirementApplicability
- RegulatorySource -> ComplianceEvidence (when evidence is direct-source-backed)

### Many-to-many

- User <-> Tenant via UserTenantMembership
- Requirement <-> ComplianceEvidence via explicit association if the system later needs a formal requirement-evidence link
- Product <-> DestinationMarket if market-specific product context is required later

### Explicit association entities preferred

- UserTenantMembership
- RequirementApplicability
- RequirementEvidenceLink (deferred unless required later)
- ProductMarketContext (deferred unless required later)

## Business invariants

1. Tenant isolation must be enforced for all tenant-owned records.
2. Requirement applicability must be context-bound to exporter/product/destination and must not be treated as globally universal.
3. Source authority must be distinguished from source status and source freshness.
4. Evidence and requirement decisions must remain traceable to source metadata and publication/effective dates.
5. No requirement or source may silently remain active after being superseded or withdrawn.
6. A record must not be deleted without preserving its provenance and lifecycle status.
7. Cross-tenant visibility must not exist for tenant-owned records.
8. Any recommendation or guidance must be traceable to a source-backed requirement or evidence record.

## Tenant boundaries

### Tenant-owned

- Exporter
- Product
- DestinationMarket
- Product-market or exporter-market context records
- ComplianceEvidence
- CertificationPermitLicense
- RequirementApplicability
- UserTenantMembership

### Shared/reference

- Authority
- RegulatorySource
- Platform-wide canonical requirement metadata if later approved

## Auditability and provenance requirements

Every business record that can materially affect compliance guidance must support:

- created_at
- updated_at
- created_by_user_id or actor reference
- updated_by_user_id or actor reference
- source reference
- effective date
- status
- archival or soft-deletion state
- supersession metadata where applicable

## Provenance boundaries

- Business data: exporter, requirement, product, destination, evidence summary
- Audit metadata: who changed it, when, which source, which version, whether it was superseded or archived

## State machines

### Requirement

- draft -> active -> superseded -> archived
- active -> archived

### RegulatorySource

- draft -> active -> superseded -> withdrawn -> archived

### Exporter

- active -> inactive -> archived

### Evidence

- uploaded -> reviewed -> accepted/rejected -> archived

## Decisions intentionally deferred

- Exact role permissions model beyond tenant-scoped membership and role assignment
- Whether canonical requirement records are global or tenant-local
- Exact taxonomies for commodities and HS-style coding
- Exact ingestion pipeline details for OCR, extracted text, and source-document versioning
- Whether all regulatory content is stored as source records only or also as normalized requirement records
- Any LLM/vector-specific persistence decisions

## Phase 1.1 status

This domain model is intentionally small, coherent, and production-oriented. It is ready to guide Phase 1.2 work, but no implementation should begin until the next phase is explicitly approved and scoped.
