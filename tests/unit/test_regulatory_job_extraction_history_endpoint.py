"""Staff API contract for read-only job extraction history."""

from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from uuid import UUID

from fastapi.testclient import TestClient

from xportra.api import regulatory_admin
from xportra.api.app import create_app
from xportra.api.dependencies import global_staff_dependency
from xportra.api.errors import PermissionDeniedError
from xportra.application.errors import ApplicationNotFoundError

ACTOR = UUID("aaaaaaaa-0000-0000-0000-000000000001")
JOB_ID = UUID("11111111-0000-0000-0000-000000000001")
RUN_ID = UUID("22222222-0000-0000-0000-000000000002")
SOURCE_ID = UUID("33333333-0000-0000-0000-000000000003")
ARTIFACT_ID = UUID("44444444-0000-0000-0000-000000000004")
DOCUMENT_ID = UUID("55555555-0000-0000-0000-000000000005")
REQUIREMENT_ID = UUID("66666666-0000-0000-0000-000000000006")

HISTORY = {
    "job_id": JOB_ID,
    "items": [
        {
            "extraction_run_id": RUN_ID,
            "normalized_document_id": DOCUMENT_ID,
            "artifact_id": ARTIFACT_ID,
            "source_id": SOURCE_ID,
            "ingestion_job_id": JOB_ID,
            "artifact_content_hash": "artifact-hash",
            "artifact_source_version": "2026-01",
            "normalized_text_sha256": "a" * 64,
            "parser_version": "v1",
            "extraction_method": "llm_semantic_chunked",
            "extraction_version": "v1",
            "prompt_version": "requirements-v1",
            "configured_model_identifier": "model-id",
            "model_identifiers": ["model-id"],
            "provider_names": ["provider-name"],
            "outcome": "partial",
            "failed_chunks": [{"reason": "provider_unavailable"}],
            "rejected_candidate_count": 1,
            "started_at": "2026-11-01T10:00:00+00:00",
            "completed_at": "2026-11-01T10:01:00+00:00",
            "candidate_count": 1,
            "persisted_candidate_count": 1,
            "candidates": [
                {
                    "candidate_index": 0,
                    "candidate_id": REQUIREMENT_ID,
                    "evidence_snapshot": {
                        "requirement_text": "Must retain the exact quotation.",
                        "source_location": {
                            "supporting_quote": "Must retain the exact quotation.",
                            "page_reference": 2,
                            "reference_status": {
                                "page": "verified",
                                "section": "not_returned_by_model",
                            },
                        },
                    },
                    "resolution_status": "persisted",
                    "is_origin": True,
                }
            ],
        },
        {
            "extraction_run_id": UUID(
                "77777777-0000-0000-0000-000000000007"
            ),
            "normalized_document_id": DOCUMENT_ID,
            "artifact_id": ARTIFACT_ID,
            "source_id": SOURCE_ID,
            "ingestion_job_id": JOB_ID,
            "artifact_content_hash": "artifact-hash",
            "artifact_source_version": "2026-01",
            "normalized_text_sha256": "a" * 64,
            "parser_version": "v1",
            "extraction_method": "llm_semantic_chunked",
            "extraction_version": "v1",
            "prompt_version": "requirements-v1",
            "configured_model_identifier": "model-id",
            "model_identifiers": ["model-id"],
            "provider_names": ["provider-name"],
            "outcome": "succeeded",
            "failed_chunks": [],
            "rejected_candidate_count": 0,
            "started_at": "2026-11-01T11:00:00+00:00",
            "completed_at": "2026-11-01T11:01:00+00:00",
            "candidate_count": 0,
            "persisted_candidate_count": 0,
            "candidates": [],
        },
    ],
}


class FakeExtractionService:
    def __init__(self, history=None, missing=False):
        self.history = history
        self.missing = missing

    def get_job_extraction_history(self, job_id):
        if self.missing:
            return None
        return self.history


def build_app(service, staff_override=None):
    app = create_app(services=SimpleNamespace(database=SimpleNamespace()))
    app.dependency_overrides[regulatory_admin._extraction_service] = (
        lambda: service
    )
    app.dependency_overrides[global_staff_dependency] = (
        staff_override if staff_override is not None else (lambda: ACTOR)
    )
    return app


class JobExtractionHistoryEndpointTests(TestCase):
    def test_staff_can_read_partial_and_empty_persisted_runs(self):
        with TestClient(build_app(FakeExtractionService(HISTORY))) as client:
            response = client.get(
                f"/regulatory/ingestion-jobs/{JOB_ID}/extraction-history"
            )

        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual(str(JOB_ID), body["job_id"])
        partial, empty = body["items"]
        self.assertEqual("partial", partial["outcome"])
        self.assertEqual(1, partial["candidate_count"])
        self.assertEqual(
            "Must retain the exact quotation.",
            partial["candidates"][0]["evidence_snapshot"][
                "source_location"
            ]["supporting_quote"],
        )
        self.assertEqual(0, empty["candidate_count"])
        self.assertEqual([], empty["candidates"])

    def test_non_staff_access_is_denied(self):
        app = build_app(
            FakeExtractionService(HISTORY),
            staff_override=lambda: (_ for _ in ()).throw(
                PermissionDeniedError()
            ),
        )
        with TestClient(app) as client:
            response = client.get(
                f"/regulatory/ingestion-jobs/{JOB_ID}/extraction-history"
            )
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error"]["code"])

    def test_unknown_job_is_not_found(self):
        service = FakeExtractionService(missing=True)
        with TestClient(build_app(service)) as client:
            response = client.get(
                f"/regulatory/ingestion-jobs/{JOB_ID}/extraction-history"
            )
        self.assertEqual(404, response.status_code)
        self.assertEqual("not_found", response.json()["error"]["code"])
