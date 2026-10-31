"""Focused endpoint tests for POST /regulatory/ingestion-jobs/{id}/retry.

Verifies the authorized staff retry control contract: GRANT_MANAGE
authorization (fail-closed), 201 creation of a new pending attempt row,
structured 400 rejection for non-retryable/bound cases, 404 for missing
jobs, and the RegulatoryIngestionJobResponse contract. No live database
is contacted.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from uuid import UUID

from fastapi.testclient import TestClient

from xportra.api import regulatory_admin
from xportra.api.app import create_app
from xportra.api.dependencies import require_global_staff
from xportra.api.errors import PermissionDeniedError
from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
)

ACTOR = UUID("aaaaaaaa-0000-0000-0000-000000000001")
JOB_ID = UUID("11111111-0000-0000-0000-000000000001")
NEW_JOB_ID = UUID("55555555-0000-0000-0000-000000000005")
ARTIFACT_ID = UUID("22222222-0000-0000-0000-000000000002")
SOURCE_ID = UUID("33333333-0000-0000-0000-000000000003")

RETRIED_JOB_ROW = {
    "id": NEW_JOB_ID,
    "artifact_id": ARTIFACT_ID,
    "source_id": SOURCE_ID,
    "status": "pending",
    "attempt_number": 2,
    "started_at": None,
    "completed_at": None,
    "error_details": None,
    "parser_version": "v1",
    "actor_user_id": ACTOR,
    "created_at": "2026-10-31T00:00:00+00:00",
    "updated_at": "2026-10-31T00:00:00+00:00",
}


class FakeRetryService:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def retry_job(self, job_id, actor_user_id=None):
        self.calls.append({"job_id": job_id, "actor_user_id": actor_user_id})
        if self.error is not None:
            raise self.error
        return self.result


def build_app(database=None, retry_service=None, staff_override=None):
    app = create_app(
        services=SimpleNamespace(database=database if database is not None else SimpleNamespace())
    )
    app.dependency_overrides[
        regulatory_admin._ingestion_service
    ] = (lambda: retry_service)
    app.dependency_overrides[require_global_staff] = (
        staff_override if staff_override is not None else (lambda: ACTOR)
    )
    return app


class JobRetryEndpointTests(TestCase):
    def test_retry_creates_pending_attempt_for_staff(self):
        service = FakeRetryService(result=RETRIED_JOB_ROW)
        with TestClient(build_app(retry_service=service)) as client:
            response = client.post(f"/regulatory/ingestion-jobs/{JOB_ID}/retry")
        self.assertEqual(201, response.status_code)
        body = response.json()
        self.assertEqual(str(NEW_JOB_ID), body["id"])
        self.assertEqual("pending", body["status"])
        self.assertEqual(2, body["attempt_number"])
        self.assertEqual(str(ARTIFACT_ID), body["artifact_id"])
        self.assertEqual(str(ACTOR), body["actor_user_id"])
        self.assertEqual(
            [{"job_id": JOB_ID, "actor_user_id": ACTOR}], service.calls
        )

    def test_retry_denied_fail_closed_without_staff_grant(self):
        app = build_app(
            retry_service=FakeRetryService(result=RETRIED_JOB_ROW),
            staff_override=lambda: (_ for _ in ()).throw(PermissionDeniedError()),
        )
        with TestClient(app) as client:
            response = client.post(f"/regulatory/ingestion-jobs/{JOB_ID}/retry")
        self.assertEqual(403, response.status_code)
        self.assertEqual("permission_denied", response.json()["error"]["code"])

    def test_retry_missing_job_is_not_found(self):
        service = FakeRetryService(error=ApplicationNotFoundError("job gone"))
        with TestClient(build_app(retry_service=service)) as client:
            response = client.post(f"/regulatory/ingestion-jobs/{JOB_ID}/retry")
        self.assertEqual(404, response.status_code)
        self.assertEqual("not_found", response.json()["error"]["code"])

    def test_retry_non_retryable_or_bound_reached_is_invalid_input(self):
        for error in (
            ApplicationValidationError("only terminally failed job"),
            ApplicationValidationError("retry limit reached"),
        ):
            service = FakeRetryService(error=error)
            with TestClient(build_app(retry_service=service)) as client:
                response = client.post(f"/regulatory/ingestion-jobs/{JOB_ID}/retry")
            self.assertEqual(400, response.status_code)
            self.assertEqual("invalid_input", response.json()["error"]["code"])
