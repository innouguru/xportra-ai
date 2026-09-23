"""Answer validation & citation integrity boundary for Phase 5.12.

Deterministic, pure validation of model-generated answers against the
authoritative citation mapping:

```text
GeneratedAnswer / LLMResponse   (Phase 5.11 — untrusted model output)
        ↓
AnswerValidator                 (this module — deterministic, pure)
        ↓
ValidatedAnswer                 (citation integrity + preserved provenance)
```

What validation PROVES
----------------------
Citation validation proves that referenced labels correspond to
authoritative retrieved evidence supplied to the model. It does NOT
prove that the model's claim is factually or legally supported by
that evidence — semantic grounding is a separate, future boundary.

What validation does
--------------------
The authoritative citation universe is
``GeneratedAnswer.prompt.citations`` (the Phase 5.10 ``[E1]``-style
labels). A citation appearing in generated text is valid only if the
label exists in that mapping. The validator:

- extracts citation-like labels from the answer text with a strict,
  deterministic parser (exact ``[E<n>]`` syntax; no fuzzy matching,
  no normalization of arbitrary identifiers);
- classifies each extracted reference as valid or invalid against
  the authoritative mapping;
- applies the documented invalid-citation policy — FAIL CLOSED via
  ``AnswerValidationError`` (invalid references are never silently
  removed, rewritten, or repaired; the answer is retained as
  untrusted output, never converted into an empty response);
- preserves the original objects by reference — the model cannot
  create provenance, evidence, or a new citation mapping.

Tenant handling: tenant identity is authoritative from the existing
evidence/prompt chain only; the validator verifies single-tenant
provenance fail-closed and never lets model text establish tenant
identity.

Security: the validator is pure domain logic — no code/SQL
execution, no tools, no filesystem, no network, no interpretation of
model output as instructions, no mutation of any input object.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from .errors import DomainValidationError
from .evidence_prompt import citation_label
from .llm import GeneratedAnswer

_CITATION_PATTERN = re.compile(r"\[E(\d+)\]")

VALIDATION_STATUS_VALID = "valid"
VALIDATION_STATUS_INVALID_CITATIONS = "invalid_citations"
VALIDATION_STATUS_EMPTY = "empty"


class AnswerValidationError(DomainValidationError):
    """An answer-validation integrity failure (fail closed).

    Distinct from ``LLMProviderError`` (Phase 5.11 operational /
    provider failures): this error means the model's output violated
    citation integrity or the validator received malformed input.
    It is never converted into an empty answer.
    """


@dataclass(frozen=True, slots=True)
class CitationExtraction:
    """Deterministic extraction result for one answer text.

    ``references`` preserves first-occurrence order and
    ``occurrences`` preserves every occurrence position, so repeated
    citations are handled deterministically without fuzz or
    normalization. ``label`` is the raw matched text (``[E7]``);
    ``index`` is the parsed number.
    """

    references: tuple[str, ...]
    occurrences: tuple[tuple[str, int], ...]

    @property
    def unique_labels(self) -> tuple[str, ...]:
        """First-occurrence-ordered unique labels."""
        return self.references

    def to_record(self) -> dict:
        return {
            "references": list(self.references),
            "occurrences": [
                {"label": label, "position": position}
                for label, position in self.occurrences
            ],
        }


def extract_citation_references(text: str) -> CitationExtraction:
    """Extract ``[E<n>]`` references from model text — strictly.

    Rules (deterministic, documented):

    - only the exact canonical syntax ``[E`` + digits + ``]`` matches;
    - no fuzzy matching, no partial matches, no normalization —
      ``[e1]``, ``E1``, ``[E1``, ``[Evidence 1]``, and ``[E007]``
      (leading zeros) are NOT citation references;
    - matches are collected in text order; ``references`` keeps
      first-occurrence order of unique labels, ``occurrences`` keeps
      every match with its character position;
    - malformed citation-like text is simply not a match — it is
      never repaired into one.
    """
    if not isinstance(text, str):
        raise DomainValidationError("answer text must be a string")
    occurrences: list[tuple[str, int]] = []
    references: list[str] = []
    seen: set[str] = set()
    for match in _CITATION_PATTERN.finditer(text):
        label = match.group(0)
        occurrences.append((label, match.start()))
        if label not in seen:
            seen.add(label)
            references.append(label)
    return CitationExtraction(
        references=tuple(references), occurrences=tuple(occurrences))


@dataclass(frozen=True, slots=True)
class ValidatedAnswer:
    """Immutable validation outcome — reference-preserving.

    The original ``GeneratedAnswer`` (and through it the
    ``EvidencePrompt``, ``PromptCitation`` objects, and the full
    Phase 5.9 provenance chain) is carried BY REFERENCE — never
    copied, reconstructed, or mutated. The original generated text
    remains recoverable verbatim via ``answer.answer_text``.

    ``status`` is one of:

    - ``valid`` — every extracted reference maps to the
      authoritative mapping (including the no-references case);
    - ``invalid_citations`` — at least one extracted reference does
      not exist in the authoritative mapping (available only on the
      non-raising path, see ``CitationAwareAnswerValidator``);
    - ``empty`` — the model produced no substantive output
      (Phase 5.11 policy respected; distinguishable from provider
      failure and from validation failure).

    ``validated_citations`` re-exposes the authoritative
    ``PromptCitation`` objects referenced by the answer, in
    first-occurrence order of the references. Model text never
    creates entries here.
    """

    answer: GeneratedAnswer
    status: str
    extraction: CitationExtraction
    validated_citations: tuple  # tuple[PromptCitation, ...]
    invalid_references: tuple[str, ...]
    tenant_id: Any

    @property
    def answer_text(self) -> str:
        """The original generated text, verbatim and unmodified."""
        return self.answer.answer_text

    @property
    def is_empty(self) -> bool:
        return self.status == VALIDATION_STATUS_EMPTY

    def to_record(self) -> dict:
        return {
            "status": self.status,
            "tenant_id": self.tenant_id,
            "extracted_references": list(self.extraction.references),
            "invalid_references": list(self.invalid_references),
            "validated_citations": [
                c.to_record() for c in self.validated_citations],
            "answer": self.answer.to_record(),
        }


@runtime_checkable
class AnswerValidator(Protocol):
    """Provider-independent answer-validation contract.

    Implementations are pure and deterministic: they consume a
    ``GeneratedAnswer`` and produce a ``ValidatedAnswer``, failing
    closed on integrity violations. They never execute model output,
    contact infrastructure, or mutate inputs.
    """

    def validate(self, answer: GeneratedAnswer) -> ValidatedAnswer:
        ...


class CitationAwareAnswerValidator:
    """Deterministic citation-integrity validator (pure domain logic).

    Invalid-citation policy (documented, fail closed): by default an
    extracted reference that does not exist in the authoritative
    mapping raises ``AnswerValidationError``. Invalid references are
    never silently removed, no citation is rewritten, no evidence is
    fabricated, and the answer is never repaired or converted into an
    empty response. Pass ``fail_on_invalid_citations=False`` to obtain
    a structured ``ValidatedAnswer`` with status
    ``invalid_citations`` instead — the raising and non-raising paths
    are mutually consistent, and the strict default is production
    behavior.

    Integrity checks (fail closed, before any classification):

    - ``GeneratedAnswer`` / prompt structure must be well-formed;
    - the authoritative citation mapping must exist and be
      duplicate-free (each ``[E<n>]`` index may appear at most once);
    - citation objects must be consistent
      (``citation.rank_position == selected.rank_position``);
    - the prompt's provenance must be single-tenant.

    Empty answers: an empty model output is a valid ``empty`` status —
    the Phase 5.11 policy is respected and emptiness stays distinct
    from provider failure and validation failure. (For a non-empty
    answer against an empty prompt, the empty mapping means any
    extracted reference is necessarily invalid — handled by the
    normal invalid-citation policy, never by fabrication.)

    Purity: no code/SQL execution, no tools, no filesystem, no
    network, no LLM calls, no interpretation of model output as
    instructions, and no mutation of any input object (frozen values
    are carried by reference).
    """

    def __init__(self, *, fail_on_invalid_citations: bool = True) -> None:
        self._fail_on_invalid = fail_on_invalid_citations

    def validate(self, answer: GeneratedAnswer) -> ValidatedAnswer:
        """Validate citation integrity of one generated answer."""
        if not isinstance(answer, GeneratedAnswer):
            raise AnswerValidationError(
                "a GeneratedAnswer is required")
        prompt = answer.prompt
        if prompt is None or not isinstance(
                getattr(prompt, "citations", None), tuple):
            raise AnswerValidationError(
                "answer carries no authoritative citation mapping")

        # Authoritative mapping integrity — duplicates and
        # inconsistencies fail closed before any classification.
        authoritative: dict[str, tuple[int, object]] = {}
        tenant_ids: set = set()
        for citation in prompt.citations:
            if not hasattr(citation, "label") or not isinstance(
                    citation.label, str):
                raise AnswerValidationError(
                    "authoritative citation mapping is malformed")
            label = citation.label
            if label in authoritative:
                raise AnswerValidationError(
                    "duplicate authoritative citation label")
            if citation.rank_position != (
                    citation.selected.rank_position):
                raise AnswerValidationError(
                    "citation identity is inconsistent with rank position")
            # The label must be exactly the canonical label of the
            # rank it names ([E1] is the rank-1 citation, and only
            # that one) — label/rank drift fails closed.
            if citation.label != citation_label(citation.rank_position):
                raise AnswerValidationError(
                    "citation label is inconsistent with rank position")
            evidence = citation.selected.ranked.evidence
            if evidence is None or evidence.tenant_id is None:
                raise AnswerValidationError(
                    "authoritative citation has no tenant identity")
            tenant_ids.add(evidence.tenant_id)
            authoritative[label] = (
                citation.rank_position, citation)

        if len(tenant_ids) > 1:
            raise AnswerValidationError(
                "authoritative citation mapping spans multiple tenants")
        tenant_id = (
            next(iter(tenant_ids)) if tenant_ids else prompt.tenant_id)

        # Empty answer: distinct valid state (Phase 5.11 policy).
        if answer.is_empty:
            return ValidatedAnswer(
                answer=answer,
                status=VALIDATION_STATUS_EMPTY,
                extraction=extract_citation_references(
                    answer.answer_text),
                validated_citations=(),
                invalid_references=(),
                tenant_id=tenant_id,
            )

        extraction = extract_citation_references(answer.answer_text)
        invalid: list[str] = []
        validated: list = []
        for label in extraction.references:
            entry = authoritative.get(label)
            if entry is None:
                invalid.append(label)
            else:
                validated.append(entry[1])

        if invalid and self._fail_on_invalid:
            raise AnswerValidationError(
                "answer references citation labels that do not exist "
                "in the authoritative citation mapping: "
                + ", ".join(sorted(set(invalid))))

        return ValidatedAnswer(
            answer=answer,
            status=(
                VALIDATION_STATUS_INVALID_CITATIONS
                if invalid else VALIDATION_STATUS_VALID),
            extraction=extraction,
            validated_citations=tuple(validated),
            invalid_references=tuple(invalid),
            tenant_id=tenant_id,
        )


__all__ = [
    "AnswerValidationError",
    "AnswerValidator",
    "CitationAwareAnswerValidator",
    "CitationExtraction",
    "ValidatedAnswer",
    "VALIDATION_STATUS_EMPTY",
    "VALIDATION_STATUS_INVALID_CITATIONS",
    "VALIDATION_STATUS_VALID",
    "extract_citation_references",
]
