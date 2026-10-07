"""Shipment lock-on-finalization (ADR-0013 lifecycle completion).

Proves successful terminal finalization moves the bound
shipment to locked in the same transaction as the
package linkage and terminal workflow row — and that
any terminal-write failure rolls all three back
together. No database: repository doubles write
through a transactional fake boundary that snapshots
and restores rows on failure, while the real
``ComplianceResultStore`` transaction logic runs.
Live-database atomicity stays gated under
``DATABASE_URL``.

Scope honored: no state machine change, no
``assessment_package_ready`` reinterpretation, no
versioning/snapshots/delete semantics, no FKs, no
lock-as-completion-signal (listing still derives
completion from workflow/package terminality). No
existing test is modified.
"""

import copy
import unittest
from contextlib import contextmanager
from uuid import UUID

from psycopg.errors import IntegrityError

from xportra.application import WorkflowApplicationService
from xportra.application.context import ApplicationContext
from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
    InfrastructureError,
    TerminalWorkflowError,
)
from xportra.application.result_store import ComplianceResultStore
from xportra.domain.compliance_workflow import (
    WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY,
    WORKFLOW_STATE_CREATED,
    ComplianceWorkflowService,
    WorkflowAnalysisRound,
)
from xportra.domain.shipment import (
    SHIPMENT_STATUS_BOUND,
    SHIPMENT_STATUS_DRAFT,
    SHIPMENT_STATUS_LOCKED,
    ShipmentError,
    ShipmentService,
)
from xportra.persistence.errors import PersistenceIntegrityError
from xportra.persistence.tenant import TenantContext

TENANT_A = TenantContext(UUID("11111111-1111-1111-1111-111111111111"))
TENANT_B = TenantContext(UUID("22222222-2222-2222-2222-222222222222"))
CTX_A = ApplicationContext(
    actor_id=None, tenant=TENANT_A, role="owner")
CTX_B = ApplicationContext(
    actor_id=None, tenant=TENANT_B, role="owner")
CASE_A = UUID("33333333-3333-3333-3333-333333333333")
CASE_B = UUID("33333333-3333-3333-3333-333333333334")
SHIPMENT_ID = UUID("44444444-4444-4444-4444-444444444444")
UNKNOWN_SHIPMENT = UUID("44444444-4444-4444-4444-444444444445")
REPORT_ID = UUID("55555555-5555-5555-5555-555555555555")

PROFILE = {
    "product": "Cocoa beans",
    "origin_country": "Nigeria",
    "destination_country": "Netherlands",
    "quantity": "20",
    "unit": "tonnes",
    "shipment_date": "2026-11-01",
}


class FakeConnection:
    """Opaque transaction handle double (identity only)."""


class TransactionalDatabase:
    """Snapshot/restore transaction boundary double.

    Repository doubles register their row mappings;
    entry snapshots every mapping and a raised failure
    restores all of them — the in-memory equivalent of
    the PostgreSQL rollback the real ``Database``
    provides. Records connections so tests can prove
    terminal writes share one transaction.
    """

    def __init__(self):
        self.repos = []
        self.connections = []

    def register(self, repo):
        self.repos.append(repo)
        return repo

    @contextmanager
    def transaction(self):
        snapshots = {id(repo): copy.deepcopy(repo.rows)
                     for repo in self.repos}
        connection = FakeConnection()
        self.connections.append(connection)
        try:
            yield connection
        except Exception:
            for repo in self.repos:
                repo.rows = snapshots[id(repo)]
            raise


class _StubRepo:
    def create_in_transaction(self, *args, **kwargs):
        raise AssertionError("unexpected repository write")


class FakeShipmentRepo:
    """Dict-backed ``ShipmentRepository`` double."""

    def __init__(self, database):
        self.rows = {}
        self.seen = []
        database.register(self)

    def _record(self, connection):
        self.seen.append(connection)

    def create_in_transaction(
        self, connection, tenant, shipment_id, case_id,
        product, origin_country, destination_country,
        quantity, unit, shipment_date, status,
    ):
        self._record(connection)
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

    def get_in_transaction(self, connection, tenant,
                           shipment_id):
        self._record(connection)
        return self.get(tenant, shipment_id)

    def save_in_transaction(
        self, connection, tenant, shipment_id, case_id,
        product, origin_country, destination_country,
        quantity, unit, shipment_date, status,
    ):
        self._record(connection)
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

    def __init__(self, database, fail_save=False):
        self.rows = {}
        self.seen = []
        self.fail_save = fail_save
        database.register(self)

    def create_in_transaction(
        self, connection, tenant, workflow_id, case_id,
        shipment_id, state,
    ):
        self.seen.append(connection)
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
        self.seen.append(connection)
        if self.fail_save:
            raise PersistenceIntegrityError(
                "compliance workflow save",
                IntegrityError("save failed"))
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


class FakePackagesRepo:
    """Dict-backed package-linkage double with failure injection."""

    def __init__(self, database, fail_create=False):
        self.rows = {}
        self.seen = []
        self.fail_create = fail_create
        database.register(self)

    def create_in_transaction(
        self, connection, tenant, workflow_id, case_id,
        shipment_id, report_id, round_index,
        open_requirements,
    ):
        self.seen.append(connection)
        if self.fail_create:
            raise PersistenceIntegrityError(
                "package creation",
                IntegrityError("package write failed"))
        key = (tenant.tenant_id, workflow_id)
        if key in self.rows:
            raise PersistenceIntegrityError(
                "package creation",
                IntegrityError("duplicate package row"))
        row = {
            "tenant_id": tenant.tenant_id,
            "workflow_id": workflow_id,
            "case_id": case_id,
            "shipment_id": shipment_id,
            "report_id": report_id,
            "round_index": round_index,
            "open_requirements": list(open_requirements),
        }
        self.rows[key] = row
        return dict(row)

    def get(self, tenant, workflow_id):
        row = self.rows.get((tenant.tenant_id, workflow_id))
        return None if row is None else dict(row)


class FakeRoundsRepo(_StubRepo):
    def __init__(self):
        self.rows = {}

    def add(self, tenant, workflow_id, round_row):
        self.rows.setdefault(
            (tenant.tenant_id, workflow_id), []).append(
                dict(round_row))

    def list_for_workflow(self, tenant, workflow_id):
        return [dict(row) for row in self.rows.get(
            (tenant.tenant_id, workflow_id), [])]


def make_store(database=None, fail_package=False,
               fail_workflow_save=False):
    database = (
        database if database is not None
        else TransactionalDatabase())
    shipments = FakeShipmentRepo(database)
    records = FakeWorkflowRecordsRepo(
        database, fail_save=fail_workflow_save)
    packages = FakePackagesRepo(
        database, fail_create=fail_package)
    store = ComplianceResultStore(
        database=database,
        reports=_StubRepo(),
        analyses=_StubRepo(),
        traces=_StubRepo(),
        rounds=FakeRoundsRepo(),
        packages=packages,
        workflows=records,
        shipments=shipments,
    )
    return store, database, shipments, records, packages


def begin_bound(store, shipment_id=SHIPMENT_ID, case_id=CASE_A,
                ctx=CTX_A, profile=None):
    """Start a profile-bound workflow through the real service."""
    service = WorkflowApplicationService(result_store=store)
    record, _ = service.start_workflow(
        ctx, case_id, shipment_id=shipment_id,
        shipment=dict(PROFILE if profile is None else profile))
    return record


def terminal_workflow(record):
    """Rebuild a started record as terminal with one round."""
    import dataclasses

    from xportra.application._guards import workflow_from_record

    return dataclasses.replace(
        workflow_from_record(record),
        state=WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY,
        rounds=(round_for(),))


def round_for(report_id=REPORT_ID):
    return WorkflowAnalysisRound(
        round_index=1,
        report_id=report_id,
        analysis_ids=(),
        trace_ids=(),
        input_fingerprints=(),
    )


class ShipmentLockDomainTests(unittest.TestCase):
    def _shipment(self, status=SHIPMENT_STATUS_BOUND):
        service = ShipmentService()
        draft = service.create(
            tenant_id=TENANT_A, shipment_id=SHIPMENT_ID,
            case_id=CASE_A, **PROFILE)
        if status == SHIPMENT_STATUS_DRAFT:
            return draft
        bound = service.mark_bound(draft, tenant_id=TENANT_A)
        if status == SHIPMENT_STATUS_BOUND:
            return bound
        return service.mark_locked(bound, tenant_id=TENANT_A)

    def test_bound_to_locked(self):
        locked = ShipmentService().mark_locked(
            self._shipment(SHIPMENT_STATUS_BOUND),
            tenant_id=TENANT_A)
        self.assertEqual(locked.status, SHIPMENT_STATUS_LOCKED)

    def test_draft_to_locked_rejected(self):
        with self.assertRaises(ShipmentError):
            ShipmentService().mark_locked(
                self._shipment(SHIPMENT_STATUS_DRAFT),
                tenant_id=TENANT_A)

    def test_locked_to_bound_rejected(self):
        with self.assertRaises(ShipmentError):
            ShipmentService().mark_bound(
                self._shipment(SHIPMENT_STATUS_LOCKED),
                tenant_id=TENANT_A)

    def test_locked_to_locked_rejected(self):
        with self.assertRaises(ShipmentError):
            ShipmentService().mark_locked(
                self._shipment(SHIPMENT_STATUS_LOCKED),
                tenant_id=TENANT_A)


class ShipmentLockFinalizeTests(unittest.TestCase):
    def test_success_locks_shipment_with_package_and_workflow(
            self):
        store, database, shipments, records, packages = (
            make_store())
        record = begin_bound(store)
        advanced = terminal_workflow(record)
        linkage = store.store_package_linkage(
            CTX_A, advanced, REPORT_ID, 1, [])
        self.assertEqual(linkage["report_id"], REPORT_ID)
        stored = store.get_shipment(CTX_A, SHIPMENT_ID)
        self.assertEqual(stored.status, SHIPMENT_STATUS_LOCKED)
        workflow_row = records.get(
            TENANT_A, advanced.id)
        self.assertEqual(
            workflow_row["state"],
            WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY)
        self.assertIsNotNone(packages.get(TENANT_A, advanced.id))

    def test_lock_package_and_workflow_share_one_transaction(
            self):
        store, database, shipments, records, packages = (
            make_store())
        record = begin_bound(store)
        advanced = terminal_workflow(record)
        database.connections.clear()
        shipments.seen.clear()
        records.seen.clear()
        packages.seen.clear()
        store.store_package_linkage(
            CTX_A, advanced, REPORT_ID, 1, [])
        self.assertEqual(len(database.connections), 1)
        only = database.connections[0]
        self.assertIn(only, shipments.seen)
        self.assertIn(only, packages.seen)
        self.assertIn(only, records.seen)

    def test_unknown_shipment_fails_closed(self):
        store, _, _, _, _ = make_store()
        record = begin_bound(store)
        advanced = terminal_workflow(record)
        import dataclasses

        forged = dataclasses.replace(
            advanced, shipment_id=UNKNOWN_SHIPMENT)
        with self.assertRaises(ApplicationNotFoundError):
            store.store_package_linkage(
                CTX_A, forged, REPORT_ID, 1, [])

    def test_cross_tenant_shipment_fails_closed(self):
        store, _, _, _, _ = make_store()
        WorkflowApplicationService(
            result_store=store).start_workflow(
                CTX_B, CASE_A, shipment_id=SHIPMENT_ID,
                shipment=dict(PROFILE))
        forged = ComplianceWorkflowService().begin(
            tenant_id=TENANT_A, case_id=CASE_A,
            shipment_id=SHIPMENT_ID)
        import dataclasses

        forged = dataclasses.replace(
            forged, state=WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY,
            rounds=(round_for(),))
        # The shipment exists, but only under tenant B:
        # resolving under tenant A reads as absent.
        with self.assertRaises(ApplicationNotFoundError):
            store.store_package_linkage(
                CTX_A, forged, REPORT_ID, 1, [])

    def test_case_mismatch_rejected(self):
        store, _, shipments, _, _ = make_store()
        begin_bound(store)
        record = begin_bound(
            store, shipment_id=UUID(
                "44444444-4444-4444-4444-444444444446"),
            case_id=CASE_B)
        advanced = terminal_workflow(record)
        import dataclasses

        forged = dataclasses.replace(
            advanced, shipment_id=SHIPMENT_ID)
        with self.assertRaises(ApplicationValidationError):
            store.store_package_linkage(
                CTX_A, forged, REPORT_ID, 1, [])

    def test_draft_shipment_cannot_lock(self):
        store, _, shipments, _, _ = make_store()
        service = ShipmentService()
        draft = service.create(
            tenant_id=TENANT_A, shipment_id=SHIPMENT_ID,
            case_id=CASE_A, **PROFILE)
        store.create_shipment_record(CTX_A, draft)
        record = begin_bound(
            store, shipment_id=UUID(
                "44444444-4444-4444-4444-444444444447"),
            case_id=CASE_A)
        advanced = terminal_workflow(record)
        import dataclasses

        forged = dataclasses.replace(
            advanced, shipment_id=SHIPMENT_ID)
        with self.assertRaises(ApplicationValidationError):
            store.store_package_linkage(
                CTX_A, forged, REPORT_ID, 1, [])


class ShipmentLockRollbackTests(unittest.TestCase):
    def test_package_failure_rolls_back_lock(self):
        store, _, shipments, records, packages = make_store(
            fail_package=True)
        record = begin_bound(store)
        advanced = terminal_workflow(record)
        with self.assertRaises(InfrastructureError):
            store.store_package_linkage(
                CTX_A, advanced, REPORT_ID, 1, [])
        self.assertEqual(
            store.get_shipment(
                CTX_A, SHIPMENT_ID).status,
            SHIPMENT_STATUS_BOUND)
        self.assertEqual(packages.rows, {})
        self.assertEqual(
            records.get(TENANT_A, advanced.id)["state"],
            WORKFLOW_STATE_CREATED)

    def test_workflow_save_failure_rolls_back_lock(self):
        store, _, shipments, records, packages = make_store(
            fail_workflow_save=True)
        record = begin_bound(store)
        advanced = terminal_workflow(record)
        with self.assertRaises(InfrastructureError):
            store.store_package_linkage(
                CTX_A, advanced, REPORT_ID, 1, [])
        self.assertEqual(
            store.get_shipment(
                CTX_A, SHIPMENT_ID).status,
            SHIPMENT_STATUS_BOUND)
        self.assertEqual(packages.rows, {})
        self.assertEqual(
            records.get(TENANT_A, advanced.id)["state"],
            WORKFLOW_STATE_CREATED)


class ShipmentLockRetryTests(unittest.TestCase):
    def test_retry_after_success_keeps_terminal_state(self):
        store, _, shipments, records, packages = make_store()
        record = begin_bound(store)
        advanced = terminal_workflow(record)
        store.store_package_linkage(
            CTX_A, advanced, REPORT_ID, 1, [])
        # A retried terminal write conflicts on the
        # package row instead of reopening anything.
        with self.assertRaises(InfrastructureError):
            store.store_package_linkage(
                CTX_A, advanced, REPORT_ID, 1, [])
        self.assertEqual(
            store.get_shipment(
                CTX_A, SHIPMENT_ID).status,
            SHIPMENT_STATUS_LOCKED)
        self.assertEqual(
            records.get(TENANT_A, advanced.id)["state"],
            WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY)

    def test_finalize_rejects_second_terminal_attempt(self):
        store, _, _, _, _ = make_store()
        service = WorkflowApplicationService(result_store=store)
        record = begin_bound(store)
        advanced = terminal_workflow(record)
        store.store_package_linkage(
            CTX_A, advanced, REPORT_ID, 1, [])
        for round_entry in advanced.rounds:
            store._rounds.add(TENANT_A, advanced.id, {
                "workflow_id": advanced.id,
                "round_index": round_entry.round_index,
                "case_id": advanced.case_id,
                "shipment_id": advanced.shipment_id,
                "report_id": round_entry.report_id,
                "analysis_ids": [],
                "trace_ids": [],
                "input_fingerprints": [],
            })
        # The service guard precedes the store call: an
        # already-finalized workflow fails as terminal
        # before any shipment write is attempted.
        submitted = dict(advanced.to_record())
        with self.assertRaises(TerminalWorkflowError):
            service.finalize_stored_package(CTX_A, submitted)


if __name__ == "__main__":
    unittest.main()
