"""Focused tests for regulatory ingestion -> EvidenceDocument linkage.

No live database required for authorization/idempotency contracts;
DB-backed linkage tested against repository conventions only.
"""
from __future__ import annotations

from unittest import TestCase
from uuid import UUID, uuid4

from xportra.application.errors import ApplicationNotFoundError, ApplicationValidationError
from xportra.application.global_staff import GRANT_MANAGE
from xportra.application.regulatory_ingestion_evidence_linkage_service import RegulatoryIngestionEvidenceLinkService
from xportra.persistence.database import Database

ACTOR = UUID("aaaaaaaa-0000-0000-0000-000000000001")
SOURCE_ID = UUID("cccccccc-0000-0000-0000-000000000003")
ARTIFACT_ID = UUID("eeeeeeee-0000-0000-0000-000000000005")
JOB_ID = UUID("ffffffff-0000-0000-0000-000000000006")
DOCUMENT_VERSION = "1.0"


class FakeDB:
    def __init__(self):
        pass
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


class FakeJobRepo:
    def __init__(self, status="completed", artifact_id=ARTIFACT_ID, source_id=SOURCE_ID):
        self.status = status
        self.artifact_id = artifact_id
        self.source_id = source_id
    def get(self, job_id):
        if job_id == JOB_ID:
            return {
                "id": JOB_ID,
                "artifact_id": self.artifact_id,
                "source_id": self.source_id,
                "status": self.status,
                "parser_version": "v1",
                "actor_user_id": ACTOR,
            }
        return None


class FakeArtifactRepo:
    def __init__(self, source_id=SOURCE_ID, content_hash="abc123", source_version=DOCUMENT_VERSION):
        self.source_id = source_id
        self.content_hash = content_hash
        self.source_version = source_version
    def get(self, artifact_id):
        if artifact_id == ARTIFACT_ID:
            return {
                "id": ARTIFACT_ID,
                "source_id": self.source_id,
                "artifact_uri": "regulatory-source-artifacts/test",
                "content_hash": self.content_hash,
                "content_length": 100,
                "content_type": "text/plain",
                "status": "validated",
                "source_version": self.source_version,
            }
        return None


class FakeSourceRepo:
    def __init__(self, title="Test Regulation", version=DOCUMENT_VERSION):
        self.title = title
        self.version = version
    def get(self, source_id):
        if source_id == SOURCE_ID:
            return {
                "id": SOURCE_ID,
                "authority_id": UUID("cccccccc-0000-0000-0000-000000000003"),
                "jurisdiction": "EU",
                "title": self.title,
                "version": self.version,
                "status": "active",
                "supersedes_source_id": None,
                "superseded_by_source_id": None,
            }
        return None


class FakeNormalizationRepo:
    def __init__(self, has_normalization=True):
        self.has_normalization = has_normalization
    def get_by_artifact(self, artifact_id):
        if self.has_normalization and artifact_id == ARTIFACT_ID:
            return {
                "id": UUID("77777777-0000-0000-0000-000000000700"),
                "artifact_id": artifact_id,
                "normalized_text": "Shall be safe.",
                "document_title": "Test Regulation",
            }
        return None


class FakeEvidenceDocRepo:
    def __init__(self, existing=None):
        self.existing = existing
    def get_by_source_identity(self, tenant, source_id, version):
        return self.existing
    def create(self, record):
        return dict(record)


class LinkageTests(TestCase):
    def test_successful_linkage_creates_evidence_document(self):
        from xportra.persistence.tenant import TenantContext
        service = RegulatoryIngestionEvidenceLinkService(
            FakeDB(),
            job_repo=FakeJobRepo(status="completed"),
            artifact_repo=FakeArtifactRepo(),
            source_repo=FakeSourceRepo(),
            normalization_repo=FakeNormalizationRepo(has_normalization=True),
            evidence_doc_repo=FakeEvidenceDocRepo(existing=None),
            grant_service=FakeGrantRepo(granted=True),
        )
        tenant = TenantContext(UUID("bbbbbbbb-0000-0000-0000-000000000002"))
        result = service.link_ingestion_result_to_evidence_document(
            actor_user_id=ACTOR, job_id=JOB_ID, tenant=tenant
        )
        self.assertIn("id", result)
        self.assertEqual(result.get("status"), "active")

    def test_idempotent_retry_does_not_duplicate_document(self):
        from xportra.persistence.tenant import TenantContext
        existing_doc = {"id": UUID("88888888-0000-0000-0000-000000000800"), "status": "active"}
        service = RegulatoryIngestionEvidenceLinkService(
            FakeDB(),
            job_repo=FakeJobRepo(status="completed"),
            artifact_repo=FakeArtifactRepo(),
            source_repo=FakeSourceRepo(),
            normalization_repo=FakeNormalizationRepo(has_normalization=True),
            evidence_doc_repo=FakeEvidenceDocRepo(existing=existing_doc),
            grant_service=FakeGrantRepo(granted=True),
        )
        tenant = TenantContext(UUID("bbbbbbbb-0000-0000-0000-000000000002"))
        result = service.link_ingestion_result_to_evidence_document(
            actor_user_id=ACTOR, job_id=JOB_ID, tenant=tenant
        )
        self.assertEqual(result.get("id"), existing_doc["id"])

    def test_failed_job_is_denied_linkage(self):
        from xportra.persistence.tenant import TenantContext
        service = RegulatoryIngestionEvidenceLinkService(
            FakeDB(),
            job_repo=FakeJobRepo(status="failed"),
            artifact_repo=FakeArtifactRepo(),
            source_repo=FakeSourceRepo(),
            normalization_repo=FakeNormalizationRepo(has_normalization=True),
            evidence_doc_repo=FakeEvidenceDocRepo(),
            grant_service=FakeGrantRepo(granted=True),
        )
        tenant = TenantContext(UUID("bbbbbbbb-0000-0000-0000-000000000002"))
        with self.assertRaises(ApplicationValidationError) as ctx:
            service.link_ingestion_result_to_evidence_document(
                actor_user_id=ACTOR, job_id=JOB_ID, tenant=tenant
            )
        self.assertIn("not completed", str(ctx.exception))

    def test_missing_job_denied(self):
        from xportra.persistence.tenant import TenantContext
        service = RegulatoryIngestionEvidenceLinkService(
            FakeDB(),
            job_repo=FakeJobRepo(status="pending"),  # wrong job id
            artifact_repo=FakeArtifactRepo(),
            source_repo=FakeSourceRepo(),
            normalization_repo=FakeNormalizationRepo(has_normalization=True),
            evidence_doc_repo=FakeEvidenceDocRepo(),
            grant_service=FakeGrantRepo(granted=True),
        )
        tenant = TenantContext(UUID("bbbbbbbb-0000-0000-0000-000000000002"))
        # Using a non-existent job id
        with self.assertRaises(ApplicationNotFoundError):
            service.link_ingestion_result_to_evidence_document(
                actor_user_id=ACTOR,
                job_id=UUID("99999999-0000-0000-0000-000000000999"),
                tenant=tenant,
            )

    def test_unauthorized_denied(self):
        from xportra.persistence.tenant import TenantContext
        service = RegulatoryIngestionEvidenceLinkService(
            FakeDB(),
            job_repo=FakeJobRepo(),
            artifact_repo=FakeArtifactRepo(),
            source_repo=FakeSourceRepo(),
            normalization_repo=FakeNormalizationRepo(),
            evidence_doc_repo=FakeEvidenceDocRepo(),
            grant_service=FakeGrantRepo(granted=False),
        )
        tenant = TenantContext(UUID("bbbbbbbb-0000-0000-0000-000000000002"))
        with self.assertRaises(Exception):
            service.link_ingestion_result_to_evidence_document(
                actor_user_id=ACTOR, job_id=JOB_ID, tenant=tenant
            )

    def test_provenance_metadata_preserved(self):
        from xportra.persistence.tenant import TenantContext
        service = RegulatoryIngestionEvidenceLinkService(
            FakeDB(),
            job_repo=FakeJobRepo(status="completed"),
            artifact_repo=FakeArtifactRepo(),
            source_repo=FakeSourceRepo(),
            normalization_repo=FakeNormalizationRepo(has_normalization=True),
            evidence_doc_repo=FakeEvidenceDocRepo(),
            grant_service=FakeGrantRepo(granted=True),
        )
        tenant = TenantContext(UUID("bbbbbbbb-0000-0000-0000-000000000002"))
        result = service.link_ingestion_result_to_evidence_document(
            actor_user_id=ACTOR,
            job_id=JOB_ID,
            tenant=tenant,
            metadata_extra={"pilot_review": True},
        )
        meta = result.get("metadata", {})
        self.assertIn("artifact_id", meta)
        self.assertIn("content_hash", meta)
        self.assertIn("parser_version", meta)
        self.assertIn("ingestion_job_id", meta)
        self.assertEqual(meta.get("pilot_review"), True)
