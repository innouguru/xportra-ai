"""Compliance user workflow contract for Phase 7.1.

The domain-level coordinator for a user's progression through a
compliance case — shipment creation through evidence submission,
analysis, review, issue resolution, re-analysis, and final
assessment packaging:

```text
begin → provide_information → note_evidence_pending
    → record applicability outcome → run_analysis
    → submit_for_review → request_additional_evidence
    → supply_evidence → run_analysis (next round)
    → submit_for_review → finalize → assessment package
```

The workflow coordinates existing capabilities rather than
reimplementing them. It determines no applicability, calculates
no assessment, risk, or action, generates no reasoning,
retrieves nothing, calls no LLM, parses no model output, and
invents no overall compliance verdict. Analysis runs delegate
to the completed Phase 6 composition boundary
(`ComplianceReasoningApplication`); the authoritative Phase 3.5
decision summary is carried by reference, never reinterpreted.

Workflow state describes process progression only
(`analysis_available`, `review_required`, …) — never
regulatory truth (`compliant`/`satisfied`/… must never become
workflow states; the module contains none of that vocabulary).

The evidence loop is explicit and non-mutating: every
`run_analysis` appends a new `WorkflowAnalysisRound`
(round index, report/analysis/trace IDs, input fingerprints)
and returns a new workflow object, so a subsequent analysis
is always distinguishable from its predecessors through the
existing deterministic identities. No new versioning system
is invented beyond the round counter.

Shipment identity is caller-supplied (no Shipment domain
object exists yet — only shipment characteristics inside
applicability input); evidence bytes live outside this
contract (recording is persistence-backed via
`ComplianceEvidenceService`), so the workflow tracks
evidence references and progression, never contents.
Persistence itself is out of scope: the workflow is a pure
in-memory coordinator Phase 8 will expose.

This module performs no retrieval, no LLM invocation, no
prompting, no database access, and no persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from .errors import DomainValidationError, require_tenant_context
from .evidence_context import EvidenceContextBudget
from .evidence_retrieval import DEFAULT_TOP_K
from .reasoning_application import (
    ComplianceReasoningApplication,
    ComplianceReasoningResult,
)

WORKFLOW_STATE_CREATED = "created"
WORKFLOW_STATE_INFORMATION_PROVIDED = "information_provided"
WORKFLOW_STATE_EVIDENCE_PENDING = "evidence_pending"
WORKFLOW_STATE_APPLICABILITY_DETERMINED = "applicability_determined"
WORKFLOW_STATE_ANALYSIS_AVAILABLE = "analysis_available"
WORKFLOW_STATE_REVIEW_REQUIRED = "review_required"
WORKFLOW_STATE_ADDITIONAL_EVIDENCE_REQUESTED = (
    "additional_evidence_requested")
WORKFLOW_STATE_REANALYSIS_REQUIRED = "reanalysis_required"
WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY = "assessment_package_ready"

WORKFLOW_STATES = frozenset({
    WORKFLOW_STATE_CREATED,
    WORKFLOW_STATE_INFORMATION_PROVIDED,
    WORKFLOW_STATE_EVIDENCE_PENDING,
    WORKFLOW_STATE_APPLICABILITY_DETERMINED,
    WORKFLOW_STATE_ANALYSIS_AVAILABLE,
    WORKFLOW_STATE_REVIEW_REQUIRED,
    WORKFLOW_STATE_ADDITIONAL_EVIDENCE_REQUESTED,
    WORKFLOW_STATE_REANALYSIS_REQUIRED,
    WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY,
})

# Phase 7.5 — explicit closure policy: a finalized workflow
# is permanently closed. The terminal state has no outgoing
# transition, so no evidence supply, re-analysis, review, or
# second finalization is possible; continuation after
# finalization is a fresh progression, never mutation of the
# finalized instance. This constant (with `is_closed`) makes
# that rule programmatically explicit for Phase 8.
WORKFLOW_TERMINAL_STATES = frozenset({
    WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY,
})

_WORKFLOW_TRANSITIONS: dict[str, tuple[str, ...]] = {
    WORKFLOW_STATE_CREATED: (
        WORKFLOW_STATE_INFORMATION_PROVIDED,
        WORKFLOW_STATE_EVIDENCE_PENDING,
    ),
    WORKFLOW_STATE_INFORMATION_PROVIDED: (
        WORKFLOW_STATE_EVIDENCE_PENDING,
        WORKFLOW_STATE_APPLICABILITY_DETERMINED,
    ),
    WORKFLOW_STATE_EVIDENCE_PENDING: (
        WORKFLOW_STATE_APPLICABILITY_DETERMINED,
    ),
    WORKFLOW_STATE_APPLICABILITY_DETERMINED: (
        WORKFLOW_STATE_ANALYSIS_AVAILABLE,
        WORKFLOW_STATE_EVIDENCE_PENDING,
    ),
    WORKFLOW_STATE_ANALYSIS_AVAILABLE: (
        WORKFLOW_STATE_REVIEW_REQUIRED,
        WORKFLOW_STATE_ADDITIONAL_EVIDENCE_REQUESTED,
    ),
    WORKFLOW_STATE_REVIEW_REQUIRED: (
        WORKFLOW_STATE_ADDITIONAL_EVIDENCE_REQUESTED,
        WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY,
    ),
    WORKFLOW_STATE_ADDITIONAL_EVIDENCE_REQUESTED: (
        WORKFLOW_STATE_REANALYSIS_REQUIRED,
    ),
    WORKFLOW_STATE_REANALYSIS_REQUIRED: (
        WORKFLOW_STATE_ANALYSIS_AVAILABLE,
    ),
    WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY: (),
}


class ComplianceWorkflowError(DomainValidationError):
    """A workflow integrity failure (fail closed).

    Raised for invalid identities, illegal state transitions,
    tenant/case mismatches, and result mismatches — never
    converted into a successful workflow state. Provider,
    retrieval, and analysis failures propagate unchanged
    under their own errors.
    """


@dataclass(frozen=True, slots=True)
class WorkflowAnalysisRound:
    """One completed analysis pass, distinguished by existing IDs.

    The round counter plus the deterministic report, analysis,
    trace, and input-fingerprint identities make every
    re-analysis distinguishable without a new versioning
    system.
    """

    round_index: int
    report_id: UUID
    analysis_ids: tuple[UUID, ...]
    trace_ids: tuple[UUID, ...]
    input_fingerprints: tuple[str, ...]

    def to_record(self) -> dict[str, Any]:
        return {
            "round_index": self.round_index,
            "report_id": str(self.report_id),
            "analysis_ids": [str(v) for v in self.analysis_ids],
            "trace_ids": [str(v) for v in self.trace_ids],
            "input_fingerprints": list(self.input_fingerprints),
        }


@dataclass(frozen=True, slots=True)
class ComplianceWorkflow:
    """Immutable user-workflow progression for one case.

    Process state only: identities, the current workflow
    state, completed analysis rounds, supplied evidence
    references, and requirements currently needing user
    action. Regulatory truth lives in the referenced Phase 6
    results, never here.
    """

    id: UUID
    tenant_id: UUID
    case_id: UUID
    shipment_id: UUID | None
    state: str
    rounds: tuple[WorkflowAnalysisRound, ...]
    supplied_evidence_ids: tuple[UUID, ...]
    open_requirements: tuple[UUID, ...]

    def to_record(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "tenant_id": str(self.tenant_id),
            "case_id": str(self.case_id),
            "shipment_id": (
                str(self.shipment_id)
                if self.shipment_id is not None else None),
            "state": self.state,
            "rounds": [r.to_record() for r in self.rounds],
            "supplied_evidence_ids": [
                str(v) for v in self.supplied_evidence_ids],
            "open_requirements": [
                str(v) for v in self.open_requirements],
        }


@dataclass(frozen=True, slots=True)
class AssessmentPackage:
    """Structured aggregation for the finished workflow.

    Composes existing authoritative information by reference:
    the latest Phase 6 result (analyses, report, traces), the
    untouched Phase 3.5 decision summary, the round history,
    and the requirements still carrying missing information.
    Not a decision engine: no verdict, no score, no
    reinterpretation.
    """

    workflow_id: UUID
    tenant_id: UUID
    case_id: UUID
    shipment_id: UUID | None
    state: str
    reasoning_result: ComplianceReasoningResult
    decision_summary: dict[str, Any] | None
    rounds: tuple[WorkflowAnalysisRound, ...]
    open_requirements: tuple[UUID, ...]

    def to_record(self) -> dict[str, Any]:
        return {
            "workflow_id": str(self.workflow_id),
            "tenant_id": str(self.tenant_id),
            "case_id": str(self.case_id),
            "shipment_id": (
                str(self.shipment_id)
                if self.shipment_id is not None else None),
            "state": self.state,
            "reasoning_result": self.reasoning_result.to_record(),
            "decision_summary": self.decision_summary,
            "rounds": [r.to_record() for r in self.rounds],
            "open_requirements": [
                str(v) for v in self.open_requirements],
        }


class ComplianceWorkflowService:
    """Pure domain coordinator for the compliance user workflow."""

    def __init__(
        self,
        *,
        reasoning_application: (
            ComplianceReasoningApplication | None) = None,
        readiness_service: Any | None = None,
    ) -> None:
        self._reasoning_application = (
            reasoning_application or ComplianceReasoningApplication())
        if not callable(getattr(
                self._reasoning_application, "analyze_case", None)):
            raise ComplianceWorkflowError(
                "a compliance reasoning application is required")
        self._readiness_service = readiness_service
        if (readiness_service is not None and not callable(getattr(
                readiness_service, "check", None))):
            raise ComplianceWorkflowError(
                "an assessment readiness service is required")

    def begin(
        self,
        *,
        tenant_id: Any,
        case_id: UUID,
        shipment_id: UUID | None = None,
    ) -> ComplianceWorkflow:
        """Enter a new workflow in its initial state."""
        require_tenant_context(tenant_id)
        tenant_uuid = tenant_id.tenant_id
        if not isinstance(case_id, UUID):
            raise ComplianceWorkflowError(
                "a case identity UUID is required")
        if shipment_id is not None and not isinstance(
                shipment_id, UUID):
            raise ComplianceWorkflowError(
                "a shipment identity UUID is required")
        workflow_id = uuid5(
            NAMESPACE_URL,
            ":".join([
                "xportra:compliance-workflow",
                tenant_uuid.hex,
                case_id.hex,
                shipment_id.hex if shipment_id is not None else "",
            ]),
        )
        return ComplianceWorkflow(
            id=workflow_id,
            tenant_id=tenant_uuid,
            case_id=case_id,
            shipment_id=shipment_id,
            state=WORKFLOW_STATE_CREATED,
            rounds=(),
            supplied_evidence_ids=(),
            open_requirements=(),
        )

    def provide_information(
        self, workflow: ComplianceWorkflow, *, tenant_id: Any
    ) -> ComplianceWorkflow:
        """Record that shipment information was provided."""
        return self._advance(
            workflow, tenant_id,
            WORKFLOW_STATE_INFORMATION_PROVIDED)

    def note_evidence_pending(
        self, workflow: ComplianceWorkflow, *, tenant_id: Any
    ) -> ComplianceWorkflow:
        """Record that evidence is awaited."""
        return self._advance(
            workflow, tenant_id, WORKFLOW_STATE_EVIDENCE_PENDING)

    def record_applicability_determined(
        self, workflow: ComplianceWorkflow, *, tenant_id: Any
    ) -> ComplianceWorkflow:
        """Record the deterministic applicability outcome."""
        return self._advance(
            workflow, tenant_id,
            WORKFLOW_STATE_APPLICABILITY_DETERMINED)

    def run_analysis(
        self,
        workflow: ComplianceWorkflow,
        cases: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        *,
        tenant_id: Any,
        rag_service: Any,
        mode: str,
        context_budget: EvidenceContextBudget,
        scope: Any | None = None,
        top_k: int = DEFAULT_TOP_K,
        candidate_pool: int | None = None,
        decision_summary: dict[str, Any] | None = None,
    ) -> tuple[ComplianceWorkflow, ComplianceReasoningResult]:
        """Run (or re-run) analysis via the Phase 6 boundary.

        State and tenant are validated before the composed
        application — and therefore before any retrieval or
        provider call. Each call appends a new round; nothing
        already recorded is mutated.
        """
        tenant_uuid = self._checked(workflow, tenant_id, (
            WORKFLOW_STATE_APPLICABILITY_DETERMINED,
            WORKFLOW_STATE_REANALYSIS_REQUIRED,
        ))
        result = self._reasoning_application.analyze_case(
            cases,
            tenant_id=tenant_id,
            case_id=workflow.case_id,
            rag_service=rag_service,
            mode=mode,
            context_budget=context_budget,
            scope=scope,
            top_k=top_k,
            candidate_pool=candidate_pool,
            decision_summary=decision_summary,
        )
        if result.case_id != workflow.case_id:
            raise ComplianceWorkflowError(
                "reasoning result belongs to a different case")
        if result.tenant_id != tenant_uuid:
            raise ComplianceWorkflowError(
                "reasoning result belongs to a different tenant")
        round_record = WorkflowAnalysisRound(
            round_index=len(workflow.rounds) + 1,
            report_id=result.report.id,
            analysis_ids=tuple(
                a.id for a in result.analyses),
            trace_ids=tuple(t.id for t in result.traces),
            input_fingerprints=tuple(
                t.input_fingerprint for t in result.traces),
        )
        advanced = replace(
            workflow,
            state=WORKFLOW_STATE_ANALYSIS_AVAILABLE,
            rounds=(*workflow.rounds, round_record),
            open_requirements=(),
        )
        return advanced, result

    def submit_for_review(
        self, workflow: ComplianceWorkflow, *, tenant_id: Any
    ) -> ComplianceWorkflow:
        """Hand the available analysis to user review."""
        return self._advance(
            workflow, tenant_id, WORKFLOW_STATE_REVIEW_REQUIRED)

    def request_additional_evidence(
        self,
        workflow: ComplianceWorkflow,
        *,
        tenant_id: Any,
        requirement_ids: list[UUID] | tuple[UUID, ...],
    ) -> ComplianceWorkflow:
        """Flag requirements needing user action (missing info)."""
        self._checked(workflow, tenant_id, (
            WORKFLOW_STATE_ANALYSIS_AVAILABLE,
            WORKFLOW_STATE_REVIEW_REQUIRED,
        ))
        if isinstance(requirement_ids, (str, bytes, UUID)):
            raise ComplianceWorkflowError(
                "requirement identities must be a list or tuple")
        if not isinstance(requirement_ids, (list, tuple)):
            raise ComplianceWorkflowError(
                "requirement identities must be a list or tuple")
        if not requirement_ids:
            raise ComplianceWorkflowError(
                "at least one requirement is required")
        for requirement_id in requirement_ids:
            if not isinstance(requirement_id, UUID):
                raise ComplianceWorkflowError(
                    "requirement identity is malformed")
        if len(set(requirement_ids)) != len(requirement_ids):
            raise ComplianceWorkflowError(
                "duplicate requirement identity in request")
        return replace(
            self._checked_workflow(workflow, tenant_id),
            state=WORKFLOW_STATE_ADDITIONAL_EVIDENCE_REQUESTED,
            open_requirements=tuple(requirement_ids),
        )

    def supply_evidence(
        self,
        workflow: ComplianceWorkflow,
        *,
        tenant_id: Any,
        evidence_ids: list[UUID] | tuple[UUID, ...],
    ) -> ComplianceWorkflow:
        """Record newly supplied evidence; re-analysis required."""
        self._checked(workflow, tenant_id, (
            WORKFLOW_STATE_ADDITIONAL_EVIDENCE_REQUESTED,
            WORKFLOW_STATE_REVIEW_REQUIRED,
        ))
        if isinstance(evidence_ids, (str, bytes, UUID)):
            raise ComplianceWorkflowError(
                "evidence identities must be a list or tuple")
        if not isinstance(evidence_ids, (list, tuple)):
            raise ComplianceWorkflowError(
                "evidence identities must be a list or tuple")
        if not evidence_ids:
            raise ComplianceWorkflowError(
                "at least one evidence identity is required")
        for evidence_id in evidence_ids:
            if not isinstance(evidence_id, UUID):
                raise ComplianceWorkflowError(
                    "evidence identity is malformed")
        known = list(workflow.supplied_evidence_ids)
        for evidence_id in evidence_ids:
            if evidence_id not in known:
                known.append(evidence_id)
        return replace(
            self._checked_workflow(workflow, tenant_id),
            state=WORKFLOW_STATE_REANALYSIS_REQUIRED,
            supplied_evidence_ids=tuple(known),
        )

    def is_closed(
        self, workflow: ComplianceWorkflow, *, tenant_id: Any
    ) -> bool:
        """Report whether the workflow is permanently closed.

        Phase 7.5 closure policy: a finalized workflow
        (`assessment_package_ready`, the sole member of
        `WORKFLOW_TERMINAL_STATES`) accepts no further
        operation — no evidence supply, no re-analysis, no
        review, no second finalization. The check is
        read-only and tenant-validated like every other
        operation.
        """
        checked = self._checked_workflow(workflow, tenant_id)
        return checked.state in WORKFLOW_TERMINAL_STATES

    def finalize(
        self,
        workflow: ComplianceWorkflow,
        reasoning_result: ComplianceReasoningResult,
        *,
        tenant_id: Any,
    ) -> tuple[ComplianceWorkflow, AssessmentPackage]:
        """Produce the final assessment package (aggregation only).

        The Phase 7.3 readiness gate runs first: a workflow
        that is not ready (wrong state, unbound shipment, no
        or stale analysis round, broken analysis/report/trace
        linkage, tenant/case mismatch) fails with a
        structured readiness failure and no package is
        produced. Carries the latest Phase 6 result and the
        untouched decision summary by reference. Requirements
        still carrying missing information are projected
        (read-only) from the result's own fields — never
        decided here.
        """
        readiness_service = self._readiness_service
        if readiness_service is None:
            from .assessment_readiness import (
                AssessmentReadinessService,
            )
            readiness_service = AssessmentReadinessService()
        readiness = readiness_service.check(
            workflow, reasoning_result, tenant_id=tenant_id)
        if not readiness.ready:
            reasons = "; ".join(
                f"{issue.code}: {issue.detail}"
                for issue in readiness.reasons)
            raise ComplianceWorkflowError(
                "workflow is not ready for finalization: "
                f"{reasons}")
        tenant_uuid = tenant_id.tenant_id
        open_requirements = tuple(
            a.requirement_id for a in reasoning_result.analyses
            if a.missing_information)
        package = AssessmentPackage(
            workflow_id=workflow.id,
            tenant_id=tenant_uuid,
            case_id=workflow.case_id,
            shipment_id=workflow.shipment_id,
            state=WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY,
            reasoning_result=reasoning_result,
            decision_summary=reasoning_result.decision_summary,
            rounds=workflow.rounds,
            open_requirements=open_requirements,
        )
        return (
            replace(
                workflow,
                state=WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY,
                open_requirements=open_requirements,
            ),
            package,
        )

    # ------------------------------------------------------------------
    # workflow integrity (fail closed)
    # ------------------------------------------------------------------

    @staticmethod
    def _checked_workflow(
        workflow: ComplianceWorkflow, tenant_id: Any
    ) -> ComplianceWorkflow:
        require_tenant_context(tenant_id)
        if not isinstance(workflow, ComplianceWorkflow):
            raise ComplianceWorkflowError(
                "a compliance workflow is required")
        if workflow.tenant_id != tenant_id.tenant_id:
            raise ComplianceWorkflowError(
                "workflow belongs to a different tenant")
        if workflow.state not in WORKFLOW_STATES:
            raise ComplianceWorkflowError(
                "workflow state is malformed")
        return workflow

    def _checked(
        self,
        workflow: ComplianceWorkflow,
        tenant_id: Any,
        allowed: tuple[str, ...],
    ) -> UUID:
        checked = self._checked_workflow(workflow, tenant_id)
        if checked.state not in allowed:
            raise ComplianceWorkflowError(
                f"workflow state {checked.state!r} does not "
                "permit this operation")
        return checked.tenant_id

    def _advance(
        self,
        workflow: ComplianceWorkflow,
        tenant_id: Any,
        target: str,
    ) -> ComplianceWorkflow:
        checked = self._checked_workflow(workflow, tenant_id)
        if target not in _WORKFLOW_TRANSITIONS[checked.state]:
            raise ComplianceWorkflowError(
                f"workflow cannot move from {checked.state!r} "
                f"to {target!r}")
        return replace(checked, state=target)


__all__ = [
    "WORKFLOW_STATES",
    "WORKFLOW_STATE_ADDITIONAL_EVIDENCE_REQUESTED",
    "WORKFLOW_STATE_ANALYSIS_AVAILABLE",
    "WORKFLOW_STATE_APPLICABILITY_DETERMINED",
    "WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY",
    "WORKFLOW_STATE_CREATED",
    "WORKFLOW_STATE_EVIDENCE_PENDING",
    "WORKFLOW_STATE_INFORMATION_PROVIDED",
    "WORKFLOW_STATE_REANALYSIS_REQUIRED",
    "WORKFLOW_STATE_REVIEW_REQUIRED",
    "AssessmentPackage",
    "ComplianceWorkflow",
    "ComplianceWorkflowError",
    "ComplianceWorkflowService",
    "WorkflowAnalysisRound",
]
