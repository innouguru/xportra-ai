"""Durable shipment listing/history reads (no new domain model).

Proves the server-backed discovery boundary composes
stored shipment rows with latest-workflow summaries —
tenant-scoped, newest-first, paginated — without a
database: a hand double implements the listing read
surface while the real ``ShipmentListingService``,
DTOs, and HTTP adapter run. Live-database round-trips
stay gated under ``DATABASE_URL`` in
``tests/integration/test_shipment_listing_postgresql.py``.

Scope honored: no aggregate, no migration, no state
machine change, no versioning/snapshots/FKs/delete
semantics; completion derives from workflow/package
terminality, never shipment ``locked``. No existing
test is modified.
"""

import unittest
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.application.context import ApplicationContext
from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
)
from xportra.application.shipments import ShipmentListingService
from xportra.domain.compliance_workflow import (
    WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY,
    WORKFLOW_STATE_CREATED,
    WORKFLOW_STATE_EVIDENCE_PENDING,
    ComplianceWorkflow,
    WorkflowAnalysisRound,
)
from xportra.domain.shipment import (
    SHIPMENT_STATUS_BOUND,
    SHIPMENT_STATUS_DRAFT,
    ShipmentService,
)
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
CASE_C = UUID("33333333-3333-3333-3333-333333333335")
SHIP_A = UUID("44444444-4444-4444-4444-444444444441")
SHIP_B = UUID("44444444-4444-4444-4444-444444444442")
SHIP_C = UUID("44444444-4444-4444-4444-444444444443")
UNKNOWN_SHIP = UUID("44444444-4444-4444-4444-444444444449")
REPORT_1 = UUID("55555555-5555-5555-5555-555555555551")


def make_shipment(tenant, shipment_id, case_id, product="Cocoa",
                  status=SHIPMENT_STATUS_BOUND):
    service = ShipmentService()
    draft = service.create(
        tenant_id=tenant, shipment_id=shipment_id,
        case_id=case_id, product=product,
        origin_country="Nigeria",
        destination_country="Netherlands")
    if status == SHIPMENT_STATUS_BOUND:
        return service.mark_bound(draft, tenant_id=tenant)
    return draft


def make_workflow(tenant, workflow_id, case_id, shipment_id,
                  state=WORKFLOW_STATE_CREATED, rounds=()):
    return ComplianceWorkflow(
        id=workflow_id,
        tenant_id=tenant.tenant_id,
        case_id=case_id,
        shipment_id=shipment_id,
        state=state,
        rounds=tuple(rounds),
        supplied_evidence_ids=(),
        open_requirements=(),
    )


def make_round(index=1):
    return WorkflowAnalysisRound(
        round_index=index,
        report_id=REPORT_1,
        analysis_ids=(),
        trace_ids=(),
        input_fingerprints=(),
    )


class FakeListingStore:
    """In-memory double for the shipment listing read surface."""

    def __init__(self):
        self.shipments = []
        self.workflows = {}
        self.packages = set()

    def add_shipment(self, shipment, created="2026-10-01T00:00:00",
                     tenant=None):
        self.shipments.append((shipment, created, tenant))

    def add_workflow(self, workflow):
        self.workflows.setdefault(
            (workflow.tenant_id, workflow.shipment_id),
            []).append(workflow)

    def add_package(self, workflow):
        self.packages.add((workflow.tenant_id, workflow.id))

    def _tenant_shipments(self, ctx):
        return [(shipment, created)
                for shipment, created, tenant in self.shipments
                if tenant is None or tenant.tenant_id == ctx.tenant_id]

    def list_shipments(self, ctx, limit, offset):
        rows = list(reversed(self._tenant_shipments(ctx)))
        rows = rows if limit is None else rows[:limit + offset]
        return [(shipment, {"created_at": created,
                            "updated_at": created})
                for shipment, created in rows[offset:]]

    def count_shipments(self, ctx):
        return len(self._tenant_shipments(ctx))

    def get_shipment_entry(self, ctx, shipment_id):
        for shipment, created, _ in self.shipments:
            if (shipment.shipment_id == shipment_id
                    and shipment.tenant_id == ctx.tenant_id):
                return (shipment, {"created_at": created,
                                   "updated_at": created})
        return None

    def list_workflows_for_shipment(self, ctx, shipment_id):
        return list(self.workflows.get(
            (ctx.tenant_id, shipment_id), []))

    def rounds_for_workflow(self, ctx, workflow_id):
        return []

    def load_package(self, ctx, workflow_id):
        if (ctx.tenant_id, workflow_id) in self.packages:
            return {"workflow_id": workflow_id}
        return None


def make_store():
    store = FakeListingStore()
    shipment_a = make_shipment(TENANT_A, SHIP_A, CASE_A)
    shipment_b = make_shipment(TENANT_A, SHIP_B, CASE_B)
    draft_c = make_shipment(
        TENANT_A, SHIP_C, CASE_C, status=SHIPMENT_STATUS_DRAFT)
    store.add_shipment(draft_c, created="2026-10-01T00:00:00",
                       tenant=TENANT_A)
    store.add_shipment(shipment_b, created="2026-10-02T00:00:00",
                       tenant=TENANT_A)
    store.add_shipment(shipment_a, created="2026-10-03T00:00:00",
                       tenant=TENANT_A)
    workflow_a = make_workflow(
        TENANT_A, UUID("66666666-6666-6666-6666-666666666661"),
        CASE_A, SHIP_A, state=WORKFLOW_STATE_EVIDENCE_PENDING,
        rounds=[make_round()])
    workflow_b = make_workflow(
        TENANT_A, UUID("66666666-6666-6666-6666-666666666662"),
        CASE_B, SHIP_B,
        state=WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY,
        rounds=[make_round()])
    store.add_workflow(workflow_a)
    store.add_workflow(workflow_b)
    store.add_package(workflow_b)
    return store


def service(store=None):
    return ShipmentListingService(
        result_store=store if store is not None else make_store())


class ShipmentListingTests(unittest.TestCase):
    def test_list_newest_first_with_summaries(self):
        dto = service().list_shipments(CTX_A)
        self.assertEqual(dto.total, 3)
        self.assertEqual(
            [item.shipment_id for item in dto.shipments],
            [str(SHIP_A), str(SHIP_B), str(SHIP_C)])
        first = dto.shipments[0]
        self.assertEqual(first.product, "Cocoa")
        self.assertEqual(first.origin_country, "Nigeria")
        self.assertEqual(
            first.destination_country, "Netherlands")
        self.assertIsNotNone(first.workflow)
        self.assertEqual(
            first.workflow.state, WORKFLOW_STATE_EVIDENCE_PENDING)
        self.assertFalse(first.workflow.is_closed)
        self.assertEqual(first.workflow.round_count, 1)
        self.assertEqual(
            first.workflow.latest_report_id, str(REPORT_1))
        self.assertEqual(first.workflow_count, 1)

    def test_draft_has_no_workflow(self):
        dto = service().list_shipments(CTX_A)
        draft = dto.shipments[2]
        self.assertIsNone(draft.workflow)
        self.assertIsNone(draft.workflow_record)
        self.assertEqual(draft.workflow_count, 0)
        self.assertEqual(draft.status, SHIPMENT_STATUS_DRAFT)

    def test_list_is_tenant_scoped(self):
        dto = service().list_shipments(CTX_B)
        self.assertEqual(dto.total, 0)
        self.assertEqual(dto.shipments, ())

    def test_pagination_slices_and_counts(self):
        dto = service().list_shipments(
            CTX_A, limit=1, offset=1)
        self.assertEqual(dto.total, 3)
        self.assertEqual(dto.limit, 1)
        self.assertEqual(dto.offset, 1)
        self.assertEqual(len(dto.shipments), 1)
        self.assertEqual(
            dto.shipments[0].shipment_id, str(SHIP_B))

    def test_pagination_rejected_when_malformed(self):
        listing = service()
        for limit in (0, -1, 101, "20", True):
            with self.assertRaises(ApplicationValidationError):
                listing.list_shipments(CTX_A, limit=limit)
        with self.assertRaises(ApplicationValidationError):
            listing.list_shipments(CTX_A, offset=-1)
        with self.assertRaises(ApplicationValidationError):
            listing.list_shipments(CTX_A, status="archived")

    def test_status_filter_uses_workflow_terminality(self):
        listing = service()
        completed = listing.list_shipments(
            CTX_A, status="completed")
        self.assertEqual(completed.total, 1)
        self.assertEqual(
            completed.shipments[0].shipment_id, str(SHIP_B))
        self.assertTrue(
            completed.shipments[0].workflow.is_closed)
        active = listing.list_shipments(CTX_A, status="active")
        self.assertEqual(active.total, 2)
        self.assertTrue(all(
            item.workflow is None or not item.workflow.is_closed
            for item in active.shipments))

    def test_terminal_without_package_is_not_completed(self):
        store = make_store()
        shipment = make_shipment(TENANT_A, UNKNOWN_SHIP, CASE_A)
        store.add_shipment(shipment, tenant=TENANT_A)
        dangling = make_workflow(
            TENANT_A,
            UUID("66666666-6666-6666-6666-666666666663"),
            CASE_A, UNKNOWN_SHIP,
            state=WORKFLOW_STATE_ASSESSMENT_PACKAGE_READY)
        store.add_workflow(dangling)
        listing = ShipmentListingService(result_store=store)
        completed = listing.list_shipments(
            CTX_A, status="completed")
        self.assertEqual(completed.total, 1)
        active = listing.list_shipments(CTX_A, status="active")
        self.assertEqual(active.total, 3)

    def test_bound_shipment_can_be_completed(self):
        dto = service().list_shipments(CTX_A, status="completed")
        item = dto.shipments[0]
        self.assertEqual(item.status, SHIPMENT_STATUS_BOUND)
        self.assertTrue(item.workflow.is_closed)

    def test_multiple_workflows_surface_count_and_latest(self):
        store = make_store()
        newer = make_workflow(
            TENANT_A,
            UUID("66666666-6666-6666-6666-666666666664"),
            CASE_C, SHIP_A, state=WORKFLOW_STATE_CREATED)
        store.workflows[(TENANT_A.tenant_id, SHIP_A)].insert(
            0, newer)
        item = ShipmentListingService(
            result_store=store).get_shipment(CTX_A, SHIP_A)
        self.assertEqual(item.workflow_count, 2)
        self.assertEqual(
            item.workflow.workflow_id, str(newer.id))

    def test_detail_found(self):
        item = service().get_shipment(CTX_A, SHIP_A)
        self.assertEqual(item.shipment_id, str(SHIP_A))
        self.assertEqual(item.case_id, str(CASE_A))
        self.assertIsNotNone(item.workflow_record)
        self.assertEqual(
            item.workflow_record["id"],
            item.workflow.workflow_id)

    def test_detail_unknown_is_not_found(self):
        with self.assertRaises(ApplicationNotFoundError):
            service().get_shipment(CTX_A, UNKNOWN_SHIP)

    def test_detail_cross_tenant_is_not_found(self):
        with self.assertRaises(ApplicationNotFoundError):
            service().get_shipment(CTX_B, SHIP_A)

    def test_unconfigured_store_fails_closed(self):
        listing = ShipmentListingService(result_store=None)
        with self.assertRaises(ApplicationValidationError):
            listing.list_shipments(CTX_A)
        with self.assertRaises(ApplicationValidationError):
            listing.get_shipment(CTX_A, SHIP_A)
        legacy = ShipmentListingService(
            result_store=SimpleNamespace())
        with self.assertRaises(ApplicationValidationError):
            legacy.list_shipments(CTX_A)


class ShipmentListingEndpointTests(unittest.TestCase):
    def _client(self, store=None):
        kept = store if store is not None else make_store()
        return TestClient(create_app(services=SimpleNamespace(
            rag=None, result_store=kept)))

    def test_list_returns_only_current_tenant(self):
        with self._client() as client:
            response = client.get(
                "/compliance/shipments", headers=HEADER_A)
            self.assertEqual(response.status_code, 200,
                             response.text)
            body = response.json()
            self.assertEqual(body["total"], 3)
            self.assertEqual(body["limit"], 20)
            self.assertEqual(body["offset"], 0)
            self.assertEqual(len(body["shipments"]), 3)
            empty = client.get(
                "/compliance/shipments", headers=HEADER_B)
            self.assertEqual(empty.status_code, 200)
            self.assertEqual(empty.json()["total"], 0)

    def test_list_pagination_and_filter(self):
        with self._client() as client:
            page = client.get(
                "/compliance/shipments?limit=1&offset=1",
                headers=HEADER_A)
            self.assertEqual(page.status_code, 200)
            body = page.json()
            self.assertEqual(body["total"], 3)
            self.assertEqual(len(body["shipments"]), 1)
            completed = client.get(
                "/compliance/shipments?status=completed",
                headers=HEADER_A)
            self.assertEqual(completed.status_code, 200)
            self.assertEqual(completed.json()["total"], 1)
            bad = client.get(
                "/compliance/shipments?limit=0", headers=HEADER_A)
            self.assertEqual(bad.status_code, 422)
            unknown_filter = client.get(
                "/compliance/shipments?status=archived",
                headers=HEADER_A)
            self.assertEqual(unknown_filter.status_code, 422)

    def test_detail_returns_shipment(self):
        with self._client() as client:
            response = client.get(
                f"/compliance/shipments/{SHIP_A}",
                headers=HEADER_A)
            self.assertEqual(response.status_code, 200,
                             response.text)
            body = response.json()
            self.assertEqual(body["shipment_id"], str(SHIP_A))
            self.assertEqual(body["product"], "Cocoa")
            self.assertIsNotNone(body["workflow"])
            self.assertEqual(
                body["workflow"]["latest_report_id"],
                str(REPORT_1))
            self.assertEqual(
                body["workflow"]["supplied_evidence_count"], 0)
            self.assertEqual(
                body["workflow"]["open_requirements_count"], 0)
            self.assertEqual(body["workflow"]["round_count"], 1)

    def test_detail_unknown_is_not_found(self):
        with self._client() as client:
            response = client.get(
                f"/compliance/shipments/{UNKNOWN_SHIP}",
                headers=HEADER_A)
            self.assertEqual(response.status_code, 404,
                             response.text)

    def test_detail_cross_tenant_is_not_found(self):
        with self._client() as client:
            response = client.get(
                f"/compliance/shipments/{SHIP_A}",
                headers=HEADER_B)
            self.assertEqual(response.status_code, 404,
                             response.text)

    def test_unwired_store_fails_closed_as_unavailable(self):
        unwired = TestClient(create_app(
            services=SimpleNamespace(rag=None, result_store=None)))
        with unwired as client:
            listing = client.get(
                "/compliance/shipments", headers=HEADER_A)
            self.assertEqual(listing.status_code, 503,
                             listing.text)
            detail = client.get(
                f"/compliance/shipments/{SHIP_A}",
                headers=HEADER_A)
            self.assertEqual(detail.status_code, 503,
                             detail.text)


if __name__ == "__main__":
    unittest.main()
