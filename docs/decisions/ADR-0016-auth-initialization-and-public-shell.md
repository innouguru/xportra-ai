# ADR-0016: Authentication initialization and public shell boundaries

- Status: Accepted
- Date: 2026-10-19
- Scope: Auth restoration and public/workspace layout composition
- Requirements: `REQUIREMENTS.md` R-10.8.2, R-10.10, R-10.12

## Context

Public authentication routes currently reuse shipment-oriented `AppShell` chrome.
That shell can show workspace navigation or shipment status outside the protected
workspace. Authentication pages also wait for `getSession()` to resolve before
rendering their forms, while the auth listener can emit a session first.

## Decision

1. Subscribe to Supabase auth-state events before starting session restoration.
   Either an auth event or the restoration result settles frontend initialization;
   restoration cannot overwrite a newer auth event.
2. Public auth routes use minimal public chrome. Workspace navigation and session
   status are rendered only by explicitly selected workspace shell instances
   mounted beneath a protected route.
3. `/start` and `/settings` are authenticated surfaces and must use the common
   `RequireAuth` boundary.
4. Public auth forms remain visible and usable while session restoration is
   pending. Restoration failures show a safe recovery message and reload action.

## Consequences

- Auth pages no longer display shipment actions or empty-shipment status.
- Protected routes continue to withhold workspace content while restoration is
  unresolved and redirect when the settled state is unauthenticated.
- No authentication provider, token policy, persistence policy, or backend
  authorization boundary changes.
