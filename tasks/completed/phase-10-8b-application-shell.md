# Phase 10.8B — Application Shell (Complete, 2026-09-28)

Authenticated-shell task under `REQUIREMENTS.md`
R-10.8 and `docs/decisions/ADR-0012-authenticated-shell-restructure.md`,
composed from the Phase 10.8A foundation. No
backend, domain, compliance, API-contract,
tenant-isolation, or deterministic-semantics
change — and no dashboard content, shipments
table, workspace, settings, or landing work.
Implementation record:
`docs/phases/phase-10-8b-application-shell.md`.

## Acceptance criteria

- [x] Shipment-first shell: sidebar + workspace,
      primary nav exactly Dashboard +
      View Shipments.
- [x] Documents/Requirements/Evidence/Assessment
      absent from primary navigation.
- [x] Expandable/collapsible desktop sidebar
      (~240px, persisted, auto-collapse
      default); accessible labels intact.
- [x] Mobile drawer with dialog semantics,
      focus trap/restore, Escape-to-close.
- [x] Brand opens the public route in a new tab
      without signing out.
- [x] Account control with Profile, Organization,
      Settings, Sign out (existing auth
      boundary; no fake pages).
- [x] Subtle notification entry point, unwired,
      no center, no fake data.
- [x] Dark/light themes through the 10.8A
      infrastructure; compact toggle.
- [x] Breadcrumb/back primitives integrated
      (contextual bar; pages compose the rest).
- [x] Auth/session behavior intact; no second
      auth, router, or state system.
- [x] Accessibility preserved (landmarks,
      `aria-current`, menus, focus, live
      regions, reduced motion, skip link).
- [x] No dashboard/shipment/workspace/landing
      implementation; no backend changes.
- [x] Full suite + tsc + build pass; next task
      clearly identified as Phase 10.8C.

## Artifacts (shell only)

- `frontend/src/shell/AuthenticatedShell.tsx`
  (new), `frontend/src/shell/shell.css` (new)
- `frontend/src/components/BrandMark.tsx`
  (additive props; default unchanged)
- `frontend/src/features/dashboard/DashboardPage.tsx`
  (transitional placeholder)
- `frontend/src/App.tsx` (`/dashboard` +
  `/shipments` routes; old tree untouched)
- `frontend/src/main.tsx` (shell stylesheet)
- Focused tests: `shell/shell.test.ts`,
  `shell/AuthenticatedShell.test.tsx`,
  `shell/AppRoutes.test.tsx`,
  `features/dashboard/DashboardPage.test.tsx`
- `docs/phases/phase-10-8b-application-shell.md`,
  `CURRENT_STATE.md`, `ACTIVE_TASK.md`,
  `ROADMAP.md`

## Verification

- Focused: 5 files / 31 tests passing.
- Full suite: 51 files / 295 tests, 0 failures
  (baseline 47/266; +4 files, +29 tests; none
  weakened).
- `npx tsc --noEmit` clean; `npm run build`
  succeeds.
- Footprint confirmed via `git status`; no
  backend/domain/API/database change.
- No commit/push performed.
