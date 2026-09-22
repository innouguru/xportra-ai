# Task: Phase 1.8 — Application/API Boundary

**Phase:** Phase 1 — Core Domain & Database
**Status:** In progress (2026-09-19)

## Objective

Establish the minimal FastAPI HTTP boundary above the validated domain/application
service layer while preserving tenant isolation, domain-rule ownership,
persistence boundaries, and service-owned transactions.

## Scope

- Application startup, router registration, dependency wiring, schemas, and
  controlled error handling.
- Explicit development/test tenant header converted to `TenantContext`.
- Service-backed endpoints for exporters, products, destination markets,
  compliance evidence, and certifications/permits/licenses.
- API unit and PostgreSQL integration tests, including atomic evidence behavior.
- Phase documentation, ADR, and project-state updates.

## Constraints

No authentication, authorization, frontend, RAG, LLM, vector database, ingestion,
retrieval, deployment infrastructure, new domain entities, or resolution of
deferred requirement tenancy. No transaction logic in route handlers.

## Acceptance Criteria

- [ ] FastAPI application and dependency container implemented.
- [ ] Explicit tenant-context flow and trust boundary documented.
- [ ] Minimal schemas and requested endpoints implemented.
- [ ] Controlled error mappings implemented and tested.
- [ ] Tenant isolation and cross-tenant relationship rejection verified.
- [ ] Service integration and atomic evidence operation verified.
- [ ] Required validation commands executed and results recorded.
- [ ] Documentation and task state updated.

## Verification

Pending.
