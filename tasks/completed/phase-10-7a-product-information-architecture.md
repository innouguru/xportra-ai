# Phase 10.7A — Public Landing Page & Application Information Architecture (Complete, 2026-09-27)

Frontend-only product/UX restructuring. Implementation
record:
`docs/phases/phase-10-7a-product-information-architecture.md`.

## Acceptance criteria

- [x] A clear public landing page exists (`/`, no
      unsupported claims, both CTAs work).
- [x] Public navigation is distinct from authenticated
      application navigation.
- [x] Primary CTA leads toward starting a shipment
      (`/start`); secondary CTA explains the workflow.
- [x] Primary navigation is materially simplified
      (Overview, Shipments, Documents, Requirements,
      Assessment; Ask Xportra + Settings secondary).
- [x] Internal workflow stages are no longer
      top-level destinations; established screens stay
      mounted as deep links.
- [x] Existing functionality remains reachable
      (all capabilities preserved verbatim).
- [x] Ask Xportra remains available but secondary.
- [x] New Shipment presents profile fields; technical
      IDs are generated behind the UI.
- [x] Shipment workspace has contextual navigation;
      Overview functions as command center.
- [x] No backend/API-contract/compliance-semantics/
      tenant-isolation change.
- [x] Focused tests pass; typecheck passes; build
      passes; full frontend tests pass.
- [x] Documentation is complete.

## Artifacts (new, frontend only)

- `frontend/src/features/landing/LandingPage.tsx` (+ test)
- `frontend/src/features/shipment/ShipmentsPage.tsx` (+ test)
- `frontend/src/features/evidence/DocumentsPage.tsx` (+ test)
- `frontend/src/features/assessment/AssessmentPage.tsx` (+ test)
- `frontend/src/features/settings/SettingsPage.tsx` (+ test)
- `frontend/src/lib/shipments.ts` (+ test)

## Artifacts (modified, frontend only)

- `App.tsx` (routes), `AppShell.tsx` (nav),
  `WorkspacePage.tsx` (hero, tabs), `WorkspaceOverview.tsx`
  (command center), `NewShipmentPage.tsx` (profile form),
  `SessionPage.tsx` (post-sign-in target), 12× empty-state
  links (`/` → `/start`), `index.css` (3 additive rules),
  plus test updates confined to navigation assertions.

## Verification

- Focused new suites: 28/28 passing.
- Full suite: 36 files / 208 tests, 0 failures
  (baseline 27/157; +9 files, +51 tests).
- `npx tsc --noEmit` clean; `npm run build` succeeds.
- Backend untouched (verified via `git status` paths).
- No commit/push performed.
