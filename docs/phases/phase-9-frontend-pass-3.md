# Phase 9 — Frontend Pass 3: Additional Evidence, Final Review/Finalize, Package, Report, History

**Status:** Complete and verified (2026-09-25)
**Phase:** Phase 9 — Frontend Implementation
**Type:** Frontend only — completes the terminal assessment workflow; no backend changes

> This record describes what was actually implemented and verified.

## Objective

Complete the remaining frontend workflow on top of the
Pass 2.5 visual baseline (reused, not redesigned):

1. Additional evidence loop
2. Explicit analysis re-run
3. Final review
4. Stored-path finalization (`POST /compliance/workflows/finalize`)
5. Assessment package presentation
6. Stored report view (`GET /compliance/reports/{report_id}`)
7. Workflow history projection (`GET /compliance/workflows/{workflow_id}/history`
   via the existing `POST /compliance/workflows/history` client)

The product now reads end to end as:

**Shipment → Requirements → Evidence → Analysis → Review → Assessment**,
with Additional Evidence looping back into Analysis, and
**Assessment / Package / Report / History** after finalization.

## What was built

### 1. Additional evidence (`src/features/evidence/AdditionalEvidencePage.tsx`)

- "Why additional evidence was requested" section renders
  only what the backend already recorded: workflow state,
  open-requirement count, supplied-evidence count, rounds,
  plus each open requirement's recorded finding detail
  (applicability, assessment, sufficiency, uncertainty,
  contradiction, recorded missing information) — never
  inferred or scored. Requesting is explicitly not a
  non-compliance finding.
- Request step wires `POST /compliance/workflows/request-additional-evidence`
  with space/comma-separated requirement IDs (prefill from
  already-open requirements offered as a link-button).
- Reference intake wires `POST /compliance-evidence` (or
  `/with-requirements` when requirement IDs are supplied):
  title + type + file reference/URI only. Copy states
  plainly that there is no file upload, no stored bytes,
  and the application never receives document content.
- Supply step wires `POST /compliance/workflows/supply-evidence`
  with evidence ID + optional requirement association.
  Copy states that supplying records a reference only: it
  does not establish compliance, change any assessment, or
  run analysis. Next step links to Analysis (explicit
  re-run) and back to findings review.
- All mutating controls disabled on terminal state, with a
  terminal notice linking to package/history.

### 2. Re-run analysis (`src/features/analysis/AnalysisPage.tsx`)

- Evidence supplied → `reanalysis_required` banner states a
  new round is required but re-running is the user's
  explicit decision, never automatic.
- Rounds table in recorded order (round, report link,
  findings count, traces count); no timestamps (none
  exist). First run vs re-run button label follows
  `record.rounds.length`.
- Single-flight guard; failure preserves usable state and
  surfaces backend semantics unchanged. On success the new
  report is held in memory and the user is routed to
  findings review. Terminal state disables runs and links
  to the stored package/report.

### 3. Final review (`src/features/assessment/FinalReviewPage.tsx`)

- Read-only review of what will become the package:
  workflow/tenant/case/shipment identity, state, rounds,
  latest report identity, received counters ( informational
  only), open-requirement snapshot, full findings via
  `FindingCard`, and a link to the stored report.
- Latest report resolves from the session report when it is
  the latest round, otherwise loads via
  `GET /compliance/reports/{report_id}` with retry.
- No recomputation, no reinterpretation: `unknown` stays
  undecided, missing evidence stays an information need, no
  verdict/score/percentage/ranking anywhere.
- Two-step finalization: "Review complete" opens a
  restrained confirmation panel ("Finalization is
  permanent… no reopen or versioning operation"), and only
  "Finalize assessment package" calls
  `POST /compliance/workflows/finalize`.
- Backend `not_ready`/`stale` 409 details render verbatim
  as a "Readiness blockers reported by the backend" section
  (reason codes + details); other errors use the
  established `userFacingErrorMessage` mapping.
- On 201: returned workflow persisted to session, package
  held in `AssessmentContext`, navigate to package.

### 4. Package (`src/features/assessment/PackagePage.tsx`)

- Terminal artifact view from `FinalPackageResponse`:
  finalized banner (text + structure, never color alone),
  assessment record identities, report counters as
  received, findings as finalized, open-requirement
  snapshot, missing/uncertainty section, carried decision
  summary rendered verbatim by key (or "none carried"),
  and read-only cross-links (stored report, history,
  review record).
- Prefers the in-memory package for the current workflow,
  otherwise re-reads via `POST /compliance/workflows/package`
  (also restores the artifact after refresh). No mutating
  control exists on this screen.

### 5. Stored report (`src/features/assessment/ReportPage.tsx`)

- `GET /compliance/reports/{report_id}` by route identity,
  presented in priority order: assessment context →
  findings → evidence/support → missing information →
  uncertainty/contradictions → authoritative summary
  reference (pointer to the package, never reconstructed).
- Counts verbatim; `unknown` never failure; missing
  information never non-compliance.

### 6. History (`src/features/assessment/HistoryPage.tsx`)

- `POST /compliance/workflows/history` projection rendered
  in the backend's grouped recorded order with sequence
  numbers, kind labels, verbatim details, and exact
  references. Explicit copy: projection, not event stream;
  no timestamps exist so none shown; no reasoning content
  copied. Readiness and final-package references shown when
  the backend provides them, with plain "not reported in
  this projection" fallbacks.

### Navigation / spine (`WorkspacePage.tsx`, `App.tsx`)

- Section nav keeps journey order with a quiet divider
  before the assessment tail (Final review · Assessment
  package · History). Stepper unchanged (Pass 2.5).
- Routes: `additional-evidence`, `analysis`, `review`,
  `final-review`, `package`, `report/:reportId`, `history`
  under `/workspace`. No dashboards, notifications,
  settings, or document-management screens.

### Session / state decisions

- Persisted: workflow record only (`sessionStorage`,
  identifiers + process state). Report/package reasoning
  content stays in memory; package/report re-read by
  identity after refresh via stored endpoints.
- No global mutable workflow store (`AssessmentContext` and
  `AnalysisContext` are narrow in-memory holders).
- No credentials, no raw evidence content stored.

### Visual / accessibility

- Pass 2.5 system reused: warm-neutral surfaces, charcoal
  ink, deep-teal accent, editorial type, compact badges,
  strong borders, focus rings; terminal state via text +
  structure + disabled controls, never color alone.
- Long UUIDs/URIs wrap (`overflow-wrap: anywhere`,
  `word-break: break-word` on `dd`, references, notices,
  banners, history) — resolves the Pass 2.5 overflow
  issue. Single-column responsive behavior preserved;
  keyboard/focus/`aria-current`/reduced-motion semantics
  retained. New styles: `.link-button`,
  `.reference-list--plain`, `.terminal-banner__title`,
  `.section-nav__divider`.

## Corrections made during verification (2026-09-25)

The Pass 3 tree was implemented but had never passed its
own checks. Verification fixes (frontend only):

- `src/app/AuthContext.tsx`: removed the
  throw-on-unconfigured from `useAuth()`. The throw crashed
  `AppShell` for signed-out users and made the
  `isConfigured` gating in `AppShell`/`NewShipmentPage`
  unreachable. Unconfigured sessions now render the
  "Sign in" path; authenticated behavior unchanged.
- `FinalReviewPage.test.tsx`: missing `within` import,
  duplicated `if` (syntax error), `renderPage(RECORD, null)`
  arity, sync assertions before async report load
  (now `findBy`), scoped multi-match title query
  (now `getAllByTitle`).
- `ReportPage.test.tsx`: `String.replaceAll` (lib target
  lacks es2021) → `split/join`; multi-match text/title
  queries → `getAllBy*`.
- `HistoryPage.test.tsx`: ambiguous `findByTitle` /
  `getByText` queries (identifiers and labels repeat
  between overview and entries) → `findAllByTitle` /
  `getAllByText`; dead `renderPage(enriched)` parameter use
  removed (the stub already serves the enriched payload).

## Verification

- `npx tsc --noEmit`: clean, 0 errors.
- `npx vitest run --testTimeout=20000`: **26 files /
  119 tests passing** (19 carried Pass 1–2.5 files plus 7
  Pass 3 files; 37 Pass-3 tests covering request reason /
  reference submission / supply / validation + API errors,
  explicit re-run + new round + failure preservation,
  review rendering + blockers + no-verdict guards,
  confirmation + terminal transition + disabled controls +
  terminal errors, package/report DTO rendering, grouped
  history with no invented timestamps).
  (Default 5s per-test timeout is too tight for this
  machine under full-suite parallel load; one interaction
  test passes in isolation and the suite is green with the
  raised timeout. No test logic was weakened.)
- `npm run build`: succeeds (`tsc --noEmit && vite build`,
  56 modules, dist emitted).
- `npm run dev`: serves 200 for `/`, `/session`,
  `/workspace/info`, `/workspace/final-review`,
  `/workspace/package`, `/workspace/history`. Rendering is
  covered by component tests; no backend live integration
  performed (no backend running here) and none claimed.

## Backend files changed

None. No Python, schema/migration, API contract, state
machine, deterministic rule, or Phase 6 reasoning change.

## Known limitations (intentional, unchanged)

- Reference-based evidence only: no file upload exists
  server-side and none is implied.
- No server-side workflow listing/resume; refresh restores
  the client-held record, package/report re-read by
  identity; otherwise handled honestly (empty states).
- No reopen/versioning after finalization (backend
  contract); the UI states this plainly.
- No notifications, dashboards, analytics, settings, or
  user management.
- Backend live integration not exercised in this pass.
