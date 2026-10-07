"""Applicability and evidence-readiness use cases.

``AssessmentApplicationService`` exposes the deterministic
Phase 2/3 read boundaries through the application
contract:

- applicability determination over caller-supplied
  requirement records and shipment facts (the context is
  built with the context tenant — never a client tenant);
- evidence-coverage readiness over caller-supplied
  compliance cases (each case tenant-checked against the
  context before delegation).

Both use cases are pure delegation plus DTO translation.
No applicability rule, risk rule, action rule, verdict,
or score exists here; unknown and missing states pass
through untouched exactly as the domain reports them.
Requirement records and case views come from the
caller's regulatory store (shared data, Phase 8 wiring);
this layer persists nothing and invents no facts.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from xportra.domain.errors import DomainValidationError
from xportra.domain.ingestion import (
    ApplicabilityContextBuilder,
    ComplianceApplicabilityService,
    ComplianceCaseReadinessService,
)

from ._guards import (
    checked_context,
    coerce_case_identities,
    ensure_tenant_match,
)
from .context import ApplicationContext
from .dtos import ApplicabilityDTO, CaseReadinessDTO
from .errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
    InvalidTransitionError,
)


class AssessmentApplicationService:
    """Stateless assessment read use cases."""

    def __init__(
        self,
        *,
        applicability_service: (
            ComplianceApplicabilityService | None) = None,
        context_builder: ApplicabilityContextBuilder | None = None,
        readiness_service: (
            ComplianceCaseReadinessService | None) = None,
        shipment_reader: Any | None = None,
    ) -> None:
        self._applicability = (
            applicability_service or ComplianceApplicabilityService())
        self._builder = context_builder or ApplicabilityContextBuilder()
        self._readiness = (
            readiness_service or ComplianceCaseReadinessService())
        for name, service, method in (
            ("applicability", self._applicability, "determine"),
            ("context builder", self._builder, "build"),
            ("readiness", self._readiness, "assess"),
        ):
            if not callable(getattr(service, method, None)):
                raise ApplicationValidationError(
                    f"an assessment {name} service is required")
        if (shipment_reader is not None
                and not callable(getattr(
                    shipment_reader, "get_shipment", None))):
            raise ApplicationValidationError(
                "a shipment reader is required")
        self._shipment_reader = shipment_reader

    def determine_applicability(
        self,
        ctx: ApplicationContext,
        requirements: list[dict[str, Any]],
        *,
        exporter: dict[str, Any] | None = None,
        product: dict[str, Any] | None = None,
        destination: dict[str, Any] | None = None,
        actor_role: str | None = None,
        business_characteristics: dict[str, Any] | None = None,
        shipment_id: UUID | None = None,
    ) -> ApplicabilityDTO:
        """Determine which requirements apply (deterministic).

        Shipment fact precedence: explicit validated
        input first, the authoritative server-owned
        shipment profile second, error when neither is
        available. Explicit facts always win over
        shipment defaults — they never override them.
        """
        ctx = checked_context(ctx)
        checked_requirements = _checked_requirements(requirements)
        for name, value in (
                ("exporter", exporter),
                ("product", product),
                ("destination", destination),
                ("business characteristics",
                 business_characteristics)):
            if value is not None and not isinstance(value, dict):
                raise ApplicationValidationError(
                    f"malformed {name} facts")
        if actor_role is not None and not isinstance(
                actor_role, str):
            raise ApplicationValidationError(
                "malformed actor role")
        if shipment_id is not None:
            if not isinstance(shipment_id, UUID):
                raise ApplicationValidationError(
                    "a shipment identity UUID is required")
            exporter, product, destination = (
                self._with_shipment_defaults(
                    ctx, shipment_id,
                    exporter, product, destination))
        try:
            context = self._builder.build(
                tenant_id=ctx.tenant_id,
                exporter=exporter,
                product=product,
                destination=destination,
                actor_role=actor_role,
                business_characteristics=business_characteristics,
            )
            report = self._applicability.determine(
                checked_requirements, context)
        except DomainValidationError as cause:
            raise ApplicationValidationError(
                str(cause), cause=cause) from cause
        return ApplicabilityDTO.from_report(report)

    def _with_shipment_defaults(
        self,
        ctx: ApplicationContext,
        shipment_id: UUID,
        exporter: dict[str, Any] | None,
        product: dict[str, Any] | None,
        destination: dict[str, Any] | None,
    ) -> tuple[
        dict[str, Any] | None,
        dict[str, Any] | None,
        dict[str, Any] | None,
    ]:
        """Fill omitted facts from the server-owned shipment.

        Explicit caller facts always win: only omitted
        (``None``) fact groups default from the stored
        profile, mapped onto the fact keys the
        applicability context builder reads
        (``country_of_registration``, ``description``,
        ``country_code``). An unknown shipment identity
        fails closed; without a configured shipment
        reader any shipment reference fails closed.
        """
        if self._shipment_reader is None:
            raise ApplicationValidationError(
                "shipment resolution is not configured")
        stored = self._shipment_reader.get_shipment(
            ctx, shipment_id)
        if stored is None:
            raise ApplicationNotFoundError(
                "no stored shipment for this shipment identity")
        if exporter is None:
            exporter = {"country_of_registration":
                        stored.origin_country}
        if product is None:
            product = {"description": stored.product}
        if destination is None:
            destination = {"country_code":
                           stored.destination_country}
        return exporter, product, destination

    def assess_case_readiness(
        self,
        ctx: ApplicationContext,
        cases: list[dict[str, Any]],
    ) -> CaseReadinessDTO:
        """Assess evidence coverage (information, not verdict)."""
        ctx = checked_context(ctx)
        if not isinstance(cases, list):
            raise ApplicationValidationError(
                "cases must be a list")
        coerced = []
        for case in cases:
            if not isinstance(case, dict):
                raise ApplicationValidationError(
                    "a compliance case is required")
            case = coerce_case_identities(case)
            tenant_id = case.get("tenant_id")
            if not isinstance(tenant_id, UUID):
                raise ApplicationValidationError(
                    "case tenant identity is malformed")
            ensure_tenant_match(ctx, tenant_id, "case")
            coerced.append(case)
        try:
            report = self._readiness.assess(
                coerced, tenant_id=ctx.tenant_id)
        except DomainValidationError as cause:
            raise ApplicationValidationError(
                str(cause), cause=cause) from cause
        return CaseReadinessDTO.from_report(report)


def _checked_requirements(requirements: Any) -> list[dict[str, Any]]:
    if (not isinstance(requirements, list)
            or not requirements):
        raise ApplicationValidationError(
            "at least one requirement record is required")
    for requirement in requirements:
        if (not isinstance(requirement, dict)
                or requirement.get("id") is None):
            raise ApplicationValidationError(
                "a requirement record with an identity is required")
    return requirements


__all__ = [
    "AssessmentApplicationService",
]
