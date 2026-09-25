"""Compliance reasoning decision trace for Phase 6.5.

A structured, machine-readable record of **which authoritative inputs
and evidence contributed to a compliance analysis**:

```text
compliance case (deterministic facts)
    + ComplianceAnalysis (validated reasoning outcome)
    + ValidatedAnswer (validated model output)
        ↓
DecisionTraceService.trace (this module — records, never decides)
        ↓
DecisionTrace (identity / deterministic inputs / typed evidence
    references / observable reasoning outcome / steps /
    fingerprints)
```

This is provenance, not chain-of-thought storage. The trace contains
structured decision-relevant facts and evidence references plus the
concise externally safe outcome fields already produced by the Phase 6
contract. It never captures hidden chain-of-thought, internal model
deliberation, scratchpad reasoning, token streams, system prompts,
provider internals, or model hidden states — none of those exist as
inputs here, so none can leak.

No second audit framework is created: the repository has no generic
audit/event contract (auditability exists only as provenance-chain and
accounting properties on Phase 4/5 values), and this trace reuses the
existing typed references (`EvidenceReference`,
`KnowledgeReference`, `SourceReference`) instead of inventing new
provenance objects.

The trace records applicability, assessment, and decision references;
it never determines them. The Phase 3.5 deterministic decision
summary remains authoritative.

Immutability and determinism follow project conventions: all values
are frozen, identity is a deterministic uuid5, and fingerprints reuse
the Phase 4/6.3 `content_fingerprint` scheme (sha256 hex) rather than
inventing another. No timestamps or random IDs are introduced —
wall-clock audit time belongs to a future persistence/API layer, not
to this deterministic domain contract.

This module performs no retrieval, no LLM invocation, no prompting,
no database access, and no persistence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from .answer_validation import (
    VALIDATION_STATUS_INVALID_CITATIONS,
    ValidatedAnswer,
)
from .compliance_reasoning import (
    ComplianceAnalysis,
    EvidenceReference,
    KnowledgeReference,
    SourceReference,
)
from .errors import DomainValidationError, require_tenant_context
from .evidence_corpus import content_fingerprint

TRACE_STEP_DETERMINISTIC_STATE = "deterministic_state_established"
TRACE_STEP_EVIDENCE_SELECTED = "evidence_selected"
TRACE_STEP_KNOWLEDGE_RETRIEVED = "knowledge_retrieved"
TRACE_STEP_REASONING_GENERATED = "reasoning_generated"
TRACE_STEP_REASONING_VALIDATED = "reasoning_validated"
TRACE_STEP_ANALYSIS_CONSTRUCTED = "analysis_constructed"

TRACE_STEPS = (
    TRACE_STEP_DETERMINISTIC_STATE,
    TRACE_STEP_EVIDENCE_SELECTED,
    TRACE_STEP_KNOWLEDGE_RETRIEVED,
    TRACE_STEP_REASONING_GENERATED,
    TRACE_STEP_REASONING_VALIDATED,
    TRACE_STEP_ANALYSIS_CONSTRUCTED,
)


class DecisionTraceError(DomainValidationError):
    """A decision-trace integrity failure (fail closed).

    Raised for malformed cases/analyses/answers, tenant or case
    mismatches, analysis-case divergence, citation-mapping
    violations, and any unvalidated or model-supplied input —
    never converted into a fabricated trace.
    """


@dataclass(frozen=True, slots=True)
class TraceStep:
    """One structured pipeline event (no model deliberation).

    ``references`` holds stable identifier strings relevant to the
    step (IDs, citation labels, fingerprints) — never prose, never
    prompts, never hidden reasoning. ``detail`` is small
    deterministic accounting (counts, states, statuses).
    """

    sequence: int
    name: str
    references: tuple[str, ...]
    detail: str = ""

    def to_record(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "name": self.name,
            "references": list(self.references),
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    """Immutable decision trace for one requirement analysis.

    Deterministic fields (identities, applicability, assessment,
    typed evidence/knowledge/source references, sufficiency and
    contradiction states, missing information) are copied or
    derived from trusted structured state. The only
    model-generated field is ``explanation`` — externally safe
    text already accepted by Phase 6 validation. ``steps``,
    ``answer_fingerprint``, and ``input_fingerprint`` are derived
    from validated structured state. Nothing here is authoritative
    for applicability, assessment, risk, action, or compliance.
    """

    id: UUID
    tenant_id: UUID
    case_id: UUID
    requirement_id: UUID
    analysis_id: UUID
    report_id: UUID | None
    context_fingerprint: str | None
    applicability: str
    assessment: str
    supporting_evidence: tuple[EvidenceReference, ...]
    conflicting_evidence: tuple[EvidenceReference, ...]
    knowledge_references: tuple[KnowledgeReference, ...]
    sources: tuple[SourceReference, ...]
    explanation: str
    evidence_sufficiency: str
    contradiction_state: str
    sufficiency_explanation: str
    uncertainty: str
    missing_information: tuple[str, ...]
    answer_fingerprint: str
    input_fingerprint: str
    steps: tuple[TraceStep, ...]

    def to_record(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "case_id": str(self.case_id),
            "requirement_id": str(self.requirement_id),
            "analysis_id": str(self.analysis_id),
            "report_id": (
                str(self.report_id)
                if self.report_id is not None else None),
            "context_fingerprint": self.context_fingerprint,
            "applicability": self.applicability,
            "assessment": self.assessment,
            "supporting_evidence": [
                e.to_record() for e in self.supporting_evidence],
            "conflicting_evidence": [
                e.to_record() for e in self.conflicting_evidence],
            "knowledge_references": [
                k.to_record() for k in self.knowledge_references],
            "sources": [s.to_record() for s in self.sources],
            "explanation": self.explanation,
            "evidence_sufficiency": self.evidence_sufficiency,
            "contradiction_state": self.contradiction_state,
            "sufficiency_explanation": (
                self.sufficiency_explanation),
            "uncertainty": self.uncertainty,
            "missing_information": list(self.missing_information),
            "answer_fingerprint": self.answer_fingerprint,
            "input_fingerprint": self.input_fingerprint,
            "steps": [step.to_record() for step in self.steps],
        }


class DecisionTraceService:
    """Record-only construction of decision traces (no decisions)."""

    def trace(
        self,
        case: dict[str, Any],
        analysis: ComplianceAnalysis,
        validated_answer: ValidatedAnswer,
        *,
        tenant_id: Any,
        report_id: UUID | None = None,
    ) -> DecisionTrace:
        """Build the trace for one analysis (deterministic, pure).

        All authoritative content is copied from the supplied typed
        objects; the answer fingerprint is recomputed (never trusted
        from model output); knowledge references are re-checked
        against the answer's authoritative citation mapping.
        """
        require_tenant_context(tenant_id)
        tenant_uuid = tenant_id.tenant_id
        case_id = self._case_identity(case, analysis, tenant_uuid)
        self._check_answer(analysis, validated_answer, tenant_uuid)
        if report_id is not None and not isinstance(report_id, UUID):
            raise DecisionTraceError(
                "report identity must be a UUID")

        answer_fingerprint = content_fingerprint(
            validated_answer.answer_text)
        input_fingerprint = self._input_fingerprint(
            tenant_uuid, case, analysis, validated_answer,
            answer_fingerprint)
        steps = self._steps(
            case_id=case_id,
            analysis=analysis,
            validated_answer=validated_answer,
            answer_fingerprint=answer_fingerprint,
        )
        trace_id = uuid5(
            NAMESPACE_URL,
            ":".join([
                str(tenant_uuid),
                str(case_id),
                str(analysis.requirement_id),
                str(analysis.id),
                input_fingerprint,
            ]),
        )
        return DecisionTrace(
            id=trace_id,
            tenant_id=tenant_uuid,
            case_id=case_id,
            requirement_id=analysis.requirement_id,
            analysis_id=analysis.id,
            report_id=report_id,
            context_fingerprint=case.get("context_fingerprint"),
            applicability=analysis.applicability,
            assessment=analysis.assessment,
            supporting_evidence=analysis.supporting_evidence,
            conflicting_evidence=analysis.conflicting_evidence,
            knowledge_references=analysis.knowledge_references,
            sources=analysis.sources,
            explanation=analysis.explanation,
            evidence_sufficiency=analysis.evidence_sufficiency,
            contradiction_state=analysis.contradiction_state,
            sufficiency_explanation=(
                analysis.sufficiency_explanation),
            uncertainty=analysis.uncertainty,
            missing_information=analysis.missing_information,
            answer_fingerprint=answer_fingerprint,
            input_fingerprint=input_fingerprint,
            steps=steps,
        )

    # ------------------------------------------------------------------
    # integrity checks (fail closed; reuse Phase 6.1–6.4 validation)
    # ------------------------------------------------------------------

    @staticmethod
    def _case_identity(
        case: dict[str, Any],
        analysis: ComplianceAnalysis,
        tenant_uuid: UUID,
    ) -> UUID:
        if not isinstance(analysis, ComplianceAnalysis):
            raise DecisionTraceError(
                "a ComplianceAnalysis is required; raw model "
                "output is never traced")
        if not isinstance(case, dict):
            raise DecisionTraceError(
                "a compliance case is required")
        case_id = case.get("id")
        if not isinstance(case_id, UUID):
            raise DecisionTraceError(
                "case identity is malformed")
        if case.get("tenant_id") != tenant_uuid:
            raise DecisionTraceError(
                "case belongs to a different tenant")
        requirement = case.get("requirement") or {}
        if requirement.get("id") != analysis.requirement_id:
            raise DecisionTraceError(
                "analysis requirement does not match the case")
        case_applicability = (case.get("applicability") or {}).get(
            "outcome")
        case_assessment = (case.get("assessment") or {}).get(
            "outcome")
        if (case_applicability != analysis.applicability
                or case_assessment != analysis.assessment):
            raise DecisionTraceError(
                "analysis diverges from the supplied case state; "
                "no trace is built on inconsistent inputs")
        case_evidence_ids = set()
        for item in case.get("evidence") or []:
            evidence_id = item.get("evidence_id") if isinstance(
                item, dict) else None
            if not isinstance(evidence_id, UUID):
                raise DecisionTraceError(
                    "case evidence is malformed")
            case_evidence_ids.add(evidence_id)
        for reference in (*analysis.supporting_evidence,
                          *analysis.conflicting_evidence):
            if reference.evidence_id not in case_evidence_ids:
                raise DecisionTraceError(
                    "analysis evidence does not belong to the "
                    "supplied case; no trace is built on "
                    "unknown evidence")
        expected_sources = set()
        for kind, view in (
            ("regulatory_source", case.get("regulatory_source")),
            ("document", case.get("document_metadata")),
        ):
            if not isinstance(view, dict):
                continue
            identifier = view.get("id")
            expected_sources.add((
                kind,
                str(identifier)
                if identifier is not None else None,
            ))
        actual_sources = {
            (item.kind, item.identifier)
            for item in analysis.sources
        }
        if actual_sources != expected_sources:
            raise DecisionTraceError(
                "analysis sources do not match the supplied "
                "case; no trace is built on unknown sources")
        return case_id

    @staticmethod
    def _check_answer(
        analysis: ComplianceAnalysis,
        validated_answer: ValidatedAnswer,
        tenant_uuid: UUID,
    ) -> None:
        if not isinstance(validated_answer, ValidatedAnswer):
            raise DecisionTraceError(
                "a ValidatedAnswer is required; raw unvalidated "
                "reasoning is never traced")
        if validated_answer.status == (
                VALIDATION_STATUS_INVALID_CITATIONS):
            raise DecisionTraceError(
                "answer failed citation integrity; no trace is "
                "built on untrusted references")
        if analysis.tenant_id != tenant_uuid:
            raise DecisionTraceError(
                "analysis belongs to a different tenant")
        # Empty-knowledge answers carry no tenant provenance
        # (``None``) — consistent with the Phase 6.1 rule, only a
        # concrete foreign tenant identity fails closed.
        if validated_answer.tenant_id is not None and (
                validated_answer.tenant_id != tenant_uuid):
            raise DecisionTraceError(
                "answer provenance belongs to a different tenant")
        allowed_labels = {
            citation.label
            for citation in validated_answer.validated_citations
        }
        for reference in analysis.knowledge_references:
            if reference.label not in allowed_labels:
                raise DecisionTraceError(
                    f"knowledge reference {reference.label} is not "
                    "in the authoritative citation mapping")

    @staticmethod
    def _input_fingerprint(
        tenant_uuid: UUID,
        case: dict[str, Any],
        analysis: ComplianceAnalysis,
        validated_answer: ValidatedAnswer,
        answer_fingerprint: str,
    ) -> str:
        """Compact fingerprint of the exact reasoning inputs.

        Stable structured inputs only — no secrets, no prompts, no
        keys, no hidden model reasoning. Detects whether this
        reasoning was generated for these exact inputs; it proves
        nothing about model correctness.
        """
        payload = {
            "tenant": str(tenant_uuid),
            "case": str(case.get("id")),
            "requirement": str(analysis.requirement_id),
            "requirement_text": analysis.requirement_text,
            "applicability": analysis.applicability,
            "assessment": analysis.assessment,
            "evidence": [
                {"id": str(item.evidence_id),
                 "status": item.status}
                for item in (*analysis.supporting_evidence,
                             *analysis.conflicting_evidence)
            ],
            "knowledge": [
                {"label": item.label,
                 "fingerprint": item.content_fingerprint}
                for item in analysis.knowledge_references
            ],
            "sources": [
                {"kind": item.kind,
                 "identifier": item.identifier}
                for item in analysis.sources
            ],
            "answer_fingerprint": answer_fingerprint,
            "explanation": analysis.explanation,
            "uncertainty": analysis.uncertainty,
            "sufficiency": analysis.evidence_sufficiency,
            "contradiction": analysis.contradiction_state,
            "missing": list(analysis.missing_information),
        }
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            default=str)
        return content_fingerprint(canonical)

    @staticmethod
    def _steps(
        *,
        case_id: UUID,
        analysis: ComplianceAnalysis,
        validated_answer: ValidatedAnswer,
        answer_fingerprint: str,
    ) -> tuple[TraceStep, ...]:
        """The canonical pipeline events (fixed order, no deliberation)."""
        evidence_ids = [
            str(item.evidence_id)
            for item in (*analysis.supporting_evidence,
                         *analysis.conflicting_evidence)
        ]
        citation_labels = [
            item.label for item in analysis.knowledge_references]
        events = [
            (TRACE_STEP_DETERMINISTIC_STATE,
             (str(case_id), str(analysis.requirement_id)),
             f"applicability={analysis.applicability} "
             f"assessment={analysis.assessment}"),
            (TRACE_STEP_EVIDENCE_SELECTED,
             tuple(evidence_ids),
             f"supporting={len(analysis.supporting_evidence)} "
             f"conflicting={len(analysis.conflicting_evidence)}"),
            (TRACE_STEP_KNOWLEDGE_RETRIEVED,
             tuple(citation_labels),
             f"citations={len(citation_labels)}"),
            (TRACE_STEP_REASONING_GENERATED,
             (answer_fingerprint,),
             f"status={validated_answer.status}"),
            (TRACE_STEP_REASONING_VALIDATED,
             tuple(citation_labels),
             f"mapping_labels={len(citation_labels)} "
             "invalid=0"),
            (TRACE_STEP_ANALYSIS_CONSTRUCTED,
             (str(analysis.id),),
             f"uncertainty={analysis.uncertainty} "
             f"sufficiency={analysis.evidence_sufficiency}"),
        ]
        return tuple(
            TraceStep(
                sequence=index,
                name=name,
                references=references,
                detail=detail,
            )
            for index, (name, references, detail) in enumerate(
                events, start=1)
        )


__all__ = [
    "TRACE_STEPS",
    "TRACE_STEP_ANALYSIS_CONSTRUCTED",
    "TRACE_STEP_DETERMINISTIC_STATE",
    "TRACE_STEP_EVIDENCE_SELECTED",
    "TRACE_STEP_KNOWLEDGE_RETRIEVED",
    "TRACE_STEP_REASONING_GENERATED",
    "TRACE_STEP_REASONING_VALIDATED",
    "DecisionTrace",
    "DecisionTraceError",
    "DecisionTraceService",
    "TraceStep",
]
