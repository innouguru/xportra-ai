"""Catalog service and endpoint unit tests (Phase 4D.10 Task 7).

Verifies the exporter-facing regulatory catalog contract:

- The service re-checks every governance precondition in the query
  itself (published status, Stage A verified, Stage B approved, active
  source, no pending review flags) — a regression for the original
  conditions-slice defect that silently dropped the published filter.
- Applicability decisions resolve from the durable
  ``xportra.regulatory_requirement_applicability`` records only: one
  row per requirement without a scope (DISTINCT applicability choice),
  fingerprint-restricted with a scope.
- Validation bounds (limit/offset) fail closed without touching the
  database.
- The endpoint resolves tenant identity from server-side membership
  (never the request), fails closed without authorization, and
  returns the serialized CatalogRequirementsResponse contract. No live
  database is contacted.
"""

from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from unittest import TestCase
from uuid import UUID

from fastapi.testclient import TestClient

import xportra.api.catalog as catalog_module
from xportra.api.app import create_app
from xportra.api.auth import MemberContext
from xportra.api.errors import PermissionDeniedError
from xportra.application.errors import ApplicationValidationError
from xportra.application.regulatory_catalog_service import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    RegulatoryCatalogService,
)
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-0000-0000-0000-000000000001")
REQUIREMENT_ID = UUID("22222222-0000-0000-0000-000000000002")
SOURCE_ID = UUID("33333333-0000-0000-0000-000000000003")
FINGERPRINT = "fp-abc-123"

MEMBER_CONTEXT = MemberContext(
    tenant=TenantContext(TENANT_ID),
    role="member",
)


CATALOG_ROW = {
    "id": REQUIREMENT_ID,
    "requirement_text": "All cocoa exports require a phytosanitary certificate.",
    "requirement_type": "documentation",
    "stage_a_status": "verified",
    "stage_b_status": "approved",
    "stage_b_pilot_scope": "cocoa EU pilot",
    "published_at": "2026-10-30T00:00:00+00:00",
    "source_id": SOURCE_ID,
    "normalized_document_id": None,
    "source_location": {"page": 2},
    "position": 1,
    "parser_version": "v1",
    "source_title": "Regulation (EU) 2019/1793",
    "source_jurisdiction": "EU",
    "source_version": "1.0",
    "source_status": "active",
    "applicability_outcome": "applicable",
    "applicability_reason": "Matches exporter scope.",
    "applicability_context_fingerprint": FINGERPRINT,
}


class FakeCursor:
    def __init__(self, store):
        self._store = store

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, parameters=None):
        self._store["statements"].append(statement)
        self._store["params"].append(tuple(parameters or ()))
        self._store["last"] = statement

    def fetchone(self):
        if "COUNT(*)" in self._store["last"]:
            return {"cnt": self._store["count_value"]}
        return self._store["one_value"]

    def fetchall(self):
        if "COUNT(*)" in self._store["last"]:
            return [{"cnt": self._store["count_value"]}]
        return list(self._store["rows"])


class FakeConnection:
    """Connection boundary: only ``cursor()`` is required by repositories."""

    def __init__(self, store):
        self._store = store

    def cursor(self):
        return FakeCursor(self._store)


class FakeDatabase:
    """Records executed SQL; satisfies the Database.connection boundary."""

    def __init__(self, rows=None, count_value=0, one_value=None):
        self.store = {
            "statements": [],
            "params": [],
            "last": "",
            "rows": rows or [],
            "count_value": count_value,
            "one_value": one_value,
        }

    @contextmanager
    def connection(self):
        yield FakeConnection(self.store)

    def transaction(self):
        return self.connection()


class RowRecordingService:
    """Captures the tenant/scope forwarded by the route handler."""

    def __init__(self, result):
        self.result = result
        self.calls = []

    def list_catalog_requirements(self, tenant, **kwargs):
        self.calls.append({"tenant": tenant, **kwargs})
        return self.result


def catalog_result():
    return {
        "items": [
            {
                "requirement_id": REQUIREMENT_ID,
                "requirement_text": CATALOG_ROW["requirement_text"],
                "requirement_type": "documentation",
                "stage_a_status": "verified",
                "stage_b_status": "approved",
                "stage_b_pilot_scope": "cocoa EU pilot",
                "published_at": CATALOG_ROW["published_at"],
                "source": {
                    "source_id": SOURCE_ID,
                    "source_title": "Regulation (EU) 2019/1793",
                    "source_jurisdiction": "EU",
                    "source_version": "1.0",
                    "source_status": "active",
                },
                "citation": {
                    "normalized_document_id": None,
                    "source_location": {"page": 2},
                    "position": 1,
                    "parser_version": "v1",
                },
                "applicability": {
                    "outcome": "applicable",
                    "reason": "Matches exporter scope.",
                    "context_fingerprint": FINGERPRINT,
                },
            }
        ],
        "limit": DEFAULT_PAGE_SIZE,
        "offset": 0,
        "total": 1,
    }


class CatalogServiceTests(TestCase):
    def test_maps_rows_and_total_as_recorded(self):
        database = FakeDatabase(
            rows=[dict(CATALOG_ROW)], count_value=1
        )
        result = RegulatoryCatalogService(database).list_catalog_requirements(
            TenantContext(TENANT_ID)
        )
        self.assertEqual(1, len(result["items"]))
        item = result["items"][0]
        self.assertEqual(REQUIREMENT_ID, item["requirement_id"])
        self.assertEqual(
            CATALOG_ROW["applicability_context_fingerprint"],
            item["applicability"]["context_fingerprint"],
        )
        self.assertEqual("applicable", item["applicability"]["outcome"])
        self.assertEqual("active", item["source"]["source_status"])
        self.assertEqual(DEFAULT_PAGE_SIZE, result["limit"])
        self.assertEqual(1, result["total"])

    def test_query_rechecks_every_governance_filter(self):
        database = FakeDatabase(rows=[dict(CATALOG_ROW)], count_value=1)
        RegulatoryCatalogService(database).list_catalog_requirements(
            TenantContext(TENANT_ID)
        )
        statements = [
            statement
            for statement in database.store["statements"]
            if "FROM" in statement
        ]
        self.assertEqual(2, len(statements))
        for statement in statements:
            # The published filter must actually reach the database:
            # a regression of the conditions-slice defect that dropped it.
            self.assertIn("r.status = 'published'", statement)
            self.assertIn("r.stage_a_status = 'verified'", statement)
            self.assertIn("r.stage_b_status = 'approved'", statement)
            self.assertIn("s.status = 'active'", statement)
            self.assertIn("NOT EXISTS", statement)
            self.assertIn("xportra.regulatory_review_flags", statement)
            self.assertIn("pending_review", statement)

    def test_no_scope_selects_one_row_per_requirement(self):
        database = FakeDatabase(rows=[], count_value=0)
        RegulatoryCatalogService(database).list_catalog_requirements(
            TenantContext(TENANT_ID)
        )
        rows_statement = [
            statement
            for statement in database.store["statements"]
            if "COUNT(*)" not in statement
        ][0]
        self.assertIn("DISTINCT ON (requirement_id)", rows_statement)
        self.assertIn("outcome = 'applicable'", rows_statement)
        self.assertIn("status = 'evaluated'", rows_statement)
        rows_params = database.store["params"][0]
        self.assertEqual(str(TENANT_ID), rows_params[0])
        self.assertEqual(3, len(rows_params))
        self.assertEqual(DEFAULT_PAGE_SIZE, rows_params[-2])
        self.assertEqual(0, rows_params[-1])

    def test_scope_restricts_to_the_requested_fingerprint(self):
        database = FakeDatabase(rows=[], count_value=0)
        RegulatoryCatalogService(database).list_catalog_requirements(
            TenantContext(TENANT_ID),
            product="cocoa",
            origin_country="NG",
            destination_country="NL",
        )
        rows_statement = [
            statement
            for statement in database.store["statements"]
            if "COUNT(*)" not in statement
        ][0]
        self.assertIn("AND context_fingerprint = %s", rows_statement)
        rows_params = database.store["params"][0]
        self.assertEqual(str(TENANT_ID), rows_params[0])
        self.assertEqual(4, len(rows_params))
        # The bound fingerprint is the deterministic scope fingerprint.
        from xportra.domain.ingestion import ApplicabilityContext, context_fingerprint

        expected = context_fingerprint(
            ApplicabilityContext(
                tenant_id=TENANT_ID,
                origin_country="NG",
                destination_country="NL",
                commodity="cocoa",
                actor_role="exporter",
            )
        )
        self.assertEqual(expected, rows_params[1])
        self.assertEqual(DEFAULT_PAGE_SIZE, rows_params[-2])
        self.assertEqual(0, rows_params[-1])

    def test_limit_and_offset_bounds_fail_closed(self):
        database = FakeDatabase(rows=[], count_value=0)
        service = RegulatoryCatalogService(database)
        with self.assertRaises(ApplicationValidationError):
            service.list_catalog_requirements(
                TenantContext(TENANT_ID),
                limit=0,
            )
        with self.assertRaises(ApplicationValidationError):
            service.list_catalog_requirements(
                TenantContext(TENANT_ID),
                limit=MAX_PAGE_SIZE + 1,
            )
        with self.assertRaises(ApplicationValidationError):
            service.list_catalog_requirements(
                TenantContext(TENANT_ID),
                offset=-1,
            )
        self.assertEqual([], database.store["statements"])


def catalog_member_dependency():
    """The exact ``Depends`` callable used by the route annotation.

    ``require_permission`` builds a fresh callable per argument, so the
    dependency-override key must be the same instance.
    """
    depends = catalog_module.list_catalog_requirements.__annotations__[
        "member"
    ].__metadata__[0]
    return depends.dependency


def build_app(member_override=None, recent_service=None, services=None):
    app = create_app(
        services=services
        if services is not None
        else SimpleNamespace(database=FakeDatabase())
    )
    app.dependency_overrides[catalog_module._catalog_service] = (
        lambda: (recent_service if recent_service is not None else SimpleNamespace())
    )
    if member_override is not None:
        app.dependency_overrides[catalog_member_dependency()] = member_override
    return app


class CatalogEndpointTests(TestCase):
    def test_returns_serialized_catalog_for_authorized_member(self):
        service = RowRecordingService(catalog_result())
        app = build_app(member_override=lambda: MEMBER_CONTEXT, recent_service=service)
        with TestClient(app) as client:
            response = client.get(
                "/catalog/requirements",
                params={"origin_country": "NG", "destination_country": "NL"},
            )
        self.assertEqual(200, response.status_code)
        body = response.json()
        self.assertEqual(1, body["total"])
        self.assertEqual(DEFAULT_PAGE_SIZE, body["limit"])
        item = body["items"][0]
        self.assertEqual(str(REQUIREMENT_ID), item["requirement_id"])
        self.assertEqual(
            "applicable", item["applicability"]["outcome"]
        )
        self.assertEqual("cocoa EU pilot", item["stage_b_pilot_scope"])
        # Tenant identity is forwarded from server-side membership only.
        self.assertEqual(
            TENANT_ID, service.calls[0]["tenant"].tenant_id
        )
        self.assertEqual(
            {
                "product": None,
                "origin_country": "NG",
                "destination_country": "NL",
                "limit": DEFAULT_PAGE_SIZE,
                "offset": 0,
            },
            { k: v for k, v in service.calls[0].items() if k != "tenant" },
        )

    def test_denies_access_without_read_tenant_resource_permission(self):
        app = build_app(
            member_override=lambda: (_ for _ in ()).throw(PermissionDeniedError()),
        )
        with TestClient(app) as client:
            response = client.get("/catalog/requirements")
        self.assertEqual(403, response.status_code)
        self.assertEqual(
            "permission_denied", response.json()["error"]["code"]
        )

    def test_fails_closed_when_application_services_are_uninitialized(self):
        app = create_app(services=SimpleNamespace())
        with TestClient(app) as client:
            response = client.get("/catalog/requirements")
        self.assertEqual(503, response.status_code)
        self.assertEqual(
            "application_not_ready", response.json()["error"]["code"]
        )
