"""Shared input guards for application use cases (private).

Tenant safety here is deterministic comparison, never
message parsing: record/object tenant identities are
compared against the context tenant before any domain
call. Rehydration rebuilds the immutable workflow from
its record form with strict shape validation.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from xportra.domain.compliance_workflow import (
    ComplianceWorkflow,
    WorkflowAnalysisRound,
)

from .context import ApplicationContext
from .errors import (
    ApplicationValidationError,
    TenantMismatchError,
)


def checked_context(ctx: Any) -> ApplicationContext:
    if not isinstance(ctx, ApplicationContext):
        raise ApplicationValidationError(
            "an application context is required")
    return ctx


def checked_uuid(value: Any, field: str) -> UUID:
    if not isinstance(value, UUID):
        raise ApplicationValidationError(
            f"a {field} identity UUID is required")
    return value


def checked_uuid_list(values: Any, field: str) -> list[UUID]:
    if (not isinstance(values, (list, tuple))
            or not values
            or isinstance(values, (str, bytes))):
        raise ApplicationValidationError(
            f"at least one {field} identity is required")
    for value in values:
        checked_uuid(value, field)
    return list(values)


def parse_uuid(value: Any, field: str) -> UUID:
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (ValueError, TypeError, AttributeError) as cause:
        raise ApplicationValidationError(
            f"malformed workflow {field}") from cause


def ensure_tenant_match(ctx: ApplicationContext,
                        tenant_id: UUID, resource: str) -> None:
    """Fail closed when a record belongs to another tenant."""
    if tenant_id != ctx.tenant_id:
        raise TenantMismatchError(
            f"{resource} belongs to a different tenant")


_CASE_IDENTITY_FIELDS = frozenset({
    "id",
    "tenant_id",
    "requirement_id",
    "evidence_id",
    "applicability_result_id",
    "assessment_id",
    "normalized_document_id",
    "artifact_id",
})

_CASE_IDENTITY_LIST_FIELDS = frozenset({
    "evidence_ids",
})


def _coerce_identity(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return UUID(value)
        except ValueError:
            return value
    return value


def _coerce_section(section: Any) -> Any:
    if isinstance(section, dict):
        coerced = {}
        for key, value in section.items():
            if key in _CASE_IDENTITY_FIELDS:
                coerced[key] = _coerce_identity(value)
            elif (key in _CASE_IDENTITY_LIST_FIELDS
                    and isinstance(value, list)):
                coerced[key] = [
                    _coerce_identity(item) for item in value]
            elif isinstance(value, (dict, list)):
                coerced[key] = _coerce_section(value)
            else:
                coerced[key] = value
        return coerced
    if isinstance(section, list):
        return [
            _coerce_section(item) if isinstance(item, dict)
            else item
            for item in section
        ]
    return section


def coerce_case_identities(case: Any) -> Any:
    """Restore UUID identities in a JSON-transported case view.

    HTTP bodies carry UUIDs as strings while the domain
    requires UUID objects. This mechanical wire translation
    coerces the documented identity fields wherever they
    appear in the case view (top level, requirement,
    applicability, assessment, evidence, provenance).
    Unparseable or unknown shapes pass through untouched
    for domain validation to reject with its own errors.
    No fact is invented or defaulted.
    """
    if not isinstance(case, dict):
        return case
    return _coerce_section(case)


def workflow_from_record(record: Any) -> ComplianceWorkflow:
    """Rehydrate the immutable workflow from its record form."""
    if not isinstance(record, dict):
        raise ApplicationValidationError(
            "a workflow record mapping is required")
    try:
        rounds = record["rounds"]
        supplied = record["supplied_evidence_ids"]
        open_requirements = record["open_requirements"]
        state = record["state"]
    except KeyError as cause:
        raise ApplicationValidationError(
            f"workflow record is missing {cause}") from cause
    if not isinstance(state, str):
        raise ApplicationValidationError(
            "malformed workflow state")
    if not isinstance(rounds, list):
        raise ApplicationValidationError("malformed rounds")
    parsed_rounds = []
    for item in rounds:
        if not isinstance(item, dict):
            raise ApplicationValidationError("malformed round")
        try:
            parsed_rounds.append(WorkflowAnalysisRound(
                round_index=item["round_index"],
                report_id=parse_uuid(
                    item["report_id"], "report"),
                analysis_ids=tuple(
                    parse_uuid(v, "analysis")
                    for v in item["analysis_ids"]),
                trace_ids=tuple(
                    parse_uuid(v, "trace")
                    for v in item["trace_ids"]),
                input_fingerprints=tuple(item["input_fingerprints"]),
            ))
        except KeyError as cause:
            raise ApplicationValidationError(
                f"round is missing {cause}") from cause
        except TypeError as cause:
            raise ApplicationValidationError(
                "malformed round identities") from cause
    if not isinstance(supplied, list) or not isinstance(
            open_requirements, list):
        raise ApplicationValidationError(
            "malformed workflow references")
    return ComplianceWorkflow(
        id=parse_uuid(record.get("id"), "workflow"),
        tenant_id=parse_uuid(record.get("tenant_id"), "tenant"),
        case_id=parse_uuid(record.get("case_id"), "case"),
        shipment_id=(
            None if record.get("shipment_id") is None
            else parse_uuid(
                record.get("shipment_id"), "shipment")),
        state=state,
        rounds=tuple(parsed_rounds),
        supplied_evidence_ids=tuple(
            parse_uuid(v, "evidence") for v in supplied),
        open_requirements=tuple(
            parse_uuid(v, "requirement")
            for v in open_requirements),
    )


__all__ = [
    "checked_context",
    "checked_uuid",
    "checked_uuid_list",
    "coerce_case_identities",
    "ensure_tenant_match",
    "parse_uuid",
    "workflow_from_record",
]
