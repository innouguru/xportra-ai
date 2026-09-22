# Task: Phase 1.10 — Tenant-role Authorization Boundary

**Phase:** Phase 1 — Core Domain & Database
**Status:** In progress (2026-09-21)

## Objective

Add a small explicit tenant-role authorization boundary above the authenticated
tenant-membership boundary while preserving tenant isolation, domain-service
ownership, persistence boundaries, and service-owned transactions.

## Scope

- Resolve a server-side `MemberContext` containing `TenantContext` and the
  selected membership role.
- Define the initial `owner`/`member` API permission policy.
- Enforce route-level authorization before domain-service calls.
- Preserve the isolated non-production development tenant-header pathway with a
  synthetic owner role.
- Add focused unit and PostgreSQL integration tests.
- Document the boundary and update project/task state.

## Constraints

- Do not change domain services or persistence authorization behavior.
- Do not accept role or permission values from client payloads or headers.
- Do not introduce a new membership schema or permission table in this phase.
- Do not start Phase 2 or regulatory/RAG work.
- Unknown roles fail closed.

## Acceptance Criteria

- [ ] `MemberContext` carries the resolved tenant and membership role.
- [ ] Owner can perform all current Phase 1.8 operations.
- [ ] Member can read tenant-owned records and create/associate evidence.
- [ ] Member is denied exporter, product, destination-market, and
      certification/permit/license creation.
- [ ] Unknown roles are denied.
- [ ] Development-header requests receive a synthetic owner role only outside
      production.
- [ ] Authorization failures return generic `403 permission_denied` responses.
- [ ] Unit and PostgreSQL integration authorization tests pass.
- [ ] Regression, compilation, dependency, and startup/import checks pass.
- [ ] `docs/phases/phase-1-10-authorization-tenant-role-boundary.md`,
      `CURRENT_STATE.md`, task state, and the required ADR are updated.

## Verification

Pending.
