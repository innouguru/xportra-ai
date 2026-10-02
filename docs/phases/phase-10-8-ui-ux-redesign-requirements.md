# Phase 10.8 — UI/UX Redesign Requirements & Architecture

> Approved 2026-09-28 as `REQUIREMENTS.md` R-10.8 with
> binding direction in
> `docs/decisions/ADR-0012-authenticated-shell-restructure.md`.
> Documentation / requirements / architecture task
> only — no implementation. No React component,
> stylesheet, route, test, backend, domain,
> compliance, API-contract, tenant-isolation, or
> deterministic-semantics change. Task record:
> `tasks/active/phase-10-8-ui-ux-redesign-requirements.md`.

## 1. Why this task exists

The Phase 10.7A/10.7B frontend is technically valid,
but the product owner has approved a new product
experience direction (calm compliance workspace,
shipment-first, resumption- and attention-centered)
and the prior R2 shell attempt was correctly
blocked for lack of approved requirements. This
task closes that governance gap so later
implementation subtasks (10.8A–10.8J) are traceable
under `AGENTS.md`.

## 2. What was established

- `REQUIREMENTS.md` R-10.8 (R-10.8.1–R-10.8.16):
  authenticated navigation, public/authenticated
  separation, sidebar shell, account menu,
  notifications entry point, theme behavior,
  dashboard purpose, shipment-first navigation,
  progressive verification, completed-shipment
  immutability, historical report behavior,
  public landing page, responsive behavior,
  accessibility, visual language, and out-of-scope
  boundaries.
- `docs/decisions/ADR-0012-authenticated-shell-restructure.md`:
  decision to move from the Phase 10.7
  topbar-oriented shell to the shipment-first
  expandable sidebar, with alternatives,
  consequences, migration notes, and explicit
  historical context.
- Approved implementation sequence (not started):
  10.8A Redesign foundation, 10.8B Application
  shell, 10.8C Dashboard, 10.8D New Shipment,
  10.8E Shipment Workspace, 10.8F Document
  Verification, 10.8G View Shipments + Historical
  Report, 10.8H Public Landing Page, 10.8I
  Settings / Notifications / Responsive, 10.8J
  Accessibility / Visual QA.

## 3. Explicit supersessions (history preserved)

Phase 10.7A/10.7B records are unchanged. The
following are superseded as direction for future
implementation, recorded in R-10.8 and ADR-0012
rather than rewritten:

- R-10.7A.2 (Overview/Shipments/Documents/
  Requirements/Assessment primary nav) →
  superseded by R-10.8.1 for future
  implementation; existing nav stays until
  10.8B.
- R-10.7B.3 (topbar-oriented shell model) →
  superseded by R-10.8.3 / ADR-0012; existing
  shell stays until 10.8B.
- R-10.7B.5 theme-switcher exclusion →
  superseded by R-10.8.6 (dual-theme support,
  dark default, palette retained).
- Notifications exclusions (R-10.1.9, R-10.4.8,
  R-10.5.4, R-10.6.6) → narrowed to the subtle
  entry-point scope only (R-10.8.5); a full
  notification center remains out of scope.

## 4. Verification

- Docs-only task: no application test was added,
  modified, or weakened.
- Frontend suite re-run unchanged to confirm the
  running UI is untouched (see task record).
- `git status` inspected to confirm no source,
  style, route, or test file changed.
