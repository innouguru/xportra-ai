# Public authentication routes and password recovery

**Status:** Complete — 2026-10-19. Implementation commit `3450e34` and
documentation commit `ab9e595` are pushed; the verified `origin/main` tip is
`ab9e595c993ed76c81a4ae2123f45af75b48b490`.

## Authorized scope

Correct public landing-page registration navigation and authentication
cross-links, then implement password recovery initiation and reset on the
existing public `/reset-password` route. Keep the existing Supabase client,
PKCE exchange, account registration flow, and protected workspace boundary.

## Acceptance criteria

- Landing-page Get Started actions target `/register`; Sign In targets `/session`.
- Sign-in and registration offer direct links to one another.
- Forgot password navigates to `/reset-password`.
- The recovery route validates an email, uses the existing Supabase recovery
  method and explicit route redirect, presents account-neutral success, and
  handles errors/loading states.
- The new-password form appears only after a valid recovery session and updates
  the password using Supabase.
- Direct public routes remain separate from workspace chrome; protected routes
  remain gated.
- Relevant tests, frontend lint, typecheck, and production build pass.
- The scoped source and documentation are committed and pushed where permitted.

## Root causes and implementation

- The landing header already linked Get Started to `/register`, but the hero
  CTA linked to protected `/start`; unauthenticated navigation from `/start`
  correctly redirected to `/session`. The hero now uses `/register` and tests
  pin both destinations.
- The sign-in form implemented forgot-password inline, including email
  validation and reset request handling, so invalid-email feedback remained on
  `/session`. It now links to `/reset-password`, which owns the email form and
  recovery feedback. Sign-in and registration now cross-link directly.
- The old reset route had only the new-password screen, and a missing code was
  interpreted as permission to show that form whenever a Supabase session
  existed. It also accepted code exchange success without requiring a returned
  recovery session. The route now offers recovery initiation, generic
  confirmation, failures and loading states; callback exchange requires a
  session; `PASSWORD_RECOVERY` is surfaced by `AuthContext`; password update
  completion is distinct from a successful email request.
- The codebase already separates public auth chrome from protected workspace
  chrome (ADR-0016). No shell or backend changes were necessary for this task.

## Verification

- `npm.cmd test -- src/app/AuthContext.test.tsx src/features/auth/ResetPasswordPage.test.tsx src/shell/AppRoutes.test.tsx src/features/landing/LandingPage.test.tsx src/features/shipment/SessionPage.test.tsx` — 69 passed.
- `npm.cmd run lint` — passed (`tsc --noEmit`).
- `npm.cmd run build` — passed; Vite emitted the existing 500 kB chunk advisory.
- `npm.cmd test` — attempted; default fork pool failed due Windows temp-cache
  ENOENT errors and worker-start timeouts (not test assertion failures).
- `npm.cmd test -- --maxWorkers=2 --no-file-parallelism` — 522 passed across
  72 files.
- Clean tracked-tree archive at `ab9e595` with the existing frontend
  `node_modules` junction: `npm.cmd run build` passed.
- No backend code or migrations changed. No production records were created.
- No browser/live production verification was performed for this revision.
- `git ls-remote origin refs/heads/main` confirmed the branch points to
  `ab9e595c993ed76c81a4ae2123f45af75b48b490`.

## Safety

No production users, organizations, memberships, database schema, secrets, or
Supabase policies are modified. Live Render/Supabase behavior must be reported
separately from local source verification.
