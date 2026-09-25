"""Deterministic compliance reasoning boundary for Phase 6.1.

The first compliance-reasoning contract: per-requirement structured
analysis combining the existing deterministic compliance state with
a validated Phase 5 RAG answer:

```text
compliance case (Phase 2.7 view: requirement + applicability
    + assessment + tenant evidence + source provenance)
        +
ValidatedAnswer (Phase 5.12: citation-checked model explanation
    + authoritative knowledge references)
        ↓
ComplianceReasoningService.analyze (this module — deterministic)
        ↓
ComplianceAnalysis (requirement / status / evidence / source /
    reason / missing information / uncertainty)
```

Authoritative-truth boundary
----------------------------
Deterministic business truth remains authoritative. The service
COPIES applicability and assessment outcomes from the supplied
case — it never reads them from model text, never alters them,
and rejects any case whose assessment contradicts its
applicability (a decisive assessment on a non-applicable
requirement fails closed as fabricated/overridden state).
Unknown states are preserved, never converted.

The model's contribution is explanation text plus the validated
knowledge references it actually cited. The service never parses
citations from text (references come only from
``ValidatedAnswer.validated_citations``) and never treats model
output as a verdict: a ``"compliant": true/false``-style claim in
the text changes nothing in the structured result.

Uncertainty semantics (conservative, categorical — the project
specifies no calibrated probability, and none is invented):

- ``determined`` — the deterministic machinery is decisive
  (applicability is ``applicable`` with a decisive assessment,
  or ``not_applicable``) AND the validated explanation is
  present with status ``valid``.
- ``uncertain`` — the machinery is decisive but the model
  produced no explanation (empty answer): the *why* is
  unaccounted for, flagged rather than fabricated.
- ``unknown`` — the machinery itself is undecided (any
  ``unknown`` in applicability/assessment).

``invalid_citations`` input fails closed: analysis is never
built on integrity-failed references.

This module performs no retrieval, no LLM invocation, no Qdrant
call, no database access, and no compliance verdict beyond
re-presenting the deterministic state. ``analyze_with_knowledge``
is a thin delegation seam to an injected ``RAGApplicationService``
whose failures propagate unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from .answer_validation import (
    VALIDATION_STATUS_EMPTY,
    VALIDATION_STATUS_INVALID_CITATIONS,
    VALIDATION_STATUS_VALID,
    ValidatedAnswer,
)
from .errors import DomainValidationError, require_tenant_context
from .evidence_context import EvidenceContextBudget
from .evidence_corpus import content_fingerprint
from .evidence_retrieval import DEFAULT_TOP_K
from .evidence_sufficiency import (
    CONTRADICTION_NONE,
    SUFFICIENCY_UNKNOWN,
    EvidenceSufficiencyError,
    EvidenceSufficiencyService,
    MissingInformationItem,
    check_no_numeric_confidence,
)

APPLICABILITY_STATES = frozenset(
    {"applicable", "not_applicable", "unknown"})
ASSESSMENT_STATES = frozenset(
    {"satisfied", "not_satisfied", "unknown"})

CERTAINTY_DETERMINED = "determined"
CERTAINTY_UNCERTAIN = "uncertain"
CERTAINTY_UNKNOWN = "unknown"

CONFLICTING_EVIDENCE_STATUSES = frozenset({"rejected", "archived"})


class ComplianceReasoningError(DomainValidationError):
    """A compliance-reasoning integrity failure (fail closed).

    Raised for malformed cases/answers, tenant mismatches,
    integrity-failed (``invalid_citations``) answers, and any
    deterministic-state contradiction — never converted into a
    fabricated analysis.
    """


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """One tenant evidence item linked to the requirement.

    Carries the case view's evidence fields only (identifier,
    type, reference pointer, status) — never file contents.
    """

    evidence_id: UUID
    evidence_type: str
    reference: str
    status: str

    def to_record(self) -> dict[str, Any]:
        return {
            "evidence_id": str(self.evidence_id),
            "evidence_type": self.evidence_type,
            "reference": self.reference,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class KnowledgeReference:
    """One validated knowledge citation behind the analysis.

    Built exclusively from the authoritative ``PromptCitation``
    objects in ``ValidatedAnswer.validated_citations`` — never
    parsed from answer text. ``[E1]`` text alone proves nothing;
    membership in the validated mapping proves the reference.
    """

    label: str
    rank_position: int
    chunk_id: UUID
    document_id: UUID
    source_id: str
    source_type: str
    source_location: str | None
    document_version: str | None
    content_fingerprint: str

    def to_record(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "rank_position": self.rank_position,
            "chunk_id": str(self.chunk_id),
            "document_id": str(self.document_id),
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_location": self.source_location,
            "document_version": self.document_version,
            "content_fingerprint": self.content_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class SourceReference:
    """One provenance pointer from the compliance case."""

    kind: str
    identifier: str | None

    def to_record(self) -> dict[str, Any]:
        return {"kind": self.kind, "identifier": self.identifier}


@dataclass(frozen=True, slots=True)
class ComplianceAnalysis:
    """Structured per-requirement compliance analysis (immutable).

    Deterministic fields (requirement, applicability, assessment,
    evidence, sources, missing information, uncertainty) are
    derived from the supplied case by fixed rules. The only
    model-sourced field is ``explanation`` — the validated
    answer's verbatim text — which can never alter the
    deterministic state. When validated ``StructuredReasoning``
    (Phase 6.3) is supplied, its explanation replaces the raw
    answer text, its suggested items are appended to the
    deterministic missing information visibly prefixed as model
    observations, and its uncertainty statement is carried
    verbatim; the deterministic ``uncertainty`` category and
    every reference remain authoritative. Phase 6.4 adds
    deterministically derived evidence-quality state —
    ``evidence_sufficiency`` (``supported``/``insufficient``/
    ``missing``/``unknown``, mirroring the existing assessment
    semantics), ``contradiction_state`` (``none``/``present`` —
    conflicts preserved, never resolved),
    ``sufficiency_explanation`` (deterministic reason text), and
    ``missing_items`` (typed, requirement-associated gaps).
    """

    id: UUID
    tenant_id: UUID
    requirement_id: UUID
    requirement_text: str
    applicability: str
    assessment: str
    explanation: str
    supporting_evidence: tuple[EvidenceReference, ...]
    conflicting_evidence: tuple[EvidenceReference, ...]
    knowledge_references: tuple[KnowledgeReference, ...]
    sources: tuple[SourceReference, ...]
    missing_information: tuple[str, ...]
    uncertainty: str
    uncertainty_explanation: str = ""
    evidence_sufficiency: str = SUFFICIENCY_UNKNOWN
    contradiction_state: str = CONTRADICTION_NONE
    sufficiency_explanation: str = ""
    missing_items: tuple[MissingInformationItem, ...] = ()

    def to_record(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "requirement_id": str(self.requirement_id),
            "requirement_text": self.requirement_text,
            "applicability": self.applicability,
            "assessment": self.assessment,
            "explanation": self.explanation,
            "supporting_evidence": [
                e.to_record() for e in self.supporting_evidence],
            "conflicting_evidence": [
                e.to_record() for e in self.conflicting_evidence],
            "knowledge_references": [
                k.to_record() for k in self.knowledge_references],
            "sources": [s.to_record() for s in self.sources],
            "missing_information": list(self.missing_information),
            "uncertainty": self.uncertainty,
            "uncertainty_explanation": self.uncertainty_explanation,
            "evidence_sufficiency": self.evidence_sufficiency,
            "contradiction_state": self.contradiction_state,
            "sufficiency_explanation": self.sufficiency_explanation,
            "missing_items": [
                item.to_record() for item in self.missing_items],
        }


class ComplianceReasoningService:
    """Deterministic compliance analysis over case + validated answer.

    ``analyze`` is pure composition: it validates the case view
    and the ``ValidatedAnswer``, copies the deterministic state,
    carries the validated explanation through verbatim, and
    derives missing-information and uncertainty by fixed rules.
    ``analyze_with_knowledge`` additionally delegates
    retrieval+generation to an injected ``RAGApplicationService``
    (failures propagate unchanged) and then analyzes.
    """

    def analyze(
        self,
        case: dict[str, Any],
        validated_answer: ValidatedAnswer,
        *,
        tenant_id: Any,
        reasoning: Any | None = None,
    ) -> ComplianceAnalysis:
        """Compose one structured analysis (deterministic, pure).

        Without ``reasoning`` the behavior is exactly Phase 6.1:
        the validated answer text becomes the explanation. With
        validated ``StructuredReasoning`` (Phase 6.3), its
        explanation, prefixed missing items, and uncertainty
        statement feed only the permitted fields; the reasoning
        must be bound to this answer (fingerprint match) or the
        call fails closed.
        """
        from .reasoning_generation import (
            MODEL_OBSERVATION_PREFIX,
            StructuredReasoning,
        )

        require_tenant_context(tenant_id)
        tenant_uuid = tenant_id.tenant_id
        requirement = self._requirement(case)
        applicability = self._applicability(case)
        assessment = self._assessment(case, applicability)
        self._check_tenant(case, validated_answer, tenant_uuid)
        if reasoning is None:
            explanation = self._explanation(validated_answer)
            model_items: tuple[str, ...] = ()
            uncertainty_explanation = ""
        else:
            if not isinstance(reasoning, StructuredReasoning):
                raise ComplianceReasoningError(
                    "reasoning must be StructuredReasoning")
            if reasoning.answer_fingerprint != content_fingerprint(
                    validated_answer.answer_text):
                raise ComplianceReasoningError(
                    "reasoning was not built from this answer")
            explanation = reasoning.explanation
            model_items = tuple(
                f"{MODEL_OBSERVATION_PREFIX}{item}"
                for item in reasoning.suggested_missing)
            uncertainty_explanation = (
                reasoning.uncertainty_explanation)

        supporting: list[EvidenceReference] = []
        conflicting: list[EvidenceReference] = []
        for item in case.get("evidence") or []:
            reference = self._evidence_reference(item)
            if reference.status in CONFLICTING_EVIDENCE_STATUSES:
                conflicting.append(reference)
            else:
                supporting.append(reference)

        knowledge = tuple(
            self._knowledge_reference(citation)
            for citation in validated_answer.validated_citations
        )
        sources = self._sources(case)
        missing = self._missing_information(
            case, applicability, assessment,
            supporting, knowledge, validated_answer,
        ) + model_items
        uncertainty = self._uncertainty(
            applicability, assessment, validated_answer)
        # Phase 6.4: model-sourced strings carry no numeric confidence.
        # Only model text is inspected — deterministic case content is
        # trusted and never checked here.
        try:
            check_no_numeric_confidence(explanation)
            if uncertainty_explanation:
                check_no_numeric_confidence(uncertainty_explanation)
        except EvidenceSufficiencyError as exc:
            raise ComplianceReasoningError(str(exc)) from exc
        # Phase 6.4: derived evidence-quality state. Outcomes and
        # evidence come from the authoritative deterministic state
        # above; this step only classifies.
        applicability_view = case.get("applicability") or {}
        assessment_view = case.get("assessment") or {}
        sufficiency = EvidenceSufficiencyService().assess(
            requirement_id=requirement["id"],
            applicability=applicability,
            assessment=assessment,
            supporting_count=len(supporting),
            conflicting_count=len(conflicting),
            has_knowledge=bool(knowledge),
            has_explanation=validated_answer.status == (
                VALIDATION_STATUS_VALID),
            applicability_reason=applicability_view.get("reason"),
            assessment_reason=assessment_view.get("reason"),
        )

        analysis_id = uuid5(
            NAMESPACE_URL,
            f"{tenant_uuid}:{case['id']}:"
            f"{content_fingerprint(explanation)}",
        )
        return ComplianceAnalysis(
            id=analysis_id,
            tenant_id=tenant_uuid,
            requirement_id=requirement["id"],
            requirement_text=requirement["text"],
            applicability=applicability,
            assessment=assessment,
            explanation=explanation,
            supporting_evidence=tuple(supporting),
            conflicting_evidence=tuple(conflicting),
            knowledge_references=knowledge,
            sources=sources,
            missing_information=missing,
            uncertainty=uncertainty,
            uncertainty_explanation=uncertainty_explanation,
            evidence_sufficiency=sufficiency.sufficiency,
            contradiction_state=sufficiency.contradiction,
            sufficiency_explanation=(
                sufficiency.sufficiency_explanation),
            missing_items=sufficiency.missing_items,
        )

    def analyze_with_knowledge(
        self,
        case: dict[str, Any],
        information_need: str,
        *,
        tenant_id: Any,
        rag_service: Any,
        mode: str,
        context_budget: EvidenceContextBudget,
        scope: Any | None = None,
        top_k: int = DEFAULT_TOP_K,
        candidate_pool: int | None = None,
    ) -> ComplianceAnalysis:
        """Retrieve knowledge via the injected RAG service, then analyze.

        Delegation only: the information need and controls are
        forwarded unchanged to ``rag_service.query`` — the single
        authoritative retrieval/generation/validation boundary.
        Provider failures propagate unchanged and never become an
        analysis.
        """
        require_tenant_context(tenant_id)
        if not isinstance(information_need, str):
            raise ComplianceReasoningError(
                "an information need is required")
        if not isinstance(context_budget, EvidenceContextBudget):
            raise ComplianceReasoningError(
                "an EvidenceContextBudget is required")
        if (
            rag_service is None
            or isinstance(rag_service, (str, bytes))
            or not callable(getattr(rag_service, "query", None))
        ):
            raise ComplianceReasoningError(
                "a RAG application service is required")
        validated = rag_service.query(
            information_need,
            tenant_id=tenant_id,
            mode=mode,
            context_budget=context_budget,
            scope=scope,
            top_k=top_k,
            candidate_pool=candidate_pool,
        )
        return self.analyze(case, validated, tenant_id=tenant_id)

    # ------------------------------------------------------------------
    # deterministic extraction (fail closed)
    # ------------------------------------------------------------------

    @staticmethod
    def _requirement(case: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(case, dict):
            raise ComplianceReasoningError(
                "a compliance case is required")
        requirement = case.get("requirement")
        if not isinstance(requirement, dict):
            raise ComplianceReasoningError(
                "case carries no requirement")
        requirement_id = requirement.get("id")
        text = requirement.get("text")
        if not isinstance(requirement_id, UUID):
            raise ComplianceReasoningError(
                "requirement identity is malformed")
        if not isinstance(text, str) or not text.strip():
            raise ComplianceReasoningError(
                "requirement text is required")
        provenance = case.get("provenance") or {}
        proven_id = provenance.get("requirement_id")
        if proven_id is not None and proven_id != requirement_id:
            raise ComplianceReasoningError(
                "requirement identity contradicts case provenance")
        return {"id": requirement_id, "text": text}

    @staticmethod
    def _applicability(case: dict[str, Any]) -> str:
        applicability = case.get("applicability")
        if not isinstance(applicability, dict):
            raise ComplianceReasoningError(
                "case carries no applicability outcome")
        outcome = applicability.get("outcome")
        if outcome not in APPLICABILITY_STATES:
            raise ComplianceReasoningError(
                "applicability outcome is malformed")
        return outcome

    @staticmethod
    def _assessment(
        case: dict[str, Any], applicability: str
    ) -> str:
        assessment = case.get("assessment")
        if not isinstance(assessment, dict):
            raise ComplianceReasoningError(
                "case carries no assessment outcome")
        outcome = assessment.get("outcome")
        if outcome not in ASSESSMENT_STATES:
            raise ComplianceReasoningError(
                "assessment outcome is malformed")
        if applicability != "applicable" and outcome != "unknown":
            raise ComplianceReasoningError(
                "decisive assessment on a non-applicable requirement "
                "contradicts the deterministic state")
        return outcome

    @staticmethod
    def _check_tenant(
        case: dict[str, Any],
        validated_answer: ValidatedAnswer,
        tenant_uuid: UUID,
    ) -> None:
        if not isinstance(validated_answer, ValidatedAnswer):
            raise ComplianceReasoningError(
                "a ValidatedAnswer is required")
        if case.get("tenant_id") != tenant_uuid:
            raise ComplianceReasoningError(
                "case belongs to a different tenant")
        if validated_answer.status == (
                VALIDATION_STATUS_INVALID_CITATIONS):
            raise ComplianceReasoningError(
                "answer failed citation integrity; no analysis "
                "is built on untrusted references")
        # An empty knowledge context carries no tenant provenance
        # (``None``) — there is no foreign content to leak, so only
        # a concrete foreign tenant identity fails closed.
        if validated_answer.tenant_id is not None and (
                validated_answer.tenant_id != tenant_uuid):
            raise ComplianceReasoningError(
                "answer provenance belongs to a different tenant")

    @staticmethod
    def _explanation(validated_answer: ValidatedAnswer) -> str:
        text = validated_answer.answer_text
        if not isinstance(text, str):
            raise ComplianceReasoningError(
                "answer text is malformed")
        return text

    @staticmethod
    def _evidence_reference(item: dict[str, Any]) -> EvidenceReference:
        if not isinstance(item, dict):
            raise ComplianceReasoningError(
                "case evidence is malformed")
        evidence_id = item.get("evidence_id")
        evidence_type = item.get("evidence_type")
        reference = item.get("reference")
        status = item.get("status")
        if not isinstance(evidence_id, UUID):
            raise ComplianceReasoningError(
                "evidence identity is malformed")
        for name, value in (
            ("evidence_type", evidence_type),
            ("reference", reference),
            ("status", status),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ComplianceReasoningError(
                    f"evidence {name} is required")
        return EvidenceReference(
            evidence_id=evidence_id,
            evidence_type=evidence_type,
            reference=reference,
            status=status,
        )

    @staticmethod
    def _knowledge_reference(citation: Any) -> KnowledgeReference:
        label = getattr(citation, "label", None)
        rank_position = getattr(citation, "rank_position", None)
        selected = getattr(citation, "selected", None)
        ranked = getattr(selected, "ranked", None)
        evidence = getattr(ranked, "evidence", None)
        if not isinstance(label, str) or not label:
            raise ComplianceReasoningError(
                "knowledge citation is malformed")
        if not isinstance(rank_position, int):
            raise ComplianceReasoningError(
                "knowledge citation is malformed")
        for name in (
            "chunk_id", "document_id", "source_id", "source_type",
            "content_fingerprint",
        ):
            value = getattr(evidence, name, None)
            if value is None or value == "":
                raise ComplianceReasoningError(
                    "knowledge citation provenance is malformed")
        if not isinstance(
                getattr(evidence, "chunk_id", None), UUID):
            raise ComplianceReasoningError(
                "knowledge citation provenance is malformed")
        if not isinstance(
                getattr(evidence, "document_id", None), UUID):
            raise ComplianceReasoningError(
                "knowledge citation provenance is malformed")
        return KnowledgeReference(
            label=label,
            rank_position=rank_position,
            chunk_id=evidence.chunk_id,
            document_id=evidence.document_id,
            source_id=evidence.source_id,
            source_type=evidence.source_type,
            source_location=getattr(
                evidence, "source_location", None),
            document_version=getattr(
                evidence, "document_version", None),
            content_fingerprint=evidence.content_fingerprint,
        )

    @staticmethod
    def _sources(case: dict[str, Any]) -> tuple[SourceReference, ...]:
        sources: list[SourceReference] = []
        for kind, view in (
            ("regulatory_source", case.get("regulatory_source")),
            ("document", case.get("document_metadata")),
        ):
            if not isinstance(view, dict):
                continue
            identifier = view.get("id")
            sources.append(SourceReference(
                kind=kind,
                identifier=str(identifier)
                if identifier is not None else None,
            ))
        return tuple(sources)

    @staticmethod
    def _missing_information(
        case: dict[str, Any],
        applicability: str,
        assessment: str,
        supporting: list[EvidenceReference],
        knowledge: tuple[KnowledgeReference, ...],
        validated_answer: ValidatedAnswer,
    ) -> tuple[str, ...]:
        missing: list[str] = []
        applicability_view = case.get("applicability") or {}
        assessment_view = case.get("assessment") or {}
        if applicability == "unknown":
            reason = applicability_view.get("reason") or (
                "no reason recorded")
            missing.append(
                f"applicability undetermined: {reason}")
        if applicability == "applicable" and assessment == "unknown":
            reason = assessment_view.get("reason") or (
                "no reason recorded")
            missing.append(f"assessment incomplete: {reason}")
            if not supporting:
                missing.append(
                    "no tenant evidence linked to this requirement")
            if not knowledge:
                missing.append(
                    "no retrieved knowledge evidence cited")
        if applicability == "applicable" and assessment == (
                "not_satisfied"):
            reason = assessment_view.get("reason") or (
                "no reason recorded")
            missing.append(
                f"satisfying evidence not established: {reason}")
        if validated_answer.status == VALIDATION_STATUS_EMPTY:
            missing.append("model produced no explanation")
        return tuple(missing)

    @staticmethod
    def _uncertainty(
        applicability: str,
        assessment: str,
        validated_answer: ValidatedAnswer,
    ) -> str:
        decisive = (
            applicability == "not_applicable"
            or (applicability == "applicable"
                and assessment in ("satisfied", "not_satisfied"))
        )
        if not decisive:
            return CERTAINTY_UNKNOWN
        if validated_answer.status == VALIDATION_STATUS_VALID and (
                validated_answer.answer_text.strip()):
            return CERTAINTY_DETERMINED
        return CERTAINTY_UNCERTAIN


__all__ = [
    "APPLICABILITY_STATES",
    "ASSESSMENT_STATES",
    "CERTAINTY_DETERMINED",
    "CERTAINTY_UNCERTAIN",
    "CERTAINTY_UNKNOWN",
    "CONFLICTING_EVIDENCE_STATUSES",
    "ComplianceAnalysis",
    "ComplianceReasoningError",
    "ComplianceReasoningService",
    "EvidenceReference",
    "KnowledgeReference",
    "SourceReference",
]
