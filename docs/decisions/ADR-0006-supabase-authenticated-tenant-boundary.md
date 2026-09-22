# ADR-0006: Supabase authenticated tenant identity boundary

- Status: Accepted
- Date: 2026-09-21
- Scope: Phase 1.9 authentication and tenant identity resolution

## Context

Phase 1.8 exposed an explicit development/test tenant header,
`X-Development-Tenant-ID`, to make the missing trust boundary visible. Phase
1.9 replaces that mechanism for normal API operation with a trustworthy
authenticated identity boundary while keeping the existing immutable
`TenantContext -> domain service -> persistence` path unchanged.

Supabase is the approved technology baseline provider (Phase 0.5), including
Supabase Auth Free where authentication is required. No second authentication
system may be introduced.

## Decision

Verify a Bearer access token as a Supabase Auth token at the API boundary,
represent the authenticated identity, and resolve the request's
`TenantContext` exclusively from the authenticated user's existing
`user_tenant_memberships` data.

- **Token verification:** Supabase Auth access tokens are verified with
  `PyJWT` using HS256 and the Supabase project JWT secret
  (`SUPABASE_JWT_SECRET`), requiring a valid signature, `exp`, and `sub`
  claims, and a matching `aud` claim (`SUPABASE_JWT_AUDIENCE`, default
  `authenticated`). When `SUPABASE_URL` is configured, the `iss` claim must
  match `<url>/auth/v1`. This is the documented Supabase server-side JWT
  verification mechanism (the same mechanism Supabase's own libraries and
  Postgres RLS use).
- **Identity representation:** a token that verifies yields an
  `AuthenticatedIdentity` (Supabase `sub` as a UUID, plus optional `email`).
  This value exists only at the API/application boundary.
- **Identity-to-user mapping:** a new nullable `users.supabase_uid` column
  (migration 002) maps the Supabase `sub` to the existing local `users` row.
  The membership table is unchanged and remains authoritative.
- **Tenant resolution:** the local user's active memberships in active tenants
  are the only source for the `TenantContext`. A client-supplied tenant
  identifier (`X-Xportra-Tenant-ID`) is only a requested context and must
  match an active membership; it is never treated as proof of membership.
- **Boundary:** domain services continue to receive only the immutable
  `TenantContext`. JWTs, tokens, HTTP headers, and request objects are not
  passed below the API/application boundary.
- **Development pathway:** `X-Development-Tenant-ID` remains available only as
  an isolated non-production fallback and is rejected in production
  (`APP_ENV=production`). It can never override or replace any supplied
  credentials.
- **Configuration:** `SUPABASE_JWT_SECRET` is required for authentication;
  `SUPABASE_JWT_AUDIENCE` defaults to `authenticated`;
  `SUPABASE_URL` optionally enables issuer verification. In production the
  application fails fast at startup if this configuration is missing.

## Alternatives considered

1. **Server-side user lookup for every request (`/auth/v1/user`).** Rejected
   because it adds a network round trip per request, depends on the anon key
   and Auth endpoint availability, and makes deterministic offline testing of
   the boundary harder. Local HMAC verification with the Supabase JWT secret
   is the documented mechanism and is stateless.
2. **Mapping the identity by email.** Rejected because email is not a stable
   identity key; the Supabase `sub` UUID is stable. A dedicated
   `users.supabase_uid` mapping keeps provider identity separate from the
   domain user record.
3. **Passing identity or tokens into domain services.** Rejected because it
   couples the domain layer to the authentication provider and violates the
   established service boundary.
4. **Treat the development header as legitimate in production.** Rejected; it
   is a trust-free mechanism and remains strictly a non-production test/development
   pathway.

## Consequences

- Requests without credentials receive `401 authentication_required`;
  malformed, invalid, or expired tokens receive distinct `401` responses with
  `WWW-Authenticate: Bearer`; authenticated users without active memberships
  receive `403`; requests selecting a tenant the user does not belong to
  receive `403`; multi-tenant users without a selection receive `400`.
- Error responses never expose JWT contents, tokens, the JWT secret, database
  details, SQL, or stack traces.
- `users.supabase_uid` is added via additive migration 002 and requires no
  change to the membership table or to tenant-owned resources.
- Authorization beyond tenant membership was implemented as the follow-on
  Phase 1.10 boundary in `ADR-0007-tenant-role-authorization-boundary.md`; the
  existing `role` column remains the source of the selected role value.
- `PyJWT` becomes an explicit project dependency.

## Linked requirements and tasks

- `REQUIREMENTS.md`: TB-3, SP-5, SP-6 and the Phase 1.9 task assignment.
- `ACTIVE_TASK.md`: Phase 1.9 — Authentication & Tenant Identity Boundary.
- `docs/phases/phase-1-9-authentication-tenant-identity.md`: implementation and
  validation record.