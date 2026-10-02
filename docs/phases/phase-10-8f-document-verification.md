# Phase 10.8F — Document Verification

> Implemented 2026-09-28 under `REQUIREMENTS.md`
> R-10.8 and
> `docs/decisions/ADR-0012-authenticated-shell-restructure.md`,
> composed from the 10.8A–10.8E foundation.
> Real verification only: upload, requirement
> linking, finding-based verdicts, authorized
> preview. No invented endpoints, extraction,
> scores, or simulated analysis. Task record:
> `tasks/active/phase-10-8f-document-verification.md`.

## 1. What was built

- `features/verification/verification.ts`:
  pure verdict mapping (recorded assessment →
  Satisfied / Not satisfied / Unknown),
  latest-finding selection, missing-line
  filtering, honest PDF/image preview kinds.
- `features/workspace/DocumentDrawer.tsx`
  (rewritten seam, same dialog contract):
  requirement context + explanation, real
  upload (backend-owned type/size rules,
  honest lifecycle notices), per-document
  Verify (supply-if-needed via
  `supply-evidence`, then the recorded
  finding or an explicit Unknown +
  analysis link), missing-information and
  explanation rendering, on-demand preview
  (inline PDF/image, fallback otherwise)
  and new-tab open via short-lived grants,
  human errors with retry, terminal
  read-only mode.
- `features/workspace/workspace.ts`:
  `requirementId` threaded to drawer +
  page wiring; no mapping changes.

## 2. Honest-capability decisions

- No verify/extract/OCR/classify endpoint
  exists — verification = link + recorded
  finding. Analysis runs stay explicit on
  their route (owner-only, caller-built
  cases); the drawer links there instead of
  synthesizing inputs.
- Requirement sync = `setRecord` on the
  `supply-evidence` response (same as the
  evidence workspace); finding refresh
  needs an analysis run (documented).
- Unknown-shape `sources` not rendered;
  registry staleness mirrors existing
  behavior; no scores, confidences,
  chain-of-thought, or progress theatrics.

## 3. Verification

- Focused: verdict lib (7) + drawer (10) +
  updated page seam — all passing.
- Full suite: 56 files / 349 of 351 passing
  in parallel; the 2 failures are the known
  pre-existing parallel-timing flake in
  unrelated `AdditionalEvidencePage` tests
  (proven again: no 10.8F file loaded in
  failing scope; 6/6 serially). No test
  weakened.
- `npx tsc --noEmit` clean; `npm run build`
  succeeds.
- Footprint confirmed via `git status`:
  `features/verification/`,
  `features/workspace/` only; no
  backend/domain/API/database change, no
  fake persistence or data, no 10.8G work.
