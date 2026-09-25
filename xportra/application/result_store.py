"""Server-side retention for Phase 6 results (Phase 8.4).

``ComplianceResultStore`` persists already-produced
authoritative result representations and rebuilds the
exact Phase 6 domain objects from them:

```text
ComplianceReasoningResult (+ workflow linkage)
        ↓ store_analysis_result (one transaction)
reports / analyses / traces / round rows
        ↓ load_current_result / load_result
ComplianceReasoningResult (rebuilt, linkage-verified)
```

This is retention, not a second compliance system: no
applicability, assessment, risk, reasoning, retrieval,
sufficiency, verdict, readiness, or transition logic
exists here. Counts are carried, never recomputed;
reports compose nothing; traces decide nothing.

Idempotency: natural keys are content-derived (uuid5),
so retrying the same result converges — conflicts
resolve by returning the matching stored representation
after verification. Round slots are first-writer-wins:
a divergent concurrent analysis keeps its own valid
client record but does not displace recorded linkage.

Reconstruction is strict data assembly with linkage
validation (tenant/case/report/analysis/trace
cross-checks); malformed or inconsistent rows fail
closed. Corrupt storage never becomes a result.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from xportra.domain.compliance_reasoning import (
    APPLICABILITY_STATES,
    ASSESSMENT_STATES,
    ComplianceAnalysis,
    EvidenceReference,
    KnowledgeReference,
    SourceReference,
)
from xportra.domain.compliance_report import (
    ComplianceAnalysisReport,
    RequirementMissingInformation,
)
from xportra.domain.compliance_workflow import (
    ComplianceWorkflow,
    WorkflowAnalysisRound,
)
from xportra.domain.decision_trace import DecisionTrace, TraceStep
from xportra.domain.errors import DomainPersistenceError
from xportra.domain.evidence_sufficiency import (
    CONTRADICTION_NONE,
    CONTRADICTION_PRESENT,
    SUFFICIENCY_INSUFFICIENT,
    SUFFICIENCY_MISSING,
    SUFFICIENCY_SUPPORTED,
    SUFFICIENCY_UNKNOWN,
)
from xportra.domain.reasoning_application import (
    ComplianceReasoningResult,
)
from xportra.persistence.errors import PersistenceIntegrityError

from ._guards import checked_context, ensure_tenant_match
from .context import ApplicationContext
from .errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
    InfrastructureError,
    sanitized_detail,
)

_SUFFICIENCY_STATES = frozenset({
    SUFFICIENCY_SUPPORTED,
    SUFFICIENCY_INSUFFICIENT,
    SUFFICIENCY_MISSING,
    SUFFICIENCY_UNKNOWN,
})
_CONTRADICTION_STATES = frozenset({
    CONTRADICTION_NONE,
    CONTRADICTION_PRESENT,
})


class ComplianceResultStore:
    """Atomic retention and exact reconstruction of results."""

    def __init__(
        self,
        *,
        database: Any,
        reports: Any,
        analyses: Any,
        traces: Any,
        rounds: Any,
        packages: Any,
    ) -> None:
        if database is None or not callable(
                getattr(database, "transaction", None)):
            raise ApplicationValidationError(
                "a database is required")
        for name, repository, method in (
            ("report", reports, "create_in_transaction"),
            ("analysis", analyses, "create_in_transaction"),
            ("trace", traces, "create_in_transaction"),
            ("round", rounds, "create_in_transaction"),
            ("package", packages, "create_in_transaction"),
        ):
            if not callable(getattr(repository, method, None)):
                raise ApplicationValidationError(
                    f"a result {name} repository is required")
        self._database = database
        self._reports = reports
        self._analyses = analyses
        self._traces = traces
        self._rounds = rounds
        self._packages = packages

    # ------------------------------------------------------------------
    # writes (single transaction per result)
    # ------------------------------------------------------------------

    def store_analysis_result(
        self,
        ctx: ApplicationContext,
        workflow: ComplianceWorkflow,
        result: ComplianceReasoningResult,
    ) -> dict[str, Any]:
        """Persist one analysis round and its result atomically.

        Returns the stored linkage (report id, round index,
        ordered analysis/trace ids). Retrying the identical
        result returns the existing linkage after
        verification instead of duplicating rows.
        """
        from xportra.domain.compliance_workflow import (
            ComplianceWorkflow as _Workflow,
        )

        ctx = checked_context(ctx)
        if not isinstance(workflow, _Workflow):
            raise ApplicationValidationError(
                "a compliance workflow is required")
        if not isinstance(result, ComplianceReasoningResult):
            raise ApplicationValidationError(
                "a compliance reasoning result is required")
        ensure_tenant_match(ctx, workflow.tenant_id, "workflow")
        ensure_tenant_match(
            ctx, result.tenant_id, "reasoning result")
        if result.case_id != workflow.case_id:
            raise ApplicationValidationError(
                "reasoning result belongs to a different case")
        if not workflow.rounds:
            raise ApplicationValidationError(
                "workflow has no recorded round to store")
        latest = workflow.rounds[-1]
        if result.report.id != latest.report_id:
            raise ApplicationValidationError(
                "reasoning result does not match the latest "
                "recorded round")
        existing = self._reports.get(ctx.tenant, result.report.id)
        if existing is not None:
            return self._adopt_stored_report(
                ctx, workflow, result, latest, existing)
        try:
            with self._database.transaction() as connection:
                self._store_report(
                    connection, ctx, workflow, result)
                self._store_analyses(
                    connection, ctx, workflow, result)
                self._store_traces(
                    connection, ctx, workflow, result)
                self._store_round(
                    connection, ctx, workflow, latest)
        except PersistenceIntegrityError:
            return self._adopt_after_conflict(
                ctx, workflow, result, latest)
        except DomainPersistenceError as cause:
            raise InfrastructureError(
                sanitized_detail(cause), cause=cause) from cause
        return {
            "report_id": result.report.id,
            "round_index": latest.round_index,
            "analysis_ids": tuple(
                a.id for a in result.analyses),
            "trace_ids": tuple(
                t.id for t in result.traces),
        }

    def _adopt_stored_report(
        self,
        ctx: ApplicationContext,
        workflow: ComplianceWorkflow,
        result: ComplianceReasoningResult,
        latest: WorkflowAnalysisRound,
        existing: dict[str, Any],
    ) -> dict[str, Any]:
        """Converge a retry onto an already-stored report.

        Retried persistence and deterministically converged
        recomputations share content-derived identities, so
        the stored representation is adopted after scope
        verification instead of duplicating rows. Only the
        round linkage is (idempotently) written.
        """
        self._verify_report_scope(
            existing, ctx, workflow, result)
        stored_analyses = self._analyses.list_for_report(
            ctx.tenant, result.report.id)
        stored_traces = self._traces.list_for_report(
            ctx.tenant, result.report.id)
        if (len(stored_analyses) != len(result.analyses)
                or len(stored_traces) != len(result.traces)):
            raise InfrastructureError(
                "stored report is missing its stored analyses")
        self._write_round(ctx, workflow, latest)
        return {
            "report_id": result.report.id,
            "round_index": latest.round_index,
            "analysis_ids": tuple(
                a.id for a in result.analyses),
            "trace_ids": tuple(
                t.id for t in result.traces),
        }

    def _adopt_after_conflict(
        self,
        ctx: ApplicationContext,
        workflow: ComplianceWorkflow,
        result: ComplianceReasoningResult,
        latest: WorkflowAnalysisRound,
    ) -> dict[str, Any]:
        """Recover a lost same-content write race atomically.

        The transaction rolled back, so a concurrent commit
        of the identical result must now be visible;
        anything else is a genuine conflict or corruption.
        """
        existing = self._reports.get(ctx.tenant, result.report.id)
        if existing is None:
            raise InfrastructureError(
                "result storage conflicted without a stored report")
        return self._adopt_stored_report(
            ctx, workflow, result, latest, existing)

    def _verify_report_scope(
        self,
        existing: dict[str, Any],
        ctx: ApplicationContext,
        workflow: ComplianceWorkflow,
        result: ComplianceReasoningResult,
    ) -> None:
        if (existing.get("case_id") != result.case_id
                or existing.get("workflow_id") != workflow.id):
            raise InfrastructureError(
                "stored report scope does not match the workflow")
        if existing.get("tenant_id") != ctx.tenant_id:
            raise InfrastructureError(
                "stored report belongs to a different tenant")

    def _write_round(
        self,
        ctx: ApplicationContext,
        workflow: ComplianceWorkflow,
        latest: WorkflowAnalysisRound,
    ) -> None:
        """Idempotently record round linkage (first writer wins).

        A divergent concurrent analysis keeps its own valid
        client record but does not displace recorded
        linkage; attempting to finalize through it fails
        closed on the mismatch instead.
        """
        try:
            with self._database.transaction() as connection:
                self._store_round(
                    connection, ctx, workflow, latest)
        except PersistenceIntegrityError:
            stored = self._rounds.get(
                ctx.tenant, workflow.id, latest.round_index)
            if stored is None or (
                    stored["report_id"] != latest.report_id):
                raise InfrastructureError(
                    "round slot already holds a different report")
        except DomainPersistenceError as cause:
            raise InfrastructureError(
                sanitized_detail(cause), cause=cause) from cause

    def store_package_linkage(
        self,
        ctx: ApplicationContext,
        workflow: ComplianceWorkflow,
        report_id: UUID,
        round_index: int,
        open_requirements: list[UUID] | tuple[UUID, ...],
    ) -> dict[str, Any]:
        """Record that a workflow finalized (linkage only).

        The package row pins workflow/case/report/round
        identities plus the open-requirement snapshot. All
        compliance content stays in the result tables; the
        summary stays carried by the stored report. At most
        one row per workflow can ever exist, which is what
        makes cross-request second-finalization
        structurally impossible — a conflicting insert
        surfaces as the persistence integrity failure the
        caller maps to terminal closure.
        """
        from xportra.domain.compliance_workflow import (
            ComplianceWorkflow as _Workflow,
        )

        ctx = checked_context(ctx)
        if not isinstance(workflow, _Workflow):
            raise ApplicationValidationError(
                "a compliance workflow is required")
        ensure_tenant_match(ctx, workflow.tenant_id, "workflow")
        if not isinstance(report_id, UUID):
            raise ApplicationValidationError(
                "a report identity UUID is required")
        if (not isinstance(round_index, int)
                or isinstance(round_index, bool)
                or round_index < 1):
            raise ApplicationValidationError(
                "a positive round index is required")
        if not isinstance(open_requirements, (list, tuple)):
            raise ApplicationValidationError(
                "open requirements must be a list or tuple")
        for requirement_id in open_requirements:
            if not isinstance(requirement_id, UUID):
                raise ApplicationValidationError(
                    "open requirement identity is malformed")
        try:
            with self._database.transaction() as connection:
                row = self._packages.create_in_transaction(
                    connection,
                    ctx.tenant,
                    workflow.id,
                    workflow.case_id,
                    workflow.shipment_id,
                    report_id,
                    round_index,
                    [str(v) for v in open_requirements],
                )
        except (PersistenceIntegrityError,
                DomainPersistenceError) as cause:
            raise InfrastructureError(
                sanitized_detail(cause), cause=cause) from cause
        return {
            "workflow_id": workflow.id,
            "report_id": report_id,
            "round_index": round_index,
        }

    def _store_report(self, connection, ctx, workflow,
                      result) -> None:
        report = result.report
        self._reports.create_in_transaction(
            connection,
            ctx.tenant,
            report.id,
            report.case_id,
            workflow.id,
            report.context_fingerprint,
            {
                "total_requirements": report.total_requirements,
                "applicable_count": report.applicable_count,
                "satisfied_count": report.satisfied_count,
                "not_satisfied_count":
                    report.not_satisfied_count,
                "unknown_count": report.unknown_count,
                "not_applicable_count":
                    report.not_applicable_count,
            },
            [str(v) for v in
             report.requirements_with_missing_information],
            [str(v) for v in report.uncertain_requirement_ids],
            [str(v) for v in
             report.requirements_with_conflicting_evidence],
            [e.to_record()
             for e in report.missing_information],
            report.conflicting_evidence_count,
            _jsonable(report.decision_summary),
        )

    def _store_analyses(self, connection, ctx, workflow,
                        result) -> None:
        for position, analysis in enumerate(result.analyses):
            self._analyses.create_in_transaction(
                connection,
                ctx.tenant,
                analysis.id,
                result.report.id,
                result.case_id,
                workflow.id,
                analysis.requirement_id,
                position,
                analysis.requirement_text,
                analysis.applicability,
                analysis.assessment,
                analysis.explanation,
                analysis.uncertainty,
                analysis.uncertainty_explanation,
                analysis.evidence_sufficiency,
                analysis.contradiction_state,
                analysis.sufficiency_explanation,
                list(analysis.missing_information),
                [e.to_record()
                 for e in analysis.supporting_evidence],
                [e.to_record()
                 for e in analysis.conflicting_evidence],
                [k.to_record()
                 for k in analysis.knowledge_references],
                [s.to_record() for s in analysis.sources],
                [i.to_record()
                 for i in analysis.missing_items],
            )

    def _store_traces(self, connection, ctx, workflow,
                      result) -> None:
        for position, trace in enumerate(result.traces):
            self._traces.create_in_transaction(
                connection,
                ctx.tenant,
                trace.id,
                result.report.id,
                trace.analysis_id,
                trace.case_id,
                workflow.id,
                trace.requirement_id,
                position,
                trace.context_fingerprint,
                trace.applicability,
                trace.assessment,
                trace.explanation,
                trace.evidence_sufficiency,
                trace.contradiction_state,
                trace.sufficiency_explanation,
                trace.uncertainty,
                list(trace.missing_information),
                trace.answer_fingerprint,
                trace.input_fingerprint,
                [s.to_record() for s in trace.steps],
                [e.to_record()
                 for e in trace.supporting_evidence],
                [e.to_record()
                 for e in trace.conflicting_evidence],
                [k.to_record()
                 for k in trace.knowledge_references],
                [s.to_record() for s in trace.sources],
            )

    def _store_round(self, connection, ctx, workflow,
                     latest) -> None:
        self._rounds.create_in_transaction(
            connection,
            ctx.tenant,
            workflow.id,
            latest.round_index,
            workflow.case_id,
            workflow.shipment_id,
            latest.report_id,
            [str(v) for v in latest.analysis_ids],
            [str(v) for v in latest.trace_ids],
            list(latest.input_fingerprints),
        )

    # ------------------------------------------------------------------
    # reads (tenant-scoped, non-leaking, validated)
    # ------------------------------------------------------------------

    def load_result(
        self,
        ctx: ApplicationContext,
        report_id: UUID,
    ) -> ComplianceReasoningResult:
        """Rebuild the exact stored result for this tenant."""
        ctx = checked_context(ctx)
        if not isinstance(report_id, UUID):
            raise ApplicationValidationError(
                "a report identity UUID is required")
        report_row = self._reports.get(ctx.tenant, report_id)
        if report_row is None:
            raise ApplicationNotFoundError(
                "analysis report was not found")
        analysis_rows = self._analyses.list_for_report(
            ctx.tenant, report_id)
        trace_rows = self._traces.list_for_report(
            ctx.tenant, report_id)
        return rebuild_result(report_row, analysis_rows, trace_rows)

    def latest_round_for_workflow(
        self,
        ctx: ApplicationContext,
        workflow_id: UUID,
    ) -> dict[str, Any] | None:
        """Return the recorded latest round linkage, if any."""
        ctx = checked_context(ctx)
        if not isinstance(workflow_id, UUID):
            raise ApplicationValidationError(
                "a workflow identity UUID is required")
        row = self._rounds.latest_for_workflow(
            ctx.tenant, workflow_id)
        if row is None:
            return None
        return {
            "workflow_id": row["workflow_id"],
            "round_index": row["round_index"],
            "case_id": row["case_id"],
            "shipment_id": row["shipment_id"],
            "report_id": row["report_id"],
            "analysis_ids": tuple(row["analysis_ids"]),
            "trace_ids": tuple(row["trace_ids"]),
            "input_fingerprints": tuple(
                row["input_fingerprints"]),
        }

    def rounds_for_workflow(
        self,
        ctx: ApplicationContext,
        workflow_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return all recorded round linkages in round order."""
        ctx = checked_context(ctx)
        if not isinstance(workflow_id, UUID):
            raise ApplicationValidationError(
                "a workflow identity UUID is required")
        return [
            {
                "workflow_id": row["workflow_id"],
                "round_index": row["round_index"],
                "case_id": row["case_id"],
                "shipment_id": row["shipment_id"],
                "report_id": row["report_id"],
                "analysis_ids": tuple(row["analysis_ids"]),
                "trace_ids": tuple(row["trace_ids"]),
                "input_fingerprints": tuple(
                    row["input_fingerprints"]),
            }
            for row in self._rounds.list_for_workflow(
                ctx.tenant, workflow_id)
        ]

    def load_package(
        self,
        ctx: ApplicationContext,
        workflow_id: UUID,
    ) -> dict[str, Any] | None:
        """Return the stored package linkage, if any."""
        ctx = checked_context(ctx)
        if not isinstance(workflow_id, UUID):
            raise ApplicationValidationError(
                "a workflow identity UUID is required")
        row = self._packages.get(ctx.tenant, workflow_id)
        if row is None:
            return None
        return {
            "workflow_id": row["workflow_id"],
            "case_id": row["case_id"],
            "shipment_id": row["shipment_id"],
            "report_id": row["report_id"],
            "round_index": row["round_index"],
            "open_requirements": tuple(
                row["open_requirements"]),
        }


__all__ = [
    "ComplianceResultStore",
    "rebuild_analysis",
    "rebuild_report",
    "rebuild_result",
    "rebuild_trace",
]


# ----------------------------------------------------------------------
# reconstruction (validated data assembly, no recomputation)
# ----------------------------------------------------------------------

def _jsonable(value: Any) -> Any:
    """Normalize caller-supplied structures for JSONB storage.

    UUID objects become strings (JSON has no UUID type);
    mappings and sequences recurse; everything else passes
    through for the repository to reject if unserializable.
    Applied only to the carried decision summary — every
    other stored payload is already emitted stringified by
    the domain ``to_record()`` contracts.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: _jsonable(item)
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _require_uuid(value: Any, field: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError, AttributeError) as cause:
        raise ApplicationValidationError(
            f"stored {field} identity is malformed") from cause


def _require_text(record: Any, field: str) -> str:
    value = record.get(field) if isinstance(record, dict) else None
    if not isinstance(value, str):
        raise ApplicationValidationError(
            f"stored {field} is malformed")
    return value


def _require_text_list(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ApplicationValidationError(
            f"stored {field} is malformed")
    for item in value:
        if not isinstance(item, str):
            raise ApplicationValidationError(
                f"stored {field} is malformed")
    return tuple(value)


def _require_mapping_list(value: Any,
                          field: str) -> tuple[dict[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        raise ApplicationValidationError(
            f"stored {field} is malformed")
    for item in value:
        if not isinstance(item, dict):
            raise ApplicationValidationError(
                f"stored {field} is malformed")
    return tuple(value)


def _check_state(value: Any, field: str,
                 allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        raise ApplicationValidationError(
            f"stored {field} is malformed")
    return value


def _evidence_reference(item: dict[str, Any]) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=_require_uuid(
            item.get("evidence_id"), "evidence"),
        evidence_type=_require_text(
            item, "evidence_type"),
        reference=_require_text(item, "reference"),
        status=_require_text(item, "status"),
    )


def _knowledge_reference(item: dict[str, Any]) -> KnowledgeReference:
    rank_position = item.get("rank_position")
    if (not isinstance(rank_position, int)
            or isinstance(rank_position, bool)):
        raise ApplicationValidationError(
            "stored knowledge rank is malformed")
    return KnowledgeReference(
        label=_require_text(item, "label"),
        rank_position=rank_position,
        chunk_id=_require_uuid(item.get("chunk_id"), "chunk"),
        document_id=_require_uuid(
            item.get("document_id"), "document"),
        source_id=_require_text(item, "source_id"),
        source_type=_require_text(item, "source_type"),
        source_location=item.get("source_location"),
        document_version=item.get("document_version"),
        content_fingerprint=_require_text(
            item, "content_fingerprint"),
    )


def _source_reference(item: dict[str, Any]) -> SourceReference:
    identifier = item.get("identifier")
    if identifier is not None and not isinstance(
            identifier, str):
        raise ApplicationValidationError(
            "stored source identifier is malformed")
    return SourceReference(
        kind=_require_text(item, "kind"),
        identifier=identifier,
    )


def _missing_item(item: dict[str, Any]):
    from xportra.domain.evidence_sufficiency import (
        MissingInformationItem,
    )

    return MissingInformationItem(
        requirement_id=_require_uuid(
            item.get("requirement_id"), "requirement"),
        kind=_require_text(item, "kind"),
        detail=_require_text(item, "detail"),
    )


def rebuild_analysis(row: dict[str, Any]) -> ComplianceAnalysis:
    """Rebuild one analysis from its stored row (exact)."""
    if not isinstance(row, dict):
        raise ApplicationValidationError(
            "stored analysis is malformed")
    return ComplianceAnalysis(
        id=_require_uuid(row.get("id"), "analysis"),
        tenant_id=_require_uuid(
            row.get("tenant_id"), "tenant"),
        requirement_id=_require_uuid(
            row.get("requirement_id"), "requirement"),
        requirement_text=_require_text(
            row, "requirement_text"),
        applicability=_check_state(
            row.get("applicability"), "applicability",
            APPLICABILITY_STATES),
        assessment=_check_state(
            row.get("assessment"), "assessment",
            ASSESSMENT_STATES),
        explanation=_require_text(row, "explanation"),
        supporting_evidence=tuple(
            _evidence_reference(item) for item in
            _require_mapping_list(
                row.get("supporting_evidence"),
                "supporting evidence")),
        conflicting_evidence=tuple(
            _evidence_reference(item) for item in
            _require_mapping_list(
                row.get("conflicting_evidence"),
                "conflicting evidence")),
        knowledge_references=tuple(
            _knowledge_reference(item) for item in
            _require_mapping_list(
                row.get("knowledge_references"),
                "knowledge references")),
        sources=tuple(
            _source_reference(item) for item in
            _require_mapping_list(row.get("sources"), "sources")),
        missing_information=_require_text_list(
            row.get("missing_information"),
            "missing information"),
        uncertainty=_require_text(row, "uncertainty"),
        uncertainty_explanation=_require_text(
            row, "uncertainty_explanation"),
        evidence_sufficiency=_check_state(
            row.get("evidence_sufficiency"),
            "evidence sufficiency", _SUFFICIENCY_STATES),
        contradiction_state=_check_state(
            row.get("contradiction_state"),
            "contradiction state", _CONTRADICTION_STATES),
        sufficiency_explanation=_require_text(
            row, "sufficiency_explanation"),
        missing_items=tuple(
            _missing_item(item) for item in
            _require_mapping_list(
                row.get("missing_items"), "missing items")),
    )


def rebuild_report(row: dict[str, Any],
                   analyses: tuple[ComplianceAnalysis, ...],
                   ) -> ComplianceAnalysisReport:
    """Rebuild one report around its rebuilt analyses."""
    if not isinstance(row, dict):
        raise ApplicationValidationError(
            "stored report is malformed")
    for field in ("total_requirements", "applicable_count",
                  "satisfied_count", "not_satisfied_count",
                  "unknown_count", "not_applicable_count",
                  "conflicting_evidence_count"):
        value = row.get(field)
        if (not isinstance(value, int)
                or isinstance(value, bool) or value < 0):
            raise ApplicationValidationError(
                f"stored report {field} is malformed")
    decision_summary = row.get("decision_summary")
    if decision_summary is not None and not isinstance(
            decision_summary, dict):
        raise ApplicationValidationError(
            "stored decision summary is malformed")
    missing_entries = []
    for item in _require_mapping_list(
            row.get("missing_information"),
            "missing information"):
        missing_entries.append(
            RequirementMissingInformation(
                requirement_id=_require_uuid(
                    item.get("requirement_id"), "requirement"),
                items=_require_text_list(
                    item.get("items"), "missing items"),
            )
        )
    return ComplianceAnalysisReport(
        id=_require_uuid(row.get("id"), "report"),
        tenant_id=_require_uuid(row.get("tenant_id"), "tenant"),
        case_id=_require_uuid(row.get("case_id"), "case"),
        context_fingerprint=row.get("context_fingerprint"),
        analyses=analyses,
        total_requirements=row["total_requirements"],
        applicable_count=row["applicable_count"],
        satisfied_count=row["satisfied_count"],
        not_satisfied_count=row["not_satisfied_count"],
        unknown_count=row["unknown_count"],
        not_applicable_count=row["not_applicable_count"],
        requirements_with_missing_information=tuple(
            _require_uuid(v, "requirement") for v in
            _require_uuid_list(
                row.get("requirements_with_missing_information"),
                "missing requirements")),
        missing_information=tuple(missing_entries),
        uncertain_requirement_ids=tuple(
            _require_uuid(v, "requirement") for v in
            _require_uuid_list(
                row.get("uncertain_requirement_ids"),
                "uncertain requirements")),
        requirements_with_conflicting_evidence=tuple(
            _require_uuid(v, "requirement") for v in
            _require_uuid_list(
                row.get("requirements_with_conflicting_evidence"),
                "conflicting requirements")),
        conflicting_evidence_count=row[
            "conflicting_evidence_count"],
        decision_summary=decision_summary,
    )


def _require_uuid_list(value: Any,
                       field: str) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise ApplicationValidationError(
            f"stored {field} is malformed")
    return tuple(value)


def rebuild_trace(row: dict[str, Any]) -> DecisionTrace:
    """Rebuild one trace from its stored row (exact)."""
    if not isinstance(row, dict):
        raise ApplicationValidationError(
            "stored trace is malformed")
    steps = []
    for item in _require_mapping_list(
            row.get("steps"), "trace steps"):
        sequence = item.get("sequence")
        references = item.get("references")
        if (not isinstance(sequence, int)
                or isinstance(sequence, bool)
                or not isinstance(references, list)
                or any(not isinstance(r, str)
                       for r in references)):
            raise ApplicationValidationError(
                "stored trace step is malformed")
        steps.append(TraceStep(
            sequence=sequence,
            name=_require_text(item, "name"),
            references=tuple(references),
            detail=item.get("detail")
            if isinstance(item.get("detail"), str) else "",
        ))
    report_id = row.get("report_id")
    return DecisionTrace(
        id=_require_uuid(row.get("id"), "trace"),
        tenant_id=_require_uuid(row.get("tenant_id"), "tenant"),
        case_id=_require_uuid(row.get("case_id"), "case"),
        requirement_id=_require_uuid(
            row.get("requirement_id"), "requirement"),
        analysis_id=_require_uuid(
            row.get("analysis_id"), "analysis"),
        report_id=(None if report_id is None
                   else _require_uuid(report_id, "report")),
        context_fingerprint=row.get("context_fingerprint"),
        applicability=_require_text(row, "applicability"),
        assessment=_require_text(row, "assessment"),
        supporting_evidence=tuple(
            _evidence_reference(item) for item in
            _require_mapping_list(
                row.get("supporting_evidence"),
                "supporting evidence")),
        conflicting_evidence=tuple(
            _evidence_reference(item) for item in
            _require_mapping_list(
                row.get("conflicting_evidence"),
                "conflicting evidence")),
        knowledge_references=tuple(
            _knowledge_reference(item) for item in
            _require_mapping_list(
                row.get("knowledge_references"),
                "knowledge references")),
        sources=tuple(
            _source_reference(item) for item in
            _require_mapping_list(row.get("sources"), "sources")),
        explanation=_require_text(row, "explanation"),
        evidence_sufficiency=_require_text(
            row, "evidence_sufficiency"),
        contradiction_state=_require_text(
            row, "contradiction_state"),
        sufficiency_explanation=_require_text(
            row, "sufficiency_explanation"),
        uncertainty=_require_text(row, "uncertainty"),
        missing_information=_require_text_list(
            row.get("missing_information"),
            "missing information"),
        answer_fingerprint=_require_text(
            row, "answer_fingerprint"),
        input_fingerprint=_require_text(
            row, "input_fingerprint"),
        steps=tuple(steps),
    )


def rebuild_result(
    report_row: dict[str, Any],
    analysis_rows: list[dict[str, Any]],
    trace_rows: list[dict[str, Any]],
) -> ComplianceReasoningResult:
    """Rebuild one reasoning result with linkage validation.

    Analyses rebuild in stored position order; traces
    reattach by analysis identity; every cross-link
    (report↔analyses↔traces, tenant, case) is verified
    before the result is returned. Anything inconsistent
    fails closed — a stored inconsistency never becomes
    a result.
    """
    if not isinstance(report_row, dict):
        raise ApplicationValidationError(
            "stored report is malformed")
    report_id = _require_uuid(report_row.get("id"), "report")
    tenant_id = _require_uuid(
        report_row.get("tenant_id"), "tenant")
    case_id = _require_uuid(report_row.get("case_id"), "case")
    analyses = tuple(
        rebuild_analysis(row) for row in analysis_rows)
    for analysis in analyses:
        if analysis.tenant_id != tenant_id:
            raise ApplicationValidationError(
                "stored analysis belongs to a different tenant")
    traces = tuple(rebuild_trace(row) for row in trace_rows)
    known_analyses = {a.id for a in analyses}
    for trace in traces:
        if trace.tenant_id != tenant_id:
            raise ApplicationValidationError(
                "stored trace belongs to a different tenant")
        # NOTE: trace.case_id is intentionally not compared
        # to the report case: Phase 6.5 scopes traces to
        # requirement-level case views by design. Case
        # linkage is enforced through the analysis the
        # trace references.
        if trace.report_id != report_id:
            raise ApplicationValidationError(
                "stored trace references a different report")
        if trace.analysis_id not in known_analyses:
            raise ApplicationValidationError(
                "stored trace references an unknown analysis")
    report = rebuild_report(report_row, analyses)
    if ({a.id for a in report.analyses} != known_analyses
            or report.id != report_id
            or report.tenant_id != tenant_id
            or report.case_id != case_id):
        raise ApplicationValidationError(
            "stored report linkage is inconsistent")
    return ComplianceReasoningResult(
        case_id=case_id,
        tenant_id=tenant_id,
        analyses=analyses,
        report=report,
        traces=traces,
        decision_summary=report.decision_summary,
    )
