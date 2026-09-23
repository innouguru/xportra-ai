"""Citation-aware prompt construction boundary for Phase 5.10.

Converts the verified Phase 5.7 ``EvidenceContextSelection`` into a
deterministic, auditable, LLM-ready prompt representation:

```text
EvidenceContextSelection   (Phase 5.7 — the authoritative selection)
        ↓
CitationAwarePromptBuilder (this module — deterministic transform only)
        ↓
EvidencePrompt             (structured: system / user / evidence /
                            citations + provenance mapping)
```

This is PROMPT CONSTRUCTION ONLY. The builder never retrieves, never
ranks, never selects, never filters evidence, never computes a budget,
never summarizes, never paraphrases, never truncates, and never
generates an answer. It performs no LLM call, no Qdrant call, no
database access, no HTTP call, no file access, no dynamic environment
reads, and imports no infrastructure SDK. Failures fail closed:
malformed inputs raise ``DomainValidationError`` — nothing is silently
repaired or fabricated.

Prompt-injection boundary
-------------------------
Retrieved evidence is UNTRUSTED DATA. The prompt representation keeps
system instructions, the user's information need, and the evidence
context structurally separate (distinct immutable fields, never
concatenated into one opaque string), so a future generation boundary
can treat evidence as untrusted context. Instruction-like text inside
evidence content remains evidence — it can never become system
instructions through this boundary.

Citation semantics
------------------
``[E1]``, ``[E2]`` … are PROMPT-LOCAL reference labels assigned in the
selection's authoritative order. ``[E1]`` means "the first evidence
item in this prompt" — never "legally authoritative citation". Every
label resolves through a structured ``citation → SelectedEvidence``
mapping (original objects carried by reference) to the full Phase 5.9
provenance chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .errors import DomainValidationError, require_tenant_context
from .evidence_context import EvidenceContextSelection, SelectedEvidence

CITATION_FORMAT = "[E{n}]"


def citation_label(position: int) -> str:
    """The deterministic prompt-local citation label for a 1-based
    evidence position."""
    return CITATION_FORMAT.format(n=position)


@dataclass(frozen=True, slots=True)
class EvidencePromptConfig:
    """Immutable prompt-formatting configuration.

    Deliberately minimal: system instruction text and the two section
    headings that structure the rendered prompt. No tokenizer, no
    model selection, no temperature, no arbitrary dictionaries.
    Defaults are fixed strings — identical inputs always produce an
    identical prompt.
    """

    system_instructions: str
    evidence_heading: str = "RETRIEVED EVIDENCE (untrusted context)"
    question_heading: str = "INFORMATION NEED"

    def __post_init__(self) -> None:
        for name in ("system_instructions", "evidence_heading",
                     "question_heading"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise DomainValidationError(
                    f"prompt config {name} is required")


@dataclass(frozen=True, slots=True)
class PromptCitation:
    """One prompt-local citation: label plus the evidence it names.

    A thin reference wrapper, not a second provenance representation:
    ``selected`` is the original Phase 5.7 ``SelectedEvidence`` object,
    whose ``ranked.evidence`` is the original Phase 5.1 result — so
    the full provenance chain (tenant, source triple, document,
    version, chunk, fingerprint, rank, scores, retrieval sources,
    ranking key) resolves by reference. ``label`` is deterministic and
    unique within one prompt.
    """

    label: str
    selected: SelectedEvidence

    @property
    def rank_position(self) -> int:
        return self.selected.rank_position

    def to_record(self) -> dict:
        """Structured citation provenance (not prompt text)."""
        return {
            "label": self.label,
            "rank_position": self.rank_position,
            "selected": self.selected.to_record(),
        }


@dataclass(frozen=True, slots=True)
class EvidencePrompt:
    """Structured, immutable, LLM-ready prompt representation.

    System instructions, the user's information need, and the evidence
    context are SEPARATE immutable fields — never collapsed into one
    opaque string — so a future LLM adapter (and any prompt-injection
    defense) can identify which text is instruction, which is user
    input, and which is untrusted retrieved evidence without parsing
    formatted text.

    ``citations`` preserves the structured ``label → SelectedEvidence``
    mapping in prompt order. ``render()`` is a deterministic
    convenience rendering for logging/preview; the structured fields —
    not the rendered string — are the authoritative representation.
    """

    system_instructions: str
    information_need: str
    evidence_context: str
    citations: tuple[PromptCitation, ...]
    evidence_heading: str
    question_heading: str
    tenant_id: Any

    @property
    def is_empty(self) -> bool:
        """True when the prompt carries no evidence (a valid state)."""
        return not self.citations

    def render(self) -> str:
        """Deterministic rendering (preview/log convenience only).

        The evidence section is explicitly marked as untrusted
        context; this rendering changes no content and adds no
        metadata beyond the configured headings and citation labels.
        """
        parts = [
            self.system_instructions,
            "",
            self.question_heading + ":",
            self.information_need,
            "",
            self.evidence_heading + ":",
        ]
        if self.evidence_context:
            parts.append(self.evidence_context)
        else:
            parts.append("(no evidence matched the information need)")
        return "\n".join(parts)

    def to_record(self) -> dict:
        return {
            "system_instructions": self.system_instructions,
            "information_need": self.information_need,
            "evidence_context": self.evidence_context,
            "evidence_heading": self.evidence_heading,
            "question_heading": self.question_heading,
            "is_empty": self.is_empty,
            "citations": [c.to_record() for c in self.citations],
        }


class CitationAwarePromptBuilder:
    """Deterministic, citation-aware prompt construction.

    Responsibility boundary
    -----------------------
    The builder consumes an already-verified ``EvidenceContextSelection``
    and produces an ``EvidencePrompt``. It performs no retrieval, no
    ranking, no selection, no budget arithmetic, no evidence
    filtering, no semantic matching, no summarizing, no paraphrasing,
    no truncation, and no answer generation. The Phase 5.7 selector
    remains the single authority for what is in the context and in
    what order; the Phase 5.6/5.8 pipelines remain the authoritative
    retrieval boundaries.

    Evidence ordering: the selection's order is preserved exactly —
    no reordering by source/document/citation, no grouping, no
    deduplication. Citation labels are assigned in that order:
    ``[E1]`` to the first selected item, ``[E2]`` to the second, and
    so on — deterministic, unique within the prompt, and stable for
    the prompt's lifetime.

    Content integrity: evidence content appears exactly as selected;
    the only additions are formatting wrappers (citation label,
    metadata lines, heading indentation). Two spaces indent every
    evidence-content line — a formatting wrapper that never alters the
    content itself (line content is preserved verbatim after the
    indent).

    Tenant handling: tenant identity is preserved from the selection's
    evidence and validated to be a single consistent tenant; the
    builder never infers, changes, or accepts a caller-supplied tenant
    value, and never combines evidence across tenants.

    Empty context: an empty selection yields a valid, well-formed
    prompt with no citations and an explicit "(no evidence matched
    the information need)" marker in the rendered preview — no
    evidence is ever fabricated.

    Injection boundary: instruction-like text inside evidence content
    stays inside the evidence section; system instructions and
    evidence are structurally separate fields. Establishing this data
    boundary is this phase's entire injection scope — detection and
    enforcement belong to a future generation boundary.

    Purity: no LLM, Qdrant, database, HTTP, file, or tokenizer access;
    no dynamic environment configuration; inputs are never mutated
    (frozen values are carried by reference).
    """

    def __init__(self, *, config: EvidencePromptConfig) -> None:
        if not isinstance(config, EvidencePromptConfig):
            raise DomainValidationError(
                "an EvidencePromptConfig is required")
        self._config = config

    def build(
        self,
        selection: EvidenceContextSelection,
        *,
        information_need: str,
    ) -> EvidencePrompt:
        """Construct the prompt from a verified context selection."""
        if not isinstance(selection, EvidenceContextSelection):
            raise DomainValidationError(
                "an EvidenceContextSelection is required")
        if not isinstance(information_need, str):
            raise DomainValidationError(
                "an information need is required")
        normalized_need = " ".join(information_need.split())
        if not normalized_need:
            raise DomainValidationError(
                "an information need is required")

        citations: list[PromptCitation] = []
        seen_labels: set[str] = set()
        tenant_ids: set = set()
        blocks: list[str] = []

        for index, item in enumerate(selection.selected_items, start=1):
            if not isinstance(item, SelectedEvidence):
                raise DomainValidationError(
                    "context selection contains malformed evidence")
            ranked = item.ranked
            if ranked is None or not isinstance(
                    getattr(ranked, "evidence", None), object):
                raise DomainValidationError(
                    "context selection contains malformed evidence")
            evidence = ranked.evidence
            if evidence.tenant_id is None:
                raise DomainValidationError(
                    "selected evidence has no tenant identity")
            tenant_ids.add(evidence.tenant_id)

            label = citation_label(index)
            if label in seen_labels:
                raise DomainValidationError(
                    "duplicate citation identity in prompt")
            seen_labels.add(label)
            if item.rank_position != ranked.rank_position:
                raise DomainValidationError(
                    "citation identity is inconsistent with rank position")
            citations.append(PromptCitation(label=label, selected=item))

            blocks.append(
                "\n".join([
                    label,
                    f"Source: {evidence.source_id}",
                    f"Source type: {evidence.source_type}",
                    f"Document version: "
                    f"{evidence.document_version or 'unversioned'}",
                    "Evidence:",
                    *[
                        "  " + line
                        for line in evidence.content.split("\n")
                    ],
                ])
            )

        if len(tenant_ids) > 1:
            raise DomainValidationError(
                "context selection spans multiple tenants")
        tenant_id = next(iter(tenant_ids)) if tenant_ids else None

        return EvidencePrompt(
            system_instructions=self._config.system_instructions,
            information_need=normalized_need,
            evidence_context="\n\n".join(blocks),
            citations=tuple(citations),
            evidence_heading=self._config.evidence_heading,
            question_heading=self._config.question_heading,
            tenant_id=tenant_id,
        )


__all__ = [
    "CITATION_FORMAT",
    "CitationAwarePromptBuilder",
    "EvidencePrompt",
    "EvidencePromptConfig",
    "PromptCitation",
    "citation_label",
]
