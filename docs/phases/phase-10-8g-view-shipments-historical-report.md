# Phase 10.8G — View Shipments + Historical Report

> Implemented 2026-09-28 under `REQUIREMENTS.md`
> R-10.8 and
> `docs/decisions/ADR-0012-authenticated-shell-restructure.md`,
> composed from the 10.8A–10.8F foundation.
> Archive + read-only history only: local
> search/filter/order, completed-report route,
> no mutations, no PDF boundary, no
> backend/domain/API change. Task record:
> `tasks/active/phase-10-8g-view-shipments-historical-report.md`.

## 1. What was built

- `features/shipment/shipmentsArchive.ts`:
  pure local query over the registry —
  profile-text search, status/product/
  destination/date filters (date only when
  stored), stable attention → active →
  completed order.
- `features/shipment/ShipmentsPage.tsx`
  (rewritten, same route/export): "Your
  shipments" with search, user-worded
  filters, count live region, desktop table
  (Shipment/Destination/Status/Date-if-any/
  Action) + mobile cards from one dataset,
  contextual open actions, device-only
  Forget, honest empty/no-result/error
  states. Completed rows open the report
  route without activating the record.
- `features/shipment/shipments.css`:
  token-only table/filter styles, single
  860px transformation.
- `features/shipment/HistoricalReportPage.tsx`
  (`/shipments/:caseId/report`): back nav,
  identity + Completed indicator, quiet
  final result from stored findings,
  requirement outcomes, supplied evidence
  with authorized open, safe-string
  sources, real completion facts (round
  count, finalized state), Start-new link.
  Active/unknown references get honest
  notices; zero mutation controls exist.
- Retargets: dashboard + workspace terminal
  "View report" → the historical route
  (same-strictness tests); `requirementVocabulary`
  exported for shared wording.

## 2. Honest-data decisions

- No timestamps/activity exist — no Updated
  column, no completion dates. Date filter/
  column render only when profiles store
  dates.
- Findings render only from the fetched
  stored report (case-gated); otherwise
  profile + evidence still stand.
- Sources show safe string fields,
  deduplicated; unknown shapes never dump
  as JSON. No identifiers, scores, or
  reasoning internals shown.
- No PDF boundary exists — no Download PDF
  control (tested absent). "New from
  completed" = the existing `/start` form
  (no clone endpoint exists).
- Registry staleness after supply mirrors
  existing behavior; archive re-reads the
  registry on everyForget/retry.

## 3. Verification

- Focused: archive lib (8) + page (8) +
  report (8) + CSS contract (5) — 29/29
  passing (ordering, search, filters,
  read-only pins, absence pins, retry).
- Full suite: 59 files / 376 tests passing
  (baseline 56/351; +3 files, +25 tests),
  0 failures, none weakened — including
  the formerly flaky evidence file.
- `npx tsc --noEmit` clean; `npm run build`
  succeeds.
- Footprint confirmed via `git status`:
  `App.tsx`, `main.tsx`,
  `features/shipment/` (archive + report),
  `features/dashboard/` + `features/workspace/`
  (report-link retargets) only; no
  backend/domain/API/database change, no
  fake persistence or data, no 10.8H work.
