# Phase 9 — Frontend Redesign Pass A: Product Shell + Shipment Workspace

**Status:** Complete and verified (2026-09-25)
**Phase:** Phase 9 — Frontend Implementation
**Type:** Composition/UX redesign of shell + workspace only; no backend changes

> The frontend was polished but still read as a styled
> workflow/form application. Pass A recomposes it around
> one mental model: Xportra is a shipment intelligence
> workspace with a compliance assessment at its center.
> The shipment is the persistent object; the workflow is
> an implementation mechanism, not the visual metaphor.

## Product/UX decisions

- **Shipment-first hierarchy:** identity → assessment
  state → what is established → what needs attention →
  what can be done next → technical identifiers last.
- **No invented attributes:** no commodity, destination,
  dates, exporter, scores, or verdicts. Origin/destination
  lines are omitted entirely because neither the frontend
  nor the backend currently holds them.
- **Operational vs artifact modes:** the workspace uses
  flat typographic hierarchy and separators; the
  editorial/document character stays on Package/Report
  (untouched in this pass), as do all detail screens.
- **Areas, not a wizard:** the five-area status strip
  (Shipment, Requirements, Evidence, Analysis, Assessment)
  reuses the existing journey/step vocabulary and states —
  no new workflow states, no rigid linear claim.

## New information hierarchy (`WorkspaceOverview`, index of `/workspace`)

1. **Export shipment** — short human reference dominant
   (`Shipment XXXXXXXX…`, full UUID secondary),
   assessment line (in progress / in review / finalized)
   plus verbatim workflow state badge.
2. **Assessment status** — five linked areas, each with a
   recorded detail (reference bound, open count, supplied
   count, rounds recorded, findings/package state).
3. **Attention** — process facts only: evidence
   requested, re-analysis required, findings ready, open
   requirements, no evidence yet, no analysis yet, plus
   report-derived missing/uncertain/conflicting counts
   when a report is in memory. Each item links to its
   existing route; supplying evidence is framed as
   recording information, never compliance; missing
   information is an information need, never
   non-compliance. Terminal workflows show a single
   read-only notice linking to the package.
4. **Workspace** — linked area index with one-line
   descriptions (incl. latest stored report when rounds
   exist).
5. **Technical details** — workflow/tenant/case/shipment
   identifiers, state, round count in a disclosure.

## Navigation model (`AppShell`, `App.tsx`, `WorkspacePage`)

- **Primary (application):** New shipment, Workspace.
- **Current shipment** (only with an active record):
  Overview, Information, Requirements, Evidence, Analysis,
  Assessment (→ final review while open, → package once
  terminal). Active section keeps `aria-current`.
- `/workspace` index now renders the overview instead of
  redirecting to info. All 14 existing routes keep
  working. No shipment list is invented or implied.
- `WorkspacePage` keeps its compact identity bar,
  identifiers disclosure, and grouped section nav; the
  dominant six-column stepper was removed from the shell
  (the `Stepper` component itself is unchanged and still
  covered by its tests).

## What remains unchanged

- All detail screens (Requirements, Evidence, Gaps,
  Additional Evidence, Analysis, Findings, Final Review,
  Package, Report, History), API clients, DTOs, contexts,
  state machine, auth behavior, and the `Stepper`
  component.
- Warm-neutral/deep-teal language; no gradients, charts,
  scores, notifications, uploads, or speculative modules.

## Backend limitations encountered

- No commodity/destination/shipment attributes exist, so
  the identity block is reference + state only.
- Attention is limited to record + in-memory report
  facts (readiness/gaps recompute on their own screens).
- No multi-shipment browsing exists; navigation
  represents the current local workspace honestly.

## Verification

- `npx tsc --noEmit`: clean, 0 errors.
- `npx vitest run --testTimeout=20000`: **27 files /
  135 tests passing** (125 carried untouched, 10 new:
  overview identity/status/attention/terminal/empty +
  shell shipment-nav presence/absence/active/terminal).
- `npm run build`: succeeds (dist emitted, untracked).
- Dev server (single vite instance, source mode,
  `http://localhost:5173`): 200 on all 11 checked
  routes; served modules verified to contain the new
  shell nav, overview, strip, attention, and responsive
  blocks. No backend live integration performed or
  claimed. Pixel-level and real-device inspection remain
  unavailable in this environment (honest limitation).

## Backend files changed

None.
