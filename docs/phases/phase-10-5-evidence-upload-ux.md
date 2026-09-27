# Phase 10.5 — Evidence Upload UX & Workflow Integration

> Implemented 2026-09-27. Makes the Phase 10.4 upload
> backend a real user-facing capability. Task record:
> `tasks/completed/phase-10-5-evidence-upload-ux.md`.
> No backend file was changed; no chat, delete,
> retention, reopening, queue, notification, RAG,
> compliance-rule, or analysis-logic work is included.

## 1. Principle

The frontend is a client of the existing backend. No
tenant authorization, validation, compliance logic,
processing decision, assessment, or RAG behavior was
reproduced in the UI. The backend remains authoritative;
the UI presents its lifecycle honestly:

```text
Selected → Uploading → Processing → Ready | Failed
```

Ready never implies satisfied; failed never reads as
usable. The words "verified", "approved", and
"compliant" appear nowhere for uploads.

## 2. Evidence workspace (`EvidencePage`)

- **Supplied evidence**: supplied IDs resolve through
  the existing `GET /compliance-evidence/{id}` into
  document name, type, evidence status, and processing
  state with a Download action; IDs that fail to load
  fall back to identifier rendering (page never breaks).
- **Needed**: open requirements as "Information needed"
  (never non-compliance), with links to gaps and
  additional evidence.
- **Upload evidence**: native file picker
  (`accept=".pdf,.docx,.jpg,.jpeg,.png"`), supported-format
  and 10 MB-maximum guidance, selected name + size,
  advisory client pre-check (backend revalidates),
  Upload action, uploading/ready/failed states with
  honest notes, and retry-by-reselection. No fake
  drag-and-drop was added.
- **Uploaded this session**: record cards with
  processing badge + note, evidence status,
  backend-returned requirement associations (or the
  honest "Requirement association will be determined
  from the compliance context."), duplicate notice,
  supply-to-workflow (disabled for failed items with
  the reason stated), and download.
- **Attention**: additional-evidence requests,
  unsupplied uploads, and — when analysis rounds exist
  and new uploads arrived — "New evidence is available
  — analysis may need to be rerun" with a "Run analysis
  again" link to the existing analysis flow. Nothing
  runs automatically; assessment change is never claimed
  before a real re-run.
- **Finalized**: upload control absent; "Upload is
  unavailable — this assessment has been finalized and
  can no longer be changed." No reopen action exists.
- No raw UUID-heavy layouts for known records; IDs
  render only as truncated identifiers or fallbacks.

## 3. Gaps + Additional Evidence

- `GapsPage`: each information need now paths to
  "Upload evidence" (`../evidence`) then supply, then
  explicit re-run. Screen remains the information-need
  view; the evidence page stays authoritative.
- `AdditionalEvidencePage`: reference flow unchanged;
  the two false "no file upload" statements now point
  at "Upload evidence on the Evidence page".

## 4. API integration (exact backend contract)

- `POST /compliance-evidence/uploads` via
  `uploadEvidenceFile` (base64 JSON transport exactly
  as `EvidenceUploadRequest`; workflow record passed
  for server-side terminal checks; no tenant IDs, keys,
  or storage internals; no `any`).
- `GET /compliance-evidence/{id}/download` via
  `fetchEvidenceDownload`; the signed URL is opened
  immediately (`window.open … noopener`) and never
  stored or displayed.
- New user-facing copies for `payload_too_large`,
  `malformed_upload_content`,
  `evidence_upload_not_configured`, and
  `resource_not_found`; all other errors keep existing
  safe mappings. Backend internals never surface.

## 5. Loading/error states

Supplied-loading, uploading, per-item preparing/
supplying, upload/association/download failures,
unauthorized, finalized, and network failures are all
handled with notices — no permanent spinners, no
swallowed failures. Failed uploads keep the selection
for retry.

## 6. Accessibility / responsive

Native labeled file input (never hidden), described-by
format hint + errors, `role="alert"` errors,
`aria-live` status notes, text+dot badges (never color
alone), inherited focus outlines and control-height
touch targets, existing reduced-motion support
(spinner only; no new animation). Layout reuses fluid
grids (`form-grid`, `field-grid`, `attention-item`
column at ≤860px); static audit found no fixed widths,
no horizontal-scroll hazards on upload elements, and
wrapping identifiers/filenames. Verified at source +
production bundle; no browser engine was available, so
no pixel-perfect claim is made.

## 7. Verification

- Frontend: **27 files / 157 tests passing** (was 26/140
  scope at Pass C baseline lineage; +17 focused tests,
  no existing test weakened — two behavior-replaced
  assertions were rewritten to the new product behavior
  at equal strength).
- `npx tsc --noEmit` clean; `npm run build` succeeds.
- Served/static: dev source-mode returned 200 on
  `/workspace/evidence`; production bundle serves 200
  and contains all new markers, routes, and CSS.
- Backend (untouched): **1902 passed + 44 skipped**,
  0 failures — baseline holds exactly. Live services
  not executed (no environment), as before.

## 8. Limitations

- Session upload list is in-memory (reload clears it;
  supplied IDs persist via the workflow record and
  re-resolve through the backend).
- No upload progress percentage (fetch has no upload
  progress events; honest spinner instead).
- Supplied IDs unknown to the session render as bare
  identifiers until their GET succeeds.
- Chat untouched; future Ask Xportra hooks were not
  pre-built (no dead code).

## 9. Explicitly NOT implemented

Conversational upload, chat UI, evidence deletion,
retention policy, workflow reopening, background
queue, notifications, new RAG behavior, new compliance
rules, new analysis logic, provider migration,
deployment infrastructure, unrelated redesign. No
packages installed. No commit/push performed.
