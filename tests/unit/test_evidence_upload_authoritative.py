"""Authoritative terminal check for evidence uploads.

Proves the upload terminal-workflow guard resolves the
server-owned workflow row instead of trusting the
submitted snapshot: a stale non-terminal snapshot for
a finalized workflow fails closed before any storage
or database mutation, while a stale terminal snapshot
for an open workflow defers to the server (server
wins). Unwired deployments keep the previous
snapshot-only behavior. No existing test is modified.
"""

import unittest
import zlib
from contextlib import contextmanager
from uuid import UUID

from xportra.application.context import ApplicationContext
from xportra.application.errors import (
    ApplicationNotFoundError,
    TerminalWorkflowError,
)
from xportra.application.evidence_upload import (
    EvidenceUploadApplicationService,
)
from xportra.application.result_store import ComplianceResultStore
from xportra.domain.compliance_workflow import (
    WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY,
    WORKFLOW_STATE_EVIDENCE_PENDING,
)
from xportra.persistence.tenant import TenantContext

TENANT_A = TenantContext(UUID("11111111-1111-1111-1111-111111111111"))
CTX_A = ApplicationContext(
    actor_id=None, tenant=TENANT_A, role="owner")
CASE_A = UUID("33333333-3333-3333-3333-333333333333")
WORKFLOW_A = UUID("44444444-4444-4444-4444-444444444444")
EVIDENCE_ID = UUID("55555555-5555-5555-5555-555555555555")

PDF_BYTES = (
    b"%PDF-1.4\n1 0 obj\n<< /Length 11 >>\nstream\n"
    + zlib.compress(b"certificate text")
    + b"\nendstream\nendobj\ntrailer\n<<>>\n"
)


def workflow_record(state, workflow_id=WORKFLOW_A):
    return {
        "id": str(workflow_id),
        "tenant_id": str(TENANT_A.tenant_id),
        "case_id": str(CASE_A),
        "shipment_id": None,
        "state": state,
        "rounds": [],
        "supplied_evidence_ids": [],
        "open_requirements": [],
    }


class _DummyDatabase:
    @contextmanager
    def transaction(self):
        yield object()


class _StubRepo:
    def create_in_transaction(self, *args, **kwargs):
        raise AssertionError("unexpected repository write")


class FakeWorkflowRecordsRepo:
    """Stored workflow rows keyed by tenant + workflow."""

    def __init__(self, rows=None):
        self.rows = dict(rows or {})

    def create_in_transaction(
        self, connection, tenant, workflow_id, case_id,
        shipment_id, state,
    ):
        key = (tenant.tenant_id, workflow_id)
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
        return None if row is None else dict(row)

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
    def list_for_workflow(self, tenant, workflow_id):
        return []


class FakeEvidenceService:
    def __init__(self):
        self.rows = {}
        self.registered = []

    def register_upload(self, tenant, *, evidence_id, **values):
        self.registered.append(evidence_id)
        row = {"id": evidence_id,
               "tenant_id": tenant.tenant_id, **values}
        row.setdefault("status", "uploaded")
        row.setdefault("processing_status", "uploaded")
        self.rows[evidence_id] = row
        return dict(row)

    def find_by_content_hash(self, tenant, content_hash):
        return None

    def set_processing_state(self, tenant, evidence_id, **kwargs):
        row = self.rows.get(evidence_id)
        if row is None:
            return None
        row.update(kwargs)
        return dict(row)

    def get(self, tenant, evidence_id):
        return None

    def associate_requirement(self, tenant, evidence_id,
                              requirement_id):
        return {"evidence_id": evidence_id,
                "requirement_id": requirement_id}


class FakeCorpusIngestion:
    def ingest(self, **kwargs):
        return {"id": UUID(int=1), "tenant_id": kwargs.get(
            "tenant_id"), "status": "ingested"}


class FakeIndexSync:
    def __init__(self):
        self.calls = []

    def sync(self, document, *, tenant_id):
        self.calls.append(document)
        return {"status": "complete"}


class FakeStorage:
    def __init__(self):
        self.puts = []

    def put(self, key, content, content_type):
        self.puts.append(key)

    def delete(self, key):
        pass

    def create_signed_url(self, key, **kwargs):
        return "https://example.test/signed"


def make_store(rows=None):
    return ComplianceResultStore(
        database=_DummyDatabase(),
        reports=_StubRepo(),
        analyses=_StubRepo(),
        traces=_StubRepo(),
        rounds=FakeRoundsRepo(),
        packages=_StubRepo(),
        workflows=FakeWorkflowRecordsRepo(rows),
    )


def stored_row(state):
    return {
        "tenant_id": TENANT_A.tenant_id,
        "workflow_id": WORKFLOW_A,
        "case_id": CASE_A,
        "shipment_id": None,
        "state": state,
        "supplied_evidence_ids": [],
        "open_requirements": [],
    }


def make_service(store=None):
    evidence = FakeEvidenceService()
    service = EvidenceUploadApplicationService(
        evidence_service=evidence,
        corpus_ingestion=FakeCorpusIngestion(),
        index_sync=FakeIndexSync(),
        storage=FakeStorage(),
        result_store=store,
    )
    return service, service._storage, evidence


def upload(service, record):
    return service.upload_evidence(
        CTX_A,
        filename="certificate.pdf",
        content_type="application/pdf",
        content=PDF_BYTES,
        workflow_record=record,
    )


class AuthoritativeTerminalTests(unittest.TestCase):
    def test_stale_open_snapshot_against_finalized_row_rejected(
            self):
        store = make_store(
            {(TENANT_A.tenant_id, WORKFLOW_A): stored_row(
                WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY)})
        service, storage, evidence = make_service(store)
        with self.assertRaises(TerminalWorkflowError):
            upload(service, workflow_record(
                WORKFLOW_STATE_EVIDENCE_PENDING))
        self.assertEqual(storage.puts, [])
        self.assertEqual(evidence.registered, [])

    def test_stale_terminal_snapshot_against_open_row_allowed(
            self):
        store = make_store(
            {(TENANT_A.tenant_id, WORKFLOW_A): stored_row(
                WORKFLOW_STATE_EVIDENCE_PENDING)})
        service, storage, evidence = make_service(store)
        dto = upload(service, workflow_record(
            WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY))
        self.assertTrue(dto.evidence_id)
        self.assertEqual(len(storage.puts), 1)
        self.assertEqual(len(evidence.registered), 1)

    def test_unknown_workflow_row_fails_closed(self):
        store = make_store()
        service, storage, evidence = make_service(store)
        with self.assertRaises(ApplicationNotFoundError):
            upload(service, workflow_record(
                WORKFLOW_STATE_EVIDENCE_PENDING))
        self.assertEqual(storage.puts, [])
        self.assertEqual(evidence.registered, [])

    def test_unwired_store_keeps_snapshot_behavior(self):
        service, storage, evidence = make_service(None)
        with self.assertRaises(TerminalWorkflowError):
            upload(service, workflow_record(
                WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY))
        dto = upload(service, workflow_record(
            WORKFLOW_STATE_EVIDENCE_PENDING))
        self.assertTrue(dto.evidence_id)
        self.assertEqual(len(storage.puts), 1)

    def test_upload_without_workflow_unaffected(self):
        store = make_store()
        service, storage, evidence = make_service(store)
        dto = service.upload_evidence(
            CTX_A,
            filename="certificate.pdf",
            content_type="application/pdf",
            content=PDF_BYTES,
        )
        self.assertTrue(dto.evidence_id)


if __name__ == "__main__":
    unittest.main()
