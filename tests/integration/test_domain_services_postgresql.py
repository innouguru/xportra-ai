import os
import unittest
from datetime import date, datetime, timezone
from uuid import UUID

from psycopg.errors import IntegrityError

from xportra.domain.errors import (
    DomainNotFoundError,
    DomainPersistenceError,
    DomainValidationError,
)
from xportra.domain.services import (
    CertificationService,
    ComplianceEvidenceService,
    DestinationMarketService,
    ExporterService,
    ProductService,
    RequirementApplicabilityService,
)
from xportra.persistence.database import Database, DatabaseSettings
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
    TenantRepository,
)
from xportra.persistence.tenant import TenantContext


class DomainServicePostgreSQLIntegrationTests(unittest.TestCase):
    database = None
    tenant_a = None
    tenant_b = None
    exporter_a = None
    exporter_b = None
    product_a = None
    destination_a = None
    requirement_global = None
    requirement_tenant_b = None
    evidence_a = None
    authority_id = UUID("00000000-0000-0000-0000-000000000001")

    @classmethod
    def setUpClass(cls):
        if not os.environ.get("DATABASE_URL", "").strip():
            raise unittest.SkipTest("DATABASE_URL is not configured")
        cls.database = Database(DatabaseSettings.from_environment())
        cls._cleanup()

        tenant_repository = TenantRepository(cls.database)
        tenant_a = tenant_repository.create("Phase 1.7 Tenant A", "phase-1-7-a")
        tenant_b = tenant_repository.create("Phase 1.7 Tenant B", "phase-1-7-b")
        cls.tenant_a = TenantContext(tenant_a["id"])
        cls.tenant_b = TenantContext(tenant_b["id"])

        exporter_repository = ExporterService(ExporterRepository(cls.database))
        cls.exporter_a = exporter_repository.create(
            cls.tenant_a, "Phase 1.7 Exporter A", registration_number="P17-A"
        )
        cls.exporter_b = exporter_repository.create(
            cls.tenant_b, "Phase 1.7 Exporter B", registration_number="P17-B"
        )

        cls.product_a = ProductService(
            ExporterRepository(cls.database), ProductRepository(cls.database)
        ).create(cls.tenant_a, cls.exporter_a["id"], "Phase 1.7 Product A")
        cls.destination_a = DestinationMarketService(
            DestinationMarketRepository(cls.database)
        ).register(cls.tenant_a, "P17", "Phase 1.7 Market")

        requirement_repository = RequirementRepository(cls.database)
        cls.requirement_global = requirement_repository.create(
            None, "P17-GLOBAL", "Phase 1.7 Global Requirement", "Integration test requirement", status="active"
        )
        cls.requirement_tenant_b = requirement_repository.create(
            cls.tenant_b, "P17-TENANT-B", "Phase 1.7 Tenant B Requirement", "Integration test requirement", status="active"
        )
        cls.evidence_a = ComplianceEvidenceService(
            cls.database,
            ComplianceEvidenceRepository(cls.database),
            EvidenceRequirementRepository(cls.database),
            requirement_repository,
        ).record(cls.tenant_a, "Phase 1.7 Evidence", "test", "test://phase-1-7/evidence")

    @classmethod
    def tearDownClass(cls):
        cls._cleanup()

    @classmethod
    def _cleanup(cls):
        if cls.database is None:
            if not os.environ.get("DATABASE_URL", "").strip():
                return
            cls.database = Database(DatabaseSettings.from_environment())
        with cls.database.transaction() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT id FROM xportra.tenants WHERE slug IN (%s, %s)",
                    ("phase-1-7-a", "phase-1-7-b"),
                )
                tenant_ids = [row["id"] for row in cursor.fetchall()]
                if tenant_ids:
                    cursor.execute("DELETE FROM xportra.requirement_applicability WHERE tenant_id = ANY(%s)", (tenant_ids,))
                    cursor.execute("DELETE FROM xportra.compliance_evidence WHERE tenant_id = ANY(%s)", (tenant_ids,))
                    cursor.execute("DELETE FROM xportra.certification_permit_licenses WHERE tenant_id = ANY(%s)", (tenant_ids,))
                    cursor.execute("DELETE FROM xportra.products WHERE tenant_id = ANY(%s)", (tenant_ids,))
                    cursor.execute("DELETE FROM xportra.exporters WHERE tenant_id = ANY(%s)", (tenant_ids,))
                    cursor.execute("DELETE FROM xportra.destination_markets WHERE tenant_id = ANY(%s)", (tenant_ids,))
                    cursor.execute("DELETE FROM xportra.requirements WHERE tenant_id = ANY(%s)", (tenant_ids,))
                    cursor.execute("DELETE FROM xportra.tenants WHERE id = ANY(%s)", (tenant_ids,))
                cursor.execute("DELETE FROM xportra.requirements WHERE requirement_code IN (%s, %s)", ("P17-GLOBAL", "P17-TENANT-B"))

    def setUp(self):
        self.exporter_service = ExporterService(ExporterRepository(self.database))
        self.product_service = ProductService(
            ExporterRepository(self.database), ProductRepository(self.database)
        )
        self.applicability_service = RequirementApplicabilityService(
            ExporterRepository(self.database),
            ProductRepository(self.database),
            DestinationMarketRepository(self.database),
            RequirementRepository(self.database),
            RequirementApplicabilityRepository(self.database),
        )
        self.evidence_service = ComplianceEvidenceService(
            self.database,
            ComplianceEvidenceRepository(self.database),
            EvidenceRequirementRepository(self.database),
            RequirementRepository(self.database),
        )
        self.certification_service = CertificationService(
            ExporterRepository(self.database),
            AuthorityRepository(self.database),
            CertificationPermitLicenseRepository(self.database),
        )

    def assert_domain_persistence_failure(self, operation):
        with self.assertRaises(DomainPersistenceError) as raised:
            operation()
        self.assertIsInstance(raised.exception.__cause__, Exception)
        self.assertIsInstance(raised.exception.cause.cause, IntegrityError)

    def test_tenant_context_and_tenant_scoping(self):
        self.assertEqual(
            self.exporter_service.get(self.tenant_a, self.exporter_a["id"])["id"],
            self.exporter_a["id"],
        )
        self.assertIsNone(self.exporter_service.get(self.tenant_a, self.exporter_b["id"]))
        with self.assertRaises(DomainValidationError):
            self.exporter_service.create(None, "No Tenant")

    def test_cross_tenant_product_relationship_is_rejected(self):
        with self.assertRaises(DomainNotFoundError):
            self.product_service.create(self.tenant_a, self.exporter_b["id"], "Invalid Product")

    def test_applicability_rules_and_tenant_requirement_visibility(self):
        applicability = self.applicability_service.record(
            self.tenant_a,
            self.requirement_global["id"],
            self.exporter_a["id"],
            self.product_a["id"],
            self.destination_a["id"],
            "required",
            datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        self.assertEqual(applicability["tenant_id"], self.tenant_a.tenant_id)
        with self.assertRaises(DomainNotFoundError):
            self.applicability_service.record(
                self.tenant_a,
                self.requirement_tenant_b["id"],
                self.exporter_a["id"],
                self.product_a["id"],
                self.destination_a["id"],
                "required",
                datetime(2026, 1, 1, tzinfo=timezone.utc),
            )
        with self.assertRaises(DomainValidationError):
            self.applicability_service.record(
                self.tenant_a,
                self.requirement_global["id"],
                self.exporter_a["id"],
                self.product_a["id"],
                self.destination_a["id"],
                "required",
                datetime(2026, 1, 2, tzinfo=timezone.utc),
                effective_to=datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

    def test_evidence_association_and_cross_tenant_requirement_rejection(self):
        linked = self.evidence_service.associate_requirement(
            self.tenant_a, self.evidence_a["id"], self.requirement_global["id"]
        )
        self.assertEqual(linked["evidence_id"], self.evidence_a["id"])
        with self.assertRaises(DomainNotFoundError):
            self.evidence_service.associate_requirement(
                self.tenant_a, self.evidence_a["id"], self.requirement_tenant_b["id"]
            )
        with self.assertRaises(DomainNotFoundError):
            self.evidence_service.associate_requirement(
                self.tenant_b, self.evidence_a["id"], self.requirement_global["id"]
            )

    def test_certification_requires_same_tenant_exporter_and_known_authority(self):
        certification = self.certification_service.record(
            self.tenant_a,
            self.exporter_a["id"],
            self.authority_id,
            "Phase 1.7 Certificate",
            date(2026, 1, 1),
            date(2026, 12, 31),
        )
        self.assertEqual(certification["tenant_id"], self.tenant_a.tenant_id)
        with self.assertRaises(DomainNotFoundError):
            self.certification_service.record(
                self.tenant_a, self.exporter_b["id"], self.authority_id, "Invalid Certificate"
            )
        with self.assertRaises(DomainNotFoundError):
            self.certification_service.record(
                self.tenant_a,
                self.exporter_a["id"],
                UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
                "Unknown Authority",
            )
        with self.assertRaises(DomainValidationError):
            self.certification_service.record(
                self.tenant_a,
                self.exporter_a["id"],
                self.authority_id,
                "Invalid Dates",
                date(2026, 12, 31),
                date(2026, 1, 1),
            )

    def test_atomic_evidence_operation_rolls_back_invalid_association(self):
        evidence_repository = ComplianceEvidenceRepository(self.database)
        before = self._count_evidence("phase-1-7-atomic")
        with self.assertRaises(DomainNotFoundError):
            self.evidence_service.record_with_requirements(
                self.tenant_a,
                "phase-1-7-atomic",
                "test",
                "test://phase-1-7/atomic",
                [self.requirement_global["id"], UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")],
            )
        self.assertEqual(self._count_evidence("phase-1-7-atomic"), before)
        self.assertEqual(
            len(self._evidence_links_for_title("phase-1-7-atomic")), 0
        )
        self.assertIsNotNone(evidence_repository)

    def test_atomic_evidence_operation_commits_valid_writes(self):
        evidence = self.evidence_service.record_with_requirements(
            self.tenant_a,
            "phase-1-7-committed",
            "test",
            "test://phase-1-7/committed",
            [self.requirement_global["id"]],
        )
        self.assertEqual(self._count_evidence("phase-1-7-committed"), 1)
        self.assertEqual(len(self._evidence_links_for_title("phase-1-7-committed")), 1)
        self.assertIsNotNone(evidence["id"])

    def test_integrity_failure_does_not_poison_following_operation(self):
        self.assert_domain_persistence_failure(
            lambda: self.exporter_service.create(
                self.tenant_a, "Duplicate Registration", registration_number="P17-A"
            )
        )
        self.assertIsNotNone(self.exporter_service.get(self.tenant_a, self.exporter_a["id"]))

    def _count_evidence(self, title):
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) AS count FROM xportra.compliance_evidence WHERE tenant_id = %s AND document_title = %s",
                    (self.tenant_a.tenant_id, title),
                )
                return cursor.fetchone()["count"]

    def _evidence_links_for_title(self, title):
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT er.id
                    FROM xportra.evidence_requirements er
                    JOIN xportra.compliance_evidence ce ON ce.id = er.evidence_id
                    WHERE ce.tenant_id = %s AND ce.document_title = %s
                    """,
                    (self.tenant_a.tenant_id, title),
                )
                return cursor.fetchall()


if __name__ == "__main__":
    unittest.main()
