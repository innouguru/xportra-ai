# ACTIVE_TASK.md — Current Active Task

## Task: Public authentication routes and password recovery

**Status:** Complete, committed, and pushed (2026-10-19). Implementation
commit `3450e34`; final documentation commit `ab9e595`; `origin/main` was
verified at `ab9e595c993ed76c81a4ae2123f45af75b48b490`.

**Authorization:** User-assigned stabilization task; requirements R-10.8.12,
R-10.12, ADR-0015, and ADR-0016.

**Scope:** Correct landing-page registration navigation, provide public
authentication cross-links, and complete the password-recovery request and
PKCE callback flow on `/reset-password`. Preserve the Supabase identity
provider, registration workflow, authentication protections, and public versus
workspace layout boundary.

**Verified:** Both landing Get Started links open `/register`; `/session` and
`/register` cross-link; forgot password opens `/reset-password`; the recovery
route requests a reset email, handles account-neutral confirmation/errors,
requires an exchanged recovery session before password update, and offers a
sign-in recovery link. Targeted/full frontend tests, lint, and production build
pass. Full frontend suite passed with bounded workers (522 tests across 72
files); see the task completion record for the default-worker environment
failure and exact commands. Source files and task/state/docs are committed.

**Production:** No production account, organization, database, secret, or
provider setting is changed. Render/Supabase deployment behavior is a separate
verification step; the Supabase redirect allowlist must include the existing
frontend `/reset-password` URL if it is not already allowed.
