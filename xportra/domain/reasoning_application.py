"""End-to-end compliance reasoning composition for Phase 6.6.

The single safe orchestration boundary for the Phase 6 domain
capability — deterministic case state through retrieval,
validated reasoning, analysis, report, and trace:

```text
compliance cases, one case (deterministic, trusted)
    + decision summary (Phase 3.5, authoritative by reference)
    + RAG controls (injected boundary, untrusted until validated)
        ↓
ComplianceReasoningApplication.analyze_case (this module —
    coordinates, never decides)
        ↓
ComplianceReasoningResult (analyses + report + traces +
    referenced decision state; no verdict)
```

Per-requirement flow per case (existing boundaries, unchanged):

1. deterministic context validated up front (tenant, case,
   requirement, evidence, and decision-summary consistency —
   before any provider invocation);
2. knowledge retrieved via the injected RAG application
   boundary (Phase 5);
3. reasoning request built deterministically (Phase 6.3);
4. structured reasoning generated and validated (Phase 6.3);
5. ``ComplianceAnalysis`` constructed (Phases 6.1 + 6.4);
6. ``ComplianceAnalysisReport`` composed (Phase 6.2);
7. ``DecisionTrace`` constructed per analysis (Phase 6.5).

The orchestrator coordinates existing services rather than
reimplementing them: it determines no applicability, no
assessment, no risk, no action, no authority, no verdict, and
resolves no conflict. It parses no model prose (Phase 6.3),
derives no sufficiency of its own (Phase 6.4), and constructs
no provenance of its own (Phases 6.1/6.5).

Failure semantics (fail closed — the repository defines no
partial-result semantics, so none are invented): deterministic
input defects fail before any retrieval or provider call, so no
misleading partial analysis can form; provider, retrieval, and
validation failures propagate unchanged and never become
``unknown``, ``insufficient``, ``not_satisfied``, or an empty
successful analysis; if any requirement's reasoning, report
composition, or trace construction fails, the whole operation
fails with no partial result returned and no failed requirement
silently omitted.

This module performs no retrieval, prompting, generation, or
validation of its own, and no database access or persistence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from .compliance_reasoning import ComplianceAnalysis
from .compliance_report import (
    ComplianceAnalysisReport,
    ComplianceReportService,
)
from .decision_trace import DecisionTrace, DecisionTraceService
from .errors import DomainValidationError, require_tenant_context
from .evidence_context import EvidenceContextBudget
from .evidence_retrieval import DEFAULT_TOP_K
from .reasoning_generation import StructuredReasoningService


class ComplianceReasoningApplicationError(DomainValidationError):
    """A reasoning-composition integrity failure (fail closed).

    Raised for invalid deterministic inputs (before any provider
    invocation) — never converted into a partial or fabricated
    result. Provider, retrieval, validation, report, and trace
    failures propagate unchanged under their own errors.
    """


@dataclass(frozen=True, slots=True)
class ComplianceReasoningResult:
    """Immutable end-to-end Phase 6 outcome for one case.

    ``analyses`` preserves the per-requirement analyses;
    ``report`` is the composed case-level report; ``traces``
    carries one decision trace per analysis in report order;
    ``decision_summary`` is the caller-supplied Phase 3.5 summary
    carried by reference, never recomputed. There is deliberately
    no overall compliance verdict field — a new independent
    verdict is structurally unrepresentable here.
    """

    case_id: UUID
    tenant_id: UUID
    analyses: tuple[ComplianceAnalysis, ...]
    report: ComplianceAnalysisReport
    traces: tuple[DecisionTrace, ...]
    decision_summary: dict[str, Any] | None

    def to_record(self) -> dict[str, Any]:
        return {
            "case_id": str(self.case_id),
            "tenant_id": str(self.tenant_id),
            "analyses": [a.to_record() for a in self.analyses],
            "report": self.report.to_record(),
            "traces": [t.to_record() for t in self.traces],
            "decision_summary": self.decision_summary,
        }


class ComplianceReasoningApplication:
    """Pure orchestration over the existing Phase 6 services."""

    def __init__(
        self,
        *,
        structured_service: StructuredReasoningService | None = None,
        report_service: ComplianceReportService | None = None,
        trace_service: DecisionTraceService | None = None,
    ) -> None:
        self._structured_service = (
            structured_service or StructuredReasoningService())
        self._report_service = (
            report_service or ComplianceReportService())
        self._trace_service = (
            trace_service or DecisionTraceService())
        for name, service, method in (
            ("structured reasoning", self._structured_service,
             "analyze_with_reasoning_and_answer"),
            ("report", self._report_service, "compose"),
            ("trace", self._trace_service, "trace"),
        ):
            if not callable(getattr(service, method, None)):
                raise ComplianceReasoningApplicationError(
                    f"a {name} service is required")

    def analyze_case(
        self,
        cases: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        *,
        tenant_id: Any,
        case_id: UUID,
        rag_service: Any,
        mode: str,
        context_budget: EvidenceContextBudget,
        scope: Any | None = None,
        top_k: int = DEFAULT_TOP_K,
        candidate_pool: int | None = None,
        decision_summary: dict[str, Any] | None = None,
    ) -> ComplianceReasoningResult:
        """Reason over every requirement of one case, end to end.

        ``case_id`` is the caller-supplied grouping identity for
        this case (mirroring the report contract — case views are
        per-requirement and carry their own derived view IDs).
        Deterministic inputs are fully validated before the first
        retrieval or provider call. Cases are processed in
        ascending stringified requirement-ID order (the Phase 3.x
        convention) so equivalent inputs always yield the same
        composition.
        """
        require_tenant_context(tenant_id)
        tenant_uuid = tenant_id.tenant_id
        if not isinstance(case_id, UUID):
            raise ComplianceReasoningApplicationError(
                "a case identity UUID is required")
        ordered = self._validated_cases(cases, tenant_uuid)
        self._check_decision_summary(decision_summary, tenant_uuid)

        triples: list[tuple[dict[str, Any], Any, Any]] = []
        for case in ordered:
            analysis, validated = (
                self._structured_service
                .analyze_with_reasoning_and_answer(
                    case,
                    tenant_id=tenant_id,
                    rag_service=rag_service,
                    mode=mode,
                    context_budget=context_budget,
                    scope=scope,
                    top_k=top_k,
                    candidate_pool=candidate_pool,
                )
            )
            triples.append((case, analysis, validated))

        context_fingerprint = ordered[0].get("context_fingerprint")
        report = self._report_service.compose(
            [analysis for _, analysis, _ in triples],
            tenant_id=tenant_id,
            case_id=case_id,
            context_fingerprint=context_fingerprint,
            decision_summary=decision_summary,
        )
        traces = tuple(
            self._trace_service.trace(
                case, analysis, validated,
                tenant_id=tenant_id,
                report_id=report.id,
            )
            for case, analysis, validated in triples
        )
        return ComplianceReasoningResult(
            case_id=case_id,
            tenant_id=tenant_uuid,
            analyses=tuple(
                analysis for _, analysis, _ in triples),
            report=report,
            traces=traces,
            decision_summary=decision_summary,
        )

    # ------------------------------------------------------------------
    # deterministic-first validation (before any provider invocation)
    # ------------------------------------------------------------------

    @staticmethod
    def _validated_cases(
        cases: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        tenant_uuid: UUID,
    ) -> tuple[dict[str, Any], ...]:
        if isinstance(cases, (str, bytes, dict)) or not isinstance(
                cases, (list, tuple)):
            raise ComplianceReasoningApplicationError(
                "compliance cases must be a list or tuple")
        if not cases:
            raise ComplianceReasoningApplicationError(
                "at least one compliance case is required")
        context_fingerprint: Any = None
        seen_requirements: set[UUID] = set()
        for case in cases:
            if not isinstance(case, dict):
                raise ComplianceReasoningApplicationError(
                    "a compliance case is required")
            if case.get("tenant_id") != tenant_uuid:
                raise ComplianceReasoningApplicationError(
                    "case belongs to a different tenant")
            if not isinstance(case.get("id"), UUID):
                raise ComplianceReasoningApplicationError(
                    "case view identity is malformed")
            if context_fingerprint is None:
                context_fingerprint = case.get(
                    "context_fingerprint")
            elif case.get("context_fingerprint") != (
                    context_fingerprint):
                raise ComplianceReasoningApplicationError(
                    "cases carry inconsistent context; no result "
                    "is built on divergent deterministic inputs")
            requirement = case.get("requirement") or {}
            requirement_id = requirement.get("id")
            if not isinstance(requirement_id, UUID):
                raise ComplianceReasoningApplicationError(
                    "requirement identity is malformed")
            if requirement_id in seen_requirements:
                raise ComplianceReasoningApplicationError(
                    "duplicate requirement identity in result")
            seen_requirements.add(requirement_id)
        return tuple(sorted(
            cases,
            key=lambda c: str(c["requirement"]["id"]),
        ))

    @staticmethod
    def _check_decision_summary(
        decision_summary: dict[str, Any] | None,
        tenant_uuid: UUID,
    ) -> None:
        if decision_summary is None:
            return
        if not isinstance(decision_summary, dict):
            raise ComplianceReasoningApplicationError(
                "decision summary must be a mapping")
        summary_tenant = decision_summary.get("tenant_id")
        if summary_tenant is not None and (
                summary_tenant != tenant_uuid):
            raise ComplianceReasoningApplicationError(
                "decision summary belongs to a different tenant")


__all__ = [
    "ComplianceReasoningApplication",
    "ComplianceReasoningApplicationError",
    "ComplianceReasoningResult",
]
