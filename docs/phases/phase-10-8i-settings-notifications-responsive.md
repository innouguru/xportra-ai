# Phase 10.8I — Settings / Notifications / Responsive

> Implemented 2026-09-28 under `REQUIREMENTS.md`
> R-10.8 (R-10.8.4–R-10.8.6, R-10.8.13–R-10.8.14)
> and `docs/decisions/ADR-0012-authenticated-shell-restructure.md`,
> on the 10.8A–10.8H foundation including the
> 10.8A.1 readable scale (preserved, never
> overridden). Utility + integration only: no
> page redesigns, no new product concepts, no
> backend/domain/API change. Task record:
> `tasks/completed/phase-10-8i-settings-notifications-responsive.md`.

## 1. Settings

- `features/settings/SettingsPage.tsx`
  (rewritten into the authenticated shell,
  same `/settings` route): Account (real
  connection fact + Sign out/Connect),
  Organization (honest unavailable),
  Preferences (real `ThemeControl` on the
  existing provider), Notifications
  (honest unavailable), Security (real API
  endpoint + session-storage facts). No
  pretend toggles, no fake persistence.

## 2. Notifications

- Unchanged by design: the shell entry
  stays subtle with its honest empty
  popover (existing 10.8B behavior +
  tests). Nothing is persisted, counted,
  or centered. Verified, not rebuilt.

## 3. Responsive corrections

Minimal, demonstrated-need only (no new
breakpoints, no redesigns):

- `.xb-app-contextbar`: wraps so crumbs
  never force horizontal overflow.
- `100dvh` alongside `100vh` for app and
  sidebar (mobile browser chrome).
- Verified intact: drawer/dialog/focus
  architecture, card grids, req grid,
  archive table↔cards, doc drawer modal,
  landing collapse, form widths.

## 4. Verification

- Focused: settings (5) + shell
  integration (4: single theme state,
  zero notification persistence, no
  bottom nav/concepts, keyboard
  landmarks) + shell CSS pins — green.
- Full suite: 61 files / 395 tests, 0
  failures, none weakened.
- `npx tsc --noEmit` clean; `npm run build`
  succeeds.
- Footprint confirmed via `git status`:
  `App.tsx` (route comment),
  `shell/shell.css`,
  `features/settings/`,
  `features/landing/landing.css`
  (viewport line) only; no backend/domain/
  API/database change, no fake APIs or
  persistence, no navigation redesign.
