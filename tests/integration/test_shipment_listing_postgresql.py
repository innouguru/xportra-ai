"""Shipment listing/history PostgreSQL integration tests.

Gated on ``DATABASE_URL`` like every other
database-backed suite: applies migration 013 over the
provisioned base schema (001–012 assumed present, as
in ``test_workflow_record_postgresql.py``), writes one
bound and one draft shipment through the real
repositories, then drives the listing/detail reads
over HTTP — asserting tenant isolation, newest-first
ordering, pagination, draft representation, and
rollback removal.
"""

import os
import pathlib
import unittest
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.application.result_store import ComplianceResultStore
from xportra.persistence.database import Database, DatabaseSettings
from xportra.persistence.repositories import (
    ComplianceAnalysisReportRepository,
    ComplianceAnalysisRepository,
    ComplianceAnalysisTraceRepository,
    ComplianceWorkflowRepository,
    ComplianceWorkflowRoundRepository,
    FinalAssessmentPackageRepository,
    ShipmentRepository,
    TenantRepository,
)
from xportra.persistence.tenant import TenantContext

MIGRATIONS = (
    pathlib.Path(__file__).resolve().parents[2] / "migrations"
)
UP = MIGRATIONS / "013_shipments.sql"
DOWN = MIGRATIONS / "013_shipments.down.sql"

TENANT_A_SLUG = "shipment-listing-integration-a"
TENANT_B_SLUG = "shipment-listing-integration-b"
CASE_ID = UUID("30333333-3333-3333-3333-333333333333")
CASE_OTHER = UUID("30333333-3333-3333-3333-333333333334")
SHIPMENT_ID = UUID("30444444-4444-4444-4444-444444444444")
SHIPMENT_DRAFT = UUID("30444444-4444-4444-4444-444444444445")
WORKFLOW_ID = UUID("30555555-5555-5555-5555-555555555555")


def apply_migration(database, path):
    with database.connection() as connection:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(path.read_text(encoding="utf-8"))


def table_exists(database, table):
    with database.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT to_regclass(%s)", (f"xportra.{table}",))
            return cursor.fetchone()["to_regclass"] is not None


class ShipmentListingPostgreSQLTests(unittest.TestCase):
    database = None

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DATABASE_URL", "").strip():
            raise unittest.SkipTest("DATABASE_URL is not configured")

        cls.database = Database(DatabaseSettings.from_environment())
        apply_migration(cls.database, UP)
        if not table_exists(cls.database, "shipments"):
            raise unittest.SkipTest(
                "migration 013 table shipments was not created")

        tenants = TenantRepository(cls.database)
        tenant_a = tenants.create(
            "Shipment Listing Tenant A", TENANT_A_SLUG)
        tenant_b = tenants.create(
            "Shipment Listing Tenant B", TENANT_B_SLUG)
        cls.tenant_a = TenantContext(tenant_a["id"])
        cls.tenant_b = TenantContext(tenant_b["id"])
        shipments = ShipmentRepository(cls.database)
        workflows = ComplianceWorkflowRepository(cls.database)
        # Separate transactions so created_at ordering is
        # deterministic (one transaction shares a timestamp).
        with cls.database.transaction() as connection:
            shipments.create_in_transaction(
                connection, cls.tenant_a, SHIPMENT_DRAFT,
                CASE_OTHER, "Sesame seeds", "Nigeria", "Ghana",
                None, None, None, "draft")
        with cls.database.transaction() as connection:
            shipments.create_in_transaction(
                connection, cls.tenant_a, SHIPMENT_ID,
                CASE_ID, "Cocoa beans", "Nigeria",
                "Netherlands", "20", "tonnes", "2026-11-01",
                "bound")
            workflows.create_in_transaction(
                connection, cls.tenant_a, WORKFLOW_ID,
                CASE_ID, SHIPMENT_ID, "evidence_pending")
        cls.store = ComplianceResultStore(
            database=cls.database,
            reports=ComplianceAnalysisReportRepository(
                cls.database),
            analyses=ComplianceAnalysisRepository(cls.database),
            traces=ComplianceAnalysisTraceRepository(
                cls.database),
            rounds=ComplianceWorkflowRoundRepository(
                cls.database),
            packages=FinalAssessmentPackageRepository(
                cls.database),
            workflows=workflows,
            shipments=shipments,
        )
        cls.client = TestClient(create_app(services=SimpleNamespace(
            rag=None,
            result_store=cls.store,
        )))

    @classmethod
    def tearDownClass(cls):
        if cls.database is None:
            return
        try:
            apply_migration(cls.database, DOWN)
            if table_exists(cls.database, "shipments"):
                raise AssertionError(
                    "rollback left shipments behind")
        finally:
            with cls.database.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id FROM xportra.tenants
                        WHERE slug IN (%s, %s)
                        """,
                        (TENANT_A_SLUG, TENANT_B_SLUG),
                    )
                    ids = [row["id"] for row in cursor.fetchall()]
                    if ids:
                        cursor.execute(
                            "DELETE FROM xportra.tenants WHERE id = ANY(%s)",
                            (ids,),
                        )

    def headers(self, tenant_id):
        return {"X-Development-Tenant-ID": str(tenant_id)}

    def test_list_shows_both_shipments_newest_first(self):
        response = self.client.get(
            "/compliance/shipments",
            headers=self.headers(self.tenant_a.tenant_id))
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["total"], 2)
        self.assertEqual(
            [item["shipment_id"] for item in body["shipments"]],
            [str(SHIPMENT_ID), str(SHIPMENT_DRAFT)])
        bound = body["shipments"][0]
        self.assertEqual(bound["product"], "Cocoa beans")
        self.assertIsNotNone(bound["workflow"])
        self.assertEqual(
            bound["workflow"]["state"], "evidence_pending")
        self.assertFalse(bound["workflow"]["is_closed"])
        draft = body["shipments"][1]
        self.assertIsNone(draft["workflow"])
        self.assertEqual(draft["workflow_count"], 0)

    def test_list_is_tenant_scoped(self):
        response = self.client.get(
            "/compliance/shipments",
            headers=self.headers(self.tenant_b.tenant_id))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["total"], 0)

    def test_detail_and_cross_tenant(self):
        headers = self.headers(self.tenant_a.tenant_id)
        response = self.client.get(
            f"/compliance/shipments/{SHIPMENT_ID}",
            headers=headers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            response.json()["case_id"], str(CASE_ID))
        headers_b = self.headers(self.tenant_b.tenant_id)
        cross = self.client.get(
            f"/compliance/shipments/{SHIPMENT_ID}",
            headers=headers_b)
        self.assertEqual(cross.status_code, 404, cross.text)


if __name__ == "__main__":
    unittest.main()
