# Phase 5.7 — Budget-Aware Context Selection

**Status:** Complete and verified (2026-09-23)
**Phase:** Phase 5 — Retrieval & RAG
**Type:** Domain context-selection boundary — deterministic budgeted
selection only; no LLM, no prompt generation, no tokenizer
infrastructure

> This record describes what was actually implemented and verified.

## Objective

Establish the domain boundary that converts already-ranked evidence
into the deterministic subset selected for downstream LLM context under
an explicit budget:

```text
Information Need
      ↓
RetrievalPipeline (Phase 5.6)
      ↓
RankedEvidenceResult[]   (Phase 5.5 rank order)
      ↓
ContextSelector (this phase)
      ↓
EvidenceContextSelection (SelectedEvidence[] + auditable accounting)
```

Context selection only — no prompt generation, no answer generation,
no compliance reasoning, no retrieval, no ranking.

## Architectural position

`xportra/domain/evidence_context.py` consumes the Phase 5.5
`RankedEvidenceResult[]` exactly as the Phase 5.6 pipeline produces it.
It never retrieves, ranks, rescores, reorders, deduplicates, or
balances sources. No Phase 5.1–5.6 contract was modified.

## Input / output contracts

**Input:** `select(ranked, *, tenant_id, budget)` —
`list[RankedEvidenceResult]` in ascending rank order, a mandatory
`TenantContext`, and an `EvidenceContextBudget`.

**Output:** `EvidenceContextSelection` (frozen) exposing:

- `budget` — the `EvidenceContextBudget` used;
- `selected_items` — tuple of `SelectedEvidence` in rank order;
- `used_budget` — sum of selected content characters;
- `remaining_budget` — property, `budget − used`;
- `skipped_rank_positions` — rank positions of items skipped for
  exceeding the remaining budget (the explicit, auditable trace of
  rank gaps);
- `to_record()` — structured, JSON-serializable selection provenance.

`SelectedEvidence` is a thin frozen wrapper carried **by reference**:
`rank_position`, the original `RankedEvidenceResult` (whose
`EvidenceRetrievalResult` preserves tenant, chunk, document, version,
chunk index, source id/type/location, content, fingerprint, embedding
model/dimensions, scores, retrieval sources, and ranking key), and the
item's `character_count`. No second evidence representation exists.

## Budget semantics

`EvidenceContextBudget(max_characters: int)` — a frozen, explicit,
strictly validated value object.

- **Accounting rule (exact, no off-by-one ambiguity):** the budget
  bounds the **sum of `len(content)` over selected evidence items
  only**. Separators, provenance labels, formatting wrappers, and
  prompt scaffolding are NOT counted — the domain selector owns the
  evidence payload only; final prompt formatting is a later boundary.
- **Approximation disclaimer:** this is a deterministic
  character-based approximation of an LLM context window, NOT an exact
  token count. Model-specific token accounting requires a tokenizer
  and is deliberately deferred to a later boundary. No tokenizer
  dependency was introduced.
- **Validation (fail-closed, `DomainValidationError`):** zero,
  negative, boolean, float, string, and `None` are all rejected; only
  positive integers are accepted.

## Selection algorithm

Greedy, single pass, in the given (rank) order:

1. Validate budget and every result (integrity + tenant, below).
2. Walk results in input order — the Phase 5.5 rank order.
3. Include an item iff `used + len(content) <= max_characters`.
4. If an item exceeds the remaining budget: skip it, record its rank
   position in `skipped_rank_positions`, continue with later items.
5. Stop at the end of input.

Determinism: identical inputs always produce an identical selection
(test-proven across repeated runs). No second relevance calculation,
no new score, no semantic or lexical computation, no LLM.

## Oversized-item policy

Two distinct cases, both explicitly designed:

1. **Item larger than the TOTAL budget** → fail-closed
   `DomainValidationError`. Rationale: such an item can never fit
   under any usage, production chunking bounds content at 1200
   characters (`MAX_CHUNK_CHARACTERS`, Phase 4.2), so hitting this
   path indicates a misused budget or corrupt evidence rather than a
   normal selection condition — silently skipping it could hide
   corruption. The selector does NOT continue past this error; the
   caller must fix the budget or the evidence.
2. **Item larger than the REMAINING budget** (but within total) →
   deterministic skip, selection CONTINUES with later smaller items,
   producing a rank gap recorded in `skipped_rank_positions`.

The final context CAN be empty: empty input, or all items skipped, are
both valid successful outcomes with zero usage. Provenance remains
intact for every included item (carried by reference); skipped items
are traceable by rank position.

## Ordering guarantees

Selected results retain the original ranking order, gaps included:
ranks 1, 3, 4 remain 1, 3, 4. The selector never sorts independently
(rank positions must be strictly ascending in input order; a violation
is rejected), never introduces diversity/source/document balancing,
and performs no deduplication — those are separate future policy
decisions.

## Provenance guarantees

Every `SelectedEvidence` preserves, by reference: tenant identity,
chunk identity, document identity/version, chunk index, source
identity/type/location, original content, content fingerprint,
embedding model/dimensions, original retrieval/ranking information
(both scores, retrieval sources, ranking key), and rank position.
Tests assert reference identity (`assertIs`) and field equality.

## Tenant guarantees

`tenant_id` is mandatory (`require_tenant_context` convention) and
every item's tenant is re-validated per result — the ranked-result
contract structurally guarantees tenant identity; the selector
preserves and revalidates it rather than introducing a second
mechanism. A mismatch fails closed. No all-tenant or optional-tenant
semantics exist.

## Failure behavior

Fail closed via `DomainValidationError`: malformed ranked input
(non-sequence, non-`RankedEvidenceResult` items), malformed/empty
content, duplicate chunk identity, non-positive/non-ascending rank
positions, cross-tenant results, items exceeding the total budget,
and invalid budgets (non-`EvidenceContextBudget`, or a rejected
`max_characters`). Nothing is silently repaired, dropped, or
truncated.

## Purity / dependency boundary

Pure domain logic: no Qdrant, HTTP, embedding, LLM, tokenizer, or
database access; no infrastructure SDK imports (AST-verified in
tests); no mutation of inputs or global state; no compliance
decisions, answers, or prompts. No dependency injection is needed —
the selector has no collaborators.

## Intentionally deferred

- Tokenizer-based (exact token) budgeting — model-specific, belongs
  to a later boundary once an LLM integration justifies the
  dependency.
- Prompt formatting and wrappers (separator/label accounting).
- Diversity, source/document balancing, and deduplication policies.
- Prompt generation, answer generation, compliance reasoning, API
  exposure, async orchestration (Phase 5.8+ / later phases).

## Implementation

- `xportra/domain/evidence_context.py` (new):
  `EvidenceContextBudget`, `SelectedEvidence`,
  `EvidenceContextSelection`, `ContextSelector` protocol,
  `DeterministicContextSelector`.
- `xportra/domain/__init__.py`: five new symbols exported.
- `tests/unit/test_evidence_context.py`: 45 focused tests (fakes only).

## Verification

- Focused Phase 5.7: **45/45** (no live Qdrant, no embeddings, no LLM,
  no tokenizer).
- Phase 5.1–5.6 focused re-runs: **251/251** (56+40+41+58+56+39) plus
  Phase 5.7's 45 → **296/296** across all Phase 5 focused suites;
  complete tree: **803 passed, 32 skipped** (719 + 39 + 45; PostgreSQL
  integration suites skip without `DATABASE_URL`, as in every prior
  phase — no failures).
- Import check: `EvidenceContextBudget`, `SelectedEvidence`,
  `EvidenceContextSelection`, `ContextSelector`,
  `DeterministicContextSelector` all resolvable from `xportra.domain`.
- No Phase 5.1–5.6 file was modified; no prior test weakened.

Phase 5 is not marked complete; Phase 5.8 has not started.
