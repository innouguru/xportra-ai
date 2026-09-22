# Phase 1.7 — Domain Service Integration & Integrity Validation

> Live validation of the Phase 1.6 domain/application service layer against
> the Supabase PostgreSQL development/test database. No production database,
> schema redesign, API, authentication, authorization, RAG, LLM, ingestion,
> retrieval, deployment, or new domain entity was introduced.

## Environment and test architecture

- Database: Xportra Supabase PostgreSQL development/test environment
- Configuration: existing `DATABASE_URL` through `DatabaseSettings`
- Service path: `TenantContext -> domain service -> repository -> PostgreSQL`
- Test module: `tests/integration/test_domain_services_postgresql.py`
- Cleanup: deterministic Phase 1.7 slugs, names, and requirement codes; cleanup
  deletes only records owned by this suite and post-run queries verify absence
- Schema: existing Phase 1.3 migration state; no migration or schema reset run

## Live tests executed

Command:

```powershell
$line = Get-Content '.env' | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1
$env:DATABASE_URL = $line.Substring(13).Trim()
.venv\Scripts\python.exe -m unittest tests.integration.test_domain_services_postgresql -v
```

Result: **8 tests passed** against live Supabase PostgreSQL.

### Tenant isolation

- Tenant A retrieved its own exporter.
- Tenant A could not retrieve Tenant B's exporter through `ExporterService`.
- Product creation with Tenant A context and Tenant B's exporter was rejected
  by the service before persistence.
- Omitting tenant context was rejected by the service boundary.
- Evidence created for Tenant A could not be associated through Tenant B's
  context.
- A tenant-local Tenant B requirement could not be used by Tenant A.

### Business-rule validation

- Valid exporter/product creation succeeded.
- Product ownership was checked against the same-tenant exporter.
- Valid requirement applicability succeeded with exporter, product, destination,
  and the existing deferred global requirement representation.
- Applicability with a tenant-inaccessible requirement was rejected.
- Invalid applicability date windows were rejected by the domain service.
- Evidence association succeeded for valid evidence and requirement records.
- Certification recording succeeded for a valid exporter, seeded authority,
  and date window.
- Cross-tenant exporter, unknown authority, and invalid certification dates were
  rejected.

### Transaction atomicity

- Valid evidence plus requirement association committed both writes.
- An invalid second requirement caused `record_with_requirements()` to fail.
- The evidence insert and association writes rolled back together.
- No orphan evidence or partial evidence-requirement association remained.

### Persistence error handling

- Duplicate exporter registration reached PostgreSQL through the service path.
- The service exposed `DomainPersistenceError`.
- The original `PersistenceIntegrityError` and PostgreSQL `IntegrityError`
  remained available as causes.
- A subsequent repository operation succeeded after the failed write.

### Connection and cleanup behavior

- All 8 live tests passed using the existing connection/transaction boundary.
- Cleanup completed successfully after the corrected test teardown ordering.
- Final read-only cleanup verification reported zero remaining Phase 1.7:
  tenants, exporters, products, destinations, evidence, certifications, and
  requirements.

## Required validation results

- Phase 1.7 live integration tests: **8 passed**
- Existing domain-service unit tests: **7 passed**
- Existing persistence unit tests: **5 passed**
- Existing Phase 1.5 PostgreSQL integration tests: **6 passed**
- Python compilation: **passed**
- Dependency validation (`pip check`): **passed**

The first Phase 1.7 execution found only a test cleanup defect: tenant-local
requirements were not deleted before their parent tenants. The test cleanup
ordering was corrected; no production implementation defect was found, and the
full suite passed on rerun.

## Deferred decisions and scope

Requirement tenancy remains deferred. The tests intentionally use both the
existing global placeholder and a tenant-local test requirement only to verify
that tenant context is enforced; they do not select a final requirement model.
Role/permission design, commodity taxonomy, evidence ingestion, requirement
normalization, retrieval, RAG/vector architecture, and all other deferred
decisions remain unresolved.

Phase 1.7 is complete. Phase 1.8 must not begin.
