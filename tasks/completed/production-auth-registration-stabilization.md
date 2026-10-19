# Production authentication and organization registration stabilization

**Status:** In progress (2026-10-19)

## Scope

Implement the approved R-10.12 stabilization for production auth controls,
optional password sign-in, sign-out state cleanup, and registration callback
recovery. Preserve server-derived registration identity and the existing
transactional backend workflow. Pending organization profile recovery uses
`sessionStorage` only.

## Acceptance checks

- Focused frontend auth, routing, and registration recovery tests pass.
- Frontend type checking and production build pass; the production artifact
  excludes development-only controls.
- Backend registration and production development-header tests pass if
  backend behavior is modified.
- Required implementation/test/documentation files are tracked and a clean
  tracked-tree verification succeeds.
- Changes are committed and pushed when the repository permits.
- Render and Supabase production settings are documented separately from
  source-level verification.

## Safeguards

- No production tenants, users, services, Supabase projects, or migrations are
  created or modified by automated tests.
- Never store passwords or auth tokens in pending registration state.
- Do not weaken tenant, identity, role, email-verification, or token
  verification rules.
