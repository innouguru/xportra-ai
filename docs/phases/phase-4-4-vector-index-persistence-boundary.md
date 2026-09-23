# Phase 4.4 — Vector Index Persistence Boundary

**Status:** Complete and verified (2026-09-22)
**Phase:** Phase 4 — Retrieval
**Type:** Concrete vector-index persistence adapter — no search/retrieval

> This record describes what was actually implemented and verified.

## Objective

Persist Phase 4.3 `IndexableEvidenceChunk`s into a Qdrant-backed vector
index while the domain layer stays Qdrant-independent:
`EvidenceDocument → EvidenceChunk[] → IndexableEvidenceChunk → Vector Index`.
Persistence only — no similarity search, top-k retrieval, query embedding,
reranking, hybrid retrieval, BM25, or RAG.

## Architecture / domain protocol

`xportra/domain/vector_index.py` defines the Qdrant-independent contract:

- `EvidenceVectorIndex` protocol — `upsert(chunk, *, tenant_id)`,
  `get(*, tenant_id, chunk_id)`, `delete(*, tenant_id, chunk_id)`,
  `count(*, tenant_id)`; every operation requires tenant context.
- Contains no `qdrant_client` import (verified by test).

`xportra/infrastructure/vector_index.py` contains
`QdrantEvidenceVectorIndex` — the only layer importing Qdrant.

## Configuration

`VectorIndexConfig` (frozen dataclass): `collection_name`,
`embedding_model`, `embedding_dimensions`, `distance_metric`
(`cosine|euclid|dot`). Dimensions are never inferred from vectors;
`VectorIndexConfig.from_embedding_config()` reuses the Phase 4.3
`EmbeddingModelConfig` boundary. Invalid dimensions/empty names/bad
metrics fail with `DomainValidationError`.

## Collection initialization

`ensure_collection()`: missing → create with configured size/distance;
existing compatible → left intact (never recreated); incompatible
dimensions/distance/unsupported layout → `VectorStoreError`
(`validate_qdrant_collection_config`); repeated calls idempotent.
Startup is non-destructive — no silent migration or replacement.

## Canonical point identity

`chunk_id` is the Qdrant point ID (`chunk_id → vector point`). Upsert is
idempotent: repeated upsert of the same chunk leaves exactly one logical
point. No second ID scheme, no UUID4, no timestamps.

## Tenant isolation

Every payload carries `tenant_id`. `get`/`delete` require tenant + chunk_id;
a point belonging to another tenant is treated as not-found (never
returned/deleted). `count` filters by tenant payload. No bulk or
collection-wide deletion.

## Provenance payload

Payload persists `tenant_id, chunk_id, document_id, chunk_index, content,
content_fingerprint, source_id, source_type, source_location,
document_version, embedding_model, embedding_dimensions`. Stored content
corresponds exactly to the embedded content — no rewriting or summarizing.

## Validation (fail closed)

Rejects: invalid/absent `TenantContext`, tenant mismatch, malformed chunk,
missing chunk/document/tenant identity, bad chunk_index, missing
provenance, unsupported `source_type`, empty content, missing fingerprint,
embedding-model mismatch, dimension mismatch, non-list/empty/non-numeric/
non-finite (NaN/±inf) embeddings. No invalid record is silently skipped.

## Error translation

Raw Qdrant exceptions never escape: all client failures are translated to
`VectorStoreError(operation, cause)` (same convention as
`DomainPersistenceError`); missing points/collections raise
`DomainNotFoundError`; validation raises `DomainValidationError`.

## Testing strategy

`tests/unit/test_evidence_vector_index.py` — 48 tests across config (6),
collection init (5), upsert (8), get (4), delete (4), validation (13),
error translation (4), regression (4), using an in-memory fake Qdrant
client. No running Qdrant server required for the unit suite.

## Explicit non-goals

No similarity/nearest-neighbor search API, top-k retrieval, query
embedding, metadata-filtered search, hybrid retrieval, BM25, keyword
search, reranking, query rewriting, retrieval orchestration, RAG, or LLM
calls. Qdrant's internal search capability is not exposed at any
application level. Retrieval and RAG remain deferred to later phases.

## Verification

- Focused: `pytest tests/unit/test_evidence_vector_index.py -q` →
  **48/48 passed**.
- Full unit suite → **438 passed** (390 baseline + 48), 0 failures,
  0 errors; only the 2 pre-existing `starlette`/`anyio` warnings.
- Import verification: `xportra.infrastructure`,
  `from xportra.domain import *`, and
  `xportra.infrastructure.vector_index` all import cleanly (the previously
  broken `ModuleNotFoundError`/`AttributeError` references are resolved).
- Real Qdrant integration: **not run** — no Qdrant server reachable
  (localhost:6333 timeout; no `QDRANT_URL`/`QDRANT_HOST` configured).
  qdrant-client 1.19.0 being installed is not treated as integration
  evidence.
