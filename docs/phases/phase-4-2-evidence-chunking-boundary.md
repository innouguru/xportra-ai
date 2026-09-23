# Phase 4.2 — Evidence Chunking Boundary

**Status:** Complete and verified (2026-09-22)
**Phase:** Phase 4 — Retrieval
**Type:** Deterministic domain transformation — no retrieval, no embeddings

> This record describes what was actually implemented and verified.

## Objective

Transform persisted evidence documents into bounded, traceable,
deterministic chunks that future retrieval systems can index:

```text
EvidenceDocument → Document Normalization → EvidenceChunk[]
```

## Service and entry point

`EvidenceChunkingService` in `xportra/domain/evidence_chunking.py`; entry
`chunk(document, *, tenant_id) -> list[dict]`. Accepts an `EvidenceDocument`
or an equivalent record dict; returns chunk records only.

## EvidenceChunk contract

`tenant_id, chunk_id, document_id, chunk_index, content,
content_fingerprint, source_id, source_type, source_location,
document_version, start_offset, end_offset`. Traceability:
tenant → source → document → chunk. No `section` field is emitted because
sections are never inferred.

## Chunking strategy and maximum size

Blank-line paragraph segmentation over the exact document content, then a
deterministic `MAX_CHUNK_CHARACTERS = 1200` bound (engineering constraint,
not retrieval tuning). Paragraphs within the bound stay intact as one
chunk. Oversized paragraphs split at the last whitespace inside each
maximum-size window; a window with no whitespace (single oversized word)
cuts at the exact boundary. The single whitespace character at a cut is the
only dropped character. Order is preserved; empty/whitespace-only
paragraphs produce no chunks.

## Content preservation invariant

Every chunk content is an exact substring of the document content
(`start_offset`/`end_offset` prove it). No summarizing, paraphrasing,
translation, grammar correction, LLM use, or removal of substantive text.
Normalization policy: **content is not normalized at all — only
segmented**; blank-line separators are the only structural delimiters
removed.

## Stable chunk identity

`stable_chunk_id = uuid5(NAMESPACE_URL, "xportra:evidence-chunk:" +
tenant_hex + ":" + document_hex + ":" + str(chunk_index) + ":" +
content_fingerprint)` — consistent with the Phase 4.0 uuid5 strategy. No
random UUIDs, timestamps, or secrets. Same document content and index →
same `chunk_id`; changed content changes the fingerprint and therefore the
affected chunk identity.

## Provenance, tenant isolation, validation

Provenance (`document_id, source_id, source_type, source_location,
document_version, tenant_id`) is propagated unchanged from the document —
never regenerated or inferred from chunk content. `TenantContext` is
required; tenant mismatch, invalid tenant, malformed document, missing
content/identity, and unsupported source types fail closed via
`DomainValidationError`. Sections, headings, authorities, jurisdictions,
and page numbers are never inferred from raw text.

## Persistence decision

No persistence in this phase: chunks are an in-memory domain
representation; no `EvidenceChunkRepository`, no migration, no schema
change. Future retrieval phases may add chunk persistence behind a
dedicated repository/migration; the existing evidence-documents table is
not modified to store chunks.

## Determinism

Identical document → identical chunk count, order, content, IDs,
fingerprints, and offsets. No randomness, timestamps, or LLM boundaries.

## Non-goals

No embeddings, sentence-transformers, vector databases, Qdrant, pgvector,
BM25, keyword/semantic search, reranking, query rewriting, retrieval
execution, RAG, LLM calls, web search, crawling, regulatory APIs, agents,
or persistence. Output is exactly `EvidenceDocument → EvidenceChunk[]`.

## Tests and verification

`tests/unit/test_evidence_chunking.py` — 25 tests covering all required
scenarios (1–25) including oversized splitting, empty/whitespace-only
paragraphs, boundary conditions, no-inference, and end-to-end document →
chunks. Focused 25/25; full suite 364/364 (339 baseline + 25), 0
failures/errors. PostgreSQL integration not run (`DATABASE_URL`
unconfigured); no database component exists in this phase.

