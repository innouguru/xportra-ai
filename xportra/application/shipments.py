"""Tenant shipment discovery reads (durable listing/history).

``ShipmentListingService`` composes the existing
server-owned rows into the read model the shipment
history UI needs:

```text
Shipment → latest workflow → rounds → latest report/package
```

This is retention assembly, not a second compliance
system: no applicability, assessment, reasoning,
retrieval, verdict, transition, or score exists here.
Workflow terminality reuses the domain-owned
``WORKFLOW_TERMINAL_STATES``; completion additionally
requires the stored package linkage, and Shipment
``locked`` is never read as a completion signal (the
audit established finalization does not enact it).

Reads are tenant-scoped and fail closed: unknown and
cross-tenant identities read as absent. Multiplicity
(one shipment across cases) surfaces as
``workflow_count`` with the latest-activity workflow
summarized — never silently discarded.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from xportra.domain.compliance_workflow import (
    WORKFLOW_TERMINAL_STATES,
    ComplianceWorkflow,
)
from xportra.domain.shipment import Shipment

from ._guards import checked_context, checked_uuid
from .context import ApplicationContext
from .dtos import (
    ShipmentItemDTO,
    ShipmentListDTO,
    ShipmentWorkflowSummaryDTO,
)
from .errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
)
from .result_store import store_supports_shipment_listing

#: Page-size bounds for shipment discovery. No
#: pagination precedent exists in the repository, so
#: the smallest standard window applies: callers omit
#: both for the first page.
DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 100

_LIST_STATUSES = frozenset({"all", "active", "completed"})


class ShipmentListingService:
    """Read-only shipment discovery over stored rows."""

    def __init__(self, *, result_store: Any | None = None) -> None:
        self._result_store = result_store

    def list_shipments(
        self,
        ctx: ApplicationContext,
        *,
        limit: int | None = None,
        offset: int | None = None,
        status: str = "all",
    ) -> ShipmentListDTO:
        """Return one page of composed shipment items.

        Newest shipments first. ``status`` filters on
        workflow terminality (``completed`` requires a
        terminal workflow state with package linkage);
        drafts and in-progress shipments read as
        ``active``. Pagination slices the filtered set
        so pages stay coherent under filtering.
        """
        ctx = checked_context(ctx)
        resolved_limit = _checked_limit(limit)
        resolved_offset = _checked_offset(offset)
        if status not in _LIST_STATUSES:
            raise ApplicationValidationError(
                "shipment status filter must be one of "
                "all, active, completed")
        store = self._listing_store()
        if status == "all":
            entries = store.list_shipments(
                ctx, resolved_limit, resolved_offset)
            total = store.count_shipments(ctx)
            composed = [self._compose(store, ctx, shipment,
                                      stamps, None)
                        for shipment, stamps in entries]
        else:
            entries = store.list_shipments(ctx, None, 0)
            resolved = [
                (shipment, stamps,
                 store.list_workflows_for_shipment(
                     ctx, shipment.shipment_id))
                for shipment, stamps in entries]
            resolved = [
                entry for entry in resolved
                if self._is_closed_view(
                    store, ctx, entry[2], status)]
            total = len(resolved)
            resolved = resolved[
                resolved_offset:
                resolved_offset + resolved_limit]
            composed = [self._compose(store, ctx, shipment,
                                      stamps, workflows)
                        for shipment, stamps, workflows
                        in resolved]
        return ShipmentListDTO(
            shipments=tuple(composed),
            limit=resolved_limit,
            offset=resolved_offset,
            total=total,
        )

    def get_shipment(
        self,
        ctx: ApplicationContext,
        shipment_id: UUID,
    ) -> ShipmentItemDTO:
        """Return one composed shipment item.

        Unknown and cross-tenant identities fail closed
        as not-found, indistinguishable from each other.
        """
        ctx = checked_context(ctx)
        checked_uuid(shipment_id, "shipment")
        store = self._listing_store()
        entry = store.get_shipment_entry(ctx, shipment_id)
        if entry is None:
            raise ApplicationNotFoundError(
                "no stored shipment for this shipment identity")
        shipment, stamps = entry
        return self._compose(store, ctx, shipment, stamps)

    def _listing_store(self) -> Any:
        if not store_supports_shipment_listing(
                self._result_store):
            raise ApplicationValidationError(
                "shipment listing is not configured")
        return self._result_store

    def _is_closed_view(
        self,
        store: Any,
        ctx: ApplicationContext,
        workflows: list,
        status: str,
    ) -> bool:
        """Filter one shipment's workflows to a status view."""
        closed = (
            bool(workflows)
            and self._is_completed(store, ctx, workflows[0]))
        return closed if status == "completed" else not closed

    def _compose(
        self,
        store: Any,
        ctx: ApplicationContext,
        shipment: Shipment,
        stamps: dict[str, str],
        workflows: list | None = None,
    ) -> ShipmentItemDTO:
        if workflows is None:
            workflows = store.list_workflows_for_shipment(
                ctx, shipment.shipment_id)
        if not workflows:
            summary = None
            record = None
        else:
            latest = workflows[0]
            summary = self._summarize(store, ctx, latest)
            record = latest.to_record()
            record = {key: (
                [str(v) for v in value]
                if key in ("supplied_evidence_ids",
                           "open_requirements")
                else value)
                for key, value in record.items()}
            record["rounds"] = [
                {**round, "report_id": str(round["report_id"]),
                 "analysis_ids": [str(v) for v in
                                  round["analysis_ids"]],
                 "trace_ids": [str(v) for v in
                               round["trace_ids"]]}
                for round in record["rounds"]]
        return ShipmentItemDTO(
            shipment_id=str(shipment.shipment_id),
            case_id=str(shipment.case_id),
            product=shipment.product,
            origin_country=shipment.origin_country,
            destination_country=shipment.destination_country,
            quantity=shipment.quantity,
            unit=shipment.unit,
            shipment_date=shipment.shipment_date,
            status=shipment.status,
            created_at=stamps.get("created_at", ""),
            updated_at=stamps.get("updated_at", ""),
            workflow=summary,
            workflow_count=len(workflows),
            workflow_record=record,
        )

    def _summarize(
        self,
        store: Any,
        ctx: ApplicationContext,
        workflow: ComplianceWorkflow,
    ) -> ShipmentWorkflowSummaryDTO:
        rounds = workflow.rounds
        latest_report = (
            None if not rounds
            else str(rounds[-1].report_id))
        return ShipmentWorkflowSummaryDTO(
            workflow_id=str(workflow.id),
            state=workflow.state,
            is_closed=self._is_completed(store, ctx, workflow),
            supplied_evidence_count=len(
                workflow.supplied_evidence_ids),
            open_requirements_count=len(
                workflow.open_requirements),
            round_count=len(rounds),
            latest_report_id=latest_report,
        )

    def _is_completed(
        self,
        store: Any,
        ctx: ApplicationContext,
        workflow: ComplianceWorkflow,
    ) -> bool:
        """Derive completion from workflow/package terminality.

        Completed means the domain terminal state with
        the expected stored package linkage — never the
        shipment ``locked`` status, which finalization
        does not enact.
        """
        if workflow.state not in WORKFLOW_TERMINAL_STATES:
            return False
        return store.load_package(ctx, workflow.id) is not None


def _checked_limit(limit: Any) -> int:
    if limit is None:
        return DEFAULT_LIST_LIMIT
    if (not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < 1 or limit > MAX_LIST_LIMIT):
        raise ApplicationValidationError(
            "shipment list limit must be between 1 and "
            f"{MAX_LIST_LIMIT}")
    return limit


def _checked_offset(offset: Any) -> int:
    if offset is None:
        return 0
    if (not isinstance(offset, int)
            or isinstance(offset, bool) or offset < 0):
        raise ApplicationValidationError(
            "shipment list offset must be a non-negative integer")
    return offset


__all__ = [
    "DEFAULT_LIST_LIMIT",
    "MAX_LIST_LIMIT",
    "ShipmentListingService",
]
