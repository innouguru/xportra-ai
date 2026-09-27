# Phase 10.5 — Evidence Upload UX & Workflow Integration (Complete, 2026-09-27)

Makes the Phase 10.4 upload backend user-facing.
Implementation record:
`docs/phases/phase-10-5-evidence-upload-ux.md`.

## Acceptance criteria

- [x] The Evidence page has a real Upload Evidence action.
- [x] The frontend calls the real Phase 10.4 upload endpoint.
- [x] Supported file information is clearly communicated.
- [x] Upload/processing/ready/failed states are represented honestly.
- [x] Download uses the authorized backend endpoint.
- [x] Evidence integrates with the existing evidence/gap workflow.
- [x] Finalized workflows cannot upload.
- [x] New evidence does not falsely imply compliance.
- [x] Re-analysis remains an explicit workflow action.
- [x] No chat functionality was added.
- [x] No deletion/retention functionality was added.
- [x] Responsive/accessibility requirements are verified.
- [x] Focused tests pass.
- [x] TypeScript passes.
- [x] Production build passes.
- [x] Backend regression remains clean (untouched: 1902 + 44).
- [x] Documentation is complete.

## Artifacts (modified, frontend only)

- `frontend/src/types/api.ts` (upload/download contracts +
  optional processing fields on `EvidenceRecord`)
- `frontend/src/api/evidence.ts` (`uploadEvidenceFile`,
  `fetchEvidenceDownload`, `fileToBase64`)
- `frontend/src/api/client.ts` (4 new user-facing error copies)
- `frontend/src/lib/evidence.ts` (upload constants, size
  format, advisory pre-check, processing labels/tones/notes)
- `frontend/src/features/evidence/EvidencePage.tsx`
  (upload workspace rewrite)
- `frontend/src/features/evidence/GapsPage.tsx` (upload path)
- `frontend/src/features/evidence/AdditionalEvidencePage.tsx`
  (stale copy corrected, flow intact)
- `frontend/src/index.css` (file-input rule only)
- Tests: `EvidencePage.test.tsx` rewritten (6→16),
  `api/evidence.test.ts` +4, `lib/evidence.test.ts` +3,
  `GapsPage`/`AdditionalEvidencePage` copy assertions updated
- Docs: phase doc, this record, `CURRENT_STATE.md`, `ACTIVE_TASK.md`

## Verification

- Frontend: 27 files / 157 tests passing (+17, none weakened).
- `npx tsc --noEmit` clean; `npm run build` succeeds.
- Served 200 on `/workspace/evidence` (dev source-mode);
  production bundle serves 200 with all new markers/routes/CSS.
  No browser engine: no pixel-perfect claim.
- Backend (no files changed): 1902 passed + 44 skipped.
- No packages installed. No commit/push performed.
