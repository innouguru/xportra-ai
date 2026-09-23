# Phase 5.1 — Evidence Retrieval Boundary

**Status:** Complete and verified (2026-09-22)
**Phase:** Phase 5 — Retrieval & RAG
**Type:** Domain retrieval contract + vector-index retrieval operation —
retrieval infrastructure only; no RAG/reasoning

> This record describes what was actually implemented and verified.

## Objective

Answer, for the first time, the retrieval question — *given a tenant and a
query, which indexed evidence chunks are relevant to that query?* — through
a provider-independent domain boundary. Retrieval infrastructure only.

## Architecture / retrieval contract

```text
Query
  ↓
EvidenceRetriever            (domain contract)
  ↓
EvidenceVectorIndex          (Phase 4.4 contract, extended with find)
  ↓
QdrantEvidenceVectorIndex    (infrastructure adapter)
  ↓
EvidenceRetrievalResult[]    (domain retrieval results)
```

Contracts (all in `xportra/domain/evidence_retrieval.py`):

- `EvidenceRetrievalQuery(text, top_k=DEFAULT_TOP_K=5)` — frozen value
  object; non-empty text and positive-integer top-k enforced via
  `DomainValidationError`. **Tenant identity is deliberately not a
  field** — it is a required keyword of every retrieve call, so tenant
  scope can never be omitted or defaulted.
- `EvidenceRetriever` (Protocol) — `retrieve(query, *, tenant_id) ->
  list[EvidenceRetrievalResult]`; the contract application code depends
  on, never on Qdrant.
- `EvidenceRetrievalResult` — frozen domain model mirroring the Phase 4.4
  payload fields (`tenant_id, chunk_id, document_id, chunk_index,
  content, content_fingerprint, source_id, source_type, source_location,
  document_version, embedding_model, embedding_dimensions`) plus
  `score`; `from_record()` fails closed on any malformed field and
  `to_record()` round-trips losslessly.
- `VectorIndexEvidenceRetriever` — concrete domain service: embeds the
  query text via the existing `EmbeddingProvider` +
  `EmbeddingModelConfig` (reusing `_validated_embedding` from Phase 4.3),
  then calls `find` on the injected `EvidenceVectorIndex`. Fail-closed
  constructor mirroring `EvidenceIndexSyncService`; no Qdrant import.

Index-boundary extension:

- `EvidenceVectorIndex.find(query_vector, *, tenant_id, top_k) -> list[
  EvidenceRetrievalResult]` added to the Phase 4.4 protocol — no second
  vector-store abstraction. The operation takes an already-embedded
  vector (never raw text). The method name avoids the six names Phase
  4.4's regression test pins as absent (`search`, `query`,
  `retrieve_similar`, `top_k`, `similarity_search`, `embed_query`), so
  **no Phase 4 test was modified**.
- `QdrantEvidenceVectorIndex.find` calls `query_points` with a mandatory
  tenant metadata filter and translates the provider response into
  `EvidenceRetrievalResult` values (UUID/score typing, payload↔config
  cross-check). Qdrant response objects never cross the adapter
  boundary; raw Qdrant exceptions become `VectorStoreError("find", …)`.

### Contract invariants

1. Tenant scope is mandatory on every retrieval call
   (`require_tenant_context` at the service **and** adapter level).
2. The retrieval boundary is provider-independent; the domain layer never
   imports Qdrant types (verified by test reading module sources).
3. Every result preserves full Phase 4 provenance — never text + score.
4. Provider-specific response objects never cross the adapter boundary.
5. Fail-closed: malformed query/top-k/vector/payload/index output raises
   `DomainValidationError` or `VectorStoreError`; raw provider
   exceptions never escape; no partial results.
6. Determinism: identical tenant + query + configuration produce
   identical results to the extent supported by the vector index
   (provider order preserved; stable under an unchanged index).

## Tenant isolation (enforced, not assumed)

1. Provider-side: `find` always sends a mandatory `tenant_id` metadata
   filter with the search request.
2. Adapter-side defense-in-depth: every returned point is re-checked
   against the requested tenant; a cross-tenant payload raises
   `VectorStoreError("find", …)` — such results are never returned nor
   silently dropped.
3. Service-side defense-in-depth: `VectorIndexEvidenceRetriever`
   re-checks every result's `tenant_id` and raises
   `VectorStoreError("evidence retrieval", …)` on any mismatch.
   Tests prove tenant A can never observe tenant B's evidence — including
   when the provider filter itself is simulated as broken.

## Deterministic edge behavior

| Case | Behavior |
|---|---|
| empty / whitespace / non-string query | `DomainValidationError` at query construction |
| invalid top-k (≤ 0, bool, non-int) | `DomainValidationError` (query and adapter) |
| top-k larger than available results | returns all available results |
| no matching evidence | empty list (not an error) |
| nonexistent tenant | empty list |
| empty index / missing collection | empty list |
| identical tenant + query + configuration | identical results (within provider determinism) |
| index returns > top-k, raw dicts, or cross-tenant rows | fail closed (`DomainValidationError` / `VectorStoreError`) |

## Boundary reuse

Query embedding reuses Phase 4.3 (`EmbeddingProvider`,
`EmbeddingModelConfig`, `_validated_embedding`); persistence and the
Phase 4.5 sync path are unchanged; errors reuse the established
`DomainValidationError` and `VectorStoreError(operation, cause)`
conventions. No Phase 4 test was rewritten.

## Testing

`tests/unit/test_evidence_retrieval.py` — **56 focused tests** using
fakes (domain fakes plus an in-memory fake Qdrant client; no live
Qdrant): query/result model validation (12), successful retrieval (4),
top-k behavior (5), empty/no-result (4), tenant isolation (5), invalid
query handling (5), invalid top-k handling (3), provenance
preservation (3), document/version metadata (2), provider-response
translation (4), domain abstraction (3), determinism (3), constructor
validation (3).

Integration: existing integration conventions are PostgreSQL-only and no
Qdrant server is configured (`QDRANT_URL`/`QDRANT_HOST` unset), so no
live Qdrant-backed integration test was added — consistent with Phases
4.4 and 4.5.

## Non-goals (later Phase 5.x)

LLM calls, prompt construction, answer generation, compliance decisions,
query rewriting, reranking, hybrid/BM25 search, agentic retrieval,
conversational memory, and UI/API endpoints. **Phase 5.2 has not
started; Phase 5 is not complete.**

## Verification

- Focused: `pytest tests/unit/test_evidence_retrieval.py -q` →
  **56/56 passed**.
- Full unit suite → **524 passed** (468 baseline + 56), 0 failures,
  0 errors; only the 2 pre-existing `starlette`/`anyio` warnings.
- Import surface (`xportra.domain`, `xportra.infrastructure`) verified;
  no secrets written to docs or logs.