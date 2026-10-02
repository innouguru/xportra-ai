# Phase 10.8F — Document Verification (Complete, 2026-09-28)

Real-verification task under `REQUIREMENTS.md`
R-10.8 and `docs/decisions/ADR-0012-authenticated-shell-restructure.md`,
composed from the 10.8A–10.8E foundation. No
backend, domain, compliance, API-contract,
tenant-isolation, or deterministic-semantics
change — and no invented endpoints, scores,
or simulated analysis. Implementation record:
`docs/phases/phase-10-8f-document-verification.md`.

## Acceptance criteria

- [x] Drawer is the requirement-scoped
      verification surface (dialog semantics
      preserved).
- [x] Real upload with backend-owned
      constraints; honest lifecycle; retry.
- [x] Verify links via `supply-evidence`
      (authoritative refresh), then the
      recorded finding or explicit Unknown.
- [x] Satisfied / Not satisfied / Unknown
      only; real reasons; no confidences.
- [x] Evidence + missing info rendered when
      returned; nothing fabricated.
- [x] Regulatory explanation only from real
      data; no invented citations.
- [x] Requirement sync via the authoritative
      response; limitations documented.
- [x] Per-document scoping; honest preview
      (PDF/image inline, fallback otherwise).
- [x] Accessible, responsive, calm; no 10.8G
      work; no backend changes.
- [x] Full suite + tsc + build pass (known
      pre-existing flake noted); next task
      clearly identified as Phase 10.8G.

## Artifacts (verification only)

- `frontend/src/features/verification/verification.ts`
  (new) + test
- `frontend/src/features/workspace/DocumentDrawer.tsx`
  (rewritten) + test
- `frontend/src/features/workspace/workspace.ts`
  (`requirementId`), `ShipmentWorkspacePage.tsx`
  (drawer wiring), page test (updated seam)
- `docs/phases/phase-10-8f-document-verification.md`,
  `CURRENT_STATE.md`, `ACTIVE_TASK.md`,
  `ROADMAP.md`

## Verification

- Focused: 7 + 10 + updated seam, passing.
- Full suite: 56 files / 349 of 351 in
  parallel (known pre-existing flake in
  unrelated evidence tests; 6/6 serially;
  none weakened).
- `npx tsc --noEmit` clean; `npm run build`
  succeeds.
- Footprint confirmed via `git status`; no
  backend/domain/API/database change.
- No commit/push performed.
