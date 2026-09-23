# Phase 5.5 — Retrieval Ranking & Reranking

**Status:** Complete and verified (2026-09-23)
**Phase:** Phase 5 — Retrieval & RAG
**Type:** Deterministic ranking boundary — no LLM, no learned reranker,
no cross-encoder, no score fusion, no compliance reasoning

> This record describes what was actually implemented and verified.

## Objective

Take the Phase 5.4 `HybridRetrievalCandidate[]` — a candidate set that is
deliberately **not** a global relevance ranking — and produce a
deterministic, explainable ordered evidence set for downstream context
selection, without introducing an LLM, a learned reranker, or score
fusion.

```text
Phase 5.4:  retrieval → find plausible candidates
Phase 5.5:  ranking   → order candidates for downstream context selection
```

A high-ranked chunk means only: *this candidate is ranked higher for
retrieval purposes under the defined ranking policy.* It does **not**
mean the evidence is legally authoritative or proves a compliance
requirement.

## Boundary

```text
HybridRetrievalCandidate[]
        ↓
EvidenceRanker          (domain protocol, provider-independent)
        ↓
RankedEvidenceResult[]
```

`xportra/domain/evidence_ranking.py` introduces three symbols, exported
from `xportra.domain`:

- `EvidenceRanker` — runtime-checkable protocol; the replaceable
  provider-independent ranking contract. It knows nothing about Qdrant,
  HTTP, embeddings, or database ranking functions, so a later
  implementation can substitute a cross-encoder or learned reranker
  without changing the retrieval boundary.
- `DeterministicEvidenceRanker` — the initial concrete policy below.
- `RankedEvidenceResult` — a thin frozen value object: `rank_position`
  (1-based, explicit for auditability), the unchanged Phase 5.1
  `EvidenceRetrievalResult` carried **by reference** (no second evidence
  representation), the candidate's `semantic_score`,
  `lexical_score`, and `retrieval_sources`, plus a structured
  `ranking_key` — the explicit sort tuple that determined the position.

`ranking_key` is structured ranking provenance, not explanation
generation: `(provenance_tier, −semantic_score, −lexical_score,
chunk_id)`. Downstream components can see exactly which inputs decided
each position.

## Ranking policy (and why it is valid)

The initial policy is deterministic and explainable. Precedent order:

1. **Provenance tier** (higher first):
   `{"semantic", "lexical"}` > `{"semantic"}` > `{"lexical"}`. This is
   an informational signal — two independent retrieval mechanisms agreed
   on this chunk — **not** a score combination.
2. Within a tier carrying a semantic score: **descending semantic
   score**.
3. Within equal semantic scores: **descending lexical score**.
4. Remaining ties: **ascending `chunk_id`** (canonical evidence
   identity).

**Why no score fusion.** The Phase 5.4 score contracts are not
comparable: the semantic score is a model similarity value from the
Phase 5.1 vector path; the lexical score is a domain-computed
term-frequency count (Phase 5.4 explicitly documents it as "not
comparable to semantic similarity"). Neither carries a normalization
guarantee, so any addition, weighting, or normalization (`semantic_score
+ lexical_score`, RRF, weighted fusion) would be an unjustified
invention pretending two different scales are one. The policy therefore
preserves both signals untouched and orders by explicit provenance plus
within-tier score comparisons, which each have a well-defined meaning.
If a future normalization is ever justified, it must be an explicit,
reviewed policy change — not an accidental side effect.

**No compliance semantics.** The policy never uses source type, source
reputation, jurisdiction, document age, presumed regulatory importance,
commodity importance, or any legal-authority assumption. No assumption
such as "regulation > guidance" is encoded; the repository contains no
canonical domain authority model that would justify one. The ranker
ranks retrieval relevance, not legal authority.

## Tie-breaking

Explicit, stable, canonical: ascending `chunk_id`. The ranker relies on
no set/dict iteration order, provider ordering, object memory identity,
or implicit collection order. Sorting uses only the explicit key tuple.
Repeated ranking of the same candidate set — in any input order —
always produces the identical output order; this is verified by test.

## Top-k semantics

Final top-k is applied at the ranking layer **after** ordering. The
ranker sees the full Phase 5.4 candidate pool — in hybrid mode the
union of two per-path `top_k`-bounded lists (up to `2 × top_k` before
Phase 5.2 duplicate collapse) — and decides the final order; only then
is the pool truncated to the final `top_k`. The retrieval candidate
count and the final ranked result count are distinct, explicit values;
no candidate is truncated before ranking and no arbitrary pool
multiplier is introduced (the `2 ×` bound is Phase 5.4's existing
two-path structure, not a new constant). Because the ranker takes an
explicit `top_k` keyword, a caller may also request more or fewer final
results than either path's retrieval count.

## Provenance preservation

Ranking changes **order**, not evidence identity. Every
`RankedEvidenceResult` carries, unchanged: evidence identity, chunk
identity, document identity, document version, source identity and
type, content, content fingerprint, tenant identity, semantic score
(where available), lexical score (where available), and retrieval
source(s). Tests prove the wrapped evidence is the same object, not a
copy, and that candidate fields are never mutated.

## Invalid / edge inputs (fail closed)

- Empty candidate list → `[]` (no error).
- Single candidate → one result at rank 1.
- Tuple input is accepted (sequence); non-list/tuple argument rejected.
- Duplicate chunk identities → `DomainValidationError`. Phase 5.4's
  union guarantees unique `chunk_id`s (merge by `chunk_id`, then Phase
  5.2 duplicate collapse by document+fingerprint — which may legitimately
  collapse *different* chunks of one document). A duplicate identity
  reaching the ranker is therefore an integrity violation, not valid
  input; it is rejected rather than silently ranked. (A distinct
  document+fingerprint duplicate inside one input list would equally
  be rejected — dedup is a retrieval concern the ranker does not
  silently redo.)
- Missing semantic or lexical score → ordering still works within the
  candidate's tier using the remaining score and the tie-break; the
  score stays `None` on the result.
- Both scores missing, invalid score types (bool, str), non-finite
  scores (NaN/inf) → rejected.
- Source/score inconsistency (score present without its source label or
  vice versa), non-frozenset sources, unsupported source labels →
  rejected.
- Invalid top-k (zero, negative, bool, float, string, `None`) →
  `DomainValidationError`.

All rejections raise `DomainValidationError` per the established
convention; malformed input is never silently converted into valid
input. Where `HybridRetrievalCandidate.__post_init__` already enforces
the Phase 5.4 invariant at construction, the ranker re-checks it as
defense in depth (guards against bypasses and gives the ranker its own
explicit contract) rather than re-deriving every Phase 5.4 rule.

## Purity

The ranker performs no network call, no Qdrant/embedding/LLM call, no
persistence, and no mutation of candidate objects, provenance, or
scores. It takes candidates and returns ranked results, making the
policy testable, deterministic, replaceable, and auditable. Tests
verify by AST inspection that the module imports nothing beyond stdlib
and intra-domain code, and that no candidate field changes across a
ranking call.

## Implementation

- `xportra/domain/evidence_ranking.py`: `RankedEvidenceResult`,
  `EvidenceRanker` protocol, `DeterministicEvidenceRanker`,
  provenance-tier constants (`PROVENANCE_BOTH`,
  `PROVENANCE_SEMANTIC_ONLY`, `PROVENANCE_LEXICAL_ONLY`), validation,
  and the explicit sort/ranking key.
- `xportra/domain/__init__.py`: ranking symbols exported alongside the
  retrieval symbols (unchanged otherwise).
- `tests/unit/test_evidence_ranking.py`: 56 focused tests.

## Verification

- Focused Phase 5.5: **56/56** (fakes only — no live Qdrant, no
  embeddings, no network).
- Phase 5.1 re-run: 56/56; Phase 5.2: 40/40; Phase 5.3: 41/41;
  Phase 5.4: 58/58 (195 focused, no regressions).
- Full unit suite: **719/719** (663 + 56), 0 failures; complete
  `tests/` tree 719 passed + 32 skipped (PostgreSQL integration suites
  skip without `DATABASE_URL`, as in every prior phase).
- Import check: `DeterministicEvidenceRanker`, `EvidenceRanker`,
  `RankedEvidenceResult` resolvable from `xportra.domain`.

No LLM, prompt, answer generation, compliance reasoning, citation
generation, agentic retrieval, conversational memory, query
classification, cross-encoder, or learned reranker was introduced.
Phase 5 is not complete; Phase 5.6 has not started.
