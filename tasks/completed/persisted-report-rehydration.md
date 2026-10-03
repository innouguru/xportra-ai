# Persisted Report Rehydration — Complete

Makes the backend-persisted analysis report visible
again after frontend reload: a shared
`useStoredReport` hook resolves the effective report
(in-memory first, else the latest recorded round's
report fetched once through the existing
`GET /compliance/reports/{report_id}` endpoint and
adopted into `AnalysisContext`), with distinct
loading/empty/error states.

Scope honored: no UI redesign, no state-machine
change, no new persistence (nothing duplicated into
browser storage), no second report API, no backend
change, no data-model change. `AnalysisContext`
keeps its narrow in-memory-cache role.

## What changed

- `frontend/src/app/useStoredReport.ts` (new): shared
  hook + `latestStoredReportId` + `StoredReportStatus`
  (`ready`/`loading`/`empty`/`error`). No fetch when
  memory holds a report or no rounds exist; one
  cancel-safe fetch otherwise; never clobbers a newer
  in-memory report; never shows another workflow's
  fetched report.
- `frontend/src/features/analysis/FindingsPage.tsx`:
  precedence in-memory → loading state → error
  (404-shaped `not_found`/`resource_not_found` renders
  the distinct "Report unavailable" empty state, other
  failures render `ErrorNotice`) → genuine "No
  analysis yet". Identical report rendering path.
- `frontend/src/features/workspace/ShipmentWorkspacePage.tsx`:
  feeds the rehydrated report into the existing
  `describeWorkspace`; no visual change otherwise.

## Verification

- New `frontend/src/app/useStoredReport.test.tsx`:
  4/4 (A no-fetch, B fetch-once + adopt, C empty,
  D error distinct from absence).
- `FindingsPage.test.tsx` +4 (persisted render after
  reload, loading state, 500 error, 404 absence);
  `ShipmentWorkspacePage.test.tsx` +1 (workspace
  findings restored after reload). Existing tests
  untouched in behavior.
- Full frontend suite: 63 files / 426 tests, 0
  failures. `npx tsc --noEmit` clean (one
  mock-typing fix using the existing cast pattern).
  `npm run build` succeeds.
