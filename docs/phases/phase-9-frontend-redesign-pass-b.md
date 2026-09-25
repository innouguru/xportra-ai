# Phase 9 — Frontend Redesign Pass B: Compliance Intelligence Detail Screens

**Status:** Complete and verified (2026-09-25)
**Phase:** Phase 9 — Frontend Implementation
**Type:** Composition redesign of operational detail screens; no backend changes

> Pass A made the workspace answer what shipment is in
> view and what needs attention. Pass B makes
> Requirements, Evidence, Analysis, and Assessment
> different views of the same compliance picture: why
> something matters, what evidence supports it, what is
> missing, and what to review next. Package, Report, and
> History stay untouched as assessment artifacts.

## Information hierarchy decisions

- **Requirements ledger** (`RequirementsPage`): the
  determination table is replaced by ruled ledger rows
  joining the just-run breakdown with recorded analysis
  findings by requirement identity (findings without a
  breakdown row are appended). Each row: open flag,
  requirement title, identifier, Applicability / Evidence
  (reference count or "None recorded") / Assessment
  ("Not yet analyzed" when absent), verbatim reason, and
  links to the finding and the evidence workspace. Counts
  render inline as receipt text, never scores.
- **Evidence workspace** (`EvidencePage`): Supplied (kept
  region + count heading) → Needed (open requirements as
  information needs, explicitly not non-compliance) →
  Attention (recorded request; registered-not-supplied
  with anchor link; honest empty states) → reference
  intake (unchanged contract/validation) → session
  registrations. Upload limitation stated up front.
- **Evidence gaps** (`GapsPage`): each gap is an
  INFORMATION NEEDED block — requirement, why it is
  needed (verbatim reason), gap badge (verbatim kind),
  current evidence state (supplied count, judged by the
  backend, not the screen), what the user can provide,
  and Register / Supply links. Missing ≠ non-compliant;
  no severity rankings.
- **Analysis** (`AnalysisPage`): intro now states what a
  run does and that deterministic assessment stays
  authoritative; rounds, coverage, and case form
  otherwise unchanged.
- **Findings** (`FindingsPage` + `FindingCard`): central
  intelligence view with group filters derived only from
  stored report data — All, Needs information, Uncertain,
  Contradictions (report rollup OR finding-level
  conflicting references), Unresolved (assessment
  unknown) — as `aria-pressed` chips with counts.
  Records link each finding to the evidence workspace;
  contradiction/uncertainty stay recorded-not-resolved
  with reviewer-inspection framing, never danger states.
- **Additional Evidence**: context strip up front
  (continuing from findings review → supply → explicit
  re-run) with distinct route links; all existing
  behavior preserved.
- **Final Review**: checkpoint composition — decision
  framing ("you have reviewed… ready to create the final
  package"), checkpoint list (findings + stored-report
  link, evidence supplied + workspace link, open needs,
  missing/uncertain/conflicting counts), numbered
  findings, unchanged two-step finalization and blocker
  rendering.

## Requirements presentation

Title-led rows (finding text, else identifier),
identifier code, three-state status grid, verbatim
reason, open-requirement flag, finding + evidence links.
Applicability/assessment badges keep exact backend
vocabulary and tones; `unknown` stays attention-toned,
never failure.

## Evidence model

Supplied (workflow record) vs Needed (open flags) vs
Attention (request state + unsupplied registrations) —
all from already-available state. Absence is never
equated with non-compliance; coverage judgment stays
server-side.

## Findings presentation

Filter chips + ruled records: counter, Requirement
kicker, serif title, status grid, hairline sections
(Explanation, Evidence with workspace link, Missing
information, Sources disclosure). Requirement title is
the anchor; no nested boxes added.

## Evidence ↔ findings relationship

Ledger rows link to findings and the evidence workspace;
finding records link back to the evidence workspace;
need blocks and attention items link both directions.
No new evidence-detail system built.

## Final-review composition

Checkpoint list first, findings second, explicit
finalization last — the user sees the decision being
asked before acting. Backend facts, blockers, and
terminal semantics unchanged.

## Backend limitations

- No joined requirement/evidence/assessment read exists
  server-side; the ledger joins two client-held sources
  by requirement identity and says so.
- No per-requirement evidence mapping exists; "Needed"
  uses open flags, "current state" uses supplied counts.
- Contradiction rollup and finding-level references can
  disagree in fixtures; the filter honors either.

## Verification

- `npx tsc --noEmit`: clean, 0 errors.
- `npx vitest run --testTimeout=20000`: **27 files /
  139 tests passing** (135 carried — two harness-only
  updates: `AnalysisProvider` wrapper for Requirements,
  `MemoryRouter` wrapper for `FindingCard` — plus 4 new:
  ledger row, evidence needed/attention, need block,
  findings filters).
- `npm run build`: succeeds (dist emitted, untracked).
- Dev server (single instance, source mode): 200 on all
  13 routes; Pass B markers verified in served modules
  and CSS. No backend live integration performed or
  claimed; pixel/device inspection unavailable here.

## Backend files changed

None.
