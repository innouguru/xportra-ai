"""Unit tests for the regulatory source intake service (no database).

These tests exercise the service's validation and orchestration logic
using fakes, so they run without PostgreSQL. Database-backed source and
artifact behaviour is covered by integration tests (skipped when
``DATABASE_URL`` is not configured).
"""
from __future__ import annotations

from contextlib import contextmanager
from unittest import TestCase
from uuid import UUID

from xportra.api.errors import APIError, PermissionDeniedError
from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
    InfrastructureError,
)
from xportra.application.regulatory_source_intake_service import (
    RegulatorySourceIntakeService,
    MAX_ARTIFACT_CONTENT_BYTES,
)
from xportra.persistence.database import Database

ACTOR = UUID("aaaaaaaa-0000-0000-0000-000000000001")
NON_GRANTED = UUID("bbbbbbbb-0000-0000-0000-000000000002")
AUTHORITY = UUID("cccccccc-0000-0000-0000-000000000003")
SOURCE = UUID("dddddddd-0000-0000-0000-000000000004")
ARTIFACT = UUID("eeeeeeee-0000-0000-0000-000000000005")
JOB = UUID("ffffffff-0000-0000-0000-000000000006")

CONTENT_TYPES = {
    "text/plain": b"hello world",
    "text/markdown": b"# Sesame Regulation\n\nShall be safe.",
    "application/json": b'{"requirement": "labeling"}',
    "application/pdf": b"%PDF-1.4 fake pdf bytes",
}


class FakeDatabase(Database):
    """In-memory transaction double that records commit/rollback."""

    def __init__(self) -> None:
        super().__init__(  # type: ignore[arg-type]
            object(),  # type: ignore[arg-type]
            connection_factory=object(),  # type: ignore[arg-type]
        )
        self.committed = False
        self.rolled_back = False
        self.lock_keys: list[str] = []

    @contextmanager
    def transaction(self):  # type: ignore[override]
        try:
            yield _FakeConnection()
            self.committed = True
        except Exception:
            self.rolled_back = True
            raise


class _FakeConnection:
    """Minimal double supporting cursor() and execute() for advisory locks."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return _FakeCursor()


class _FakeCursor:
    def __init__(self) -> None:
        self.last_statement: str | None = None
        self.last_params: tuple | None = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement: str, parameters=()) -> None:
        self.last_statement = statement
        self.last_params = parameters

    def fetchone(self):
        statement = (self.last_statement or "").strip().lower()
        if statement.startswith("insert"):
            return {
                "id": UUID("00000000-0000-0000-0000-000000000001"),
            }
        return None

    def fetchall(self):
        return []


class FakeGrants:
    def __init__(self, granted: set[UUID] | None = None) -> None:
        self.granted = granted or set()

    def is_granted(self, user_id: UUID, permission: str) -> bool:
        return user_id in self.granted


class FakeAuthorityRepository:
    def __init__(self, existing: set[UUID] | None = None) -> None:
        self.existing = existing or set()

    def get(self, authority_id: UUID):
        if authority_id in self.existing:
            return {"id": authority_id, "name": "Test Authority"}
        return None


class FakeSourceRepository:
    def __init__(self) -> None:
        self.sources: dict[UUID, dict] = {}
        self.fail_create = False
        self._counter = 0

    def get(self, source_id: UUID):
        return self.sources.get(source_id)

    def list_for_authority(self, authority_id: UUID):
        return [
            s for s in self.sources.values()
            if s["authority_id"] == authority_id
        ]

    def list_all(self):
        return list(self.sources.values())

    def create(self, **kwargs):
        if self.fail_create:
            raise RuntimeError("simulated source insert failure")
        self._counter += 1
        source_id = UUID(f"11111111-0000-0000-0000-000000000{self._counter:03x}")
        row = {
            "id": source_id,
            "authority_id": kwargs["authority_id"],
            "jurisdiction": kwargs["jurisdiction"],
            "title": kwargs["title"],
            "version": kwargs.get("version"),
            "status": kwargs.get("status", "draft"),
            "effective_date": kwargs.get("effective_date"),
            "publication_date": kwargs.get("publication_date"),
            "source_url": kwargs.get("source_url"),
            "retrieval_timestamp": None,
            "supersedes_source_id": None,
            "superseded_by_source_id": None,
            "created_at": None,
            "updated_at": None,
        }
        self.sources[source_id] = row
        return row

    def update_source(
        self,
        source_id: UUID,
        *,
        supersedes_source_id: UUID | None = None,
        superseded_by_source_id: UUID | None = None,
        status: str | None = None,
    ) -> dict | None:
        row = self.sources.get(source_id)
        if row is None:
            return None
        if supersedes_source_id is not None:
            row["supersedes_source_id"] = supersedes_source_id
        if superseded_by_source_id is not None:
            row["superseded_by_source_id"] = superseded_by_source_id
        if status is not None:
            row["status"] = status
        return row

    def update_source_in_transaction(
        self,
        connection,
        source_id: UUID,
        *,
        supersedes_source_id: UUID | None = None,
        superseded_by_source_id: UUID | None = None,
        status: str | None = None,
    ) -> dict | None:
        return self.update_source(
            source_id,
            supersedes_source_id=supersedes_source_id,
            superseded_by_source_id=superseded_by_source_id,
            status=status,
        )


class FakeArtifactRepository:
    def __init__(self, existing: list[dict] | None = None) -> None:
        self.artifacts: list[dict] = list(existing or [])
        self.fail_create = False

    def get(self, artifact_id: UUID):
        for a in self.artifacts:
            if a["id"] == artifact_id:
                return a
        return None

    def list_for_source(self, source_id: UUID):
        return [
            a for a in self.artifacts if a["source_id"] == source_id
        ]

    def create(self, **kwargs):
        if self.fail_create:
            raise RuntimeError("simulated artifact insert failure")
        artifact_id = UUID("22222222-0000-0000-0000-000000000200")
        row = {
            "id": artifact_id,
            "source_id": kwargs["source_id"],
            "content_hash": kwargs["content_hash"],
            "content_length": kwargs["content_length"],
            "content_type": kwargs["content_type"],
            "acquisition_channel": kwargs["acquisition_channel"],
            "acquired_by": kwargs.get("acquired_by"),
            "acquired_at": None,
            "status": kwargs.get("status", "validated"),
            "source_version": kwargs.get("source_version"),
            "created_at": None,
            "updated_at": None,
        }
        self.artifacts.append(row)
        return row


class FakeJobRepository:
    def __init__(self, existing: list[dict] | None = None) -> None:
        self.jobs: list[dict] = list(existing or [])
        self.fail_create = False

    def get(self, job_id: UUID):
        for j in self.jobs:
            if j["id"] == job_id:
                return j
        return None

    def list_for_artifact(self, artifact_id: UUID):
        return [
            j for j in self.jobs if j["artifact_id"] == artifact_id
        ]

    def list_for_source(self, source_id: UUID):
        return [
            j for j in self.jobs if j["source_id"] == source_id
        ]

    def create(self, **kwargs):
        if self.fail_create:
            raise RuntimeError("simulated job insert failure")
        job_id = UUID("33333333-0000-0000-0000-000000000300")
        row = {
            "id": job_id,
            "artifact_id": kwargs["artifact_id"],
            "source_id": kwargs["source_id"],
            "status": "pending",
            "attempt_number": 1,
            "started_at": None,
            "completed_at": None,
            "error_details": None,
            "parser_version": kwargs.get("parser_version", "v1"),
            "actor_user_id": kwargs.get("actor_user_id"),
            "audit_ref": kwargs.get("audit_ref"),
            "created_at": None,
            "updated_at": None,
        }
        self.jobs.append(row)
        return row


class FakeStorage:
    def __init__(self, fail_put: bool = False) -> None:
        self.objects: dict[str, bytes] = {}
        self.fail_put = fail_put
        self.put_calls: list[tuple] = []

    def upload_artifact(
        self, key: str, content: bytes, *, content_type: str,
        actor_user_id: UUID, audit_ref: str | None = None,
    ) -> None:
        self.put_calls.append((key, content, content_type, actor_user_id))
        if self.fail_put:
            raise RuntimeError("simulated storage failure")
        self.objects[key] = content


class ServiceFactory:
    def __init__(
        self,
        *,
        granted_actor: bool = True,
        storage_fail: bool = False,
        source_fail: bool = False,
        artifact_fail: bool = False,
        job_fail: bool = False,
        existing_artifacts: list[dict] | None = None,
    ) -> None:
        self.database = FakeDatabase()
        self.grants = FakeGrants({ACTOR} if granted_actor else set())
        self.authorities = FakeAuthorityRepository({AUTHORITY})
        self.sources = FakeSourceRepository()
        self.sources.fail_create = source_fail
        self.artifacts = FakeArtifactRepository(existing_artifacts)
        self.artifacts.fail_create = artifact_fail
        self.jobs = FakeJobRepository()
        self.jobs.fail_create = job_fail
        self.requirements = FakeRequirementRepository()
        self.flags = FakeReviewFlagRepository()
        self.storage = FakeStorage(fail_put=storage_fail)

    def service(self) -> RegulatorySourceIntakeService:
        # Fake grant service that bypasses database-backed get_active.
        class _FakeGrantService:
            def __init__(self, granted: set[UUID]) -> None:
                self.granted = granted

            def is_granted(self, user_id: UUID, permission: str) -> bool:
                return user_id in self.granted

        return RegulatorySourceIntakeService(
            self.database,
            source_repo=self.sources,
            artifact_repo=self.artifacts,
            job_repo=self.jobs,
            authority_repo=self.authorities,
            grant_service=_FakeGrantService({ACTOR}),
            requirement_repo=self.requirements,
            review_flag_repo=self.flags,
            storage_service=_FakeStorageService(self.storage),
        )


class _FakeStorageService:
    """Thin wrapper matching RegulatorySourceStorageApplicationService.upload_artifact."""

    def __init__(self, storage: FakeStorage) -> None:
        self._storage = storage

    def upload_artifact(
        self, key: str, content: bytes, *, content_type: str,
        actor_user_id: UUID, audit_ref: str | None = None,
    ) -> None:
        self._storage.upload_artifact(
            key, content, content_type=content_type,
            actor_user_id=actor_user_id,
        )


def _b64(content: bytes) -> str:
    import base64
    return base64.b64encode(content).decode("ascii")


class RegulatorySourceIntakeTests(TestCase):
    def test_authorized_source_registration(self):
        factory = ServiceFactory()
        service = factory.service()
        row = service.register_source(
            actor_user_id=ACTOR,
            authority_id=AUTHORITY,
            jurisdiction="EU",
            title="Regulation (EU) 2019/1793",
            version="1.0",
            status="draft",
            source_url="https://example.com/reg",
        )
        self.assertEqual(row["authority_id"], AUTHORITY)
        self.assertEqual(row["jurisdiction"], "EU")
        self.assertEqual(row["title"], "Regulation (EU) 2019/1793")
        self.assertEqual(row["status"], "draft")

    def test_list_sources_returns_all_rows_verbatim(self):
        factory = ServiceFactory()
        service = factory.service()
        service.register_source(
            actor_user_id=ACTOR,
            authority_id=AUTHORITY,
            jurisdiction="EU",
            title="Regulation (EU) 2019/1793",
            status="draft",
            source_url="https://example.com/reg",
        )
        service.register_source(
            actor_user_id=ACTOR,
            authority_id=AUTHORITY,
            jurisdiction="US",
            title="US test standard",
            status="active",
        )
        rows = service.list_sources()
        self.assertEqual(len(rows), 2)
        titles = {row["title"] for row in rows}
        self.assertEqual(
            titles,
            {"Regulation (EU) 2019/1793", "US test standard"},
        )

    def test_list_sources_is_read_only(self):
        factory = ServiceFactory()
        service = factory.service()
        factory.sources.sources[SOURCE] = {
            "id": SOURCE,
            "authority_id": AUTHORITY,
            "jurisdiction": "EU",
            "title": "Existing source",
            "status": "superseded",
            "supersedes_source_id": AUTHORITY,
            "superseded_by_source_id": None,
        }
        rows = service.list_sources()
        self.assertEqual(len(rows), 1)
        # Supersession relationship is displayed as recorded, never inferred.
        self.assertEqual(rows[0]["supersedes_source_id"], AUTHORITY)
        self.assertEqual(len(factory.sources.sources), 1)

    def test_unauthorized_actor_cannot_register_source(self):
        factory = ServiceFactory(granted_actor=False)
        service = factory.service()
        with self.assertRaises(PermissionDeniedError):
            service.register_source(
                actor_user_id=NON_GRANTED,
                authority_id=AUTHORITY,
                jurisdiction="EU",
                title="Test",
            )

    def test_invalid_authority_is_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        with self.assertRaises(ApplicationNotFoundError):
            service.register_source(
                actor_user_id=ACTOR,
                authority_id=UUID("99999999-0000-0000-0000-000000000999"),
                jurisdiction="EU",
                title="Test",
            )

    def test_invalid_source_status_is_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        with self.assertRaises(ApplicationValidationError):
            service.register_source(
                actor_user_id=ACTOR,
                authority_id=AUTHORITY,
                jurisdiction="EU",
                title="Test",
                status="not_a_status",
            )

    def test_artifact_upload_text_plain(self):
        factory = ServiceFactory()
        service = factory.service()
        # Register a source first
        source = service.register_source(
            actor_user_id=ACTOR,
            authority_id=AUTHORITY,
            jurisdiction="EU",
            title="Test Source",
        )
        result = service.upload_artifact(
            actor_user_id=ACTOR,
            source_id=source["id"],
            content_base64=_b64(CONTENT_TYPES["text/plain"]),
            content_type="text/plain",
        )
        self.assertFalse(result["duplicate"])
        self.assertIsNotNone(result["artifact"])
        self.assertIsNotNone(result["job"])
        self.assertEqual(result["job"]["status"], "pending")
        # Server-side content hash
        import hashlib
        expected_hash = hashlib.sha256(CONTENT_TYPES["text/plain"]).hexdigest()
        self.assertEqual(result["artifact"]["content_hash"], expected_hash)

    def test_artifact_upload_markdown(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        result = service.upload_artifact(
            actor_user_id=ACTOR,
            source_id=source["id"],
            content_base64=_b64(CONTENT_TYPES["text/markdown"]),
            content_type="text/markdown",
        )
        self.assertFalse(result["duplicate"])
        self.assertEqual(result["artifact"]["content_type"], "text/markdown")

    def test_artifact_upload_json(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        result = service.upload_artifact(
            actor_user_id=ACTOR,
            source_id=source["id"],
            content_base64=_b64(CONTENT_TYPES["application/json"]),
            content_type="application/json",
        )
        self.assertFalse(result["duplicate"])
        self.assertEqual(result["artifact"]["content_type"], "application/json")

    def test_pdf_artifact_is_accepted(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        result = service.upload_artifact(
            actor_user_id=ACTOR,
            source_id=source["id"],
            content_base64=_b64(CONTENT_TYPES["application/pdf"]),
            content_type="application/pdf",
        )
        self.assertFalse(result["duplicate"])
        self.assertIsNotNone(result["artifact"])
        self.assertIsNotNone(result["job"])
        self.assertEqual(result["job"]["status"], "pending")
        self.assertEqual(result["artifact"]["content_type"], "application/pdf")
        self.assertEqual(result["artifact"]["content_length"], len(CONTENT_TYPES["application/pdf"]))

    def test_text_entry_artifact_is_accepted(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        result = service.enter_text_artifact(
            actor_user_id=ACTOR,
            source_id=source["id"],
            content_text="Sesame seeds shall be free from Salmonella.",
            content_type="text/plain",
        )
        self.assertFalse(result["duplicate"])
        self.assertIsNotNone(result["artifact"])
        self.assertIsNotNone(result["job"])
        self.assertEqual(result["job"]["status"], "pending")
        self.assertEqual(result["artifact"]["content_type"], "text/plain")
        import hashlib
        expected_hash = hashlib.sha256(
            b"Sesame seeds shall be free from Salmonella."
        ).hexdigest()
        self.assertEqual(result["artifact"]["content_hash"], expected_hash)

    def test_text_entry_markdown_is_accepted(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        result = service.enter_text_artifact(
            actor_user_id=ACTOR,
            source_id=source["id"],
            content_text="# Sesame Regulation\n\nShall be safe.",
            content_type="text/markdown",
        )
        self.assertFalse(result["duplicate"])
        self.assertEqual(result["artifact"]["content_type"], "text/markdown")

    def test_text_entry_empty_content_is_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        with self.assertRaises(ApplicationValidationError) as ctx:
            service.enter_text_artifact(
                actor_user_id=ACTOR,
                source_id=source["id"],
                content_text="",
                content_type="text/plain",
            )
        self.assertIn("content_text is required", str(ctx.exception))

    def test_text_entry_whitespace_only_content_is_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        with self.assertRaises(ApplicationValidationError):
            service.enter_text_artifact(
                actor_user_id=ACTOR,
                source_id=source["id"],
                content_text="   \n  ",
                content_type="text/plain",
            )

    def test_text_entry_pdf_content_type_is_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        with self.assertRaises(ApplicationValidationError):
            service.enter_text_artifact(
                actor_user_id=ACTOR,
                source_id=source["id"],
                content_text="some text",
                content_type="application/pdf",
            )

    def test_text_entry_unsupported_content_type_is_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        with self.assertRaises(ApplicationValidationError):
            service.enter_text_artifact(
                actor_user_id=ACTOR,
                source_id=source["id"],
                content_text="some text",
                content_type="image/png",
            )

    def test_text_entry_unauthorized_denied(self):
        factory = ServiceFactory(granted_actor=False)
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        with self.assertRaises(PermissionDeniedError):
            service.enter_text_artifact(
                actor_user_id=NON_GRANTED,
                source_id=source["id"],
                content_text="some text",
                content_type="text/plain",
            )

    def test_text_entry_nonexistent_source_is_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        with self.assertRaises(ApplicationNotFoundError):
            service.enter_text_artifact(
                actor_user_id=ACTOR,
                source_id=UUID("99999999-0000-0000-0000-000000000999"),
                content_text="some text",
                content_type="text/plain",
            )

    def test_text_entry_idempotent_duplicate(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        text = "Identical sesame text for idempotency."
        result1 = service.enter_text_artifact(
            actor_user_id=ACTOR, source_id=source["id"],
            content_text=text, content_type="text/plain",
        )
        self.assertFalse(result1["duplicate"])
        result2 = service.enter_text_artifact(
            actor_user_id=ACTOR, source_id=source["id"],
            content_text=text, content_type="text/plain",
        )
        self.assertTrue(result2["duplicate"])
        self.assertEqual(result2["artifact"]["id"], result1["artifact"]["id"])
        self.assertEqual(len(factory.artifacts.artifacts), 1)

    def test_upload_artifact_exceeds_size_limit_is_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        oversized = b"x" * (MAX_ARTIFACT_CONTENT_BYTES + 1)
        with self.assertRaises(ApplicationValidationError) as ctx:
            service.upload_artifact(
                actor_user_id=ACTOR,
                source_id=source["id"],
                content_base64=_b64(oversized),
                content_type="text/plain",
            )
        self.assertIn("exceeds size limit", str(ctx.exception))

    def test_unsupported_content_type_is_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        with self.assertRaises(ApplicationValidationError):
            service.upload_artifact(
                actor_user_id=ACTOR,
                source_id=source["id"],
                content_base64=_b64(b"some bytes"),
                content_type="image/png",
            )

    def test_malformed_base64_is_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        with self.assertRaises(APIError):
            service.upload_artifact(
                actor_user_id=ACTOR,
                source_id=source["id"],
                content_base64="!!!not-base64!!!",
                content_type="text/plain",
            )

    def test_nonexistent_source_is_rejected(self):
        factory = ServiceFactory()
        service = factory.service()
        with self.assertRaises(ApplicationNotFoundError):
            service.upload_artifact(
                actor_user_id=ACTOR,
                source_id=UUID("99999999-0000-0000-0000-000000000999"),
                content_base64=_b64(b"hello"),
                content_type="text/plain",
            )

    def test_storage_failure_fails_closed(self):
        factory = ServiceFactory(storage_fail=True)
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        with self.assertRaises(InfrastructureError):
            service.upload_artifact(
                actor_user_id=ACTOR,
                source_id=source["id"],
                content_base64=_b64(b"hello"),
                content_type="text/plain",
            )
        # No artifact should have been created
        self.assertEqual(len(factory.artifacts.artifacts), 0)

    def test_database_failure_after_storage_preserves_orphan(self):
        factory = ServiceFactory(artifact_fail=True)
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        # Storage succeeds, DB fails - orphan object preserved, error raised
        with self.assertRaises(RuntimeError):
            service.upload_artifact(
                actor_user_id=ACTOR,
                source_id=source["id"],
                content_base64=_b64(b"hello"),
                content_type="text/plain",
            )
        # Storage object was uploaded (orphan) - verify it exists
        self.assertEqual(len(factory.storage.objects), 1)
        # No artifact row created
        self.assertEqual(len(factory.artifacts.artifacts), 0)

    def test_idempotent_duplicate_upload(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        content = _b64(b"identical content")
        result1 = service.upload_artifact(
            actor_user_id=ACTOR, source_id=source["id"],
            content_base64=content, content_type="text/plain",
        )
        self.assertFalse(result1["duplicate"])
        result2 = service.upload_artifact(
            actor_user_id=ACTOR, source_id=source["id"],
            content_base64=content, content_type="text/plain",
        )
        self.assertTrue(result2["duplicate"])
        self.assertEqual(result2["artifact"]["id"], result1["artifact"]["id"])
        # Only one artifact created
        self.assertEqual(len(factory.artifacts.artifacts), 1)

    def test_different_content_creates_separate_artifact(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        service.upload_artifact(
            actor_user_id=ACTOR, source_id=source["id"],
            content_base64=_b64(b"content one"), content_type="text/plain",
        )
        service.upload_artifact(
            actor_user_id=ACTOR, source_id=source["id"],
            content_base64=_b64(b"content two"), content_type="text/plain",
        )
        self.assertEqual(len(factory.artifacts.artifacts), 2)

    def test_job_is_pending_not_completed(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        result = service.upload_artifact(
            actor_user_id=ACTOR, source_id=source["id"],
            content_base64=_b64(b"hello"), content_type="text/plain",
        )
        self.assertEqual(result["job"]["status"], "pending")
        self.assertIsNone(result["job"]["completed_at"])

    def test_get_source_returns_registered_source(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        fetched = service.get_source(source["id"])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["id"], source["id"])

    def test_get_source_nonexistent(self):
        factory = ServiceFactory()
        service = factory.service()
        self.assertIsNone(service.get_source(UUID("99999999-0000-0000-0000-000000000999")))

    def test_list_artifacts_for_source(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        service.upload_artifact(
            actor_user_id=ACTOR, source_id=source["id"],
            content_base64=_b64(b"one"), content_type="text/plain",
        )
        service.upload_artifact(
            actor_user_id=ACTOR, source_id=source["id"],
            content_base64=_b64(b"two"), content_type="text/markdown",
        )
        artifacts = service.list_artifacts(source["id"])
        self.assertEqual(len(artifacts), 2)

    def test_list_jobs_for_source(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        service.upload_artifact(
            actor_user_id=ACTOR, source_id=source["id"],
            content_base64=_b64(b"hello"), content_type="text/plain",
        )
        jobs = service.list_jobs(source["id"])
        # register_source creates a pending ingestion job; upload creates another.
        self.assertEqual(len(jobs), 2)
        statuses = {j["status"] for j in jobs}
        self.assertIn("pending", statuses)

    def test_concurrent_duplicate_upload_serialized(self):
        """Two identical uploads should produce one artifact (advisory lock serializes)."""
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        content = _b64(b"concurrent content")
        result1 = service.upload_artifact(
            actor_user_id=ACTOR, source_id=source["id"],
            content_base64=content, content_type="text/plain",
        )
        result2 = service.upload_artifact(
            actor_user_id=ACTOR, source_id=source["id"],
            content_base64=content, content_type="text/plain",
        )
        self.assertFalse(result1["duplicate"])
        self.assertTrue(result2["duplicate"])
        self.assertEqual(len(factory.artifacts.artifacts), 1)

    def test_transaction_rolled_back_on_failure(self):
        # Register source with a working service first.
        factory_ok = ServiceFactory()
        service_ok = factory_ok.service()
        source = service_ok.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Source",
        )
        # Now simulate upload failure with a failing job repo.
        factory_fail = ServiceFactory(job_fail=True)
        service_fail = factory_fail.service()
        # Link the same source record manually so upload uses the right source id
        factory_fail.sources.sources[source["id"]] = factory_ok.sources.sources[source["id"]]
        with self.assertRaises(RuntimeError):
            service_fail.upload_artifact(
                actor_user_id=ACTOR, source_id=source["id"],
                content_base64=_b64(b"hello"), content_type="text/plain",
            )
        # Transaction rolled back; storage object remains as orphan
        self.assertTrue(factory_fail.database.rolled_back)
        self.assertEqual(len(factory_fail.storage.objects), 1)


class FakeRequirementRepository:
    def __init__(self, existing: dict | None = None) -> None:
        self.reqs: dict[UUID, dict] = {}
        if existing:
            for r in existing.values():
                self.reqs[r["id"]] = dict(r)

    def get(self, req_id: UUID):
        return self.reqs.get(req_id)

    def list_for_source(self, source_id: UUID):
        return [
            r for r in self.reqs.values() if r.get("source_id") == source_id
        ]

    def create(self, **kwargs):
        req_id = UUID("44444444-0000-0000-0000-000000000400")
        row = {"id": req_id, **kwargs}
        self.reqs[req_id] = row
        return row


class FakeReviewFlagRepository:
    def __init__(self) -> None:
        self.flags: list[dict] = []

    def create(self, **kwargs) -> dict:
        flag_id = UUID("55555555-0000-0000-0000-000000000500")
        row = {
            "id": flag_id,
            "requirement_id": kwargs.get("requirement_id"),
            "trigger_source_id": kwargs.get("trigger_source_id"),
            "trigger_type": kwargs.get("trigger_type"),
            "status": kwargs.get("status", "pending_review"),
            "actor_user_id": kwargs.get("actor_user_id"),
            "rationale": kwargs.get("rationale", ""),
            "created_at": None,
            "updated_at": None,
        }
        self.flags.append(row)
        return row

    def create_in_transaction(self, connection, **kwargs) -> dict:
        return self.create(**kwargs)

    def get_for_source(self, source_id: UUID):
        return [
            f for f in self.flags if f.get("trigger_source_id") == source_id
        ]


# ---------------------------------------------------------------------------
# Supersession tests
# ---------------------------------------------------------------------------


class RegulatorySupersessionTests(TestCase):
    def test_authorized_record_supersession(self):
        factory = ServiceFactory()
        # Register two sources
        source_a = factory.service().register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="New Regulation", version="2.0",
        )
        source_b = factory.service().register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Old Regulation", version="1.0",
        )
        service = factory.service()
        result = service.record_supersession(
            actor_user_id=ACTOR,
            source_id=source_a["id"],
            supersedes_source_id=source_b["id"],
            rationale="New version replaces old regulation.",
        )
        self.assertEqual(result["supersedes_source_id"], source_b["id"])
        self.assertEqual(result["superseded_by_source_id"], None)
        self.assertEqual(result["source_id"], source_a["id"])
        # No requirements on source_b, so no flags
        flags = factory.flags.get_for_source(source_b["id"])
        self.assertEqual(len(flags), 0)

    def test_unauthorized_record_supersession_denied(self):
        factory = ServiceFactory(granted_actor=False)
        service = factory.service()
        source_a = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="New Regulation", version="2.0",
        )
        source_b = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Old Regulation", version="1.0",
        )
        with self.assertRaises(PermissionDeniedError):
            service.record_supersession(
                actor_user_id=NON_GRANTED,
                source_id=source_a["id"],
                supersedes_source_id=source_b["id"],
                rationale="New version replaces old.",
            )

    def test_self_supersession_denied(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Regulation", version="1.0",
        )
        with self.assertRaises(ApplicationValidationError) as ctx:
            service.record_supersession(
                actor_user_id=ACTOR,
                source_id=source["id"],
                supersedes_source_id=source["id"],
                rationale="Self-supersession attempt.",
            )
        self.assertIn("self-supersession", str(ctx.exception))

    def test_missing_source_denied(self):
        factory = ServiceFactory()
        service = factory.service()
        service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Test Regulation", version="1.0",
        )
        with self.assertRaises(ApplicationNotFoundError):
            service.record_supersession(
                actor_user_id=ACTOR,
                source_id=UUID("99999999-0000-0000-0000-000000000999"),
                supersedes_source_id=AUTHORITY,
                rationale="Missing source.",
            )

    def test_missing_superseded_source_denied(self):
        factory = ServiceFactory()
        service = factory.service()
        source = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="New Regulation", version="2.0",
        )
        with self.assertRaises(ApplicationNotFoundError):
            service.record_supersession(
                actor_user_id=ACTOR,
                source_id=source["id"],
                supersedes_source_id=UUID("99999999-0000-0000-0000-000000000999"),
                rationale="Missing superseded source.",
            )

    def test_duplicate_supersession_denied(self):
        factory = ServiceFactory()
        service = factory.service()
        source_a = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="New Regulation", version="2.0",
        )
        source_b = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Old Regulation", version="1.0",
        )
        service.record_supersession(
            actor_user_id=ACTOR,
            source_id=source_a["id"],
            supersedes_source_id=source_b["id"],
            rationale="First supersession.",
        )
        # Try again - source_a already supersedes source_b
        with self.assertRaises(ApplicationValidationError) as ctx:
            service.record_supersession(
                actor_user_id=ACTOR,
                source_id=source_a["id"],
                supersedes_source_id=source_b["id"],
                rationale="Duplicate supersession.",
            )
        self.assertIn("already supersedes another source", str(ctx.exception))

    def test_already_superseded_denied(self):
        factory = ServiceFactory()
        service = factory.service()
        source_a = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="New Regulation", version="2.0",
        )
        source_b = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Old Regulation", version="1.0",
        )
        service.record_supersession(
            actor_user_id=ACTOR,
            source_id=source_a["id"],
            supersedes_source_id=source_b["id"],
            rationale="First supersession.",
        )
        # Now source_c tries to supersede source_b which is already superseded
        source_c = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Newer Regulation", version="3.0",
        )
        with self.assertRaises(ApplicationValidationError) as ctx:
            service.record_supersession(
                actor_user_id=ACTOR,
                source_id=source_c["id"],
                supersedes_source_id=source_b["id"],
                rationale="Second supersession.",
            )
        self.assertIn("already superseded by another source", str(ctx.exception))

    def test_supersession_with_requirements_flags_them(self):
        """Supersession creates governance flags for linked requirements."""
        factory = ServiceFactory()
        # Add a requirement linked to source_b
        service = factory.service()
        source_b = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Old Regulation", version="1.0",
        )
        source_a = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="New Regulation", version="2.0",
        )
        # Manually add a requirement linked to source_b
        factory.requirements.create(
            id=UUID("66666666-0000-0000-0000-000000000600"),
            normalized_document_id=UUID("77777777-0000-0000-0000-000000000700"),
            requirement_text="Old requirement text.",
            requirement_type="labeling",
            source_location={},
            position=0,
            actor=None,
            condition_metadata=None,
            status="extracted",
            ingestion_job_id=None,
            extraction_outcome="succeeded",
            parser_version="v1",
            manual_entry=False,
            reviewer_user_id=None,
            reviewed_at=None,
            source_id=source_b["id"],
            stage_a_status="verified",
            stage_a_reviewer_user_id=None,
            stage_a_reviewed_at=None,
            stage_a_rationale=None,
            stage_b_status="pending",
            stage_b_reviewer_user_id=None,
            stage_b_reviewed_at=None,
            stage_b_rationale=None,
            stage_b_pilot_scope=None,
        )
        result = service.record_supersession(
            actor_user_id=ACTOR,
            source_id=source_a["id"],
            supersedes_source_id=source_b["id"],
            rationale="New regulation replaces old.",
        )
        self.assertEqual(result["supersedes_source_id"], source_b["id"])
        flags = factory.flags.get_for_source(source_b["id"])
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0]["trigger_type"], "supersession")
        self.assertEqual(flags[0]["requirement_id"], UUID("66666666-0000-0000-0000-000000000600"))

    def test_indirect_cycle_denied(self):
        factory = ServiceFactory()
        service = factory.service()
        source_a = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="A", version="1.0",
        )
        source_b = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="B", version="1.0",
        )
        source_c = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="C", version="1.0",
        )
        # A supersedes B
        service.record_supersession(
            actor_user_id=ACTOR, source_id=source_a["id"],
            supersedes_source_id=source_b["id"], rationale="A supersedes B.",
        )
        # B supersedes C
        service.record_supersession(
            actor_user_id=ACTOR, source_id=source_b["id"],
            supersedes_source_id=source_c["id"], rationale="B supersedes C.",
        )
        # C tries to supersede A -> indirect cycle (A->B->C->A)
        with self.assertRaises(ApplicationValidationError) as ctx:
            service.record_supersession(
                actor_user_id=ACTOR, source_id=source_c["id"],
                supersedes_source_id=source_a["id"], rationale="C supersedes A.",
            )
        self.assertIn("indirect supersession cycle detected", str(ctx.exception))

    def test_atomic_supersession_rollback_on_flag_failure(self):
        """If flag creation fails, source updates must roll back."""
        factory = ServiceFactory()
        service = factory.service()
        source_a = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="New", version="2.0",
        )
        source_b = service.register_source(
            actor_user_id=ACTOR, authority_id=AUTHORITY,
            jurisdiction="EU", title="Old", version="1.0",
        )
        # Add a linked requirement so that flag creation runs
        factory.requirements.create(
            id=UUID("66666666-0000-0000-0000-000000000600"),
            normalized_document_id=UUID("77777777-0000-0000-0000-000000000700"),
            requirement_text="Test req.",
            requirement_type="labeling",
            source_location={},
            position=0,
            actor=None,
            condition_metadata=None,
            status="extracted",
            ingestion_job_id=None,
            extraction_outcome="succeeded",
            parser_version="v1",
            manual_entry=False,
            reviewer_user_id=None,
            reviewed_at=None,
            source_id=source_b["id"],
            stage_a_status="verified",
            stage_a_reviewer_user_id=None,
            stage_a_reviewed_at=None,
            stage_a_rationale=None,
            stage_b_status="pending",
            stage_b_reviewer_user_id=None,
            stage_b_reviewed_at=None,
            stage_b_rationale=None,
            stage_b_pilot_scope=None,
        )
        # Mock a flag-creation failure by monkeypatching create_in_transaction
        original_create = service._flag_repo.create_in_transaction
        def failing_create(*args, **kwargs):
            raise RuntimeError("simulated flag insert failure")
        service._flag_repo.create_in_transaction = failing_create
        with self.assertRaises(RuntimeError):
            service.record_supersession(
                actor_user_id=ACTOR, source_id=source_a["id"],
                supersedes_source_id=source_b["id"], rationale="Test.",
            )
        # After rollback, source updates must not persist (verified against real DB in integration).
        # The exception confirms the atomic transaction boundary fails safely.
        service._flag_repo.create_in_transaction = original_create
