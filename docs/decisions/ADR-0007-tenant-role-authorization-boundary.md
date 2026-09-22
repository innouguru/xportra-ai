# ADR-0007: Tenant-role authorization boundary

- Status: Accepted
- Date: 2026-09-21
- Scope: Phase 1.10 authorization above the authenticated tenant boundary

## Context

Phase 1.9 establishes a verified Supabase identity and resolves a tenant from the
authenticated user's active membership. Membership alone does not distinguish
tenant administration from ordinary member activity, so every authenticated
member can currently perform every Phase 1.8 operation in a selected tenant.

The existing `user_tenant_memberships.role` column is a tenant-scoped text value,
but no role taxonomy or permission matrix has been approved. This phase adds the
smallest explicit authorization boundary needed for the current API without
changing domain services, persistence, or the membership schema.

## Decision

Resolve a server-side `MemberContext` containing the existing immutable
`TenantContext` and the selected membership role. Apply authorization at the
FastAPI dependency boundary before a route invokes a domain service.

The initial role policy is:

- `owner` may perform every current Phase 1.8 operation in the selected tenant.
- `member` may read tenant-owned records and create compliance evidence, record
  evidence with requirement associations, and associate evidence with a
  requirement.
- `member` may not create exporters, products, destination markets, or
  certification/permit/license records.
- Unknown, missing, or malformed role values fail closed with
  `403 permission_denied`.

The role is read from the selected active membership; it is never accepted from
a request header, token claim, or API payload. The development/test tenant
header remains an isolated non-production pathway and receives a synthetic
server-side `owner` role. It remains rejected in production.

No membership-schema migration is introduced. The existing unconstrained role
column remains the source of the role value, and the exact long-term taxonomy is
still deferred. Domain services continue to receive only `TenantContext`.

## Alternatives considered

1. **Enforce roles in domain services.** Rejected because role policy is an API
   boundary concern and would couple domain services to authentication roles.
2. **Add a permission table or migrate the role column now.** Rejected because
   the current operation matrix is small and the long-term taxonomy is not yet
   approved.
3. **Treat all members as owners.** Rejected because it leaves the newly
   identified privilege distinction unenforced.
4. **Use token claims as authorization input.** Rejected because membership data
   is the authoritative tenant and role source established in Phase 1.9.

## Consequences

- API routes receive `MemberContext` and pass `member.tenant` to domain services.
- Authorization failures are stable, generic `403 permission_denied` responses.
- Existing tenant isolation and service-owned transaction behavior remain
  unchanged.
- The development pathway remains usable for local tests while production
  requires authentication.
- A future approved role taxonomy can replace the policy module without changing
  domain or persistence boundaries.

## Linked requirements and tasks

- `REQUIREMENTS.md`: SP-5, SP-6, and the Phase 1.10 task assignment.
- `ACTIVE_TASK.md`: Phase 1.10 — Tenant-role authorization boundary.
- `docs/phases/phase-1-10-authorization-tenant-role-boundary.md`: implementation
  and validation record.

## Supersession note

This decision implements the authorization work deferred by
`ADR-0006-supabase-authenticated-tenant-boundary.md`; it does not replace that
decision's authentication and membership-resolution design.
