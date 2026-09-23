# Phase 5.2 — Retrieval Quality & Query Semantics

**Status:** Complete and verified (2026-09-22)
**Phase:** Phase 5 — Retrieval & RAG
**Type:** Query semantics + retrieval-quality behavior — retrieval
infrastructure only; no LLM/RAG/reranking

> This record describes what was actually implemented and verified.

## Objective

Convert a user/application information need into a well-defined
retrieval query — establishing normalization, configuration, embedding
boundary, ordering, and duplicate semantics — without introducing LLM
reasoning or answer generation.

## Retrieval-query semantics (three representations)

```text
information need (raw application/user text)
    ↓ EvidenceRetrievalConfig.build_query() / EvidenceRetrievalQuery(...)
validated + normalized domain query   (text + top_k; tenant NOT a field)
    ↓ EmbeddingProvider.embed(normalized text)          [Phase 4.3]
query vector (vector-store representation — internal only)
    ↓ EvidenceRetrieval.find(...) / EvidenceVectorIndex.find(vector, …)
EvidenceRetrievalResult[]   (ordered, duplicate-collapsed)
```

- The domain query is `EvidenceRetrievalQuery`; the vector-store query
  representation (the embedded vector) never appears in domain objects,
  and no Qdrant-specific concept is exposed above the adapter.
- Tenant scope stays an execution-level required keyword (Phase 5.1
  design) — not duplicated into query or configuration.
- `EvidenceRetrievalConfig(top_k=DEFAULT_TOP_K=5)` — the application
  retrieval configuration: exactly one field (`top_k`), reusing the
  Phase 5.1 constant (no competing default);
  `build_query(information_need)` is the explicit information-need →
  validated-query boundary.
- No second embedding configuration system: `EmbeddingProvider` +
  `EmbeddingModelConfig` (Phase 4.3) remain the only embedding
  contracts, injected into the retriever constructor.

## Normalization rules (deterministic only)

- Trim surrounding whitespace and collapse internal whitespace runs
  (spaces, tabs, newlines) to single spaces — `" ".join(text.split())`.
- Reject empty, whitespace-only, and non-string input with
  `DomainValidationError`.
- Preserve case, punctuation, wording, and compliance terminology
  exactly. Example: `What documents are required for exporting cocoa?`
  is embedded verbatim (after whitespace normalization) — never
  rewritten into a guessed alternative. No stemming, stop-word
  removal, synonym substitution, or LLM rewriting: the retrieval layer
  never changes the information need semantically.
- The normalized text is exactly what is passed to the embedding
  provider (tested).

## Ordering contract

- Results are returned in **descending relevance score**, with ties
  broken by **ascending `chunk_id`** — deterministic regardless of the
  order a provider emits tied results.
- Implemented as a stable normalization sort in
  `VectorIndexEvidenceRetriever.retrieve`. It never recomputes,
  modifies, or reranks scores (ordering ≠ reranking) and never
  conflicts with provider semantics: every configured distance metric
  scores higher = closer. The adapter continues to pass provider order
  through unchanged; the service normalizes to this documented
  contract.

## Duplicate / version behavior

The existing identity model was inspected first: `document_id =
uuid5(tenant, source_id, version)` (Phase 4.0) and
`content_fingerprint = sha256(content)` (Phase 4.2).

- **Exact-duplicate rule**: after ordering, only the first (best-ranked)
  result per (`document_id`, `content_fingerprint`) is kept — same
  document identity (which fixes tenant + source + version) AND
  identical content is redundant.
- Evidence from **different documents, versions, or sources is never
  collapsed**, even for byte-identical text, because its provenance
  differs (tested: identical text with different `document_id` → both
  kept; versions v1/v2 → both kept).
- Deduplication runs after top-k limiting, so the result count may be
  below top-k when duplicates were present (documented and tested).
- **Near-duplicates (non-identical text): intentionally not
  collapsed** — the existing model provides no safe deterministic rule;
  heuristic similarity thresholds are deferred to a later phase rather
  than invented here.

## Failure semantics (fail closed)

| Failure | Outcome |
|---|---|
| embedding provider failure | `DomainValidationError` ("embedding provider failed: …") |
| vector index failure | `VectorStoreError("evidence retrieval", cause)` |
| malformed result container/item | `DomainValidationError` |
| invalid configuration (config top-k, embedding config, constructor) | `DomainValidationError` |
| cross-tenant result | `VectorStoreError` |
| no matching evidence | `[]` (the only path to an empty success) |

Infrastructure failures are never converted into empty successful
retrievals; a genuine failure remains distinguishable from "no evidence
found" (tested).

## Testing

`tests/unit/test_evidence_retrieval_quality.py` — **40 focused tests**
(fakes only, no live Qdrant): normalization (5), invalid-query
rejection (3), configuration (5), embedding boundary (5), ordering (4),
duplicates/versions (6), no-result/tenant (4), provider hiding (3),
failure semantics (5).

One Phase 5.1 fixture correction (documented): `seed_entries` assigned
the same `content_fingerprint` to different content, violating the
Phase 4 `sha256(content)` invariant that the duplicate rule relies on;
the fingerprint data was corrected — **no assertion was weakened** and
all 56 Phase 5.1 tests still pass.

Integration: no Qdrant server is configured; consistent with Phases
4.4/4.5/5.1, no live integration test was added.

## Non-goals (later phases)

LLM answer generation, prompt construction, compliance conclusions,
legal interpretation, reranking, hybrid search, LLM-based query
rewriting, agentic retrieval, conversational memory, LLM-generated
citations, and UI work. **Phase 5.3 has not started; Phase 5 is not
complete.**

## Verification

- Focused: `pytest tests/unit/test_evidence_retrieval_quality.py -q`
  → **40/40 passed**.
- Phase 5.1 focused re-run → **56/56 passed**.
- Full unit suite → **564 passed** (524 baseline + 40), 0 failures,
  0 errors; only the 2 pre-existing `starlette`/`anyio` warnings.
- Import surface (`xportra.domain`) verified; no secrets written.