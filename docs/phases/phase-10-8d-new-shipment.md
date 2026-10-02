# Phase 10.8D — New Shipment

> Implemented 2026-09-28 under `REQUIREMENTS.md`
> R-10.8 and
> `docs/decisions/ADR-0012-authenticated-shell-restructure.md`,
> composed from the 10.8A/10.8B/10.8C foundation.
> Shipment intake only: progressive product →
> destination → details form in the new shell,
> explicit unknown controls, field-level
> validation, existing creation boundary. No
> workspace, verification, archive, dashboard
> redesign, or backend/domain/API change. Task
> record:
> `tasks/active/phase-10-8d-new-shipment.md`.

## 1. What was built

- `features/shipment/NewShipmentPage.tsx`
  (rewritten): "Start a new shipment" with the
  approved supporting copy; primary Product +
  "Where is it going?" (country, no port —
  none exists in the architecture) section;
  secondary Shipment details (origin,
  quantity, unit, date); past-device
  datalist suggestions (free text stays
  free, no classification claims);
  per-optional-field "I don’t know"
  checkboxes (disable + clear; stored as ""
  in the unchanged string-only profile,
  never displayed as known); field-level
  human validation with focus management;
  BackButton + crumbs; real pending,
  403, and error states; submit reuses
  `startWorkflow` + registry + `/workspace`
  navigation byte-for-byte.
- `primitives/primitives.css`: additive
  token-only `xb-form` family (form, section,
  field, input, hint, error, check, actions)
  + focus-visible coverage; contract test
  extended (strengthened, not weakened).

## 2. Honest-architecture decisions

- No product catalog, country list, port, or
  per-shipment questionnaire exists in any
  boundary — all omitted, never invented.
  Origin stays required (existing frontend
  validation, compliance context); quantity/
  unit/date stay optional with explicit
  unknown (empty storage is UI-explicit
  unknown, never a known value downstream).
- Draft autosave NOT implemented: no draft
  persistence boundary exists and the 10.8D
  guardrail forbids inventing
  localStorage/session/fake persistence. No
  Saved indicator is shown (nothing to show).
  Only submitted shipments persist (workflow
  record + registry), resumable from the
  dashboard — criteria 10–12 hold through
  creation, not drafts.
- Completion is the genuine async creation
  ("Creating your shipment…") straight into
  the existing workspace; no fake pause.

## 3. Verification

- Focused: 10 page tests + extended CSS
  contract — 16/16 passing (opening,
  follow-ups, validation + focus, unknown,
  identical backend contract, 403, failure
  preservation, real progress, back nav,
  honest suggestions, no port).
- Full suite: 52 files / 318 tests passing
  (baseline 52/313; +5 net), 0 failures —
  including the formerly flaky evidence
  file this run.
- `npx tsc --noEmit` clean; `npm run build`
  succeeds.
- Footprint confirmed via `git status`:
  `NewShipmentPage.*`, `primitives.css`,
  `primitives.test.ts` only; no
  backend/domain/API/database change, no fake
  persistence or data, no 10.8E/F/G work.
