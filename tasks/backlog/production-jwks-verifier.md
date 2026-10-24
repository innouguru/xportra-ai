# Task: Production JWKS verifier (backend, Phase 10.9)

- Status: approved, not yet scheduled (backlog).
- Traces to: `REQUIREMENTS.md` R-10.9;
  `docs/decisions/ADR-0014-es256-jwks-verification-supabase-signin.md`.
- Order: FIRST implementation task in the authentication
  sequence. The frontend sign-in task
  (`tasks/backlog/frontend-supabase-sign-in.md`) is blocked
  on this task's deployment and production-token
  verification.

## Objective

Extend `SupabaseTokenVerifier` to accept valid production
ES256 access tokens via the trusted Supabase JWKS while
retaining HS256 for the existing legacy-token
configuration, without changing the bearer-token contract,
tenant-membership resolution, or role authorization.

## Scope

- ES256 path: `kid` resolution exclusively against the
  JWKS derived from `SUPABASE_URL`; server-side
  algorithm allowlist with per-algorithm pinned keys
  (HS256/secret, ES256/JWKS key); unchanged claim
  checks (issuer, audience, expiration, subject,
  UUID format).
- Safe JWKS caching with bounded lifetime and rotation
  tolerance; fail-closed behavior including JWKS
  outage (existing 401 semantics).
- Declare the cryptographic dependency backing EC
  verification in `pyproject.toml`.
- Focused regression tests: ES256 round-trip, unknown
  `kid` rejection, alg-confusion rejection in both
  directions, fail-closed JWKS outage, no-leak error
  assertions. Existing HS256 suites pass unweakened.

## Non-goals

No user recreation, no membership changes, no schema
migration, no Supabase signing-setting changes, no
new provider, no cookie sessions, no verification
weakening (R-10.9.9, ADR-0014).

## Acceptance criteria

1. Synthetic ES256 tokens verify; HS256 legacy tests
   pass unweakened; wrong-alg/unknown-`kid`/bad-signature
   tokens 401; JWKS outage 401s closed.
2. No token, secret, or key material in logs or errors.
3. Tenant/role behavior byte-identical (existing
   isolation suites green).
4. Backend deployed; a real production ES256 token
   verifies against an authenticated read before this
   task is marked complete.
