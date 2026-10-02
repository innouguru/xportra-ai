# Phase 10.8E — Shipment Workspace

> Implemented 2026-09-28 under `REQUIREMENTS.md`
> R-10.8 and
> `docs/decisions/ADR-0012-authenticated-shell-restructure.md`,
> composed from the 10.8A/10.8B/10.8C/10.8D
> foundation. Workspace only: briefing,
> primary action, details, requirements, doc
> seam, read-only completed state. No
> verification engine, archive, report,
> settings, or backend/domain/API change. Task
> record:
> `tasks/active/phase-10-8e-shipment-workspace.md`.

## 1. What was built

- `features/workspace/workspace.ts`: pure
  mapping over the client record, registry
  profile, and case-matched in-memory report
  — briefing + attention flag, single
  primary action over existing routes,
  findings → approved vocabulary with
  explanations/missing lists, honest
  open-count/none fallbacks, addressed/total
  progress, explicit-unknown details. Raw
  workflow states never reach the UI.
- `features/workspace/ShipmentWorkspacePage.tsx`:
  `/shipments/:caseId` page (entry lookup,
  record sync for deep links, cross-shipment
  report gating) — back nav, crumbs,
  identity + status, dominant briefing, one
  primary CTA, quiet read-only banner for
  completed records, requirements grid,
  documents panel, side details (stacked on
  mobile), honest empty state.
- `features/workspace/DocumentDrawer.tsx`:
  dialog drawer seam (Escape, trap, restore,
  autofocus; full-width modal ≤860px) with
  requirement context, honest 10.8F notice,
  real documents link, explicitly disabled
  Verify action.
- `features/workspace/workspace.css`:
  token-only briefing/layout/drawer styles.
- `App.tsx`: `/shipments/:caseId` route;
  dashboard entry opens retargeted from
  `/workspace` to the new route (same
  strictness assertions, updated targets).

## 2. Honest-data decisions

- Requirements render only from the
  case-matched in-memory report; otherwise
  the open-requirement count or an honest
  "none identified yet" panel — never
  fabricated cards or progress.
- Sources with unknown shapes are not
  rendered; "Why required?" shows the
  backend explanation string only.
- Activity omitted: no client-side source
  exists; 10.8G covers history. Timestamps,
  ports, scores, charts omitted likewise.
- Completed records: banner + zero mutating
  controls on this page (deep-link legacy
  surfaces migrate in later phases).

## 3. Verification

- Focused: translation (9) + page (7) —
  16/16 passing (briefing, actions,
  vocabulary, progress, fallbacks, drawer,
  read-only, empty, scope pins).
- Full suite: 54 files / 334 tests passing
  (baseline 52/318; +2 files, +16 tests),
  0 failures, none weakened.
- `npx tsc --noEmit` clean; `npm run build`
  succeeds.
- Footprint confirmed via `git status`:
  `App.tsx`, `main.tsx` (stylesheet),
  `features/workspace/`,
  `features/dashboard/` (destination
  retarget only) + additive `RequirementCard`
  children; no backend/domain/API/database
  change, no fake persistence or data, no
  10.8F/G work.
