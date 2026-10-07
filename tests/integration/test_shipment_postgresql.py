"""Server-owned shipment PostgreSQL integration tests.

Gated on ``DATABASE_URL`` like every other
database-backed suite: applies migration 013 over the
provisioned base schema (001 assumed present for the
tenant foreign key), then drives the shipment boundary
over HTTP — first start persists shipment + workflow in
one transaction, retry converges, forged identities
fail closed — reading the ``shipments`` row fresh from
PostgreSQL. Rolls migration 013 back afterwards and
verifies removal.
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

TENANT_A_SLUG = "shipment-integration-a"
TENANT_B_SLUG = "shipment-integration-b"
CASE_ID = UUID("20333333-3333-3333-3333-333333333333")
CASE_OTHER = UUID("20333333-3333-3333-3333-333333333334")
SHIPMENT_ID = UUID("20444444-4444-4444-4444-444444444444")
UNKNOWN_SHIPMENT = UUID("20444444-4444-4444-4444-444444444445")

PROFILE = {
    "product": "Cocoa beans",
    "origin_country": "Nigeria",
    "destination_country": "Netherlands",
    "quantity": "20",
    "unit": "tonnes",
    "shipment_date": "2026-11-01",
}


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


class ShipmentPostgreSQLTests(unittest.TestCase):
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
            "Shipment Tenant A", TENANT_A_SLUG)
        tenant_b = tenants.create(
            "Shipment Tenant B", TENANT_B_SLUG)
        cls.tenant_a = TenantContext(tenant_a["id"])
        cls.tenant_b = TenantContext(tenant_b["id"])
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
            workflows=ComplianceWorkflowRepository(cls.database),
            shipments=ShipmentRepository(cls.database),
        )
        cls.shipments = ShipmentRepository(cls.database)
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

    def test_start_persists_shipment_and_workflow(self):
        headers = self.headers(self.tenant_a.tenant_id)
        response = self.client.post(
            "/compliance/workflows/start", headers=headers,
            json={"case_id": str(CASE_ID),
                  "shipment_id": str(SHIPMENT_ID),
                  "shipment": PROFILE})
        self.assertEqual(response.status_code, 201, response.text)
        record = response.json()["workflow"]
        self.assertEqual(record["shipment_id"], str(SHIPMENT_ID))
        row = self.shipments.get(self.tenant_a, SHIPMENT_ID)
        self.assertIsNotNone(row)
        self.assertEqual(row["case_id"], CASE_ID)
        self.assertEqual(row["product"], "Cocoa beans")
        self.assertEqual(row["status"], "bound")

    def test_retry_converges_and_forgery_fails_closed(self):
        headers = self.headers(self.tenant_a.tenant_id)
        first = self.client.post(
            "/compliance/workflows/start", headers=headers,
            json={"case_id": str(CASE_ID),
                  "shipment_id": str(SHIPMENT_ID),
                  "shipment": PROFILE})
        self.assertEqual(first.status_code, 201, first.text)
        second = self.client.post(
            "/compliance/workflows/start", headers=headers,
            json={"case_id": str(CASE_ID),
                  "shipment_id": str(SHIPMENT_ID),
                  "shipment": PROFILE})
        self.assertEqual(second.status_code, 201, second.text)
        self.assertEqual(first.json()["workflow"],
                         second.json()["workflow"])
        forged = self.client.post(
            "/compliance/workflows/start", headers=headers,
            json={"case_id": str(CASE_OTHER),
                  "shipment_id": str(UNKNOWN_SHIPMENT)})
        self.assertEqual(forged.status_code, 404, forged.text)
        headers_b = self.headers(self.tenant_b.tenant_id)
        cross = self.client.post(
            "/compliance/workflows/start", headers=headers_b,
            json={"case_id": str(CASE_ID),
                  "shipment_id": str(SHIPMENT_ID)})
        self.assertEqual(cross.status_code, 404, cross.text)


if __name__ == "__main__":
    unittest.main()
