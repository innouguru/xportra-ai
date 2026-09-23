# Phase 4.3 — Evidence Embedding & Indexing Boundary

**Status:** Complete (2026-09-22)
**Phase:** Phase 4 — Retrieval
**Type:** Indexing-side boundary — validation of chunk content, embedding request through a provider protocol, and indexed chunk representation. No retrieval/similarity-search/RAG.

> This record describes what was actually implemented and verified.

## Objective

Establish the boundary between deterministic Phase 4.2 chunks and a future vector/index representation:

```text
EvidenceDocument
      ↓
EvidenceChunk[]
      ↓
EvidenceIndexingService
      ↓
IndexableEvidenceChunk (model id, dimensions, embedding vector, provenance)
```

The domain depends on an `EmbeddingProvider` protocol, never on a specific vendor SDK, so local models or hosted APIs can later be substituted. Retrieval (similarity search, top-k, metadata filtering, hybrid/BM25, reranking, query embedding, RAG, LLM answering) is explicitly out of scope.

## Services and boundaries

- `xportra/domain/evidence_indexing.py`
  - `EmbeddingModelConfig(model_identifier, dimensions)` — explicit contract; never silently inferred.
  - `EmbeddingProvider` protocol with `embed(text: str) -> list[float]`.
  - `IndexableEvidenceChunk` frozen dataclass + `to_record()`.
  - `EvidenceIndexingService.index(chunks, *, tenant_id, provider, config)` — fail-closed.
- `__init__.py` exports `EmbeddingModelConfig, EmbeddingProvider, IndexableEvidenceChunk, EvidenceIndexingService`.

## Input/output contract

Input: sequence of Phase 4.2 `EvidenceChunk` dicts + `TenantContext` + `EmbeddingProvider` + `EmbeddingModelConfig`. Output: list of `IndexableEvidenceChunk` records preserving `tenant_id, chunk_id, document_id, chunk_index, content, content_fingerprint, source_id, source_type, source_location, document_version` plus `embedding_model, embedding_dimensions, embedding_vector`.

`chunk_id` stays the canonical identity; no new random identity is generated. The embedding is associated with the exact chunk content that produced it. Traceable: `tenant → source → document → chunk → embedding`.

## Validation and invariants (fail closed, no silent skipping)

- `require_tenant_context(tenant_id)`; config must be `EmbeddingModelConfig`; provider must expose a callable `embed`; `chunks` must be a sequence.
- Each chunk validated: non-dict rejected; `tenant_id` mismatch rejected; `chunk_id`/`document_id` must be `UUID`; `chunk_index` must be a non-negative `int`; `content` must be a non-blank string; `content_fingerprint` must be a non-blank string; `source_id` must be a non-blank string; `source_type` must be in the Phase 4.0 `SOURCE_TYPES` set; `document_version`, if present, must be a string.
- Provider output validated in `_validated_embedding()`: must be a non-empty list/tuple; not a string/bytes; no bool elements; all numeric; all finite; length must equal `config.dimensions`.
- Provider failure is caught and converted to `DomainValidationError` (fail closed, never skipped).
- Malformed input or embedding does not silently skip; it raises.

## Tenant isolation, provenance, content preservation

- `TenantContext` required; chunk tenant must match; every indexed record carries the same tenant identity.
- Source provenance (`source_id`, `source_type`, `source_location`, `document_version`) and `document_id` preserved unchanged from the chunk.
- Content preserved exactly; `content_fingerprint` preserved unchanged.

## Model configuration

Explicit `EmbeddingModelConfig` required: `model_identifier` (non-blank string) and `dimensions` (positive integer, not bool). Validation rejects blank/missing identifier, zero/negative/bool dimensions. This is the minimum configuration for this phase; no provider credentials or external API requirements are baked in.

## Vector-database persistence decision

Deferred. Phase 4.3 produces `IndexableEvidenceChunk` records in memory/domain representation only. No Qdrant, pgvector, Pinecone, Elasticsearch, or other vector store is implemented. A concrete vector-store adapter belongs in a later phase.

## Non-goals (explicit)

No retrieval, similarity search, top-k, metadata filtering, hybrid/BM25, keyword search, reranking, query embedding/embedding-retrieval, query rewriting, retrieval orchestration, RAG, LLM calls for answering, web search, crawling, regulatory APIs, agents, or vector-store writes.

## Tests and verification

`tests/unit/test_evidence_indexing.py` — 26 tests:
1. valid chunk indexed with model id/dimensions/vector
2. multiple chunks indexed
3. deterministic provider call (once per chunk content)
4. dimension validation
5. inconsistent dimensions rejected
6. non-finite embedding rejected (nan, inf)
7. empty embedding rejected
8. malformed embedding types rejected (string/dict/list-with-non-numeric/int/set)
9. malformed chunk rejected (no silent skipping)
10. missing chunk/document identity rejected
11. tenant mismatch rejected
12. invalid tenant context rejected
13. provenance preserved
14. content preserved exactly
15. content fingerprint preserved
16. document/chunk identity preserved
17. provider failure fails closed
18. per-chunk embeddings preserved
19. empty input → empty output deterministic
20. malformed container rejected
21. stable index representation
22. model identifier preserved
23. config validation
24. service requires provider + config
25. end-to-end chunking → indexing traceability
26. missing-field rejection set

Focused 26/26; full suite 390/390 (364 baseline + 26), 0 failures/errors; Phase 4.0–4.2 suites unchanged. PostgreSQL integration not run (`DATABASE_URL` unconfigured). Stray `_last_indexing_run.txt` removed. Earlier contracts (4.0–3.9) unchanged.
