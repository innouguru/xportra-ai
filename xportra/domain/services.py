"""Application-facing domain services above PostgreSQL persistence."""

from collections.abc import Sequence
from datetime import date, datetime
from typing import Any
from uuid import UUID

from psycopg.errors import IntegrityError

from xportra.persistence.database import Database
from xportra.persistence.errors import PersistenceIntegrityError
from xportra.persistence.repositories import (
    AuthorityRepository,
    CertificationPermitLicenseRepository,
    ComplianceEvidenceRepository,
    DestinationMarketRepository,
    EvidenceRequirementRepository,
    ExporterRepository,
    ProductRepository,
    RequirementApplicabilityRepository,
    RequirementRepository,
)
from xportra.persistence.tenant import TenantContext

from .errors import (
    DomainNotFoundError,
    DomainPersistenceError,
    DomainValidationError,
    require_tenant_context,
)


class ExporterService:
    def __init__(self, repository: ExporterRepository) -> None:
        self._repository = repository

    def create(
        self,
        tenant: TenantContext,
        legal_name: str,
        trading_name: str | None = None,
        registration_number: str | None = None,
        country_of_registration: str | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        require_tenant_context(tenant)
        return _persist(
            "exporter creation",
            lambda: self._repository.create(
                tenant,
                legal_name,
                trading_name,
                registration_number,
                country_of_registration,
                status,
            ),
        )

    def get(self, tenant: TenantContext, exporter_id: UUID) -> dict[str, Any] | None:
        require_tenant_context(tenant)
        return self._repository.get(tenant, exporter_id)


class ProductService:
    def __init__(
        self,
        exporter_repository: ExporterRepository,
        product_repository: ProductRepository,
    ) -> None:
        self._exporters = exporter_repository
        self._products = product_repository

    def create(
        self,
        tenant: TenantContext,
        exporter_id: UUID,
        product_name: str,
        commodity_code: str | None = None,
        description: str | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        require_tenant_context(tenant)
        self._require_exporter(tenant, exporter_id)
        return _persist(
            "product creation",
            lambda: self._products.create(
                tenant,
                exporter_id,
                product_name,
                commodity_code,
                description,
                status,
            ),
        )

    def get(self, tenant: TenantContext, product_id: UUID) -> dict[str, Any] | None:
        require_tenant_context(tenant)
        return self._products.get(tenant, product_id)

    def _require_exporter(self, tenant: TenantContext, exporter_id: UUID) -> None:
        if self._exporters.get(tenant, exporter_id) is None:
            raise DomainNotFoundError(f"exporter {exporter_id} was not found for tenant")


class DestinationMarketService:
    def __init__(self, repository: DestinationMarketRepository) -> None:
        self._repository = repository

    def register(
        self,
        tenant: TenantContext,
        country_code: str,
        market_name: str,
        regulatory_context: str | None = None,
        status: str = "active",
    ) -> dict[str, Any]:
        require_tenant_context(tenant)
        return _persist(
            "destination market registration",
            lambda: self._repository.create(
                tenant,
                country_code,
                market_name,
                regulatory_context,
                status,
            ),
        )

    def get(self, tenant: TenantContext, destination_id: UUID) -> dict[str, Any] | None:
        require_tenant_context(tenant)
        return self._repository.get(tenant, destination_id)


class RequirementApplicabilityService:
    def __init__(
        self,
        exporter_repository: ExporterRepository,
        product_repository: ProductRepository,
        destination_repository: DestinationMarketRepository,
        requirement_repository: RequirementRepository,
        repository: RequirementApplicabilityRepository,
    ) -> None:
        self._exporters = exporter_repository
        self._products = product_repository
        self._destinations = destination_repository
        self._requirements = requirement_repository
        self._repository = repository

    def record(
        self,
        tenant: TenantContext,
        requirement_id: UUID,
        exporter_id: UUID,
        product_id: UUID,
        destination_id: UUID,
        applicability_status: str,
        effective_from: datetime,
        reason_summary: str | None = None,
        effective_to: datetime | None = None,
        version: str | None = None,
    ) -> dict[str, Any]:
        require_tenant_context(tenant)
        exporter = self._require_record(
            self._exporters.get(tenant, exporter_id), "exporter", exporter_id
        )
        product = self._require_record(
            self._products.get(tenant, product_id), "product", product_id
        )
        self._require_record(
            self._destinations.get(tenant, destination_id),
            "destination market",
            destination_id,
        )
        self._require_record(
            self._requirements.get(tenant, requirement_id),
            "requirement",
            requirement_id,
        )
        if product["exporter_id"] != exporter["id"]:
            raise DomainValidationError("product does not belong to the exporter")
        if effective_to is not None and effective_to < effective_from:
            raise DomainValidationError("effective_to must not precede effective_from")
        return _persist(
            "requirement applicability recording",
            lambda: self._repository.create(
                tenant,
                requirement_id,
                exporter_id,
                product_id,
                destination_id,
                applicability_status,
                effective_from,
                reason_summary,
                effective_to,
                version,
            ),
        )

    @staticmethod
    def _require_record(record: dict[str, Any] | None, name: str, record_id: UUID) -> dict[str, Any]:
        if record is None:
            raise DomainNotFoundError(f"{name} {record_id} was not found for tenant")
        return record


class ComplianceEvidenceService:
    def __init__(
        self,
        database: Database,
        evidence_repository: ComplianceEvidenceRepository,
        evidence_requirement_repository: EvidenceRequirementRepository,
        requirement_repository: RequirementRepository,
    ) -> None:
        self._database = database
        self._evidence = evidence_repository
        self._evidence_requirements = evidence_requirement_repository
        self._requirements = requirement_repository

    def record(
        self,
        tenant: TenantContext,
        document_title: str,
        document_type: str,
        file_reference_or_uri: str,
        source_id: UUID | None = None,
        content_hash: str | None = None,
        status: str = "uploaded",
    ) -> dict[str, Any]:
        require_tenant_context(tenant)
        return _persist(
            "compliance evidence recording",
            lambda: self._evidence.create(
                tenant,
                document_title,
                document_type,
                file_reference_or_uri,
                source_id,
                content_hash,
                status,
            ),
        )

    def get(self, tenant: TenantContext, evidence_id: UUID) -> dict[str, Any] | None:
        require_tenant_context(tenant)
        return self._evidence.get(tenant, evidence_id)

    def record_with_requirements(
        self,
        tenant: TenantContext,
        document_title: str,
        document_type: str,
        file_reference_or_uri: str,
        requirement_ids: Sequence[UUID],
        source_id: UUID | None = None,
        content_hash: str | None = None,
        status: str = "uploaded",
    ) -> dict[str, Any]:
        require_tenant_context(tenant)
        if not requirement_ids:
            raise DomainValidationError("at least one requirement is required")
        for requirement_id in requirement_ids:
            if self._requirements.get(tenant, requirement_id) is None:
                raise DomainNotFoundError(f"requirement {requirement_id} was not found")
        try:
            with self._database.transaction() as connection:
                evidence = self._evidence.create_in_transaction(
                    connection,
                    tenant,
                    document_title,
                    document_type,
                    file_reference_or_uri,
                    source_id,
                    content_hash,
                    status,
                )
                for requirement_id in requirement_ids:
                    self._evidence_requirements.link_in_transaction(
                        connection, tenant, evidence["id"], requirement_id
                    )
                return evidence
        except PersistenceIntegrityError as cause:
            raise DomainPersistenceError(
                "compliance evidence and requirement association", cause
            ) from cause
        except IntegrityError as cause:
            persistence_error = PersistenceIntegrityError(
                "compliance evidence and requirement association", cause
            )
            raise DomainPersistenceError(
                "compliance evidence and requirement association", persistence_error
            ) from persistence_error

    def associate_requirement(
        self, tenant: TenantContext, evidence_id: UUID, requirement_id: UUID
    ) -> dict[str, Any]:
        require_tenant_context(tenant)
        if self._evidence.get(tenant, evidence_id) is None:
            raise DomainNotFoundError(f"evidence {evidence_id} was not found for tenant")
        if self._requirements.get(tenant, requirement_id) is None:
            raise DomainNotFoundError(f"requirement {requirement_id} was not found")
        return _persist(
            "evidence requirement association",
            lambda: self._evidence_requirements.link(tenant, evidence_id, requirement_id),
        )


class CertificationService:
    def __init__(
        self,
        exporter_repository: ExporterRepository,
        authority_repository: AuthorityRepository,
        repository: CertificationPermitLicenseRepository,
    ) -> None:
        self._exporters = exporter_repository
        self._authorities = authority_repository
        self._repository = repository

    def record(
        self,
        tenant: TenantContext,
        exporter_id: UUID,
        issuing_authority_id: UUID,
        title: str,
        issue_date: date | None = None,
        expiry_date: date | None = None,
        status: str = "issued",
        document_reference: str | None = None,
    ) -> dict[str, Any]:
        require_tenant_context(tenant)
        if self._exporters.get(tenant, exporter_id) is None:
            raise DomainNotFoundError(f"exporter {exporter_id} was not found for tenant")
        if self._authorities.get(issuing_authority_id) is None:
            raise DomainNotFoundError(f"authority {issuing_authority_id} was not found")
        if issue_date is not None and expiry_date is not None and expiry_date < issue_date:
            raise DomainValidationError("expiry_date must not precede issue_date")
        return _persist(
            "certification recording",
            lambda: self._repository.create(
                tenant,
                exporter_id,
                issuing_authority_id,
                title,
                issue_date,
                expiry_date,
                status,
                document_reference,
            ),
        )

    def get(self, tenant: TenantContext, certificate_id: UUID) -> dict[str, Any] | None:
        require_tenant_context(tenant)
        return self._repository.get(tenant, certificate_id)


def _persist(operation: str, action):
    try:
        return action()
    except PersistenceIntegrityError as cause:
        raise DomainPersistenceError(operation, cause) from cause
