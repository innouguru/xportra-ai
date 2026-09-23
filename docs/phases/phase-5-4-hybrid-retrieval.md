# Phase 5.4 — Hybrid Retrieval Boundary

**Status:** Complete and verified (2026-09-22)
**Phase:** Phase 5 — Retrieval & RAG
**Type:** Retrieval composition boundary — semantic + lexical paths, no
ranking intelligence

> This record describes what was actually implemented and verified.

## Objective

Let Xportra retrieve evidence using both semantic similarity and exact
compliance terminology (``Form NXP``, ``HS code 1801``, ``SONCAP``,
``Section 4.2``, ``NAFDAC``) through one explicit, provider-independent
boundary — without adding a second search system, an LLM, a reranker, or
an invented ranking policy.

## Semantic retrieval path (Phase 5.1–5.3, unchanged)

```text
normalized query → EmbeddingProvider → query vector
    → EvidenceVectorIndex.find(vector, *, tenant_id, top_k, scope)
    → EvidenceRetrievalResult[]  (ordered, duplicate-collapsed)
```

`ComposedHybridEvidenceRetriever` in semantic mode delegates to the
injected Phase 5.1 `EvidenceRetriever` service verbatim — the vector
boundary was not replaced or bypassed, and the lexical index is never
called in this mode.

## Lexical retrieval path (new)

Contract: `EvidenceLexicalIndex.find_lexical(terms, *, tenant_id, top_k,
scope=None)` — provider-independent, receives already-normalized terms
(never raw text), returns complete `EvidenceRetrievalResult` values.

Deterministic lexical semantics (domain-owned, `evidence_hybrid.py`):

- **Tokenization**: maximal runs of alphanumeric characters
  (Unicode-aware, so accented letters survive), **lowercased**. All other
  characters — whitespace, punctuation, slashes, dots — are separators.
  No stemming, no stop-words, no fuzzy/synonym handling.
- **Case**: case-insensitive (both content and terms are lowercased).
- **Matching**: a chunk matches iff **every** query term occurs as a
  whole token in its content (AND). No partial-token, prefix, or
  substring matching: `SONCAPX` does not satisfy `soncap`, `18012` does
  not satisfy `1801`.
- **Empty lexical query**: a query whose normalized text has no
  alphanumeric term (e.g. `!!!`) is rejected with
  `DomainValidationError` for lexical and hybrid modes; semantic mode is
  unaffected.
- **Lexical relevance**: total query-term occurrences in the chunk
  content (a term-frequency measure — not comparable to semantic
  similarity; see score semantics).

Qdrant translation (infrastructure only): `scroll` with
`must = [tenant condition, …scope conditions, MatchText(content)]`. The
provider's full-text index can over-match (its tokenizer/prefix
behaviour), so the adapter **verifies every candidate against the
domain's exact whole-token rule** and narrows over-matches; the domain
rule — not provider tokenization — defines the results. A missing
collection returns an empty result, never an error.

## Hybrid composition

```text
                    ┌─ semantic retrieval (EvidenceRetriever) ─┐
normalized query ──┤                                            ├─ candidate union
                    └─ lexical retrieval (EvidenceLexicalIndex) ┘
```

`ComposedHybridEvidenceRetriever.retrieve_candidates(query, *,
tenant_id, mode, scope=None)` — `mode` is explicit and required
(`semantic` | `lexical` | `hybrid`, validated against `RETRIEVAL_MODES`);
there is no default and no silent inference. Candidate sets are bounded
by `top_k` per path, so the union contains at most `2 × top_k` entries
before deduplication. Because no valid fusion or ranking method exists at
this phase, the hybrid output is documented as a **deterministic
candidate set, not a global relevance ranking**.