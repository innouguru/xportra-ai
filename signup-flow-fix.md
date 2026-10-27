# Signup Flow Fix — Password Creation After Email Confirmation

Status: PASS WITH CONDITIONS (implementation complete; build passes; focused tests pass; live verification checklist documented; no production deployment performed).

## Confirmed root cause

**`sessionStorage` is tab-scoped.** Both `pendingRegistration.ts` and `onboarding.ts` used `sessionStorage` to store the pending organization profile and onboarding state. When an email confirmation link is clicked, it normally opens in a **new browser tab**. That new tab cannot access the signup tab's `sessionStorage`, so:

- `readPendingRegistration()` returns `null` (no cached org profile)
- `readOnboardingState()` returns `null` (no onboarding state)
- `AuthCallbackPage` treated the confirmed user as an existing user (no evidence of onboarding need) and navigated to the intended destination (`/dashboard`, `/start`, etc.), skipping password creation entirely.

## Changes

### Modified files
- `frontend/src/app/pendingRegistration.ts` — changed storage from `sessionStorage` to `localStorage` (shared across tabs from the same origin). Updated documentation comments accordingly.
- `frontend/src/app/onboarding.ts` — changed storage from `sessionStorage` to `localStorage`. Updated documentation comments to explain cross-tab availability and security model.
- `frontend/src/features/auth/AuthCallbackPage.tsx` — redirects ALL registration-flow confirmations (`flow=registration`) to `/setup-password` regardless of whether cached profile state is available. When `flow=registration` and no pending profile exists (new-tab scenario), onboarding is recorded as incomplete so protected routes still redirect to `/setup-password`. Removed the `missing-profile` error path for registration confirmations.
- `frontend/src/app/RequireAuth.tsx` — already enforced onboarding only when evidence exists; works correctly with `localStorage` since `readPendingRegistration()` and `readOnboardingState()` now read cross-tab state.
- `frontend/src/app/App.tsx` — added `/setup-password` route (from prior milestone).
- `frontend/src/features/auth/SetupPasswordPage.tsx` — dedicated password-creation screen (from prior milestone).
- Test files updated/added for new-tab scenario.

### Test files
- `frontend/src/features/auth/AuthCallbackPage.test.tsx` — updated `missing-profile` test to verify new-tab redirect to `/setup-password`; added new-tab no-profile test; changed `sessionStorage.clear()` to `localStorage.clear()`.
- `frontend/src/features/auth/setup-password-flow.test.tsx` — added tests for new-tab form rendering, onboarding bypass prevention via `RequireAuth`, and established-user dashboard access.
- `frontend/src/app/pendingRegistration.test.ts` — changed `sessionStorage.clear()`/`getItem`/`setItem` to `localStorage`.

## How new-tab onboarding state works securely

1. `registerWithEmail()` saves the org profile and onboarding state (incomplete) to `localStorage` in the signup tab.
2. User clicks the confirmation email link → opens in a **new tab** at `/auth/callback?code=...&flow=registration`.
3. The new tab reads `localStorage` (shared origin) — finds the pending profile and/or incomplete onboarding state.
4. `AuthCallbackPage` exchanges the PKCE code for a session, then redirects to `/setup-password?next=...`.
5. `/setup-password` verifies the session. If missing/expired, shows recoverable state with links to sign in or restart registration.
6. User creates and confirms a password. Client-side validation checks length (`>= 8`) and match.
7. After `auth.updateUser({ password })` succeeds via Supabase Auth:
   - Pending org profile is finalized via `registerOrganization()` (if present).
   - Profile is cleared, onboarding marked complete in `localStorage`.
   - User navigates to intended destination.
8. `RequireAuth` on protected routes checks `localStorage` onboarding state; redirects to `/setup-password` if incomplete.

**Security model:**
- Plaintext password is never stored in `localStorage`, URLs, analytics, or logs.
- `updatePassword` (`updateUser({ password })`) is the only mechanism; no custom hashing or DB writes.
- Direct navigation to `/dashboard` is blocked by `RequireAuth` when onboarding evidence exists.
- Refreshing `/setup-password` preserves state via `localStorage` + Supabase session persistence.
- `localStorage` state alone never bypasses Supabase Auth session validation — a valid session is required for protected routes.
- Password must succeed via `updateUser()` before onboarding is marked complete.

## Deployment

**Frontend redeployment alone is sufficient.** No backend or Supabase configuration changes are required. The fix is entirely client-side: `localStorage` sharing + `AuthCallbackPage` routing logic.

## Manual live verification (fresh test email)

1. Open deployed signup page (`/register`) in tab A.
2. Register a new user.
3. Leave tab A open. Open the confirmation email link (opens in new tab B).
4. Verify tab B shows `/setup-password`, not `/dashboard`.
5. Attempt to navigate directly to `/dashboard` in tab B before setting password; verify redirect back to `/setup-password`.
6. Set and confirm a valid password in tab B.
7. Verify registration finalization succeeds and `/dashboard` opens.
8. Sign out, sign in with new email + password (`/session` → password mode).
9. Test password reset (`/reset-password`).
10. Close tab A before opening confirmation link; repeat steps 4–7.
11. Refresh `/setup-password` or `/auth/callback` where safe; verify no crash or bypass.
12. Verify no duplicate organization/membership records (backend idempotency).

No production database writes, authorization grants, `.env` changes, or remote pushes were made.
