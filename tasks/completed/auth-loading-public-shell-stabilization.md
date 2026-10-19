# Authentication loading and public shell stabilization

## Status

Complete on 2026-10-19 after source tests and production build. See
`tasks/completed/auth-loading-public-shell-stabilization.md` for the outcome.

## Requirement

Fix the reported `/register` and `/session` indefinite preparation UI and remove
workspace/shipment navigation from public routes while preserving protected
workspace behavior. This task is authorized by the active user assignment and
`REQUIREMENTS.md` R-10.8.2, R-10.10, and R-10.12.

## Acceptance checks

- Supabase auth-event/session-restore ordering always settles initialization on
  either usable signal; restoration errors present a recovery action.
- Registration and sign-in forms render and remain usable on their public routes
  even if session restoration is still pending.
- Public landing/auth/callback/reset surfaces do not mount workspace or shipment
  navigation/status; protected routes remain gated.
- Regression tests, frontend type checking, and production build pass.
- Changes are source-tracked, committed, and pushed without unrelated files.

## Findings

- `AuthContext` started `getSession()` before registering the auth listener. If
  the listener event superseded the pending restore, initialization could remain
  unresolved; auth pages hid their forms behind that state.
- `AppShell` bundled public marketing links and shipment empty-state UI. Auth
  pages reused it. `/start` and `/settings` mounted authenticated shell routes
  without `RequireAuth`.

## Implementation and verification

- Auth events are subscribed before `getSession`; a newer auth event wins over
  the restoration promise, and restore failures surface a safe recovery message.
- Registration and sign-in forms stay visible and usable during a pending
  restoration without an indefinite loading message. Protected routes continue
  to wait for a session result.
- Auth routes use minimal public chrome; workspace chrome is explicit and
  mounted only on protected workspace pages. `/start` and `/settings` are gated.
- Focused frontend tests: 71 passed. Full frontend suite: 72 files / 516 tests
  passed. `npm.cmd run lint` and `npm.cmd run build` passed. The build reported
  the existing large-chunk advisory. No live browser, Render, or Supabase check
  was performed.
- Commit `a243a818da8fa8a537a3ae8b5d4fc97d43259227` contains the complete
  implementation. A Git archive of that exact commit passed `npm.cmd run lint`,
  `npm.cmd run build`, and a backend `xportra.api.app` import. The source files
  changed by this task were already tracked; the ADR and task record were
  included in the commit. The implementation and follow-up state commits were
  pushed to `origin/main`; `git ls-remote origin refs/heads/main` verified the
  remote after the state commit. Live production behavior remains unverified.
