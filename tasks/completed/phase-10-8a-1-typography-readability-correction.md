# Phase 10.8A.1 — Typography & Readability Correction (Complete, 2026-09-28)

Focused correction over the Phase 10.8A
foundation: 16px body baseline, 13px micro
minimum, stronger hierarchy, clamp hero.
No page redesign, navigation, routes,
colors, spacing, backend, or second design
system. Implementation record:
`docs/phases/phase-10-8a-1-typography-readability-correction.md`;
Phase 10.8A record unchanged.

## Acceptance criteria

- [x] Canonical tokens retuned in both themes
      (display clamp 40–52px, title 30px,
      section 22px, card/lead 18px, body
      16px, small 15px, meta 13px).
- [x] Readable baseline on app + landing
      roots; status line separation; lead
      descriptions.
- [x] Landing hero follows the new scale;
      nav/cards/forms/archive readable.
- [x] No tiny text below the 13px minimum;
      responsive + a11y foundations intact.
- [x] Full suite + tsc + build pass; next is
      Phase 10.8I.

## Artifacts

- `frontend/src/theme/tokens.css` (scale +
  lead token, both themes)
- `frontend/src/shell/shell.css`,
  `frontend/src/primitives/primitives.css`,
  `frontend/src/features/landing/landing.css`
  (base size, status leading, lead usage)
- `frontend/src/theme/tokens.test.ts`
  (readability contract), landing + primitives
  contract pins
- `docs/phases/phase-10-8a-1-typography-readability-correction.md`,
  `CURRENT_STATE.md`, `ACTIVE_TASK.md`,
  `ROADMAP.md`

## Verification

- Focused theme/primitives/landing/shell:
  13 files green.
- Full suite: 60 files / 388 tests, 0 failures
  (baseline 60/383; +5 tests; none weakened).
- `npx tsc --noEmit` clean; `npm run build`
  succeeds.
- No commit/push performed.
