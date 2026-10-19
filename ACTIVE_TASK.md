# ACTIVE_TASK.md — Current Active Task

## Task: Authentication initialization and public-shell stabilization

**Status:** Complete on 2026-10-19. Implementation commit
`a243a818da8fa8a537a3ae8b5d4fc97d43259227` passed clean-tree verification;
implementation and state documentation were pushed to `origin/main` and the
remote branch was verified.

**Authorization:** User-assigned stabilization follow-up; `REQUIREMENTS.md`
R-10.8.2, R-10.10, R-10.12; ADR-0012 and ADR-0015. The shell boundary detail is
recorded in ADR-0016.

**Scope:** Settle auth initialization correctly when auth events race with
session restoration, keep public auth forms usable during pending restoration,
provide a recovery state on restore failure, separate authentication-page
chrome from protected workspace chrome, and guard `/start` and `/settings`.

**Verification passed:** focused frontend tests (71 passed), complete frontend
suite (516 passed across 72 files), `npm.cmd run lint`, and `npm.cmd run build`.
The build emitted a large-chunk advisory. No browser-based or live production
verification was performed.

**Previous task:** Production authentication/registration implementation remains
in commit `60e32bf986a9630a244ed4c61d78b11f0f8ece88`; live Render and Supabase
verification remains outstanding. Deploy only the existing frontend service
for this frontend-only follow-up. Confirm SPA fallback still serves direct
routes; no new Supabase setting is introduced here.

**Live check:** Read-only browser inspection on 2026-10-19 confirmed the current
Render frontend still serves the pre-fix `/register` and `/session` UI. The
landing route loaded without workspace navigation; unauthenticated `/dashboard`
showed only session restoration text and no protected content. Redeployment and
post-deploy verification are outstanding.
