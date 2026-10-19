# ACTIVE_TASK.md — Current Active Task

## Task: Authentication initialization and public-shell stabilization

**Status:** Source implementation and frontend verification complete on
2026-10-19; commit, push, and clean-checkout validation are pending.

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
