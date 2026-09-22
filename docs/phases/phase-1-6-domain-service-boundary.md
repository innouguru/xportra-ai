# Phase 1.6 — Domain Service & Business Rule Boundary

> Application/domain services above the Phase 1.4 persistence layer. No API,
> authentication, authorization, regulatory intelligence, RAG, vector,
> ingestion, or deployment functionality is included.

## Boundary

The service layer lives under `xportra.domain` and depends on persistence
interfaces/classes, while callers depend on service methods and domain errors.
Services receive `TenantContext` explicitly for every tenant-owned operation.
They do not infer tenant ownership from arbitrary record input or bypass
tenant-scoped repositories.

Implemented services:

- `ExporterService`: create and tenant-scoped retrieval
- `ProductService`: create/retrieve after verifying the exporter belongs to the
  same tenant
- `DestinationMarketService`: tenant-scoped market registration
- `RequirementApplicabilityService`: context-bound applicability recording
- `ComplianceEvidenceService`: evidence recording, requirement association, and
  atomic evidence-plus-requirements recording
- `CertificationService`: certification recording after exporter and authority
  existence checks

No new domain entities were added. Authority and regulatory-source reads remain
persistence concerns because this phase does not introduce source workflows.

## Rule ownership

### Database-owned invariants

The service layer relies on PostgreSQL for rules already represented in the
schema:

- primary/foreign-key integrity
- composite tenant-aware relationships
- tenant-scoped uniqueness
- required columns
- lifecycle/status checks
- effective-date check constraints

Services do not duplicate these constraints as a second source of truth.

### Persistence-owned concerns

The persistence layer owns:

- SQL and parameter binding
- connection/session cleanup
- transaction context management
- conversion of raw integrity failures to `PersistenceIntegrityError`
- tenant-scoped query predicates

### Domain/application-owned invariants

The service layer owns coordination and preconditions that span records:

- explicit `TenantContext` is required for tenant-owned operations
- a product must be associated with an exporter in the same tenant before the
  product is created
- applicability must have an exporter, product, destination, and requirement
  context in the same tenant scope
- a product must belong to the exporter used for applicability
- certification recording requires the exporter and issuing authority to exist
- evidence association requires evidence and requirement records to exist
- applicability and certification date windows are rejected before persistence
- evidence recording with requirement links requires at least one requirement

No regulatory applicability rule, authority-ranking rule, role/permission
rule, commodity classification rule, or compliance recommendation was added.

## Error boundary

`DomainValidationError` represents failed domain preconditions.
`DomainNotFoundError` represents a required missing record.
`DomainPersistenceError` translates `PersistenceIntegrityError` while retaining
it as the cause, so callers receive a domain-facing error without losing the
underlying database failure.

## Transactions

Single-write service operations use repository transaction boundaries.
`ComplianceEvidenceService.record_with_requirements()` uses one
`Database.transaction()` and transaction-aware evidence/link repository methods
so evidence creation and every requirement association commit or roll back as
one unit.

No distributed transaction, event bus, or speculative unit-of-work framework
was introduced.

## Testing

Added `tests/unit/test_domain_services.py` with 7 tests covering:

- explicit tenant-context enforcement
- tenant propagation to repositories
- same-tenant exporter/product preconditions
- applicability relationship validation
- persistence-error translation
- atomic multi-write rollback behavior
- required requirement association input

Executed:

```powershell
.venv\Scripts\python.exe -m unittest tests.unit.test_domain_services -v
```

Result: **7 tests passed**. Existing persistence unit tests and Phase 1.5 live
integration tests are not duplicated by this phase.

## Deferred decisions

Requirement tenancy remains deferred. The service layer accepts the existing
nullable/global-or-tenant requirement representation without selecting a final
model. Role/permission design, commodity taxonomy, evidence-ingestion
workflow, requirement normalization, RAG/vector architecture, document
ingestion, and retrieval strategy remain deferred.

## Scope status

Phase 1.6 is complete for the implemented domain boundary. Phase 1.7 must not
begin.
