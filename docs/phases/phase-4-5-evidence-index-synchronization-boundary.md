# Phase 4.5 — Evidence Index Synchronization Boundary

**Status:** Complete and verified (2026-09-22)
**Phase:** Phase 4 — Retrieval
**Type:** Orchestration boundary — no retrieval/search/RAG

> This record describes what was actually implemented and verified.

## Objective

Keep the persistent vector index aligned with the canonical evidence corpus:
`EvidenceDocument → EvidenceChunk[] → IndexableEvidenceChunk → Vector Index`.
Orchestration only — this is not a retrieval phase.

## Synchronization flow / service responsibilities

`EvidenceIndexSyncService` (`xportra/domain/evidence_index_sync.py`), entry
`sync(document, *, tenant_id)`:

1. Validate tenant context (`require_tenant_context`) and that the document
   record's `tenant_id` matches; document `id` must be a UUID.
2. Chunk via the existing `EvidenceChunkingService` (no chunking logic here;
   empty/malformed chunk output is rejected, not skipped).
3. Embed/index via the existing `EvidenceIndexingService` with the injected
   `EmbeddingProvider` + explicit `EmbeddingModelConfig`.
4. Persist each `IndexableEvidenceChunk` through the `EvidenceVectorIndex`
   protocol (never raw Qdrant).
5. Return a deterministic report: `tenant_id`, `document_id`,
   `document_version`, `chunk_count`, `indexed_count`, `indexed_chunk_ids`,
   `status: "complete"` — only on full success.

Constructor fail-closed: each of chunking/indexing/vector_index/provider
must expose its callable, and `embedding_config` must be an
`EmbeddingModelConfig`, else `DomainValidationError`.

## Boundary reuse

The service contains zero chunking, embedding, or vector-store logic. It
coordinates the existing services exactly as `Sync → Chunking → Indexing →
VectorIndex`; no duplicated chunking/embedding code and no direct Qdrant
dependency (only the Phase 4.4 domain protocol).

## Tenant guarantees

Fail-closed on: missing/invalid tenant context; document tenant ≠ supplied
tenant; any generated chunk with a different tenant; any indexable chunk
with a different tenant. No operation crosses tenant boundaries.

## Deterministic behavior / idempotency

Same document synchronized twice → same chunk identities and same vector
point IDs (canonical `chunk_id → point` from Phases 4.2/4.4); repeated
upsert leaves no duplicate logical points. No second synchronization ID
scheme and no pre-check/skip logic — deterministic upsert through the
existing persistence boundary.

## Version behavior

`document_version` is carried through to the report and preserved on chunks.
Different document versions have distinct Phase 4.0 document IDs, so their
chunks/points remain distinguishable; one version never silently overwrites
another.

## Failure and partial synchronization

Fail-closed: malformed chunks, invalid embeddings, tenant mismatches, invalid
documents, and vector persistence failures all raise through existing
conventions (`DomainValidationError` / `VectorStoreError`). An upsert failure
is wrapped as `VectorStoreError("evidence index sync (chunk N of M)")` —
a success report is never returned for partial work, and raw Qdrant
exceptions never escape. **No rollback**: already-persisted points are not
deleted on failure because upsert is idempotent and points may pre-date this
sync; re-running after a fix is safe. No queues, distributed transactions,
or background workers.

## Empty/invalid input

Invalid/empty documents fail via the established Phase 4.2/4.3 domain rules
(e.g. "document produced no evidence chunks"); zero-content vectors are
never created.

## Testing

`tests/unit/test_evidence_index_sync.py` — **30 focused tests** using fakes
for chunking/indexing/vector-index (no live Qdrant): happy path and report
shape, boundary-reuse assertions, tenant isolation, determinism/repeat-sync,
versioning, failure/partial-failure (no false success), and invalid input.

## Non-goals

No similarity/top-k retrieval, query embeddings, query rewriting, metadata
search, BM25, hybrid search, reranking, retrieval orchestration, RAG, LLM
answer generation, document acquisition/crawling, API endpoints, background
workers, or compliance-rule changes. Live Qdrant integration not run (no
server configured); the Phase 4.4 adapter already has isolated unit coverage.

## Verification

Focused 30/30; full suite **468/468** (438 baseline + 30), 0 failures/errors.
 Phase 4.5 — Evidence Index Synchronization Boundary