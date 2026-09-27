# Phase 10.4 — Evidence Upload Implementation

> Implemented 2026-09-27 under `REQUIREMENTS.md` R-10.4
> (resolved product decisions U1–U7). Implements the
> Phase 10.3 boundary
> (`docs/phases/phase-10-3-evidence-upload-ingestion-boundary.md`)
> under ADR-0011
> (`docs/decisions/ADR-0011-evidence-upload-ingestion-boundary.md`).
> Task record:
> `tasks/completed/phase-10-4-evidence-upload-implementation.md`.
> No Phase 1–10.3 behavior is changed; no frontend, chat,
> delete/retention, queue, or compliance redesign is
> introduced.

## 1. Implemented path

```text
POST /compliance-evidence/uploads (member-allowed)
    ↓ authenticate actor / resolve tenant (existing)
    ↓ workflow authorization + terminal check (existing
    │   is_closed semantics; 409 before any mutation)
    ↓ availability pre-checks (storage/indexing wired;
    │   503 before any mutation when unwired)
    ↓ file-size validation (10 MB, U2)
    ↓ file-type + magic-byte validation (U1)
    ↓ content-hash idempotency (same tenant → same row)
    ↓ server-generated evidence identity + object key (U6)
    ↓ private Storage put (compensating delete on
    │   registration failure)
    ↓ database registration (migration 011 columns)
    ↓ requirement association (link absent on failure)
    ↓ processing: parse → corpus ingest (4.1) → index
    │   sync (4.2 → 4.5) → ready | failed (U7)
    ↓ 201 with identifiers + lifecycle state (never
      bytes, text, keys, or URLs)
```

`GET /compliance-evidence/{id}/download`
(member-readable) verifies tenant + ownership, then
issues one short-lived signed URL (U4).

## 2. Storage (U4)

- Domain protocol `EvidenceObjectStore`
  (`xportra/domain/evidence_storage.py`): `put`,
  `delete` (compensating only), `create_signed_url`.
  The domain/application layers never touch Supabase
  SDK details (there is no SDK — the adapter uses
  `httpx`, already a declared dependency).
- One private bucket (`tenant-evidence`,
  `EVIDENCE_STORAGE_BUCKET`); server-composed keys
  `tenant/{tenant_id}/evidence/{evidence_id}/{content_hash}{ext}`
  (`compose_object_key` — client text can never reach
  storage). No public buckets/URLs, no
  client-controlled keys, no unrestricted downloads.
- `InMemoryEvidenceObjectStore` (tests/dev; opaque
  unguessable download tokens, keys never embedded).
- `SupabaseEvidenceObjectStore` (private Storage REST:
  server-side put with upsert, compensating delete,
  `POST .../sign/...` short-lived URLs). Static error
  messages only — no keys, URLs, bytes, or
  credentials. Configuration (`SUPABASE_URL` +
  `SUPABASE_SERVICE_ROLE_KEY`, optional
  `EVIDENCE_STORAGE_BUCKET`) is documented in
  `.env.example` (placeholders only) and
  `docs/architecture/environment-schema.md`; missing
  configuration fails closed at composition time.
- Production composer
  (`xportra/infrastructure/evidence_upload.py`):
  storage adapter + `EvidenceIndexSyncService` built
  from the canonical vector/embedding variables onto
  the SAME collection/model Phase 5 reads (no new
  collection, scope, or pipeline). `ApplicationServices`
  gains optional `evidence_storage` /
  `evidence_index_sync` slots (default `None` — existing
  behavior unchanged) plus opt-in
  `from_environment_with_evidence_upload()`
  (mirrors the `from_environment_with_rag` precedent).

## 3. File validation (U1/U2)

`xportra/domain/evidence_upload.py` — dedicated
validation boundary, no I/O:

- Closed MVP set: PDF (`application/pdf`),
  DOCX (OOXML wordprocessing), JPEG (`image/jpeg`),
  PNG (`image/png`). Anything else → rejection.
- Declared content type AND magic bytes
  (`%PDF-`; ZIP + `[Content_Types].xml` +
  `word/document.xml`; `FF D8 FF`;
  `89 50 4E 47 0D 0A 1A 0A`); extension↔MIME
  consistency as a check only (extension never
  authoritative). Client MIME never trusted alone.
- 10 MB per file on decoded bytes (`EvidenceFileTooLargeError`
  → HTTP 413 `payload_too_large`; all other
  violations → 400). Rejected before storage.
- Filename safety: no separators, null bytes,
  control characters, dot-only, empty, or over-long
  names. Filenames are display metadata only.
- Uploaded files are never executed. DOCX is read
  via stdlib zip/XML with entity declarations
  rejected (XXE guard); extracted text is
  length-bounded (zip-bomb guard).

## 4. Persistence (U3/U5/U7)

- Migration `011_evidence_upload_processing.sql`
  (+ rollback): eight additive columns on the
  EXISTING `compliance_evidence` table (no second
  evidence table) — `processing_status`
  (`uploaded/processing/ready/failed`),
  `processing_step`, `processing_error` (static step
  codes only), `processed_at`, `original_filename`,
  `mime_type`, `storage_bucket`, `uploaded_by`
  (initiating actor subject, NULL for dev
  identities); partial unique index
  `(tenant_id, content_hash)` for idempotency;
  processing index. `content_hash` stays nullable so
  legacy reference rows are unaffected.
- Repository: `register_upload` (server-generated
  id, key reference, no bytes/text/URLs),
  `get_by_content_hash` (tenant-scoped),
  `set_processing_state` (tenant-scoped update).
- Domain `ComplianceEvidenceService`: matching
  `register_upload` (review status must start
  `uploaded`; starting `ready` is rejected),
  `find_by_content_hash`, `set_processing_state`.
- Audit (U5): actor, tenant, workflow/shipment
  linkage (via supply/history), upload identity,
  content hash, storage reference, processing +
  association + superseded status, timestamps.
  Never: contents, text, secrets, signed URLs, bytes.
  No second audit system.
- Retention (U3): no delete endpoint exists (verified
  404/405); `archived` review status marks
  inactive/superseded rows, which `is_evidence_usable`
  excludes from new analysis while provenance stays
  intact. No retention period invented.

## 5. Processing lifecycle (U7)

`uploaded → processing → ready | failed`, persisted
per transition, separate from review status and from
compliance state. `ready` means ingestion/indexing
passed — never compliance.

- Parse: stdlib-only MVP adapters (DOCX paragraphs;
  PDF literal strings incl. FlateDecode streams; PNG
  tEXt / JPEG COM embedded text). No OCR: images
  without embedded text fail closed at `parse`
  (registered + stored for provenance, `failed`,
  never `ready`).
- Normalize/ingest: the EXISTING
  `EvidenceDocumentIngestionService` (Phase 4.1) with
  server-derived deterministic identity
  (`source_id = tenant-evidence:{evidence_id}`,
  `version = content_hash`) — U6, never colliding
  with regulatory sources; idempotent retry returns
  the identical row.
- Chunk/index: the injected Phase 4.5 sync boundary
  (chunking → indexing → vector upsert), unchanged.
  Index failure marks `failed(sync)` and propagates
  (never a false `ready`); parse/ingest failure marks
  `failed(step)` and returns 201 retryable.
- Retry = idempotent re-invocation (same hash → same
  identities); non-ready rows re-run the pipeline.
- Semantics preserved: uploads arrive `uploaded`
  (never accepted), so the Phase 2.6 rule still
  governs satisfaction; `uploaded ≠ ready ≠
  sufficient ≠ satisfied` is asserted by test
  (ready evidence with `uploaded` status does not
  satisfy; applicability output is byte-identical
  before/after upload).
- Terminal workflows (`assessment_package_ready`)
  are rejected with `terminal_workflow` BEFORE any
  storage/database mutation (verified empty);
  no reopening/versioning exists.

## 6. API

- `POST /compliance-evidence/uploads` (201,
  member-allowed via `CREATE_COMPLIANCE_EVIDENCE`):
  JSON transport with base64 bytes (see §8),
  `extra="forbid"` (tenant IDs, keys, storage
  internals rejected), optional requirement links
  and workflow record (server revalidates per the
  8.2 precedent). Response: identifiers + lifecycle
  state only.
- `GET /compliance-evidence/{id}/download` (200,
  member-readable): tenant + ownership verified
  first; cross-tenant lookups are 404-non-leaking;
  response carries the single short-lived signed
  URL by purpose (`expires_in_seconds: 300`).
- Errors reuse the existing shape: 400
  `invalid_input`, 404 `not_found`, 409
  `terminal_workflow`, 413 `payload_too_large`
  (new subclass mapping, ordered before the plain
  validation entry), 422 transport validation, 503
  `infrastructure_failure` / `evidence_upload_not_configured`.
  Production 5xx carries no details (verified).
- `ComplianceEvidenceResponse` gains optional
  processing/upload fields (additive; pre-migration
  rows and old doubles still serialize).

## 7. Verification

- Focused: `tests/unit/test_phase_10_4_evidence_upload.py`
  (70 tests) + `tests/unit/test_evidence_upload_migration.py`
  (9 tests) — 79/79 passing (+22 subtests).
- Full backend suite: **1902 passed + 44 skipped**,
  0 failures — baseline was 1823 passed + 44
  skipped (79 new, no regressions; skips are the
  unchanged live gates).
- Live Supabase Storage / Postgres / Qdrant /
  OpenRouter: NOT executed (no environment) — the
  Supabase adapter is covered against a fake-HTTP
  backend; no live verification is claimed.

## 8. Deliberate deviations from the Phase 10.3 sketch

- JSON+base64 transport instead of multipart: no
  `python-multipart` dependency is introduced; the
  domain validates decoded bytes identically, and
  the API bounds the transport shape.
- Stdlib-only extraction adapters (no PyMuPDF/
  python-docx installs, no OCR): best-effort PDF
  text, full DOCX text, embedded image metadata
  text. Images without extractable text are stored
  + registered but `failed` (honest, fail-closed).
- No archive/supersede endpoint (U3 allows marking;
  the `archived` status + `is_evidence_usable`
  contract carry it; a future task may expose it).
- `is_evidence_usable(row)` (ready + not
  archived/rejected) is defined, unit-tested, and
  documented as the contract future analysis wiring
  must honor; current assessment already requires
  accepted/reviewed status, so ready uploads still
  satisfy nothing by themselves.

## 9. Explicitly NOT implemented

Frontend upload UI, conversational upload, chat
changes (verified untouched), delete endpoint,
retention policy, background queue, notifications,
workflow reopening, compliance rule changes,
retrieval/reasoning redesign, provider migration,
deployment infrastructure. No packages installed.
