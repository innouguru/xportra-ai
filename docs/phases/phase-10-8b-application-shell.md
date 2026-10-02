# Phase 10.8B — Application Shell

> Implemented 2026-09-28 under `REQUIREMENTS.md`
> R-10.8 (R-10.8.1–R-10.8.6, R-10.8.13–R-10.8.14
> shell concerns) and
> `docs/decisions/ADR-0012-authenticated-shell-restructure.md`,
> composed from the Phase 10.8A foundation
> (`docs/phases/phase-10-8a-redesign-foundation.md`).
> Authenticated shell only: sidebar, navigation,
> brand behavior, account entry, notification
> entry, theme usage, workspace frame, two
> routes. No dashboard content, no shipments
> table, no workspace/settings/landing work, no
> backend/domain/API change. Task record:
> `tasks/active/phase-10-8b-application-shell.md`.

## 1. What was built

- `shell/AuthenticatedShell.tsx`: desktop
  expandable sidebar (240px; persisted
  preference with auto-collapse default under
  1100px), mobile dialog drawer (scrim,
  focus trap, Escape, focus restore), exactly
  two primary destinations with `aria-current`,
  new-tab brand, account menu (Profile /
  Organization disabled-honest "Soon",
  Settings link, Sign out / Sign in through
  `useAuth`), unwired notification popover,
  compact theme toggle through `useTheme`,
  contextual breadcrumb bar + skip link.
- `shell/shell.css`: token-only styles
  (240px contract, selected indicator + bold,
  drawer/scrim, menus, focus, reduced motion).
- `components/BrandMark.tsx`: additive
  `newTab` (new-tab public link, session
  untouched) and `compact` (glyph-only)
  props; default output byte-identical.
- `features/dashboard/DashboardPage.tsx`:
  transitional placeholder reserving the
  "Your shipments" title; no cards/metrics.
- `App.tsx`: `/dashboard` (placeholder) and
  `/shipments` (existing list, unmodified)
  served inside the new shell; public `/`,
  `/workspace` tree, and `/settings` untouched.

## 2. Verification

- Focused: `shell/*` + dashboard + BrandMark —
  5 files / 31 tests passing (nav exactness,
  old-concept absence, collapse, brand
  new-tab + session intact, account menu +
  sign-out boundary, notifications, theme,
  drawer dialog + trap + restore, landmarks,
  route separation).
- Full suite: 51 files / 295 tests passing
  (baseline 47/266; +4 files, +29 tests),
  0 failures, none weakened.
- `npx tsc --noEmit` clean; `npm run build`
  succeeds.
- Footprint confirmed via `git status`:
  `App.tsx`, `BrandMark.tsx`, `main.tsx`
  (stylesheet import), `shell/`,
  `features/dashboard/` only; no
  backend/domain/API/database change, no fake
  persistence or data, no product pages.
