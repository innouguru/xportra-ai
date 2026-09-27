# Local Development Bootstrap

> LOCAL DEVELOPMENT ONLY. Nothing in this document
> applies to production. Production authentication is
> unchanged: `X-Development-Tenant-ID` is rejected
> there by the existing Phase 10.1 boundary, and Bearer
> tokens are the only production mechanism.

## Why a development tenant is required

The development-tenant pathway (`X-Development-Tenant-ID`
header, or the Session page development field) accepts
any tenant UUID without a database lookup — but every
persistence operation enforces foreign-key integrity
against `xportra.tenants(id)`. Without a matching tenant
row, recording evidence, exporters, or anything else
fails. The Bearer-token pathway additionally requires a
user row plus an active membership row
(`TenantMembershipResolver`).

## Provision it

Requirements: `DATABASE_URL` pointing at a local
development database with migrations applied, and
`APP_ENV` anything except `production` (the script
refuses production before opening a connection).

```console
python -m xportra.dev.bootstrap
```

The script ensures, idempotently:

- tenant `local-development` ("Local Development Tenant")
- user `local-developer@xportra.local` ("Local Developer")
- one active `owner` membership between them

Reruns find the existing rows by their unique natural
keys (slug, email, membership pair) and report them as
"already existed" — nothing is duplicated. Conflicting
pre-existing state (suspended tenant, revoked or
differently-roled membership, a foreign Supabase link)
aborts with an explanation instead of overwriting.

Example output:

```text
Xportra local development bootstrap
Tenant ID: <uuid> (created|already existed)
User ID: <uuid> (created|already existed)
Membership role: owner (created|already existed)
...
```

Only identifiers and roles are printed — never the
database DSN, tokens, or secrets.

## Use the tenant ID

- Frontend: open the Session page (`/session`) and
  paste the Tenant ID into the **Development tenant
  ID** field (labelled local-development-only). Set
  `VITE_API_BASE_URL` if the API is not on
  `http://localhost:8000`.
- API directly: send `X-Development-Tenant-ID:
  <tenant-id>`. This grants the synthetic owner role
  for local testing only.

## Supabase Auth (only for Bearer-token testing)

The bootstrap does not fake authentication and never
mints tokens. The dev-header path needs no Supabase
project at all. To test true Bearer-token requests:

1. Create a real user in the Supabase dashboard
   (Authentication → Users) and copy its Auth UUID.
2. Link it to the development user row:

```console
python -m xportra.dev.bootstrap --supabase-uid <auth-user-uuid>
```

3. Request with `Authorization: Bearer <real-JWT>`.
   The resolver matches the token subject to the
   linked row and its active membership.

The link is refused if the development user is
already linked elsewhere, or if the identity belongs
to another user.
