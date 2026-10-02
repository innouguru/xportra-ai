# Phase 10.8G — View Shipments + Historical Report (Complete, 2026-09-28)

Archive + read-only history task under
`REQUIREMENTS.md` R-10.8 and
`docs/decisions/ADR-0012-authenticated-shell-restructure.md`,
composed from the 10.8A–10.8F foundation. No
backend, domain, compliance, API-contract,
tenant-isolation, or deterministic-semantics
change — and no mutations, scores, charts,
PDF invention, or fake data. Implementation
record:
`docs/phases/phase-10-8g-view-shipments-historical-report.md`.

## Acceptance criteria

- [x] "Your shipments" archive with local
      search, honest filters, stable
      attention → active → completed order.
- [x] Desktop table + mobile cards from one
      dataset; text + indicator statuses.
- [x] Completed rows open the historical
      report; never the workspace.
- [x] Historical report: profile, final
      result, requirements, evidence,
      sources, completion facts — read-only.
- [x] No mutation controls exist on history
      (pinned); active references redirect
      honestly.
- [x] No PDF control (no boundary; pinned
      absent); limitation documented.
- [x] No identifiers/scores/technical terms
      (pinned); unavailable fields omitted.
- [x] No 10.8H work; no backend changes.
- [x] Full suite + tsc + build pass; next task
      clearly identified as Phase 10.8H.

## Artifacts (archive + history only)

- `frontend/src/features/shipment/shipmentsArchive.ts`
  (new) + test
- `frontend/src/features/shipment/ShipmentsPage.tsx`
  (rewritten) + test
- `frontend/src/features/shipment/shipments.css`
  (new) + test
- `frontend/src/features/shipment/HistoricalReportPage.tsx`
  (new) + test
- `frontend/src/App.tsx` (report route),
  `main.tsx` (stylesheet),
  `features/dashboard/` + `features/workspace/`
  (report-link retargets), `workspace.ts`
  (shared vocabulary)
- `docs/phases/phase-10-8g-view-shipments-historical-report.md`,
  `CURRENT_STATE.md`, `ACTIVE_TASK.md`,
  `ROADMAP.md`

## Verification

- Focused: 29/29 passing.
- Full suite: 59 files / 376 tests, 0 failures
  (baseline 56/351; +3 files, +25 tests; none
  weakened).
- `npx tsc --noEmit` clean; `npm run build`
  succeeds.
- Footprint confirmed via `git status`; no
  backend/domain/API/database change.
- No commit/push performed.
