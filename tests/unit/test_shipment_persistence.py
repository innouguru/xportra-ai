"""Tenant-scoped shipment persistence boundary (migration 013, ADR-0013).

Proves the server-owned shipment aggregate — commercial
profile facts plus the draft → bound → locked lifecycle —
is persisted, resolved tenant-scopely, and authoritative
over client-supplied shipment identities, without a
database: dict-backed repository doubles stand in for
PostgreSQL while the real ``ComplianceResultStore``,
application services, and HTTP adapter run. Live-database
round-trips stay gated under ``DATABASE_URL`` in
``tests/integration/test_shipment_postgresql.py``.

Scope honored: no workflow-state redesign, no profile
duplication into ``compliance_workflows``, no weight /
exporter / product-master / market FKs, no versioning,
no snapshots, no archive/delete surface. No existing
test is modified.
"""

import pathlib
import re
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient
from psycopg.errors import IntegrityError

from xportra.api.app import create_app
from xportra.application import WorkflowApplicationService
from xportra.application.analysis import AnalysisApplicationService
from xportra.application.assessments import (
    AssessmentApplicationService,
)
from xportra.application.context import ApplicationContext
from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
    InfrastructureError,
    InvalidTransitionError,
    StaleAnalysisError,
    TerminalWorkflowError,
)
from xportra.application.result_store import ComplianceResultStore
from xportra.domain.shipment import (
    SHIPMENT_STATUS_BOUND,
    SHIPMENT_STATUS_DRAFT,
    SHIPMENT_STATUS_LOCKED,
    ShipmentError,
    ShipmentService,
    shipment_from_record,
)
from xportra.persistence.errors import PersistenceIntegrityError
from xportra.persistence.tenant import TenantContext

TENANT_A = TenantContext(UUID("11111111-1111-1111-1111-111111111111"))
TENANT_B = TenantContext(UUID("22222222-2222-2222-2222-222222222222"))
CTX_A = ApplicationContext(
    actor_id=None, tenant=TENANT_A, role="owner")
CTX_B = ApplicationContext(
    actor_id=None, tenant=TENANT_B, role="owner")
HEADER_A = {"X-Development-Tenant-ID": str(TENANT_A.tenant_id)}
HEADER_B = {"X-Development-Tenant-ID": str(TENANT_B.tenant_id)}
CASE_A = UUID("33333333-3333-3333-3333-333333333333")
CASE_B = UUID("33333333-3333-3333-3333-333333333334")
SHIPMENT_ID = UUID("44444444-4444-4444-4444-444444444444")
UNKNOWN_SHIPMENT = UUID("44444444-4444-4444-4444-444444444445")

PROFILE = {
    "product": "Cocoa beans",
    "origin_country": "Nigeria",
    "destination_country": "Netherlands",
    "quantity": "20",
    "unit": "tonnes",
    "shipment_date": "2026-11-01",
}

MIGRATIONS = (
    pathlib.Path(__file__).resolve().parents[2] / "migrations"
)
UP_013 = MIGRATIONS / "013_shipments.sql"
DOWN_013 = MIGRATIONS / "013_shipments.down.sql"


class _DummyDatabase:
    """Transaction boundary double (connections unused by fakes)."""

    @contextmanager
    def transaction(self):
        yield object()


class _StubRepo:
    """Satisfies store construction; fails on any real write."""

    def create_in_transaction(self, *args, **kwargs):
        raise AssertionError("unexpected repository write")


class _StubRoundsRepo(_StubRepo):
    """Round linkage double with no recorded rounds."""

    def list_for_workflow(self, tenant, workflow_id):
        return []


class FakeShipmentRepo:
    """Dict-backed ``ShipmentRepository`` double."""

    def __init__(self):
        self.rows = {}

    def create_in_transaction(
        self, connection, tenant, shipment_id, case_id,
        product, origin_country, destination_country,
        quantity, unit, shipment_date, status,
    ):
        key = (tenant.tenant_id, shipment_id)
        if key in self.rows:
            raise PersistenceIntegrityError(
                "shipment creation",
                IntegrityError("duplicate shipment row"))
        row = {
            "tenant_id": tenant.tenant_id,
            "shipment_id": shipment_id,
            "case_id": case_id,
            "product": product,
            "origin_country": origin_country,
            "destination_country": destination_country,
            "quantity": quantity,
            "unit": unit,
            "shipment_date": shipment_date,
            "status": status,
        }
        self.rows[key] = row
        return dict(row)

    def get(self, tenant, shipment_id):
        row = self.rows.get((tenant.tenant_id, shipment_id))
        return None if row is None else dict(row)

    def save_in_transaction(
        self, connection, tenant, shipment_id, case_id,
        product, origin_country, destination_country,
        quantity, unit, shipment_date, status,
    ):
        key = (tenant.tenant_id, shipment_id)
        if key not in self.rows:
            return None
        row = {
            "tenant_id": tenant.tenant_id,
            "shipment_id": shipment_id,
            "case_id": case_id,
            "product": product,
            "origin_country": origin_country,
            "destination_country": destination_country,
            "quantity": quantity,
            "unit": unit,
            "shipment_date": shipment_date,
            "status": status,
        }
        self.rows[key] = row
        return dict(row)


class FakeWorkflowRecordsRepo:
    """Dict-backed ``ComplianceWorkflowRepository`` double."""

    def __init__(self):
        self.rows = {}

    def create_in_transaction(
        self, connection, tenant, workflow_id, case_id,
        shipment_id, state,
    ):
        key = (tenant.tenant_id, workflow_id)
        if key in self.rows:
            raise PersistenceIntegrityError(
                "compliance workflow creation",
                IntegrityError("duplicate workflow row"))
        row = {
            "tenant_id": tenant.tenant_id,
            "workflow_id": workflow_id,
            "case_id": case_id,
            "shipment_id": shipment_id,
            "state": state,
            "supplied_evidence_ids": [],
            "open_requirements": [],
        }
        self.rows[key] = row
        return dict(row)

    def get(self, tenant, workflow_id):
        row = self.rows.get((tenant.tenant_id, workflow_id))
        if row is None:
            return None
        return {
            **row,
            "supplied_evidence_ids": list(
                row["supplied_evidence_ids"]),
            "open_requirements": list(row["open_requirements"]),
        }

    def save_in_transaction(
        self, connection, tenant, workflow_id, case_id,
        shipment_id, state, supplied_evidence_ids,
        open_requirements,
    ):
        key = (tenant.tenant_id, workflow_id)
        if key not in self.rows:
            return None
        self.rows[key] = {
            "tenant_id": tenant.tenant_id,
            "workflow_id": workflow_id,
            "case_id": case_id,
            "shipment_id": shipment_id,
            "state": state,
            "supplied_evidence_ids": list(supplied_evidence_ids),
            "open_requirements": list(open_requirements),
        }
        return dict(self.rows[key])


def make_store(shipments=None, records=None):
    shipments = (
        shipments if shipments is not None
        else FakeShipmentRepo())
    records = (
        records if records is not None
        else FakeWorkflowRecordsRepo())
    store = ComplianceResultStore(
        database=_DummyDatabase(),
        reports=_StubRepo(),
        analyses=_StubRepo(),
        traces=_StubRepo(),
        rounds=_StubRoundsRepo(),
        packages=_StubRepo(),
        workflows=records,
        shipments=shipments,
    )
    return store, shipments, records


def wired_service(store):
    return WorkflowApplicationService(result_store=store)


def make_requirement(index):
    return {
        "id": UUID(f"00000000-0000-0000-0000-{index:012d}"),
        "requirement_text": f"Requirement {index} filing duty.",
    }


def make_requirement_body(index):
    """Wire-form requirement (string identities, as over HTTP)."""
    return {
        "id": f"00000000-0000-0000-0000-{index:012d}",
        "requirement_text": f"Requirement {index} filing duty.",
    }


class ShipmentDomainTests(unittest.TestCase):
    def test_create_draft_normalizes_blank_optionals(self):
        shipment = ShipmentService().create(
            tenant_id=TENANT_A, shipment_id=SHIPMENT_ID,
            case_id=CASE_A, product="  Cocoa beans ",
            origin_country="Nigeria",
            destination_country="Netherlands",
            quantity="", unit="  ", shipment_date=None)
        self.assertEqual(shipment.status, SHIPMENT_STATUS_DRAFT)
        self.assertEqual(shipment.product, "Cocoa beans")
        self.assertIsNone(shipment.quantity)
        self.assertIsNone(shipment.unit)
        self.assertIsNone(shipment.shipment_date)

    def test_create_rejects_blank_required_facts(self):
        service = ShipmentService()
        for field in ("product", "origin_country",
                      "destination_country"):
            kwargs = dict(
                tenant_id=TENANT_A, shipment_id=SHIPMENT_ID,
                case_id=CASE_A, product="Cocoa",
                origin_country="Nigeria",
                destination_country="Netherlands")
            kwargs[field] = "   "
            with self.assertRaises(ShipmentError):
                service.create(**kwargs)

    def test_create_rejects_malformed_identities(self):
        with self.assertRaises(ShipmentError):
            ShipmentService().create(
                tenant_id=TENANT_A,
                shipment_id="not-a-uuid", case_id=CASE_A,
                product="Cocoa", origin_country="Nigeria",
                destination_country="Netherlands")

    def test_lifecycle_draft_bound_locked(self):
        service = ShipmentService()
        draft = service.create(
            tenant_id=TENANT_A, shipment_id=SHIPMENT_ID,
            case_id=CASE_A, product="Cocoa",
            origin_country="Nigeria",
            destination_country="Netherlands")
        bound = service.mark_bound(
            draft, tenant_id=TENANT_A)
        self.assertEqual(bound.status, SHIPMENT_STATUS_BOUND)
        locked = service.mark_locked(
            bound, tenant_id=TENANT_A)
        self.assertEqual(locked.status, SHIPMENT_STATUS_LOCKED)
        with self.assertRaises(ShipmentError):
            service.mark_bound(bound, tenant_id=TENANT_A)
        with self.assertRaises(ShipmentError):
            service.mark_locked(draft, tenant_id=TENANT_A)

    def test_bound_and_locked_reject_profile_edits(self):
        service = ShipmentService()
        draft = service.create(
            tenant_id=TENANT_A, shipment_id=SHIPMENT_ID,
            case_id=CASE_A, product="Cocoa",
            origin_country="Nigeria",
            destination_country="Netherlands")
        edited = service.update_profile(
            draft, tenant_id=TENANT_A, quantity="20")
        self.assertEqual(edited.quantity, "20")
        bound = service.mark_bound(draft, tenant_id=TENANT_A)
        with self.assertRaises(ShipmentError):
            service.update_profile(
                bound, tenant_id=TENANT_A, quantity="20")
        locked = service.mark_locked(
            bound, tenant_id=TENANT_A)
        with self.assertRaises(ShipmentError):
            service.update_profile(
                locked, tenant_id=TENANT_A, quantity="20")

    def test_cross_tenant_operation_rejected(self):
        draft = ShipmentService().create(
            tenant_id=TENANT_A, shipment_id=SHIPMENT_ID,
            case_id=CASE_A, product="Cocoa",
            origin_country="Nigeria",
            destination_country="Netherlands")
        with self.assertRaises(ShipmentError):
            ShipmentService().mark_bound(
                draft, tenant_id=TENANT_B)

    def test_record_round_trip(self):
        shipment = ShipmentService().create(
            tenant_id=TENANT_A, shipment_id=SHIPMENT_ID,
            case_id=CASE_A, **PROFILE)
        rebuilt = shipment_from_record(shipment.to_record())
        self.assertEqual(rebuilt, shipment)

    def test_record_rejects_unknown_status(self):
        shipment = ShipmentService().create(
            tenant_id=TENANT_A, shipment_id=SHIPMENT_ID,
            case_id=CASE_A, **PROFILE)
        record = shipment.to_record()
        record["status"] = "archived"
        with self.assertRaises(ShipmentError):
            shipment_from_record(record)


class ShipmentStartTests(unittest.TestCase):
    def setUp(self):
        self.store, _, _ = make_store()
        self.service = wired_service(self.store)

    def test_first_start_persists_shipment_and_workflow(self):
        record, _ = self.service.start_workflow(
            CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
            shipment=dict(PROFILE))
        self.assertEqual(record["shipment_id"], str(SHIPMENT_ID))
        self.assertEqual(record["case_id"], str(CASE_A))
        stored = self.store.get_shipment(CTX_A, SHIPMENT_ID)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.product, "Cocoa beans")
        self.assertEqual(stored.origin_country, "Nigeria")
        self.assertEqual(
            stored.destination_country, "Netherlands")
        self.assertEqual(stored.quantity, "20")
        self.assertEqual(stored.unit, "tonnes")
        self.assertEqual(stored.shipment_date, "2026-11-01")
        self.assertEqual(stored.status, SHIPMENT_STATUS_BOUND)
        self.assertEqual(stored.case_id, CASE_A)

    def test_failed_shipment_persistence_leaves_no_workflow(
            self):
        from xportra.domain.compliance_workflow import (
            ComplianceWorkflowService,
        )

        class _ConflictWithoutRow(FakeShipmentRepo):
            def create_in_transaction(self, *args, **kwargs):
                raise PersistenceIntegrityError(
                    "shipment creation",
                    IntegrityError("duplicate shipment row"))

            def get(self, tenant, shipment_id):
                return None

        records = FakeWorkflowRecordsRepo()
        failing = ComplianceResultStore(
            database=_DummyDatabase(),
            reports=_StubRepo(),
            analyses=_StubRepo(),
            traces=_StubRepo(),
            rounds=_StubRepo(),
            packages=_StubRepo(),
            workflows=records,
            shipments=_ConflictWithoutRow(),
        )
        shipment = ShipmentService().create(
            tenant_id=TENANT_A, shipment_id=SHIPMENT_ID,
            case_id=CASE_A, **PROFILE)
        workflow = ComplianceWorkflowService().begin(
            tenant_id=TENANT_A, case_id=CASE_A,
            shipment_id=SHIPMENT_ID)
        with self.assertRaises(InfrastructureError):
            failing.create_shipment_with_workflow_record(
                CTX_A, shipment, workflow)
        self.assertEqual(records.rows, {})

    def test_retry_converges_without_replacing_facts(self):
        service = self.service
        first, _ = service.start_workflow(
            CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
            shipment=dict(PROFILE))
        second, _ = service.start_workflow(
            CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
            shipment=dict(PROFILE))
        self.assertEqual(first, second)
        store = self.store
        self.assertEqual(len(store._shipments.rows), 1)
        self.assertEqual(
            store.get_shipment(CTX_A, SHIPMENT_ID).product,
            "Cocoa beans")

    def test_retry_with_different_profile_fails_closed(self):
        service = self.service
        service.start_workflow(
            CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
            shipment=dict(PROFILE))
        altered = dict(PROFILE, destination_country="Ghana")
        with self.assertRaises(StaleAnalysisError):
            service.start_workflow(
                CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
                shipment=altered)
        self.assertEqual(
            self.store.get_shipment(
                CTX_A, SHIPMENT_ID).destination_country,
            "Netherlands")

    def test_retry_with_different_case_fails_closed(self):
        service = self.service
        service.start_workflow(
            CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
            shipment=dict(PROFILE))
        with self.assertRaises(StaleAnalysisError):
            service.start_workflow(
                CTX_A, CASE_B, shipment_id=SHIPMENT_ID,
                shipment=dict(PROFILE))

    def test_unknown_shipment_reference_rejected(self):
        with self.assertRaises(ApplicationNotFoundError):
            self.service.start_workflow(
                CTX_A, CASE_A, shipment_id=UNKNOWN_SHIPMENT)

    def test_cross_tenant_shipment_reference_rejected(self):
        service = self.service
        service.start_workflow(
            CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
            shipment=dict(PROFILE))
        with self.assertRaises(ApplicationNotFoundError):
            service.start_workflow(
                CTX_B, CASE_A, shipment_id=SHIPMENT_ID)

    def test_case_mismatch_rejected(self):
        service = self.service
        service.start_workflow(
            CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
            shipment=dict(PROFILE))
        with self.assertRaises(InvalidTransitionError):
            service.start_workflow(
                CTX_A, CASE_B, shipment_id=SHIPMENT_ID)

    def test_locked_shipment_rejects_new_binding(self):
        store = self.store
        service = self.service
        service.start_workflow(
            CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
            shipment=dict(PROFILE))
        stored = store.get_shipment(CTX_A, SHIPMENT_ID)
        locked = ShipmentService().mark_locked(
            stored, tenant_id=TENANT_A)
        store.save_shipment_record(CTX_A, locked)
        with self.assertRaises(TerminalWorkflowError):
            service.start_workflow(
                CTX_A, CASE_B, shipment_id=SHIPMENT_ID)

    def test_profile_without_store_fails_closed(self):
        service = WorkflowApplicationService()
        with self.assertRaises(ApplicationValidationError):
            service.start_workflow(
                CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
                shipment=dict(PROFILE))

    def test_malformed_profile_rejected(self):
        with self.assertRaises(ApplicationValidationError):
            self.service.start_workflow(
                CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
                shipment=["not", "a", "mapping"])
        with self.assertRaises(ApplicationValidationError):
            self.service.start_workflow(
                CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
                shipment=dict(PROFILE, weight="10kg"))
        with self.assertRaises(InvalidTransitionError):
            self.service.start_workflow(
                CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
                shipment=dict(PROFILE, product="   "))

    def test_server_generated_identity_when_omitted(self):
        record, _ = self.service.start_workflow(
            CTX_A, CASE_A, shipment=dict(PROFILE))
        stored = self.store.get_shipment(
            CTX_A, UUID(record["shipment_id"]))
        self.assertIsNotNone(stored)
        self.assertEqual(stored.product, "Cocoa beans")


class ShipmentResolutionTests(unittest.TestCase):
    def test_get_shipment_unknown_reads_as_absent(self):
        store, _, _ = make_store()
        self.assertIsNone(store.get_shipment(CTX_A, SHIPMENT_ID))

    def test_get_shipment_is_tenant_scoped(self):
        store, _, _ = make_store()
        wired_service(store).start_workflow(
            CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
            shipment=dict(PROFILE))
        self.assertIsNone(store.get_shipment(CTX_B, SHIPMENT_ID))
        self.assertIsNotNone(
            store.get_shipment(CTX_A, SHIPMENT_ID))

    def test_save_missing_shipment_fails_closed(self):
        store, _, _ = make_store()
        shipment = ShipmentService().create(
            tenant_id=TENANT_A, shipment_id=SHIPMENT_ID,
            case_id=CASE_A, **PROFILE)
        with self.assertRaises(ApplicationNotFoundError):
            store.save_shipment_record(CTX_A, shipment)

    def test_store_validates_shipment_repository(self):
        with self.assertRaises(ApplicationValidationError):
            ComplianceResultStore(
                database=_DummyDatabase(),
                reports=_StubRepo(),
                analyses=_StubRepo(),
                traces=_StubRepo(),
                rounds=_StubRepo(),
                packages=_StubRepo(),
                shipments=SimpleNamespace(),
            )


class ShipmentApplicabilityTests(unittest.TestCase):
    def _service_with_shipment(self):
        store, _, _ = make_store()
        wired_service(store).start_workflow(
            CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
            shipment=dict(PROFILE))
        return AssessmentApplicationService(
            shipment_reader=store)

    def test_explicit_input_still_works(self):
        service = AssessmentApplicationService()
        dto = service.determine_applicability(
            CTX_A, [make_requirement(1), make_requirement(2)],
            exporter={"country_of_registration": "NG"},
            destination={"country_code": "GH"})
        self.assertEqual(dto.counts["total_requirements"], 2)

    def test_bound_shipment_supplies_default_profile(self):
        service = self._service_with_shipment()
        from_shipment = service.determine_applicability(
            CTX_A, [make_requirement(1)],
            shipment_id=SHIPMENT_ID)
        explicit = AssessmentApplicationService(
        ).determine_applicability(
            CTX_A, [make_requirement(1)],
            exporter={"country_of_registration": "Nigeria"},
            product={"description": "Cocoa beans"},
            destination={"country_code": "Netherlands"})
        self.assertEqual(from_shipment.counts,
                         explicit.counts)

    def test_explicit_facts_win_over_shipment_defaults(self):
        service = self._service_with_shipment()
        dto = service.determine_applicability(
            CTX_A, [make_requirement(1)],
            product={"description": "Sesame seeds"},
            shipment_id=SHIPMENT_ID)
        explicit = AssessmentApplicationService(
        ).determine_applicability(
            CTX_A, [make_requirement(1)],
            exporter={"country_of_registration": "Nigeria"},
            product={"description": "Sesame seeds"},
            destination={"country_code": "Netherlands"})
        self.assertEqual(dto.counts, explicit.counts)

    def test_unknown_shipment_fails_closed(self):
        service = self._service_with_shipment()
        with self.assertRaises(ApplicationNotFoundError):
            service.determine_applicability(
                CTX_A, [make_requirement(1)],
                shipment_id=UNKNOWN_SHIPMENT)

    def test_shipment_reference_without_reader_fails_closed(
            self):
        service = AssessmentApplicationService()
        with self.assertRaises(ApplicationValidationError):
            service.determine_applicability(
                CTX_A, [make_requirement(1)],
                shipment_id=SHIPMENT_ID)

    def test_cross_tenant_shipment_reads_as_unknown(self):
        store, _, _ = make_store()
        wired_service(store).start_workflow(
            CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
            shipment=dict(PROFILE))
        service = AssessmentApplicationService(
            shipment_reader=store)
        with self.assertRaises(ApplicationNotFoundError):
            service.determine_applicability(
                CTX_B, [make_requirement(1)],
                shipment_id=SHIPMENT_ID)


class ShipmentAnalysisTests(unittest.TestCase):
    def _analysis_service(self, store):
        from xportra.application.analysis import (
            AnalysisApplicationService,
        )

        class _RAG:
            def query(self, *args, **kwargs):
                raise AssertionError(
                    "retrieval must not run before "
                    "shipment verification")

        return AnalysisApplicationService(
            rag_service=_RAG(), result_store=store)

    def test_unknown_bound_shipment_blocks_analysis(self):
        store, shipments, _ = make_store()
        record, _ = wired_service(store).start_workflow(
            CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
            shipment=dict(PROFILE))
        del shipments.rows[(TENANT_A.tenant_id, SHIPMENT_ID)]
        with self.assertRaises(ApplicationNotFoundError):
            self._analysis_service(store).run_analysis(
                CTX_A, record, [{"id": "case-1"}])

    def test_case_mismatched_shipment_blocks_analysis(self):
        store, shipments, _ = make_store()
        record, _ = wired_service(store).start_workflow(
            CTX_A, CASE_A, shipment_id=SHIPMENT_ID,
            shipment=dict(PROFILE))
        shipments.rows[(TENANT_A.tenant_id, SHIPMENT_ID)] = {
            "tenant_id": TENANT_A.tenant_id,
            "shipment_id": SHIPMENT_ID,
            "case_id": CASE_B,
            "product": PROFILE["product"],
            "origin_country": PROFILE["origin_country"],
            "destination_country":
                PROFILE["destination_country"],
            "quantity": PROFILE["quantity"],
            "unit": PROFILE["unit"],
            "shipment_date": PROFILE["shipment_date"],
            "status": SHIPMENT_STATUS_BOUND,
        }
        with self.assertRaises(ApplicationValidationError):
            self._analysis_service(store).run_analysis(
                CTX_A, record, [{"id": "case-1"}])

    def test_no_shipment_store_keeps_previous_behavior(self):
        service = AnalysisApplicationService(
            rag_service=SimpleNamespace(
                query=lambda *a, **k: (_ for _ in ()).throw(
                    AssertionError("no retrieval"))),
        )
        record, _ = WorkflowApplicationService(
        ).start_workflow(
            CTX_A, CASE_A, shipment_id=SHIPMENT_ID)
        with self.assertRaises(ApplicationValidationError):
            service.run_analysis(CTX_A, record, [])


class Migration013StructureTests(unittest.TestCase):
    def test_migration_files_exist(self):
        self.assertTrue(UP_013.is_file())
        self.assertTrue(DOWN_013.is_file())

    def test_transaction_markers_balanced(self):
        for path in (UP_013, DOWN_013):
            text = path.read_text(encoding="utf-8")
            self.assertEqual(len(re.findall(r"^BEGIN;$", text, re.M)), 1)
            self.assertEqual(len(re.findall(r"^COMMIT;$", text, re.M)), 1)
            self.assertTrue(
                text.index("BEGIN;") < text.index("COMMIT;"))

    def test_up_creates_shipments_table(self):
        text = UP_013.read_text(encoding="utf-8")
        created = re.findall(
            r"CREATE TABLE IF NOT EXISTS (\S+)", text)
        self.assertEqual(tuple(created), ("xportra.shipments",))
        for column in ("tenant_id", "shipment_id", "case_id",
                       "product", "origin_country",
                       "destination_country", "quantity",
                       "unit", "shipment_date", "status",
                       "created_at", "updated_at"):
            self.assertIn(column, text)
        self.assertIn("PRIMARY KEY (tenant_id, shipment_id)", text)
        for status in ("draft", "bound", "locked"):
            self.assertIn(f"'{status}'", text)
        self.assertIn("shipments_set_updated_at", text)
        ddl = "\n".join(
            line for line in text.splitlines()
            if not line.strip().startswith("--"))
        self.assertNotIn("compliance_workflows", ddl)
        for forbidden in ("weight", "exporter_id", "product_id",
                          "destination_id", "shipment_reference",
                          "version"):
            self.assertNotIn(forbidden, text)

    def test_down_removes_only_the_shipments_table(self):
        text = DOWN_013.read_text(encoding="utf-8")
        dropped = re.findall(r"DROP TABLE IF EXISTS (\S+);", text)
        self.assertEqual(dropped, ["xportra.shipments"])

    def test_no_profile_columns_in_workflow_table(self):
        up_012 = (MIGRATIONS / "012_compliance_workflows.sql"
                  ).read_text(encoding="utf-8")
        for column in ("product", "origin_country",
                       "destination_country"):
            self.assertNotIn(column, up_012)


class ShipmentStartEndpointTests(unittest.TestCase):
    def _client(self):
        store, _, _ = make_store()
        return store, TestClient(create_app(services=SimpleNamespace(
            rag=None, result_store=store)))

    def _start_body(self, case_id=CASE_A,
                    shipment_id=SHIPMENT_ID, profile=True):
        body = {"case_id": str(case_id)}
        if shipment_id is not None:
            body["shipment_id"] = str(shipment_id)
        if profile:
            body["shipment"] = dict(PROFILE)
        return body

    def test_start_with_profile_persists_and_returns_201(self):
        store, client = self._client()
        with client:
            response = client.post(
                "/compliance/workflows/start", headers=HEADER_A,
                json=self._start_body())
            self.assertEqual(response.status_code, 201,
                             response.text)
            workflow = response.json()["workflow"]
            self.assertEqual(workflow["shipment_id"],
                             str(SHIPMENT_ID))
            stored = store.get_shipment(CTX_A, SHIPMENT_ID)
            self.assertIsNotNone(stored)
            self.assertEqual(stored.product, "Cocoa beans")

    def test_restart_converges_on_authoritative_state(self):
        _, client = self._client()
        with client:
            first = client.post(
                "/compliance/workflows/start", headers=HEADER_A,
                json=self._start_body())
            second = client.post(
                "/compliance/workflows/start", headers=HEADER_A,
                json=self._start_body())
            self.assertEqual(first.status_code, 201)
            self.assertEqual(second.status_code, 201)
            self.assertEqual(first.json()["workflow"],
                             second.json()["workflow"])

    def test_restart_with_different_profile_is_stale(self):
        _, client = self._client()
        with client:
            first = client.post(
                "/compliance/workflows/start", headers=HEADER_A,
                json=self._start_body())
            self.assertEqual(first.status_code, 201)
            altered = self._start_body()
            altered["shipment"] = dict(
                PROFILE, destination_country="Ghana")
            retry = client.post(
                "/compliance/workflows/start", headers=HEADER_A,
                json=altered)
            self.assertEqual(retry.status_code, 409,
                             retry.text)

    def test_unknown_shipment_identity_is_not_found(self):
        _, client = self._client()
        with client:
            response = client.post(
                "/compliance/workflows/start", headers=HEADER_A,
                json=self._start_body(
                    shipment_id=UNKNOWN_SHIPMENT, profile=False))
            self.assertEqual(response.status_code, 404,
                             response.text)

    def test_cross_tenant_shipment_identity_is_not_found(self):
        _, client = self._client()
        with client:
            created = client.post(
                "/compliance/workflows/start", headers=HEADER_A,
                json=self._start_body())
            self.assertEqual(created.status_code, 201)
            forged = client.post(
                "/compliance/workflows/start", headers=HEADER_B,
                json=self._start_body(
                    shipment_id=SHIPMENT_ID, profile=False))
            self.assertEqual(forged.status_code, 404,
                             forged.text)

    def test_case_mismatch_is_rejected(self):
        _, client = self._client()
        with client:
            created = client.post(
                "/compliance/workflows/start", headers=HEADER_A,
                json=self._start_body())
            self.assertEqual(created.status_code, 201)
            mismatched = client.post(
                "/compliance/workflows/start", headers=HEADER_A,
                json=self._start_body(
                    case_id=CASE_B, profile=False))
            self.assertEqual(mismatched.status_code, 409,
                             mismatched.text)

    def test_start_without_profile_keeps_legacy_behavior(self):
        client = TestClient(create_app(services=SimpleNamespace(
            rag=None, result_store=None)))
        with client:
            response = client.post(
                "/compliance/workflows/start", headers=HEADER_A,
                json=self._start_body(profile=False))
            self.assertEqual(response.status_code, 201,
                             response.text)

    def test_reference_without_profile_needs_stored_shipment(self):
        _, client = self._client()
        with client:
            response = client.post(
                "/compliance/workflows/start", headers=HEADER_A,
                json=self._start_body(profile=False))
            self.assertEqual(response.status_code, 404,
                             response.text)

    def test_applicability_shipment_default_over_http(self):
        _, client = self._client()
        with client:
            created = client.post(
                "/compliance/workflows/start", headers=HEADER_A,
                json=self._start_body())
            self.assertEqual(created.status_code, 201)
            response = client.post(
                "/compliance/assessments/applicability",
                headers=HEADER_A,
                json={"requirements": [make_requirement_body(1)],
                      "shipment_id": str(SHIPMENT_ID)})
            self.assertEqual(response.status_code, 200,
                             response.text)


if __name__ == "__main__":
    unittest.main()
