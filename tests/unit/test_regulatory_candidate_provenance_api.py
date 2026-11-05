"""Staff API contracts for regulatory candidate provenance."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest import TestCase
from uuid import UUID

from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.api.dependencies import global_staff_dependency, stage_a_dependency
from xportra.api.errors import PermissionDeniedError
from xportra.api.regulatory_admin import (
    _extraction_service,
    _stage_a_service,
)

ACTOR = UUID("aaaaaaaa-0000-0000-0000-000000000001")
SOURCE_ID = UUID("dddddddd-0000-0000-0000-000000000004")
ARTIFACT_ID = UUID("eeeeeeee-0000-0000-0000-000000000005")
DOCUMENT_ID = UUID("11111111-0000-0000-0000-000000000100")
JOB_ID = UUID("ffffffff-0000-0000-0000-000000000006")
CANDIDATE_ID = UUID("22222222-0000-0000-0000-000000000200")
RUN_ID = UUID("33333333-0000-0000-0000-000000000300")
NOW = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)
QUOTE = "Shall carry a phytosanitary certificate."

HISTORY = {
    "extraction_run_id": RUN_ID,
    "normalized_document_id": DOCUMENT_ID,
    "artifact_id": ARTIFACT_ID,
    "source_id": SOURCE_ID,
    "ingestion_job_id": JOB_ID,
    "artifact_content_hash": "a" * 64,
    "artifact_source_version": "2024-edition",
    "normalized_text_sha256": "b" * 64,
    "parser_version": "v1",
    "extraction_method": "llm_semantic_chunked",
    "extraction_version": "v1",
    "prompt_version": "regulatory-requirements-v1",
    "configured_model_identifier": "test/model",
    "model_identifiers": ["test/model"],
    "provider_names": [],
    "outcome": "succeeded",
    "failed_chunks": [],
    "rejected_candidate_count": 0,
    "started_at": NOW,
    "completed_at": NOW,
    "candidate_index": 0,
    "evidence_snapshot": {
        "requirement_text": QUOTE,
        "source_location": {
            "supporting_quote": QUOTE,
            "page_reference": 3,
            "section_reference": "Article 4",
        },
    },
    "resolution_status": "persisted",
    "is_origin": True,
}

CANDIDATE = {
    "id": CANDIDATE_ID,
    "source_id": SOURCE_ID,
    "artifact_id": ARTIFACT_ID,
    "normalized_document_id": DOCUMENT_ID,
    "requirement_text": QUOTE,
    "requirement_type": "documentation",
    "source_location": HISTORY["evidence_snapshot"]["source_location"],
    "position": 0,
    "actor": None,
    "status": "extracted",
    "extraction_outcome": "succeeded",
    "parser_version": "v1",
    "manual_entry": False,
    "reviewer_user_id": None,
    "reviewed_at": None,
    "ingestion_job_id": JOB_ID,
    "created_at": NOW,
    "updated_at": NOW,
    "source_title": "Test Regulation",
    "source_jurisdiction": "EU",
    "source_version": "1.0",
    "source_status": "active",
    "source_authority_id": None,
    "artifact_uri": "regulatory-source-artifacts/test/a",
    "artifact_content_hash": "a" * 64,
    "artifact_source_version": "2024-edition",
    "artifact_status": "validated",
    "artifact_content_length": 100,
    "artifact_content_type": "text/plain",
    "artifact_acquisition_channel": "manual_upload",
    "ingestion_job_status": "completed",
    "ingestion_job_error_details": None,
    "ingestion_job_parser_version": "v1",
    "document_parser_name": "plain-text-v1",
    "extraction_history": [HISTORY],
    "stage_a_status": "pending",
    "stage_a_reviewer_user_id": None,
    "stage_a_reviewed_at": None,
    "stage_a_rationale": None,
}


class FakeCandidateService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_candidate_with_provenance(self, candidate_id):
        self.calls.append("detail")
        return CANDIDATE if candidate_id == CANDIDATE_ID else None

    def list_artifacts_for_source(self, source_id):
        self.calls.append("artifacts")
        return [{"id": ARTIFACT_ID}] if source_id == SOURCE_ID else []

    def list_candidates_for_artifact(self, artifact_id):
        self.calls.append("candidates")
        if artifact_id != ARTIFACT_ID:
            return []
        candidate = dict(CANDIDATE)
        candidate["extraction_history"] = []
        return [candidate]


class FakeStageAService:
    def get_candidate_stage_a(self, candidate_id):
        return CANDIDATE if candidate_id == CANDIDATE_ID else None


def build_app(service: FakeCandidateService, staff_override=None):
    app = create_app(services=SimpleNamespace(database=object()))
    app.dependency_overrides[_extraction_service] = lambda: service
    app.dependency_overrides[global_staff_dependency] = (
        staff_override if staff_override is not None else (lambda: ACTOR)
    )
    return app


class CandidateProvenanceApiTests(TestCase):
    def test_candidate_detail_exposes_artifact_and_run_evidence(self):
        service = FakeCandidateService()
        with TestClient(build_app(service)) as client:
            response = client.get(
                f"/regulatory/candidates/{CANDIDATE_ID}"
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source_version"], "1.0")
        self.assertEqual(body["artifact_source_version"], "2024-edition")
        self.assertEqual(body["artifact_content_hash"], "a" * 64)
        self.assertEqual(body["document_parser_name"], "plain-text-v1")
        self.assertEqual(
            body["extraction_history"][0]["evidence_snapshot"][
                "source_location"
            ]["supporting_quote"],
            QUOTE,
        )

    def test_candidate_list_includes_available_provenance(self):
        service = FakeCandidateService()
        with TestClient(build_app(service)) as client:
            response = client.get(
                f"/regulatory/sources/{SOURCE_ID}/candidates"
            )

        self.assertEqual(response.status_code, 200)
        item = response.json()["items"][0]
        self.assertEqual(item["artifact_source_version"], "2024-edition")
        self.assertEqual(item["source_location"]["page_reference"], 3)
        self.assertEqual(item["extraction_history"], [])

    def test_unauthorized_candidate_request_remains_denied(self):
        service = FakeCandidateService()

        def denied():
            raise PermissionDeniedError()

        with TestClient(build_app(service, denied)) as client:
            response = client.get(
                f"/regulatory/candidates/{CANDIDATE_ID}"
            )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(service.calls, [])

    def test_stage_a_detail_schema_accepts_provenance_with_optional_fields(self):
        app = create_app(services=SimpleNamespace(database=object()))
        app.dependency_overrides[_stage_a_service] = (
            lambda: FakeStageAService()
        )
        app.dependency_overrides[stage_a_dependency] = lambda: ACTOR
        with TestClient(app) as client:
            response = client.get(
                f"/regulatory/candidates/{CANDIDATE_ID}/stage-a"
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            body["artifact_source_version"], "2024-edition"
        )
        self.assertEqual(
            body["extraction_history"][0]["extraction_run_id"],
            str(RUN_ID),
        )
