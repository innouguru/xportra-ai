import os
import unittest
from datetime import datetime, timezone
from uuid import UUID

from psycopg import IntegrityError

from xportra.persistence.database import Database, DatabaseSettings
from xportra.persistence.errors import PersistenceIntegrityError
from xportra.persistence.repositories import (
    ComplianceEvidenceRepository,
    DestinationMarketRepository,
    EvidenceRequirementRepository,
    ExporterRepository,
    ProductRepository,
    RequirementApplicabilityRepository,
    RequirementRepository,
    TenantRepository,
    UserRepository,
    UserTenantMembershipRepository,
)
from xportra.persistence.tenant import TenantContext


class PostgreSQLPersistenceIntegrationTests(unittest.TestCase):
    database = None
    tenant_a = None
    tenant_b = None
    user_id = None
    exporter_a_id = None
    exporter_b_id = None
    product_a_id = None
    destination_a_id = None
    requirement_id = None
    evidence_id = None

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DATABASE_URL", "").strip():
            raise unittest.SkipTest("DATABASE_URL is not configured")

        cls.database = Database(DatabaseSettings.from_environment())
        cls._cleanup_test_data()

        tenant_repository = TenantRepository(cls.database)
        tenant_a = tenant_repository.create(
            "Phase 1.5 Tenant A", "phase-1-5-integration-a"
        )
        tenant_b = tenant_repository.create(
            "Phase 1.5 Tenant B", "phase-1-5-integration-b"
        )
        cls.tenant_a = TenantContext(tenant_a["id"])
        cls.tenant_b = TenantContext(tenant_b["id"])

        user = UserRepository(cls.database).create(
            "Phase 1.5 User", "phase-1-5-integration@example.invalid", "active"
        )
        cls.user_id = user["id"]
        membership_repository = UserTenantMembershipRepository(cls.database)
        membership_repository.add(cls.tenant_a, cls.user_id, "test")
        membership_repository.add(cls.tenant_b, cls.user_id, "test")

        exporter_repository = ExporterRepository(cls.database)
        exporter_a = exporter_repository.create(
            cls.tenant_a, "Phase 1.5 Exporter A", registration_number="P15-A"
        )
        exporter_b = exporter_repository.create(
            cls.tenant_b, "Phase 1.5 Exporter B", registration_number="P15-B"
        )
        cls.exporter_a_id = exporter_a["id"]
        cls.exporter_b_id = exporter_b["id"]

        product = ProductRepository(cls.database).create(
            cls.tenant_a, cls.exporter_a_id, "Phase 1.5 Product A"
        )
        cls.product_a_id = product["id"]
        destination = DestinationMarketRepository(cls.database).create(
            cls.tenant_a, "P15", "Phase 1.5 Market"
        )
        cls.destination_a_id = destination["id"]

        requirement = RequirementRepository(cls.database).create(
            None,
            "P15-REQ",
            "Phase 1.5 Requirement",
            "Requirement used only by integration tests",
            status="active",
        )
        cls.requirement_id = requirement["id"]

        evidence = ComplianceEvidenceRepository(cls.database).create(
            cls.tenant_a,
            "Phase 1.5 Evidence",
            "test",
            "test://phase-1-5/evidence",
        )
        cls.evidence_id = evidence["id"]

    @classmethod
    def tearDownClass(cls):
        cls._cleanup_test_data()

    @classmethod
    def _cleanup_test_data(cls):
        if cls.database is None:
            if not os.environ.get("DATABASE_URL", "").strip():
                return
            cls.database = Database(DatabaseSettings.from_environment())

        with cls.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id FROM xportra.tenants
                    WHERE slug IN (%s, %s)
                    """,
                    ("phase-1-5-integration-a", "phase-1-5-integration-b"),
                )
                tenant_ids = [row["id"] for row in cursor.fetchall()]
                if tenant_ids:
                    cursor.execute(
                        """
                        DELETE FROM xportra.requirement_applicability
                        WHERE tenant_id = ANY(%s)
                        """,
                        (tenant_ids,),
                    )
                    cursor.execute(
                        """
                        DELETE FROM xportra.compliance_evidence
                        WHERE tenant_id = ANY(%s)
                        """,
                        (tenant_ids,),
                    )
                    cursor.execute(
                        """
                        DELETE FROM xportra.products
                        WHERE tenant_id = ANY(%s)
                        """,
                        (tenant_ids,),
                    )
                    cursor.execute(
                        """
                        DELETE FROM xportra.exporters
                        WHERE tenant_id = ANY(%s)
                        """,
                        (tenant_ids,),
                    )
                    cursor.execute(
                        """
                        DELETE FROM xportra.destination_markets
                        WHERE tenant_id = ANY(%s)
                        """,
                        (tenant_ids,),
                    )
                    cursor.execute(
                        """
                        DELETE FROM xportra.user_tenant_memberships
                        WHERE tenant_id = ANY(%s)
                        """,
                        (tenant_ids,),
                    )
                    cursor.execute(
                        """
                        DELETE FROM xportra.tenants
                        WHERE id = ANY(%s)
                        """,
                        (tenant_ids,),
                    )
                cursor.execute(
                    """
                    DELETE FROM xportra.requirements
                    WHERE requirement_code = 'P15-REQ'
                    """
                )
                cursor.execute(
                    """
                    DELETE FROM xportra.users
                    WHERE email = 'phase-1-5-integration@example.invalid'
                    """
                )

    def assert_integrity_failure(self, operation):
        with self.assertRaises(PersistenceIntegrityError) as raised:
            operation()
        self.assertIsInstance(raised.exception.__cause__, IntegrityError)

    def test_tenant_scoped_create_retrieve_and_filtering(self):
        exporter_repository = ExporterRepository(self.database)

        own_a = exporter_repository.get(self.tenant_a, self.exporter_a_id)
        own_b = exporter_repository.get(self.tenant_b, self.exporter_b_id)
        hidden_b = exporter_repository.get(self.tenant_a, self.exporter_b_id)

        self.assertEqual(own_a["tenant_id"], self.tenant_a.tenant_id)
        self.assertEqual(own_b["tenant_id"], self.tenant_b.tenant_id)
        self.assertIsNone(hidden_b)

        with self.assertRaises(TypeError):
            ProductRepository(self.database).get(self.product_a_id)

    def test_cross_tenant_relationship_is_rejected_by_repository_and_database(self):
        self.assert_integrity_failure(
            lambda: ProductRepository(self.database).create(
                self.tenant_a, self.exporter_b_id, "Cross Tenant Product"
            )
        )

    def test_valid_associations_and_invalid_references(self):
        applicability = RequirementApplicabilityRepository(self.database).create(
            self.tenant_a,
            self.requirement_id,
            self.exporter_a_id,
            self.product_a_id,
            self.destination_a_id,
            "required",
            datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(
            RequirementApplicabilityRepository(self.database)
            .get(self.tenant_a, applicability["id"])["tenant_id"],
            self.tenant_a.tenant_id,
        )

        evidence_link = EvidenceRequirementRepository(self.database).link(
            self.tenant_a, self.evidence_id, self.requirement_id
        )
        self.assertEqual(evidence_link["evidence_id"], self.evidence_id)
        self.assertEqual(
            len(
                EvidenceRequirementRepository(self.database).list_for_evidence(
                    self.tenant_a, self.evidence_id
                )
            ),
            1,
        )

        self.assert_integrity_failure(
            lambda: ProductRepository(self.database).create(
                self.tenant_a,
                UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
                "Invalid Parent Product",
            )
        )

    def test_repository_constraint_errors_preserve_integrity_cause(self):
        exporter_repository = ExporterRepository(self.database)
        self.assert_integrity_failure(
            lambda: exporter_repository.create(
                self.tenant_a,
                "Duplicate Registration",
                registration_number="P15-A",
            )
        )
        self.assert_integrity_failure(
            lambda: exporter_repository.create(
                self.tenant_a,
                None,
                registration_number="P15-NULL-NAME",
            )
        )
        self.assert_integrity_failure(
            lambda: exporter_repository.create(
                self.tenant_a,
                "Invalid Status",
                registration_number="P15-INVALID-STATUS",
                status="invalid",
            )
        )
        self.assert_integrity_failure(
            lambda: RequirementApplicabilityRepository(self.database).create(
                self.tenant_a,
                self.requirement_id,
                self.exporter_a_id,
                self.product_a_id,
                self.destination_a_id,
                "required",
                datetime(2026, 1, 2, tzinfo=timezone.utc),
                effective_to=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        )

    def test_transaction_commit_rollback_cleanup_and_reuse(self):
        committed_slug = "phase-1-5-transaction-commit"
        rolled_back_slug = "phase-1-5-transaction-rollback"
        try:
            with self.database.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO xportra.tenants (legal_name, slug, status)
                        VALUES (%s, %s, %s)
                        """,
                        ("Committed Transaction", committed_slug, "active"),
                    )
            self.assertIsNotNone(
                TenantRepository(self.database).get(
                    TenantRepository(self.database).create(
                        "Reusable Transaction", "phase-1-5-transaction-reuse"
                    )["id"]
                )
            )

            with self.assertRaises(IntegrityError):
                with self.database.transaction() as connection:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            """
                            INSERT INTO xportra.tenants (legal_name, slug, status)
                            VALUES (%s, %s, %s)
                            """,
                            ("Rolled Back Transaction", rolled_back_slug, "active"),
                        )
                        cursor.execute(
                            """
                            INSERT INTO xportra.exporters
                                (tenant_id, legal_name, status)
                            VALUES (%s, %s, %s)
                            """,
                            (self.tenant_a.tenant_id, "Invalid Transaction Exporter", "invalid"),
                        )

            with self.database.connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT id FROM xportra.tenants WHERE slug = %s",
                        (rolled_back_slug,),
                    )
                    self.assertIsNone(cursor.fetchone())
                    self.assertFalse(connection.closed)
        finally:
            with self.database.transaction() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM xportra.tenants WHERE slug IN (%s, %s, %s)",
                        (committed_slug, rolled_back_slug, "phase-1-5-transaction-reuse"),
                    )

    def test_connection_closes_and_subsequent_operation_works(self):
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 AS result")
                self.assertEqual(cursor.fetchone()["result"], 1)
            self.assertFalse(connection.closed)
        self.assertTrue(connection.closed)

        self.assertIsNotNone(
            TenantRepository(self.database).get(self.tenant_a.tenant_id)
        )


if __name__ == "__main__":
    unittest.main()
