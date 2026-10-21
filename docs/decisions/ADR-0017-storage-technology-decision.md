# ADR-0017 Addendum — Storage Technology Review and Implementation Plan

**Status:** Technology review complete; technology baseline suitable; storage/access policy for regulatory artifacts remains unresolved; PDF parser integration remains open; in-process worker mechanism approved conditionally (Task 3B).
**Date:** 2026-10-21
**Linked:** ADR-0017 (`docs/decisions/ADR-0017-regulatory-knowledge-administration.md`), technology baseline (`docs/architecture/technology-baseline.md`).

## Evidence inspected

- `docs/technologies.md`: does not exist (documented gap).
- Authoritative technology specification: `docs/architecture/technology-baseline.md` (approved baseline: PostgreSQL via Supabase Free; Supabase Storage Free; PyMuPDF for PDF; `python-docx`; BeautifulSoup; custom Python normalization/chunking; sentence-transformers; Qdrant; FastAPI; Python 3.13; no Docker).
- `.env`: `VECTOR_STORE_URL` (hosted Qdrant endpoint, masked), `VECTOR_STORE_COLLECTION=xportra-regulatory`, `EMBEDDING_MODEL=all-MiniLM-L6-v2`, `LLM_API_KEY` empty, `LLM_MODEL` empty, `EMBEDDING_DIMENSIONS` empty, `DATABASE_URL` points to hosted Supabase (`postgres` superuser/admin role), `QDRANT_API_KEY` present (secret). No `REGULATORY_WORKER_ACTOR_USER_ID` or storage bucket name configured.
- Existing storage contracts (`xportra/domain/evidence_storage.py`, `xportra/infrastructure/evidence_storage.py`): private bucket `tenant-evidence`, server-composed keys, private-only access, signed URL downloads (`DEFAULT_DOWNLOAD_URL_TTL_SECONDS` = 300), no public URLs. The protocol (`EvidenceObjectStore`) supports `put`/`delete`/`create_signed_url`.
- Existing migrations: 011 (`evidence_upload_processing`) confirms storage-related processing states; 003 (`regulatory_source_artifacts`) defines artifact metadata (`artifact_uri`, `content_hash`, `content_length`, `content_type`, `acquisition_channel`) but does not specify durable storage backend, retention policy, or access audience.
- Dependency inspection (`pyproject.toml`): `PyMuPDF` is mentioned in the technology baseline but not declared in dependencies; `python-docx` not declared either. This confirms a dependency gap before PDF ingestion can proceed.
- Deployment audit (`docs/deployment/XPORTA-V1-DEPLOYMENT.md` §14): Qdrant endpoint reachable but collection `xportra-regulatory` missing (404); deployment never performed; `.env` uses `postgres` superuser/admin role; no separate application DB user exists.

## Technology assessment

- **PostgreSQL (Supabase Free)**: fully suitable for durable ingestion jobs (`regulatory_ingestion_jobs` migration 018), artifact metadata (`regulatory_source_artifacts`), audit linkage (`global_staff_audit`), and transaction-bound claim/retry/recovery. Atomic transactions (`database.transaction()`), advisory locks (`pg_advisory_xact_lock`), and idempotency constraints (`(artifact_id, attempt_number)`) are supported.
- **Supabase Storage Free**: suitable for durable original-file retention but requires an explicit private bucket/access policy separate from `tenant-evidence`. The existing `EvidenceObjectStore` protocol can be extended or reused; the technology baseline supports multiple private buckets (`Supabase Storage Free` supports bucket-level access control). No new external storage provider is required.
- **In-process worker mechanism**: the smallest viable mechanism under Render/no-Docker/budget constraints. A PostgreSQL-backed polling worker within the existing FastAPI lifespan (Task 3B implementation) satisfies durable job persistence, bounded retries, safe shutdown, and crash recovery (expired claim reset to `retryable`). It does not claim exactly-once delivery; safe retries and idempotency through attempt numbering are the current contract. No Docker, no new paid service, no external queue required.
- **PDF parser/library**: not integrated. The technology baseline specifies `PyMuPDF` but it is not declared in `pyproject.toml`. Integration requires dependency addition, parser contract verification (encryption detection, size/page/time/memory limits, partial extraction reporting, scanned/unreadable PDF handling), and security review. This remains a capability gate (ADR-0017 §4) before PDF ingestion is permitted.

## Storage/access policy gap

The existing evidence-upload storage boundary (`EvidenceObjectStore`) is tenant-scoped (`EVIDENCE_STORAGE_BUCKET = "tenant-evidence"`). Regulatory source artifacts are global (operator-managed, not tenant-owned) and must not be exposed through tenant evidence APIs or download paths. The technology baseline does not specify a dedicated regulatory-source storage bucket or retention/deletion policy. This gap must be resolved before production ingestion of regulatory sources:

- **Recommendation**: define a dedicated private Supabase Storage bucket (e.g., `regulatory-source-artifacts`) with server-composed keys, restricted access (only the service identity with an active `GRANT_MANAGE` grant), and no public download URLs. Preserve the original artifact (immutable bytes, content hash `content_hash`, exact URI `artifact_uri`) separately from tenant evidence.
- **Retention/deletion**: undefined (`docs/phases/phase-4d-regulatory-knowledge-administration.md` §Task 2 notes retention/deletion controls unresolved; ADR-0017 §5 confirms retention/deletion policy and duration remain open). Do not choose a retention duration or deletion rule until approved.

## Authorization boundary (Task 3B evaluation)

The ingestion mutations (`start_ingestion`, `claim_job`, `complete_job`, `fail_job`) enforce `GlobalStaffGrantService.is_granted(actor_user_id, GRANT_MANAGE)`. The automated worker (`RegulatoryIngestionWorker`) requires a configured service identity (`REGULATORY_WORKER_ACTOR_USER_ID`) that holds an active `GRANT_MANAGE` grant. This does not invent a new permission mechanism — it uses the existing `GRANT_MANAGE` authorization model. However, a dedicated service identity and its active grant must be provisioned through the approved bootstrap/authorization procedure (`tasks/blocked/bootstrap-authorization-policy.md`, `docs/phases/phase-4d-10-authorization-evidence-procedure.md`). The worker fails closed when this identity/grant is missing (`_is_authorized()` returns `False` and execution skips). This preserves the original submitter attribution (`actor_user_id` in the job record) separate from the service identity that executes claims/completions.

## PDF parser selection (existing dependency evaluation)

- `docs/architecture/technology-baseline.md` specifies `PyMuPDF` (`fitz`) for PDF extraction.
- `pyproject.toml` does not declare `PyMuPDF`; no `fitz` import exists in `xportra/domain/ingestion.py` or any regulatory parser module.
- The regulatory parser (`ArtifactParsingService`) supports only `text/plain`, `text/markdown`, `application/json`. No PDF support exists.
- Recommendation: add `pymupdf` (or equivalent `fitz`-compatible package) to `pyproject.toml` after dependency review; extend `ArtifactParsingService` with bounded PDF parsing; verify encryption detection, size limits, page-level provenance, partial extraction reporting, and scanned/unreadable PDF handling; do not claim PDF ingestion is supported until integration is verified with focused tests.

## Implementation prerequisites (before production regulatory ingestion)

1. **Storage/access policy**: define and configure the dedicated private storage bucket/access policy for regulatory artifacts; confirm retention/deletion policy is approved (ADR-0017 §5; unresolved).
2. **Service identity/grant**: configure `REGULATORY_WORKER_ACTOR_USER_ID` (or equivalent) and provision an active `GRANT_MANAGE` grant through the approved authorization procedure (`tasks/blocked/bootstrap-authorization-policy.md`; separate from any bootstrap mechanism). The worker skips execution safely until this is confirmed.
3. **PDF parser integration**: add `PyMuPDF` to `pyproject.toml`; extend `ArtifactParsingService`; verify security/review limits; add focused tests for PDF extraction, partial failure, and manual recovery.
4. **Recovery/retry verification**: verify the in-process worker mechanism with live PostgreSQL integration tests (skipped in current environment when `DATABASE_URL` absent); confirm crash recovery resets expired claims safely without duplicating effects or corrupting audit linkage.
5. **Operational prerequisites**: confirm Render hosting compatibility (no Docker), budget constraints respected, and operational ownership defined (ADR-0017 §3, §5; deployment audit `XPORTA-V1-DEPLOYMENT.md` §14).

Only prerequisites #2 and #4 are directly required for the current in-process mechanism to execute safely; #1 and #3 are required before real regulatory PDF/text ingestion can proceed. #5 remains an open operational gate.
