# Phase 1.10 — Authorization & Tenant Role Boundary

> Status: Complete — 2026-09-21
>
> This phase adds the minimum explicit role-aware authorization boundary above
> the authenticated tenant-membership boundary without redesigning the domain
> model or introducing new persistence structures.

## 1. Role model discovered

The approved schema already contains `xportra.user_tenant_memberships.role` as a
server-side tenant membership attribute. No richer RBAC taxonomy or permission
matrix existed in the codebase or approved documentation, so the minimum explicit
role model was defined from the current API requirements:

- `owner` — tenant administrator/manager; may perform all current tenant
  operations.
- `member` — ordinary tenant user; may read tenant-owned records and create or
  associate compliance evidence.

Unknown, missing, or malformed role values fail closed. The role is resolved from
server-side membership data; it is never accepted from a request header, token
claim, or client payload.

## 2. Authorization policy

The API layer enforces authorization after authenticated identity and tenant
membership resolution, before route handlers invoke domain services.

### 2.1 Permissions and operation mapping

| Operation | `owner` | `member` |
| --- | --- | --- |
| Read tenant-owned resources | Yes | Yes |
| Create exporter | Yes | No |
| Create product | Yes | No |
| Register destination market | Yes | No |
| Create compliance evidence | Yes | Yes |
| Associate evidence with requirement | Yes | Yes |
| Create certification / permit / license | Yes | No |

This reflects the current Phase 1.8 API scope without inventing a future policy
engine or resource-level ACL system.

## 3. Boundary placement

Authorization is enforced at the API/application boundary in the FastAPI
dependency chain:

- `xportra/api/auth.py` resolves `MemberContext` from authenticated identity +
  active membership + server-side role selection.
- `xportra/api/dependencies.py` exposes the role-aware dependency path and keeps
  the isolated development-header pathway only outside production.
- `xportra/api/authorization.py` defines the minimal `owner`/`member` policy and
  the permission constants.
- `xportra/api/router.py` applies `require_permission(...)` to protected routes.

The domain services continue receiving only `TenantContext`. No JWT, request
object, or HTTP auth state is passed into the domain or persistence layers.

## 4. Request path

```text
HTTP Request
    -> Supabase authentication
    -> AuthenticatedIdentity
    -> Tenant membership resolution
    -> TenantContext + membership role
    -> Authorization check
    -> Domain/application service
    -> Persistence
```

Authentication answers “who is the user?” Membership answers “which tenant may
this user operate in?” Authorization answers “which operations may this user
perform within that tenant?”

## 5. Error behavior

- unauthenticated -> `401` with `AuthenticationError`
- authenticated but no tenant membership -> `403` with existing membership error
- authenticated tenant member without required permission -> `403`
  `permission_denied`
- tenant-scoped record not found -> `404` resource-not-found behavior

Error payloads do not expose SQL, stack traces, tokens, or secrets. The generic
permission denial remains stable for unauthorized operations.

## 6. Tenant isolation and security

- tenant membership is checked against the authenticated user's active
  memberships before any selected tenant is accepted;
- a client-supplied tenant ID is not treated as proof of access;
- role selection is server-side only from the selected active membership;
- cross-tenant resources remain inaccessible because the service methods receive
  a tenant-scoped `TenantContext` and DB queries bind both tenant and resource ID.

## 7. Database changes

No schema migration was required for the role model because the approved
`user_tenant_memberships.role` column already existed and the application only
needed to interpret it at the boundary. No permission table, ACL table, or new
domain entities were introduced.

## 8. Testing and verification

Validated with these commands and results:

```powershell
& "C:/Users/hp/Desktop/AI PROJECTS/Xportra AI/.venv/Scripts/python.exe" -m unittest discover tests/unit -v
```

Result: 45 tests ran, all passed.

```powershell
& "C:/Users/hp/Desktop/AI PROJECTS/Xportra AI/.venv/Scripts/python.exe" -m unittest tests.unit.test_auth tests.unit.test_api tests.integration.test_auth_postgresql tests.integration.test_api_postgresql tests.integration.test_domain_services_postgresql tests.integration.test_persistence_postgresql -v
```

Result: 33 tests ran, 29 passed and 4 PostgreSQL integration suites skipped
because `DATABASE_URL` is not configured in the current environment. The
authorization and authentication unit suites passed as expected.

## 9. Defects discovered and corrected

- The dev/test tenant header path was correctly isolated to non-production.
- Authorization policy enforcement remained generic and stable, returning the
  expected `403 permission_denied` behavior.
- No major defects were found in the implemented role boundary; the remaining
  database-backed integration tests are gated only by missing environment
  configuration.

## 10. Remaining limitations and deferred decisions

This intentionally small model is not a full enterprise RBAC system. It remains
limited to the current API and existing membership model. Future work can extend
it with a more formal permission model only after the approved requirements and
domain model explicitly call for it.

Out-of-scope items remain intentionally deferred, including role-management UI,
user administration APIs, resource ACLs, permission tables, and broader policy
engines.

## 11. Completion status

Phase 1.10 is complete for the approved scope. It establishes the minimum
explicit authorization boundary required for the current authenticated tenant
API without expanding into out-of-scope enterprise authorization work.
