# Phase 10.8 — UI/UX Redesign Requirements & Architecture (Complete, 2026-09-28)

Documentation / requirements / architecture task
under `REQUIREMENTS.md` R-10.8 (added below). No
backend, domain, compliance, API-contract,
tenant-isolation, or deterministic-semantics
change — and no frontend implementation either.
Implementation record:
`docs/phases/phase-10-8-ui-ux-redesign-requirements.md`;
binding direction:
`docs/decisions/ADR-0012-authenticated-shell-restructure.md`.

## Acceptance criteria

- [x] Redesign formally represented in canonical
      requirements (R-10.8.1–R-10.8.16).
- [x] New shell direction covered by an ADR
      (ADR-0012, with alternatives, consequences,
      migration notes).
- [x] Conflicting Phase 10.7 decisions explicitly
      superseded (R-10.7A.2, R-10.7B.3, R-10.7B.5
      theme-switcher exclusion; notifications
      exclusions narrowed to entry-point scope) —
      historical records unchanged, supersessions
      recorded in R-10.8 and ADR-0012.
- [x] ACTIVE_TASK.md, CURRENT_STATE.md, ROADMAP.md,
      and the ADR index updated and internally
      consistent.
- [x] No source/UI implementation performed; no
      existing navigation removed.
- [x] Existing application tests untouched and
      passing.
- [x] Next implementation task clearly identified
      as Phase 10.8A — Redesign Foundation.

## Approved implementation sequence (not started)

```text
10.8A — Redesign foundation
10.8B — Application shell
10.8C — Dashboard
10.8D — New Shipment
10.8E — Shipment Workspace
10.8F — Document Verification
10.8G — View Shipments + Historical Report
10.8H — Public Landing Page
10.8I — Settings / Notifications / Responsive
10.8J — Accessibility / Visual QA
```

## Artifacts (docs/harness only)

- `REQUIREMENTS.md` (R-10.8; supersession notes
  under R-10.7B.5 and the future-phases paragraph)
- `docs/decisions/ADR-0012-authenticated-shell-restructure.md`
  (new) + `docs/decisions/README.md` (index)
- `docs/phases/phase-10-8-ui-ux-redesign-requirements.md`
  (new)
- `CURRENT_STATE.md`, `ACTIVE_TASK.md`,
  `ROADMAP.md`

## Verification

- Frontend suite re-run: files/tests unchanged,
  0 failures (see completion report).
- `npx tsc --noEmit` clean (no source changed).
- `git status` confirms no application source,
  style, route, or test file changed.
- No commit/push performed.
