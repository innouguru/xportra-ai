"""Budget-aware context selection boundary for Phase 5.7.

Converts already-ranked evidence into the deterministic subset selected
for downstream LLM context under an explicit budget:

```text
RankedEvidenceResult[]   (Phase 5.5 ranker output, via Phase 5.6)
        ↓
EvidenceContextSelector  (this module)
        ↓
EvidenceContextSelection (selected items + auditable accounting)
```

This is CONTEXT SELECTION ONLY. The selector never retrieves, never
ranks, never rescores, never reorders, never deduplicates, and never
balances sources. It performs no LLM call, no embedding call, no HTTP
call, no Qdrant call, no database access, and imports no infrastructure
SDK. Failures are fail-closed: malformed evidence, duplicate chunk
identity, tenant mismatch, and invalid budgets raise
``DomainValidationError`` — nothing is silently repaired, dropped, or
truncated.

Budget semantics
----------------
The budget counts **evidence content characters only**. Separators,
labels, formatting wrappers, and any prompt scaffolding are NOT counted
here — final prompt formatting belongs to a later boundary. This is a
deterministic approximation of an LLM context window, NOT an exact
token count; model-specific token accounting requires a tokenizer and
is deliberately deferred. No tokenizer dependency is introduced.

Oversized-item policy
---------------------
An item whose content exceeds the TOTAL budget can never fit under any
budget usage and is rejected fail-closed (a misused or corrupt budget,
not a normal skip — production chunking bounds content at 1200
characters, so this should be impossible). An item that fits the total
budget but exceeds the REMAINING budget is SKIPPED deterministically
and selection CONTINUES with later items (a rank gap results). Content
is never truncated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .errors import DomainValidationError, require_tenant_context
from .evidence_ranking import RankedEvidenceResult


@dataclass(frozen=True, slots=True)
class EvidenceContextBudget:
    """Explicit, validated context budget in content characters.

    Semantics (documented approximation — NOT an exact LLM token
    count): the budget bounds the sum of ``len(content)`` over the
    selected evidence items. Evidence content only — separators,
    provenance labels, formatting wrappers, and prompt scaffolding are
    not accounted here; final prompt formatting is a later boundary's
    concern. Model-specific token accounting (which requires a
    tokenizer) is deliberately deferred; this phase establishes the
    deterministic budget boundary only.

    The type is strict by design: booleans (a subclass of int), floats,
    strings, ``None``, zero, and negative values are all rejected
    fail-closed so a silent mis-budget can never produce a silently
    wrong context.
    """

    max_characters: int

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_characters, bool)
            or not isinstance(self.max_characters, int)
            or self.max_characters <= 0
        ):
            raise DomainValidationError(
                "context budget must be a positive integer (characters)")


@dataclass(frozen=True, slots=True)
class SelectedEvidence:
    """One evidence item selected for context — provenance-preserving.

    A thin wrapper, not a second evidence representation: the ranked
    result is carried by reference (same object), so tenant, chunk,
    document, version, chunk index, source, content, fingerprint,
    embedding contract, scores, retrieval sources, and ranking key all
    survive unchanged. ``rank_position`` is re-exposed at the top level
    for downstream auditability, and ``character_count`` makes the
    budget contribution of this item explicit.
    """

    rank_position: int
    ranked: RankedEvidenceResult
    character_count: int

    def to_record(self) -> dict:
        """Structured selection provenance (not prompt text)."""
        return {
            "rank_position": self.rank_position,
            "character_count": self.character_count,
            "ranked": self.ranked.to_record(),
        }


@dataclass(frozen=True, slots=True)
class EvidenceContextSelection:
    """Deterministic selection outcome with auditable accounting.

    ``skipped_rank_positions`` records, in rank order, the positions of
    items skipped because they exceeded the remaining budget — the
    explicit, auditable trace of any rank gap. The selection may be
    empty (successful input ``[]``, or nothing fit); that is a valid
    outcome, never an error.
    """

    budget: EvidenceContextBudget
    selected_items: tuple[SelectedEvidence, ...]
    used_budget: int
    skipped_rank_positions: tuple[int, ...]

    @property
    def remaining_budget(self) -> int:
        return self.budget.max_characters - self.used_budget

    def to_record(self) -> dict:
        return {
            "budget": self.budget.max_characters,
            "used_budget": self.used_budget,
            "remaining_budget": self.remaining_budget,
            "skipped_rank_positions": list(self.skipped_rank_positions),
            "selected_items": [
                item.to_record() for item in self.selected_items
            ],
        }


@runtime_checkable
class ContextSelector(Protocol):
    """Domain contract for budget-aware context selection.

    Implementations must be pure: they consume already-ranked evidence
    in rank order and return a deterministic selection. They never
    retrieve, rank, rescore, or contact any infrastructure.
    """

    def select(
        self,
        ranked: list[RankedEvidenceResult],
        *,
        tenant_id: Any,
        budget: EvidenceContextBudget,
    ) -> EvidenceContextSelection: ...


class DeterministicContextSelector:
    """Greedy in-rank-order selection under an explicit budget.

    Algorithm (deterministic, no reordering, no rescoring)
    ------------------------------------------------------
    1. Validate the budget and every ranked result (structural
       integrity + tenant, below).
    2. Walk the results in the given order — the Phase 5.5 rank order.
    3. Include an item iff ``used + len(content) <= budget``.
    4. If an item exceeds the remaining budget, SKIP it, record its
       rank position, and CONTINUE with later items.
    5. Stop at the end of the input.

    Ordering: selected items retain the original ranking order, gaps
    included (ranks 1, 3, 4 stay 1, 3, 4) — the selector never sorts
    independently. Rank positions must be positive integers strictly
    ascending in input order; position-value gaps are acceptable, an
    ordering violation is not.

    Oversized items: an item larger than the TOTAL budget can never
    fit under any budget usage and indicates a misused or corrupt
    budget (evidence chunking bounds content at 1200 characters, so
    this should be impossible in production) — rejected fail-closed
    rather than silently skipped, to avoid hiding corruption. An item
    that fits the total budget but not the remaining budget is skipped
    and selection continues. Content is never truncated.

    Empty input: a valid, successful empty selection with zero usage.

    Tenant isolation: ``tenant_id`` is mandatory
    (``require_tenant_context``) and every result's tenant is
    re-validated per item — the ranked-result contract structurally
    guarantees tenant identity; this preserves and revalidates it
    rather than introducing a second mechanism. A mismatch fails
    closed.

    Integrity: results must be ``RankedEvidenceResult`` values with a
    non-empty string content payload (guaranteed by
    ``EvidenceRetrievalResult`` construction and re-checked as defense
    in depth). Duplicate chunk identity is rejected (the ranker
    guarantees uniqueness). Nothing is silently repaired or dropped.

    Purity: no infrastructure dependency of any kind; inputs are never
    mutated (frozen values are carried by reference, never copied or
    modified).
    """

    def select(
        self,
        ranked: list[RankedEvidenceResult],
        *,
        tenant_id: Any,
        budget: EvidenceContextBudget,
    ) -> EvidenceContextSelection:
        require_tenant_context(tenant_id)
        if not isinstance(budget, EvidenceContextBudget):
            raise DomainValidationError(
                "an EvidenceContextBudget is required")
        if not isinstance(ranked, (list, tuple)):
            raise DomainValidationError(
                "context selection received malformed ranked evidence")
        if not ranked:
            return EvidenceContextSelection(
                budget=budget,
                selected_items=(),
                used_budget=0,
                skipped_rank_positions=(),
            )

        max_chars = budget.max_characters
        seen_chunks: set = set()
        previous_position: int | None = None
        selected: list[SelectedEvidence] = []
        skipped: list[int] = []
        used = 0

        for item in ranked:
            if not isinstance(item, RankedEvidenceResult):
                raise DomainValidationError(
                    "context selection received malformed ranked evidence")
            evidence = item.evidence
            if evidence is None or not isinstance(
                    evidence.content, str) or not evidence.content:
                raise DomainValidationError(
                    "ranked evidence content is malformed")
            if evidence.tenant_id != tenant_id.tenant_id:
                raise DomainValidationError(
                    "ranked evidence contains a cross-tenant result")
            chunk_id = evidence.chunk_id
            if chunk_id in seen_chunks:
                raise DomainValidationError(
                    "ranked evidence contains duplicate chunk identity")
            seen_chunks.add(chunk_id)
            position = item.rank_position
            if (
                isinstance(position, bool)
                or not isinstance(position, int)
                or position <= 0
            ):
                raise DomainValidationError(
                    "rank position is malformed")
            if previous_position is not None and position <= previous_position:
                raise DomainValidationError(
                    "ranked evidence is not in ascending rank order")
            previous_position = position

            size = len(evidence.content)
            if size > max_chars:
                raise DomainValidationError(
                    "ranked evidence exceeds the total context budget")
            if used + size > max_chars:
                skipped.append(position)
                continue
            used += size
            selected.append(
                SelectedEvidence(
                    rank_position=position,
                    ranked=item,
                    character_count=size,
                )
            )

        return EvidenceContextSelection(
            budget=budget,
            selected_items=tuple(selected),
            used_budget=used,
            skipped_rank_positions=tuple(skipped),
        )


__all__ = [
    "ContextSelector",
    "DeterministicContextSelector",
    "EvidenceContextBudget",
    "EvidenceContextSelection",
    "SelectedEvidence",
]
