"""Server-owned workflow-record continuity (migration 012).

Proves the workflow progression row — state, shipment
binding, supplied evidence references, open
requirements — is persisted, reloaded per request, and
authoritative over the submitted snapshot, without a
database: dict-backed repository doubles stand in for
PostgreSQL while the real ``ComplianceResultStore``
comparison/retention logic runs. Live-database
round-trips are gated in
``tests/integration/test_workflow_record_postgresql.py``.
"""

import pathlib
import re
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import UUID

from psycopg.errors import IntegrityError

from xportra.application import WorkflowApplicationService
from xportra.application.context import ApplicationContext
from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
    StaleAnalysisError,
    TenantMismatchError,
)
from xportra.application.result_store import ComplianceResultStore
from xportra.persistence.errors import PersistenceIntegrityError
from xportra.persistence.tenant import TenantContext

TENANT_A = TenantContext(UUID("11111111-1111-1111-1111-111111111111"))
TENANT_B = TenantContext(UUID("22222222-2222-2222-2222-222222222222"))
CTX_A = ApplicationContext(
    actor_id=None, tenant=TENANT_A, role="owner")
CTX_B = ApplicationContext(
    actor_id=None, tenant=TENANT_B, role="owner")
CASE_ID = UUID("33333333-3333-3333-3333-333333333333")
SHIPMENT_ID = UUID("44444444-4444-4444-4444-444444444444")
EVIDENCE_A = UUID("55555555-5555-5555-5555-555555555555")
REQUIREMENT_A = UUID("66666666-6666-6666-6666-666666666666")

MIGRATIONS = (
    pathlib.Path(__file__).resolve().parents[2] / "migrations"
)
UP_012 = MIGRATIONS / "012_compliance_workflows.sql"
DOWN_012 = MIGRATIONS / "012_compliance_workflows.down.sql"


class _DummyDatabase:
    """Transaction boundary double (connections unused by fakes)."""

    @contextmanager
    def transaction(self):
        yield object()


class _StubRepo:
    """Satisfies store construction; fails on any real write."""

    def create_in_transaction(self, *args, **kwargs):
        raise AssertionError("unexpected repository write")


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


class FakeRoundsRepo(_StubRepo):
    """Dict-backed round linkage in store-row shape."""

    def __init__(self):
        self.rows = []

    def list_for_workflow(self, tenant, workflow_id):
        return [
            dict(row) for row in self.rows
            if row["tenant_id"] == tenant.tenant_id
            and row["workflow_id"] == workflow_id
        ]


class FakeEvidenceLookup:
    """Tenant-scoped recorded-evidence double."""

    def __init__(self, known=()):
        self.known = set(known)

    def get(self, tenant, evidence_id):
        if (tenant.tenant_id, evidence_id) in self.known:
            return {"evidence_id": evidence_id}
        return None


def make_store(records=None, rounds=None, evidence=None):
    records = records or FakeWorkflowRecordsRepo()
    rounds = rounds or FakeRoundsRepo()
    store = ComplianceResultStore(
        database=_DummyDatabase(),
        reports=_StubRepo(),
        analyses=_StubRepo(),
        traces=_StubRepo(),
        rounds=rounds,
        packages=_StubRepo(),
        workflows=records,
    )
    return store, records, rounds


def wired_service(store, evidence=None):
    return WorkflowApplicationService(
        result_store=store, evidence_service=evidence)


def reviewable_record(store, records, ctx, case_id):
    """Start a workflow parked in a supply-accepting state.

    The domain only accepts evidence supply from
    ``additional_evidence_requested``/``review_required``;
    the stored row and the submitted snapshot are moved
    together so the snapshot stays current.
    """
    record, _ = wired_service(store).start_workflow(
        ctx, case_id, shipment_id=SHIPMENT_ID)
    records.rows[
        (ctx.tenant.tenant_id, UUID(record["id"]))
    ]["state"] = "review_required"
    return {**record, "state": "review_required"}


class WorkflowRecordPersistenceTests(unittest.TestCase):
    def test_start_persists_and_next_request_loads_from_store(self):
        store, records, _ = make_store()
        first = wired_service(store)
        record, _ = first.start_workflow(
            CTX_A, CASE_ID, shipment_id=SHIPMENT_ID)
        row = records.get(TENANT_A, UUID(record["id"]))
        self.assertIsNotNone(row)
        self.assertEqual(row["state"], "created")
        self.assertEqual(row["shipment_id"], SHIPMENT_ID)
        # A fresh service instance (a later request) advances
        # the workflow from the stored row, not from memory.
        second = wired_service(store)
        advanced, _ = second.provide_information(CTX_A, record)
        self.assertEqual(advanced["state"], "information_provided")
        row = records.get(TENANT_A, UUID(record["id"]))
        self.assertEqual(row["state"], "information_provided")

    def test_mutation_of_unknown_workflow_fails_closed(self):
        legacy = WorkflowApplicationService()
        record, _ = legacy.start_workflow(
            CTX_A, CASE_ID, shipment_id=SHIPMENT_ID)
        store, _, _ = make_store()
        with self.assertRaises(ApplicationNotFoundError):
            wired_service(store).provide_information(CTX_A, record)

    def test_stale_state_snapshot_is_rejected(self):
        store, _, _ = make_store()
        service = wired_service(store)
        began, _ = service.start_workflow(
            CTX_A, CASE_ID, shipment_id=SHIPMENT_ID)
        current, _ = wired_service(store).provide_information(
            CTX_A, began)
        self.assertEqual(current["state"], "information_provided")
        with self.assertRaises(StaleAnalysisError) as raised:
            wired_service(store).provide_information(CTX_A, began)
        self.assertEqual(
            raised.exception.reasons[0][0], "stale_workflow_state")

    def test_stale_supplied_references_are_rejected(self):
        store, records, _ = make_store()
        began, _ = wired_service(store).start_workflow(
            CTX_A, CASE_ID, shipment_id=SHIPMENT_ID)
        # Another request supplied evidence since; the stale
        # snapshot must fail before any transition runs.
        records.rows[
            (TENANT_A.tenant_id, UUID(began["id"]))
        ]["supplied_evidence_ids"] = [EVIDENCE_A]
        with self.assertRaises(StaleAnalysisError) as raised:
            wired_service(store).note_evidence_pending(CTX_A, began)
        self.assertEqual(raised.exception.reasons[0][0],
                         "stale_workflow_references")

    def test_stale_round_linkage_is_rejected(self):
        store, _, rounds = make_store()
        service = wired_service(store)
        record, _ = service.start_workflow(
            CTX_A, CASE_ID, shipment_id=SHIPMENT_ID)
        rounds.rows.append({
            "tenant_id": TENANT_A.tenant_id,
            "workflow_id": UUID(record["id"]),
            "round_index": 1,
            "case_id": CASE_ID,
            "shipment_id": SHIPMENT_ID,
            "report_id": UUID(
                "77777777-7777-7777-7777-777777777777"),
            "analysis_ids": (),
            "trace_ids": (),
            "input_fingerprints": (),
        })
        with self.assertRaises(StaleAnalysisError) as raised:
            wired_service(store).provide_information(CTX_A, record)
        self.assertEqual(raised.exception.reasons[0][0],
                         "stale_round_linkage")

    def test_cross_tenant_mutation_is_rejected(self):
        store, _, _ = make_store()
        record, _ = wired_service(store).start_workflow(
            CTX_A, CASE_ID, shipment_id=SHIPMENT_ID)
        with self.assertRaises(TenantMismatchError):
            wired_service(store).provide_information(CTX_B, record)

    def test_repeat_start_converges_without_resetting(self):
        store, records, _ = make_store()
        first, _ = wired_service(store).start_workflow(
            CTX_A, CASE_ID, shipment_id=SHIPMENT_ID)
        progressed, _ = wired_service(store).provide_information(
            CTX_A, first)
        repeat, _ = wired_service(store).start_workflow(
            CTX_A, CASE_ID, shipment_id=SHIPMENT_ID)
        self.assertEqual(repeat["id"], first["id"])
        self.assertEqual(repeat["state"], "information_provided")
        self.assertEqual(len(records.rows), 1)
        self.assertEqual(progressed["state"], "information_provided")

    def test_legacy_path_unchanged_without_store(self):
        service = WorkflowApplicationService()
        record, _ = service.start_workflow(
            CTX_A, CASE_ID, shipment_id=SHIPMENT_ID)
        for operation in ("provide_information",
                          "note_evidence_pending",
                          "record_applicability"):
            record, _ = getattr(service, operation)(CTX_A, record)
        self.assertEqual(record["state"], "applicability_determined")

    def test_unknown_evidence_cannot_attach(self):
        store, records, _ = make_store()
        record = reviewable_record(store, records, CTX_A, CASE_ID)
        with self.assertRaises(ApplicationNotFoundError):
            wired_service(
                store, evidence=FakeEvidenceLookup(),
            ).supply_evidence(CTX_A, record, EVIDENCE_A)

    def test_other_tenant_evidence_cannot_attach(self):
        store, records, _ = make_store()
        lookup = FakeEvidenceLookup(
            {(TENANT_A.tenant_id, EVIDENCE_A)})
        record_b = reviewable_record(store, records, CTX_B, CASE_ID)
        with self.assertRaises(ApplicationNotFoundError):
            wired_service(store, evidence=lookup).supply_evidence(
                CTX_B, record_b, EVIDENCE_A)
        record_a = reviewable_record(store, records, CTX_A, CASE_ID)
        supplied, _ = wired_service(
            store, evidence=lookup).supply_evidence(
                CTX_A, record_a, EVIDENCE_A)
        self.assertIn(str(EVIDENCE_A),
                      supplied["supplied_evidence_ids"])

    def test_store_validates_workflow_repository(self):
        with self.assertRaises(ApplicationValidationError):
            ComplianceResultStore(
                database=_DummyDatabase(),
                reports=_StubRepo(),
                analyses=_StubRepo(),
                traces=_StubRepo(),
                rounds=_StubRepo(),
                packages=_StubRepo(),
                workflows=SimpleNamespace(),
            )
        bare = ComplianceResultStore(
            database=_DummyDatabase(),
            reports=_StubRepo(),
            analyses=_StubRepo(),
            traces=_StubRepo(),
            rounds=_StubRepo(),
            packages=_StubRepo(),
        )
        # Without the boundary the store keeps the previous
        # client-held behavior: resolving returns the
        # validated submission and saving is a no-op.
        self.assertFalse(hasattr(bare, "_workflows")
                         and bare._workflows is not None)
        resolved = bare.resolve_authoritative_workflow(
            CTX_A, WorkflowApplicationService().start_workflow(
                CTX_A, CASE_ID, shipment_id=SHIPMENT_ID)[0])
        self.assertEqual(resolved.case_id, CASE_ID)
        self.assertIsNone(bare.save_workflow_record(
            CTX_A, resolved))


class Migration012StructureTests(unittest.TestCase):
    def test_migration_files_exist(self):
        self.assertTrue(UP_012.is_file())
        self.assertTrue(DOWN_012.is_file())

    def test_transaction_markers_balanced(self):
        for path in (UP_012, DOWN_012):
            text = path.read_text(encoding="utf-8")
            self.assertEqual(len(re.findall(r"^BEGIN;$", text, re.M)), 1)
            self.assertEqual(len(re.findall(r"^COMMIT;$", text, re.M)), 1)
            self.assertTrue(
                text.index("BEGIN;") < text.index("COMMIT;"))

    def test_up_creates_workflows_table_with_state_check(self):
        text = UP_012.read_text(encoding="utf-8")
        created = re.findall(
            r"CREATE TABLE IF NOT EXISTS (\S+)", text)
        self.assertEqual(
            tuple(created), ("xportra.compliance_workflows",))
        for state in ("created", "information_provided",
                      "evidence_pending",
                      "applicability_determined",
                      "analysis_available", "review_required",
                      "additional_evidence_requested",
                      "reanalysis_required",
                      "assessment_package_ready"):
            self.assertIn(f"'{state}'", text)
        self.assertIn("PRIMARY KEY (tenant_id, workflow_id)", text)
        self.assertIn("supplied_evidence_ids UUID[]", text)
        self.assertIn("open_requirements UUID[]", text)

    def test_down_removes_only_the_workflows_table(self):
        text = DOWN_012.read_text(encoding="utf-8")
        dropped = re.findall(r"DROP TABLE IF EXISTS (\S+);", text)
        self.assertEqual(
            dropped, ["xportra.compliance_workflows"])


if __name__ == "__main__":
    unittest.main()
