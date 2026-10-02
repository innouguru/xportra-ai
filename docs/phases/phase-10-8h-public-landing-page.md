# Phase 10.8H — Public Landing Page

> Implemented 2026-09-28 under `REQUIREMENTS.md`
> R-10.8 (R-10.8.2, R-10.8.12, R-10.8.15) and
> `docs/decisions/ADR-0012-authenticated-shell-restructure.md`.
> Public route only: dedicated chrome, R-10.8.12
> copy, captioned illustration, quiet CTA and
> footer. No workspace/auth changes, no claims
> beyond the implemented product. Task record:
> `tasks/active/phase-10-8h-public-landing-page.md`.

## 1. What was built

- `features/landing/LandingPage.tsx`
  (rewritten, same `/` route): public nav
  (brand, section anchors, Sign In, Start a
  Shipment), hero (R-10.8.12 eyebrow,
  headline, supporting message, two CTAs,
  no-certification note), captioned static
  preview from real primitives, audience
  section (Nigeria factual/restrained),
  four how-it-works steps (01–04 per
  R-10.8.12), value grid, trust section
  with no-guarantee note, quiet CTA,
  minimal footer with real routes only.
  No `AppShell` — the page renders
  identically signed in or out, so
  workspace navigation cannot leak.
- `features/landing/landing.css`:
  token-only public styles, single 860px
  breakpoint, focus + reduced motion.

## 2. Copy reconciliation

- R-10.8 is canonical over the task brief:
  four steps (Create/Determine/Verify/Get
  ready) instead of three; CTAs "Start a
  Shipment" / "Sign In" instead of "Get
  started" / "Sign in" (footer keeps one
  "Get started" link to the real `/start`
  route). The three task-brief concepts
  are covered across steps 1/2/3–4.
- Preview sample content is visibly
  captioned as illustration, never
  presented as a live shipment.

## 3. Verification

- Focused: page (7) + CSS contract (5) —
  12/12 passing (hero, sections, routes,
  signed-in separation, scope pins).
- Full suite: 60 files / 383 tests passing
  (baseline 59/376; +1 file, +7 tests),
  0 failures, none weakened.
- `npx tsc --noEmit` clean; `npm run build`
  succeeds.
- Footprint confirmed via `git status`:
  `main.tsx` (stylesheet) +
  `features/landing/` only; no auth,
  backend/domain/API/database change, no
  fake claims/data/endpoints, no 10.8I work.
