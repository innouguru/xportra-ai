# Phase 10.7B — Xportra Visual System & Brand Direction

> Implemented 2026-09-27 under `REQUIREMENTS.md` R-10.7B.
> Frontend visual system only. No backend, domain,
> compliance, API-contract, tenant-isolation, or
> deterministic-semantics change. Task record:
> `tasks/completed/phase-10-7b-visual-system-brand-direction.md`.

## 1. Direction

Xportra now presents as a commercial SaaS product:
dark near-black foundation, off-white typography,
one electric-lime brand accent, restrained semantic
colors, strong type hierarchy, generous spacing,
subtle borders, minimal noise. The language of the
system is original to Xportra — no external brand,
logo, wording, illustration, or layout was copied.

## 2. Design tokens

Colors flow through centralized `:root` tokens; no
component carries a literal color (pinned by test):

- Foundations: near-black background, two elevated
  dark surfaces.
- Typography: off-white primary, muted secondaries
  (both AA+ on the foundation).
- Brand accent (electric lime) reserved for identity
  and primary actions; hover brightens, foreground
  stays near-black.
- Semantic states keep their own colors, visually
  distinct from brand: success green, warning amber,
  error red, info blue — each with text + indicator,
  never color alone.

Legacy token names remain defined as aliases so
existing components keep working unchanged.

## 3. Brand mark

`BrandMark` renders the existing wordmark plus a
glyph slot, used in the shell. The slot carries no
invented geometry — when an X/P monogram asset is
explicitly approved, only the slot contents change.
Tests pin the absence of SVG/path/img artwork.

## 4. Shell, landing, workspace

- Wide screens (≥1100px) lay the shell out as a
  sidebar (brand, primary nav, secondary, session);
  below that the wrapping topbar is unchanged. DOM
  order, roles, and labels are identical in both.
- Landing hero composes eyebrow, display headline
  ("Export with confidence."), approved subcopy,
  both CTAs, and a principles row of true product
  attributes — no wall of text, no invented claims.
- Workspace tabs keep the restrained selected state
  (bold + lime underline + tint), now unambiguous on
  dark. Button hierarchy: one lime primary per
  action group, outlined secondary, text tertiary.
- Cards keep meaningful grouping; surfaces flatten
  through tokens rather than new chrome. The
  conversation drawer keeps its behavior with an
  elevated assistant surface.

## 5. Compliance semantics preserved

Satisfied/supported/ready stay informational blue;
information-needed and unknown stay attention amber;
not-satisfied and failed stay attention red with
words doing the work; uploaded/absent stay neutral.
Tone mappings are untouched — only their dark-theme
values changed, all contrast-checked. Statuses still
render verbatim with badges, flags, and explicit
state text.

## 6. Responsive and accessibility

Drawer becomes a bottom sheet under 860px (unchanged
breakpoint); fluid grids, wrapping identifiers, and
sticky composer carry over. Native controls, labels,
`role="alert"` errors, `aria-live` statuses, dialog
focus trap/return/Escape, visible lime focus
outlines, control-height targets, and reduced-motion
support are all preserved. Verified statically and
in jsdom; no browser engine was available, so no
pixel-perfect claim is made.

## 7. Verification

- Focused: design-token contract (10), brand mark
  (2), landing hero (2 new), compliance tones (4),
  shell artwork guard (1) — all passing.
- Full frontend suite: **39 files / 227 tests
  passing** (baseline 36/208; +3 files, +19 tests),
  0 failures. No existing test weakened.
- `npx tsc --noEmit` clean; `npm run build`
  succeeds (68 modules).
- Backend untouched: no backend suite re-run
  required. Live services not executed (no
  environment), as before. No packages installed.

## 8. Explicitly NOT implemented

Final X/P monogram artwork (separate approval);
light theme or theme switcher; new product
capabilities; conversational upload; chat changes;
evidence deletion; retention policy; workflow
reopening; background queue; notifications; RAG,
reasoning, or compliance-rule changes; provider
migration; deployment infrastructure. No
commit/push performed.
