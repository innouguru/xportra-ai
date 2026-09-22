# Phase 1.9 — Authentication & Tenant Identity Boundary

> Replaces the Phase 1.8 development/test tenant-header mechanism with a real
> authenticated identity boundary built on Supabase Auth and the existing
> `user_tenant_memberships` model. Domain services still receive only the
> existing immutable `TenantContext`.

## Status

**Complete — 2026-09-21.** Supabase Auth access-token verification,
authenticated-identity representation, tenant-membership resolution,
`TenantContext` construction, production isolation of the development
pathway, focused unit/integration tests, and full regression validation are
implemented and verified. Phase 2 has not started.

## Request path

```text
HTTP Request
    -> Authentication verification (Supabase Auth JWT)
    -> Authenticated identity
    -> Tenant membership resolution
    -> TenantContext
    -> Domain/Application Service
    -> Persistence
```

## Authentication flow

Requests present `Authorization: Bearer <access_token>`. The API boundary
verifies the token as a Supabase Auth access token:

1. `SupabaseAuthSettings.from_environment()` reads `SUPABASE_JWT_SECRET`
   (required for authentication), `SUPABASE_JWT_AUDIENCE` (default
   `authenticated`), and `SUPABASE_URL` (optional; enables issuer
   verification).
2. `SupabaseTokenVerifier` decodes and verifies the token with `PyJWT` using
   HS256 and the Supabase project JWT secret, requiring a valid signature, an
   `exp` claim, a `sub` claim, and a matching `aud` claim. When `SUPABASE_URL`
   is configured, the `iss` claim must equal `<url>/auth/v1`.
3. A verified token yields an `AuthenticatedIdentity` containing the Supabase
   user `sub` (as a UUID) and the optional `email` claim.

This is the documented Supabase server-side JWT verification mechanism (the
same mechanism Supabase libraries and Postgres RLS use) and does not require a
network round trip per request. No second authentication system was created.

## Authenticated identity representation

`xportra/api/auth.py` defines:

- `SupabaseAuthSettings` — immutable authentication configuration.
- `AuthenticatedIdentity` — frozen dataclass with `subject: UUID` and
  `email: str | None`.
- `SupabaseTokenVerifier` — token verification and identity extraction.
- `TenantMembershipResolver` — membership-based `TenantContext` resolution.

Identities exist only at the API/application boundary. They are never passed
to domain services, persisted by the application, or logged.

## Identity-to-user mapping

Migration `migrations/002_add_supabase_auth_identity.sql` adds a nullable,
unique `users.supabase_uid` column mapping the Supabase `sub` to the existing
local `users` row (`UserRepository.get_by_supabase_uid`). The membership table
was not redesigned; no new membership entity was introduced. Provisioning the
local user record and its memberships remains an operator concern; this phase
does not invent user creation or role semantics.

## Tenant-membership resolution

`UserTenantMembershipRepository.list_active_for_user` returns the user's
memberships where both the membership and its tenant are `active`. The
`TenantMembershipResolver` uses only that data:

- no local user or no active memberships -> `403 tenant_membership_required`;
- exactly one active membership and no selection -> that tenant;
- multiple active memberships and no selection -> `400
  tenant_selection_required`;
- a requested tenant (`X-Xportra-Tenant-ID`) not among the active memberships
  -> `403 tenant_not_member`.

The client-supplied tenant identifier is only a requested context and is
always checked against the authenticated user's membership. It can never prove
membership.

## TenantContext construction

The resolver constructs the existing immutable
`xportra.persistence.tenant.TenantContext(tenant_id)` only after a matching
active membership is confirmed. The dependency `get_tenant_context`
(`xportra/api/dependencies.py`) passes that value into router handlers, which
pass it unchanged into tenant-aware domain services.

## API/service boundary

- `xportra/api/auth.py` — verification, identity, resolution.
- `xportra/api/dependencies.py` — `get_tenant_context` wires verification +
  resolution and preserves the isolated development/test pathway.
- `xportra/api/errors.py` — `AuthenticationError` (401) with
  `WWW-Authenticate: Bearer`; membership failures are stable `APIError`s.
- Domain services and persistence are unchanged in ownership. No JWT, token,
  HTTP header, or request object crosses the boundary.

## API behavior

| Credential / membership state | HTTP | Error code |
| --- | --- | --- |
| No credentials | 401 | `authentication_required` |
| Malformed/invalid token (signature, audience, subject, issuer) | 401 | `invalid_token` |
| Expired token | 401 | `expired_token` |
| Authenticated, no active membership | 403 | `tenant_membership_required` |
| Requested tenant not a member | 403 | `tenant_not_member` |
| Multiple memberships, no selection | 400 | `tenant_selection_required` |
| Development header used in production | 503 | `development_tenant_context_disabled` |
| Resource outside tenant scope | 404 | `resource_not_found` |

Responses never include JWT contents, tokens, the JWT secret, database
details, SQL, stack traces, or secret configuration. Response and log
assertions verify tokens/secrets cannot be observed in output.

### Behavior change from Phase 1.8

A request with neither credentials nor the development tenant header previously
returned `400 tenant_context_required`. It now returns
`401 authentication_required`, matching the new security posture. Existing API
tests were updated for this intentional change.

## Development/test behavior

- `X-Development-Tenant-ID` remains an isolated non-production fallback. It is
  honored only when no `Authorization` is present and `APP_ENV` is not
  `production`. It can never override or substitute for supplied credentials.
- When `APP_ENV=production`, the development header is rejected (503) and the
  provision of credentials is enforced (401).
- Integration tests mint HS256 tokens with a test-only JWT secret
  (`SUPABASE_JWT_SECRET` set from test configuration), create temporary
  tenants/users/memberships, and remove all of them in teardown. A
  deterministic cleanup test verifies zero Phase 1.9 tenants/users remain.

## Production behavior

- Production requires valid `Authorization` credentials; the dev-pathway is
  blocked.
- `create_app()` fails fast at startup when `APP_ENV=production` and
  `SUPABASE_JWT_SECRET` is not configured.
- No service-role key is used anywhere in the boundary; only the JWT secret
  (client-verification secret) is required.

## Configuration

New environment variables (see `docs/architecture/environment-schema.md` and
`.env.example`):

- `SUPABASE_URL` — optional; enables issuer verification. Not a secret.
- `SUPABASE_JWT_SECRET` — required for authentication; server-side secret.
- `SUPABASE_JWT_AUDIENCE` — expected `aud`; defaults to `authenticated`.

No actual credential values were committed. `DATABASE_URL` configuration was
unchanged. `PyJWT` was added to `pyproject.toml` (`pyjwt>=2.8,<3`) and
installed into `.venv` (additive, non-destructive).

## Tests and validation

### New Phase 1.9 unit tests — `tests/unit/test_auth.py`

Command:

```powershell
.venv\Scripts\python.exe -m unittest tests.unit.test_auth -v
```

Result: **23 tests passed**. Coverage includes settings parsing, valid-token
identity extraction, malformed/invalid-signature/wrong-audience/missing-subject/
non-UUID-subject/missing-exp/expired-token rejection, optional issuer
verification, and resolver behavior (no membership, single membership, tenant
selection, unrelated-tenant rejection, multi-tenant selection, no information
leakage in error messages).

### New Phase 1.9 API tests — `tests/unit/test_api.py`

Result: **10 tests passed** (7 existing Phase 1.8 tests updated for the
missing-credentials change, plus missing-credentials, invalid-token, and
no-leakage API tests).

### New Phase 1.9 integration tests — `tests/integration/test_auth_postgresql.py`

Command:

```powershell
$line = Get-Content '.env' | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -First 1
$env:DATABASE_URL = $line.Substring('DATABASE_URL='.Length).Trim()
.venv\Scripts\python.exe -m unittest tests.integration.test_auth_postgresql -v
```

Result: **12 tests passed** against the Supabase PostgreSQL development/test
database. Coverage includes valid-token operation within the membership
tenant, missing/malformed/invalid/expired credentials, no-membership rejection,
client-supplied tenant bypass prevention, multi-tenant selection, tenant
isolation between authenticated users, cross-tenant relationship rejection,
authenticated evidence-with-requirements, dev-header isolation, production
blocking of the dev header, credential/secret non-leakage in responses and
logs, and deterministic cleanup.

### Regression suites

- API unit tests: **10 passed**.
- API PostgreSQL integration tests: **6 passed**.
- Domain-service unit tests: **7 passed**.
- Phase 1.7 PostgreSQL domain-service integration tests: **8 passed**.
- Persistence unit tests: **5 passed**.
- Phase 1.5 PostgreSQL persistence integration tests: **6 passed**.

### Other validation

- Python compilation (`python -m compileall -q xportra tests`): passed.
- Dependency validation (`python -m pip check`): **passed; no broken
  requirements found**.
- Application import/startup: passed.
- Migration `002_add_supabase_auth_identity.sql` applied and verified
  (column + unique partial index); down migration provided.

## Defects discovered and corrected

1. During the first Phase 1.9 integration run, `setUpClass` referenced an
   undefined `suspended` tenant variable, failing suite setup. The suspended
   tenant creation result is now captured before creating the
   suspended-tenant membership. The full integration matrix passed on rerun.
2. Test-seed JWT secrets shorter than PyJWT's 32-byte recommendation produced
   `InsecureKeyLengthWarning` noise. All test secrets were lengthened to at
   least 32 bytes.

## Security considerations

- Verification is stateless HMAC (HS256) with the Supabase JWT secret;
  signatures, `exp`, `sub`, `aud`, and optionally `iss` are validated.
- Tokens and secrets never appear in responses, messages, or logs.
- Membership resolution is server-side and cannot be influenced by
  client-provided tenant identifiers.
- Tenant-owned resource access still requires `TenantContext` in the domain
  layer, so even a valid member is confined to their tenant's data.
- The development header is isolated to non-production and cannot be enabled
  in production.

## Remaining authorization limitations

Tenant membership identity is established, but this phase does **not**
implement authorization:

- any authenticated user with an active membership in a tenant may perform all
  current operations within that tenant;
- the existing `role` column is not given new semantics (no RBAC, no
  permission matrix, no per-action policy);
- no action-level authorization decisions are made.

A comprehensive authorization/RBAC model beyond tenant membership remains
future work and was explicitly out of scope.

## Deferred decisions

Requirement tenancy, comprehensive RBAC/authorization, new roles, permission
matrices, frontend authentication UI, password-reset UI, email-management UI,
MFA, social login, RAG, LLM integration, vector database, document ingestion,
retrieval, regulatory intelligence, AI-generated guidance, background workers,
deployment infrastructure, new domain entities, commodity taxonomy/HS coding,
evidence-ingestion strategy, and requirement-normalization strategy remain
deferred or out of scope. Local-user provisioning automation and
membership-administration APIs also remain future work.

No Phase 2 work was started. Phase 1.9 is complete.