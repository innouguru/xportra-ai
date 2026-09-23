"""Retrieval-to-context pipeline composition boundary for Phase 5.8.

The second application-facing orchestration entry point: it composes
the completed Phase 5.6 retrieval pipeline and the Phase 5.7 context
selector into one call:

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

This module is COMPOSITION ONLY. It reimplements nothing: no
retrieval, no ranking, no deduplication, no scope handling, no tenant
isolation mechanism, no budget arithmetic, no oversized-item policy,
no truncation. Every concern is delegated to the existing, already
verified boundary that owns it.

It performs no LLM call, no embedding call, no Qdrant call, no HTTP
call, no database access, no prompt generation, no compliance
reasoning, and no answer generation. Failures from the lower layers
propagate unchanged: a successful empty selection continues to mean
exactly "retrieval succeeded and no evidence was selected" — never a
masked operational failure.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .errors import DomainValidationError, require_tenant_context
from .evidence_context import ContextSelector, EvidenceContextBudget
from .evidence_pipeline import (
    RetrievalPipeline,
    build_evidence_retrieval_pipeline,
)
from .evidence_ranking import RankedEvidenceResult
from .evidence_retrieval import DEFAULT_TOP_K


@runtime_checkable
class EvidenceContextPipelineContract(Protocol):
    """Application-facing retrieval-to-context contract.

    One call: an information need in, a budgeted, tenant-scoped
    ``EvidenceContextSelection`` out. Implementations must delegate
    retrieval to a ``RetrievalPipeline`` and selection to a
    ``ContextSelector`` without reimplementing either.
    """

    def select_context(
        self,
        information_need: str,
        *,
        tenant_id: Any,
        mode: str,
        context_budget: EvidenceContextBudget,
        scope=None,
        top_k: int = DEFAULT_TOP_K,
        candidate_pool: int | None = None,
    ) -> Any: ...


class EvidenceContextPipeline:
    """Compose Phase 5.6 retrieval and Phase 5.7 context selection.

    Dependency injection
    --------------------
    Both collaborators are injected explicitly — the orchestrator never
    constructs a hybrid retriever, a ranker, an embedding provider, a
    Qdrant client, or any infrastructure adapter:

    ```text
    EvidenceContextPipeline
        ↓ RetrievalPipeline   (Phase 5.6 — retrieval + ranking)
        ↓ ContextSelector     (Phase 5.7 — budgeted selection)
    ```

    Delegation
    ----------
    Retrieval: ``retrieve(...)`` is forwarded unchanged — information
    need, tenant, mode, scope, ``top_k``, and ``candidate_pool`` — to
    the injected ``RetrievalPipeline``, which remains the single
    authoritative retrieval/ranking boundary. This layer never calls
    ``ComposedHybridEvidenceRetriever`` or ``EvidenceRanker`` directly
    and never truncates ranked results before the selector.

    Selection: the ranked results are passed to the injected
    ``ContextSelector`` together with the caller's
    ``EvidenceContextBudget`` — the Phase 5.7 boundary remains the
    sole owner of budget accounting, oversized-item policy, skipped
    rank positions, and selection order. This layer performs no budget
    arithmetic, no pre-filtering, no content truncation, no token
    estimation, and never inspects individual evidence scores.

    Tenant / scope / mode
    ---------------------
    ``tenant_id`` is a mandatory keyword at this API boundary
    (``require_tenant_context``) so unscoped retrieval cannot even be
    expressed here; the established Phase 5.1/5.3/5.6/5.7 tenant
    validation remains the only isolation mechanism. ``scope`` is
    forwarded unchanged (object identity preserved). ``mode`` is
    forwarded unchanged — the Phase 5.6 pipeline owns mode validation;
    this layer introduces no new mode and no silent conversion.

    Result integrity
    ----------------
    The orchestrator is not a transformation boundary: the
    ``EvidenceContextSelection`` returned is the exact object produced
    by the injected selector — same selected items, same accounting,
    same skipped rank positions. Ranked results are handed to the
    selector in retrieval order without modification. The only added
    check is structural defense-in-depth on the pipeline's output
    (the pipeline is an injected collaborator), mirroring Phase 5.6.

    Failure semantics
    -----------------
    No broad exception handling: retrieval, ranking, and
    context-selection failures propagate unchanged from the
    responsible boundary. Failures are never converted into an empty
    successful selection.
    """

    def __init__(
        self,
        *,
        retrieval_pipeline: Any,
        context_selector: Any,
    ) -> None:
        if (
            retrieval_pipeline is None
            or isinstance(retrieval_pipeline, (str, bytes))
            or not callable(
                getattr(retrieval_pipeline, "retrieve", None))
        ):
            raise DomainValidationError(
                "a retrieval pipeline is required")
        if (
            context_selector is None
            or isinstance(context_selector, (str, bytes))
            or not callable(getattr(context_selector, "select", None))
        ):
            raise DomainValidationError(
                "a context selector is required")
        self._retrieval_pipeline = retrieval_pipeline
        self._context_selector = context_selector

    def select_context(
        self,
        information_need: str,
        *,
        tenant_id: Any,
        mode: str,
        context_budget: EvidenceContextBudget,
        scope=None,
        top_k: int = DEFAULT_TOP_K,
        candidate_pool: int | None = None,
    ) -> Any:
        """Run retrieval + ranking, then budgeted context selection.

        Returns the exact ``EvidenceContextSelection`` produced by the
        injected selector. An empty ranked set flows to the selector
        unchanged and yields its established successful empty
        selection — this layer turns it into neither an error nor a
        fabricated result.
        """
        require_tenant_context(tenant_id)
        if not isinstance(information_need, str):
            raise DomainValidationError(
                "an information need is required")
        if not isinstance(context_budget, EvidenceContextBudget):
            raise DomainValidationError(
                "an EvidenceContextBudget is required")
        ranked = self._retrieval_pipeline.retrieve(
            information_need,
            tenant_id=tenant_id,
            mode=mode,
            scope=scope,
            top_k=top_k,
            candidate_pool=candidate_pool,
        )
        self._validate_ranked(ranked)
        return self._context_selector.select(
            ranked,
            tenant_id=tenant_id,
            budget=context_budget,
        )

    @staticmethod
    def _validate_ranked(ranked: object) -> None:
        """Structural defense-in-depth on the pipeline's output.

        Not a re-ranking, not a copy, not a mutation: a malformed
        retrieval response fails closed instead of leaking downstream.
        """
        if not isinstance(ranked, (list, tuple)):
            raise DomainValidationError(
                "retrieval pipeline produced malformed output")
        for item in ranked:
            if not isinstance(item, RankedEvidenceResult):
                raise DomainValidationError(
                    "retrieval pipeline produced malformed output")


def build_evidence_context_pipeline(
    *,
    semantic_retriever,
    lexical_index,
    ranker=None,
    context_selector=None,
) -> EvidenceContextPipeline:
    """Smallest composition helper: wire the concrete pipeline.

    Combines the Phase 5.6 ``build_evidence_retrieval_pipeline``
    factory (which validates its own dependencies and defaults the
    Phase 5.5 ``DeterministicEvidenceRanker``) with the Phase 5.7
    ``DeterministicContextSelector`` (the default when ``context_selector``
    is omitted). This is a construction boundary only: no
    dependency-injection framework, no application startup wiring, no
    infrastructure construction.
    """
    if context_selector is None:
        from .evidence_context import DeterministicContextSelector

        context_selector = DeterministicContextSelector()
    retrieval_pipeline = build_evidence_retrieval_pipeline(
        semantic_retriever=semantic_retriever,
        lexical_index=lexical_index,
        ranker=ranker,
    )
    return EvidenceContextPipeline(
        retrieval_pipeline=retrieval_pipeline,
        context_selector=context_selector,
    )


__all__ = [
    "EvidenceContextPipeline",
    "EvidenceContextPipelineContract",
    "build_evidence_context_pipeline",
]
