# Task: Phase 4D Milestone 7 — Staff Regulatory Ingestion Dashboard

**Status:** Completed and verified (2026-10-29).
**Authorization basis:** Explicitly assigned by user tasking. Backend/production
authorization state unchanged; no grants created or revoked; no push.

## Context recovered on inspection

A prior closeout claimed this milestone complete, but inspection of the
repository showed:

- `frontend/src/features/ingestion/` held a non-compiling file (JSX
  fragments interleaved inside callback bodies, references to an
  undefined `children` value, one-argument calls to `(credentials, id)`
  API functions, imports of decision-submitting functions that were
  never used, and no decision forms).
- The "Regulatory Ingestion" nav item pointed at `/regulatory-ingestion`,
  which was not registered (fell through to `/`).
- A complete, committed, tested staff surface
  (`features/regulatory/RegulationAdminPage.tsx`, route `/regulatory`)
  already implements the entire ingestion-to-review workflow.

## Implemented

1. `features/ingestion/IngestionDashboard.tsx` — rewritten as the
   navigation-facing entry point for `/regulatory-ingestion`, composing
   the tested `RegulationAdminPage` (single implementation of the
   authorization-sensitive workflow; no duplicated privileged logic).
2. `App.tsx` — `/regulatory-ingestion` registered behind `RequireAuth` +
   `AuthenticatedShell`; `/regulatory` deep link unchanged.
3. `AuthenticatedShell.test.tsx` — nav assertion strengthened to three
   destinations including `/regulatory-ingestion`; shell/css comments
   updated.
4. Backend contract corrections (`frontend/src/api/regulatory.ts` +
   `RegulationAdminPage.tsx`):
   - Stage B `pilot_scope` is mandatory server-side
     (`RegulatoryStageBReviewRequest`, `min_length=1`); the form now
     requires it and never sends `null`.
   - Stage B `evidence_references` is `list[dict]` server-side; the
     comma-separated string input (guaranteed 422) was removed and
     history entries render reference objects verbatim.
5. Stale-response guard: source-detail and candidate-review loads are
   request-token sequenced so late responses for previous selections
   cannot overwrite current state.
6. Manual candidate entry is explicitly identified as a separate
   backend-backed capability in the empty state, not simulated.

## Not offered (and why)

- No job retry action: no staff retry endpoint exists (retryable jobs
  are reclaimed automatically by the worker).
- No publication/applicability action: eligibility is backend-only
  (`GET .../eligibility`), and publication is not a frontend capability.

## Tests and verification

- New `IngestionDashboard.test.tsx`: 9/9 pass (renders/inspects sources
  with jobs+candidates at the nav route, authorization denial as error,
  Stage A payload + refresh, duplicate-submission prevention while
  pending, Stage B pilot-scope requirement + exact supported payload,
  no publication controls, stale-response discard, empty state,
  error + retry). API calls are mocked at the existing fetch boundary.
- Full frontend suite: 582 passed / 1 failed. The failure
  (`RegisterPage.test.tsx` "retains pending profile data...") is
  pre-existing and unrelated: it asserts `sessionStorage` while
  `app/pendingRegistration.ts` intentionally persists in `localStorage`
  (AuthCallbackPage tests assert `localStorage`). Recommend a separate
  one-line correction task.
- `npm run lint` (tsc --noEmit): pass. `npm run build`: pass (existing
  large-chunk advisory).
- Backend focused regression: Stage A review, Stage B review,
  publication eligibility, source intake, worker, eligible-requirements
  endpoint, governance-blocks-Stage-B — 112/112 pass.
- PostgreSQL integration tests skipped: no `DATABASE_URL` in this
  environment. All passing results are mocked/unit-level; no database
  integration was exercised and no production system was contacted.

## Files changed

- `frontend/src/features/ingestion/IngestionDashboard.tsx` (rewritten)
- `frontend/src/features/ingestion/IngestionDashboard.test.tsx` (new)
- `frontend/src/features/regulatory/RegulationAdminPage.tsx`
  (pilot-scope required, evidence-ref contract, stale guards, honest
  empty-state copy)
- `frontend/src/api/regulatory.ts` (Stage B payload + history types)
- `frontend/src/api/regulatory.test.ts` (Stage B payload expectation)
- `frontend/src/App.tsx` (route registration + doc comment)
- `frontend/src/shell/AuthenticatedShell.tsx` (nav item already present;
  doc comment updated)
- `frontend/src/shell/AuthenticatedShell.test.tsx` (nav assertions)
- `frontend/src/shell/shell.css` (comment)
- `ACTIVE_TASK.md`, `CURRENT_STATE.md` (state documentation)
