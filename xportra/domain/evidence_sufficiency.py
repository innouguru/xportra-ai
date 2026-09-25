"""Evidence sufficiency, contradiction, and uncertainty reasoning for Phase 6.4.

Transparent reasoning about evidence quality — not a compliance decision
engine. This module derives structured evidence-quality state from the
already-authoritative deterministic state; it decides nothing:

```text
applicability + assessment (deterministic, trusted)
    + linked evidence counts (supporting vs conflicting)
    + validated knowledge presence
        ↓
EvidenceSufficiencyService.assess (this module — pure derivation)
        ↓
EvidenceSufficiencyAssessment
    (sufficiency / contradiction / typed missing items /
     deterministic sufficiency explanation)
        ↓
ComplianceReasoningService.analyze (carries the derived values
    onto ComplianceAnalysis; deterministic fields stay authoritative)
```

Sufficiency semantics (mirrors ``RequirementAssessmentService`` — no new
algorithm; category matching alone never satisfies, absence of evidence
is never a failure finding):

- ``supported`` — applicable with a decisive assessment (``satisfied``
  or ``not_satisfied``): the supplied evidence materially supports the
  deterministic assessment, in either direction.
- ``missing`` — applicable, ``unknown`` assessment, zero linked tenant
  evidence: a required fact/document/evidence item is absent.
- ``insufficient`` — applicable, ``unknown`` assessment, linked tenant
  evidence exists but does not establish the requirement.
- ``unknown`` — the deterministic machinery itself is undecided
  (``unknown`` applicability, or any non-applicable requirement whose
  assessment is necessarily ``unknown``): sufficiency cannot be
  determined from the supplied state.

The four states are never collapsed into one generic ``"uncertain"``
label, and ``missing``/``insufficient`` never become ``not_satisfied``
by themselves.

Contradiction semantics (the smallest safe representation — the domain
defines no conflict-resolution rule, so none is invented):

- ``none`` — no conflicting (rejected/archived) evidence linked.
- ``present`` — at least one conflicting item linked. Supporting and
  conflicting lists are both preserved with source/provenance and
  requirement association intact; the conflict is described, never
  resolved. No source precedence is applied: the project distinguishes
  authoritative regulatory sources from other guidance (ADR-0003) but
  defines no ordering among tenant evidence items.

Uncertainty uses the Phase 6.1 categorical model (``determined`` /
``uncertain`` / ``unknown``) unchanged. This module adds only the
deterministic *reason* it is surfaced (via ``sufficiency_explanation``
and typed missing items); it never emits percentages, probability
scores, calibrated confidence, or numeric model confidence. Model text
carrying numeric confidence claims (percentages or probabilities tied
to confidence language) fails closed via ``check_no_numeric_confidence``.
The check is deliberately narrow — bare quantities in quoted
requirements (``"Form NXP"``, ``"30 days"``, ``"[E1]"``) are not
confidence claims and are never flagged.

Missing information is typed (``MissingInformationItem``: requirement
association + machine-actionable kind + human detail) so consumers never
parse prose. Kinds reuse the deterministic vocabulary. The model never
invents a required document: typed items derive only from the supplied
deterministic context; model suggestions travel separately with the
``model observation:`` prefix (Phase 6.3).

This module performs no retrieval, no LLM invocation, no prompting, no
citation handling, no database access, and no persistence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from .errors import DomainValidationError

SUFFICIENCY_SUPPORTED = "supported"
SUFFICIENCY_INSUFFICIENT = "insufficient"
SUFFICIENCY_MISSING = "missing"
SUFFICIENCY_UNKNOWN = "unknown"

EVIDENCE_SUFFICIENCY_STATES = frozenset({
    SUFFICIENCY_SUPPORTED,
    SUFFICIENCY_INSUFFICIENT,
    SUFFICIENCY_MISSING,
    SUFFICIENCY_UNKNOWN,
})

CONTRADICTION_NONE = "none"
CONTRADICTION_PRESENT = "present"

CONTRADICTION_STATES = frozenset({
    CONTRADICTION_NONE,
    CONTRADICTION_PRESENT,
})

MISSING_KIND_APPLICABILITY_UNDETERMINED = "applicability_undetermined"
MISSING_KIND_ASSESSMENT_INCOMPLETE = "assessment_incomplete"
MISSING_KIND_EVIDENCE_ABSENT = "evidence_absent"
MISSING_KIND_EVIDENCE_INSUFFICIENT = "evidence_insufficient"
MISSING_KIND_KNOWLEDGE_UNCITED = "knowledge_uncited"
MISSING_KIND_EXPLANATION_ABSENT = "explanation_absent"
MISSING_KIND_SATISFYING_EVIDENCE_UNESTABLISHED = (
    "satisfying_evidence_unestablished")

MISSING_KINDS = frozenset({
    MISSING_KIND_APPLICABILITY_UNDETERMINED,
    MISSING_KIND_ASSESSMENT_INCOMPLETE,
    MISSING_KIND_EVIDENCE_ABSENT,
    MISSING_KIND_EVIDENCE_INSUFFICIENT,
    MISSING_KIND_KNOWLEDGE_UNCITED,
    MISSING_KIND_EXPLANATION_ABSENT,
    MISSING_KIND_SATISFYING_EVIDENCE_UNESTABLISHED,
})

# Numeric-confidence guard: a number is a confidence claim only when tied
# to confidence language. Bare quantities ("30 days", "[E1]", "Form NXP")
# never match.
_NUMERIC_CONFIDENCE_PATTERNS = (
    re.compile(
        r"(?i)\b(?:confidence|confident|probability|probable|likely"
        r"|certainty|certain|sure)\b[^.\n]{0,60}?\b\d+(?:\.\d+)?\s*%"),
    re.compile(
        r"(?i)\b\d+(?:\.\d+)?\s*%\s*(?:confidence|confident|probability"
        r"|probable|likely|certainty|certain|sure)\b"),
    re.compile(
        r"(?i)\b(?:confidence|probability)\b[^.\n]{0,40}?"
        r"(?:[:=]|\bis\b|\s)\s*(?:0?\.\d+|\d+(?:\.\d+)?\s*%)"),
    re.compile(
        r"(?i)\b(?:i am|i'm|we are|we're)\s+"
        r"(?:\d+(?:\.\d+)?\s*%|0?\.\d+)\s+"
        r"(?:confident|certain|sure)\b"),
)


class EvidenceSufficiencyError(DomainValidationError):
    """An evidence-sufficiency integrity failure (fail closed).

    Raised for malformed derivation inputs and for model text carrying
    numeric confidence claims — never converted into analysis content.
    """


@dataclass(frozen=True, slots=True)
class MissingInformationItem:
    """One missing-information gap bound to its requirement.

    ``kind`` is machine-actionable (no prose parsing); ``detail`` is the
    human-readable description grounded in the deterministic context.
    Deterministically derived only — the model invents no items here.
    """

    requirement_id: UUID
    kind: str
    detail: str

    def to_record(self) -> dict[str, Any]:
        return {
            "requirement_id": str(self.requirement_id),
            "kind": self.kind,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class EvidenceSufficiencyAssessment:
    """Derived evidence-quality state for one requirement (immutable).

    All fields derive from trusted deterministic state by fixed rules.
    """

    requirement_id: UUID
    sufficiency: str
    contradiction: str
    missing_items: tuple[MissingInformationItem, ...]
    sufficiency_explanation: str

    def to_record(self) -> dict[str, Any]:
        return {
            "requirement_id": str(self.requirement_id),
            "sufficiency": self.sufficiency,
            "contradiction": self.contradiction,
            "missing_items": [
                item.to_record() for item in self.missing_items],
            "sufficiency_explanation": self.sufficiency_explanation,
        }


def check_no_numeric_confidence(text: str) -> None:
    """Reject model text carrying numeric confidence claims (fail closed).

    Only model-sourced strings are ever checked — deterministic case
    content (reasons, references) is trusted and never inspected here.
    """
    if not isinstance(text, str):
        raise EvidenceSufficiencyError(
            "model text must be a string")
    for pattern in _NUMERIC_CONFIDENCE_PATTERNS:
        if pattern.search(text):
            raise EvidenceSufficiencyError(
                "model text carries a numeric confidence claim; "
                "categorical uncertainty only")


class EvidenceSufficiencyService:
    """Pure derivation of evidence-quality state (no decisions)."""

    def assess(
        self,
        *,
        requirement_id: UUID,
        applicability: str,
        assessment: str,
        supporting_count: int,
        conflicting_count: int,
        has_knowledge: bool,
        has_explanation: bool,
        applicability_reason: str | None = None,
        assessment_reason: str | None = None,
    ) -> EvidenceSufficiencyAssessment:
        """Derive sufficiency, contradiction, and typed gaps.

        Mirrors ``RequirementAssessmentService`` outcomes without
        reimplementing them: the caller supplies the authoritative
        outcomes and evidence counts; this method only classifies.
        """
        if not isinstance(requirement_id, UUID):
            raise EvidenceSufficiencyError(
                "requirement identity is malformed")
        if applicability not in (
                "applicable", "not_applicable", "unknown"):
            raise EvidenceSufficiencyError(
                "applicability outcome is malformed")
        if assessment not in ("satisfied", "not_satisfied", "unknown"):
            raise EvidenceSufficiencyError(
                "assessment outcome is malformed")
        for name, value in (
            ("supporting_count", supporting_count),
            ("conflicting_count", conflicting_count),
        ):
            if (isinstance(value, bool) or not isinstance(value, int)
                    or value < 0):
                raise EvidenceSufficiencyError(
                    f"{name} must be a non-negative integer")

        sufficiency = self._sufficiency(
            applicability, assessment,
            supporting_count + conflicting_count)
        contradiction = (
            CONTRADICTION_PRESENT if conflicting_count
            else CONTRADICTION_NONE)
        missing = self._missing_items(
            requirement_id=requirement_id,
            applicability=applicability,
            assessment=assessment,
            linked_count=supporting_count + conflicting_count,
            has_knowledge=has_knowledge,
            has_explanation=has_explanation,
            applicability_reason=applicability_reason,
            assessment_reason=assessment_reason,
        )
        explanation = self._explanation(
            sufficiency=sufficiency,
            contradiction=contradiction,
            applicability=applicability,
            assessment=assessment,
            conflicting_count=conflicting_count,
        )
        return EvidenceSufficiencyAssessment(
            requirement_id=requirement_id,
            sufficiency=sufficiency,
            contradiction=contradiction,
            missing_items=missing,
            sufficiency_explanation=explanation,
        )

    # ------------------------------------------------------------------
    # deterministic derivation (fail closed)
    # ------------------------------------------------------------------

    @staticmethod
    def _sufficiency(
        applicability: str,
        assessment: str,
        linked_count: int,
    ) -> str:
        if applicability != "applicable":
            return SUFFICIENCY_UNKNOWN
        if assessment in ("satisfied", "not_satisfied"):
            return SUFFICIENCY_SUPPORTED
        if linked_count == 0:
            return SUFFICIENCY_MISSING
        return SUFFICIENCY_INSUFFICIENT

    @staticmethod
    def _missing_items(
        *,
        requirement_id: UUID,
        applicability: str,
        assessment: str,
        linked_count: int,
        has_knowledge: bool,
        has_explanation: bool,
        applicability_reason: str | None,
        assessment_reason: str | None,
    ) -> tuple[MissingInformationItem, ...]:
        items: list[MissingInformationItem] = []

        def add(kind: str, detail: str) -> None:
            items.append(MissingInformationItem(
                requirement_id=requirement_id,
                kind=kind,
                detail=detail,
            ))

        if applicability == "unknown":
            add(
                MISSING_KIND_APPLICABILITY_UNDETERMINED,
                "applicability undetermined: "
                f"{applicability_reason or 'no reason recorded'}",
            )
        if applicability == "applicable" and assessment == "unknown":
            add(
                MISSING_KIND_ASSESSMENT_INCOMPLETE,
                "assessment incomplete: "
                f"{assessment_reason or 'no reason recorded'}",
            )
            if linked_count == 0:
                add(
                    MISSING_KIND_EVIDENCE_ABSENT,
                    "no tenant evidence linked to this requirement",
                )
            else:
                add(
                    MISSING_KIND_EVIDENCE_INSUFFICIENT,
                    "linked tenant evidence exists but does not "
                    "establish the requirement",
                )
            if not has_knowledge:
                add(
                    MISSING_KIND_KNOWLEDGE_UNCITED,
                    "no retrieved knowledge evidence cited",
                )
        if (applicability == "applicable"
                and assessment == "not_satisfied"):
            add(
                MISSING_KIND_SATISFYING_EVIDENCE_UNESTABLISHED,
                "satisfying evidence not established: "
                f"{assessment_reason or 'no reason recorded'}",
            )
        if not has_explanation:
            add(
                MISSING_KIND_EXPLANATION_ABSENT,
                "model produced no explanation",
            )
        return tuple(items)

    @staticmethod
    def _explanation(
        *,
        sufficiency: str,
        contradiction: str,
        applicability: str,
        assessment: str,
        conflicting_count: int,
    ) -> str:
        if sufficiency == SUFFICIENCY_SUPPORTED:
            text = (
                "supplied evidence materially supports the "
                f"'{assessment}' assessment; the deterministic state "
                "is unchanged by this explanation"
            )
        elif sufficiency == SUFFICIENCY_MISSING:
            text = (
                "no tenant evidence linked to this requirement; "
                "absence of evidence is not a failure finding — "
                "the assessment remains 'unknown'"
            )
        elif sufficiency == SUFFICIENCY_INSUFFICIENT:
            text = (
                "linked evidence exists but does not establish the "
                "requirement; the assessment remains 'unknown' and "
                "is not treated as satisfied or not satisfied"
            )
        else:
            if applicability == "unknown":
                text = (
                    "the deterministic machinery is undecided on "
                    "applicability; evidence sufficiency cannot be "
                    "determined from the supplied state"
                )
            else:
                text = (
                    "the requirement is not applicable, so no "
                    "assessment was performed; evidence sufficiency "
                    "is not decidable"
                )
        if contradiction == CONTRADICTION_PRESENT:
            text += (
                f"; {conflicting_count} conflicting evidence item(s) "
                "preserved without resolution — no source precedence "
                "applied and no document judged authoritative"
            )
        return text


__all__ = [
    "CONTRADICTION_NONE",
    "CONTRADICTION_PRESENT",
    "CONTRADICTION_STATES",
    "EVIDENCE_SUFFICIENCY_STATES",
    "MISSING_KINDS",
    "MISSING_KIND_APPLICABILITY_UNDETERMINED",
    "MISSING_KIND_ASSESSMENT_INCOMPLETE",
    "MISSING_KIND_EVIDENCE_ABSENT",
    "MISSING_KIND_EVIDENCE_INSUFFICIENT",
    "MISSING_KIND_EXPLANATION_ABSENT",
    "MISSING_KIND_KNOWLEDGE_UNCITED",
    "MISSING_KIND_SATISFYING_EVIDENCE_UNESTABLISHED",
    "SUFFICIENCY_INSUFFICIENT",
    "SUFFICIENCY_MISSING",
    "SUFFICIENCY_SUPPORTED",
    "SUFFICIENCY_UNKNOWN",
    "EvidenceSufficiencyAssessment",
    "EvidenceSufficiencyError",
    "EvidenceSufficiencyService",
    "MissingInformationItem",
    "check_no_numeric_confidence",
]
