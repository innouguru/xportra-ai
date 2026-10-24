# Phase 1 — Shipment Workspace UX Simplification

## Objective

Implement only Phase 1 of the approved Shipment Workspace UX Proposal. Keep
the existing shipment-first navigation, use the case-specific shipment page as
the canonical overview, clarify next actions and status language, and explain
the local-only hide operation. Preserve compatible legacy workflow screens.

## Acceptance criteria

- Active shipment entry points resolve to `/shipments/:caseId`; unqualified
  `/workspace` redirects when a session-restored case ID is available.
- Nested `/workspace/*` routes remain protected and functional as compatibility
  screens; no generic redirect loses their intent.
- Dashboard empty state has one New shipment action.
- Overview removes repeated findings/attention rows and duplicate status
  presentation while retaining one state-based primary action.
- Shipment statuses are presented as Not started, In progress, Needs your
  attention, or Completed only when supported by the workflow state.
- Completed package messaging explicitly says it is not government approval or
  export clearance; completed work stays read-only.
- Shipment hide control truthfully describes device-local hiding and does not
  delete backend data.
- Existing shipment form, evidence, auth, tenant boundaries, and backend
  contracts remain unchanged.

## Verification plan

- Focused dashboard, route, workspace, shipment-list, status, and shipment-form
  tests.
- Full frontend test suite, `npm.cmd run lint`, and `npm.cmd run build`.
- Review Git diff and confirm unrelated existing modifications remain intact.

## Guardrails

- No backend/API/database changes or migrations.
- No document/analysis phase work.
- No commit or push for this user-assigned task.

## Completion record

- Focused regressions: 51 passed across dashboard, shipment list, historical
  report, route compatibility, and workspace overview tests.
- Full frontend suite: 524 passed across 72 files.
- `npm.cmd run lint`: passed.
- `npm.cmd run build`: passed; Vite emitted the existing advisory that the
  minified JavaScript chunk exceeds 500 kB.
- `git diff --check`: passed; Git printed expected LF-to-CRLF normalization
  warnings for edited files.
- No backend tests were needed because backend code was not changed.
- No live Render/Supabase or browser verification, commit, or push was performed.
- Pre-existing unrelated working-tree files were preserved.
