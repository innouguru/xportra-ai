# Phase 5.6 — Retrieval Pipeline Orchestration

**Status:** Complete and verified (2026-09-23)
**Phase:** Phase 5 — Retrieval & RAG
**Type:** Application-facing orchestration boundary — composition only;
no LLM, no context selection, no answer generation

> This record describes what was actually implemented and verified.

## Objective

Give downstream Xportra components one clear retrieval entry point —
`retrieve(information_need, tenant_id=…, mode=…, scope=…, top_k=…)` —
so they never manually compose hybrid retrieval, scope, tenant context,
ranking, and top-k themselves.

```text
Information Need
      ↓
EvidenceRetrievalQuery (Phase 5.2 semantics)
      ↓
HybridEvidenceRetriever (Phase 5.4)
      ↓
HybridRetrievalCandidate[]
      ↓
EvidenceRanker (Phase 5.5)
      ↓
RankedEvidenceResult[]
```

This is an orchestration boundary only. No context-window construction,
no prompt generation, no compliance reasoning, no answer generation.

## Orchestration contract

`xportra/domain/evidence_pipeline.py`:

- `RetrievalPipeline` — runtime-checkable application-facing protocol;
  the name follows repository protocol conventions.
- `EvidenceRetrievalPipeline` — the concrete orchestrator.
- `build_evidence_retrieval_pipeline(...)` — smallest composition
  helper (below).

All three are exported from `xportra.domain`. No competing query, scope,
candidate, or result model was created: the pipeline constructs the
Phase 5.2 `EvidenceRetrievalQuery` (getting normalization semantics for
free), forwards the Phase 5.3 `EvidenceRetrievalScope` unchanged, and
returns Phase 5.5 `RankedEvidenceResult` values verbatim.

## Dependency composition

Both collaborators are injected explicitly; the pipeline never
constructs a Qdrant client, embedding provider, or infrastructure
adapter:

```text
EvidenceRetrievalPipeline
        ↓ HybridEvidenceRetriever   → EvidenceVectorIndex / lexical infra
        ↓ EvidenceRanker            → pure domain policy
```

Constructor validation is structural (callable `retrieve_candidates` /
`rank` methods required) and fails closed, keeping the pipeline testable
with fakes.

## Tenant propagation

`tenant_id` is a mandatory keyword accepted only as a
`TenantContext` (via the existing `require_tenant_context` convention)
and is forwarded **unchanged** to the hybrid retriever. Unscoped or
all-tenant retrieval cannot be expressed; the Phase 5.1/5.3 isolation
remains the only tenant mechanism — this layer adds no competing one
and triggers before any retriever call.

## Scope propagation

`scope` is forwarded unchanged (identity-preserved, tested with
`assertIs`): `None` keeps the Phase 5.3 meaning of tenant-only
retrieval; an empty scope remains tenant-scoped; a populated scope
reaches both retrieval branches through the Phase 5.4 composition. The
pipeline never reconstructs scope from dictionaries — a dict scope is
rejected fail-closed. Scope violations still fail closed inside the
Phase 5.4/5.3 defense-in-depth, which remains authoritative.

## Retrieval-mode behavior

`mode` is an explicit, required keyword — `semantic` | `lexical` |
`hybrid` — validated against the Phase 5.4 `RETRIEVAL_MODES` set before
any retriever call. There is no silent default (a call omitting `mode`
raises `TypeError`), so retrieval behavior is never ambiguous, and an
invalid mode (e.g. `"bm25"`) fails closed with `DomainValidationError`
without reaching the retriever. The three Phase 5.4 modes pass through
unchanged; mode semantics (embedding vs never-embedding vs both) remain
owned by Phase 5.4.

## Top-k ownership

Exactly ONE authoritative final top-k exists: the Phase 5.5 ranker's
post-ordering truncation, driven by the pipeline's `top_k` argument
(default `DEFAULT_TOP_K`). The candidate pool is a separate, explicit
knob:

- `candidate_pool` (default: `top_k`) becomes the per-path retrieval
  bound inside the Phase 5.4 query.
- The ranker therefore sees the full merged candidate set (up to
  2 × candidate_pool before Phase 5.2 duplicate collapse) and decides
  both the final order and the final cut.
- The pipeline never truncates before ranking and never multiplies
  top-k by a hidden constant; a caller wanting ranking to see more
  candidates passes a larger `candidate_pool` explicitly. The
  retrieve→rank→truncate anti-pattern is structurally avoided.

## Failure propagation

No broad exception handling: embedding, vector-store, lexical, and
ranking failures propagate unchanged from the responsible boundary
(tested with raised sentinels, identity-checked). The pipeline converts
nothing into an empty success — `[]` continues to mean exactly
"retrieval completed successfully and no evidence matched" (reached via
empty candidates from a successful retrieval, which flows through the
ranker and returns `[]`).

## Result integrity

The pipeline is not a transformation boundary: ranked results are
returned exactly as the ranker produced them — same objects (identity
asserted), same order, same `rank_position`, scores, retrieval-source
provenance, and `ranking_key`. Evidence identity, chunk identity,
document identity/version, source identity, tenant identity, content,
and content fingerprint all survive untouched. The only added check is
structural defense-in-depth on the injected ranker's output (a
malformed ranker response fails closed instead of leaking downstream) —
mirroring how Phase 5.4 re-validates provider results.

## Purity

The pipeline performs no LLM call, no direct embedding call, no direct
Qdrant call, no lexical matching, no score computation, no mutation of
dependency results (candidates and canned retriever output are asserted
unchanged), and no compliance decisions. An AST test verifies the
module imports only `typing`/`__future__` plus intra-domain code — no
`qdrant_client`, HTTP, or SDK import is possible.

## Convenience wiring

`build_evidence_retrieval_pipeline(*, semantic_retriever,
lexical_index, ranker=None)` composes the Phase 5.4
`ComposedHybridEvidenceRetriever` (which validates its own
dependencies) with the Phase 5.5 `DeterministicEvidenceRanker` (the
default when `ranker` is omitted — the documented initial policy, not a
hidden alternative). It is a construction boundary only: no
dependency-injection framework, no application startup wiring (no
existing application boundary needs one yet).

## Intentionally deferred

Context selection / context-window construction, prompt generation,
compliance reasoning, answer generation, citation generation, conversational
memory, and agentic retrieval remain unimplemented. The pipeline hands
`RankedEvidenceResult[]` to whatever downstream component those phases
define. Phase 5 is not complete; Phase 5.7 has not started.

## Implementation

- `xportra/domain/evidence_pipeline.py` (new): `RetrievalPipeline`
  protocol, `EvidenceRetrievalPipeline`,
  `build_evidence_retrieval_pipeline`.
- `xportra/domain/__init__.py`: three pipeline symbols exported.
- `tests/unit/test_evidence_pipeline.py`: 39 focused tests (fakes only).

## Verification

- Focused Phase 5.6: **39/39** (fakes only — no live Qdrant, no
  embeddings, no network).
- Phase 5.1–5.5 focused re-runs: **251/251** (56 + 40 + 41 + 58 + 56),
  no regressions.
- Complete `tests/` tree: **758 passed, 32 skipped** (719 + 39;
  PostgreSQL integration suites skip without `DATABASE_URL`, as in
  every prior phase).
- Import check: `EvidenceRetrievalPipeline`, `RetrievalPipeline`,
  `build_evidence_retrieval_pipeline` resolvable from `xportra.domain`.
