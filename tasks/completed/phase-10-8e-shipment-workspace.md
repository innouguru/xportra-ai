# Phase 10.8E — Shipment Workspace (Complete, 2026-09-28)

Briefing-dominant workbench task under
`REQUIREMENTS.md` R-10.8 and
`docs/decisions/ADR-0012-authenticated-shell-restructure.md`,
composed from the 10.8A–10.8D foundation. No
backend, domain, compliance, API-contract,
tenant-isolation, or deterministic-semantics
change — and no verification engine, archive,
historical report, settings, scores, charts,
or fake data. Implementation record:
`docs/phases/phase-10-8e-shipment-workspace.md`.

## Acceptance criteria

- [x] `/shipments/:caseId` workspace with
      identity, back nav, crumbs, status.
- [x] Dominant plain-English briefing + one
      primary action over existing routes.
- [x] Compact details with explicit unknowns;
      side panel desktop, stacked mobile.
- [x] Requirement work items from
      case-matched findings (approved
      vocabulary, disclosure, missing lists);
      honest fallbacks; real progress only.
- [x] Document drawer seam (dialog, Escape,
      trap, restore; honest 10.8F notice).
- [x] Completed shipments read-only, no
      mutating controls, no reopening.
- [x] No technical states user-facing
      (pinned); responsive; accessible.
- [x] Dashboard entry opens retargeted to the
      new route (same-strictness tests).
- [x] No 10.8F/G work; no backend changes.
- [x] Full suite + tsc + build pass; next task
      clearly identified as Phase 10.8F.

## Artifacts (workspace only)

- `frontend/src/features/workspace/workspace.ts`
  (new), `ShipmentWorkspacePage.tsx` (new),
  `DocumentDrawer.tsx` (new),
  `workspace.css` (new)
- `frontend/src/features/workspace/workspace.test.ts`
  (new), `ShipmentWorkspacePage.test.tsx` (new)
- `frontend/src/App.tsx` (`/shipments/:caseId`),
  `main.tsx` (stylesheet),
  `features/dashboard/` (destination retarget),
  `primitives/shipment.tsx` (additive children)
- `docs/phases/phase-10-8e-shipment-workspace.md`,
  `CURRENT_STATE.md`, `ACTIVE_TASK.md`,
  `ROADMAP.md`

## Verification

- Focused: 16/16 passing.
- Full suite: 54 files / 334 tests, 0 failures
  (baseline 52/318; +2 files, +16 tests; none
  weakened).
- `npx tsc --noEmit` clean; `npm run build`
  succeeds.
- Footprint confirmed via `git status`; no
  backend/domain/API/database change.
- No commit/push performed.
