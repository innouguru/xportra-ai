# ADR-0005: FastAPI application boundary

- Status: Accepted
- Date: 2026-09-19
- Scope: Phase 1.8 application/API boundary

## Context

The validated domain/application services require an explicit `TenantContext`
and coordinate the existing PostgreSQL repositories. Xportra AI needs a small
HTTP boundary to prove that external requests are translated into service calls
without moving business rules, repository access, or transaction ownership into
route handlers.

Phase 1.8 is intentionally not a complete product API and does not implement
authentication or production user identity.

## Decision

Use FastAPI as the HTTP application framework and place the boundary under
`xportra.api`.

- A small application factory creates the FastAPI application, registers the
  router, configures exception handlers, and wires an `ApplicationServices`
  container during startup.
- API routes depend on the service container and an explicit development/test
  tenant header, `X-Development-Tenant-ID`.
- The tenant header is parsed into the existing immutable `TenantContext` and
  passed unchanged to domain services. It is not an authentication or
  authorization mechanism.
- Pydantic request and response schemas translate HTTP payloads at the boundary.
  They validate structure, required fields, basic types, UUID identifiers, and
  dates without duplicating domain rules.
- Routes call domain/application services only. Repositories and database
  transactions remain below the service layer.
- Domain, validation, integrity, and unexpected failures are mapped to stable,
  non-sensitive HTTP error responses while their exception cause chains remain
  available internally.

The minimal resource surface covers exporters, products, destination markets,
compliance evidence, and certification/permit/license records. Evidence can be
recorded with requirement associations through the existing atomic service
operation.

## Alternatives considered

1. **Put SQL or repository calls in routes.** Rejected because it would bypass
   tenant-aware service preconditions and duplicate persistence access patterns.
2. **Implement JWT, Supabase Auth, or RBAC now.** Rejected because authentication
   is explicitly outside Phase 1.8. A clearly named development/test tenant
   header makes the missing trust mechanism visible.
3. **Generate an API from repository models.** Rejected because it would expose
   persistence shapes and create an unnecessarily broad surface.
4. **Use a different application framework.** Rejected because FastAPI is the
   approved core runtime baseline and directly supports explicit schemas,
   dependency injection, and controlled exception handling.

## Consequences

- API tests can replace `ApplicationServices` with spies while integration tests
  use the real `TenantContext -> service -> repository -> PostgreSQL` path.
- The header mechanism is safe only for development/test use and must be
  replaced by an approved authentication/authorization boundary before
  production exposure.
- FastAPI and its HTTP test client are explicit project dependencies.
- No new domain entity, transaction implementation, authorization system, or
  production infrastructure is introduced.
- Requirement tenancy, authentication, frontend, ingestion, retrieval, RAG, and
  all other deferred decisions remain unchanged.

## Linked requirements and tasks

- `REQUIREMENTS.md`: SP-5, TB-2, and the Phase 1.8 task assignment.
- `ACTIVE_TASK.md`: Phase 1.8 — Application/API Boundary.
- `docs/phases/phase-1-8-api-application-boundary.md`: implementation and
  validation record.

## Supersession note

The development/test tenant-header mechanism described here is replaced for
normal API operation by the authenticated tenant identity boundary recorded in
`ADR-0006-supabase-authenticated-tenant-boundary.md` (Phase 1.9). The header
remains only as an isolated non-production fallback.
