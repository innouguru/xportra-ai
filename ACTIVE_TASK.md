# ACTIVE_TASK.md — Current Active Task

## Task: frontend-supabase-sign-in (Phase 10.10)

**Status:** Implementation complete, not yet deployed (2026-10-12).

Implemented Supabase magic-link sign-in for the frontend
(R-10.10, ADR-0014): `@supabase/supabase-js` client
singleton (PKCE, manual code exchange), session
bootstrap/subscribe/refresh/sign-out in `AuthContext`
(manual-state API preserved), reworked `/session`
(magic link + dev field, no token paste),
`/auth/callback` route, `RequireAuth` on workspace
routes, Supabase sign-out in shell + settings.
`apiFetch` untouched (same Bearer contract). Backend
untouched. Gates: frontend suite 69 files / 471 tests
passing (64 new, mocked client, zero network);
`tsc --noEmit` clean; `npm run build` succeeds.
No secrets in code/bundle; no tenant/user/membership
changes. Task record:
`tasks/completed/frontend-supabase-sign-in.md`
(uncommitted).

Next (operator): set the Supabase dashboard redirect
URLs (§8A: Site URL + exact `/auth/callback`
destination — NOT verified), rebuild the frontend
with `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`,
`VITE_SUPABASE_ANON_KEY`, redeploy the static site
(including the SPA fallback for `/auth/callback`),
then run the end-to-end smoke (magic-link sign-in,
reload persistence, sign-out, unauthenticated 401,
membership intact). Do not claim production
authentication works until that smoke passes.
