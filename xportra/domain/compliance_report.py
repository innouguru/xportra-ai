"""Case-level compliance analysis report composition for Phase 6.2.

Composition (not a decision engine): multiple existing
per-requirement ``ComplianceAnalysis`` objects plus the existing
deterministic decision state are joined into one structured,
immutable report for later API/UI consumption:

```text
ComplianceAnalysis[]            (Phase 6.1 — per requirement)
    + decision_summary dict     (Phase 3.5 — authoritative
                                 applicability/risk/action state)
        ↓
ComplianceReportService.compose (this module — deterministic)
        ↓
ComplianceAnalysisReport        (ordered analyses + aggregates
                                 + referenced decision state)
```

No new verdict. The report carries NO overall compliance
status field: authoritative case-level state arrives only via
the referenced Phase 3.5 decision summary (risk, actions,
applicability counts as that service computed them). Counts in
this report are composition arithmetic over analysis outcomes
only — never parsed from explanation prose, never inferred,
never converted across states (``not_applicable`` is never
``satisfied``; ``unknown`` stays ``unknown``).

Ordering is deterministic and documented: analyses are ordered
by ascending stringified ``requirement_id`` (the Phase 3.x
convention), never by database or insertion order. Duplicate
requirement identity is rejected explicitly — conflicting
analyses for one requirement are never silently merged or
dropped.

This module performs no retrieval, no LLM invocation, no
prompting, no validation beyond structural composition checks,
no database access, and no persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from .compliance_reasoning import (
    CERTAINTY_UNCERTAIN,
    ComplianceAnalysis,
)
from .errors import DomainValidationError, require_tenant_context


class ComplianceReportError(DomainValidationError):
    """A report-composition integrity failure (fail closed).

    Raised for malformed analyses, duplicate requirement
    identity, tenant/case inconsistency, and malformed
    decision-summary references — never converted into a
    fabricated report.
    """


@dataclass(frozen=True, slots=True)
class RequirementMissingInformation:
    """Missing-information items bound to their requirement.

    Association is preserved structurally: a future UI renders
    each requirement's gaps without parsing prose and without
    confusing one requirement's gaps for another's.
    """

    requirement_id: UUID
    items: tuple[str, ...]

    def to_record(self) -> dict[str, Any]:
        return {
            "requirement_id": str(self.requirement_id),
            "items": list(self.items),
        }


@dataclass(frozen=True, slots=True)
class ComplianceAnalysisReport:
    """Immutable case-level composition of per-requirement analyses.

    ``analyses`` preserves the original ``ComplianceAnalysis``
    objects (typed evidence/knowledge/source references intact —
    never flattened into strings, never re-associated).
    ``decision_summary`` is the caller-supplied Phase 3.5 summary
    carried by reference, not recomputed. Aggregate counts are
    derived from analysis outcomes alone; explanation text is
    never consulted.
    """

    id: UUID
    tenant_id: UUID
    case_id: UUID
    context_fingerprint: str | None
    analyses: tuple[ComplianceAnalysis, ...]
    total_requirements: int
    applicable_count: int
    satisfied_count: int
    not_satisfied_count: int
    unknown_count: int
    not_applicable_count: int
    requirements_with_missing_information: tuple[UUID, ...]
    missing_information: tuple[RequirementMissingInformation, ...]
    uncertain_requirement_ids: tuple[UUID, ...]
    requirements_with_conflicting_evidence: tuple[UUID, ...]
    conflicting_evidence_count: int
    decision_summary: dict[str, Any] | None

    @property
    def is_empty(self) -> bool:
        """True when the report composes zero analyses."""
        return self.total_requirements == 0

    def to_record(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "case_id": str(self.case_id),
            "context_fingerprint": self.context_fingerprint,
            "is_empty": self.is_empty,
            "total_requirements": self.total_requirements,
            "applicable_count": self.applicable_count,
            "satisfied_count": self.satisfied_count,
            "not_satisfied_count": self.not_satisfied_count,
            "unknown_count": self.unknown_count,
            "not_applicable_count": self.not_applicable_count,
            "requirements_with_missing_information": [
                str(value) for value in
                self.requirements_with_missing_information],
            "missing_information": [
                entry.to_record()
                for entry in self.missing_information],
            "uncertain_requirement_ids": [
                str(value)
                for value in self.uncertain_requirement_ids],
            "requirements_with_conflicting_evidence": [
                str(value) for value in
                self.requirements_with_conflicting_evidence],
            "conflicting_evidence_count":
                self.conflicting_evidence_count,
            "analyses": [a.to_record() for a in self.analyses],
            "decision_summary": self.decision_summary,
        }


class ComplianceReportService:
    """Deterministic composition of analyses into a case report."""

    def compose(
        self,
        analyses: list[ComplianceAnalysis] | tuple[ComplianceAnalysis, ...],
        *,
        tenant_id: Any,
        case_id: UUID,
        context_fingerprint: str | None = None,
        decision_summary: dict[str, Any] | None = None,
    ) -> ComplianceAnalysisReport:
        """Join per-requirement analyses into one ordered report."""
        require_tenant_context(tenant_id)
        tenant_uuid = tenant_id.tenant_id
        ordered = self._ordered_analyses(analyses, tenant_uuid)
        self._check_case_identity(case_id, context_fingerprint)
        summary = self._check_decision_summary(
            decision_summary, tenant_uuid)

        counts = self._counts(ordered)
        missing_ids: list[UUID] = []
        missing_entries: list[RequirementMissingInformation] = []
        uncertain_ids: list[UUID] = []
        conflicting_ids: list[UUID] = []
        conflicting_total = 0
        for analysis in ordered:
            if analysis.missing_information:
                missing_ids.append(analysis.requirement_id)
                missing_entries.append(
                    RequirementMissingInformation(
                        requirement_id=analysis.requirement_id,
                        items=analysis.missing_information,
                    )
                )
            if analysis.uncertainty == CERTAINTY_UNCERTAIN:
                uncertain_ids.append(analysis.requirement_id)
            if analysis.conflicting_evidence:
                conflicting_ids.append(analysis.requirement_id)
                conflicting_total += len(analysis.conflicting_evidence)

        report_id = uuid5(
            NAMESPACE_URL,
            ":".join([
                str(tenant_uuid),
                str(case_id),
                *[str(a.requirement_id) for a in ordered],
                *[str(a.id) for a in ordered],
            ]),
        )
        return ComplianceAnalysisReport(
            id=report_id,
            tenant_id=tenant_uuid,
            case_id=case_id,
            context_fingerprint=context_fingerprint,
            analyses=ordered,
            total_requirements=len(ordered),
            applicable_count=counts["applicable"],
            satisfied_count=counts["satisfied"],
            not_satisfied_count=counts["not_satisfied"],
            unknown_count=counts["unknown"],
            not_applicable_count=counts["not_applicable"],
            requirements_with_missing_information=tuple(missing_ids),
            missing_information=tuple(missing_entries),
            uncertain_requirement_ids=tuple(uncertain_ids),
            requirements_with_conflicting_evidence=tuple(
                conflicting_ids),
            conflicting_evidence_count=conflicting_total,
            decision_summary=summary,
        )

    # ------------------------------------------------------------------
    # deterministic composition (fail closed)
    # ------------------------------------------------------------------

    @staticmethod
    def _ordered_analyses(
        analyses: list[ComplianceAnalysis]
        | tuple[ComplianceAnalysis, ...],
        tenant_uuid: UUID,
    ) -> tuple[ComplianceAnalysis, ...]:
        if isinstance(analyses, (str, bytes, dict)) or not isinstance(
                analyses, (list, tuple)):
            raise ComplianceReportError(
                "requirement analyses must be a list or tuple")
        seen: set[UUID] = set()
        for analysis in analyses:
            if not isinstance(analysis, ComplianceAnalysis):
                raise ComplianceReportError(
                    "report composes ComplianceAnalysis objects only")
            if analysis.tenant_id != tenant_uuid:
                raise ComplianceReportError(
                    "analysis belongs to a different tenant")
            if analysis.requirement_id in seen:
                raise ComplianceReportError(
                    "duplicate requirement identity in report")
            seen.add(analysis.requirement_id)
        return tuple(sorted(
            analyses, key=lambda a: str(a.requirement_id)))

    @staticmethod
    def _check_case_identity(
        case_id: UUID, context_fingerprint: str | None
    ) -> None:
        if not isinstance(case_id, UUID):
            raise ComplianceReportError(
                "a case identity UUID is required")
        if context_fingerprint is not None and (
                not isinstance(context_fingerprint, str)
                or not context_fingerprint.strip()):
            raise ComplianceReportError(
                "context fingerprint must be a non-empty string")

    @staticmethod
    def _check_decision_summary(
        decision_summary: dict[str, Any] | None,
        tenant_uuid: UUID,
    ) -> dict[str, Any] | None:
        if decision_summary is None:
            return None
        if not isinstance(decision_summary, dict):
            raise ComplianceReportError(
                "decision summary must be a mapping")
        summary_tenant = decision_summary.get("tenant_id")
        if summary_tenant is not None and (
                summary_tenant != tenant_uuid):
            raise ComplianceReportError(
                "decision summary belongs to a different tenant")
        return decision_summary

    @staticmethod
    def _counts(
        ordered: tuple[ComplianceAnalysis, ...]
    ) -> dict[str, int]:
        counts = {
            "applicable": 0,
            "satisfied": 0,
            "not_satisfied": 0,
            "unknown": 0,
            "not_applicable": 0,
        }
        for analysis in ordered:
            applicability = analysis.applicability
            assessment = analysis.assessment
            if applicability == "applicable":
                counts["applicable"] += 1
                if assessment == "satisfied":
                    counts["satisfied"] += 1
                elif assessment == "not_satisfied":
                    counts["not_satisfied"] += 1
                elif assessment == "unknown":
                    counts["unknown"] += 1
                else:  # pragma: no cover - 6.1 rejects this first
                    raise ComplianceReportError(
                        "analysis carries an unknown assessment state")
            elif applicability == "not_applicable":
                counts["not_applicable"] += 1
            elif applicability == "unknown":
                counts["unknown"] += 1
            else:  # pragma: no cover - 6.1 rejects this first
                raise ComplianceReportError(
                    "analysis carries an unknown applicability state")
        accounted = (
            counts["satisfied"] + counts["not_satisfied"]
            + counts["unknown"] + counts["not_applicable"]
        )
        if accounted != len(ordered):
            raise ComplianceReportError(
                "aggregate counts do not partition the analyses")
        return counts


__all__ = [
    "ComplianceAnalysisReport",
    "ComplianceReportError",
    "ComplianceReportService",
    "RequirementMissingInformation",
]
