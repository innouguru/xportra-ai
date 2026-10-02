# Phase 10.8D — New Shipment (Complete, 2026-09-28)

Focused intake task under `REQUIREMENTS.md`
R-10.8 and `docs/decisions/ADR-0012-authenticated-shell-restructure.md`,
composed from the 10.8A/10.8B/10.8C foundation.
No backend, domain, compliance, API-contract,
tenant-isolation, or deterministic-semantics
change — and no workspace, verification,
archive, dashboard redesign, or fake
persistence. Implementation record:
`docs/phases/phase-10-8d-new-shipment.md`.

## Acceptance criteria

- [x] `/start` is the real New Shipment
      experience (product + destination first,
      details second, no port, no giant form).
- [x] Free-text product/destination with
      device-honest suggestions; no second
      product model, no classification claims.
- [x] Adaptive scope limited to what the
      architecture supports; nothing invented.
- [x] Explicit "I don’t know" for optional
      fields; unknown never fabricated.
- [x] Human-readable field validation with
      focus; no technical messages.
- [x] Creation through `startWorkflow` +
      registry (identical contract); incomplete
      submitted work resumable from dashboard.
- [x] No draft autosave/Saved indicator —
      reported as an architectural limitation
      (no backing boundary; nothing invented).
- [x] Natural completion into the existing
      workspace; no fake loading.
- [x] Responsive, accessible, shell-integrated;
      no 10.8E/F/G work.
- [x] Full suite + tsc + build pass; next task
      clearly identified as Phase 10.8E.

## Artifacts (intake only)

- `frontend/src/features/shipment/NewShipmentPage.tsx`
  (rewritten), `NewShipmentPage.test.tsx`
  (rewritten, 10 tests)
- `frontend/src/primitives/primitives.css`
  (`xb-form` family), `primitives.test.ts`
  (extended)
- `docs/phases/phase-10-8d-new-shipment.md`,
  `CURRENT_STATE.md`, `ACTIVE_TASK.md`,
  `ROADMAP.md`

## Verification

- Focused: 16/16 passing.
- Full suite: 52 files / 318 tests, 0 failures
  (baseline 52/313; +5 net; none weakened).
- `npx tsc --noEmit` clean; `npm run build`
  succeeds.
- Footprint confirmed via `git status`; no
  backend/domain/API/database change.
- No commit/push performed.
