"""Application-facing DTOs translated from domain records.

Every DTO is an explicit allow-list: translators select
named fields from domain ``to_record()`` output (or from
live in-session result/package objects where the domain
holds no record form) and reject malformed input with
``ApplicationValidationError``. Internal frozen domain
objects are never exposed directly.

Deliberate exclusions (never selected, even though the
domain records carry them):

- ``input_fingerprints`` (round entries),
  ``content_fingerprint`` (knowledge references), and
  ``answer_fingerprint`` — internal implementation
  fingerprints. Rounds stay distinguishable by
  ``round_index`` plus report/analysis/trace identities;
  citations stay traceable by label/chunk/document/source
  references. Fingerprints remain server-side in the
  domain views.
- prompts, model identifiers, raw provider responses,
  chain-of-thought — provider internals stay server-side.
- secrets, credentials, database rows beyond the
  explicitly listed evidence fields.

Deliberate inclusions by reference (carried, not
remodeled):

- Phase 6 nested provenance records (supporting /
  conflicting evidence, knowledge references, sources,
  missing items) are stable plain-data provenance
  contracts; the finding DTO selects *which sections*
  appear but does not remodel their items.
- The Phase 3.5 decision summary is an existing
  plain-data authority carried by reference in the final
  package DTO only — never reinterpreted, never scored.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from xportra.domain.compliance_workflow import AssessmentPackage
from xportra.domain.reasoning_application import (
    ComplianceReasoningResult,
)

from .errors import ApplicationValidationError

_REPORT_COUNT_KEYS = (
    "total_requirements",
    "applicable_count",
    "satisfied_count",
    "not_satisfied_count",
    "unknown_count",
    "not_applicable_count",
)


def _uuid_string(value: Any, field: str) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as cause:
        raise ApplicationValidationError(
            f"malformed {field} identity") from cause


def _uuid_list(values: Any, field: str) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ApplicationValidationError(
            f"malformed {field} identities")
    return tuple(_uuid_string(v, field) for v in values)


def _require_mapping(record: Any, name: str) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ApplicationValidationError(
            f"malformed {name} record")
    return record


def _require_text(record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str):
        raise ApplicationValidationError(
            f"malformed {field}")
    return value


@dataclass(frozen=True, slots=True)
class ShipmentDTO:
    """Shipment identity for a workflow's case."""

    tenant_id: str
    shipment_id: str
    case_id: str

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> ShipmentDTO:
        record = _require_mapping(record, "shipment")
        return cls(
            tenant_id=_uuid_string(
                record.get("tenant_id"), "tenant"),
            shipment_id=_uuid_string(
                record.get("shipment_id"), "shipment"),
            case_id=_uuid_string(
                record.get("case_id"), "case"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "shipment_id": self.shipment_id,
            "case_id": self.case_id,
        }


@dataclass(frozen=True, slots=True)
class EvidenceReferenceDTO:
    """Domain evidence reference supplied for a case."""

    evidence_id: str
    case_id: str
    requirement_id: str | None

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> EvidenceReferenceDTO:
        record = _require_mapping(record, "evidence reference")
        requirement_id = record.get("requirement_id")
        return cls(
            evidence_id=_uuid_string(
                record.get("evidence_id"), "evidence"),
            case_id=_uuid_string(
                record.get("case_id"), "case"),
            requirement_id=(
                None if requirement_id is None
                else _uuid_string(requirement_id, "requirement")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "case_id": self.case_id,
            "requirement_id": self.requirement_id,
        }


@dataclass(frozen=True, slots=True)
class EvidenceRecordDTO:
    """Recorded evidence artifact identity (never contents)."""

    evidence_id: str
    tenant_id: str
    document_title: str | None
    document_type: str | None
    status: str | None

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> EvidenceRecordDTO:
        record = _require_mapping(record, "evidence")
        for field in ("document_title", "document_type", "status"):
            value = record.get(field)
            if value is not None and not isinstance(value, str):
                raise ApplicationValidationError(
                    f"malformed evidence {field}")
        return cls(
            evidence_id=_uuid_string(
                record.get("id"), "evidence"),
            tenant_id=_uuid_string(
                record.get("tenant_id"), "tenant"),
            document_title=record.get("document_title"),
            document_type=record.get("document_type"),
            status=record.get("status"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "tenant_id": self.tenant_id,
            "document_title": self.document_title,
            "document_type": self.document_type,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class AnalysisRoundDTO:
    """One completed analysis round (references only)."""

    round_index: int
    report_id: str
    analysis_ids: tuple[str, ...]
    trace_ids: tuple[str, ...]

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> AnalysisRoundDTO:
        record = _require_mapping(record, "analysis round")
        round_index = record.get("round_index")
        if not isinstance(round_index, int) or round_index < 1:
            raise ApplicationValidationError(
                "malformed round index")
        return cls(
            round_index=round_index,
            report_id=_uuid_string(
                record.get("report_id"), "report"),
            analysis_ids=_uuid_list(
                record.get("analysis_ids"), "analysis"),
            trace_ids=_uuid_list(
                record.get("trace_ids"), "trace"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_index": self.round_index,
            "report_id": self.report_id,
            "analysis_ids": list(self.analysis_ids),
            "trace_ids": list(self.trace_ids),
        }


@dataclass(frozen=True, slots=True)
class WorkflowDTO:
    """Client view of workflow progression state."""

    workflow_id: str
    tenant_id: str
    case_id: str
    shipment_id: str | None
    state: str
    is_closed: bool
    round_count: int
    rounds: tuple[AnalysisRoundDTO, ...]
    supplied_evidence_ids: tuple[str, ...]
    open_requirements: tuple[str, ...]

    @classmethod
    def from_record(cls, record: dict[str, Any], *,
                    is_closed: bool) -> WorkflowDTO:
        record = _require_mapping(record, "workflow")
        shipment_id = record.get("shipment_id")
        return cls(
            workflow_id=_uuid_string(
                record.get("id"), "workflow"),
            tenant_id=_uuid_string(
                record.get("tenant_id"), "tenant"),
            case_id=_uuid_string(
                record.get("case_id"), "case"),
            shipment_id=(
                None if shipment_id is None
                else _uuid_string(shipment_id, "shipment")),
            state=_require_text(record, "state"),
            is_closed=bool(is_closed),
            round_count=len(_rounds(record)),
            rounds=tuple(
                AnalysisRoundDTO.from_record(item)
                for item in _rounds(record)),
            supplied_evidence_ids=_uuid_list(
                record.get("supplied_evidence_ids"), "evidence"),
            open_requirements=_uuid_list(
                record.get("open_requirements"), "requirement"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "tenant_id": self.tenant_id,
            "case_id": self.case_id,
            "shipment_id": self.shipment_id,
            "state": self.state,
            "is_closed": self.is_closed,
            "round_count": self.round_count,
            "rounds": [r.to_dict() for r in self.rounds],
            "supplied_evidence_ids": list(
                self.supplied_evidence_ids),
            "open_requirements": list(self.open_requirements),
        }


def _rounds(record: dict[str, Any]) -> list[Any]:
    rounds = record.get("rounds")
    if not isinstance(rounds, list):
        raise ApplicationValidationError("malformed rounds")
    return rounds


@dataclass(frozen=True, slots=True)
class RequirementFindingDTO:
    """One requirement's findings with carried provenance."""

    analysis_id: str
    requirement_id: str
    requirement_text: str
    applicability: str
    assessment: str
    explanation: str
    uncertainty: str
    uncertainty_explanation: str
    evidence_sufficiency: str
    sufficiency_explanation: str
    contradiction_state: str
    missing_information: tuple[str, ...]
    supporting_evidence: tuple[dict[str, Any], ...]
    conflicting_evidence: tuple[dict[str, Any], ...]
    knowledge_references: tuple[dict[str, Any], ...]
    sources: tuple[dict[str, Any], ...]
    missing_items: tuple[dict[str, Any], ...]

    @classmethod
    def from_record(cls, record: dict[str, Any],
                    ) -> RequirementFindingDTO:
        record = _require_mapping(record, "analysis")
        return cls(
            analysis_id=_uuid_string(
                record.get("id"), "analysis"),
            requirement_id=_uuid_string(
                record.get("requirement_id"), "requirement"),
            requirement_text=_require_text(
                record, "requirement_text"),
            applicability=_require_text(
                record, "applicability"),
            assessment=_require_text(record, "assessment"),
            explanation=_require_text(record, "explanation"),
            uncertainty=_require_text(record, "uncertainty"),
            uncertainty_explanation=_require_text(
                record, "uncertainty_explanation"),
            evidence_sufficiency=_require_text(
                record, "evidence_sufficiency"),
            sufficiency_explanation=_require_text(
                record, "sufficiency_explanation"),
            contradiction_state=_require_text(
                record, "contradiction_state"),
            missing_information=_text_list(
                record.get("missing_information")),
            supporting_evidence=_provenance_list(
                record.get("supporting_evidence")),
            conflicting_evidence=_provenance_list(
                record.get("conflicting_evidence")),
            knowledge_references=_knowledge_list(
                record.get("knowledge_references")),
            sources=_provenance_list(record.get("sources")),
            missing_items=_provenance_list(
                record.get("missing_items")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "requirement_id": self.requirement_id,
            "requirement_text": self.requirement_text,
            "applicability": self.applicability,
            "assessment": self.assessment,
            "explanation": self.explanation,
            "uncertainty": self.uncertainty,
            "uncertainty_explanation": (
                self.uncertainty_explanation),
            "evidence_sufficiency": self.evidence_sufficiency,
            "sufficiency_explanation": (
                self.sufficiency_explanation),
            "contradiction_state": self.contradiction_state,
            "missing_information": list(
                self.missing_information),
            "supporting_evidence": list(
                self.supporting_evidence),
            "conflicting_evidence": list(
                self.conflicting_evidence),
            "knowledge_references": list(
                self.knowledge_references),
            "sources": list(self.sources),
            "missing_items": list(self.missing_items),
        }


def _text_list(values: Any) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        raise ApplicationValidationError(
            "malformed missing information")
    for value in values:
        if not isinstance(value, str):
            raise ApplicationValidationError(
                "malformed missing information")
    return tuple(values)


def _provenance_list(values: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(values, (list, tuple)):
        raise ApplicationValidationError(
            "malformed provenance references")
    for value in values:
        if not isinstance(value, dict):
            raise ApplicationValidationError(
                "malformed provenance references")
    return tuple(values)


def _knowledge_list(values: Any) -> tuple[dict[str, Any], ...]:
    """Knowledge references without internal fingerprints."""
    return tuple(
        {key: value for key, value in item.items()
         if key != "content_fingerprint"}
        for item in _provenance_list(values)
    )


@dataclass(frozen=True, slots=True)
class AnalysisReportDTO:
    """Case-level report: counts plus per-requirement findings."""

    report_id: str
    case_id: str
    counts: dict[str, int]
    requirements_with_missing_information: tuple[str, ...]
    uncertain_requirement_ids: tuple[str, ...]
    requirements_with_conflicting_evidence: tuple[str, ...]
    conflicting_evidence_count: int
    findings: tuple[RequirementFindingDTO, ...]

    @classmethod
    def from_result(cls, result: ComplianceReasoningResult,
                    ) -> AnalysisReportDTO:
        if not isinstance(result, ComplianceReasoningResult):
            raise ApplicationValidationError(
                "malformed reasoning result")
        return cls.from_record(result.report.to_record())

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> AnalysisReportDTO:
        record = _require_mapping(record, "report")
        counts = {}
        for key in _REPORT_COUNT_KEYS:
            value = record.get(key)
            if not isinstance(value, int):
                raise ApplicationValidationError(
                    f"malformed report {key}")
            counts[key] = value
        analyses = record.get("analyses")
        if not isinstance(analyses, list):
            raise ApplicationValidationError(
                "malformed report analyses")
        conflicting = record.get("conflicting_evidence_count")
        if not isinstance(conflicting, int):
            raise ApplicationValidationError(
                "malformed conflicting evidence count")
        return cls(
            report_id=_uuid_string(
                record.get("id"), "report"),
            case_id=_uuid_string(
                record.get("case_id"), "case"),
            counts=counts,
            requirements_with_missing_information=_uuid_list(
                record.get(
                    "requirements_with_missing_information"),
                "requirement"),
            uncertain_requirement_ids=_uuid_list(
                record.get("uncertain_requirement_ids"),
                "requirement"),
            requirements_with_conflicting_evidence=_uuid_list(
                record.get(
                    "requirements_with_conflicting_evidence"),
                "requirement"),
            conflicting_evidence_count=conflicting,
            findings=tuple(
                RequirementFindingDTO.from_record(item)
                for item in analyses),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "case_id": self.case_id,
            "counts": dict(self.counts),
            "requirements_with_missing_information": list(
                self.requirements_with_missing_information),
            "uncertain_requirement_ids": list(
                self.uncertain_requirement_ids),
            "requirements_with_conflicting_evidence": list(
                self.requirements_with_conflicting_evidence),
            "conflicting_evidence_count": (
                self.conflicting_evidence_count),
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass(frozen=True, slots=True)
class ReadinessDTO:
    """Finalization readiness: outcome plus reason codes."""

    ready: bool
    reasons: tuple[tuple[str, str], ...]

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> ReadinessDTO:
        record = _require_mapping(record, "readiness")
        ready = record.get("ready")
        reasons = record.get("reasons")
        if not isinstance(ready, bool):
            raise ApplicationValidationError(
                "malformed readiness outcome")
        if not isinstance(reasons, list):
            raise ApplicationValidationError(
                "malformed readiness reasons")
        parsed = []
        for item in reasons:
            if (not isinstance(item, dict)
                    or not isinstance(item.get("code"), str)
                    or not isinstance(item.get("detail"), str)):
                raise ApplicationValidationError(
                    "malformed readiness reasons")
            parsed.append((item["code"], item["detail"]))
        return cls(ready=ready, reasons=tuple(parsed))

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "reasons": [
                {"code": code, "detail": detail}
                for code, detail in self.reasons
            ],
        }


@dataclass(frozen=True, slots=True)
class HistoryEntryDTO:
    """One history entry (identifiers only).

    ``input_fingerprint`` references are dropped: rounds
    stay distinguishable by index plus report/analysis/
    trace identities, and fingerprints remain server-side.
    """

    sequence: int
    kind: str
    detail: str
    references: tuple[tuple[str, str], ...]

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> HistoryEntryDTO:
        record = _require_mapping(record, "history entry")
        sequence = record.get("sequence")
        references = record.get("references")
        if not isinstance(sequence, int):
            raise ApplicationValidationError(
                "malformed history sequence")
        if not isinstance(references, list):
            raise ApplicationValidationError(
                "malformed history references")
        parsed = []
        for item in references:
            if (not isinstance(item, dict)
                    or not isinstance(item.get("label"), str)
                    or not isinstance(item.get("value"), str)):
                raise ApplicationValidationError(
                    "malformed history references")
            if item["label"] == "input_fingerprint":
                continue
            parsed.append((item["label"], item["value"]))
        return cls(
            sequence=sequence,
            kind=_require_text(record, "kind"),
            detail=_require_text(record, "detail"),
            references=tuple(parsed),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "kind": self.kind,
            "detail": self.detail,
            "references": [
                {"label": label, "value": value}
                for label, value in self.references
            ],
        }


@dataclass(frozen=True, slots=True)
class PackageReferenceDTO:
    """Identity-only final-package reference."""

    workflow_id: str
    report_id: str
    round_count: int
    decision_summary_present: bool

    @classmethod
    def from_record(cls, record: dict[str, Any],
                    ) -> PackageReferenceDTO:
        record = _require_mapping(record, "package reference")
        round_count = record.get("round_count")
        present = record.get("decision_summary_present")
        if not isinstance(round_count, int):
            raise ApplicationValidationError(
                "malformed package round count")
        if not isinstance(present, bool):
            raise ApplicationValidationError(
                "malformed package summary flag")
        return cls(
            workflow_id=_uuid_string(
                record.get("workflow_id"), "workflow"),
            report_id=_uuid_string(
                record.get("report_id"), "report"),
            round_count=round_count,
            decision_summary_present=present,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "report_id": self.report_id,
            "round_count": self.round_count,
            "decision_summary_present": (
                self.decision_summary_present),
        }


@dataclass(frozen=True, slots=True)
class HistoryDTO:
    """Client view of workflow history."""

    workflow_id: str
    tenant_id: str
    case_id: str
    shipment_id: str | None
    state: str
    entries: tuple[HistoryEntryDTO, ...]
    round_count: int
    latest_report_id: str | None
    decision_summary_present: bool
    readiness: ReadinessDTO | None
    final_package: PackageReferenceDTO | None

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> HistoryDTO:
        record = _require_mapping(record, "history view")
        shipment_id = record.get("shipment_id")
        latest_report_id = record.get("latest_report_id")
        readiness = record.get("readiness")
        final_package = record.get("final_package")
        entries = record.get("entries")
        round_count = record.get("round_count")
        present = record.get("decision_summary_present")
        if not isinstance(entries, list):
            raise ApplicationValidationError(
                "malformed history entries")
        if not isinstance(round_count, int):
            raise ApplicationValidationError(
                "malformed history round count")
        if not isinstance(present, bool):
            raise ApplicationValidationError(
                "malformed history summary flag")
        return cls(
            workflow_id=_uuid_string(
                record.get("workflow_id"), "workflow"),
            tenant_id=_uuid_string(
                record.get("tenant_id"), "tenant"),
            case_id=_uuid_string(
                record.get("case_id"), "case"),
            shipment_id=(
                None if shipment_id is None
                else _uuid_string(shipment_id, "shipment")),
            state=_require_text(record, "state"),
            entries=tuple(
                HistoryEntryDTO.from_record(item)
                for item in entries),
            round_count=round_count,
            latest_report_id=(
                None if latest_report_id is None
                else _uuid_string(latest_report_id, "report")),
            decision_summary_present=present,
            readiness=(
                None if readiness is None
                else ReadinessDTO.from_record(readiness)),
            final_package=(
                None if final_package is None
                else PackageReferenceDTO.from_record(
                    final_package)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "tenant_id": self.tenant_id,
            "case_id": self.case_id,
            "shipment_id": self.shipment_id,
            "state": self.state,
            "entries": [e.to_dict() for e in self.entries],
            "round_count": self.round_count,
            "latest_report_id": self.latest_report_id,
            "decision_summary_present": (
                self.decision_summary_present),
            "readiness": (
                None if self.readiness is None
                else self.readiness.to_dict()),
            "final_package": (
                None if self.final_package is None
                else self.final_package.to_dict()),
        }


@dataclass(frozen=True, slots=True)
class FinalPackageDTO:
    """Client view of the final assessment package."""

    workflow_id: str
    tenant_id: str
    case_id: str
    shipment_id: str | None
    state: str
    round_count: int
    open_requirements: tuple[str, ...]
    report: AnalysisReportDTO
    decision_summary: dict[str, Any] | None

    @classmethod
    def from_package(cls, package: AssessmentPackage,
                     ) -> FinalPackageDTO:
        if not isinstance(package, AssessmentPackage):
            raise ApplicationValidationError(
                "malformed assessment package")
        summary = package.decision_summary
        if summary is not None and not isinstance(summary, dict):
            raise ApplicationValidationError(
                "malformed decision summary")
        shipment_id = package.shipment_id
        return cls(
            workflow_id=str(package.workflow_id),
            tenant_id=str(package.tenant_id),
            case_id=str(package.case_id),
            shipment_id=(
                None if shipment_id is None
                else str(shipment_id)),
            state=str(package.state),
            round_count=len(package.rounds),
            open_requirements=tuple(
                str(v) for v in package.open_requirements),
            report=AnalysisReportDTO.from_result(
                package.reasoning_result),
            decision_summary=summary,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "tenant_id": self.tenant_id,
            "case_id": self.case_id,
            "shipment_id": self.shipment_id,
            "state": self.state,
            "round_count": self.round_count,
            "open_requirements": list(self.open_requirements),
            "report": self.report.to_dict(),
            "decision_summary": self.decision_summary,
        }


@dataclass(frozen=True, slots=True)
class ApplicabilityResultDTO:
    """One requirement's applicability outcome."""

    requirement_id: str
    outcome: str
    reason: str

    @classmethod
    def from_record(cls, record: dict[str, Any],
                    ) -> ApplicabilityResultDTO:
        record = _require_mapping(record, "applicability result")
        reason = record.get("reason")
        return cls(
            requirement_id=_uuid_string(
                record.get("requirement_id"), "requirement"),
            outcome=_require_text(record, "outcome"),
            reason=reason if isinstance(reason, str) else "",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "outcome": self.outcome,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ApplicabilityDTO:
    """Batch applicability determination for an export case."""

    counts: dict[str, int]
    results: tuple[ApplicabilityResultDTO, ...]

    @classmethod
    def from_report(cls, report: dict[str, Any]) -> ApplicabilityDTO:
        report = _require_mapping(report, "applicability report")
        counts = {}
        for key in ("total_requirements", "applicable_count",
                    "not_applicable_count", "unknown_count"):
            value = report.get(key)
            if not isinstance(value, int):
                raise ApplicationValidationError(
                    f"malformed applicability {key}")
            counts[key] = value
        results = report.get("results")
        if not isinstance(results, list):
            raise ApplicationValidationError(
                "malformed applicability results")
        return cls(
            counts=counts,
            results=tuple(
                ApplicabilityResultDTO.from_record(item)
                for item in results),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "counts": dict(self.counts),
            "results": [r.to_dict() for r in self.results],
        }


@dataclass(frozen=True, slots=True)
class ReadinessGapDTO:
    """One explicitly missing information item."""

    requirement_id: str
    kind: str
    reason: str

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> ReadinessGapDTO:
        record = _require_mapping(record, "readiness gap")
        reason = record.get("reason")
        return cls(
            requirement_id=_uuid_string(
                record.get("requirement_id"), "requirement"),
            kind=_require_text(record, "kind"),
            reason=reason if isinstance(reason, str) else "",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "kind": self.kind,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class CaseReadinessDTO:
    """Evidence-coverage readiness (information, not verdict)."""

    readiness_state: str
    required_information: int
    known_information: int
    missing_information_count: int
    gaps: tuple[ReadinessGapDTO, ...]
    missing_evidence_requirements: tuple[str, ...]
    unknown_applicability_requirements: tuple[str, ...]
    unknown_assessment_requirements: tuple[str, ...]

    @classmethod
    def from_report(cls, report: dict[str, Any]) -> CaseReadinessDTO:
        report = _require_mapping(report, "readiness report")
        if report.get("status") != "readiness_report":
            raise ApplicationValidationError(
                "not a readiness report")
        gaps = report.get("gaps")
        if not isinstance(gaps, list):
            raise ApplicationValidationError(
                "malformed readiness gaps")
        counts = {}
        for key, field in (
                ("required_information", "required"),
                ("known_information", "known"),
                ("missing_information", "missing")):
            value = report.get(key)
            if not isinstance(value, int):
                raise ApplicationValidationError(
                    f"malformed readiness {field} count")
            counts[field] = value
        return cls(
            readiness_state=_require_text(
                report, "readiness_state"),
            required_information=counts["required"],
            known_information=counts["known"],
            missing_information_count=counts["missing"],
            gaps=tuple(
                ReadinessGapDTO.from_record(item)
                for item in gaps),
            missing_evidence_requirements=_uuid_list(
                report.get("missing_evidence_requirements"),
                "requirement"),
            unknown_applicability_requirements=_uuid_list(
                report.get(
                    "unknown_applicability_requirements"),
                "requirement"),
            unknown_assessment_requirements=_uuid_list(
                report.get("unknown_assessment_requirements"),
                "requirement"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "readiness_state": self.readiness_state,
            "required_information": self.required_information,
            "known_information": self.known_information,
            "missing_information_count": (
                self.missing_information_count),
            "gaps": [g.to_dict() for g in self.gaps],
            "missing_evidence_requirements": list(
                self.missing_evidence_requirements),
            "unknown_applicability_requirements": list(
                self.unknown_applicability_requirements),
            "unknown_assessment_requirements": list(
                self.unknown_assessment_requirements),
        }


__all__ = [
    "AnalysisReportDTO",
    "AnalysisRoundDTO",
    "ApplicabilityDTO",
    "ApplicabilityResultDTO",
    "CaseReadinessDTO",
    "EvidenceRecordDTO",
    "EvidenceReferenceDTO",
    "FinalPackageDTO",
    "HistoryDTO",
    "HistoryEntryDTO",
    "PackageReferenceDTO",
    "ReadinessDTO",
    "ReadinessGapDTO",
    "RequirementFindingDTO",
    "ShipmentDTO",
    "WorkflowDTO",
]
