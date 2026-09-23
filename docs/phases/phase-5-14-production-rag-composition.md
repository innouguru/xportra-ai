# Phase 5.14 — Production RAG Composition & Infrastructure Wiring

**Status:** Complete and verified (2026-09-23)
**Phase:** Phase 5 — Retrieval & RAG
**Type:** Composition-root and infrastructure wiring — the real
dependency graph behind `POST /rag/query`; no domain-contract
redesign, no vendor adapter, no new vector database

> This record describes what was actually implemented and verified.

## Objective

Wire the Phase 5.13 application chain to existing production
infrastructure so the endpoint executes the real pipeline:

```text
HTTP → auth/tenant → RAGApplicationService → EvidenceContextPipeline
→ HybridEvidenceRetriever → Qdrant/embedding infrastructure
→ DeterministicEvidenceRanker → DeterministicContextSelector
→ EvidencePrompt → LLMClient → GeneratedAnswer
→ CitationAwareAnswerValidator → HTTP response
```

## Prior-art check

Minimum inspection found all required implementations already in
place: `QdrantEvidenceVectorIndex` (vector `find` + lexical
`find_lexical`, tenant-first filters), the `EmbeddingProvider`
protocol (no concrete implementation), `ScriptedLLMClient` only
(no vendor adapter), canonical env vars for Qdrant/LLM/embeddings,
and the `ApplicationServices`/`lifespan` lifecycle. No duplicate
Qdrant, embedding, configuration, or service abstraction was
created. One genuine gap — no `EmbeddingProvider` implementation
— was closed with the single approved-baseline (TB-6)
implementation rather than a second abstraction.

## Composition root

`xportra/infrastructure/rag_composition.py` (new) is the one
explicit composition root:

- `RAGInfrastructureConfig` — the single authoritative config
  path (`VECTOR_STORE_URL`, `VECTOR_STORE_COLLECTION`,
  `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` (new, documented in
  `environment-schema.md` + `.env.example`), `LLM_API_KEY`,
  `LLM_MODEL`; generation/prompt use domain/composition
  defaults). Missing/invalid values raise `RAGConfigurationError`
  (wrapping `LLMConfigurationError` where applicable). The secret
  holder (`LLMSettings`) is `field(repr=False)`-excluded from the
  repr.
- `SentenceTransformerEmbeddingProvider` — the single approved
  TB-6 baseline implementation. Lazy model load on first
  `embed()` (composition/import never download anything);
  fail-closed input/dimension validation; load failures surface
  as `VectorStoreError`; inference failures propagate to the
  existing retrieval failure translation. A `model_loader`
  callable seam keeps it deterministically testable.
- `compose_rag_stack(config, *, embedding_provider=None,
  llm_client)` — builds the graph from existing classes:
  `QdrantClient` → one `QdrantEvidenceVectorIndex` serving BOTH
  semantic and lexical paths → `VectorIndexEvidenceRetriever` →
  `build_evidence_retrieval_pipeline` →
  `build_evidence_context_pipeline` →
  `build_rag_application_service` (fail-closed validator
  default). Returns `RAGComposition(service, vector_index,
  embedding_provider, llm_client, config)` with an
  `ensure_collection()` lifecycle hook. Nothing is constructed
  per request; no policy is duplicated.
- `compose_rag_stack_from_environment(...)` — env-driven
  convenience.

## Dependency graph

```
RAGInfrastructureConfig.from_environment()
  QdrantClient(url) → QdrantEvidenceVectorIndex ─┬─ find (semantic)
    SentenceTransformerEmbeddingProvider (lazy) ─┘  find_lexical
  → VectorIndexEvidenceRetriever → ComposedHybridEvidenceRetriever
  → EvidenceRetrievalPipeline (DeterministicEvidenceRanker)
  → EvidenceContextPipeline (DeterministicContextSelector)
  → CitationAwarePromptBuilder → RAGApplicationService
  → CitationAwareAnswerValidator   (+ injected LLMClient)
```

## Infrastructure implementations selected

- Vector: existing `QdrantEvidenceVectorIndex` (unchanged).
  Existing tenant/scope protections stay authoritative; the API
  never touches Qdrant.
- Embeddings: new `SentenceTransformerEmbeddingProvider`
  (TB-6). Configured model must match the collection
  (`VectorIndexConfig.from_embedding_config` linkage);
  dimensions validated per call; no silent fallback model.
- Lexical: the same Qdrant index (`find_lexical`) — no second
  search system.

## LLM adapter status

No vendor adapter exists and none was introduced (§5: no
unreviewed SDK; `xportra/domain` stays SDK-free). `llm_client`
is a required explicit seam of the composition root
(`RAGConfigurationError` when absent); `ScriptedLLMClient`
remains test-only. Production LLM awaits a future reviewed
adapter that plugs into the unchanged `LLMClient` contract.

## Configuration path / lifecycle

`ApplicationServices.from_environment_with_rag(*, llm_client,
embedding_provider=None)` composes once per lifecycle;
`from_environment()` is unchanged (`rag=None` → 503 preserved).
The composition root is resolved lazily via `importlib` so
`xportra.api` keeps zero static imports of
`xportra.infrastructure` (the Phase 5.13 boundary guarantee —
a prior boundary test enforces this and still passes
unmodified). `ensure_collection()` is available for explicit
startup verification (creates/validates, fails clearly, never
exposes credentials). `pyproject.toml` now declares the
previously-undeclared-but-used `qdrant-client` plus the newly
used `sentence-transformers` (CD-12 compliance; declaration
only, no installs).

## Tenant isolation verification

Proven through real composition with deterministic fakes:
Tenant A retrieves only A evidence; Tenant B only B; body
`tenant_id` override → 422 with the index never called; scope
for another tenant's document yields empty (no bypass);
cross-tenant vector rows are rejected by the existing integrity
check (502); out-of-scope rows likewise; responses never carry
another tenant's identifiers. No second tenant-security
implementation was added.

## Failure behavior

Preserved end to end: vector failure → 502; embedding failure →
the existing retrieval translation (409, never success); LLM
failure → 502; validation failure → 422; missing/invalid config
→ `RAGConfigurationError` at startup/composition; empty LLM
output → 200 `empty`; no evidence → 200 valid empty-context
path. No broad catch-and-return anywhere.

## Observability

Existing `logging.getLogger(__name__)` convention; composition
logs collection/model identifiers only. Tests assert logs and
responses contain no keys, URLs with credentials, headers, or
tokens. No full evidence/answer logging was introduced.

## Deterministic integration test

`tests/unit/test_rag_composition.py` (46 tests): real
`RAGApplicationService` + real Phase 5 pipeline objects + fake
vector/embedding infra + `ScriptedLLMClient` + real validator,
exercised through HTTP — proving tenant preservation,
evidence→prompt→validation flow, validated citations,
provenance in the response, invalid-citation rejection, and
provider-failure semantics.

## Opt-in live smoke test

`tests/integration/test_rag_qdrant_smoke.py`: skipped unless
`QDRANT_URL` is set; throwaway uniquely-named collection,
deleted afterwards; no Docker, no production credentials.

## Explicitly deferred

Vendor LLM adapter (OpenRouter/TB-5), production LLM wiring,
model routing/failover/retries, semantic grounding, streaming,
agents/tools, background workers, API/auth redesign.

## Files created / modified

- Created: `xportra/infrastructure/rag_composition.py`,
  `tests/unit/test_rag_composition.py`,
  `tests/integration/test_rag_qdrant_smoke.py`,
  `docs/phases/phase-5-14-production-rag-composition.md`.
- Modified (additive): `xportra/infrastructure/__init__.py`
  (composition exports), `xportra/api/dependencies.py`
  (`from_environment_with_rag`), `pyproject.toml` (two
  declarations), `.env.example` + `environment-schema.md`
  (`EMBEDDING_DIMENSIONS`).
- No Phase 5.1–5.13 behavior file modified; no prior test
  touched (one prior boundary test initially flagged the new
  wiring import; the wiring was reworked to preserve the
  guaranteed layering instead of weakening the test).

## Verification

- Focused Phase 5.14: 46/46 passing.
- Phase 5.1–5.14 focused: 649/649 passing.
- Full suite: 1117 passed + 33 skipped (32 `DATABASE_URL` +
  1 `QDRANT_URL`-gated smoke), 0 failures, 0 errors.
- Import/export checks pass; domain purity CLEAN
  (no HTTP/provider/infrastructure imports); API layer
  constructs no infrastructure clients (AST-verified).
- Skipped: 32 PostgreSQL integration tests (`DATABASE_URL`
  unconfigured) and the opt-in Qdrant smoke test
  (`QDRANT_URL` unconfigured) — environment limitations.
- Unresolved: production LLM adapter selection/implementation;
  live Qdrant verification of the composed stack. Phase 5
  remains open pending the project's phase-completion
  decision.
