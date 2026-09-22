# Phase 1.8 — Application/API Boundary

> Minimal FastAPI application boundary above the validated Phase 1.6/1.7
> domain/application service layer. Authentication, production identity, and a
> complete product API remain intentionally outside this phase.

## Status

**Complete — 2026-09-19.** The HTTP boundary, explicit development/test tenant
context, schemas, controlled error mapping, focused resource endpoints, API
tests, and live PostgreSQL integration validation are implemented and verified.
Phase 1.9 has not started.

## Architecture and responsibilities

The implemented request path is:

```text
HTTP Request
  -> FastAPI API/application boundary
  -> existing domain/application services
  -> existing psycopg repositories
  -> PostgreSQL
```

### API/application boundary

`xportra/api/` is responsible for:

- creating the FastAPI application and wiring startup state;
- registering the focused API router;
- resolving the service container as a request dependency;
- translating JSON/path/header input into explicit Pydantic schemas;
- converting the explicit development/test tenant header into `TenantContext`;
- mapping domain, validation, integrity, and unexpected failures to stable HTTP
  responses; and
- serializing service results through API response schemas.

The API does not execute SQL, open database connections, inspect repository
models, or implement domain/compliance rules.

### Domain/application services

The existing `xportra.domain` services remain responsible for:

- tenant-aware coordination and preconditions;
- same-tenant exporter/product and evidence/requirement checks;
- certification exporter and authority checks;
- date-window business rules;
- translating persistence integrity failures to domain-facing errors; and
- transaction boundaries for multi-write operations.

The API invokes service methods only. In particular,
`ComplianceEvidenceService.record_with_requirements()` remains the owner of the
atomic evidence-plus-requirement transaction.

### Persistence and PostgreSQL

The existing `xportra.persistence` layer remains responsible for SQL,
parameter binding, tenant predicates, connection cleanup, transaction context
management, and integrity-error capture. PostgreSQL remains the owner of
primary/foreign-key, uniqueness, status, and date-window constraints.

## Application structure

- `xportra/api/app.py` — application factory, lifespan startup, router
  registration, and exception-handler registration.
- `xportra/api/dependencies.py` — `ApplicationServices` container and explicit
  development/test tenant-context dependency.
- `xportra/api/router.py` — small service-backed resource router.
- `xportra/api/schemas.py` — explicit request and response schemas.
- `xportra/api/errors.py` — API error type and controlled exception handlers.
- `xportra/api/__init__.py` — package exports.

The default application object is `xportra.api.app:app`. `create_app()` accepts
an `ApplicationServices` instance so API tests can inject service spies without
changing production wiring.

## Tenant-context flow and trust boundary

The phase uses the explicit header:

```text
X-Development-Tenant-ID: <UUID>
```

The dependency:

1. rejects the mechanism when `APP_ENV=production`;
2. requires a non-empty UUID in development/test;
3. constructs the existing immutable `xportra.persistence.tenant.TenantContext`;
4. passes that value unchanged into every tenant-owned service call.

This is deliberately **not authentication**. It does not establish user
identity, membership, JWT validity, RBAC, or production authorization. It exists
only to make the missing trust boundary visible while validating the API/service
path. Production exposure requires a separately approved authenticated tenant
context mechanism.

## Endpoints

All endpoints require `X-Development-Tenant-ID` in development/test.

| Method | Path | Service operation |
| --- | --- | --- |
| `POST` | `/exporters` | `ExporterService.create` |
| `GET` | `/exporters/{exporter_id}` | `ExporterService.get` |
| `POST` | `/products` | `ProductService.create` |
| `GET` | `/products/{product_id}` | `ProductService.get` |
| `POST` | `/destination-markets` | `DestinationMarketService.register` |
| `GET` | `/destination-markets/{destination_id}` | `DestinationMarketService.get` |
| `POST` | `/compliance-evidence` | `ComplianceEvidenceService.record` |
| `GET` | `/compliance-evidence/{evidence_id}` | `ComplianceEvidenceService.get` |
| `POST` | `/compliance-evidence/with-requirements` | `ComplianceEvidenceService.record_with_requirements` |
| `POST` | `/compliance-evidence/{evidence_id}/requirements` | `ComplianceEvidenceService.associate_requirement` |
| `POST` | `/certifications-permits-licenses` | `CertificationService.record` |
| `GET` | `/certifications-permits-licenses/{certificate_id}` | `CertificationService.get` |

The surface is intentionally small and does not expose repository methods
automatically.

## Request/response schema strategy

`xportra/api/schemas.py` defines separate request and response models. Requests
use `extra="forbid"` and validate:

- required fields;
- basic string/list/object structure;
- UUID identifiers;
- date and datetime fields; and
- non-empty required names/references.

Status and domain-specific values are not duplicated as API business rules;
existing service preconditions and PostgreSQL constraints remain authoritative.
Responses are explicit API models rather than repository/database model
exposure.

## Error mapping

| Condition | HTTP status | API error code | Internal handling |
| --- | ---: | --- | --- |
| Missing development/test tenant context | 400 | `tenant_context_required` | `APIError` |
| Malformed JSON, missing fields, invalid UUID/date | 422 | `validation_error` | `RequestValidationError` handler |
| Tenant-scoped resource missing | 404 | `resource_not_found` | `DomainNotFoundError` handler |
| Domain/business-rule violation | 409 | `domain_validation_error` | `DomainValidationError` handler |
| Persistence integrity failure | 409 | `integrity_error` | `DomainPersistenceError` handler |
| Unexpected exception | 500 | `internal_error` | generic handler; internal cause/trace retained for logs |

Error responses do not include PostgreSQL connection strings, SQL, constraint
text, stack traces, or secret values. The original exception cause chain remains
available internally.

## Transaction ownership

The API route for `/compliance-evidence/with-requirements` only unpacks the
validated request and calls `ComplianceEvidenceService.record_with_requirements`.
The service opens one `Database.transaction()`, creates evidence, creates every
requirement association, and commits or rolls back as one unit. No transaction
logic was added to the route handler.

## Tests and validation

### API unit tests

Command:

```powershell
.venv\Scripts\python.exe -m unittest tests.unit.test_api -v
```

Result: **7 tests passed**.

Coverage includes valid service calls, all focused resource routes, malformed
and missing fields, unknown fields, invalid identifiers/dates, explicit tenant
context, tenant isolation, cross-tenant relationships, not-found/domain/
integrity/unexpected error mapping, production disablement of the development
tenant mechanism, and evidence service dispatch.

### API PostgreSQL integration tests

Command:

```powershell
$line = Get-Content '.env' | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1
$env:DATABASE_URL = $line.Substring('DATABASE_URL='.Length).Trim()
.venv\Scripts\python.exe -m unittest tests.integration.test_api_postgresql -v
```

Result: **6 tests passed** against the Supabase PostgreSQL development/test
database.

Coverage includes live service-backed creation/retrieval, tenant A own-resource
access, Tenant A denial of Tenant B resources, cross-tenant product/certificate/
evidence relationship rejection, not-found/domain/integrity mapping without
database-detail leakage, malformed/missing request rejection, unexpected-error
sanitization, and atomic evidence-plus-requirement rollback/commit behavior.

### Existing regression suites

- Domain-service unit tests: **7 passed**.
- Phase 1.7 PostgreSQL domain-service integration tests: **8 passed**.
- Persistence unit tests: **5 passed**.
- Phase 1.5 PostgreSQL persistence integration tests: **6 passed**.

### Other validation

- Python compilation (`python -m compileall -q xportra tests`): **passed**.
- Dependency validation (`python -m pip check`): **passed; no broken
  requirements found**.
- Application import/startup validation (`from xportra.api.app import app,
  create_app` and TestClient lifespan use): **passed**.
- Final Phase 1.8 cleanup verification: dedicated API test tenants, exporters,
  products, destinations, evidence, certifications, and requirements were
  removed by test teardown.

The FastAPI TestClient emitted a non-failing Starlette deprecation warning about
the local `httpx`/TestClient combination; it did not affect test results.

## Defects discovered and corrected

The first live API integration run found that
`ComplianceEvidenceService` had no retrieval method even though the repository
supported tenant-scoped evidence retrieval and the API boundary required it.
The minimal service method `ComplianceEvidenceService.get()` was added without
changing repository or transaction behavior. The full validation matrix passed
on rerun.

Destination-market and certification retrieval methods were also added at the
existing service boundary to support the intentionally small retrieval surface.

## Deferred decisions and scope confirmation

Requirement tenancy remains unresolved. Authentication, Supabase Auth, JWT,
production user identity, RBAC, authorization policy, frontend/UI, RAG, LLM,
vector database, document ingestion, retrieval, regulatory intelligence,
AI-generated guidance, background workers, deployment infrastructure, new
domain entities, commodity taxonomy/HS coding, evidence-ingestion strategy, and
requirement-normalization strategy remain deferred or out of scope.

No Phase 1.9 work was started. Phase 1.8 is complete.
