from __future__ import annotations

import unittest
from uuid import UUID

from xportra.application.regulatory_publication_index_service import (
    RegulatoryPublicationIndexService,
)
from xportra.domain.evidence_corpus import GLOBAL_REGULATORY_TENANT_ID

REQUIREMENT_ID = UUID("10000000-0000-0000-0000-000000000001")
SOURCE_ID = UUID("20000000-0000-0000-0000-000000000002")
CLAIM_TOKEN = UUID("30000000-0000-0000-0000-000000000003")
OLD_CHUNK_ID = UUID("40000000-0000-0000-0000-000000000004")
NEW_CHUNK_ID = UUID("50000000-0000-0000-0000-000000000005")
_UNSET = object()


def _job(**overrides):
    row = {
        "requirement_id": REQUIREMENT_ID,
        "desired_state": "published",
        "attempt_count": 1,
        "claim_token": CLAIM_TOKEN,
        "indexed_chunk_ids": [OLD_CHUNK_ID],
        "publication_fingerprint": None,
    }
    row.update(overrides)
    return row


def _published_requirement(**overrides):
    row = {
        "id": REQUIREMENT_ID,
        "requirement_text": "The exporter must retain the certificate.",
        "source_id": SOURCE_ID,
        "source_location": {"page": 4, "section": "2.1"},
        "source_title": "Export Regulation",
        "source_jurisdiction": "NG",
        "source_version": "2026-01",
    }
    row.update(overrides)
    return row


class FakeJobRepository:
    def __init__(self, *, job=None, requirement=None):
        self.job = job
        self.requirement = requirement
        self.completed = None
        self.failed = None
        self.eligible_ids = {}

    def claim_next(self, *, lease_seconds):
        return self.job

    def get_current_requirement(self, requirement_id):
        return self.requirement

    def complete_claim(
        self,
        requirement_id,
        claim_token,
        *,
        indexed_chunk_ids,
        publication_fingerprint,
    ):
        self.completed = {
            "requirement_id": requirement_id,
            "claim_token": claim_token,
            "indexed_chunk_ids": indexed_chunk_ids,
            "publication_fingerprint": publication_fingerprint,
        }
        return True

    def fail_claim(
        self,
        requirement_id,
        claim_token,
        *,
        failure_kind,
        retry_seconds,
        max_attempts,
    ):
        self.failed = {
            "failure_kind": failure_kind,
            "retry_seconds": retry_seconds,
            "max_attempts": max_attempts,
        }
        return True

    def renew_claim(self, *args, **kwargs):
        return True

    def currently_eligible_requirement_ids(self, requirement_ids):
        return {
            requirement_id: fingerprint
            for requirement_id, fingerprint in self.eligible_ids.items()
            if requirement_id in requirement_ids
        }


class FakeIndexSync:
    def __init__(self, *, chunk_ids=None, fail_sync=False):
        self.chunk_ids = list(chunk_ids or [NEW_CHUNK_ID])
        self.fail_sync = fail_sync
        self.synced = []
        self.deleted = []

    def sync(self, document, *, tenant_id):
        self.synced.append((document, tenant_id))
        if self.fail_sync:
            raise RuntimeError("sensitive underlying diagnostic")
        return {"indexed_chunk_ids": list(self.chunk_ids)}

    def delete_chunks(self, chunk_ids, *, tenant_id):
        self.deleted.append((list(chunk_ids), tenant_id))


class RegulatoryPublicationIndexServiceTests(unittest.TestCase):
    def make_service(
        self, *, job=_UNSET, requirement=_UNSET, index_sync=None
    ):
        self.jobs = FakeJobRepository(
            job=_job() if job is _UNSET else job,
            requirement=(
                _published_requirement()
                if requirement is _UNSET
                else requirement),
        )
        self.index_sync = index_sync or FakeIndexSync()
        return RegulatoryPublicationIndexService(
            database=None,
            index_sync=self.index_sync,
            job_repository=self.jobs,
        )

    def test_published_requirement_indexes_as_global_regulatory_content(self):
        service = self.make_service()

        self.assertTrue(service.process_next())

        document, tenant = self.index_sync.synced[0]
        self.assertEqual(tenant.tenant_id, GLOBAL_REGULATORY_TENANT_ID)
        self.assertEqual(document["source_id"], str(SOURCE_ID))
        self.assertEqual(document["content"], _published_requirement()[
            "requirement_text"])
        self.assertEqual(
            document["index_metadata"],
            {
                "content_scope": "global_regulatory",
                "regulatory_requirement_id": REQUIREMENT_ID,
                "publication_status": "published",
                "publication_fingerprint": (
                    self.index_sync.synced[0][0]["index_metadata"][
                        "publication_fingerprint"]),
            },
        )
        self.assertEqual(
            self.jobs.completed["indexed_chunk_ids"], [NEW_CHUNK_ID])
        self.assertEqual(self.index_sync.deleted[0][0], [OLD_CHUNK_ID])

    def test_removed_requirement_deletes_all_previously_indexed_chunks(self):
        service = self.make_service(
            job=_job(desired_state="removed"),
            requirement=_published_requirement(),
        )

        service.process_next()

        self.assertEqual(self.index_sync.synced, [])
        self.assertEqual(self.index_sync.deleted[0][0], [OLD_CHUNK_ID])
        self.assertEqual(self.jobs.completed["indexed_chunk_ids"], [])

    def test_changed_content_keeps_identical_chunks_and_removes_stale_chunks(self):
        sync = FakeIndexSync(chunk_ids=[OLD_CHUNK_ID, NEW_CHUNK_ID])
        service = self.make_service(index_sync=sync)

        service.process_next()

        self.assertEqual(sync.deleted, [])
        self.assertEqual(
            self.jobs.completed["indexed_chunk_ids"],
            [OLD_CHUNK_ID, NEW_CHUNK_ID],
        )

    def test_ineligible_requirement_removes_prior_points(self):
        service = self.make_service(requirement=None)

        service.process_next()

        self.assertEqual(self.index_sync.synced, [])
        self.assertEqual(self.index_sync.deleted[0][0], [OLD_CHUNK_ID])
        self.assertEqual(self.jobs.completed["indexed_chunk_ids"], [])

    def test_index_failure_is_scheduled_for_bounded_retry(self):
        sync = FakeIndexSync(fail_sync=True)
        service = self.make_service(index_sync=sync)

        service.process_next()

        self.assertEqual(
            self.jobs.failed,
            {
                "failure_kind": "RuntimeError",
                "retry_seconds": 30,
                "max_attempts": 5,
            },
        )
        self.assertIsNone(self.jobs.completed)
        self.assertEqual(self.index_sync.deleted, [])

    def test_current_eligibility_filter_is_authoritative(self):
        service = self.make_service(job=None)
        self.jobs.eligible_ids = {REQUIREMENT_ID: "a" * 64}

        self.assertEqual(
            service.currently_eligible_requirement_ids(
                {REQUIREMENT_ID, SOURCE_ID}),
            {REQUIREMENT_ID: "a" * 64},
        )
        self.assertFalse(service.process_next())


if __name__ == "__main__":
    unittest.main()
