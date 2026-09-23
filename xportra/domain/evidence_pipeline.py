"""Retrieval pipeline orchestration boundary for Phase 5.6.

The first application-facing entry point that composes the completed
retrieval components into one call:

```text
information need
      ↓
EvidenceRetrievalQuery (Phase 5.2 semantics)
      ↓
HybridEvidenceRetriever (Phase 5.4: semantic / lexical / hybrid)
      ↓
HybridRetrievalCandidate[]
      ↓
EvidenceRanker (Phase 5.5 deterministic policy)
      ↓
RankedEvidenceResult[]
```

This module is an ORCHESTRATION boundary only. It reimplements nothing:
no semantic retrieval, no lexical matching, no deduplication, no scope
matching, no ranking policy, no score handling. It owns exactly one
concern — the final ranked-result limit — and forwards everything else
unchanged to the existing boundaries.

It performs no LLM call, no direct embedding call, no Qdrant call, no
context-window construction, no prompt generation, no compliance
reasoning, and no answer generation. Failures from the lower layers
propagate unchanged: `[]` continues to mean exactly
"retrieval completed successfully and no evidence matched" — never a
masked failure.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .errors import DomainValidationError, require_tenant_context
from .evidence_hybrid import (
    RETRIEVAL_MODES,
    ComposedHybridEvidenceRetriever,
    EvidenceLexicalIndex,
    HybridRetrievalCandidate,
)
from .evidence_ranking import (
    DeterministicEvidenceRanker,
    EvidenceRanker,
    RankedEvidenceResult,
)
from .evidence_retrieval import (
    DEFAULT_TOP_K,
    EvidenceRetrievalQuery,
    EvidenceRetrievalScope,
    EvidenceRetriever,
)


@runtime_checkable
class RetrievalPipeline(Protocol):
    """Application-facing retrieval contract: one call, ranked results.

    Tenant identity is a required keyword — unscoped or all-tenant
    retrieval cannot be expressed through this boundary. ``mode`` is
    explicit (``semantic`` | ``lexical`` | ``hybrid``) so retrieval
    behavior is never ambiguous. Implementations must preserve ranked
    results exactly as the ranker produced them.
    """

    def retrieve(
        self,
        information_need: str,
        *,
        tenant_id: Any,
        mode: str,
        scope: EvidenceRetrievalScope | None = None,
        top_k: int = DEFAULT_TOP_K,
        candidate_pool: int | None = None,
    ) -> list[RankedEvidenceResult]: ...


class EvidenceRetrievalPipeline:
    """Compose Phase 5.4 hybrid retrieval and Phase 5.5 ranking.

    Dependency injection
    --------------------
    Both collaborators are injected explicitly — the pipeline never
    constructs a Qdrant client, an embedding provider, or any
    infrastructure adapter, so it is testable with fakes:

    ```text
    EvidenceRetrievalPipeline
        ↓ HybridEvidenceRetriever   (→ vector index / lexical infra)
        ↓ EvidenceRanker            (pure domain policy)
    ```

    Top-k ownership
    ---------------
    There is exactly ONE authoritative final top-k: the Phase 5.5
    ranker's post-ordering truncation, driven by this call's ``top_k``.
    The candidate pool size is a separate, explicit value:
    ``candidate_pool`` (default: ``top_k``) becomes the per-path
    retrieval bound inside the Phase 5.4 query, so the ranker sees the
    full merged candidate set (up to 2 × candidate_pool before the
    Phase 5.2 duplicate collapse) and decides the final order and cut.
    The pipeline never truncates before ranking and never multiplies
    top-k by a hidden constant — a caller wanting ranking to see more
    candidates passes a larger ``candidate_pool`` explicitly.

    Failure semantics
    -----------------
    No broad exception handling: embedding, vector-store, lexical, and
    ranking failures propagate unchanged from the responsible boundary.
    The pipeline converts nothing into an empty success.

    Result integrity
    ----------------
    The pipeline is not a transformation boundary: ranked results are
    returned exactly as the ranker produced them — same objects, same
    order, same rank positions, scores, provenance, and ranking keys.
    The only added check is structural defense-in-depth on the ranker's
    output (the ranker is an injected collaborator, like the provider
    results Phase 5.4 re-validates).
    """

    def __init__(
        self,
        *,
        hybrid_retriever: Any,
        ranker: EvidenceRanker,
    ) -> None:
        if (
            hybrid_retriever is None
            or isinstance(hybrid_retriever, (str, bytes))
            or not callable(
                getattr(hybrid_retriever, "retrieve_candidates", None))
        ):
            raise DomainValidationError(
                "a hybrid evidence retriever is required")
        if (
            ranker is None
            or isinstance(ranker, (str, bytes))
            or not callable(getattr(ranker, "rank", None))
        ):
            raise DomainValidationError("an evidence ranker is required")
        self._hybrid_retriever = hybrid_retriever
        self._ranker = ranker

    def retrieve(
        self,
        information_need: str,
        *,
        tenant_id: Any,
        mode: str,
        scope: EvidenceRetrievalScope | None = None,
        top_k: int = DEFAULT_TOP_K,
        candidate_pool: int | None = None,
    ) -> list[RankedEvidenceResult]:
        """Run hybrid retrieval, then deterministic ranking.

        ``tenant_id`` is a mandatory keyword and is forwarded unchanged
        to the hybrid retriever (the Phase 5.1/5.3 isolation remains the
        only tenant mechanism — this layer adds no competing one).
        ``scope`` is forwarded unchanged; ``None`` keeps the Phase 5.3
        meaning of tenant-only retrieval. ``mode`` is explicit and
        validated against the Phase 5.4 mode set. ``top_k`` is the final
        ranked-result count; ``candidate_pool`` is the optional per-path
        retrieval bound (default ``top_k``).
        """
        require_tenant_context(tenant_id)
        if not isinstance(information_need, str):
            raise DomainValidationError(
                "an information need is required")
        if mode not in RETRIEVAL_MODES:
            raise DomainValidationError("unsupported retrieval mode")
        if scope is not None and not isinstance(
                scope, EvidenceRetrievalScope):
            raise DomainValidationError(
                "an evidence retrieval scope is required")
        if candidate_pool is not None:
            # EvidenceRetrievalQuery validates positivity; this explicit
            # check keeps the two top-k knobs individually attributable.
            if (
                isinstance(candidate_pool, bool)
                or not isinstance(candidate_pool, int)
                or candidate_pool <= 0
            ):
                raise DomainValidationError(
                    "candidate pool must be a positive integer")
        pool = top_k if candidate_pool is None else candidate_pool
        query = EvidenceRetrievalQuery(
            text=information_need, top_k=pool)
        candidates = self._hybrid_retriever.retrieve_candidates(
            query,
            tenant_id=tenant_id,
            mode=mode,
            scope=scope,
        )
        if not isinstance(candidates, (list, tuple)):
            raise DomainValidationError(
                "hybrid retrieval produced malformed output")
        ranked = self._ranker.rank(list(candidates), top_k=top_k)
        self._validate_ranked(ranked)
        return ranked

    @staticmethod
    def _validate_ranked(ranked: object) -> None:
        """Structural defense-in-depth on the injected ranker's output.

        Not a re-ranking, not a copy, not a mutation: a malformed ranker
        response fails closed instead of leaking downstream.
        """
        if not isinstance(ranked, list):
            raise DomainValidationError(
                "evidence ranking produced malformed output")
        for item in ranked:
            if not isinstance(item, RankedEvidenceResult):
                raise DomainValidationError(
                    "evidence ranking produced malformed output")


def build_evidence_retrieval_pipeline(
    *,
    semantic_retriever: EvidenceRetriever,
    lexical_index: EvidenceLexicalIndex,
    ranker: EvidenceRanker | None = None,
) -> EvidenceRetrievalPipeline:
    """Smallest composition helper: wire the concrete pipeline.

    Combines the Phase 5.4 ``ComposedHybridEvidenceRetriever`` (which
    validates its own dependencies) with the Phase 5.5
    ``DeterministicEvidenceRanker`` (the default when ``ranker`` is
    omitted — the documented initial policy, not a hidden alternative).
    This is a construction boundary only: no dependency-injection
    framework, no application startup wiring, no infrastructure
    construction.
    """
    if ranker is None:
        ranker = DeterministicEvidenceRanker()
    hybrid_retriever = ComposedHybridEvidenceRetriever(
        semantic_retriever=semantic_retriever,
        lexical_index=lexical_index,
    )
    return EvidenceRetrievalPipeline(
        hybrid_retriever=hybrid_retriever,
        ranker=ranker,
    )
