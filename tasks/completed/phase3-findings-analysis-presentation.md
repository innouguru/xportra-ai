# Phase 3 — Findings and Analysis Presentation

**Status: Complete (2026-10-20).**

## Objective

Make the shipment's recorded analysis and findings easier to understand while
preserving the existing backend record and assessment meaning.

## Acceptance criteria

- Findings lead with a concise explanation of the analysis record and its
  limits; no UI language implies regulatory approval or clearance.
- Finding states use plain-language presentation while evidence, missing
  information, conflicts, uncertainty, and provenance remain available.
- Report summary counts do not double-count a requirement flagged in more than
  one report rollup.
- Findings provide one prominent next action based on the existing workflow
  state and report data; other supported actions remain available secondarily.
- Analysis shows a human-readable workflow position and preserves explicit,
  user-triggered analysis, round history, failure handling, and operator case
  building.
- No backend, API, schema, migration, or assessment semantic changes.

## Verification plan

- Focused findings, presentation-helper, analysis, and stored-report tests.
- Full frontend test suite, `npm.cmd run lint`, and `npm.cmd run build`.
- Preserve and review pre-existing Phase 1/2 and unrelated working-tree changes.

## Guardrails

- No regulatory rules, findings, sources, or results invented.
- Do not remove supported review, evidence, request, report, or analysis routes.
- No commit or push.

## Completion record

- Findings use plain-language states, keep supported evidence and source
  details, avoid dumping unknown provenance fields, and keep record
  identifiers out of historical reports.
- Empty findings are explicitly described as not proving compliance or
  export clearance. A missing/unreadable stored report is not presented as an
  empty findings list.
- The primary findings action now accounts for workflow state and missing,
  uncertain, or conflicting report data; other actions remain available.
- Focused Phase 3 tests passed (48/48). The isolated assessment-page suite
  passed (4/4) after updating its stale visible-heading expectations to
  "Information coverage"; assertions still verify the explicit "Run
  analysis" action.
- Full frontend suite: `npm.cmd run test -- --maxWorkers=2` — 539 passed
  across 72 files.
- `npm.cmd run lint` — passed (TypeScript no-emit check).
- `npm.cmd run build` — passed; Vite emitted the existing >500 kB chunk
  advisory.
- `git diff --check` — passed.
- The former failures were stale test expectations: the analysis screen
  intentionally renamed its visible heading while retaining the section
  accessible name. No application behavior change was needed for this fix.
- No backend tests were needed because backend code was not changed. No live
  production verification, commit, or push was performed. Existing local
  changes and artifacts were preserved.
