# ACTIVE_TASK.md — Current Active Task

## Task: Production authentication and organization registration stabilization

**Status:** Source implementation, verification, commit, and push complete on
2026-10-19 (`60e32bf986a9630a244ed4c61d78b11f0f8ece88`). Live Render and
Supabase verification remains outstanding.

**Authorization:** `REQUIREMENTS.md` R-10.12 and ADR-0015, approved for this
stabilization task.

**Scope:** Remove development-only controls from production builds while
retaining local development behavior and backend production rejection; support
Supabase magic-link and password sign-in; make sign-out honor remote results
and clear session-derived UI state; repair registration callback recovery and
safe retries using `sessionStorage`.

**Acceptance checks passed:** focused and complete frontend tests (506 passed),
type check and production build, focused backend auth/registration tests (73
passed), production-bundle development-control scan, and clean tracked-tree
frontend build/backend import. No production organizations or users were
created. Migration 014 was not rerun; task context reports it applied in the
existing production database.

**Deployment remains external:** verify Render build/start settings and deploy
the existing frontend/backend services after source verification. Verify
Supabase email/password provider policy and redirect allowlist before claiming
live authentication and callback behavior.
