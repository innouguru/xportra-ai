# Phase 10.8C — Dashboard: Your Shipments

> Implemented 2026-09-28 under `REQUIREMENTS.md`
> R-10.8 (R-10.8.1, R-10.8.7–R-10.8.9,
> R-10.8.13–R-10.8.15 dashboard concerns),
> `docs/decisions/ADR-0012-authenticated-shell-restructure.md`,
> and the 10.8A/10.8B foundation. Resumption
> workspace only: greeting, counts, attention,
> recent, empty/loading/error. No New Shipment
> form, no workspace, no verification, no
> archive, no backend/domain/API change. Task
> record:
> `tasks/active/phase-10-8c-dashboard.md`.

## 1. What was built

- `features/dashboard/dashboard.ts`: pure
  presentation mapping over the existing
  device-local registry (`lib/shipments`,
  most-recent-first) and existing process
  states (`lib/workflow`) — time-aware
  greeting, per-state plain-English status +
  attention + real-destination action,
  attention/recent partition (recent capped
  at 3, no cross-section duplicates),
  defensive `loadDashboard`, and `openShipment`
  (existing setRecord + navigate mechanism).
- `features/dashboard/DashboardPage.tsx`:
  replaces the 10.8B placeholder. Greeting
  eyebrow, "Your shipments" title, real
  counts summary, primary + New Shipment
  action (`/start`), attention section above
  recent, `ShipmentCard` composition with
  whole-card open + separate action button,
  honest empty/loading/error states.
- `primitives/shipment.tsx`: additive
  `onSelect` on `ShipmentCard` (session load
  before navigation; `href` kept as the
  destination hint).

## 2. Honest-data decisions

- Attention membership derives from stored
  state + supplied-evidence/round counts
  only (early/incomplete states, empty
  evidence requests, findings awaiting
  review). No technical state is user-facing
  (pinned by test across all nine states).
- Unavailable backend facts are omitted,
  never fabricated: no timestamps/last
  activity, no "N more details" counts, no
  scores or charts. Loading is a genuine
  async-shaped read; the error path is a
  real defensive catch with working retry.
- Destinations are existing routes only
  (`/start`, `/workspace` + deep links).

## 3. Verification

- Focused: mapping (19) + page (7) + extended
  primitive — dashboard files 26/26 passing;
  `AppRoutes` route tests unaffected.
- Full suite: 52 files / 313 tests passing —
  51 files / 307 in parallel plus the 6
  `AdditionalEvidencePage` tests serially.
  That file has a pre-existing timing flake
  under parallel workers (fails with none of
  this task's files loaded; passes alone and
  with `--maxWorkers=1`); unrelated to 10.8C,
  no test weakened.
- `npx tsc --noEmit` clean; `npm run build`
  succeeds.
- Footprint confirmed via `git status`:
  `primitives/shipment.*`,
  `features/dashboard/` only; no
  backend/domain/API/database change, no fake
  persistence or data, no 10.8D/E/F/G work.
