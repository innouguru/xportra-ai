"""The ingestion-job endpoints must serialize the registration record.

Registering a source creates an ingestion job with no artifact
(``artifact_id IS NULL``; migration 033). The job response model required
an artifact, so listing a newly registered source's jobs failed response
validation and returned HTTP 500 -- breaking the source page the moment
a source was registered. These tests go through the real endpoints.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from uuid import UUID

from fastapi.testclient import TestClient

from xportra.api import regulatory_admin
from xportra.api.app import create_app
from xportra.api.dependencies import global_staff_dependency

ACTOR = UUID("aaaaaaaa-0000-0000-0000-000000000001")
SOURCE_ID = UUID("33333333-0000-0000-0000-000000000003")
ARTIFACT_ID = UUID("22222222-0000-0000-0000-000000000002")
PLACEHOLDER_ID = UUID("11111111-0000-0000-0000-000000000001")
DOCUMENT_JOB_ID = UUID("44444444-0000-0000-0000-000000000004")


def _row(job_id, artifact_id):
    return {
        "id": job_id,
        "artifact_id": artifact_id,
        "source_id": SOURCE_ID,
        "status": "pending",
        "attempt_number": 1,
        "started_at": None,
        "completed_at": None,
        "error_details": None,
        "parser_version": "v1",
        "actor_user_id": ACTOR,
        "created_at": "2026-11-02T00:00:00+00:00",
        "updated_at": "2026-11-02T00:00:00+00:00",
    }


class FakeIntakeService:
    def __init__(self, rows):
        self.rows = rows

    def list_jobs(self, source_id):
        return list(self.rows)

    def get_job(self, job_id):
        return next((r for r in self.rows if r["id"] == job_id), None)


def _client(rows):
    app = create_app(services=SimpleNamespace(database=SimpleNamespace()))
    app.dependency_overrides[regulatory_admin._intake_service] = lambda: FakeIntakeService(rows)
    app.dependency_overrides[global_staff_dependency] = lambda: ACTOR
    return TestClient(app)


class JobResponseContractTests(TestCase):
    def test_listing_jobs_includes_the_registration_record(self):
        rows = [
            _row(PLACEHOLDER_ID, None),
            _row(DOCUMENT_JOB_ID, ARTIFACT_ID),
        ]
        response = _client(rows).get(f"/regulatory/sources/{SOURCE_ID}/ingestion-jobs")
        self.assertEqual(200, response.status_code, response.text)
        body = response.json()
        self.assertEqual(2, body["total"])
        by_id = {item["id"]: item for item in body["items"]}
        self.assertIsNone(by_id[str(PLACEHOLDER_ID)]["artifact_id"])
        self.assertEqual(str(ARTIFACT_ID), by_id[str(DOCUMENT_JOB_ID)]["artifact_id"])

    def test_listing_jobs_for_a_just_registered_source(self):
        # The exact state right after registration: one record, no document.
        response = _client([_row(PLACEHOLDER_ID, None)]).get(
            f"/regulatory/sources/{SOURCE_ID}/ingestion-jobs"
        )
        self.assertEqual(200, response.status_code, response.text)
        self.assertIsNone(response.json()["items"][0]["artifact_id"])

    def test_fetching_the_registration_record_by_id(self):
        response = _client([_row(PLACEHOLDER_ID, None)]).get(
            f"/regulatory/ingestion-jobs/{PLACEHOLDER_ID}"
        )
        self.assertEqual(200, response.status_code, response.text)
        self.assertIsNone(response.json()["artifact_id"])
