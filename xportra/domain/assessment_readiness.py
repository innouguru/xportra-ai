"""Workflow-to-assessment readiness gate for Phase 7.3.

The deterministic domain rule answering *is this workflow ready
to be finalized?* — never *is this shipment compliant?*:

```text
workflow + latest Phase 6 result
        ↓
AssessmentReadinessService.check (this module — pure)
        ↓
READY  →  ComplianceWorkflowService.finalize (7.1, unchanged
            package construction)
NOT READY  →  structured readiness failure (no package)
```

Readiness describes process completion only: the workflow is
in its review state, a shipment reference is bound (Phase
7.2), at least one analysis round completed, and the supplied
Phase 6 result is the latest recorded round with its
analysis/report/trace linkage intact. Regulatory truth stays
owned by the existing deterministic machinery and Phase 6
outputs: missing evidence, ``unknown`` or ``not_satisfied``
assessments, contradictions, and uncertainty never block
readiness, and the authoritative Phase 3.5 decision summary
is carried by reference (it may be absent — the 7.1 contract
accepts that — and is never recomputed here).

Staleness is a freshness rule, not a judgment: evidence
supplied after the latest analysis moves the workflow to
``reanalysis_required`` (wrong state for finalization), and a
result whose report no longer matches the latest recorded
round is stale. A fresh ``run_analysis`` plus review restores
readiness.

Failure semantics mirror the workflow boundary: malformed
inputs (bad tenant context, non-workflow, malformed state,
non-result) raise immediately; domain-level gaps return
``ready = False`` with deterministic issue codes;
provider/retrieval failures are impossible here — this module
performs no retrieval, no LLM invocation, no reasoning, no
persistence, and no database access.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from .compliance_workflow import (
    WORKFLOW_STATE_REVIEW_REQUIRED,
    WORKFLOW_STATES,
    ComplianceWorkflow,
    ComplianceWorkflowError,
)
from .errors import require_tenant_context
from .reasoning_application import ComplianceReasoningResult

READINESS_TENANT_MISMATCH = "tenant_mismatch"
READINESS_CASE_MISMATCH = "case_mismatch"
READINESS_INVALID_WORKFLOW_STATE = "invalid_workflow_state"
READINESS_MISSING_SHIPMENT_REFERENCE = "missing_shipment_reference"
READINESS_NO_ANALYSIS = "no_analysis"
READINESS_ANALYSIS_STALE = "analysis_stale"
READINESS_ANALYSIS_INTEGRITY_FAILURE = "analysis_integrity_failure"


@dataclass(frozen=True, slots=True)
class ReadinessIssue:
    """One deterministic reason a workflow is not ready."""

    code: str
    detail: str

    def to_record(self) -> dict[str, Any]:
        return {"code": self.code, "detail": self.detail}


@dataclass(frozen=True, slots=True)
class AssessmentReadiness:
    """Immutable readiness outcome for finalization.

    ``ready`` answers process readiness only — never a
    compliance verdict. ``reasons`` is empty exactly when
    ready, and lists deterministic issue codes otherwise.
    """

    ready: bool
    reasons: tuple[ReadinessIssue, ...]

    def to_record(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "reasons": [r.to_record() for r in self.reasons],
        }


class AssessmentReadinessService:
    """Pure readiness gate for workflow finalization."""

    def check(
        self,
        workflow: ComplianceWorkflow,
        reasoning_result: ComplianceReasoningResult,
        *,
        tenant_id: Any,
    ) -> AssessmentReadiness:
        """Evaluate whether finalization may proceed.

        Malformed inputs raise ``ComplianceWorkflowError``
        (corrupt state is never a readiness answer);
        domain-level gaps return ``ready = False`` with
        issue codes. No provider, retrieval, or reasoning
        call is possible on any path.
        """
        require_tenant_context(tenant_id)
        tenant_uuid = tenant_id.tenant_id
        if not isinstance(workflow, ComplianceWorkflow):
            raise ComplianceWorkflowError(
                "a compliance workflow is required")
        if workflow.state not in WORKFLOW_STATES:
            raise ComplianceWorkflowError(
                "workflow state is malformed")
        if not isinstance(
                reasoning_result, ComplianceReasoningResult):
            raise ComplianceWorkflowError(
                "a compliance reasoning result is required")

        issues: list[ReadinessIssue] = []
        if workflow.tenant_id != tenant_uuid:
            issues.append(ReadinessIssue(
                READINESS_TENANT_MISMATCH,
                "workflow belongs to a different tenant"))
        if reasoning_result.tenant_id != tenant_uuid:
            issues.append(ReadinessIssue(
                READINESS_TENANT_MISMATCH,
                "reasoning result belongs to a different tenant"))
        if reasoning_result.case_id != workflow.case_id:
            issues.append(ReadinessIssue(
                READINESS_CASE_MISMATCH,
                "reasoning result belongs to a different case"))
        if workflow.state != WORKFLOW_STATE_REVIEW_REQUIRED:
            issues.append(ReadinessIssue(
                READINESS_INVALID_WORKFLOW_STATE,
                f"workflow state {workflow.state!r} does not "
                "permit finalization"))
        if workflow.shipment_id is None:
            issues.append(ReadinessIssue(
                READINESS_MISSING_SHIPMENT_REFERENCE,
                "workflow has no bound shipment reference"))
        if not workflow.rounds:
            issues.append(ReadinessIssue(
                READINESS_NO_ANALYSIS,
                "no completed analysis round recorded"))
            return AssessmentReadiness(
                ready=not issues, reasons=tuple(issues))

        latest = workflow.rounds[-1]
        report = reasoning_result.report
        if report.id != latest.report_id:
            issues.append(ReadinessIssue(
                READINESS_ANALYSIS_STALE,
                "reasoning result does not match the latest "
                "recorded round"))
            return AssessmentReadiness(
                ready=not issues, reasons=tuple(issues))

        self._check_integrity(
            workflow, reasoning_result, latest, issues)
        return AssessmentReadiness(
            ready=not issues, reasons=tuple(issues))

    @staticmethod
    def _check_integrity(
        workflow: ComplianceWorkflow,
        reasoning_result: ComplianceReasoningResult,
        latest: Any,
        issues: list[ReadinessIssue],
    ) -> None:
        """Verify latest-round analysis/report/trace linkage."""
        analyses = reasoning_result.analyses
        report = reasoning_result.report
        traces = reasoning_result.traces
        analysis_ids = tuple(a.id for a in analyses)
        if analysis_ids != latest.analysis_ids:
            issues.append(ReadinessIssue(
                READINESS_ANALYSIS_INTEGRITY_FAILURE,
                "result analyses do not match the latest "
                "recorded round"))
        if tuple(a.id for a in report.analyses) != analysis_ids:
            issues.append(ReadinessIssue(
                READINESS_ANALYSIS_INTEGRITY_FAILURE,
                "report analyses do not match the result analyses"))
        for analysis in analyses:
            if analysis.tenant_id != workflow.tenant_id:
                issues.append(ReadinessIssue(
                    READINESS_ANALYSIS_INTEGRITY_FAILURE,
                    "analysis belongs to a different tenant"))
                break
        if tuple(t.id for t in traces) != latest.trace_ids:
            issues.append(ReadinessIssue(
                READINESS_ANALYSIS_INTEGRITY_FAILURE,
                "result traces do not match the latest "
                "recorded round"))
        if (tuple(t.input_fingerprint for t in traces)
                != latest.input_fingerprints):
            issues.append(ReadinessIssue(
                READINESS_ANALYSIS_INTEGRITY_FAILURE,
                "trace input fingerprints do not match the "
                "latest recorded round"))
        known = set(analysis_ids)
        for trace in traces:
            if trace.report_id != report.id:
                issues.append(ReadinessIssue(
                    READINESS_ANALYSIS_INTEGRITY_FAILURE,
                    "trace report reference does not match "
                    "the result report"))
                break
        for trace in traces:
            if trace.analysis_id not in known:
                issues.append(ReadinessIssue(
                    READINESS_ANALYSIS_INTEGRITY_FAILURE,
                    "trace analysis reference does not match "
                    "the result analyses"))
                break
        for trace in traces:
            if trace.tenant_id != workflow.tenant_id:
                issues.append(ReadinessIssue(
                    READINESS_ANALYSIS_INTEGRITY_FAILURE,
                    "trace belongs to a different tenant"))
                break


__all__ = [
    "READINESS_ANALYSIS_INTEGRITY_FAILURE",
    "READINESS_ANALYSIS_STALE",
    "READINESS_CASE_MISMATCH",
    "READINESS_INVALID_WORKFLOW_STATE",
    "READINESS_MISSING_SHIPMENT_REFERENCE",
    "READINESS_NO_ANALYSIS",
    "READINESS_TENANT_MISMATCH",
    "AssessmentReadiness",
    "AssessmentReadinessService",
    "ReadinessIssue",
]
