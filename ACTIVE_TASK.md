# ACTIVE_TASK.md — Current Active Task

## Task: Persisted Report Rehydration

**Status:** Complete (2026-10-03).

Frontend-only: shared `useStoredReport` hook
rehydrates the backend-persisted analysis report
through the existing stored-report endpoint, so
FindingsPage and the shipment workspace render it
after reload instead of showing "Run an analysis
first". Distinct loading/empty/error states; no UI
redesign, no backend change, no browser persistence.

Verification: new hook suite 4/4; FindingsPage +4,
workspace +1; full frontend suite 63 files / 426
tests, 0 failures; `npx tsc --noEmit` clean;
`npm run build` succeeds. Task record:
`tasks/completed/persisted-report-rehydration.md`.
Committed; push not requested.
