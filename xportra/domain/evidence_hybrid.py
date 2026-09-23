"""Hybrid retrieval boundary for Phase 5.4.

Retrieval infrastructure only. Composes the Phase 5.1–5.3 semantic path
(``EvidenceRetriever`` → ``EmbeddingProvider`` → ``EvidenceVectorIndex``)
with a provider-independent lexical path (``EvidenceLexicalIndex``) so
evidence can be found both semantically and by exact compliance terms
(``Form NXP``, ``HS code 1801``, ``SONCAP``, ``Section 4.2``, ``NAFDAC``).

Semantic similarity scores and lexical relevance are NOT comparable:
this module never adds, weights, or fuses them. Each per-path score is
preserved separately on an explicit candidate representation, so a later
phase can perform ranking or reranking. No LLM query rewriting, no
generated search terms, no reranking model, no query classification, and
no answer generation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from .errors import (
    DomainValidationError,
    VectorStoreError,
    require_tenant_context,
)
from .evidence_retrieval import (
    EvidenceRetrievalQuery,
    EvidenceRetrievalResult,
    EvidenceRetrievalScope,
    evidence_duplicate_key,
)

RETRIEVAL_MODES = frozenset({"semantic", "lexical", "hybrid"})
RETRIEVAL_SOURCES = frozenset({"semantic", "lexical"})


def lexical_tokens(text: str) -> tuple[str, ...]:
    """Deterministic lexical tokenization (raw, order-preserving).

    Tokens are maximal runs of alphanumeric characters (Unicode-aware:
    accented letters are kept), lowercased. Whitespace and all other
    punctuation are separators — so ``HS code 1801.`` tokenizes to
    ``hs``, ``code``, ``1801``. No stemming, no stop-word removal, no
    fuzzy or synonym handling.
    """
    tokens: list[str] = []
    current: list[str] = []
    for char in text:
        if char.isalnum():
            current.append(char.lower())
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tuple(tokens)


def lexical_terms(text: str) -> tuple[str, ...]:
    """Query terms: tokens, deduplicated in first-occurrence order."""
    terms: list[str] = []
    seen: set[str] = set()
    for token in lexical_tokens(text):
        if token in seen:
            continue
        seen.add(token)
        terms.append(token)
    return tuple(terms)


def lexical_matches(content: str, terms: tuple[str, ...]) -> bool:
    """Exact whole-token AND match: every term must occur as a token.

    No partial-token, prefix, fuzzy, or substring matching: ``SONCAPX``
    does not satisfy the term ``soncap``.
    """
    if not terms:
        return False
    present = set(lexical_tokens(content))
    return all(term in present for term in terms)


def lexical_relevance_score(
    content: str, terms: tuple[str, ...]
) -> float:
    """Deterministic lexical relevance: total query-term occurrences.

    This measures term frequency only — it is NOT comparable to a
    semantic similarity score and is never fused with one. Phase 5.4
    preserves it for later ranking phases.
    """
    if not terms:
        return 0.0
    counts: dict[str, int] = {}
    for token in lexical_tokens(content):
        counts[token] = counts.get(token, 0) + 1
    return float(sum(counts.get(term, 0) for term in terms))


@runtime_checkable
class EvidenceLexicalIndex(Protocol):
    """Provider-independent lexical retrieval boundary.

    ``terms`` are already-normalized lexical terms (see
    ``lexical_terms``): lowercase alphanumeric tokens, deduplicated,
    non-empty. Implementations must apply the mandatory tenant
    condition, the optional Phase 5.3 scope, and the exact whole-token
    match rule; they must return at most ``top_k`` complete
    ``EvidenceRetrievalResult`` values whose ``score`` is the
    deterministic lexical relevance, ordered by lexical relevance
    descending then ``chunk_id`` ascending. Raw query text is never
    accepted here and no provider-specific type crosses this boundary.
    """

    def find_lexical(
        self,
        terms: tuple[str, ...],
        *,
        tenant_id: Any,
        top_k: int,
        scope: EvidenceRetrievalScope | None = None,
    ) -> list[EvidenceRetrievalResult]:
        ...


@dataclass(frozen=True, slots=True)
class HybridRetrievalCandidate:
    """One evidence candidate with explicit per-path retrieval provenance.

    ``evidence`` is the existing Phase 5.1 result model (never a copy or
    a competing payload model); ``retrieval_sources`` states which
    mechanisms produced this candidate. The two scores are preserved
    separately and are deliberately NOT fused: no combined, weighted, or
    normalized score is produced by this phase.
    """

    evidence: EvidenceRetrievalResult
    semantic_score: float | None
    lexical_score: float | None
    retrieval_sources: frozenset[str]

    def __post_init__(self) -> None:
        if not isinstance(self.evidence, EvidenceRetrievalResult):
            raise DomainValidationError("evidence result is malformed")
        for name in ("semantic_score", "lexical_score"):
            value = getattr(self, name)
            if value is None:
                continue
            if (isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)):
                raise DomainValidationError(f"{name} is malformed")
        sources = self.retrieval_sources
        if isinstance(sources, set):
            sources = frozenset(sources)
            object.__setattr__(self, "retrieval_sources", sources)
        if (not isinstance(sources, frozenset) or not sources
                or not sources <= RETRIEVAL_SOURCES):
            raise DomainValidationError(
                "retrieval sources are malformed")
        if ("semantic" in sources) != (self.semantic_score is not None):
            raise DomainValidationError(
                "semantic provenance is inconsistent")
        if ("lexical" in sources) != (self.lexical_score is not None):
            raise DomainValidationError(
                "lexical provenance is inconsistent")

    @property
    def is_hybrid(self) -> bool:
        """True when both retrieval mechanisms produced this candidate."""
        return len(self.retrieval_sources) == len(RETRIEVAL_SOURCES)

    def source_labels(self) -> tuple[str, ...]:
        """Deterministic, sorted source labels for reporting."""
        return tuple(sorted(self.retrieval_sources))


@runtime_checkable
class HybridEvidenceRetriever(Protocol):
    """Hybrid retrieval contract over the Phase 5.1–5.3 invariants.

    ``mode`` is explicit (no default) — ``semantic``, ``lexical``, or
    ``hybrid``. Tenant scope remains a required keyword, ``scope``
    carries the Phase 5.3 metadata restrictions, normalization and top-k
    come from the Phase 5.2 ``EvidenceRetrievalQuery``, and every
    returned candidate preserves complete Phase 5.1 evidence provenance.
    """

    def retrieve_candidates(
        self,
        query: EvidenceRetrievalQuery,
        *,
        tenant_id: Any,
        mode: str,
        scope: EvidenceRetrievalScope | None = None,
    ) -> list[HybridRetrievalCandidate]:
        ...


class ComposedHybridEvidenceRetriever:
    """Compose the semantic and lexical paths into a candidate set.

    Modes (explicit, never inferred):

    - ``semantic`` — delegates to the injected Phase 5.1
      ``EvidenceRetriever`` unchanged (embedding → vector search); the
      lexical index is never called.
    - ``lexical`` — ``EvidenceLexicalIndex.find_lexical`` over terms
      derived from the normalized query text; no embedding call at all.
    - ``hybrid`` — both branches run; a chunk returned by both is merged
      by its canonical ``chunk_id``, preserving both scores and both
      source labels.

    Ordering is deterministic but explicitly NOT a global relevance
    ranking: candidates are grouped by available semantic score, then
    lexical score, then ``chunk_id`` — no weighting, normalization, or
    score addition. The Phase 5.2 duplicate rule (document + content
    fingerprint) is then applied, so the union never returns the same
    evidence twice and never collapses provenance-distinct documents or
    versions.

    Fail closed, with NO degraded mode: if either branch fails in hybrid
    mode the call raises (``VectorStoreError`` for the lexical branch,
    the semantic retriever's own error otherwise) — partial retrieval is
    never returned as if it were complete. Tenant and scope invariants
    are re-checked on every result from both branches.
    """

    def __init__(
        self,
        *,
        semantic_retriever: EvidenceRetriever,
        lexical_index: EvidenceLexicalIndex,
    ) -> None:
        if semantic_retriever is None or not callable(
            getattr(semantic_retriever, "retrieve", None)
        ):
            raise DomainValidationError(
                "a semantic evidence retriever is required")
        if (
            lexical_index is None
            or isinstance(lexical_index, (str, bytes))
            or not callable(getattr(lexical_index, "find_lexical", None))
        ):
            raise DomainValidationError(
                "an evidence lexical index is required")
        self._semantic = semantic_retriever
        self._lexical = lexical_index

    def retrieve_candidates(
        self,
        query: EvidenceRetrievalQuery,
        *,
        tenant_id: Any,
        mode: str,
        scope: EvidenceRetrievalScope | None = None,
    ) -> list[HybridRetrievalCandidate]:
        """Run the requested mode and return explicit candidates."""
        require_tenant_context(tenant_id)
        if not isinstance(query, EvidenceRetrievalQuery):
            raise DomainValidationError(
                "an evidence retrieval query is required")
        if mode not in RETRIEVAL_MODES:
            raise DomainValidationError("unsupported retrieval mode")
        if scope is None:
            scope = EvidenceRetrievalScope()
        elif not isinstance(scope, EvidenceRetrievalScope):
            raise DomainValidationError(
                "an evidence retrieval scope is required")
        terms: tuple[str, ...] = ()
        if mode in ("lexical", "hybrid"):
            terms = lexical_terms(query.text)
            if not terms:
                raise DomainValidationError(
                    "lexical query contains no searchable terms")
        semantic_results: list[EvidenceRetrievalResult] = []
        lexical_results: list[EvidenceRetrievalResult] = []
        if mode in ("semantic", "hybrid"):
            semantic_results = self._validate_results(
                self._semantic.retrieve(
                    query, tenant_id=tenant_id, scope=scope),
                tenant_id, scope, "semantic path")
        if mode in ("lexical", "hybrid"):
            try:
                raw_lexical = self._lexical.find_lexical(
                    terms,
                    tenant_id=tenant_id,
                    top_k=query.top_k,
                    scope=scope,
                )
            except Exception as exc:
                raise VectorStoreError(
                    "hybrid evidence retrieval (lexical path)",
                    exc,
                ) from exc
            lexical_results = self._validate_results(
                raw_lexical, tenant_id, scope, "lexical path")
        candidates = _merge_candidates(semantic_results, lexical_results)
        ordered = sorted(candidates, key=_candidate_order_key)
        return _collapse_duplicate_candidates(ordered)

    @staticmethod
    def _validate_results(
        results: object,
        tenant_id: Any,
        scope: EvidenceRetrievalScope,
        label: str,
    ) -> list[EvidenceRetrievalResult]:
        """Defense in depth: tenant, then scope, on every result."""
        if not isinstance(results, (list, tuple)):
            raise DomainValidationError(
                "evidence retrieval produced malformed output")
        validated: list[EvidenceRetrievalResult] = []
        for item in results:
            if not isinstance(item, EvidenceRetrievalResult):
                raise DomainValidationError("retrieval result is malformed")
            if item.tenant_id != tenant_id.tenant_id:
                raise VectorStoreError(
                    "evidence retrieval",
                    ValueError(f"{label} returned a cross-tenant result"),
                )
            if not scope.accepts(item):
                raise VectorStoreError(
                    "evidence retrieval",
                    ValueError(
                        f"{label} returned a result outside the "
                        "requested scope"),
                )
            validated.append(item)
        return validated


def _merge_candidates(
    semantic_results: list[EvidenceRetrievalResult],
    lexical_results: list[EvidenceRetrievalResult],
) -> list[HybridRetrievalCandidate]:
    """Union by canonical ``chunk_id``, preserving both paths' scores."""
    merged: dict[UUID, HybridRetrievalCandidate] = {}
    for result in semantic_results:
        merged[result.chunk_id] = HybridRetrievalCandidate(
            evidence=result,
            semantic_score=result.score,
            lexical_score=None,
            retrieval_sources=frozenset({"semantic"}),
        )
    for result in lexical_results:
        existing = merged.get(result.chunk_id)
        if existing is None:
            merged[result.chunk_id] = HybridRetrievalCandidate(
                evidence=result,
                semantic_score=None,
                lexical_score=result.score,
                retrieval_sources=frozenset({"lexical"}),
            )
        else:
            merged[result.chunk_id] = HybridRetrievalCandidate(
                evidence=existing.evidence,
                semantic_score=existing.semantic_score,
                lexical_score=result.score,
                retrieval_sources=frozenset({"semantic", "lexical"}),
            )
    return list(merged.values())


def _candidate_order_key(
    candidate: HybridRetrievalCandidate,
) -> tuple[int, float, int, float, UUID]:
    """Deterministic candidate ordering — explicitly NOT a fused ranking.

    Semantic-scored candidates first (descending), then lexical-scored
    (descending), then ``chunk_id`` ascending. No weights, no
    normalization, no score addition: a later phase may rerank.
    """
    semantic = candidate.semantic_score
    lexical = candidate.lexical_score
    return (
        0 if semantic is not None else 1,
        -(semantic if semantic is not None else 0.0),
        0 if lexical is not None else 1,
        -(lexical if lexical is not None else 0.0),
        candidate.evidence.chunk_id,
    )


def _collapse_duplicate_candidates(
    candidates: list[HybridRetrievalCandidate],
) -> list[HybridRetrievalCandidate]:
    """Apply the authoritative Phase 5.2 duplicate rule to candidates."""
    seen: set[tuple[UUID, str]] = set()
    kept: list[HybridRetrievalCandidate] = []
    for candidate in candidates:
        key = evidence_duplicate_key(candidate.evidence)
        if key in seen:
            continue
        seen.add(key)
        kept.append(candidate)
    return kept