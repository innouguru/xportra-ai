# Task: Frontend Supabase sign-in (Phase 10.10)

- Status: implementation complete, not yet deployed (2026-10-12).
- Traces to: `REQUIREMENTS.md` R-10.10;
  `docs/decisions/ADR-0014-es256-jwks-verification-supabase-signin.md`.
- Order: SECOND implementation task in the authentication
  sequence. Backend deployment AND production-token
  verification (`25f3502`, HTTP 200) were confirmed before
  implementation. Do not start frontend deployment until
  the operator sets the Supabase redirect URLs (§8A) and
  frontend build variables, then runs the end-to-end
  smoke (acceptance criterion 3, still pending).

## Objective

Replace the manual bearer-token paste with supported
Supabase magic-link sign-in (`@supabase/supabase-js`,
PKCE) so the existing owner authenticates without
copying JWTs, while keeping the bearer-token API
contract and the non-production dev-tenant pathway.

## Scope

- New `@supabase/supabase-js` dependency; client
  singleton; `AuthContext` session bootstrap /
  `onAuthStateChange` / refresh / sign-out.
- Reworked session surface (email link initiation,
  check-email states) and dedicated PKCE callback
  route registered ahead of the `* → /` catch-all.
- Frontend tests with a mocked client (zero network):
  session/restore/refresh/sign-out, callback
  success/failure, expired-session convergence to
  sign-in-again. Existing suites pass unweakened.

## Non-goals

No backend changes, no password/third-party providers,
no user recreation, no membership changes, no schema
migration, no backend secrets in frontend code
(R-10.10.6, ADR-0014).

## Acceptance criteria

1. Owner magic-link sign-in with zero JWT copying;
   session survives reload; sign-out clears and
   routes to `/session`; expired sessions prompt
   re-sign-in.
2. All API calls unchanged (`Authorization: Bearer`);
   dev-tenant header still impossible in production.
3. Frontend deployed with public client identifiers
   only; end-to-end production smoke passes
   (sign-in, refresh, sign-out, unauthenticated 401,
   membership intact).

## Verification (2026-10-12, local; no deployment)

- New `@supabase/supabase-js` dependency (v2.117.3);
  `supabaseClient.ts` singleton (PKCE, manual code
  exchange, allow-listed return paths);
  `AuthContext` session bootstrap/subscribe/refresh/
  sign-out with unchanged manual-state API;
  reworked `SessionPage` (magic link + dev field,
  no token paste); `AuthCallbackPage` +
  `/auth/callback`; `RequireAuth` on workspace
  routes; Supabase sign-out in shell + settings.
- `apiFetch` unchanged (same Bearer contract, same
  401/403 mapping, no retries).
- Frontend suite: 69 files / 471 tests passing
  (64 new auth tests: config, session, callback,
  guards, sign-out, no-leak); `tsc --noEmit`
  clean; `npm run build` succeeds.
- Backend untouched (no diff outside `frontend/`,
  docs, and task records). No secrets in code or
  bundle; no tenant/user/membership changes.
- Pending operator: Supabase dashboard redirect
  URLs (§8A), frontend rebuild with the three
  build variables, redeploy, end-to-end smoke.
