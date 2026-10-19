# ADR-0014: ES256/JWKS token verification and frontend Supabase sign-in

- Status: Accepted
- Date: 2026-10-12
- Scope: Phase 10.9 production JWT verification compatibility and
  Phase 10.10 frontend Supabase authentication
  (`REQUIREMENTS.md` R-10.9/R-10.10)

## Context

The Supabase authentication boundary (ADR-0006) verifies Bearer
access tokens with `PyJWT` using HS256 and the project JWT secret
(`SUPABASE_JWT_SECRET`), requiring signature, `exp`, `sub`
(UUID), `aud`, and — when `SUPABASE_URL` is configured — the
`<url>/auth/v1` issuer. That design matched the legacy Supabase
signing system, in which one shared secret signs every token.

The production Supabase project has moved to the asymmetric
signing-keys system and now issues access tokens signed with
ES256. The current verifier passes `algorithms=["HS256"]`, so
every valid production token is rejected with
`401 invalid_token` before any signature evaluation (confirmed
by local reproduction with a synthetic ES256-header token:
`InvalidAlgorithmError — the specified alg value is not
allowed`). The existing owner account and tenant membership are
in place and must be preserved; the failure is verification
format, not identity data.

Separately, the frontend session surface
(`frontend/src/features/shipment/SessionPage.tsx`) accepts only
a manually pasted bearer token kept in React memory
(`frontend/src/app/AuthContext.tsx`). There is no Supabase
client and no magic-link callback handler, so following a
Supabase magic link lands on `/` with no Xportra session. The
intended integration is the official `@supabase/supabase-js`
client with PKCE magic-link authentication — but no client can
succeed until the backend accepts the ES256 tokens Auth issues.

## Decision

1. **Verify ES256 via the trusted Supabase JWKS.**
   `SupabaseTokenVerifier` gains an ES256 path that resolves
   the token's `kid` exclusively against the public keys
   published at the project's JWKS endpoint (derived from the
   existing `SUPABASE_URL`; no new secret is introduced) and
   keeps every existing claim check (issuer, audience,
   expiration, subject, UUID format).
2. **Pin algorithms to key types.** HS256 verifies only with
   the shared secret (retained solely for the existing
   supported legacy-token configuration); ES256 verifies only
   with JWKS-resolved EC public keys. Keys are never used
   across algorithms, and no `alg` is honored from an
   untrusted JWT header outside the server-side allowlist.
3. **Fail closed.** Unsupported algorithms, unknown key IDs,
   invalid signatures, malformed claims, and JWKS
   unavailability all reject with the existing 401 semantics.
   JWKS responses are cached with a bounded lifetime and
   tolerate provider key rotation. Tokens, secrets, and key
   material never enter logs or error responses (R-10.1.4 /
   R-10.1.5 hold).
4. **Declare the cryptographic dependency.** EC verification
   requires the `cryptography` package backing PyJWT; it is
   added to `pyproject.toml` as an explicit dependency
   (CD-12/CD-13). `httpx` (already declared) serves JWKS
   retrieval. Tenant-membership resolution, role checks, and
   the production `X-Development-Tenant-ID` rejection are
   untouched.
5. **Frontend signs in with `@supabase/supabase-js` (PKCE).**
   Email magic-link initiation, dedicated callback route,
   session restoration, token refresh, and sign-out; all API
   calls keep the existing `Authorization: Bearer` contract,
   and the local-development tenant mechanism stays
   non-production-only. Only public client identifiers
   (project URL, publishable key) are configured for the
   frontend build; backend secrets never appear client-side.
6. **Ordering is a hard dependency.** The frontend work
   depends on the backend verifier being deployed and
   verified with a real production ES256 token first. Until
   then, magic-link sign-in cannot authenticate anyone,
   regardless of client correctness.

## Alternatives considered

1. **Change the Supabase project's signing settings back to
   HS256.** Rejected: it fights the provider's direction
   (HS256 is officially not recommended for production),
   disturbs a working production Auth configuration, and
   trades a bounded code change for platform regression.
2. **Per-request verification against the Auth server
   (`GET /auth/v1/user`).** Rejected as the primary
   mechanism: it puts Auth in the request hot path (latency,
   availability coupling, extra server-side key handling)
   and contradicts the stateless local-verification design
   ADR-0006 chose deliberately. It remains a diagnostic
   option, not the architecture.
3. **Hand-rolled GoTrue REST integration instead of
   `supabase-js`.** Rejected: reimplements PKCE exchange,
   storage, and refresh with a larger review surface for no
   architectural gain; the official client is one declared
   dependency.
4. **Accepting any `alg` with a combined key set.**
   Rejected as unsafe: it enables algorithm/key-confusion
   attacks. The allowlist-plus-pinned-keys design above is
   the minimum that stays secure.
5. **Cookie-based sessions.** Rejected: requires backend
   issuance/validation changes and CORS credential redesign;
   out of scope for owner sign-in.

## Consequences

- Valid production ES256 tokens verify; legacy HS256 tokens
  keep verifying only under the existing secret
  configuration; everything else 401s exactly as today.
- `pyproject.toml` gains `cryptography`; no other
  dependency, migration, or configuration-schema change is
  implied by this decision (JWKS URL derives from
  `SUPABASE_URL`).
- The existing owner `sub → users.supabase_uid` mapping and
  memberships resolve unchanged — no user recreation, no
  membership edits, no migration.
- New regression tests are required with the implementation:
  ES256 round-trip, `kid`-unknown and alg-confusion
  rejection in both directions, fail-closed JWKS outage,
  and no-leak error assertions; existing HS256 suites must
  pass unweakened.
- Frontend magic-link work is sequenced after backend
  deployment plus production-token verification; its own
  tests use a mocked Supabase client with zero network.

## Non-goals (explicit)

No user recreation, no membership changes, no database
schema migration, no change to Supabase signing settings,
no new authentication provider, no password or third-party
login, no cookie sessions, and no weakening of signature
verification or tenant/role authorization.

## Linked requirements and tasks

- `REQUIREMENTS.md`: TB-3, SP-5, SP-6, R-10.1.2, R-10.1.3,
  R-10.1.4, R-10.1.5, R-10.1.7, R-10.9, R-10.10.
- Prior decisions: ADR-0006 (boundary this extends),
  ADR-0008 (production hardening it preserves).
- Invariants: INVARIANTS.md #4 (tenant isolation), #8
  (this ADR), #9 (no weakened tests).
- Tasks: `tasks/backlog/production-jwks-verifier.md`,
  `tasks/backlog/frontend-supabase-sign-in.md`
  (ordered: backend verifier first).
