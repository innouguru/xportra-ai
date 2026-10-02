# Phase 10.8A — Redesign Foundation (Complete, 2026-09-28)

Frontend-foundation task under `REQUIREMENTS.md`
R-10.8 and
`docs/decisions/ADR-0012-authenticated-shell-restructure.md`.
No backend, domain, compliance, API-contract,
tenant-isolation, or deterministic-semantics
change — and no product pages, shell migration,
or new routes. Implementation record:
`docs/phases/phase-10-8a-redesign-foundation.md`.

## Acceptance criteria

- [x] Minimal frontend audit with
      KEEP/ADAPT/REPLACE/REMOVE recorded
      (nothing deleted).
- [x] Canonical `xb-` design tokens, dark
      default + light theme (color-only
      difference; palette retained).
- [x] Theme infrastructure (provider, hook,
      persistence, system fallback, accessible
      selector for future Settings).
- [x] Typography, spacing, radius (10/12px
      surfaces), elevation, restrained motion
      with reduced-motion support.
- [x] Layout, status, feedback, shipment, and
      requirement primitives (display-only,
      plain-English labels, no domain logic).
- [x] Responsive (860px/640px) and
      accessibility (landmarks, focus, live
      regions, drawer helpers) foundations;
      skip-link behavior preserved.
- [x] Focused + full frontend suites pass;
      tsc clean; build succeeds.
- [x] Next task clearly identified as Phase
      10.8B — Application Shell.

## Artifacts (frontend foundation only)

- `frontend/src/theme/tokens.css` (new)
- `frontend/src/theme/theme.tsx` (new)
- `frontend/src/primitives/primitives.css` (new)
- `frontend/src/primitives/a11y.ts`,
  `layout.tsx`, `status.tsx`, `feedback.tsx`,
  `shipment.tsx` (new)
- Focused tests (new): `theme/tokens.test.ts`,
  `theme/theme.test.tsx`,
  `primitives/primitives.test.ts`,
  `layout/status/feedback/shipment/a11y`
  test files
- `frontend/src/main.tsx` (ThemeProvider +
  stylesheet wiring only)
- `docs/phases/phase-10-8a-redesign-foundation.md`,
  `CURRENT_STATE.md`, `ACTIVE_TASK.md`,
  `ROADMAP.md`

## Verification

- Focused: 8 files / 39 tests passing.
- Full suite: 47 files / 266 tests, 0 failures
  (baseline 39/227; +8 files, +39 tests; none
  weakened).
- `npx tsc --noEmit` clean; `npm run build`
  succeeds.
- Footprint confirmed via `git status`:
  `main.tsx` + `theme/` + `primitives/` only.
- No commit/push performed.
