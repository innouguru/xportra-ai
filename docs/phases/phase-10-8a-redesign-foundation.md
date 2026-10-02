# Phase 10.8A — Redesign Foundation

> Implemented 2026-09-28 under `REQUIREMENTS.md`
> R-10.8 (R-10.8.3–R-10.8.9, R-10.8.13–R-10.8.15
> foundation concerns) and
> `docs/decisions/ADR-0012-authenticated-shell-restructure.md`.
> Frontend foundation only: canonical tokens,
> theme infrastructure, reusable primitives. No
> product pages, no shell migration, no routes
> added, no backend/domain/API change. Task
> record:
> `tasks/active/phase-10-8a-redesign-foundation.md`.

## 1. Audit classification

Inspected: build setup (`package.json`,
`vite.config.ts`, `main.tsx`), routing
(`App.tsx`), `AppShell`, `BrandMark`,
`index.css` + token tests, `StatusBits`,
`api/*`, `app/*` contexts, `lib/*` helpers,
all feature pages, `SettingsPage`.

- KEEP: `api/*` + tests (typed backend
  boundary), `app/*` contexts (auth/workflow/
  analysis/assessment), `lib/*` helpers +
  compliance-tone pins, conversation feature,
  all feature pages (untouched; replaced by
  later 10.8 phases), `BrandMark` structure and
  glyph seam (no new mark invented),
  `index.css` + `index.css.test.ts` frozen for
  existing components, skip-link behavior.
- ADAPT: `StatusBits` states stay for old
  pages; canonical `primitives/feedback.tsx`
  mirrors their prop shapes so 10.8B+ pages
  migrate by changing the import path. Button
  classes (`.primary-button` etc.) are reused,
  not duplicated, by new primitives.
- REPLACE (later, not in 10.8A):
  topbar-oriented shell styling and concept
  navigation migrate in 10.8B; old components
  migrate off `index.css` tokens in later
  phases. Nothing replaced yet.
- REMOVE: nothing. No code deleted in 10.8A.

## 2. Foundation established

- `theme/tokens.css`: canonical `xb-`
  namespaced tokens — backgrounds, surfaces,
  borders, three text tiers, lime brand +
  foreground + subtle tint, four semantic
  colors each with a subtle tint, focus,
  disabled, 7-step type scale, 8-point spacing
  scale + gutters + control height + measure,
  three radii (10px/12px surfaces), three
  elevation levels, two motion durations.
  Dark default (brand values match the frozen
  direction); `[data-theme="light"]` overrides
  in color only.
- `theme/theme.tsx`: `ThemeProvider`
  (localStorage `xportra.theme.mode.v1`,
  system-preference fallback + live follow,
  publishes `data-theme`), safe `useTheme`
  fallback, accessible `ThemeControl`
  radiogroup for the future Settings surface.
- `primitives/primitives.css`: token-only
  styles (no literals, gradients, or glass)
  for workspace, page header, breadcrumbs,
  back button, topbar/sidebar slot
  containers, status/badge/metric/attention,
  empty/loading/error, card grid + cards with
  stretched-link pattern, summary rows,
  requirement cards, theme control;
  860px/640px breakpoints, visible focus,
  reduced-motion rules.
- `primitives/layout.tsx`: WorkspaceContainer,
  PageHeader, Breadcrumbs, BackButton,
  TopBar, Sidebar (brand/nav/footer slots +
  collapsed class; items/drawer are 10.8B).
- `primitives/status.tsx`: StatusTone +
  StatusIndicator, StatusBadge,
  MetricSummary, AttentionIndicator.
- `primitives/feedback.tsx`: EmptyState,
  LoadingState, ErrorState.
- `primitives/shipment.tsx`: ShipmentStatus,
  ShipmentCard (whole-card link + separately
  focusable action), ShipmentSummary,
  RequirementStatus, RequirementCard,
  DocumentStatus — display-only props,
  plain-English labels, no domain logic.
- `primitives/a11y.ts`: `useEscapeKey`,
  `useFocusRestore` for 10.8B+ drawers.
- `main.tsx`: imports tokens + primitives
  after `index.css`; wraps the app in
  `ThemeProvider` (default dark = no visual
  change to existing UI).

## 3. Verification

- Focused: 8 files / 39 tests passing
  (`theme/*`, `primitives/*`).
- Full suite: 47 files / 266 tests passing
  (baseline 39/227; +8 files, +39 tests),
  0 failures, 0 skips changed.
- `npx tsc --noEmit` clean; `npm run build`
  succeeds (both themes compile through the
  shared token system).
- `git status` confirms the footprint is
  `main.tsx` + `theme/` + `primitives/` only;
  no backend/domain/API/database change, no
  fake persistence, no product pages.
