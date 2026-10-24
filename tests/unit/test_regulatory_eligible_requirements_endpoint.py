"""Focused endpoint tests for regulatory eligible-requirements publication gate.

No live database required for authorization and schema contract;
repository-level verification relies on existing mock conventions.
"""
from __future__ import annotations

from unittest import TestCase
from uuid import UUID

from xportra.api.errors import PermissionDeniedError
from xportra.application.global_staff import GRANT_MANAGE
from xportra.application.regulatory_publication_eligibility_service import RegulatoryPublicationEligibilityService
from xportra.application.errors import ApplicationNotFoundError, ApplicationValidationError
from xportra.persistence.tenant import TenantContext
from xportra.api.schemas import RegulatoryEligibleRequirementsResponse

ACTOR = UUID("aaaaaaaa-0000-0000-0000-000000000001")
SOURCE_ID = UUID("cccccccc-0000-0000-0000-000000000003")
REQUIREMENT_ID = UUID("66666666-0000-0000-0000-000000000600")


class FakeDB:
    def __init__(self, rows=None):
        self._rows = rows or {}
    def connection(self):
        class Conn:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def cursor(self):
                class Cursor:
                    def __enter__(self): return self
                    def __exit__(self, *a): pass
                    def execute(self, sql, params=()): pass
                    def fetchone(self): return None
                    def fetchall(self): return []
                return Cursor()
        return Conn()
    def transaction(self):
        class Ctx:
            def __enter__(self): return self
            def __exit__(self, *a): pass
        return Ctx()


class FakeGrantRepo:
    def __init__(self, granted=True):
        self.granted = granted
    def is_granted(self, user_id, permission):
        return self.granted and user_id == ACTOR


class FakeRequirementRepo:
    def __init__(self, rows=None):
        self.rows = rows or {}
    def get(self, req_id):
        return self.rows.get(req_id)
    def get_eligible_for_publication(self, source_filter=None, pilot_scope_filter=None):
        eligible = []
        for row in self.rows.values():
            if row.get("status") != "extracted": continue
            if row.get("extraction_outcome") != "succeeded": continue
            if row.get("stage_a_status") != "verified": continue
            if row.get("stage_b_status") != "approved": continue
            if source_filter is not None and UUID(row.get("source_id", "")) != source_filter: continue
            if pilot_scope_filter is not None and row.get("stage_b_pilot_scope") != pilot_scope_filter: continue
            eligible.append(dict(row))
        return eligible


class FakeSourceRepo:
    def __init__(self, status="active"):
        self.status = status
    def get(self, source_id):
        if source_id == SOURCE_ID:
            return {"id": SOURCE_ID, "status": self.status, "version": "1.0", "title": "Test"}
        return None


class FakeFlagRepo:
    def __init__(self, flags=None):
        self.flags = flags or {}
    def list_pending_for_source(self, source_id):
        return [f for f in self.flags.get(str(source_id), []) if f.get("status") == "pending_review"]
    def get_for_requirement(self, req_id):
        return self.flags.get(str(req_id), [])


class FakeJobRepo:
    def __init__(self, status="completed"):
        self.status = status
    def get(self, job_id):
        return {"id": job_id, "status": self.status, "parser_version": "v1"}


class EndpointTests(TestCase):
    def _service(self, **kw):
        from xportra.persistence.tenant import TenantContext
        defaults = {
            "database": FakeDB(),
            "requirement_repo": FakeRequirementRepo({
                REQUIREMENT_ID: {
                    "id": REQUIREMENT_ID,
                    "normalized_document_id": UUID("77777777-0000-0000-0000-000000000700"),
                    "source_id": SOURCE_ID,
                    "status": "extracted",
                    "extraction_outcome": "succeeded",
                    "stage_a_status": "verified",
                    "stage_b_status": "approved",
                    "parser_version": "v1",
                    "ingestion_job_id": UUID("ffffffff-0000-0000-0000-000000000006"),
                    "stage_b_pilot_scope": "sesame-eu-pilot-v1",
                }
            }),
            "source_repo": FakeSourceRepo(status="active"),
            "review_flag_repo": FakeFlagRepo(flags={SOURCE_ID: [], str(REQUIREMENT_ID): []}),
            "job_repo": FakeJobRepo(status="completed"),
        }
        defaults.update(kw)
        return RegulatoryPublicationEligibilityService(**defaults)

    def test_eligible_endpoint_contract(self):
        service = self._service()
        tenant = TenantContext(UUID("bbbbbbbb-0000-0000-0000-000000000002"))
        eligible = service.get_eligible_requirements(tenant=tenant)
        ids = [r.get("id") for r in eligible]
        self.assertIn(REQUIREMENT_ID, ids)

    def test_ineligible_not_returned(self):
        service = self._service(
            requirement_repo=FakeRequirementRepo({
                REQUIREMENT_ID: {
                    "id": REQUIREMENT_ID,
                    "normalized_document_id": UUID("77777777-0000-0000-0000-000000000700"),
                    "source_id": SOURCE_ID,
                    "status": "extracted",
                    "extraction_outcome": "failed",
                    "stage_a_status": "verified",
                    "stage_b_status": "approved",
                    "parser_version": "v1",
                    "ingestion_job_id": UUID("ffffffff-0000-0000-0000-000000000006"),
                    "stage_b_pilot_scope": "sesame-eu-pilot-v1",
                }
            })
        )
        tenant = TenantContext(UUID("bbbbbbbb-0000-0000-0000-000000000002"))
        eligible = service.get_eligible_requirements(tenant=tenant)
        self.assertNotIn(REQUIREMENT_ID, [r.get("id") for r in eligible])
