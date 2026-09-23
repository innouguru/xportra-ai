# Phase 4.1 — Evidence Document Ingestion Boundary

**Status:** Complete and verified (2026-09-22)
**Phase:** Phase 4 — Retrieval
**Type:** Controlled ingestion boundary — no acquisition, no search/retrieval

> This record describes what was actually implemented and verified.

## Objective

Controlled conversion of an external/source evidence artifact into a
validated `EvidenceDocument` in the Phase 4.0 corpus:
Source → Ingestion Boundary → EvidenceDocument → Repository → Corpus.
No retrieval, embeddings, chunking, or RAG.

## Service and entry point

`EvidenceDocumentIngestionService` in `xportra/domain/evidence_ingestion.py`;
entry `ingest(source_record, *, tenant_id)`. The service owns the ingestion
contract; `EvidenceDocumentRepository` owns persistence mechanics (no raw
SQL from the domain; repository is never bypassed).

## Input contract

Phase 4.0 `EvidenceDocument` fields (`title, content, source_type,
source_id, source_location, jurisdiction, document_version, effective_date,
retrieved_at, status, metadata`, optional `tenant_id`). No second document
model. A record-supplied `tenant_id` must equal the method `tenant_id`
(`TenantContext`, authoritative for scoping).

## Validation and provenance

Fail closed on: non-dict record; invalid/missing/conflicting tenant;
missing/blank `source_id`; missing `source_type`; missing/blank
`source_location`; empty `title`; empty `content`; unsupported source type
(no case-folding — `"REGULATION"`/`"Regulation"` are rejected, reusing the
Phase 4.0 vocabulary); malformed `metadata` (must be dict); non-date
`effective_date`/`retrieved_at` (must carry `isoformat`); non-string or
whitespace-padded `document_version`. Provenance (`source_id`,
`source_type`, `source_location`, `document_id`) is required — no anonymous
records, no inferred provenance. Existing `DomainValidationError` /
`DomainPersistenceError` conventions; no new hierarchy.

## Normalization

Loss-minimizing only: surrounding whitespace stripped from `title` and
`source_location`; `source_id` stripped (documented Phase 4.0 identity
behavior). Stored `content` is preserved byte-for-byte, so the content
fingerprint deterministically reflects source evidence. No rewriting,
summarizing, paraphrasing, or LLM title generation.

## Identity, dedup, idempotency

Reuses Phase 4.0 stable identity: uuid5 from tenant hex + `source_id` +
version; no new scheme. Same tenant + `source_id` + version resolves to the
same logical document. Identical duplicate (same source identity, version,
content/metadata/provenance, fingerprint) → idempotent return of the
existing document (no second write). Same source/version with materially
different content or provenance → `DomainValidationError` (no silent
overwrite, no version mutation). Different versions → distinct documents.
Repository `PersistenceIntegrityError` → `DomainPersistenceError`.

## Tenant isolation, metadata, status

`TenantContext` required; record/method tenant conflict rejected; all
repository calls tenant-scoped; persisted row tenant re-verified. Metadata
must remain a structured dict, preserved as provided — no flattening, no
injected tenant IDs, decisions, risk scores, or claims. Status reuses
`active|inactive` only; `active` never means compliant/valid/sufficient.

## Non-goals

No HTTP fetching, crawling, filesystem or cloud acquisition, connectors, or
regulatory API calls (the record must already contain the artifact). No
embeddings, vector/Qdrant, BM25, ranking, reranking, chunking, query
rewriting, RAG, LLM, agents. No compliance verdicts, risk, or applicability
decisions. Phase 4.1 ends at the persisted evidence document.

## Tests and verification

`tests/unit/test_evidence_document_ingestion.py` — 26 tests (25 required
scenarios + 3 boundary extras: integrity-error translation, no inferred
fields, malformed record). Focused 26/26; full suite 339/339 (313 baseline
+ 26), 0 failures/errors; earlier suites unchanged. PostgreSQL integration
not run (`DATABASE_URL` unconfigured); the existing Phase 4.0 repository and
migration 009 provide persistence.
