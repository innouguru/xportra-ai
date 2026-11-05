"""Persistence operations for durable regulatory publication indexing."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from xportra.persistence.database import Database
from xportra.persistence.repositories import _fetch_all, _fetch_one
from xportra.domain.regulatory_publication import (
    regulatory_publication_fingerprint,
)

_CURRENTLY_PUBLISHED = """
    r.status = 'published'
    AND r.stage_a_status = 'verified'
    AND r.stage_b_status = 'approved'
    AND s.status = 'active'
    AND NOT EXISTS (
        SELECT 1
        FROM xportra.regulatory_review_flags AS f
        WHERE f.status = 'pending_review'
          AND (
              f.requirement_id = r.id
              OR f.trigger_source_id = r.source_id
          )
    )
"""

_INDEXABLE_REQUIREMENT = f"""
    SELECT r.id, r.requirement_text, r.source_id,
           r.normalized_document_id, r.source_location, r.position,
           r.parser_version, r.published_at,
           s.title AS source_title, s.jurisdiction AS source_jurisdiction,
           s.version AS source_version
    FROM xportra.regulatory_requirements AS r
    JOIN xportra.regulatory_sources AS s ON s.id = r.source_id
    WHERE r.id = %s AND {_CURRENTLY_PUBLISHED}
"""


class RegulatoryPublicationIndexJobRepository:
    """Claim and update the PostgreSQL publication-index outbox."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def claim_next(self, *, lease_seconds: int = 300) -> dict[str, Any] | None:
        with self._database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    WITH candidate AS (
                        SELECT requirement_id
                        FROM xportra.regulatory_publication_index_jobs
                        WHERE (
                            status IN ('pending', 'retryable')
                            AND next_attempt_at <= now()
                        ) OR (
                            status = 'processing'
                            AND lease_expires_at <= now()
                        )
                        ORDER BY created_at, requirement_id
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    UPDATE xportra.regulatory_publication_index_jobs AS job
                    SET status = 'processing',
                        attempt_count = job.attempt_count + 1,
                        claim_token = gen_random_uuid(),
                        lease_expires_at = now()
                            + make_interval(secs => %s),
                        updated_at = now()
                    FROM candidate
                    WHERE job.requirement_id = candidate.requirement_id
                    RETURNING job.requirement_id, job.desired_state,
                              job.attempt_count, job.claim_token,
                              job.indexed_chunk_ids,
                              job.publication_fingerprint
                    """,
                    (lease_seconds,),
                )
                row = cursor.fetchone()
        return dict(row) if row is not None else None

    def renew_claim(
        self,
        requirement_id: UUID,
        claim_token: UUID,
        *,
        lease_seconds: int = 300,
    ) -> bool:
        with self._database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE xportra.regulatory_publication_index_jobs
                    SET lease_expires_at = now()
                            + make_interval(secs => %s),
                        updated_at = now()
                    WHERE requirement_id = %s
                      AND status = 'processing'
                      AND claim_token = %s
                    RETURNING requirement_id
                    """,
                    (lease_seconds, requirement_id, claim_token),
                )
                return cursor.fetchone() is not None

    def get_current_requirement(
        self, requirement_id: UUID
    ) -> dict[str, Any] | None:
        row = _fetch_one(
            self._database,
            _INDEXABLE_REQUIREMENT,
            (requirement_id,),
        )
        return dict(row) if row is not None else None

    def currently_eligible_requirement_ids(
        self, requirement_ids: set[UUID]
    ) -> dict[UUID, str]:
        if not requirement_ids:
            return {}
        rows = _fetch_all(
            self._database,
            f"""
            SELECT r.id, r.requirement_text, r.source_id,
                   r.normalized_document_id, r.source_location, r.position,
                   r.parser_version,
                   s.title AS source_title,
                   s.jurisdiction AS source_jurisdiction,
                   s.version AS source_version
            FROM xportra.regulatory_requirements AS r
            JOIN xportra.regulatory_sources AS s ON s.id = r.source_id
            WHERE r.id = ANY(%s) AND {_CURRENTLY_PUBLISHED}
            """,
            (list(requirement_ids),),
        )
        return {
            UUID(str(row["id"])): regulatory_publication_fingerprint(row)
            for row in rows
        }

    def complete_claim(
        self,
        requirement_id: UUID,
        claim_token: UUID,
        *,
        indexed_chunk_ids: list[UUID],
        publication_fingerprint: str | None,
    ) -> bool:
        with self._database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE xportra.regulatory_publication_index_jobs
                    SET status = CASE
                            WHEN desired_state = 'published'
                                 AND cardinality(%s::uuid[]) > 0
                                THEN 'indexed'
                            ELSE 'removed'
                        END,
                        indexed_chunk_ids = %s,
                        publication_fingerprint = %s,
                        claim_token = NULL,
                        lease_expires_at = NULL,
                        last_error = NULL,
                        updated_at = now()
                    WHERE requirement_id = %s
                      AND status = 'processing'
                      AND claim_token = %s
                    RETURNING requirement_id
                    """,
                    (
                        indexed_chunk_ids,
                        indexed_chunk_ids,
                        publication_fingerprint,
                        requirement_id,
                        claim_token,
                    ),
                )
                return cursor.fetchone() is not None

    def fail_claim(
        self,
        requirement_id: UUID,
        claim_token: UUID,
        *,
        failure_kind: str,
        retry_seconds: int,
        max_attempts: int = 5,
    ) -> bool:
        if not isinstance(failure_kind, str) or not failure_kind.isidentifier():
            raise ValueError("failure kind must be a safe identifier")
        with self._database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE xportra.regulatory_publication_index_jobs
                    SET status = CASE
                            WHEN attempt_count >= %s THEN 'failed'
                            ELSE 'retryable'
                        END,
                        next_attempt_at = now()
                            + make_interval(secs => %s),
                        claim_token = NULL,
                        lease_expires_at = NULL,
                        last_error = %s,
                        updated_at = now()
                    WHERE requirement_id = %s
                      AND status = 'processing'
                      AND claim_token = %s
                    RETURNING status
                    """,
                    (
                        max_attempts,
                        retry_seconds,
                        failure_kind,
                        requirement_id,
                        claim_token,
                    ),
                )
                return cursor.fetchone() is not None
