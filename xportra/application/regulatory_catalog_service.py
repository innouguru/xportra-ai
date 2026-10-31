"""Exporter-facing regulatory catalog service.

Selects published regulatory requirements that are applicable to an
authenticated organization's export scope, reusing the existing
durable applicability decisions stored in
``xportra.regulatory_requirement_applicability``.

Catalog rules (all must hold; fail-closed on missing/inconsistent state):
- Requirement status == 'published' (deliberately published by staff).
- Stage A verification == 'verified' and Stage B approval == 'approved'
  (implied by publication, but re-checked as defense in depth).
- Source is active (not superseded/withdrawn/archived).
- No pending review flags on the requirement or its source.
- A durable applicability record exists for the tenant + requirement
  (+ context fingerprint when a scope is requested) with outcome ==
  'applicable' and status == 'evaluated'.
- Unknown, missing, incomplete, or inconsistent applicability is excluded
  (never inferred as eligible).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from xportra.application.errors import ApplicationValidationError
from xportra.persistence.database import Database
from xportra.persistence.repositories import _fetch_all, _fetch_one
from xportra.persistence.tenant import TenantContext

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


class RegulatoryCatalogService:
    """Read-only catalog over published, applicable requirements for a tenant."""

    def __init__(self, database: Database) -> None:
        self._database = database

    # ---------------------------------------------------------------- queries

    def list_catalog_requirements(
        self,
        tenant: TenantContext,
        *,
        product: str | None = None,
        origin_country: str | None = None,
        destination_country: str | None = None,
        limit: int = DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Return published requirements applicable to the tenant's scope.

        Builds an applicability context from the supplied scope parameters,
        computes the deterministic context fingerprint, and queries the
        persisted applicability decisions for matching requirements.

        Scope parameters are optional. When omitted, the catalog returns all
        published requirements that have an applicable applicability record
        for this tenant under any evaluated scope (one row per requirement).
        When provided, only requirements applicable to the requested scope
        are returned.

        Unknown, missing, or unresolved applicability is never returned as
        applicable.
        """
        if limit < 1 or limit > MAX_PAGE_SIZE:
            raise ApplicationValidationError(
                f"limit must be between 1 and {MAX_PAGE_SIZE}"
            )
        if offset < 0:
            raise ApplicationValidationError("offset must be non-negative")

        fingerprint = self._context_fingerprint(
            tenant.tenant_id, product, origin_country, destination_country
        )

        rows = self._fetch_catalog_rows(
            tenant.tenant_id,
            fingerprint,
            limit=limit,
            offset=offset,
        )

        total = self._count_catalog_rows(tenant.tenant_id, fingerprint)

        items = [
            {
                "requirement_id": row["id"],
                "requirement_text": row["requirement_text"],
                "requirement_type": row.get("requirement_type", "unknown"),
                "stage_a_status": row.get("stage_a_status", "pending"),
                "stage_b_status": row.get("stage_b_status", "pending"),
                "stage_b_pilot_scope": row.get("stage_b_pilot_scope"),
                "published_at": row.get("published_at"),
                "source": {
                    "source_id": row.get("source_id"),
                    "source_title": row.get("source_title"),
                    "source_jurisdiction": row.get("source_jurisdiction"),
                    "source_version": row.get("source_version"),
                    "source_status": row.get("source_status"),
                },
                "citation": {
                    "normalized_document_id": row.get("normalized_document_id"),
                    "source_location": row.get("source_location"),
                    "position": row.get("position"),
                    "parser_version": row.get("parser_version"),
                },
                "applicability": {
                    "outcome": row["applicability_outcome"],
                    "reason": row["applicability_reason"],
                    "context_fingerprint": row["applicability_context_fingerprint"],
                },
            }
            for row in rows
        ]

        return {
            "items": items,
            "limit": limit,
            "offset": offset,
            "total": total,
        }

    # ---------------------------------------------------------------- internals

    def _context_fingerprint(
        self,
        tenant_id: UUID,
        product: str | None,
        origin_country: str | None,
        destination_country: str | None,
    ) -> str | None:
        """Compute the deterministic fingerprint for the requested scope.

        Returns ``None`` when no scope parameters are supplied, indicating
        that any evaluated scope should be matched.
        """
        if product is None and origin_country is None and destination_country is None:
            return None

        from xportra.domain.ingestion import ApplicabilityContext, context_fingerprint

        context = ApplicabilityContext(
            tenant_id=tenant_id,
            origin_country=origin_country,
            destination_country=destination_country,
            commodity=product,
            actor_role="exporter",
        )
        return context_fingerprint(context)

    def _applicability_subquery(
        self,
        tenant_id: UUID,
        fingerprint: str | None,
    ) -> tuple[str, list[Any]]:
        """Build the distinct applicability decision subquery.

        One row per requirement: the most recent ``applicable`` evaluated
        decision, restricted to the requested fingerprint when one is
        supplied. The per-fingerprint UNIQUE constraint guarantees a
        single matching row in that case; without a scope, a requirement
        applicable under several scopes must still appear exactly once.
        """
        params: list[Any] = [str(tenant_id)]
        fingerprint_filter = ""
        if fingerprint is not None:
            params.append(fingerprint)
            fingerprint_filter = "\n              AND context_fingerprint = %s"
        sql = f"""
            SELECT DISTINCT ON (requirement_id) requirement_id,
                   outcome, reason, context_fingerprint
            FROM xportra.regulatory_requirement_applicability
            WHERE tenant_id = %s
              AND outcome = 'applicable'
              AND status = 'evaluated'{fingerprint_filter}
            ORDER BY requirement_id, created_at DESC, id DESC
        """
        return sql, params

    def _fetch_catalog_rows(
        self,
        tenant_id: UUID,
        fingerprint: str | None,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        """Execute the catalog query with all governance filters."""
        applicability_sql, params = self._applicability_subquery(
            tenant_id, fingerprint
        )
        params.extend([limit, offset])
        sql = f"""
            SELECT r.id, r.requirement_text, r.requirement_type,
                   r.stage_a_status, r.stage_b_status, r.stage_b_pilot_scope,
                   r.published_at, r.source_id, r.normalized_document_id,
                   r.source_location, r.position, r.parser_version,
                   s.title AS source_title, s.jurisdiction AS source_jurisdiction,
                   s.version AS source_version, s.status AS source_status,
                   a.outcome AS applicability_outcome,
                   a.reason AS applicability_reason,
                   a.context_fingerprint AS applicability_context_fingerprint
            FROM ({applicability_sql}
            ) AS a
            JOIN xportra.regulatory_requirements AS r
              ON r.id = a.requirement_id
            LEFT JOIN xportra.regulatory_sources AS s
              ON s.id = r.source_id
            WHERE r.status = 'published'
              AND r.stage_a_status = 'verified'
              AND r.stage_b_status = 'approved'
              AND s.status = 'active'
              AND NOT EXISTS (
                  SELECT 1
                  FROM xportra.regulatory_review_flags AS f
                  WHERE f.status = 'pending_review'
                    AND (
                        f.requirement_id = r.id
                        OR (r.source_id IS NOT NULL
                            AND f.trigger_source_id = r.source_id)
                    )
              )
            ORDER BY r.created_at ASC, r.id ASC
            LIMIT %s OFFSET %s
        """
        rows = _fetch_all(self._database, sql, tuple(params))
        return [dict(row) for row in rows]

    def _count_catalog_rows(
        self,
        tenant_id: UUID,
        fingerprint: str | None,
    ) -> int:
        """Count total matching catalog rows for pagination."""
        applicability_sql, params = self._applicability_subquery(
            tenant_id, fingerprint
        )
        sql = f"""
            SELECT COUNT(*) AS cnt
            FROM ({applicability_sql}
            ) AS a
            JOIN xportra.regulatory_requirements AS r
              ON r.id = a.requirement_id
            LEFT JOIN xportra.regulatory_sources AS s
              ON s.id = r.source_id
            WHERE r.status = 'published'
              AND r.stage_a_status = 'verified'
              AND r.stage_b_status = 'approved'
              AND s.status = 'active'
              AND NOT EXISTS (
                  SELECT 1
                  FROM xportra.regulatory_review_flags AS f
                  WHERE f.status = 'pending_review'
                    AND (
                        f.requirement_id = r.id
                        OR (r.source_id IS NOT NULL
                            AND f.trigger_source_id = r.source_id)
                    )
              )
        """
        row = _fetch_one(self._database, sql, tuple(params))
        return int(row["cnt"]) if row else 0
