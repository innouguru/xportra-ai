"""Compliance-analysis use cases (Phase 6 via the workflow).

``AnalysisApplicationService`` orchestrates analysis runs
over an existing workflow progression: it rehydrates the
workflow record, enforces tenant ownership and terminal
closure *before* any expensive call, delegates the run to
the domain workflow service (which in turn delegates to
the Phase 6 composition boundary), and translates the
result into an ``AnalysisReportDTO``.

Retrieval/LLM infrastructure is never constructed here:
the RAG service is injected (production wiring lives in
``xportra.infrastructure``) and passed straight through
to the domain. Re-running analysis is the same use case —
the workflow state machine distinguishes first runs from
re-runs, not this layer. No applicability, assessment,
reasoning, or verdict logic exists here.

When a result store is configured, each successful run
is retained atomically (report, analyses, traces, round
linkage) so later requests can resolve the authoritative
result without trusting the client; retention failure
fails the request rather than silently dropping the
result.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from xportra.domain.compliance_workflow import (
    ComplianceWorkflowError,
    ComplianceWorkflowService,
)
from xportra.domain.errors import (
    LLMProviderError,
    VectorStoreError,
)
from xportra.domain.evidence_context import EvidenceContextBudget
from xportra.domain.evidence_retrieval import DEFAULT_TOP_K
from xportra.domain.reasoning_application import (
    ComplianceReasoningResult,
)

from ._guards import (
    checked_context,
    coerce_case_identities,
    ensure_tenant_match,
    workflow_from_record,
)
from .context import ApplicationContext
from .dtos import AnalysisReportDTO
from .errors import (
    ApplicationValidationError,
    InfrastructureError,
    InvalidTransitionError,
    TerminalWorkflowError,
    sanitized_detail,
)


class AnalysisApplicationService:
    """Stateless analysis use cases over workflow records."""

    def __init__(
        self,
        *,
        workflow_service: ComplianceWorkflowService | None = None,
        rag_service: Any,
        default_mode: str = "hybrid",
        result_store: Any | None = None,
    ) -> None:
        self._workflows = (
            workflow_service or ComplianceWorkflowService())
        if not callable(getattr(
                self._workflows, "run_analysis", None)):
            raise ApplicationValidationError(
                "a workflow service is required")
        if not callable(getattr(rag_service, "query", None)):
            raise ApplicationValidationError(
                "a retrieval service is required")
        if not isinstance(default_mode, str) or not default_mode.strip():
            raise ApplicationValidationError(
                "a default retrieval mode is required")
        if (result_store is not None
                and not callable(getattr(
                    result_store, "store_analysis_result", None))):
            raise ApplicationValidationError(
                "a result store is required")
        self._rag_service = rag_service
        self._default_mode = default_mode
        self._result_store = result_store

    def run_analysis(
        self,
        ctx: ApplicationContext,
        workflow_record: dict[str, Any],
        cases: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        *,
        mode: str | None = None,
        max_context_chars: int = 4000,
        top_k: int | None = None,
        candidate_pool: int | None = None,
        decision_summary: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], ComplianceReasoningResult,
               AnalysisReportDTO]:
        """Run (or re-run) compliance analysis for the workflow.

        Returns the updated workflow record, the live
        reasoning result (in-session for downstream use
        cases such as finalization), and the client-facing
        report DTO. ``decision_summary`` is the existing
        authoritative Phase 3.5 summary carried by
        reference when supplied.
        """
        ctx = checked_context(ctx)
        workflow = workflow_from_record(workflow_record)
        ensure_tenant_match(ctx, workflow.tenant_id, "workflow")
        self._ensure_open(ctx, workflow)
        checked_cases = [coerce_case_identities(case)
                         for case in _checked_cases(cases)]
        resolved_mode = _checked_mode(
            self._default_mode if mode is None else mode)
        budget = _checked_budget(max_context_chars)
        resolved_top_k = _checked_optional_positive(
            top_k, "top_k", DEFAULT_TOP_K)
        resolved_pool = _checked_optional_positive(
            candidate_pool, "candidate_pool", None)
        if decision_summary is not None and not isinstance(
                decision_summary, dict):
            raise ApplicationValidationError(
                "decision summary must be a mapping")
        decision_summary = _coerce_summary_scope(decision_summary)
        try:
            advanced, result = self._workflows.run_analysis(
                workflow, checked_cases,
                tenant_id=ctx.tenant,
                rag_service=self._rag_service,
                mode=resolved_mode,
                context_budget=budget,
                top_k=resolved_top_k,
                candidate_pool=resolved_pool,
                decision_summary=decision_summary,
            )
        except ComplianceWorkflowError as cause:
            raise InvalidTransitionError(
                str(cause), cause=cause) from cause
        except (LLMProviderError, VectorStoreError) as cause:
            raise InfrastructureError(
                sanitized_detail(cause), cause=cause) from cause
        if self._result_store is not None:
            self._result_store.store_analysis_result(
                ctx, advanced, result)
        return (advanced.to_record(), result,
                AnalysisReportDTO.from_result(result))

    def describe_report(
        self,
        result: ComplianceReasoningResult,
    ) -> AnalysisReportDTO:
        """Project a reasoning result to its report DTO."""
        if not isinstance(result, ComplianceReasoningResult):
            raise ApplicationValidationError(
                "a compliance reasoning result is required")
        return AnalysisReportDTO.from_result(result)

    def _ensure_open(self, ctx: ApplicationContext,
                     workflow: Any) -> None:
        try:
            closed = self._workflows.is_closed(
                workflow, tenant_id=ctx.tenant)
        except ComplianceWorkflowError as cause:
            raise InvalidTransitionError(
                str(cause), cause=cause) from cause
        if closed:
            raise TerminalWorkflowError(
                "workflow is permanently closed; start a fresh "
                "progression for further work")


def _coerce_summary_scope(
        decision_summary: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Restore the summary tenant identity from its wire form.

    Summaries crossing HTTP carry the tenant UUID as a
    string while the domain compares UUID objects.
    Unparseable values pass through for domain validation
    to reject with its own error.
    """
    if decision_summary is None:
        return None
    tenant_id = decision_summary.get("tenant_id")
    if isinstance(tenant_id, str):
        try:
            return {**decision_summary, "tenant_id": UUID(tenant_id)}
        except ValueError:
            return decision_summary
    return decision_summary


def _checked_cases(cases: Any) -> list[dict[str, Any]]:
    if (not isinstance(cases, (list, tuple))
            or not cases
            or isinstance(cases, (str, bytes, dict))):
        raise ApplicationValidationError(
            "at least one compliance case is required")
    for case in cases:
        if not isinstance(case, dict):
            raise ApplicationValidationError(
                "a compliance case is required")
    return list(cases)


def _checked_mode(mode: Any) -> str:
    if not isinstance(mode, str) or not mode.strip():
        raise ApplicationValidationError(
            "a retrieval mode is required")
    return mode


def _checked_budget(max_context_chars: Any) -> EvidenceContextBudget:
    if (not isinstance(max_context_chars, int)
            or isinstance(max_context_chars, bool)
            or max_context_chars <= 0):
        raise ApplicationValidationError(
            "a positive context budget is required")
    return EvidenceContextBudget(max_context_chars)


def _checked_optional_positive(value: Any, field: str,
                               default: int | None) -> int | None:
    if value is None:
        return default
    if (not isinstance(value, int)
            or isinstance(value, bool)
            or value <= 0):
        raise ApplicationValidationError(
            f"a positive {field} is required")
    return value


__all__ = [
    "AnalysisApplicationService",
]
