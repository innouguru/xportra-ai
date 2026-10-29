"""Focused tests for regulatory publication eligibility gate.

No live database required; uses repository-level contracts and
existing mock patterns from regulatory governance / stage tests.
"""
from __future__ import annotations

from unittest import TestCase
from uuid import UUID

from xportra.application.errors import ApplicationNotFoundError, ApplicationValidationError
from xportra.application.global_staff import GRANT_MANAGE
from xportra.application.regulatory_publication_eligibility_service import RegulatoryPublicationEligibilityService
from xportra.domain.errors import DomainValidationError
from xportra.persistence.tenant import TenantContext

ACTOR = UUID("aaaaaaaa-0000-0000-0000-000000000001")
SOURCE_ID = UUID("cccccccc-0000-0000-0000-000000000003")
REQUIREMENT_ID = UUID("66666666-0000-0000-0000-000000000600")
TENANT = UUID("bbbbbbbb-0000-0000-0000-000000000002")


class FakeDB:
    def __init__(self, rows_for_db=None):
        self._rows = rows_for_db or {}
    def connection(self):
        class Conn:
            def __enter__(self): return self
            def __exit__(self, *a): pass
            def cursor(self):
                class Cursor:
                    def __enter__(self): return self
                    def __exit__(self, *a): pass
                    def execute(self, sql, params=()):
                        pass
                    def fetchone(self):
                        return None
                    def fetchall(self):
                        return []
                return Cursor()
            def transaction(self):
                class Ctx:
                    def __enter__(self): return self
                    def __exit__(self, *a): pass
                return Ctx()
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
            if row.get("status") != "extracted":
                continue
            if row.get("extraction_outcome") != "succeeded":
                continue
            if row.get("stage_a_status") != "verified":
                continue
            if row.get("stage_b_status") != "approved":
                continue
            if source_filter is not None and UUID(row.get("source_id", "")) != source_filter:
                continue
            if pilot_scope_filter is not None and row.get("stage_b_pilot_scope") != pilot_scope_filter:
                continue
            eligible.append(dict(row))
        return eligible


class FakeSourceRepo:
    def __init__(self, active=True, superseded=False, withdrawn=False, status="active"):
        self.active = active
        self.superseded = superseded
        self.withdrawn = withdrawn
        self.status = status
    def get(self, source_id):
        if source_id == SOURCE_ID:
            return {
                "id": SOURCE_ID,
                "status": self.status,
                "version": "1.0",
                "title": "Test Regulation",
            }
        return None


class FakeFlagRepo:
    def __init__(self, flags=None):
        self.flags = flags or {}
    def list_pending_for_source(self, source_id):
        return [f for f in self.flags.get(source_id, []) if f.get("status") == "pending_review"]
    def get_for_requirement(self, requirement_id):
        return self.flags.get(str(requirement_id), [])


class FakeJobRepo:
    def __init__(self, status="completed"):
        self.status = status
    def get(self, job_id):
        return {"id": job_id, "status": self.status, "parser_version": "v1"}


class EligibilityTests(TestCase):
    def _service(self, **kwargs):
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
                    "ingestion_job_id": UUID("11111111-0000-0000-0000-000000000006"),
                    "stage_b_pilot_scope": "sesame-eu-pilot-v1",
                }
            }),
            "source_repo": FakeSourceRepo(status="active"),
            "review_flag_repo": FakeFlagRepo(flags={
                SOURCE_ID: [],
                str(REQUIREMENT_ID): [],
            }),
            "job_repo": FakeJobRepo(status="completed"),
        }
        defaults.update(kwargs)
        return RegulatoryPublicationEligibilityService(**defaults)

    def test_eligible_selection_passes_all_rules(self):
        service = self._service()
        tenant = TenantContext(TENANT)
        # Monkey-patch repository method for focused eligibility contract verification.
        def mock_eligible(source_filter=None, pilot_scope_filter=None):
            rows = self._service(
                requirement_repo=FakeRequirementRepo({
                    REQUIREMENT_ID: {
                        "id": REQUIREMENT_ID,
                        "normalized_document_id": UUID("77777777-0000-0000-0000-000000000700"),
                        "source_id": SOURCE_ID,
                        "status": "extracted",
                        "extraction_outcome": "succeeded",
                        "stage_a_status": "verified",
                        "stage_b_status": "approved",
                        "parser_version": "v1",
                        "ingestion_job_id": UUID("11111111-0000-0000-0000-000000000006"),
                        "stage_b_pilot_scope": "sesame-eu-pilot-v1",
                    }
                })
            )._requirement_repo.get_eligible_for_publication(
                source_filter=source_filter,
                pilot_scope_filter=pilot_scope_filter,
            )
            return rows
        service._requirement_repo.get_eligible_for_publication = mock_eligible
        eligible = service.get_eligible_requirements(tenant=tenant)
        ids = [r.get("id") for r in eligible]
        self.assertIn(REQUIREMENT_ID, ids)

    def test_eligible_single_check_true(self):
        service = self._service()
        tenant = TenantContext(TENANT)
        def mock_eligible(source_filter=None, pilot_scope_filter=None):
            return [
                {
                    "id": REQUIREMENT_ID,
                    "normalized_document_id": UUID("77777777-0000-0000-0000-000000000700"),
                    "source_id": SOURCE_ID,
                    "status": "extracted",
                    "extraction_outcome": "succeeded",
                    "stage_a_status": "verified",
                    "stage_b_status": "approved",
                    "parser_version": "v1",
                    "ingestion_job_id": UUID("11111111-0000-0000-0000-000000000006"),
                    "stage_b_pilot_scope": "sesame-eu-pilot-v1",
                }
            ]
        service._requirement_repo.get_eligible_for_publication = mock_eligible
        self.assertTrue(service.is_eligible(REQUIREMENT_ID, tenant=tenant))

    def test_ineligible_after_failed_extraction(self):
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
                    "ingestion_job_id": UUID("11111111-0000-0000-0000-000000000006"),
                    "stage_b_pilot_scope": "sesame-eu-pilot-v1",
                }
            })
        )
        tenant = TenantContext(TENANT)
        # Monkey-patch repository for focused contract verification.
        service._requirement_repo.get_eligible_for_publication = lambda **kw: []
        self.assertFalse(service.is_eligible(REQUIREMENT_ID, tenant=tenant))

    def test_ineligible_after_partial_extraction(self):
        service = self._service(
            requirement_repo=FakeRequirementRepo({
                REQUIREMENT_ID: {
                    "id": REQUIREMENT_ID,
                    "normalized_document_id": UUID("77777777-0000-0000-0000-000000000700"),
                    "source_id": SOURCE_ID,
                    "status": "extracted",
                    "extraction_outcome": "partial",
                    "stage_a_status": "verified",
                    "stage_b_status": "approved",
                    "parser_version": "v1",
                    "ingestion_job_id": UUID("11111111-0000-0000-0000-000000000006"),
                    "stage_b_pilot_scope": "sesame-eu-pilot-v1",
                }
            })
        )
        tenant = TenantContext(TENANT)
        service._requirement_repo.get_eligible_for_publication = lambda **kw: []
        self.assertFalse(service.is_eligible(REQUIREMENT_ID, tenant=tenant))

    def test_ineligible_when_stage_a_not_verified(self):
        service = self._service(
            requirement_repo=FakeRequirementRepo({
                REQUIREMENT_ID: {
                    "id": REQUIREMENT_ID,
                    "normalized_document_id": UUID("77777777-0000-0000-0000-000000000700"),
                    "source_id": SOURCE_ID,
                    "status": "extracted",
                    "extraction_outcome": "succeeded",
                    "stage_a_status": "pending",
                    "stage_b_status": "approved",
                    "parser_version": "v1",
                    "ingestion_job_id": UUID("11111111-0000-0000-0000-000000000006"),
                    "stage_b_pilot_scope": "sesame-eu-pilot-v1",
                }
            })
        )
        tenant = TenantContext(TENANT)
        service._requirement_repo.get_eligible_for_publication = lambda **kw: []
        eligible = service.get_eligible_requirements(tenant=tenant)
        self.assertNotIn(REQUIREMENT_ID, [r.get("id") for r in eligible])

    def test_ineligible_when_stage_b_not_approved(self):
        service = self._service(
            requirement_repo=FakeRequirementRepo({
                REQUIREMENT_ID: {
                    "id": REQUIREMENT_ID,
                    "normalized_document_id": UUID("77777777-0000-0000-0000-000000000700"),
                    "source_id": SOURCE_ID,
                    "status": "extracted",
                    "extraction_outcome": "succeeded",
                    "stage_a_status": "verified",
                    "stage_b_status": "pending",
                    "parser_version": "v1",
                    "ingestion_job_id": UUID("11111111-0000-0000-0000-000000000006"),
                    "stage_b_pilot_scope": "sesame-eu-pilot-v1",
                }
            })
        )
        tenant = TenantContext(TENANT)
        service._requirement_repo.get_eligible_for_publication = lambda **kw: []
        self.assertFalse(service.is_eligible(REQUIREMENT_ID, tenant=tenant))

    def test_ineligible_when_source_superseded(self):
        service = self._service(
            source_repo=FakeSourceRepo(status="superseded"),
        )
        tenant = TenantContext(TENANT)
        service._requirement_repo.get_eligible_for_publication = lambda **kw: []
        eligible = service.get_eligible_requirements(tenant=tenant)
        self.assertNotIn(REQUIREMENT_ID, [r.get("id") for r in eligible])

    def test_ineligible_when_pending_flag_on_source(self):
        service = self._service(
            review_flag_repo=FakeFlagRepo(flags={SOURCE_ID: [{"status": "pending_review", "trigger_type": "supersession"}]}),
        )
        tenant = TenantContext(TENANT)
        eligible = service.get_eligible_requirements(tenant=tenant)
        service._requirement_repo.get_eligible_for_publication = lambda **kw: []
        self.assertNotIn(REQUIREMENT_ID, [r.get("id") for r in eligible])

    def test_ineligible_when_pending_flag_on_requirement(self):
        service = self._service(
            review_flag_repo=FakeFlagRepo(flags={str(REQUIREMENT_ID): [{"status": "pending_review", "trigger_type": "version_change"}]}),
        )
        tenant = TenantContext(TENANT)
        service._requirement_repo.get_eligible_for_publication = lambda **kw: []
        eligible = service.get_eligible_requirements(tenant=tenant)
        self.assertNotIn(REQUIREMENT_ID, [r.get("id") for r in eligible])

    def test_ineligible_when_provenance_missing(self):
        # Requirement with missing normalized_document_id or incomplete ingestion reference is excluded.
        service = self._service(
            requirement_repo=FakeRequirementRepo({
                REQUIREMENT_ID: {
                    "id": REQUIREMENT_ID,
                    "normalized_document_id": None,
                    "source_id": SOURCE_ID,
                    "status": "extracted",
                    "extraction_outcome": "succeeded",
                    "stage_a_status": "verified",
                    "stage_b_status": "approved",
                    "parser_version": "v1",
                    "ingestion_job_id": UUID("11111111-0000-0000-0000-000000000006"),
                    "stage_b_pilot_scope": "sesame-eu-pilot-v1",
                }
            })
        )
        tenant = TenantContext(TENANT)
        service._requirement_repo.get_eligible_for_publication = lambda **kw: []
        eligible = service.get_eligible_requirements(tenant=tenant)
        self.assertNotIn(REQUIREMENT_ID, [r.get("id") for r in eligible])

    # ---------------------------------------------------------------- check_eligibility

    def test_check_eligibility_eligible_with_empty_reasons(self):
        service = self._service()
        eligible, reasons = service.check_eligibility(REQUIREMENT_ID)
        self.assertTrue(eligible)
        self.assertEqual(reasons, [])

    def test_check_eligibility_ineligible_failed_extraction(self):
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
                    "ingestion_job_id": UUID("11111111-0000-0000-0000-000000000006"),
                    "stage_b_pilot_scope": "sesame-eu-pilot-v1",
                }
            })
        )
        eligible, reasons = service.check_eligibility(REQUIREMENT_ID)
        self.assertFalse(eligible)
        self.assertTrue(any("extraction outcome" in r for r in reasons))

    def test_check_eligibility_ineligible_stage_a_not_verified(self):
        service = self._service(
            requirement_repo=FakeRequirementRepo({
                REQUIREMENT_ID: {
                    "id": REQUIREMENT_ID,
                    "normalized_document_id": UUID("77777777-0000-0000-0000-000000000700"),
                    "source_id": SOURCE_ID,
                    "status": "extracted",
                    "extraction_outcome": "succeeded",
                    "stage_a_status": "pending",
                    "stage_b_status": "approved",
                    "parser_version": "v1",
                    "ingestion_job_id": UUID("11111111-0000-0000-0000-000000000006"),
                    "stage_b_pilot_scope": "sesame-eu-pilot-v1",
                }
            })
        )
        eligible, reasons = service.check_eligibility(REQUIREMENT_ID)
        self.assertFalse(eligible)
        self.assertTrue(any("Stage A" in r for r in reasons))

    def test_check_eligibility_ineligible_stage_b_not_approved(self):
        service = self._service(
            requirement_repo=FakeRequirementRepo({
                REQUIREMENT_ID: {
                    "id": REQUIREMENT_ID,
                    "normalized_document_id": UUID("77777777-0000-0000-0000-000000000700"),
                    "source_id": SOURCE_ID,
                    "status": "extracted",
                    "extraction_outcome": "succeeded",
                    "stage_a_status": "verified",
                    "stage_b_status": "pending",
                    "parser_version": "v1",
                    "ingestion_job_id": UUID("11111111-0000-0000-0000-000000000006"),
                    "stage_b_pilot_scope": "sesame-eu-pilot-v1",
                }
            })
        )
        eligible, reasons = service.check_eligibility(REQUIREMENT_ID)
        self.assertFalse(eligible)
        self.assertTrue(any("Stage B" in r for r in reasons))

    def test_check_eligibility_ineligible_source_superseded(self):
        service = self._service(
            source_repo=FakeSourceRepo(status="superseded"),
        )
        eligible, reasons = service.check_eligibility(REQUIREMENT_ID)
        self.assertFalse(eligible)
        self.assertTrue(any("source status" in r for r in reasons))

    def test_check_eligibility_ineligible_pending_flag(self):
        service = self._service(
            review_flag_repo=FakeFlagRepo(flags={
                str(REQUIREMENT_ID): [{"status": "pending_review", "trigger_type": "version_change"}]
            }),
        )
        eligible, reasons = service.check_eligibility(REQUIREMENT_ID)
        self.assertFalse(eligible)
        self.assertTrue(any("pending governance" in r for r in reasons))

    def test_check_eligibility_ineligible_missing_provenance(self):
        service = self._service(
            requirement_repo=FakeRequirementRepo({
                REQUIREMENT_ID: {
                    "id": REQUIREMENT_ID,
                    "normalized_document_id": None,
                    "source_id": SOURCE_ID,
                    "status": "extracted",
                    "extraction_outcome": "succeeded",
                    "stage_a_status": "verified",
                    "stage_b_status": "approved",
                    "parser_version": "v1",
                    "ingestion_job_id": None,
                    "stage_b_pilot_scope": "sesame-eu-pilot-v1",
                }
            })
        )
        eligible, reasons = service.check_eligibility(REQUIREMENT_ID)
        self.assertFalse(eligible)
        self.assertTrue(any("provenance" in r.lower() for r in reasons))

    def test_check_eligibility_requirement_not_found(self):
        service = self._service()
        eligible, reasons = service.check_eligibility(
            UUID("99999999-0000-0000-0000-000000000999")
        )
        self.assertFalse(eligible)
        self.assertTrue(any("not found" in r for r in reasons))

    def test_is_eligible_delegates_to_check_eligibility(self):
        service = self._service()
        self.assertTrue(service.is_eligible(REQUIREMENT_ID))
        # Ineligible case
        service2 = self._service(
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
                    "ingestion_job_id": UUID("11111111-0000-0000-0000-000000000006"),
                    "stage_b_pilot_scope": "sesame-eu-pilot-v1",
                }
            })
        )
        self.assertFalse(service2.is_eligible(REQUIREMENT_ID))
