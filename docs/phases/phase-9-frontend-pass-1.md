# Phase 9 — Frontend Pass 1: Foundation, Shell & Shipment Opening

**Status:** Complete and verified (2026-09-24)
**Phase:** Phase 9 — Frontend Implementation
**Type:** React + TypeScript SPA foundation; presentation only, no compliance logic

> This record describes what was actually implemented and verified.

## Objective

Implement Pass 1 of the UI/Product Architecture journey:
foundation, application shell, typed API client,
authentication/context plumbing, shipment workspace, New
Shipment, Shipment Information, and Requirements — against
the frozen backend API, without modifying it.

## Frontend architecture

- `frontend/` — Vite 8 + React 19 + TypeScript (strict,
  `noUnusedLocals`), react-router-dom v7. Free/open-source
  only: `react`, `react-dom`, `react-router-dom` runtime;
  vitest + Testing Library + jsdom for tests.
- `src/api/` — centralized client (`client.ts`: base URL,
  auth headers, error mapping) plus per-area typed
  endpoint modules (`workflows.ts`). No raw `fetch()`
  outside `client.ts` (no other fetch calls exist).
- `src/types/api.ts` — wire shapes mirroring
  `xportra/api/schemas.py` and application DTOs.
- `src/lib/workflow.ts` — pure presentation mapping
  (state labels, journey spine, step statuses,
  applicability tones). No verdicts, scores, or
  reinterpretation; unknown backend values pass through.
- `src/app/` — `AuthContext` (in-memory bearer/dev-tenant
  credentials), `WorkflowProvider` (client-held workflow
  record + sessionStorage resume, matching the server's
  stateless transfer contract).
- `src/components/` — `AppShell`, `Stepper`, `StatusBits`
  (Field/Identifier/StatusBadge/ErrorNotice/EmptyState/
  LoadingState/Collapsible).
- `src/features/{shipment,requirements}/` — Pass 1 pages.
- Visual system (`index.css`): light warm-neutral
  foundation (`#faf8f3`), charcoal typography, single
  deep-teal accent, thin borders, 6px radii, restrained
  shadows, serif display + system sans, responsive
  collapse, `prefers-reduced-motion` support.

## Routes/screens implemented (Pass 1)

- `/` — New Shipment (case/shipment UUIDs, client-side
  UUID validation + generate buttons, 201 → workspace).
- `/session` — bearer token (production) or dev-tenant
  ID (explicitly labeled local-development-only).
- `/workspace` — shipment header (workflow/case/
  shipment IDs, process state labeled as process, not
  verdict), journey stepper, section nav.
- `/workspace/info` — structured identity + information
  steps (provide-information, note-evidence-pending).
- `/workspace/requirements` — record-applicability
  action + deterministic breakdown form (requirement
  records + origin/destination/commodity facts) with a
  results table rendering backend outcomes verbatim;
  `unknown` shown as attention, never failure.

## API endpoints integrated (Pass 1)

- `POST /compliance/workflows/start` (201)
- `POST /compliance/workflows/provide-information`
- `POST /compliance/workflows/note-evidence-pending`
- `POST /compliance/workflows/record-applicability`
- `POST /compliance/assessments/applicability`
- Read-only status projection client-side from held records

## Important UX decisions

- Applicability outcomes render verbatim; `unknown` is
  "attention" tone with undecided language.
- Journey stepper marks process position; reaching a
  step never implies compliance.
- Statuses pair tone with text/shape (badges include a
  dot + text), never color alone.
- Backend error codes map to user messages preserving
  semantics (terminal/stale/permission/tenant cases
  covered; no compliance meaning invented).
- Evidence intake intentionally deferred to Pass 2
  (reference/URI form, no file uploader — none exists
  server-side either).
- Analysis/findings/finalize intentionally deferred to
  Passes 2–3.

## Tests run and exact results

- `npx tsc --noEmit`: clean, 0 errors.
- `npx vitest run`: **7 files, 35 tests, all passing**:
  `client.test.ts` (9: headers, base URL, error
  envelope/network mapping, per-code messages,
  no-invented-meaning), `workflows.test.ts` (4: routes,
  methods, bodies), `workflow.test.ts` (lib: labels,
  spine, terminal, action-required, tones),
  `AppShell.test.tsx` (3), `NewShipmentPage.test.tsx`
  (3: validation, create+navigate, denial message),
  `WorkspacePage.test.tsx` (3: empty state, header,
  stepper semantics), `RequirementsPage.test.tsx` (2:
  record action, verbatim outcomes).
- `npm run build` (vite production build): succeeds
  (tsc + bundle, ~282 KB JS / ~88 KB gzip).
- Backend suite: not re-run (zero backend files
  changed — verified via `git status`; frontend is
  additive under `frontend/`).

## Backend files changed, if any

None. Backend untouched; `git status` shows only the
new `frontend/` tree plus docs/state updates below.

## Blockers or API gaps

None for Pass 1 scope. Known deferred gaps (unchanged
from the UI architecture spec): no file-upload
endpoint, no workflow listing/resume endpoint, no
standalone readiness read, no role-introspection
endpoint. None block Passes 2–3 as specified.

## Documentation updated

- This phase document.
- `tasks/completed/phase-9-frontend-pass-1.md`.
- `CURRENT_STATE.md` (frontend track entry).
- `ACTIVE_TASK.md` (this task, complete).

## What remains for the next frontend pass

Pass 2: Evidence (reference intake form), Evidence Gaps
(case-readiness display), Analysis (run action +
findings report rendering), Findings Review. Then
Pass 3: Additional Evidence, Final Review/Finalize,
Package/Report/History. Test + build gates repeat per
pass. No backend changes anticipated.
