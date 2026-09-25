# Phase 9 — Frontend Pass 2: Evidence, Analysis & Findings Review

**Status:** Complete and verified (2026-09-24)
**Phase:** Phase 9 — Frontend Implementation
**Type:** React + TypeScript presentation work; no compliance logic, no backend changes

> This record describes what was actually implemented and verified.

## Objective

Implement Pass 2 of the UI/Product Architecture journey:
evidence reference intake, evidence gaps, case-readiness
display, analysis runs, and the Findings Review screen —
against the frozen backend API, without modifying it.

## API endpoints integrated (Pass 2)

- `POST /compliance-evidence` and
  `POST /compliance-evidence/with-requirements` (201,
  member-allowed) — reference intake, never file bytes.
- `GET /compliance-evidence/{evidence_id}` — record reads.
- `POST /compliance/workflows/supply-evidence` —
  hand recorded evidence to the workflow.
- `POST /compliance/workflows/submit-for-review` —
  mark analysis reviewed.
- `POST /compliance/assessments/case-readiness` —
  readiness state plus typed gaps, rendered verbatim.
- `POST /compliance/workflows/analyze` — first runs
  and re-runs (the state machine routes passes);
  updated record retained, report held in memory.

## Evidence UX

Intake registers title/type/URI references (optional
requirement links at intake) and then supplies recorded
IDs to the workflow; the form states explicitly that no
file upload exists. Supplied IDs render from the
workflow record; per-record detail reads back through
`GET`. No drag-and-drop, no progress fakery, no byte
handling anywhere.

## Gaps and readiness UX

Case views are assembled only from held or typed
records (requirement identity/text, recorded
applicability/assessment outcomes, evidence
references) via the shared `CaseBuilder`; the backend
validates. `readiness_state` and gap `kind`/`reason`
render verbatim — missing, insufficient, unknown, and
contradictory states are information needs, never
non-compliance, failure, scores, or percentages.

## Analysis flow

Pre-run panel shows evidence coverage plus current
workflow state and round number; analysis is an
explicit, single-flight operation (duplicate submission
prevented, no fabricated progress); success stores the
report in memory, retains the updated record, and
navigates to review; failures preserve usable state
and surface backend semantics unchanged.

## Findings architecture

`FindingCard` renders every DTO section — requirement,
applicability, assessment, explanation, supporting and
conflicting evidence, sufficiency, missing
information, sources/provenance, uncertainty —
with contradictions displayed, never resolved.
Report counts describe the received report; badge
values are constrained by test to verbatim backend
vocabulary. No scores, verdicts, percentages, or
numeric confidence exist.

## Routes/screens implemented (Pass 2)

- `/workspace/evidence` — intake + session register +
  supplied list.
- `/workspace/gaps` — case assembly + readiness outcome.
- `/workspace/analysis` — readiness panel + case
  assembly + run/re-run.
- `/workspace/review` — findings review centerpiece
  (empty state routes to analysis when no report).

## Important UX decisions

- Case assembly is explicit structured input, never
  inferred; malformed cases fail server-side with
  surfaced errors.
- Reports live in memory only (`AnalysisContext`);
  only identifiers + process state persist to
  sessionStorage, matching the server transfer
  contract.
- Terminal workflows disable analysis via the
  backend 409 path (no frontend state-machine
  duplication beyond presenting `is_closed`-style
  state when already known).

## Tests run and exact results

- `npx tsc --noEmit`: clean, 0 errors.
- `npx vitest run`: **18 files, 73 tests, all passing**
  (35 Pass 1 + 38 new: 3 evidence API, 2 analysis API,
  1 assessments API, 4 evidence lib, 4 findings lib,
  2 CaseBuilder, 4 FindingCard, 5 EvidencePage,
  3 GapsPage, 5 AnalysisPage, 4 FindingsPage, plus
  adjusted navigation coverage).
- `npm run build` (tsc + vite bundle): succeeds.
- Backend suite: not re-run (zero backend files
  changed — verified via `git status`; pre-existing
  backend modifications belong to prior sessions).

## Backend files changed, if any

None.

## Blockers or API gaps

None for Pass 2 scope. Deferred gaps unchanged from
Pass 1 (file upload, workflow listing/resume,
standalone readiness read, role introspection).

## Documentation updated

- This phase document.
- `tasks/completed/phase-9-frontend-pass-2.md`.
- `CURRENT_STATE.md` (Pass 2 entry).
- `ACTIVE_TASK.md` (this task, complete).

## What remains for Pass 3

Additional Evidence loop UI (request-additional-
evidence trigger already exists server-side),
Final Review/Finalize (explicit confirm + terminal
handling), Assessment Package, stored Report, and
History views. Test + build gates repeat. No backend
changes anticipated.
