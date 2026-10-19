# ACTIVE_TASK.md — Current Active Task

## Task: Production authentication and organization registration stabilization

**Status:** Implementation and verification in progress.

**Authorization:** `REQUIREMENTS.md` R-10.12 and ADR-0015, approved for this
stabilization task.

**Scope:** Remove development-only controls from production builds while
retaining local development behavior and backend production rejection; support
Supabase magic-link and password sign-in; make sign-out honor remote results
and clear session-derived UI state; repair registration callback recovery and
safe retries using `sessionStorage`.

**Acceptance checks:** focused frontend authentication/registration/routing
tests; frontend type check and production build; relevant backend registration
and production-development-header tests; review tracked source and final diff.
No production organizations or users may be created. Do not rerun migration
014; task context reports it applied in the existing production database.

**Deployment remains external:** verify Render build/start settings and deploy
the existing frontend/backend services after source verification. Verify
Supabase email/password provider policy and redirect allowlist before claiming
live authentication and callback behavior.
