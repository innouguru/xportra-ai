# ACTIVE_TASK.md — Current Active Task

## Task: Public authentication routes and password recovery

**Status:** Complete in source (2026-10-19); commit and remote verification
are the remaining Git steps.

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
failure and exact commands. Source files are tracked; task/state/docs and
commit/push are being finalized.

**Production:** No production account, organization, database, secret, or
provider setting is changed. Render/Supabase deployment behavior is a separate
verification step; the Supabase redirect allowlist must include the existing
frontend `/reset-password` URL if it is not already allowed.
