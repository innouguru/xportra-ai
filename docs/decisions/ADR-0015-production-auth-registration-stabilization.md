# ADR-0015: Production authentication and registration stabilization

- Status: Accepted
- Date: 2026-10-19
- Scope: `REQUIREMENTS.md` R-10.12; stabilization of the existing
  Supabase authentication and organization-registration flows.

## Context

ADR-0014 established Supabase PKCE magic-link authentication and explicitly
excluded password sign-in. The approved production stabilization requirements
now add email/password sign-in as an alternative using the existing Supabase
client and provider. The existing organization-registration flow also depends
on a same-tab pending profile to complete a server-controlled transactional
provisioning request after email verification.

The sign-in and registration surfaces must retain one identity provider, the
verified Bearer-token API boundary, and server-derived tenant and owner role.
Pending registration data must not contain credentials or authentication
tokens. A registration callback must not treat a valid authentication session
as proof that an organization was created.

## Decision

1. Keep Supabase as the only authentication system. Offer `signInWithOtp`
   magic-link sign-in and `signInWithPassword` for existing accounts; password
   sign-in never creates accounts. Do not silently change Supabase email
   confirmation policy. Provider configuration must be verified separately.
2. Keep the local-development tenant control behind the Vite development build
   flag, and retain the backend production rejection of
   `X-Development-Tenant-ID`.
3. Treat a successful Supabase sign-out result as the boundary for clearing
   local authenticated state and redirecting. A failed result leaves the
   session state intact and reports a safe error.
4. Keep the minimal pending organization profile in `sessionStorage` for the
   supported same-tab callback. Mark registration callbacks explicitly so a
   missing or invalid profile produces a recovery message instead of silently
   completing sign-in. Preserve pending data after provisioning failure for a
   retry; clear it on successful provisioning or explicit cancellation.
5. Continue to derive identity, tenant, and owner membership in the backend
   from the verified authentication context and its existing transaction.

## Consequences

- This decision supersedes the password-authentication exclusion in
  ADR-0014 and R-10.10.6 only. Its token verification, provider, tenant
  isolation, and security decisions remain in force.
- Existing production Supabase email/password provider settings and redirect
  allowlists must be checked by an operator before claiming live password or
  callback behavior.
- `sessionStorage` does not promise recovery when an email link opens in a
  different tab, browser, or device. The callback must explain this limitation.
- No migration or production data change is needed or authorized.

## Verification

Mocked frontend tests cover authentication methods, sign-out outcomes, and
registration callback recovery. Backend tests continue to verify production
development-header rejection and transactional registration safeguards. Live
Supabase and Render behavior remains a deployment verification step.
