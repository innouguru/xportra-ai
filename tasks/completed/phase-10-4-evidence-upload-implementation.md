# Phase 10.4 — Evidence Upload Implementation (Complete, 2026-09-27)

Implements the approved evidence-upload boundary (Phase 10.3
scope, ADR-0011) under `REQUIREMENTS.md` R-10.4 with resolved
product decisions U1–U7. Minimum production-safe path only.

## Acceptance criteria

- [x] U1–U7 recorded as resolved (phase doc §13, ADR-0011
  addendum, R-10.4, this record).
- [x] Private storage boundary exists (domain protocol +
  in-memory + Supabase-HTTPS implementations; one private
  bucket; server-composed keys; no public URLs).
- [x] 10 MB validation exists (server-side, pre-storage,
  413 mapping).
- [x] PDF/DOCX/JPEG/PNG validation exists (declared type
  + magic bytes; extension consistency only).
- [x] Magic-byte validation exists (authoritative over
  client MIME).
- [x] Server-generated identities/object keys exist
  (evidence id, content hash, key, corpus source/version;
  client chooses none).
- [x] Evidence processing state is persisted (migration
  011 + rollback; `uploaded → processing → ready | failed`).
- [x] Existing ingestion/indexing pipeline is reused
  (4.1 ingestion, 4.2–4.5 sync; no parallel pipeline;
  no Phase 5/6 changes).
- [x] Idempotency is deterministic (same tenant + hash →
  same row; cross-tenant independent).
- [x] Terminal workflows cannot be modified (409 before
  any mutation; verified empty; no reopening).
- [x] Download authorization is tenant-safe (ownership
  verified; 404-non-leaking; short-lived signed URLs).
- [x] No public storage access exists.
- [x] Upload does not imply compliance (ready ≠
  sufficient ≠ satisfied, asserted by test).
- [x] Security/error-surface tests pass (isolation,
  authz, validation, lifecycle, semantics, production
  sanitization, no leakage).
- [x] Full regression passes (1902 passed + 44 skipped).
- [x] Documentation is complete (phase doc, ADR addendum,
  R-10.4, schema, env template, state files).
- [x] No frontend/chat/compliance redesign introduced
  (chat route verified untouched; no delete endpoint).

## Artifacts (new)

- `xportra/domain/evidence_upload.py` (validation, keys,
  extraction, U7 states, usability predicate)
- `xportra/domain/evidence_storage.py` (protocol, bucket,
  errors)
- `xportra/infrastructure/evidence_storage.py`
  (in-memory + Supabase-HTTPS)
- `xportra/infrastructure/evidence_upload.py`
  (production composers)
- `xportra/application/evidence_upload.py` (use case, DTOs)
- `xportra/api/evidence_uploads.py` (2 endpoints)
- `migrations/011_evidence_upload_processing.sql` (+ down)
- `tests/unit/test_phase_10_4_evidence_upload.py` (70)
- `tests/unit/test_evidence_upload_migration.py` (9)
- `docs/phases/phase-10-4-evidence-upload-implementation.md`

## Artifacts (modified, all additive)

- `xportra/persistence/repositories.py`,
  `xportra/domain/services.py`,
  `xportra/application/errors.py` (+ `__init__.py`),
  `xportra/domain/__init__.py`,
  `xportra/infrastructure/__init__.py`,
  `xportra/api/{errors,schemas,dependencies,app}.py`,
  `docs/architecture/environment-schema.md`, `.env.example`
  (placeholders only), Phase 10.3 docs (U1–U7 resolved),
  `REQUIREMENTS.md` (R-10.4), `CURRENT_STATE.md`,
  `ACTIVE_TASK.md`, `docs/decisions/README.md` (index).

## Verification

- Focused: 79/79 passing (+22 subtests).
- Full suite: 1902 passed + 44 skipped, 0 failures
  (baseline 1823 + 44; +79 new, no regressions).
- Live Supabase/Postgres/Qdrant/OpenRouter: NOT
  executed (no environment); Supabase adapter covered
  against a fake-HTTP backend only.
- No packages installed. No commit/push performed.
