from contextlib import contextmanager
from datetime import datetime, timezone
import unittest
from uuid import UUID

from psycopg.errors import UniqueViolation

from xportra.domain.errors import (
    DomainNotFoundError,
    DomainPersistenceError,
    DomainValidationError,
)
from xportra.domain.services import (
    ComplianceEvidenceService,
    ExporterService,
    ProductService,
    RequirementApplicabilityService,
)
from xportra.persistence.errors import PersistenceIntegrityError
from xportra.persistence.tenant import TenantContext

TENANT = TenantContext(UUID("11111111-1111-1111-1111-111111111111"))
EXPORTER_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
PRODUCT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
DESTINATION_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
REQUIREMENT_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
EVIDENCE_ID = UUID("eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee")


class FakeExporterRepository:
    def __init__(self, exporter=None, error=None):
        self.exporter = exporter
        self.error = error
        self.get_calls = []
        self.create_calls = []

    def get(self, tenant, exporter_id):
        self.get_calls.append((tenant, exporter_id))
        return self.exporter

    def create(self, *args):
        if self.error:
            raise self.error
        self.create_calls.append(args)
        return {"id": EXPORTER_ID, "tenant_id": TENANT.tenant_id}


class FakeProductRepository:
    def __init__(self, product=None):
        self.product = product
        self.get_calls = []
        self.create_calls = []

    def get(self, tenant, product_id):
        self.get_calls.append((tenant, product_id))
        return self.product

    def create(self, *args):
        self.create_calls.append(args)
        return {"id": PRODUCT_ID, "tenant_id": TENANT.tenant_id}


class FakeDestinationRepository:
    def __init__(self, destination=None):
        self.destination = destination

    def get(self, _tenant, _destination_id):
        return self.destination


class FakeRequirementRepository:
    def __init__(self, requirement=None):
        self.requirement = requirement
        self.get_calls = []

    def get(self, tenant, requirement_id):
        self.get_calls.append((tenant, requirement_id))
        return self.requirement


class FakeApplicabilityRepository:
    def __init__(self):
        self.create_calls = []

    def create(self, *args):
        self.create_calls.append(args)
        return {"id": "applicability"}


class FakeEvidenceRepository:
    def __init__(self):
        self.transaction_rows = []

    def get(self, _tenant, _evidence_id):
        return {"id": EVIDENCE_ID}

    def create_in_transaction(self, _connection, tenant, *args):
        row = {"id": EVIDENCE_ID, "tenant_id": tenant.tenant_id}
        self.transaction_rows.append(row)
        return row


class FakeEvidenceRequirementRepository:
    def __init__(self, fail_on_call=None):
        self.calls = []
        self.fail_on_call = fail_on_call

    def link_in_transaction(self, _connection, tenant, evidence_id, requirement_id):
        self.calls.append((tenant, evidence_id, requirement_id))
        if self.fail_on_call == len(self.calls):
            cause = PersistenceIntegrityError("test association", UniqueViolation("duplicate"))
            raise cause
        return {"id": len(self.calls)}


class FakeDatabase:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    @contextmanager
    def transaction(self):
        try:
            yield object()
        except Exception:
            self.rolled_back = True
            raise
        else:
            self.committed = True


class DomainServiceTests(unittest.TestCase):
    def test_product_service_requires_parent_in_same_tenant(self):
        exporter_repository = FakeExporterRepository(
            {"id": EXPORTER_ID, "tenant_id": TENANT.tenant_id}
        )
        product_repository = FakeProductRepository()
        service = ProductService(exporter_repository, product_repository)

        result = service.create(TENANT, EXPORTER_ID, "Cocoa")

        self.assertEqual(result["id"], PRODUCT_ID)
        self.assertEqual(exporter_repository.get_calls, [(TENANT, EXPORTER_ID)])
        self.assertEqual(product_repository.create_calls[0][0], TENANT)

    def test_product_service_rejects_missing_parent_before_persistence(self):
        service = ProductService(FakeExporterRepository(), FakeProductRepository())

        with self.assertRaises(DomainNotFoundError):
            service.create(TENANT, EXPORTER_ID, "Cocoa")

    def test_tenant_context_cannot_be_omitted(self):
        service = ExporterService(FakeExporterRepository())

        with self.assertRaises(DomainValidationError):
            service.create(None, "Exporter")

    def test_applicability_requires_product_to_belong_to_exporter(self):
        service = RequirementApplicabilityService(
            FakeExporterRepository({"id": EXPORTER_ID}),
            FakeProductRepository({"id": PRODUCT_ID, "exporter_id": UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")}),
            FakeDestinationRepository({"id": DESTINATION_ID}),
            FakeRequirementRepository({"id": REQUIREMENT_ID}),
            FakeApplicabilityRepository(),
        )

        with self.assertRaises(DomainValidationError):
            service.record(
                TENANT,
                REQUIREMENT_ID,
                EXPORTER_ID,
                PRODUCT_ID,
                DESTINATION_ID,
                "required",
                datetime(2026, 1, 1, tzinfo=timezone.utc),
            )

    def test_persistence_error_is_translated_at_domain_boundary(self):
        cause = PersistenceIntegrityError("exporter creation", UniqueViolation("duplicate"))
        service = ExporterService(FakeExporterRepository(error=cause))

        with self.assertRaises(DomainPersistenceError) as raised:
            service.create(TENANT, "Duplicate")

        self.assertIs(raised.exception.__cause__, cause)
        self.assertEqual(raised.exception.operation, "exporter creation")

    def test_evidence_and_requirements_rollback_as_one_operation(self):
        database = FakeDatabase()
        evidence_repository = FakeEvidenceRepository()
        link_repository = FakeEvidenceRequirementRepository(fail_on_call=2)
        requirement_repository = FakeRequirementRepository({"id": REQUIREMENT_ID})
        service = ComplianceEvidenceService(
            database, evidence_repository, link_repository, requirement_repository
        )

        with self.assertRaises(DomainPersistenceError):
            service.record_with_requirements(
                TENANT,
                "Evidence",
                "test",
                "test://evidence",
                [REQUIREMENT_ID, REQUIREMENT_ID],
            )

        self.assertTrue(database.rolled_back)
        self.assertFalse(database.committed)
        self.assertEqual(len(evidence_repository.transaction_rows), 1)
        self.assertEqual(len(link_repository.calls), 2)

    def test_evidence_operation_requires_a_requirement(self):
        service = ComplianceEvidenceService(
            FakeDatabase(),
            FakeEvidenceRepository(),
            FakeEvidenceRequirementRepository(),
            FakeRequirementRepository(),
        )

        with self.assertRaises(DomainValidationError):
            service.record_with_requirements(
                TENANT, "Evidence", "test", "test://evidence", []
            )


if __name__ == "__main__":
    unittest.main()
