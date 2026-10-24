# Phase 2 — Contextual Document Workflow UX

## Objective

Make the existing shipment document workflow easier to understand by
distinguishing file processing, evidence supply, and recorded assessment while
preserving existing APIs and behavior.

## Acceptance criteria

- Shipment-scoped document records show the available document identity,
  processing state, evidence state, and supported next action separately.
- A newly supplied document is not presented as assessed by an earlier
  analysis result.
- Failed processing has an explicit safe retry path only through the existing
  idempotent upload operation.
- Analysis remains an explicit action; upload and supply never trigger it.
- Missing requirement records are not replaced with a fabricated checklist.
- Existing tenant-safe upload, supply, authorized download, and finalized
  workflow behavior remains intact.

## Verification plan

- Focused DocumentDrawer, EvidencePage, and shipment workspace tests.
- Frontend full test suite, `npm.cmd run lint`, and `npm.cmd run build`.
- Review the complete diff and preserve existing local changes.

## Guardrails

- No backend/API/schema changes, migration, or Phase 3 findings redesign.
- No new regulatory requirements or claims.
- No commit or push.

## Completion record

- Focused command: `npm.cmd run test -- src/features/workspace/DocumentDrawer.test.tsx src/features/workspace/ShipmentWorkspacePage.test.tsx src/features/workspace/workspace.test.ts src/features/evidence/EvidencePage.test.tsx src/features/evidence/DocumentsPage.test.tsx src/features/evidence/AdditionalEvidencePage.test.tsx src/features/evidence/GapsPage.test.tsx src/lib/evidence.test.ts` — 72 passed across 8 files.
- Full suite: `npm.cmd run test -- --maxWorkers=2` — 529 passed across 72 files.
- `npm.cmd run lint` — passed (TypeScript no-emit check).
- `npm.cmd run build` — passed; Vite emitted the existing >500 kB chunk advisory.
- The default-worker `npm.cmd run test` run had two timing-sensitive failures in pre-existing `AdditionalEvidencePage` tests (one timeout and one interrupted input assertion); both passed with two workers. No assertions in that file were changed.
- No backend tests were needed because no backend code changed. No live production verification was performed.
- Existing local Phase 1 and unrelated working-tree changes, including `NewShipmentPage.tsx` and its test, were preserved. No commit or push was made.
