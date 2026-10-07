"""Tenant-scoped commercial shipment aggregate (ADR-0013).

The first-class owner of commercial shipment/profile
facts — product, origin, destination, quantity, unit,
and shipment date — independently from the compliance
workflow/process state:

```text
Tenant
  └── Shipment (this module: facts + lifecycle)
        └── ComplianceWorkflow (process state, elsewhere)
```

The aggregate owns facts about the shipment; the
workflow owns the process of assessing it. No workflow
state, evidence reference, round, package, verdict, or
score lives here, and no shipment profile field is
duplicated into ``compliance_workflows``.

Lifecycle (shipment-only, distinct from the workflow
lifecycle):

```text
draft → bound → locked
```

- ``draft`` — created from intake facts, not yet bound
  to any workflow. Fully editable.
- ``bound`` — associated with a live compliance
  workflow. Profile edits require explicit domain
  handling; this module offers no bound-state edit —
  the application keeps shipments immutable after
  binding rather than inventing a reanalysis path.
- ``locked`` — terminal. Read-only; corrections are a
  new shipment, never a mutation.

Identity is the tenant-scoped pair
``(tenant_id, shipment_id)``; ``case_id`` is the
reasoning/case grouping reference, never the primary
identity. A shipment UUID from a request proves
nothing by itself — resolution under the caller
tenant happens in the persistence boundary.

This module performs no retrieval, no LLM invocation,
no database access, and no persistence.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from .errors import DomainValidationError, require_tenant_context

SHIPMENT_STATUS_DRAFT = "draft"
SHIPMENT_STATUS_BOUND = "bound"
SHIPMENT_STATUS_LOCKED = "locked"

SHIPMENT_STATUSES = frozenset({
    SHIPMENT_STATUS_DRAFT,
    SHIPMENT_STATUS_BOUND,
    SHIPMENT_STATUS_LOCKED,
})

#: Editable lifecycle states: only ``draft`` accepts
#: profile edits through this module. ``bound`` edits
#: require explicit domain handling that does not exist
#: yet (ADR-0013 §9); ``locked`` is terminal.
_EDITABLE_STATUSES = frozenset({SHIPMENT_STATUS_DRAFT})


class ShipmentError(DomainValidationError):
    """A shipment integrity failure (fail closed).

    Raised for malformed identities, blank required
    profile facts, illegal lifecycle transitions, and
    tenant/case mismatches — never converted into a
    bound workflow state.
    """


@dataclass(frozen=True, slots=True)
class Shipment:
    """Immutable tenant-owned commercial shipment instance.

    Commercial facts (product, origin, destination,
    quantity, unit, shipment date) plus the shipment-only
    lifecycle status. Optional facts normalize blank to
    ``None``; required facts must be non-blank.
    """

    tenant_id: UUID
    shipment_id: UUID
    case_id: UUID
    product: str
    origin_country: str
    destination_country: str
    quantity: str | None = None
    unit: str | None = None
    shipment_date: str | None = None
    status: str = SHIPMENT_STATUS_DRAFT

    def to_record(self) -> dict[str, Any]:
        return {
            "tenant_id": str(self.tenant_id),
            "shipment_id": str(self.shipment_id),
            "case_id": str(self.case_id),
            "product": self.product,
            "origin_country": self.origin_country,
            "destination_country": self.destination_country,
            "quantity": self.quantity,
            "unit": self.unit,
            "shipment_date": self.shipment_date,
            "status": self.status,
        }


class ShipmentService:
    """Pure domain owner of shipment facts and lifecycle."""

    def create(
        self,
        *,
        tenant_id: Any,
        shipment_id: UUID,
        case_id: UUID,
        product: Any,
        origin_country: Any,
        destination_country: Any,
        quantity: Any | None = None,
        unit: Any | None = None,
        shipment_date: Any | None = None,
    ) -> Shipment:
        """Create a draft shipment from validated intake facts."""
        require_tenant_context(tenant_id)
        tenant_uuid = tenant_id.tenant_id
        for name, value in (
            ("shipment_id", shipment_id),
            ("case_id", case_id),
        ):
            if not isinstance(value, UUID):
                raise ShipmentError(
                    f"shipment {name} must be a UUID")
        return Shipment(
            tenant_id=tenant_uuid,
            shipment_id=shipment_id,
            case_id=case_id,
            product=_required_text(product, "product"),
            origin_country=_required_text(
                origin_country, "origin_country"),
            destination_country=_required_text(
                destination_country, "destination_country"),
            quantity=_optional_text(quantity, "quantity"),
            unit=_optional_text(unit, "unit"),
            shipment_date=_optional_text(
                shipment_date, "shipment_date"),
            status=SHIPMENT_STATUS_DRAFT,
        )

    def update_profile(
        self,
        shipment: Shipment,
        *,
        tenant_id: Any,
        product: Any = None,
        origin_country: Any = None,
        destination_country: Any = None,
        quantity: Any = None,
        unit: Any = None,
        shipment_date: Any = None,
    ) -> Shipment:
        """Replace draft profile facts (draft only, explicit).

        Bound and locked shipments reject edits here: a
        bound edit must invalidate dependent compliance
        outputs through workflow transitions that do not
        exist yet, so silence would corrupt history.
        """
        shipment = self._checked(shipment, tenant_id)
        if shipment.status not in _EDITABLE_STATUSES:
            raise ShipmentError(
                f"shipment in status {shipment.status!r} "
                "is read-only; corrections require a new "
                "shipment")
        patch: dict[str, Any] = {}
        if product is not None:
            patch["product"] = _required_text(
                product, "product")
        if origin_country is not None:
            patch["origin_country"] = _required_text(
                origin_country, "origin_country")
        if destination_country is not None:
            patch["destination_country"] = _required_text(
                destination_country, "destination_country")
        if quantity is not None:
            patch["quantity"] = _optional_text(
                quantity, "quantity")
        if unit is not None:
            patch["unit"] = _optional_text(unit, "unit")
        if shipment_date is not None:
            patch["shipment_date"] = _optional_text(
                shipment_date, "shipment_date")
        return replace(shipment, **patch)

    def mark_bound(
        self, shipment: Shipment, *, tenant_id: Any
    ) -> Shipment:
        """Move a draft shipment to bound (workflow attached)."""
        shipment = self._checked(shipment, tenant_id)
        if shipment.status != SHIPMENT_STATUS_DRAFT:
            raise ShipmentError(
                f"shipment cannot move from "
                f"{shipment.status!r} to 'bound'")
        return replace(shipment, status=SHIPMENT_STATUS_BOUND)

    def mark_locked(
        self, shipment: Shipment, *, tenant_id: Any
    ) -> Shipment:
        """Move a bound shipment to locked (terminal)."""
        shipment = self._checked(shipment, tenant_id)
        if shipment.status != SHIPMENT_STATUS_BOUND:
            raise ShipmentError(
                f"shipment cannot move from "
                f"{shipment.status!r} to 'locked'")
        return replace(shipment, status=SHIPMENT_STATUS_LOCKED)

    @staticmethod
    def _checked(
        shipment: Shipment, tenant_id: Any
    ) -> Shipment:
        require_tenant_context(tenant_id)
        if not isinstance(shipment, Shipment):
            raise ShipmentError("a shipment is required")
        if shipment.tenant_id != tenant_id.tenant_id:
            raise ShipmentError(
                "shipment belongs to a different tenant")
        if shipment.status not in SHIPMENT_STATUSES:
            raise ShipmentError("shipment status is malformed")
        return shipment


def shipment_from_record(record: Any) -> Shipment:
    """Rehydrate a shipment from its stored/record form."""
    if not isinstance(record, dict):
        raise ShipmentError(
            "a shipment record mapping is required")
    try:
        status = record["status"]
        product = record["product"]
        origin_country = record["origin_country"]
        destination_country = record["destination_country"]
    except KeyError as cause:
        raise ShipmentError(
            f"shipment record is missing {cause}") from cause
    if status not in SHIPMENT_STATUSES:
        raise ShipmentError("shipment status is malformed")
    shipment = Shipment(
        tenant_id=_parse_uuid(record.get("tenant_id"), "tenant"),
        shipment_id=_parse_uuid(
            record.get("shipment_id"), "shipment"),
        case_id=_parse_uuid(record.get("case_id"), "case"),
        product=_required_text(product, "product"),
        origin_country=_required_text(
            origin_country, "origin_country"),
        destination_country=_required_text(
            destination_country, "destination_country"),
        quantity=_optional_stored(
            record.get("quantity"), "quantity"),
        unit=_optional_stored(record.get("unit"), "unit"),
        shipment_date=_optional_stored(
            record.get("shipment_date"), "shipment_date"),
        status=status,
    )
    return shipment


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ShipmentError(
            f"shipment {field} must be a non-blank string")
    return value.strip()


def _optional_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ShipmentError(
            f"shipment {field} must be a string")
    stripped = value.strip()
    return stripped or None


def _optional_stored(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return _optional_text(value, field)


def _parse_uuid(value: Any, field: str) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (ValueError, TypeError,
            AttributeError) as cause:
        raise ShipmentError(
            f"malformed shipment {field}") from cause


__all__ = [
    "SHIPMENT_STATUSES",
    "SHIPMENT_STATUS_BOUND",
    "SHIPMENT_STATUS_DRAFT",
    "SHIPMENT_STATUS_LOCKED",
    "Shipment",
    "ShipmentError",
    "ShipmentService",
    "shipment_from_record",
]
