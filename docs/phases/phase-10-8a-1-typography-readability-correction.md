# Phase 10.8A.1 — Typography & Readability Correction

> Implemented 2026-09-28 as a focused
> correction over the Phase 10.8A foundation
> (`docs/phases/phase-10-8a-redesign-foundation.md`,
> unchanged). Canonical token values only,
> plus three token-consuming declarations —
> no page redesign, no navigation, route,
> color, spacing, or backend change. Task
> record:
> `tasks/completed/phase-10-8a-1-typography-readability-correction.md`.

## 1. Canonical scale (both themes, shared)

| Token | Before | After |
| ----- | ------ | ----- |
| `--xb-text-display` | 1.75rem | `clamp(2.5rem, 1.25rem + 5vw, 3.25rem)` (52px cap, 40px floor) |
| `--xb-text-title` | 1.375rem | 1.875rem (30px) |
| `--xb-text-section` | 1.125rem | 1.375rem (22px) |
| `--xb-text-card` | 1rem | 1.125rem (18px) |
| `--xb-text-lead` (new) | — | 1.125rem (18px) |
| `--xb-text-body` | 0.95rem | 1rem (16px) |
| `--xb-text-small` | 0.85rem | 0.9375rem (15px) |
| `--xb-text-meta` | 0.75rem | 0.8125rem (13px minimum) |
| `--xb-leading-body` | 1.6 | unchanged |

No component CSS needed value changes:
every surface already consumes these
tokens, so landing, shell, dashboard,
cards, requirements, forms, archive, and
verification all step up together.

## 2. Token-consuming declarations

- `.xb-app`, `.xb-land`: 16px body
  baseline + body leading (previously
  inherited 15.5px from frozen legacy CSS).
- `.xb-status`: body line-height so
  multi-word statuses never collapse
  against their indicator.
- `.xb-page-header__description`,
  `.xb-land-lede`: lead token.

## 3. Verification

- New readability contract in
  `theme/tokens.test.ts` (minimums +
  strict hierarchy + hero floor +
  leading, both themes); hero/lede pins
  in landing + primitives contract tests.
- Focused theme/primitives/landing/shell:
  13 files green.
- Full suite: 60 files / 388 tests, 0
  failures (baseline 60/383; +5 tests;
  none weakened).
- `npx tsc --noEmit` clean; `npm run build`
  succeeds.
- Footprint: `theme/tokens.css`,
  `shell/shell.css`,
  `features/landing/landing.css`,
  `primitives/primitives.css`, and test
  files only. No backend/database/route/
  navigation/design-system changes.
