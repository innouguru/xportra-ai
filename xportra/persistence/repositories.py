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

    def get_by_slug(self, slug: str) -> Row | None:
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.tenants WHERE slug = %s",
            (slug,),
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

    def get_by_email(self, email: str) -> Row | None:
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.users WHERE email = %s",
            (email,),
        )

    def set_supabase_uid(self, user_id: UUID, supabase_uid: UUID) -> Row | None:
        try:
            with self._database.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE xportra.users
                        SET supabase_uid = %s
                        WHERE id = %s
                        RETURNING *
                        """,
                        (supabase_uid, user_id),
                    )
                    return cursor.fetchone()
        except IntegrityError as cause:
            raise PersistenceIntegrityError("user identity linking", cause) from cause


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
            SELECT m.id, m.tenant_id, m.role, m.status,
                   t.legal_name AS tenant_legal_name
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

    def list_all(self) -> list[Row]:
        """Return all regulatory sources (administration listing).

        Read-only; displays stored rows verbatim, including
        supersession links, without inferring any relationship.
        """
        return _fetch_all(
            self._database,
            """
            SELECT * FROM xportra.regulatory_sources
            ORDER BY created_at DESC, id
            """,
            (),
        )

    def create(
        self,
        authority_id: UUID,
        jurisdiction: str,
        title: str,
        version: str | None = None,
        status: str = "draft",
        effective_date: Any | None = None,
        publication_date: Any | None = None,
        source_url: str | None = None,
    ) -> Row:
        return _insert(
            self._database,
            "regulatory source creation",
            """
            INSERT INTO xportra.regulatory_sources
                (authority_id, jurisdiction, title, version, status,
                 effective_date, publication_date, source_url, retrieval_timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
            RETURNING *
            """,
            (
                authority_id, jurisdiction, title, version, status,
                effective_date, publication_date, source_url,
            ),
        )

    def update_source(
        self,
        source_id: UUID,
        *,
        supersedes_source_id: UUID | None = None,
        superseded_by_source_id: UUID | None = None,
        status: str | None = None,
    ) -> Row | None:
        parts: list[str] = []
        params: list[Any] = []
        if supersedes_source_id is not None:
            parts.append("supersedes_source_id = %s")
            params.append(supersedes_source_id)
        if superseded_by_source_id is not None:
            parts.append("superseded_by_source_id = %s")
            params.append(superseded_by_source_id)
        if status is not None:
            parts.append("status = %s")
            params.append(status)
        parts.append("updated_at = now()")
        params.append(source_id)
        return _insert(
            self._database,
            "regulatory source update",
            f"""
            UPDATE xportra.regulatory_sources
            SET {", ".join(parts)}
            WHERE id = %s
            RETURNING *
            """,
            tuple(params),
        )

    def update_source_in_transaction(
        self,
        connection,
        source_id: UUID,
        *,
        supersedes_source_id: UUID | None = None,
        superseded_by_source_id: UUID | None = None,
        status: str | None = None,
    ) -> Row | None:
        parts: list[str] = []
        params: list[Any] = []
        if supersedes_source_id is not None:
            parts.append("supersedes_source_id = %s")
            params.append(supersedes_source_id)
        if superseded_by_source_id is not None:
            parts.append("superseded_by_source_id = %s")
            params.append(superseded_by_source_id)
        if status is not None:
            parts.append("status = %s")
            params.append(status)
        parts.append("updated_at = now()")
        params.append(source_id)
        return _insert_in_transaction(
            connection,
            "regulatory source update",
            f"""
            UPDATE xportra.regulatory_sources
            SET {", ".join(parts)}
            WHERE id = %s
            RETURNING *
            """,
            tuple(params),
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
        id: UUID,
        artifact_id: UUID,
        source_id: UUID,
        document_title: str,
        normalized_text: str,
        normalized_content: Any,
        content_type: str,
        parser_name: str,
        status: str = "normalized",
        normalized_at: Any | None = None,
        created_at: Any | None = None,
        updated_at: Any | None = None,
    ) -> Row:
        return _insert(
            self._database,
            "regulatory document normalization creation",
            """
            INSERT INTO xportra.regulatory_document_normalizations
                (id, artifact_id, source_id, document_title, normalized_text,
                 normalized_content, content_type, parser_name, status, normalized_at,
                 created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                id,
                artifact_id,
                source_id,
                document_title,
                normalized_text,
                Jsonb(normalized_content),
                content_type,
                parser_name,
                status,
                normalized_at or None,
                created_at or None,
                updated_at or None,
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
                 source_location, position, actor, condition_metadata, status,
                 ingestion_job_id, extraction_outcome, parser_version,
                 manual_entry, reviewer_user_id, reviewed_at, source_id,
                 stage_a_status, stage_a_reviewer_user_id,
                 stage_a_reviewed_at, stage_a_rationale,
                 stage_b_status, stage_b_reviewer_user_id,
                 stage_b_reviewed_at, stage_b_rationale, stage_b_pilot_scope)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                values.get("ingestion_job_id"),
                values.get("extraction_outcome", "succeeded"),
                values.get("parser_version"),
                values.get("manual_entry", False),
                values.get("reviewer_user_id"),
                values.get("reviewed_at"),
                values.get("source_id"),
                values.get("stage_a_status", "pending"),
                values.get("stage_a_reviewer_user_id"),
                values.get("stage_a_reviewed_at"),
                values.get("stage_a_rationale"),
                values.get("stage_b_status", "pending"),
                values.get("stage_b_reviewer_user_id"),
                values.get("stage_b_reviewed_at"),
                values.get("stage_b_rationale"),
                values.get("stage_b_pilot_scope"),
            ),
        )

    def get_eligible_for_publication(
        self,
        source_filter: UUID | None = None,
        pilot_scope_filter: str | None = None,
    ) -> list[Row]:
        """Select only requirements meeting all publication eligibility rules."""
        conditions: list[str] = [
            "r.status = 'extracted'",
            "r.stage_a_status = 'verified'",
            "r.stage_b_status = 'approved'",
            # Extraction outcome: successful extraction pipeline OR an
            # authorized manual recovery entry with reviewer attribution.
            "(r.extraction_outcome = 'succeeded' OR "
            "(r.extraction_outcome = 'manual' AND r.manual_entry = TRUE "
            "AND r.reviewer_user_id IS NOT NULL))",
        ]
        params: list[Any] = []
        if source_filter is not None:
            conditions.append("r.source_id = %s")
            params.append(str(source_filter))
        if pilot_scope_filter is not None:
            conditions.append("r.stage_b_pilot_scope = %s")
            params.append(pilot_scope_filter.strip())
        sql = f"""
            SELECT r.*, s.status AS source_status, s.version AS source_version,
                   r.source_location, r.ingestion_job_id, r.normalized_document_id,
                   r.parser_version, r.extraction_outcome, r.stage_a_status,
                   r.stage_a_reviewer_user_id, r.stage_a_reviewed_at, r.stage_a_rationale,
                   r.stage_b_status, r.stage_b_reviewer_user_id,
                   r.stage_b_reviewed_at, r.stage_b_rationale, r.stage_b_pilot_scope,
                   r.manual_entry, r.status, r.created_at, r.updated_at
            FROM xportra.regulatory_requirements AS r
            LEFT JOIN xportra.regulatory_sources AS s ON s.id = r.source_id
            WHERE {" AND ".join(conditions)}
            ORDER BY r.created_at ASC, r.id ASC
        """
        return _fetch_all(self._database, sql, tuple(params) if params else ())

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

    def list_for_source(self, source_id: UUID) -> list[Row]:
        return _fetch_all(
            self._database,
            """
            SELECT requirement.*, document.artifact_id, document.source_id
            FROM xportra.regulatory_requirements AS requirement
            JOIN xportra.regulatory_document_normalizations AS document
              ON document.id = requirement.normalized_document_id
            WHERE requirement.source_id = %s
            ORDER BY requirement.position, requirement.id
            """,
            (source_id,),
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

    def get_with_provenance(self, requirement_id: UUID) -> Row | None:
        """Return a candidate with source, artifact, and ingestion-job provenance.

        Joins regulatory sources and source artifacts so a reviewer can trace
        candidate text back to the source/artifact and extraction run.
        """
        return _fetch_one(
            self._database,
            """
            SELECT requirement.*,
                   document.artifact_id, document.source_id,
                   source.title AS source_title,
                   source.jurisdiction AS source_jurisdiction,
                   source.version AS source_version,
                   source.status AS source_status,
                   source.authority_id AS source_authority_id,
                   artifact.artifact_uri AS artifact_uri,
                   artifact.content_hash AS artifact_content_hash,
                   artifact.content_length AS artifact_content_length,
                   artifact.content_type AS artifact_content_type,
                   artifact.acquisition_channel AS artifact_acquisition_channel,
                   job.id AS ingestion_job_id,
                   job.status AS ingestion_job_status,
                   job.error_details AS ingestion_job_error_details,
                   job.parser_version AS ingestion_job_parser_version
            FROM xportra.regulatory_requirements AS requirement
            JOIN xportra.regulatory_document_normalizations AS document
              ON document.id = requirement.normalized_document_id
            LEFT JOIN xportra.regulatory_sources AS source
              ON source.id = requirement.source_id
            LEFT JOIN xportra.regulatory_source_artifacts AS artifact
              ON artifact.id = document.artifact_id
            LEFT JOIN xportra.regulatory_ingestion_jobs AS job
              ON job.id = requirement.ingestion_job_id
            WHERE requirement.id = %s
            """,
            (requirement_id,),
        )

    def update_stage_a(
        self,
        requirement_id: UUID,
        stage_a_status: str,
        reviewer_user_id: UUID,
        reviewed_at: Any,
        rationale: str,
    ) -> Row | None:
        return _insert(
            self._database,
            "regulatory requirement stage-a update",
            """
            UPDATE xportra.regulatory_requirements
            SET stage_a_status = %s,
                stage_a_reviewer_user_id = %s,
                stage_a_reviewed_at = %s,
                stage_a_rationale = %s,
                updated_at = %s
            WHERE id = %s
            RETURNING *
            """,
            (
                stage_a_status,
                reviewer_user_id,
                reviewed_at,
                rationale,
                reviewed_at,
                requirement_id,
            ),
        )


    def update_stage_b(
        self,
        requirement_id: UUID,
        stage_b_status: str,
        reviewer_user_id: UUID,
        reviewed_at: Any,
        rationale: str,
        pilot_scope: str,
    ) -> Row | None:
        return _insert(
            self._database,
            "regulatory requirement stage-b update",
            """
            UPDATE xportra.regulatory_requirements
            SET stage_b_status = %s,
                stage_b_reviewer_user_id = %s,
                stage_b_reviewed_at = %s,
                stage_b_rationale = %s,
                stage_b_pilot_scope = %s,
                updated_at = %s
            WHERE id = %s
            RETURNING *
            """,
            (
                stage_b_status,
                reviewer_user_id,
                reviewed_at,
                rationale,
                pilot_scope,
                reviewed_at,
                requirement_id,
            ),
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

    def register_upload(
        self,
        tenant: TenantContext,
        *,
        evidence_id: UUID,
        document_title: str,
        document_type: str,
        file_reference_or_uri: str,
        content_hash: str,
        original_filename: str | None = None,
        mime_type: str | None = None,
        storage_bucket: str | None = None,
        uploaded_by: UUID | None = None,
        status: str = "uploaded",
        processing_status: str = "uploaded",
    ) -> Row:
        """Register one uploaded evidence file (Phase 10.4).

        The evidence identity is server-generated by the
        caller; the storage reference is the server-composed
        object key. Registration never stores file bytes,
        document text, or signed URLs.
        """
        return _insert(
            self._database,
            "compliance evidence upload registration",
            """
            INSERT INTO xportra.compliance_evidence
                (id, tenant_id, document_title, document_type,
                 file_reference_or_uri, content_hash, status,
                 processing_status, original_filename, mime_type,
                 storage_bucket, uploaded_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (evidence_id, tenant.tenant_id, document_title,
             document_type, file_reference_or_uri, content_hash,
             status, processing_status, original_filename,
             mime_type, storage_bucket, uploaded_by),
        )

    def get_by_content_hash(
        self, tenant: TenantContext, content_hash: str
    ) -> Row | None:
        """Fetch one tenant-owned evidence row by content hash.

        Backs content-hash idempotency: identical bytes
        within one tenant resolve to one row, while
        cross-tenant identical hashes stay independent
        (the lookup is always tenant-scoped).
        """
        return _fetch_one(
            self._database,
            """
            SELECT * FROM xportra.compliance_evidence
            WHERE tenant_id = %s AND content_hash = %s
            ORDER BY uploaded_at, id LIMIT 1
            """,
            (tenant.tenant_id, content_hash),
        )

    def set_processing_state(
        self,
        tenant: TenantContext,
        evidence_id: UUID,
        *,
        processing_status: str,
        processing_step: str | None = None,
        processing_error: str | None = None,
        processed_at: Any = None,
    ) -> Row | None:
        """Advance one evidence row's processing lifecycle state."""
        with self._database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE xportra.compliance_evidence
                    SET processing_status = %s,
                        processing_step = %s,
                        processing_error = %s,
                        processed_at = %s
                    WHERE tenant_id = %s AND id = %s
                    RETURNING *
                    """,
                    (processing_status, processing_step,
                     processing_error, processed_at,
                     tenant.tenant_id, evidence_id),
                )
                return cursor.fetchone()


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

class EvidenceDocumentRepository:
    """Tenant-scoped persistence boundary for the evidence corpus."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def create(self, record: Row) -> Row:
        return _insert(
            self._database,
            "evidence document creation",
            """
            INSERT INTO xportra.evidence_documents
                (id, tenant_id, title, content, source_type, source_id,
                 source_location, jurisdiction, document_version,
                 effective_date, retrieved_at, status, metadata,
                 content_fingerprint)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                record["id"],
                record["tenant_id"],
                record["title"],
                record["content"],
                record["source_type"],
                record["source_id"],
                record.get("source_location"),
                record.get("jurisdiction"),
                record.get("document_version"),
                record.get("effective_date"),
                record.get("retrieved_at"),
                record["status"],
                Jsonb(record.get("metadata") or {}),
                record["content_fingerprint"],
            ),
        )

    def get_by_id(self, tenant: TenantContext, document_id: UUID) -> Row | None:
        return _fetch_one(
            self._database,
            """SELECT * FROM xportra.evidence_documents
               WHERE tenant_id = %s AND id = %s""",
            (tenant.tenant_id, document_id),
        )

    def get_by_source_identity(
        self, tenant: TenantContext, source_id: str, version: str | None
    ) -> Row | None:
        norm_version = version.strip() if isinstance(version, str) else None
        if norm_version == "":
            norm_version = None
        if norm_version is None:
            statement = """SELECT * FROM xportra.evidence_documents
                WHERE tenant_id = %s AND source_id = %s
                  AND document_version IS NULL"""
            parameters: Sequence[Any] = (tenant.tenant_id, source_id)
        else:
            statement = """SELECT * FROM xportra.evidence_documents
                WHERE tenant_id = %s AND source_id = %s
                  AND document_version = %s"""
            parameters = (tenant.tenant_id, source_id, norm_version)
        return _fetch_one(self._database, statement, parameters)

    def list_for_tenant(self, tenant: TenantContext) -> list[Row]:
        return _fetch_all(
            self._database,
            """SELECT * FROM xportra.evidence_documents
               WHERE tenant_id = %s ORDER BY created_at, id""",
            (tenant.tenant_id,),
        )


class ComplianceAnalysisReportRepository:
    """Tenant-scoped persistence for composed analysis reports.

    Stores the already-composed report representation: counts
    are carried, never recomputed. The decision summary is the
    caller-supplied Phase 3.5 reference carried verbatim.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    def create_in_transaction(
        self,
        connection,
        tenant: TenantContext,
        report_id: UUID,
        case_id: UUID,
        workflow_id: UUID,
        context_fingerprint: str | None,
        counts: dict[str, int],
        requirements_with_missing_information: list[str],
        uncertain_requirement_ids: list[str],
        requirements_with_conflicting_evidence: list[str],
        missing_information: list[Any],
        conflicting_evidence_count: int,
        decision_summary: Any | None,
    ) -> Row:
        return _insert_in_transaction(
            connection,
            "compliance analysis report creation",
            """
            INSERT INTO xportra.compliance_analysis_reports
                (id, tenant_id, case_id, workflow_id,
                 context_fingerprint, total_requirements,
                 applicable_count, satisfied_count,
                 not_satisfied_count, unknown_count,
                 not_applicable_count, conflicting_evidence_count,
                 requirements_with_missing_information,
                 uncertain_requirement_ids,
                 requirements_with_conflicting_evidence,
                 missing_information, decision_summary)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                report_id,
                tenant.tenant_id,
                case_id,
                workflow_id,
                context_fingerprint,
                counts["total_requirements"],
                counts["applicable_count"],
                counts["satisfied_count"],
                counts["not_satisfied_count"],
                counts["unknown_count"],
                counts["not_applicable_count"],
                conflicting_evidence_count,
                Jsonb(requirements_with_missing_information),
                Jsonb(uncertain_requirement_ids),
                Jsonb(requirements_with_conflicting_evidence),
                Jsonb(missing_information),
                Jsonb(decision_summary)
                if decision_summary is not None else None,
            ),
        )

    def get(
        self, tenant: TenantContext, report_id: UUID
    ) -> Row | None:
        return _fetch_one(
            self._database,
            """SELECT * FROM xportra.compliance_analysis_reports
               WHERE tenant_id = %s AND id = %s""",
            (tenant.tenant_id, report_id),
        )


class ComplianceAnalysisRepository:
    """Tenant-scoped persistence for per-requirement analyses.

    Stores the already-composed analysis representation.
    Typed reference lists keep their fixed domain schemas
    as JSONB (the established evidence_ids convention);
    every identity, state, and ordering field is a column.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    def create_in_transaction(
        self,
        connection,
        tenant: TenantContext,
        analysis_id: UUID,
        report_id: UUID,
        case_id: UUID,
        workflow_id: UUID,
        requirement_id: UUID,
        position: int,
        requirement_text: str,
        applicability: str,
        assessment: str,
        explanation: str,
        uncertainty: str,
        uncertainty_explanation: str,
        evidence_sufficiency: str,
        contradiction_state: str,
        sufficiency_explanation: str,
        missing_information: list[str],
        supporting_evidence: list[Any],
        conflicting_evidence: list[Any],
        knowledge_references: list[Any],
        sources: list[Any],
        missing_items: list[Any],
    ) -> Row:
        return _insert_in_transaction(
            connection,
            "compliance analysis creation",
            """
            INSERT INTO xportra.compliance_analyses
                (id, tenant_id, report_id, case_id, workflow_id,
                 requirement_id, position, requirement_text,
                 applicability, assessment, explanation,
                 uncertainty, uncertainty_explanation,
                 evidence_sufficiency, contradiction_state,
                 sufficiency_explanation, missing_information,
                 supporting_evidence, conflicting_evidence,
                 knowledge_references, sources, missing_items)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s)
            RETURNING *
            """,
            (
                analysis_id,
                tenant.tenant_id,
                report_id,
                case_id,
                workflow_id,
                requirement_id,
                position,
                requirement_text,
                applicability,
                assessment,
                explanation,
                uncertainty,
                uncertainty_explanation,
                evidence_sufficiency,
                contradiction_state,
                sufficiency_explanation,
                Jsonb(missing_information),
                Jsonb(supporting_evidence),
                Jsonb(conflicting_evidence),
                Jsonb(knowledge_references),
                Jsonb(sources),
                Jsonb(missing_items),
            ),
        )

    def get(
        self, tenant: TenantContext, analysis_id: UUID
    ) -> Row | None:
        return _fetch_one(
            self._database,
            """SELECT * FROM xportra.compliance_analyses
               WHERE tenant_id = %s AND id = %s""",
            (tenant.tenant_id, analysis_id),
        )

    def list_for_report(
        self, tenant: TenantContext, report_id: UUID
    ) -> list[Row]:
        return _fetch_all(
            self._database,
            """SELECT * FROM xportra.compliance_analyses
               WHERE tenant_id = %s AND report_id = %s
               ORDER BY position, id""",
            (tenant.tenant_id, report_id),
        )


class ComplianceAnalysisTraceRepository:
    """Tenant-scoped persistence for record-only decision traces.

    Stores the already-constructed trace representation:
    identifier linkage, copied deterministic state, and the
    structured pipeline steps. No deliberation, prompts, or
    provider internals are representable here.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    def create_in_transaction(
        self,
        connection,
        tenant: TenantContext,
        trace_id: UUID,
        report_id: UUID,
        analysis_id: UUID,
        case_id: UUID,
        workflow_id: UUID,
        requirement_id: UUID,
        position: int,
        context_fingerprint: str | None,
        applicability: str,
        assessment: str,
        explanation: str,
        evidence_sufficiency: str,
        contradiction_state: str,
        sufficiency_explanation: str,
        uncertainty: str,
        missing_information: list[str],
        answer_fingerprint: str,
        input_fingerprint: str,
        steps: list[Any],
        supporting_evidence: list[Any],
        conflicting_evidence: list[Any],
        knowledge_references: list[Any],
        sources: list[Any],
    ) -> Row:
        return _insert_in_transaction(
            connection,
            "compliance analysis trace creation",
            """
            INSERT INTO xportra.compliance_analysis_traces
                (id, tenant_id, report_id, analysis_id, case_id,
                 workflow_id, requirement_id, position,
                 context_fingerprint, applicability, assessment,
                 explanation, evidence_sufficiency,
                 contradiction_state, sufficiency_explanation,
                 uncertainty, missing_information,
                 answer_fingerprint, input_fingerprint, steps,
                 supporting_evidence, conflicting_evidence,
                 knowledge_references, sources)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s)
            RETURNING *
            """,
            (
                trace_id,
                tenant.tenant_id,
                report_id,
                analysis_id,
                case_id,
                workflow_id,
                requirement_id,
                position,
                context_fingerprint,
                applicability,
                assessment,
                explanation,
                evidence_sufficiency,
                contradiction_state,
                sufficiency_explanation,
                uncertainty,
                Jsonb(missing_information),
                answer_fingerprint,
                input_fingerprint,
                Jsonb(steps),
                Jsonb(supporting_evidence),
                Jsonb(conflicting_evidence),
                Jsonb(knowledge_references),
                Jsonb(sources),
            ),
        )

    def get(
        self, tenant: TenantContext, trace_id: UUID
    ) -> Row | None:
        return _fetch_one(
            self._database,
            """SELECT * FROM xportra.compliance_analysis_traces
               WHERE tenant_id = %s AND id = %s""",
            (tenant.tenant_id, trace_id),
        )

    def list_for_report(
        self, tenant: TenantContext, report_id: UUID
    ) -> list[Row]:
        return _fetch_all(
            self._database,
            """SELECT * FROM xportra.compliance_analysis_traces
               WHERE tenant_id = %s AND report_id = %s
               ORDER BY position, id""",
            (tenant.tenant_id, report_id),
        )


class ComplianceWorkflowRoundRepository:
    """Tenant-scoped server-side round linkage per workflow.

    Records which report each authoritative round index
    points to. This is linkage, not a second workflow
    history: states and transitions stay client-held and
    domain-owned; these rows are the anti-forgery anchor
    that lets later requests verify claimed round history
    and resolve the current result. First writer wins per
    (workflow, round_index); divergent concurrent analyses
    keep their own client records but only the recorded
    linkage finalizes.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    def create_in_transaction(
        self,
        connection,
        tenant: TenantContext,
        workflow_id: UUID,
        round_index: int,
        case_id: UUID,
        shipment_id: UUID | None,
        report_id: UUID,
        analysis_ids: list[str],
        trace_ids: list[str],
        input_fingerprints: list[str],
    ) -> Row:
        return _insert_in_transaction(
            connection,
            "compliance workflow round creation",
            """
            INSERT INTO xportra.compliance_workflow_rounds
                (tenant_id, workflow_id, round_index, case_id,
                 shipment_id, report_id, analysis_ids, trace_ids,
                 input_fingerprints)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                tenant.tenant_id,
                workflow_id,
                round_index,
                case_id,
                shipment_id,
                report_id,
                Jsonb(analysis_ids),
                Jsonb(trace_ids),
                Jsonb(input_fingerprints),
            ),
        )

    def get(
        self,
        tenant: TenantContext,
        workflow_id: UUID,
        round_index: int,
    ) -> Row | None:
        return _fetch_one(
            self._database,
            """SELECT * FROM xportra.compliance_workflow_rounds
               WHERE tenant_id = %s AND workflow_id = %s
                 AND round_index = %s""",
            (tenant.tenant_id, workflow_id, round_index),
        )

    def list_for_workflow(
        self, tenant: TenantContext, workflow_id: UUID
    ) -> list[Row]:
        return _fetch_all(
            self._database,
            """SELECT * FROM xportra.compliance_workflow_rounds
               WHERE tenant_id = %s AND workflow_id = %s
               ORDER BY round_index""",
            (tenant.tenant_id, workflow_id),
        )

    def latest_for_workflow(
        self, tenant: TenantContext, workflow_id: UUID
    ) -> Row | None:
        return _fetch_one(
            self._database,
            """SELECT * FROM xportra.compliance_workflow_rounds
               WHERE tenant_id = %s AND workflow_id = %s
               ORDER BY round_index DESC LIMIT 1""",
            (tenant.tenant_id, workflow_id),
        )


class ComplianceWorkflowRepository:
    """Tenant-scoped server-owned workflow progression rows.

    Persists the mutable workflow record the client used
    to echo back each request: identity binding, current
    state, supplied evidence references, and open
    requirements. This is storage for the existing domain
    record, not a second workflow model — transition rules
    stay domain-owned, round linkage stays in
    ``compliance_workflow_rounds``, and result content
    stays in the result tables. One row per workflow;
    ``save_in_transaction`` overwrites only the stored
    row and reports ``None`` when no row exists (the
    caller fails closed instead of resurrecting state).
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    def create_in_transaction(
        self,
        connection,
        tenant: TenantContext,
        workflow_id: UUID,
        case_id: UUID,
        shipment_id: UUID | None,
        state: str,
    ) -> Row:
        return _insert_in_transaction(
            connection,
            "compliance workflow creation",
            """
            INSERT INTO xportra.compliance_workflows
                (tenant_id, workflow_id, case_id, shipment_id,
                 state)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                tenant.tenant_id,
                workflow_id,
                case_id,
                shipment_id,
                state,
            ),
        )

    def get(
        self, tenant: TenantContext, workflow_id: UUID
    ) -> Row | None:
        return _fetch_one(
            self._database,
            """SELECT * FROM xportra.compliance_workflows
               WHERE tenant_id = %s AND workflow_id = %s""",
            (tenant.tenant_id, workflow_id),
        )

    def list_for_shipment(
        self, tenant: TenantContext, shipment_id: UUID
    ) -> list[Row]:
        """Return every workflow bound to a shipment, latest first.

        One workflow per (shipment, case) is the domain
        invariant, but nothing in the schema forbids the
        same shipment across cases — callers receive all
        rows in recency order and decide explicitly.
        """
        return _fetch_all(
            self._database,
            """SELECT * FROM xportra.compliance_workflows
               WHERE tenant_id = %s AND shipment_id = %s
               ORDER BY updated_at DESC, workflow_id DESC""",
            (tenant.tenant_id, shipment_id),
        )

    def save_in_transaction(
        self,
        connection,
        tenant: TenantContext,
        workflow_id: UUID,
        case_id: UUID,
        shipment_id: UUID | None,
        state: str,
        supplied_evidence_ids: list[UUID],
        open_requirements: list[UUID],
    ) -> Row | None:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE xportra.compliance_workflows
                    SET case_id = %s,
                        shipment_id = %s,
                        state = %s,
                        supplied_evidence_ids = %s,
                        open_requirements = %s
                    WHERE tenant_id = %s AND workflow_id = %s
                    RETURNING *
                    """,
                    (
                        case_id,
                        shipment_id,
                        state,
                        supplied_evidence_ids,
                        open_requirements,
                        tenant.tenant_id,
                        workflow_id,
                    ),
                )
                return cursor.fetchone()
        except IntegrityError as cause:
            raise PersistenceIntegrityError(
                "compliance workflow save", cause) from cause


class ShipmentRepository:
    """Tenant-scoped server-owned commercial shipment rows.

    Persists the ADR-0013 shipment aggregate: commercial
    profile facts plus the shipment-only lifecycle status.
    Identity is the composite ``(tenant_id, shipment_id)``
    — lookups never resolve by ``shipment_id`` alone, so a
    caller can never reach another tenant's row. This is
    storage for the domain ``Shipment`` record, not a
    second shipment model: validation and lifecycle rules
    stay domain-owned, workflow progression stays in
    ``compliance_workflows``, and result content stays in
    the result tables. ``save_in_transaction`` overwrites
    only the stored row and reports ``None`` when no row
    exists (the caller fails closed instead of
    resurrecting state).
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    def create_in_transaction(
        self,
        connection,
        tenant: TenantContext,
        shipment_id: UUID,
        case_id: UUID,
        product: str,
        origin_country: str,
        destination_country: str,
        quantity: str | None,
        unit: str | None,
        shipment_date: str | None,
        status: str,
    ) -> Row:
        return _insert_in_transaction(
            connection,
            "shipment creation",
            """
            INSERT INTO xportra.shipments
                (tenant_id, shipment_id, case_id, product,
                 origin_country, destination_country,
                 quantity, unit, shipment_date, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                tenant.tenant_id,
                shipment_id,
                case_id,
                product,
                origin_country,
                destination_country,
                quantity,
                unit,
                shipment_date,
                status,
            ),
        )

    def get(
        self, tenant: TenantContext, shipment_id: UUID
    ) -> Row | None:
        return _fetch_one(
            self._database,
            """SELECT * FROM xportra.shipments
               WHERE tenant_id = %s AND shipment_id = %s""",
            (tenant.tenant_id, shipment_id),
        )

    def get_in_transaction(
        self, connection, tenant: TenantContext, shipment_id: UUID
    ) -> Row | None:
        """Read one shipment row inside the caller's transaction.

        Lets terminal writes (finalization) verify and
        lock the shipment atomically instead of
        observing pre-commit state across separate
        transactions.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT * FROM xportra.shipments
                   WHERE tenant_id = %s AND shipment_id = %s""",
                (tenant.tenant_id, shipment_id),
            )
            return cursor.fetchone()

    def list_for_tenant(
        self,
        tenant: TenantContext,
        limit: int | None,
        offset: int,
    ) -> list[Row]:
        if limit is None:
            return _fetch_all(
                self._database,
                """SELECT * FROM xportra.shipments
                   WHERE tenant_id = %s
                   ORDER BY created_at DESC, shipment_id DESC
                   OFFSET %s""",
                (tenant.tenant_id, offset),
            )
        return _fetch_all(
            self._database,
            """SELECT * FROM xportra.shipments
               WHERE tenant_id = %s
               ORDER BY created_at DESC, shipment_id DESC
               LIMIT %s OFFSET %s""",
            (tenant.tenant_id, limit, offset),
        )

    def count_for_tenant(self, tenant: TenantContext) -> int:
        row = _fetch_one(
            self._database,
            """SELECT COUNT(*) AS count FROM xportra.shipments
               WHERE tenant_id = %s""",
            (tenant.tenant_id,),
        )
        return int(row["count"]) if row is not None else 0

    def save_in_transaction(
        self,
        connection,
        tenant: TenantContext,
        shipment_id: UUID,
        case_id: UUID,
        product: str,
        origin_country: str,
        destination_country: str,
        quantity: str | None,
        unit: str | None,
        shipment_date: str | None,
        status: str,
    ) -> Row | None:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE xportra.shipments
                    SET case_id = %s,
                        product = %s,
                        origin_country = %s,
                        destination_country = %s,
                        quantity = %s,
                        unit = %s,
                        shipment_date = %s,
                        status = %s
                    WHERE tenant_id = %s AND shipment_id = %s
                    RETURNING *
                    """,
                    (
                        case_id,
                        product,
                        origin_country,
                        destination_country,
                        quantity,
                        unit,
                        shipment_date,
                        status,
                        tenant.tenant_id,
                        shipment_id,
                    ),
                )
                return cursor.fetchone()
        except IntegrityError as cause:
            raise PersistenceIntegrityError(
                "shipment save", cause) from cause


class FinalAssessmentPackageRepository:
    """Tenant-scoped linkage for produced final packages.

    Stores linkage only — workflow/case/report/round
    identities plus the open-requirement snapshot. All
    compliance content lives in the result tables; the
    decision summary stays carried by the stored report.
    At most one row per workflow ever exists, which is
    what makes cross-request second-finalization
    structurally impossible.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    def create_in_transaction(
        self,
        connection,
        tenant: TenantContext,
        workflow_id: UUID,
        case_id: UUID,
        shipment_id: UUID | None,
        report_id: UUID,
        round_index: int,
        open_requirements: list[str],
    ) -> Row:
        return _insert_in_transaction(
            connection,
            "final assessment package creation",
            """
            INSERT INTO xportra.final_assessment_packages
                (tenant_id, workflow_id, case_id, shipment_id,
                 report_id, round_index, open_requirements)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                tenant.tenant_id,
                workflow_id,
                case_id,
                shipment_id,
                report_id,
                round_index,
                Jsonb(open_requirements),
            ),
        )

    def get(
        self, tenant: TenantContext, workflow_id: UUID
    ) -> Row | None:
        return _fetch_one(
            self._database,
            """SELECT * FROM xportra.final_assessment_packages
               WHERE tenant_id = %s AND workflow_id = %s""",
            (tenant.tenant_id, workflow_id),
        )


class GlobalStaffGrantRepository:
    """Current-state global staff permission grants (Model A).

    At most one row exists per ``(user_id, permission)`` pair. Revocation
    UPDATEs the existing row (setting ``revoked_at``/``revoked_by``); it is
    never deleted. Re-grant reactivates the existing row. Historical grant
    periods are preserved only in the append-only audit table.
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    def get(self, user_id: UUID, permission: str) -> Row | None:
        return _fetch_one(
            self._database,
            """
            SELECT * FROM xportra.global_staff_grants
            WHERE user_id = %s AND permission = %s
            """,
            (user_id, permission),
        )

    def get_active(self, user_id: UUID, permission: str) -> Row | None:
        return _fetch_one(
            self._database,
            """
            SELECT * FROM xportra.global_staff_grants
            WHERE user_id = %s AND permission = %s AND status = 'active'
            """,
            (user_id, permission),
        )

    def list_active_for_user(self, user_id: UUID) -> list[Row]:
        """Active grant rows for one user (current-state read path), used by
        ``GET /me`` to expose which global staff permissions the caller holds."""
        return _fetch_all(
            self._database,
            """
            SELECT permission FROM xportra.global_staff_grants
            WHERE user_id = %s AND status = 'active'
            ORDER BY permission
            """,
            (user_id,),
        )

    def list_for_user(self, user_id: UUID) -> list[Row]:
        return _fetch_all(
            self._database,
            """
            SELECT * FROM xportra.global_staff_grants
            WHERE user_id = %s
            ORDER BY permission, created_at, id
            """,
            (user_id,),
        )

    def lock_in_transaction(
        self, connection, user_id: UUID, permission: str
    ) -> Row | None:
        """Lock and return the current-state grant row for mutation."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM xportra.global_staff_grants
                WHERE user_id = %s AND permission = %s
                FOR UPDATE
                """,
                (user_id, permission),
            )
            return cursor.fetchone()

    def insert_in_transaction(
        self,
        connection,
        user_id: UUID,
        permission: str,
        granted_by: UUID,
        reason: str | None,
    ) -> Row:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO xportra.global_staff_grants
                        (user_id, permission, status, granted_at, granted_by, reason)
                    VALUES (%s, %s, 'active', now(), %s, %s)
                    RETURNING *
                    """,
                    (user_id, permission, granted_by, reason),
                )
                return cursor.fetchone()
        except IntegrityError as cause:
            raise PersistenceIntegrityError(
                "global staff grant creation", cause
            ) from cause

    def exists_any_in_transaction(self, connection, permission: str) -> bool:
        """Return whether any grant row exists for the permission."""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1 FROM xportra.global_staff_grants
                WHERE permission = %s
                LIMIT 1
                """,
                (permission,),
            )
            return cursor.fetchone() is not None

    def reactivate_in_transaction(
        self,
        connection,
        user_id: UUID,
        permission: str,
        granted_by: UUID,
        reason: str | None,
    ) -> Row | None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE xportra.global_staff_grants
                SET status = 'active',
                    granted_at = now(),
                    granted_by = %s,
                    revoked_at = NULL,
                    revoked_by = NULL,
                    reason = %s,
                    updated_at = now()
                WHERE user_id = %s AND permission = %s
                RETURNING *
                """,
                (granted_by, reason, user_id, permission),
            )
            return cursor.fetchone()

    def revoke_in_transaction(
        self,
        connection,
        user_id: UUID,
        permission: str,
        revoked_by: UUID,
        reason: str | None,
    ) -> Row | None:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE xportra.global_staff_grants
                SET status = 'revoked',
                    revoked_at = now(),
                    revoked_by = %s,
                    reason = %s,
                    updated_at = now()
                WHERE user_id = %s AND permission = %s AND status = 'active'
                RETURNING *
                """,
                (revoked_by, reason, user_id, permission),
            )
            return cursor.fetchone()


class GlobalStaffAuthorizationRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def get_by_ref(self, authorization_ref: str) -> Row | None:
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.global_staff_authorizations WHERE authorization_ref = %s",
            (authorization_ref,),
        )

    def get_approved_unconsumed(self, target_user_id: UUID, permission: str) -> Row | None:
        return _fetch_one(
            self._database,
            """
            SELECT * FROM xportra.global_staff_authorizations
            WHERE target_user_id = %s AND permission = %s
              AND status = 'approved' AND (consumed_at IS NULL OR status <> 'consumed')
            ORDER BY approved_at DESC LIMIT 1
            """,
            (target_user_id, permission),
        )

    def consume_in_transaction(
        self,
        connection,
        authorization_id: UUID,
        consumed_by: UUID,
    ) -> Row | None:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE xportra.global_staff_authorizations
                    SET status = 'consumed', consumed_at = now(), consumed_by = %s, updated_at = now()
                    WHERE id = %s AND status = 'approved' AND consumed_at IS NULL
                    RETURNING *
                    """,
                    (consumed_by, authorization_id),
                )
                return cursor.fetchone()
        except IntegrityError as cause:
            raise PersistenceIntegrityError(
                "global staff authorization consumption", cause
            ) from cause


class GlobalStaffAuditRepository:
    """Append-only audit of global staff permission-management events.

    Rows are inserted only; ordinary application roles cannot update or
    delete historical records (enforced by a database trigger).
    """

    def __init__(self, database: Database) -> None:
        self._database = database

    def insert_in_transaction(
        self,
        connection,
        event_type: str,
        actor_user_id: UUID,
        target_user_id: UUID,
        permission: str,
        reason: str | None,
        authorization_ref: str | None = None,
    ) -> Row:
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO xportra.global_staff_audit
                        (event_type, actor_user_id, target_user_id, permission, reason, authorization_ref)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING *
                    """,
                    (event_type, actor_user_id, target_user_id, permission, reason, authorization_ref),
                )
                return cursor.fetchone()
        except IntegrityError as cause:
            raise PersistenceIntegrityError(
                "global staff audit creation", cause
            ) from cause

    def list_for_target(self, target_user_id: UUID) -> list[Row]:
        return _fetch_all(
            self._database,
            """
            SELECT * FROM xportra.global_staff_audit
            WHERE target_user_id = %s
            ORDER BY created_at, id
            """,
            (target_user_id,),
        )

    def count_for_target(self, target_user_id: UUID) -> int:
        row = _fetch_one(
            self._database,
            """
            SELECT COUNT(*) AS count FROM xportra.global_staff_audit
            WHERE target_user_id = %s
            """,
            (target_user_id,),
        )
        return int(row["count"]) if row is not None else 0


class RegulatoryIngestionJobRepository:
    def __init__(self, database) -> None:
        self._database = database

    def create(self, artifact_id, source_id, actor_user_id=None, audit_ref=None, parser_version="v1", attempt_number=None):
        from .database import Database
        return _insert(
            self._database,
            "regulatory ingestion job creation",
            "INSERT INTO xportra.regulatory_ingestion_jobs (artifact_id, source_id, status, actor_user_id, audit_ref, parser_version, attempt_number) VALUES (%s, %s, 'pending', %s, %s, %s, %s) RETURNING *",
            (artifact_id, source_id, actor_user_id, audit_ref, parser_version, attempt_number if attempt_number is not None else 1),
        )

    def get(self, job_id):
        return _fetch_one(self._database, "SELECT * FROM xportra.regulatory_ingestion_jobs WHERE id = %s", (job_id,))

    def get_by_artifact_attempt(self, artifact_id, attempt_number):
        return _fetch_one(self._database, "SELECT * FROM xportra.regulatory_ingestion_jobs WHERE artifact_id = %s AND attempt_number = %s", (artifact_id, attempt_number))

    def max_attempts_for_artifact(self, artifact_id):
        row = _fetch_one(
            self._database,
            "SELECT COALESCE(MAX(attempt_number), 0) AS max_attempt FROM xportra.regulatory_ingestion_jobs WHERE artifact_id = %s",
            (artifact_id,),
        )
        return int(row["max_attempt"]) if row is not None else 0

    def list_for_artifact(self, artifact_id):
        return _fetch_all(self._database, "SELECT * FROM xportra.regulatory_ingestion_jobs WHERE artifact_id = %s ORDER BY attempt_number, created_at", (artifact_id,))

    def list_for_source(self, source_id):
        return _fetch_all(self._database, "SELECT * FROM xportra.regulatory_ingestion_jobs WHERE source_id = %s ORDER BY created_at, id", (source_id,))

    def claim(self, job_id, actor_user_id=None):
        from psycopg.errors import IntegrityError
        from .errors import PersistenceIntegrityError
        try:
            with self._database.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("UPDATE xportra.regulatory_ingestion_jobs SET status = 'claimed', started_at = now(), actor_user_id = %s WHERE id = %s AND status IN ('pending', 'retryable') RETURNING *", (actor_user_id, job_id))
                    return cursor.fetchone()
        except IntegrityError as cause:
            raise PersistenceIntegrityError("regulatory ingestion job claim", cause) from cause

    def complete(self, job_id, actor_user_id=None):
        from psycopg.errors import IntegrityError
        from .errors import PersistenceIntegrityError
        try:
            with self._database.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("UPDATE xportra.regulatory_ingestion_jobs SET status = 'completed', completed_at = now(), actor_user_id = COALESCE(%s, actor_user_id) WHERE id = %s AND status IN ('claimed', 'processing', 'retryable') RETURNING *", (actor_user_id, job_id))
                    return cursor.fetchone()
        except IntegrityError as cause:
            raise PersistenceIntegrityError("regulatory ingestion job complete", cause) from cause

    def fail(self, job_id, error_details=None, make_retryable=False, actor_user_id=None):
        from psycopg.errors import IntegrityError
        from .errors import PersistenceIntegrityError
        next_status = "retryable" if make_retryable else "failed"
        # Bounded-retry accounting: each retryable failure increments the
        # per-attempt retry counter; terminal failures leave it unchanged
        # so the authorized retry endpoint can distinguish a fresh attempt.
        if make_retryable:
            update_sql = "UPDATE xportra.regulatory_ingestion_jobs SET status = 'retryable', completed_at = now(), error_details = %s, actor_user_id = COALESCE(%s, actor_user_id), retry_count = retry_count + 1 WHERE id = %s AND status IN ('claimed', 'processing', 'pending') RETURNING *"
        else:
            update_sql = "UPDATE xportra.regulatory_ingestion_jobs SET status = 'failed', completed_at = now(), error_details = %s, actor_user_id = COALESCE(%s, actor_user_id) WHERE id = %s AND status IN ('claimed', 'processing', 'pending') RETURNING *"
        try:
            with self._database.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(update_sql, (error_details, actor_user_id, job_id))
                    return cursor.fetchone()
        except IntegrityError as cause:
            raise PersistenceIntegrityError("regulatory ingestion job fail", cause) from cause


class RegulatoryArtifactLegalHoldRepository:
    """Durable, append-only legal-hold records for regulatory artifacts."""

    def __init__(self, database) -> None:
        self._database = database

    def create(
        self,
        artifact_id,
        actor_user_id,
        authorization_ref,
        reason,
        status="active",
    ):
        return _insert(
            self._database,
            "regulatory artifact legal hold creation",
            """
            INSERT INTO xportra.regulatory_artifact_legal_hold
                (artifact_id, status, actor_user_id, authorization_ref, reason)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (artifact_id, status, actor_user_id, authorization_ref, reason),
        )

    def get_active_for_artifact(self, artifact_id):
        return _fetch_all(
            self._database,
            "SELECT * FROM xportra.regulatory_artifact_legal_hold WHERE artifact_id = %s AND status = 'active' ORDER BY placed_at ASC",
            (artifact_id,),
        )

    def get_by_hold_id(self, hold_id):
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.regulatory_artifact_legal_hold WHERE id = %s",
            (hold_id,),
        )

    def release(
        self,
        hold_id,
        released_by,
        release_authorization_ref,
    ):
        try:
            with self._database.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "UPDATE xportra.regulatory_artifact_legal_hold SET status = 'released', released_at = now(), released_by = %s, release_authorization_ref = %s WHERE id = %s AND status = 'active' RETURNING *",
                        (released_by, release_authorization_ref, hold_id),
                    )
                    return cursor.fetchone()
        except IntegrityError as cause:
            raise PersistenceIntegrityError("regulatory artifact legal hold release", cause) from cause


class RegulatoryArtifactDeletionIntentRepository:
    """Durable deletion-intent records with safe state-machine support."""

    def __init__(self, database) -> None:
        self._database = database

    def create(
        self,
        artifact_id,
        content_hash,
        actor_user_id,
        authorization_ref,
        reason,
        retention_eligibility,
        legal_hold_active=False,
        audit_event_ref=None,
    ):
        return _insert(
            self._database,
            "regulatory artifact deletion intent creation",
            """
            INSERT INTO xportra.regulatory_artifact_deletion_intent
                (artifact_id, content_hash, status, actor_user_id, authorization_ref, reason, retention_eligibility, legal_hold_active, audit_event_ref)
            VALUES (%s, %s, 'pending', %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (artifact_id, content_hash, actor_user_id, authorization_ref, reason, retention_eligibility, legal_hold_active, audit_event_ref),
        )

    def get_by_artifact_auth_actor(self, artifact_id, authorization_ref, actor_user_id):
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.regulatory_artifact_deletion_intent WHERE artifact_id = %s AND authorization_ref = %s AND actor_user_id = %s ORDER BY created_at DESC LIMIT 1",
            (artifact_id, authorization_ref, actor_user_id),
        )

    def get_by_artifact(self, artifact_id):
        return _fetch_all(
            self._database,
            "SELECT * FROM xportra.regulatory_artifact_deletion_intent WHERE artifact_id = %s ORDER BY created_at DESC",
            (artifact_id,),
        )

    def update_status(
        self,
        intent_id,
        status,
        deleted_at=None,
        reconciled=None,
        reconciliation_note=None,
        retry_attempt=None,
        max_retry_attempt=None,
    ):
        try:
            with self._database.transaction() as connection:
                with connection.cursor() as cursor:
                    parts = ["UPDATE xportra.regulatory_artifact_deletion_intent SET status = %s"]
                    params = [status]
                    if deleted_at is not None:
                        parts.append("deleted_at = %s")
                        params.append(deleted_at)
                    if reconciled is not None:
                        parts.append("reconciled = %s")
                        params.append(reconciled)
                    if reconciliation_note is not None:
                        parts.append("reconciliation_note = %s")
                        params.append(reconciliation_note)
                    if retry_attempt is not None:
                        parts.append("retry_attempt = %s")
                        params.append(retry_attempt)
                    if max_retry_attempt is not None:
                        parts.append("max_retry_attempt = %s")
                        params.append(max_retry_attempt)
                    parts.append("updated_at = now() WHERE id = %s RETURNING *")
                    params.append(intent_id)
                    cursor.execute(" ".join(parts), tuple(params))
                    return cursor.fetchone()
        except IntegrityError as cause:
            raise PersistenceIntegrityError("regulatory artifact deletion intent status update", cause) from cause


class RegulatoryReviewFlagRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def create(
        self,
        requirement_id: UUID | None,
        trigger_source_id: UUID | None,
        trigger_type: str,
        actor_user_id: UUID | None,
        rationale: str,
    ) -> dict[str, Any]:
        return _insert(
            self._database,
            "regulatory review flag creation",
            """
            INSERT INTO xportra.regulatory_review_flags
                (requirement_id, trigger_source_id, trigger_type,
                 status, actor_user_id, rationale, created_at, updated_at)
            VALUES (%s, %s, %s, 'pending_review', %s, %s, now(), now())
            RETURNING *
            """,
            (requirement_id, trigger_source_id, trigger_type, actor_user_id, rationale),
        )

    def create_in_transaction(
        self,
        connection,
        requirement_id: UUID | None,
        trigger_source_id: UUID | None,
        trigger_type: str,
        actor_user_id: UUID | None,
        rationale: str,
    ) -> dict[str, Any]:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO xportra.regulatory_review_flags
                    (requirement_id, trigger_source_id, trigger_type,
                     status, actor_user_id, rationale, created_at, updated_at)
                VALUES (%s, %s, %s, 'pending_review', %s, %s, now(), now())
                RETURNING *
                """,
                (requirement_id, trigger_source_id, trigger_type, actor_user_id, rationale),
            )
            return dict(cursor.fetchone())

    def get_for_requirement(self, requirement_id: UUID) -> list[dict[str, Any]]:
        return _fetch_all(
            self._database,
            "SELECT * FROM xportra.regulatory_review_flags WHERE requirement_id = %s ORDER BY created_at DESC",
            (requirement_id,),
        )

    def get_for_source(self, source_id: UUID) -> list[dict[str, Any]]:
        return _fetch_all(
            self._database,
            "SELECT * FROM xportra.regulatory_review_flags WHERE trigger_source_id = %s ORDER BY created_at DESC",
            (source_id,),
        )

    def update_status(
        self,
        flag_id: UUID,
        status: str,
        rationale: str | None = None,
    ) -> dict[str, Any] | None:
        with self._database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE xportra.regulatory_review_flags
                    SET status = %s, rationale = COALESCE(%s, rationale), updated_at = now()
                    WHERE id = %s RETURNING *
                    """,
                    (status, rationale, flag_id),
                )
                return cursor.fetchone()

    def get_by_id(self, flag_id: UUID) -> dict[str, Any] | None:
        return _fetch_one(
            self._database,
            "SELECT * FROM xportra.regulatory_review_flags WHERE id = %s",
            (flag_id,),
        )

    def list_pending_for_source(self, source_id: UUID) -> list[dict[str, Any]]:
        return _fetch_all(
            self._database,
            "SELECT * FROM xportra.regulatory_review_flags WHERE trigger_source_id = %s AND status = 'pending_review' ORDER BY created_at",
            (source_id,),
        )
