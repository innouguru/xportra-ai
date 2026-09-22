"""Small SQL repositories aligned with the Phase 1 database schema."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from psycopg.errors import IntegrityError
from psycopg.types.json import Jsonb

from .database import Database
from .errors import PersistenceIntegrityError
from .tenant import TenantContext

Row = dict[str, Any]


def _fetch_one(database: Database, statement: str, parameters: Sequence[Any]) -> Row | None:
    with database.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            return cursor.fetchone()


def _fetch_all(database: Database, statement: str, parameters: Sequence[Any] = ()) -> list[Row]:
    with database.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            return list(cursor.fetchall())


def _insert(
    database: Database,
    operation: str,
    statement: str,
    parameters: Sequence[Any],
) -> Row:
    try:
        with database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters)
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError(f"{operation} did not return a row")
                return row
    except IntegrityError as cause:
        raise PersistenceIntegrityError(operation, cause) from cause


def _insert_in_transaction(
    connection,
    operation: str,
    statement: str,
    parameters: Sequence[Any],
) -> Row:
    try:
        with connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError(f"{operation} did not return a row")
            return row
    except IntegrityError as cause:
        raise PersistenceIntegrityError(operation, cause) from cause


class TenantRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, legal_name: str, slug: str, status: str = "active") -> Row:
        return _insert(
            self._database,
            "tenant creation",
            """
            INSERT INTO xportra.tenants (legal_name, slug, status)
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (legal_name, slug, status),
        )

    def get(self, tenant_id: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.tenants WHERE id = %s",
            (tenant_id,),
        )


class UserRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(
        self,
        display_name: str,
        email: str | None,
        status: str = "invited",
        supabase_uid: UUID | None = None,
    ) -> Row:
        return _insert(
            self._database,
            "user creation",
            """
            INSERT INTO xportra.users (display_name, email, status, supabase_uid)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (display_name, email, status, supabase_uid),
        )

    def get(self, user_id: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.users WHERE id = %s",
            (user_id,),
        )

    def get_by_supabase_uid(self, supabase_uid: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.users WHERE supabase_uid = %s",
            (supabase_uid,),
        )


class UserTenantMembershipRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def add(self, tenant: TenantContext, user_id: UUID, role: str, status: str = "active") -> Row:
        return _insert(
            self._database,
            "membership creation",
            """
            INSERT INTO xportra.user_tenant_memberships (tenant_id, user_id, role, status)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (tenant.tenant_id, user_id, role, status),
        )

    def list_for_tenant(self, tenant: TenantContext) -> list[Row]:
        return _fetch_all(
            self._database,
            """
            SELECT * FROM xportra.user_tenant_memberships
            WHERE tenant_id = %s
            ORDER BY added_at, id
            """,
            (tenant.tenant_id,),
        )

    def list_active_for_user(self, user_id: UUID) -> list[Row]:
        return _fetch_all(
            self._database,
            """
            SELECT m.id, m.tenant_id, m.role, m.status
            FROM xportra.user_tenant_memberships AS m
            JOIN xportra.tenants AS t ON t.id = m.tenant_id
            WHERE m.user_id = %s AND m.status = 'active' AND t.status = 'active'
            ORDER BY m.added_at, m.id
            """,
            (user_id,),
        )


class AuthorityRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def get(self, authority_id: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.authorities WHERE id = %s",
            (authority_id,),
        )

    def list_active(self) -> list[Row]:
        return _fetch_all(
            self._database,
            "SELECT * FROM xportra.authorities WHERE status = 'active' ORDER BY name, id",
        )


class RegulatorySourceRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def get(self, source_id: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.regulatory_sources WHERE id = %s",
            (source_id,),
        )

    def list_for_authority(self, authority_id: UUID) -> list[Row]:
        return _fetch_all(
            self._database,
            """
            SELECT * FROM xportra.regulatory_sources
            WHERE authority_id = %s
            ORDER BY effective_date NULLS LAST, id
            """,
            (authority_id,),
        )


class ExporterRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(
        self,
        tenant: TenantContext,
        legal_name: str,
        trading_name: str | None = None,
        registration_number: str | None = None,
        country_of_registration: str | None = None,
        status: str = "active",
    ) -> Row:
        return _insert(
            self._database,
            "exporter creation",
            """
            INSERT INTO xportra.exporters
                (tenant_id, legal_name, trading_name, registration_number,
                 country_of_registration, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (tenant.tenant_id, legal_name, trading_name, registration_number,
             country_of_registration, status),
        )

    def get(self, tenant: TenantContext, exporter_id: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.exporters WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, exporter_id),
        )


class ProductRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(
        self,
        tenant: TenantContext,
        exporter_id: UUID,
        product_name: str,
        commodity_code: str | None = None,
        description: str | None = None,
        status: str = "active",
    ) -> Row:
        return _insert(
            self._database,
            "product creation",
            """
            INSERT INTO xportra.products
                (tenant_id, exporter_id, product_name, commodity_code, description, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (tenant.tenant_id, exporter_id, product_name, commodity_code, description, status),
        )

    def get(self, tenant: TenantContext, product_id: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.products WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, product_id),
        )


class DestinationMarketRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(
        self,
        tenant: TenantContext,
        country_code: str,
        market_name: str,
        regulatory_context: str | None = None,
        status: str = "active",
    ) -> Row:
        return _insert(
            self._database,
            "destination market creation",
            """
            INSERT INTO xportra.destination_markets
                (tenant_id, country_code, market_name, regulatory_context, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (tenant.tenant_id, country_code, market_name, regulatory_context, status),
        )

    def get(self, tenant: TenantContext, destination_id: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.destination_markets WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, destination_id),
        )


class RequirementRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(
        self,
        tenant: TenantContext | None,
        requirement_code: str,
        title: str,
        description: str,
        applicability_logic_ref: str | None = None,
        status: str = "draft",
        effective_date: Any = None,
        version: str | None = None,
    ) -> Row:
        tenant_id = None if tenant is None else tenant.tenant_id
        return _insert(
            self._database,
            "requirement creation",
            """
            INSERT INTO xportra.requirements
                (tenant_id, requirement_code, title, description,
                 applicability_logic_ref, status, effective_date, version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (tenant_id, requirement_code, title, description,
             applicability_logic_ref, status, effective_date, version),
        )

    def get(self, tenant: TenantContext | None, requirement_id: UUID) -> Row | None:
        if tenant is None:
            statement = "SELECT * FROM xportra.requirements WHERE tenant_id IS NULL AND id = %s"
            parameters: Sequence[Any] = (requirement_id,)
        else:
            statement = """
                SELECT * FROM xportra.requirements
                WHERE id = %s AND (tenant_id = %s OR tenant_id IS NULL)
            """
            parameters = (requirement_id, tenant.tenant_id)
        return _fetch_one(self._database, statement, parameters)


class RequirementSourceRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def link(self, tenant: TenantContext | None, requirement_id: UUID, source_id: UUID) -> Row:
        tenant_id = None if tenant is None else tenant.tenant_id
        return _insert(
            self._database,
            "requirement-source link creation",
            """
            INSERT INTO xportra.requirement_sources (tenant_id, requirement_id, source_id)
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (tenant_id, requirement_id, source_id),
        )

    def list_for_requirement(self, tenant: TenantContext | None, requirement_id: UUID) -> list[Row]:
        if tenant is None:
            statement = """
                SELECT * FROM xportra.requirement_sources
                WHERE requirement_id = %s AND tenant_id IS NULL
                ORDER BY created_at, id
            """
            parameters: Sequence[Any] = (requirement_id,)
        else:
            statement = """
                SELECT * FROM xportra.requirement_sources
                WHERE requirement_id = %s AND (tenant_id = %s OR tenant_id IS NULL)
                ORDER BY created_at, id
            """
            parameters = (requirement_id, tenant.tenant_id)
        return _fetch_all(self._database, statement, parameters)


class RegulatorySourceArtifactRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(
        self,
        source_id: UUID,
        artifact_uri: str,
        content_hash: str,
        content_length: int,
        content_type: str,
        acquisition_channel: str,
        acquired_by: str | None = None,
        acquired_at: Any | None = None,
        status: str = "validated",
        source_version: str | None = None,
        validation_notes: str | None = None,
    ) -> Row:
        return _insert(
            self._database,
            "regulatory source artifact creation",
            """
            INSERT INTO xportra.regulatory_source_artifacts
                (source_id, artifact_uri, content_hash, content_length, content_type,
                 acquisition_channel, acquired_by, acquired_at, status, source_version,
                 validation_notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                source_id,
                artifact_uri,
                content_hash,
                content_length,
                content_type,
                acquisition_channel,
                acquired_by,
                acquired_at or None,
                status,
                source_version,
                validation_notes,
            ),
        )

    def get(self, artifact_id: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.regulatory_source_artifacts WHERE id = %s",
            (artifact_id,),
        )

    def list_for_source(self, source_id: UUID) -> list[Row]:
        return _fetch_all(
            self._database,
            """
            SELECT * FROM xportra.regulatory_source_artifacts
            WHERE source_id = %s
            ORDER BY acquired_at, id
            """,
            (source_id,),
        )

class RegulatoryDocumentNormalizationRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(
        self,
        *,
        artifact_id: UUID,
        source_id: UUID,
        document_title: str,
        normalized_text: str,
        normalized_content: Any,
        content_type: str,
        parser_name: str,
        status: str = "normalized",
        normalized_at: Any | None = None,
    ) -> Row:
        return _insert(
            self._database,
            "regulatory document normalization creation",
            """
            INSERT INTO xportra.regulatory_document_normalizations
                (artifact_id, source_id, document_title, normalized_text,
                 normalized_content, content_type, parser_name, status, normalized_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                artifact_id,
                source_id,
                document_title,
                normalized_text,
                normalized_content,
                content_type,
                parser_name,
                status,
                normalized_at or None,
            ),
        )

    def get_by_artifact(self, artifact_id: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.regulatory_document_normalizations WHERE artifact_id = %s",
            (artifact_id,),
        )

    def get(self, normalization_id: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.regulatory_document_normalizations WHERE id = %s",
            (normalization_id,),
        )

    def list_for_source(self, source_id: UUID) -> list[Row]:
        return _fetch_all(
            self._database,
            """
            SELECT * FROM xportra.regulatory_document_normalizations
            WHERE source_id = %s
            ORDER BY normalized_at, id
            """,
            (source_id,),
        )


class RegulatoryDocumentMetadataRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, **values: Any) -> Row:
        return _insert(
            self._database,
            "regulatory document metadata creation",
            """
            INSERT INTO xportra.regulatory_document_metadata
                (normalized_document_id, document_title, authority_name,
                 document_type, classification, publication_date, effective_date,
                 reference_identifier, version, jurisdiction, language, sections,
                 status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                values["normalized_document_id"],
                values.get("document_title"),
                values.get("authority_name"),
                values.get("document_type"),
                values["classification"],
                values.get("publication_date"),
                values.get("effective_date"),
                values.get("reference_identifier"),
                values.get("version"),
                values.get("jurisdiction"),
                values.get("language"),
                Jsonb(values["sections"]),
                values["status"],
            ),
        )

    def get_by_document(self, normalized_document_id: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            """
            SELECT metadata.*, document.artifact_id, document.source_id
            FROM xportra.regulatory_document_metadata AS metadata
            JOIN xportra.regulatory_document_normalizations AS document
              ON document.id = metadata.normalized_document_id
            WHERE metadata.normalized_document_id = %s
            """,
            (normalized_document_id,),
        )

    def get(self, metadata_id: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.regulatory_document_metadata WHERE id = %s",
            (metadata_id,),
        )

    def list_for_source(self, source_id: UUID) -> list[Row]:
        return _fetch_all(
            self._database,
            """
            SELECT metadata.*, document.artifact_id, document.source_id
            FROM xportra.regulatory_document_metadata AS metadata
            JOIN xportra.regulatory_document_normalizations AS document
              ON document.id = metadata.normalized_document_id
            WHERE document.source_id = %s
            ORDER BY metadata.created_at, metadata.id
            """,
            (source_id,),
        )


class RegulatoryRequirementRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, **values: Any) -> Row:
        condition_metadata = values.get("condition_metadata")
        return _insert(
            self._database,
            "regulatory requirement creation",
            """
            INSERT INTO xportra.regulatory_requirements
                (id, normalized_document_id, requirement_text, requirement_type,
                 source_location, position, actor, condition_metadata, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                values["id"],
                values["normalized_document_id"],
                values["requirement_text"],
                values["requirement_type"],
                Jsonb(values["source_location"]),
                values["position"],
                values.get("actor"),
                Jsonb(condition_metadata) if condition_metadata is not None else None,
                values["status"],
            ),
        )

    def list_for_document(self, normalized_document_id: UUID) -> list[Row]:
        return _fetch_all(
            self._database,
            """
            SELECT requirement.*, document.artifact_id, document.source_id
            FROM xportra.regulatory_requirements AS requirement
            JOIN xportra.regulatory_document_normalizations AS document
              ON document.id = requirement.normalized_document_id
            WHERE requirement.normalized_document_id = %s
            ORDER BY requirement.position, requirement.id
            """,
            (normalized_document_id,),
        )

    def get(self, requirement_id: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            """
            SELECT requirement.*, document.artifact_id, document.source_id
            FROM xportra.regulatory_requirements AS requirement
            JOIN xportra.regulatory_document_normalizations AS document
              ON document.id = requirement.normalized_document_id
            WHERE requirement.id = %s
            """,
            (requirement_id,),
        )


class RegulatoryRequirementApplicabilityRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, **values: Any) -> Row:
        return _insert(
            self._database,
            "regulatory requirement applicability creation",
            """
            INSERT INTO xportra.regulatory_requirement_applicability
                (id, tenant_id, requirement_id, context_fingerprint, outcome,
                 reason, context, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                values["id"],
                values["tenant_id"],
                values["requirement_id"],
                values["context_fingerprint"],
                values["outcome"],
                values["reason"],
                Jsonb(values["context"]),
                values["status"],
            ),
        )

    def get_by_identity(
        self,
        tenant_id: UUID,
        requirement_id: UUID,
        context_fingerprint: str,
    ) -> Row | None:
        return _fetch_one(
            self._database,
            """
            SELECT * FROM xportra.regulatory_requirement_applicability
            WHERE tenant_id = %s AND requirement_id = %s AND context_fingerprint = %s
            """,
            (tenant_id, requirement_id, context_fingerprint),
        )

    def list_for_tenant(self, tenant_id: UUID) -> list[Row]:
        return _fetch_all(
            self._database,
            """
            SELECT * FROM xportra.regulatory_requirement_applicability
            WHERE tenant_id = %s
            ORDER BY created_at, id
            """,
            (tenant_id,),
        )


class RequirementAssessmentRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, **values: Any) -> Row:
        return _insert(
            self._database,
            "requirement assessment creation",
            """
            INSERT INTO xportra.regulatory_requirement_assessments
                (id, tenant_id, requirement_id, applicability_result_id,
                 evidence_fingerprint, evidence_id, evidence_ids, outcome,
                 reason, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                values["id"],
                values["tenant_id"],
                values["requirement_id"],
                values["applicability_result_id"],
                values["evidence_fingerprint"],
                values.get("evidence_id"),
                Jsonb(values["evidence_ids"]),
                values["outcome"],
                values["reason"],
                values["status"],
            ),
        )

    def get_by_identity(
        self,
        tenant_id: UUID,
        requirement_id: UUID,
        applicability_result_id: UUID,
        evidence_fingerprint: str,
    ) -> Row | None:
        return _fetch_one(
            self._database,
            """
            SELECT * FROM xportra.regulatory_requirement_assessments
            WHERE tenant_id = %s AND requirement_id = %s
              AND applicability_result_id = %s AND evidence_fingerprint = %s
            """,
            (tenant_id, requirement_id, applicability_result_id, evidence_fingerprint),
        )

    def list_for_tenant(self, tenant_id: UUID) -> list[Row]:
        return _fetch_all(
            self._database,
            """
            SELECT * FROM xportra.regulatory_requirement_assessments
            WHERE tenant_id = %s
            ORDER BY created_at, id
            """,
            (tenant_id,),
        )


class RequirementApplicabilityRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(
        self,
        tenant: TenantContext,
        requirement_id: UUID,
        exporter_id: UUID,
        product_id: UUID,
        destination_id: UUID,
        applicability_status: str,
        effective_from: Any,
        reason_summary: str | None = None,
        effective_to: Any = None,
        version: str | None = None,
    ) -> Row:
        return _insert(
            self._database,
            "requirement applicability creation",
            """
            INSERT INTO xportra.requirement_applicability
                (tenant_id, requirement_id, exporter_id, product_id, destination_id,
                 applicability_status, reason_summary, effective_from, effective_to, version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (tenant.tenant_id, requirement_id, exporter_id, product_id, destination_id,
             applicability_status, reason_summary, effective_from, effective_to, version),
        )

    def get(self, tenant: TenantContext, applicability_id: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            """
            SELECT * FROM xportra.requirement_applicability
            WHERE tenant_id = %s AND id = %s
            """,
            (tenant.tenant_id, applicability_id),
        )


class ComplianceEvidenceRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(
        self,
        tenant: TenantContext,
        document_title: str,
        document_type: str,
        file_reference_or_uri: str,
        source_id: UUID | None = None,
        content_hash: str | None = None,
        status: str = "uploaded",
    ) -> Row:
        return _insert(
            self._database,
            "compliance evidence creation",
            """
            INSERT INTO xportra.compliance_evidence
                (tenant_id, source_id, document_title, document_type,
                 file_reference_or_uri, content_hash, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (tenant.tenant_id, source_id, document_title, document_type,
             file_reference_or_uri, content_hash, status),
        )

    def get(self, tenant: TenantContext, evidence_id: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.compliance_evidence WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, evidence_id),
        )

    def create_in_transaction(
        self,
        connection,
        tenant: TenantContext,
        document_title: str,
        document_type: str,
        file_reference_or_uri: str,
        source_id: UUID | None = None,
        content_hash: str | None = None,
        status: str = "uploaded",
    ) -> Row:
        return _insert_in_transaction(
            connection,
            "compliance evidence creation",
            """
            INSERT INTO xportra.compliance_evidence
                (tenant_id, source_id, document_title, document_type,
                 file_reference_or_uri, content_hash, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (tenant.tenant_id, source_id, document_title, document_type,
             file_reference_or_uri, content_hash, status),
        )


class EvidenceRequirementRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def link(self, tenant: TenantContext, evidence_id: UUID, requirement_id: UUID) -> Row:
        return _insert(
            self._database,
            "evidence-requirement link creation",
            """
            INSERT INTO xportra.evidence_requirements (tenant_id, evidence_id, requirement_id)
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (tenant.tenant_id, evidence_id, requirement_id),
        )

    def list_for_evidence(self, tenant: TenantContext, evidence_id: UUID) -> list[Row]:
        return _fetch_all(
            self._database,
            """
            SELECT * FROM xportra.evidence_requirements
            WHERE tenant_id = %s AND evidence_id = %s
            ORDER BY created_at, id
            """,
            (tenant.tenant_id, evidence_id),
        )

    def link_in_transaction(
        self,
        connection,
        tenant: TenantContext,
        evidence_id: UUID,
        requirement_id: UUID,
    ) -> Row:
        return _insert_in_transaction(
            connection,
            "evidence-requirement link creation",
            """
            INSERT INTO xportra.evidence_requirements (tenant_id, evidence_id, requirement_id)
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (tenant.tenant_id, evidence_id, requirement_id),
        )


class CertificationPermitLicenseRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(
        self,
        tenant: TenantContext,
        exporter_id: UUID,
        issuing_authority_id: UUID,
        title: str,
        issue_date: Any = None,
        expiry_date: Any = None,
        status: str = "issued",
        document_reference: str | None = None,
    ) -> Row:
        return _insert(
            self._database,
            "certification creation",
            """
            INSERT INTO xportra.certification_permit_licenses
                (tenant_id, exporter_id, issuing_authority_id, title,
                 issue_date, expiry_date, status, document_reference)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (tenant.tenant_id, exporter_id, issuing_authority_id, title,
             issue_date, expiry_date, status, document_reference),
        )

    def get(self, tenant: TenantContext, certificate_id: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            """
            SELECT * FROM xportra.certification_permit_licenses
            WHERE tenant_id = %s AND id = %s
            """,
            (tenant.tenant_id, certificate_id),
        )