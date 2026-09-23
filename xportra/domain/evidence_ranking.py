"""Evidence ranking boundary for Phase 5.5.

Takes the Phase 5.4 ``HybridRetrievalCandidate[]`` output — a candidate
set, deliberately NOT a global relevance ranking — and produces a
deterministic, explainable ordered evidence set for downstream context
selection.

The ranker is a pure domain operation:

- no network, Qdrant, embedding, or LLM call;
- no mutation of candidate objects, provenance, or scores;
- no score addition, weighting, normalization, or fusion;
- no compliance or legal-authority judgment.

It is intentionally replaceable: a later implementation can substitute
a cross-encoder or learned reranker behind the same ``EvidenceRanker``
protocol without changing the retrieval boundary.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from .errors import DomainValidationError
from .evidence_hybrid import RETRIEVAL_SOURCES, HybridRetrievalCandidate
from .evidence_retrieval import EvidenceRetrievalResult


@dataclass(frozen=True, slots=True)
class RankedEvidenceResult:
    """One ranked evidence item — order plus the unchanged Phase 5.4 payload.

    This is a thin wrapper, NOT a second evidence representation: the
    complete Phase 5.1 ``EvidenceRetrievalResult`` is carried by
    reference (same object as the candidate's evidence), so every
    provenance field — chunk/document identity, version, source,
    content, fingerprint, tenant — survives ranking unchanged. The
    per-path scores and retrieval sources are also preserved exactly as
    the Phase 5.4 candidate carried them.

    ``rank_position`` is 1-based and exposed explicitly for auditability
    (downstream components do not rely on list position).
    ``ranking_key`` is the structured tuple that determined the order —
    it makes the "why this position" answer auditable without any
    natural-language explanation being generated.
    """

    rank_position: int
    evidence: EvidenceRetrievalResult
    semantic_score: float | None
    lexical_score: float | None
    retrieval_sources: frozenset[str]
    ranking_key: tuple[int, float, float, UUID]

    def to_record(self) -> dict:
        """Structured ranking provenance (not natural-language text)."""
        return {
            "rank_position": self.rank_position,
            "evidence": self.evidence.to_record(),
            "semantic_score": self.semantic_score,
            "lexical_score": self.lexical_score,
            "retrieval_sources": sorted(self.retrieval_sources),
            "ranking_key": list(self.ranking_key),
        }


@runtime_checkable
class EvidenceRanker(Protocol):
    """Domain-level contract for evidence ranking.

    Implementations must be provider-independent and pure: they take a
    sequence of ``HybridRetrievalCandidate`` and return an ordered list
    of ``RankedEvidenceResult``. No Qdrant type, HTTP detail, or
    database ranking function may appear in any implementation's
    signature; ranking happens entirely in the domain.
    """

    def rank(
        self,
        candidates: list[HybridRetrievalCandidate],
        *,
        top_k: int,
    ) -> list[RankedEvidenceResult]: ...


class DeterministicEvidenceRanker:
    """Deterministic, explainable ranking policy for Phase 5.5.

    Ranking policy
    --------------
    1. Provenance precedence (higher first):
       - ``{"semantic", "lexical"}`` — both independent retrieval paths
         found this chunk;
       - ``{"semantic"}`` — semantic path only;
       - ``{"lexical"}`` — lexical path only.
    2. Within the same provenance tier, higher ``semantic_score`` first.
    3. Within equal semantic scores, higher ``lexical_score`` first.
    4. Remaining ties broken by ascending ``chunk_id``.

    Why this policy is valid
    ------------------------
    Phase 5.4 deliberately preserves semantic similarity and lexical
    term frequency as separate signals. They have different scales and
    different meanings (cosine-similarity-like score vs raw occurrence
    count), so they are NOT mathematically comparable and are never
    added, weighted, normalized, or fused here. The provenance tier is
    an informational signal — "two independent retrieval mechanisms
    agreed on this chunk" — not a score combination. Every signal used
    is already explicit on the Phase 5.4 candidate; nothing is inferred.

    No compliance semantics: the policy never uses source type,
    source reputation, jurisdiction, document age, or any presumed
    legal authority. A high rank means only "ranked higher for
    retrieval purposes under this policy" — never "legally
    authoritative" or "proves a compliance requirement". The repository
    contains no canonical domain authority model that would justify
    such assumptions.

    Determinism & tie-breaking
    --------------------------
    The sort key is fully explicit and derived only from candidate
    fields: provenance tier, the two scores, and the canonical
    ``chunk_id``. No set/dict iteration order, no provider ordering,
    and no object identity participate. Repeated ranking of the same
    candidate set — in any input order — always produces the identical
    output order.
    """

    def rank(
        self,
        candidates: list[HybridRetrievalCandidate],
        *,
        top_k: int,
    ) -> list[RankedEvidenceResult]:
        """Rank candidates and return the top ``top_k`` in ranked order.

        Pure: the input sequence is not mutated, candidates are not
        modified, and no external system is contacted. ``top_k`` is the
        FINAL ranked-result count (not a candidate-pool size) and must
        be a positive integer. An empty candidate list returns ``[]``.
        """
        self._validate_top_k(top_k)
        validated = self._validate_candidates(candidates)
        if not validated:
            return []
        ranked = self._rank_validated(validated)
        return ranked[:top_k]

    # ------------------------------------------------------------------
    # Validation (defense in depth; Phase 5.4 guarantees the invariant)
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_top_k(top_k: int) -> None:
        if (
            isinstance(top_k, bool)
            or not isinstance(top_k, int)
            or top_k <= 0
        ):
            raise DomainValidationError(
                "top-k must be a positive integer")

    @classmethod
    def _validate_candidates(
        cls, candidates: list[HybridRetrievalCandidate]
    ) -> list[HybridRetrievalCandidate]:
        if not isinstance(candidates, (list, tuple)):
            raise DomainValidationError(
                "evidence ranking received malformed candidate list")
        validated: list[HybridRetrievalCandidate] = []
        for candidate in candidates:
            cls._validate_one(candidate)
            validated.append(candidate)
        return validated

    @staticmethod
    def _validate_one(candidate: Any) -> None:
        """Enforce the Phase 5.4 candidate invariant — fail closed.

        ``HybridRetrievalCandidate`` construction already validates
        source/score consistency and non-empty sources; this re-check
        guards against subclass/monkeypatch bypasses and gives the
        ranker its own explicit contract. Malformed candidates are
        rejected, never silently converted into valid ones.
        """
        if not isinstance(candidate, HybridRetrievalCandidate):
            raise DomainValidationError(
                "evidence ranking received a malformed candidate")
        for name, score in (
            ("semantic_score", candidate.semantic_score),
            ("lexical_score", candidate.lexical_score),
        ):
            if score is None:
                continue
            if (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(score)
            ):
                raise DomainValidationError(f"{name} is malformed")
        sources = candidate.retrieval_sources
        if not isinstance(sources, frozenset):
            raise DomainValidationError(
                "candidate retrieval_sources is malformed")
        if not sources or not sources <= RETRIEVAL_SOURCES:
            raise DomainValidationError(
                "candidate retrieval_sources is malformed")
        if ("semantic" in sources) != (candidate.semantic_score is not None):
            raise DomainValidationError(
                "candidate semantic provenance is inconsistent")
        if ("lexical" in sources) != (candidate.lexical_score is not None):
            raise DomainValidationError(
                "candidate lexical provenance is inconsistent")

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    @classmethod
    def _rank_validated(
        cls, candidates: list[HybridRetrievalCandidate]
    ) -> list[RankedEvidenceResult]:
        seen: set[UUID] = set()
        for candidate in candidates:
            chunk_id = candidate.evidence.chunk_id
            if chunk_id in seen:
                raise DomainValidationError(
                    "candidate list contains duplicate chunk identity")
            seen.add(chunk_id)
        ordered = sorted(
            candidates,
            key=lambda c: (
                _provenance_tier(c),
                -(c.semantic_score if c.semantic_score is not None else 0.0),
                -(c.lexical_score if c.lexical_score is not None else 0.0),
                c.evidence.chunk_id,
            ),
        )
        return [
            RankedEvidenceResult(
                rank_position=position,
                evidence=cand.evidence,
                semantic_score=cand.semantic_score,
                lexical_score=cand.lexical_score,
                retrieval_sources=cand.retrieval_sources,
                ranking_key=_ranking_key(cand),
            )
            for position, cand in enumerate(ordered, start=1)
        ]


# Provenance tiers used for ranking-order precedence.
# Candidates retrieved by BOTH independent paths carry higher retrieval
# confidence than candidates found by a single path.
PROVENANCE_BOTH = 0
PROVENANCE_SEMANTIC_ONLY = 1
PROVENANCE_LEXICAL_ONLY = 2


def _provenance_tier(candidate: HybridRetrievalCandidate) -> int:
    """Map retrieval sources to ordering precedence (lower = higher)."""
    sources = candidate.retrieval_sources
    if sources == frozenset({"semantic", "lexical"}):
        return PROVENANCE_BOTH
    if sources == frozenset({"semantic"}):
        return PROVENANCE_SEMANTIC_ONLY
    if sources == frozenset({"lexical"}):
        return PROVENANCE_LEXICAL_ONLY
    raise DomainValidationError("candidate retrieval_sources is malformed")


def _ranking_key(candidate: HybridRetrievalCandidate) -> tuple[int, float, float, UUID]:
    """The explicit sort key, exposed per result for explainability."""
    return (
        _provenance_tier(candidate),
        -(candidate.semantic_score
          if candidate.semantic_score is not None else 0.0),
        -(candidate.lexical_score
          if candidate.lexical_score is not None else 0.0),
        candidate.evidence.chunk_id,
    )
