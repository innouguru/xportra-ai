# Phase 5.8 — Retrieval-to-Context Pipeline Composition

**Status:** Complete and verified (2026-09-23)
**Phase:** Phase 5 — Retrieval & RAG
**Type:** Domain orchestration boundary — composition only; no LLM,
no prompt generation, no API exposure, no new retrieval, ranking, or
selection behavior

> This record describes what was actually implemented and verified.

## Objective

Compose the already-completed retrieval pipeline (Phase 5.6) and the
context-selection boundary (Phase 5.7) into one application-facing
orchestration contract:

```text
information need
      ↓
RetrievalPipeline   (Phase 5.6: retrieval + ranking)
      ↓
RankedEvidenceResult[]
      ↓
ContextSelector     (Phase 5.7: budgeted selection)
      ↓
EvidenceContextSelection
```

Composition only. This phase explicitly does NOT include: API
exposure, async facades, prompt construction or formatting, LLM
generation, compliance reasoning, tokenizer infrastructure, or any
new retrieval, ranking, or context-selection algorithm.

## Architectural position

`xportra/domain/evidence_context_pipeline.py` is the second
application-facing orchestration entry point, after the Phase 5.6
`EvidenceRetrievalPipeline`. It composes two injected collaborators
and owns nothing of their behavior — no retrieval, no ranking, no
deduplication, no scope handling, no tenant-isolation mechanism, no
budget arithmetic, no oversized-item policy, no truncation.

## Input / output contract

```python
EvidenceContextPipeline.select_context(
    information_need,
    *,
    tenant_id,            # mandatory (require_tenant_context)
    mode,                 # "semantic" | "lexical" | "hybrid", forwarded
    context_budget,       # EvidenceContextBudget (Phase 5.7 value object)
    scope=None,           # EvidenceRetrievalScope | None, forwarded unchanged
    top_k=DEFAULT_TOP_K,  # final ranked-result count, forwarded
    candidate_pool=None,  # per-path retrieval bound, forwarded
) -> EvidenceContextSelection
```

A `EvidenceContextPipelineContract` runtime-checkable protocol
documents the shape for future implementations (e.g., an async facade
behind the same boundary, if ever justified).

## Collaborators & dependency injection

Both collaborators are injected explicitly:

- `RetrievalPipeline` (Phase 5.6) — the authoritative retrieval +
  ranking boundary;
- `ContextSelector` (Phase 5.7) — the authoritative budgeted
  selection boundary.

The orchestrator never constructs a hybrid retriever, a ranker, an
embedding provider, a Qdrant client, or any infrastructure adapter.
Construction validation is fail-closed (`DomainValidationError` when a
collaborator is missing, a string/bytes placeholder, or lacks the
required callable — `retrieve` / `select`). No DI framework; no
application startup wiring.

A minimal construction helper,
`build_evidence_context_pipeline(semantic_retriever, lexical_index,
ranker=None, context_selector=None)`, wires the concrete stack via
the Phase 5.6 `build_evidence_retrieval_pipeline` factory and the
Phase 5.7 `DeterministicContextSelector` default — construction
consistency only, no new wiring semantics.

## Retrieval delegation

`retrieve(...)` is forwarded unchanged: information need, tenant,
mode, scope, `top_k`, and `candidate_pool` all reach the Phase 5.6
pipeline untouched. The orchestrator never calls
`ComposedHybridEvidenceRetriever` or `EvidenceRanker` directly, never
performs retrieval itself, and never truncates ranked results before
the selector. Mode validation and duplicate/scope semantics remain
owned by the lower boundaries — invalid modes are forwarded and their
rejection propagates, never silently converted.

## Context-selection delegation

Ranked results are passed to the selector **unchanged** — same
objects, same order, same provenance — together with the caller's
`EvidenceContextBudget`. Phase 5.7 remains the single authority for
budget accounting, oversized-item policy, skipped rank positions, and
selection order. The orchestrator performs no budget arithmetic, no
pre-filtering, no content truncation, no token estimation, and never
inspects individual evidence scores.

## Tenant / scope propagation

`tenant_id` is a mandatory keyword at this API boundary
(`require_tenant_context`), so unscoped retrieval cannot even be
expressed here; the established Phase 5.1/5.3/5.6/5.7 validation
remains the only isolation mechanism — no second one was created.
`scope` is forwarded unchanged with object identity preserved
(test-proven via `assertIs`).

## Result integrity

The `EvidenceContextSelection` returned is the **exact object**
produced by the injected selector (test-proven via `assertIs`): no
reconstruction, no field stripping, no re-ranking, no competing
revalidation. The full provenance chain survives the complete path —
tenant, chunk/document/version identity, chunk index, source
id/type/location, content, content fingerprint, embedding
model/dimensions, both scores, retrieval sources, rank position, and
ranking key — because every layer carries the original objects by
reference. The only added check is structural defense-in-depth on the
retrieval pipeline's output (malformed list or non-`RankedEvidenceResult`
items fail closed), mirroring the Phase 5.6 pattern.

## Empty behavior

A successful empty ranked set flows to the selector unchanged and
returns its established successful empty `EvidenceContextSelection`
(zero usage). The orchestrator converts it into neither an error nor a
fabricated result. Empty success stays distinct from operational or
integrity failure.

## Failure semantics

Fail-closed with no broad exception handling: retrieval failures
(including arbitrary `RuntimeError`/`KeyError` integrity failures)
and context-selection failures propagate **unchanged** — test-proven
via exception-identity assertions. Failures are never converted into
an empty successful selection; the selector is never invoked after a
retrieval failure, and validation failures (`None` tenant, non-string
information need, non-budget object, malformed retrieval output) fail
closed before any collaborator runs.

## Purity / dependency boundary

Pure domain orchestration, AST-verified in tests: the module imports
only its own sibling domain modules plus stdlib `typing`/`__future__`
— no `qdrant_client`, HTTP, embedding, tokenizer, LLM, or database
SDK. No network I/O, no LLM calls, no mutation of input evidence or
global state, no compliance decisions, no prompts, no answers. The
complete composition runs against in-memory fakes only.

## Intentionally deferred

- API exposure and async facades (the protocol allows a future async
  implementation behind the same contract).
- Prompt construction and formatting (a later boundary; the Phase 5.7
  budget counts evidence content only).
- LLM generation, compliance reasoning, and answer generation.
- Any learned reranking or alternative selection policy (both remain
  replaceable behind the injected protocols without changing this
  composition).

## Implementation

- `xportra/domain/evidence_context_pipeline.py` (new):
  `EvidenceContextPipelineContract`, `EvidenceContextPipeline`,
  `build_evidence_context_pipeline`.
- `xportra/domain/__init__.py`: three new symbols exported.
- `tests/unit/test_evidence_context_pipeline.py`: 41 focused tests
  (fakes only).

## Verification

- Focused Phase 5.8: **41/41** (no live Qdrant, no embeddings, no
  LLM, no network).
- Phase 5.1–5.7 focused re-runs and complete tree: see
  `CURRENT_STATE.md`.
- Import check: `EvidenceContextPipeline`,
  `EvidenceContextPipelineContract`, `build_evidence_context_pipeline`
  all resolvable from `xportra.domain`.
- No Phase 5.1–5.7 file was modified; no prior test weakened.

Phase 5 is not marked complete; no Phase 5.9 exists in the phase plan.
