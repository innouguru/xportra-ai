"""Durable synchronization of currently published requirements to Qdrant."""

from __future__ import annotations

import json
import logging
import threading
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from xportra.domain.evidence_corpus import GLOBAL_REGULATORY_TENANT_ID
from xportra.domain.errors import DomainValidationError
from xportra.domain.regulatory_publication import (
    regulatory_publication_fingerprint,
)
from xportra.persistence.database import Database
from xportra.persistence.regulatory_publication_index import (
    RegulatoryPublicationIndexJobRepository,
)
from xportra.persistence.tenant import TenantContext

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
LEASE_SECONDS = 300


class RegulatoryPublicationIndexService:
    """Process durable publication-index jobs using existing index services."""

    def __init__(
        self,
        database: Database,
        *,
        index_sync: Any,
        job_repository: RegulatoryPublicationIndexJobRepository | None = None,
    ) -> None:
        if index_sync is None or not callable(
            getattr(index_sync, "sync", None)
        ) or not callable(getattr(index_sync, "delete_chunks", None)):
            raise DomainValidationError(
                "an evidence index synchronization service is required")
        self._jobs = job_repository or (
            RegulatoryPublicationIndexJobRepository(database))
        self._index_sync = index_sync
        self._global_context = TenantContext(
            GLOBAL_REGULATORY_TENANT_ID)

    def currently_eligible_requirement_ids(
        self, requirement_ids: set[UUID]
    ) -> dict[UUID, str]:
        return self._jobs.currently_eligible_requirement_ids(requirement_ids)

    def process_next(self) -> bool:
        job = self._jobs.claim_next(lease_seconds=LEASE_SECONDS)
        if job is None:
            return False

        requirement_id = UUID(str(job["requirement_id"]))
        claim_token = UUID(str(job["claim_token"]))
        stop_heartbeat = threading.Event()
        heartbeat = threading.Thread(
            target=self._renew_claim,
            args=(requirement_id, claim_token, stop_heartbeat),
            daemon=True,
        )
        heartbeat.start()
        try:
            self._synchronize_claimed_job(
                job,
                requirement_id=requirement_id,
                claim_token=claim_token,
            )
        except Exception as exc:  # background job must be durably failed
            delay = min(30 * 2 ** max(0, int(job["attempt_count"]) - 1), 900)
            self._jobs.fail_claim(
                requirement_id,
                claim_token,
                failure_kind=type(exc).__name__,
                retry_seconds=delay,
                max_attempts=MAX_ATTEMPTS,
            )
            logger.error(
                "Regulatory publication indexing failed for %s (%s).",
                requirement_id,
                type(exc).__name__,
            )
        finally:
            stop_heartbeat.set()
            heartbeat.join()
        return True

    def _synchronize_claimed_job(
        self,
        job: dict[str, Any],
        *,
        requirement_id: UUID,
        claim_token: UUID,
    ) -> None:
        previous_ids = {
            UUID(str(raw_id))
            for raw_id in (job.get("indexed_chunk_ids") or [])
        }
        new_ids: set[UUID] = set()
        publication_fingerprint = None

        row = self._jobs.get_current_requirement(requirement_id)
        if row is not None:
            document = self._to_index_document(row)
            report = self._index_sync.sync(
                document,
                tenant_id=self._global_context,
            )
            new_ids = set(report["indexed_chunk_ids"])
            publication_fingerprint = document[
                "index_metadata"]["publication_fingerprint"]

        stale_ids = sorted(previous_ids - new_ids)
        if stale_ids:
            self._index_sync.delete_chunks(
                stale_ids, tenant_id=self._global_context)

        updated = self._jobs.complete_claim(
            requirement_id,
            claim_token,
            indexed_chunk_ids=sorted(new_ids),
            publication_fingerprint=publication_fingerprint,
        )
        if not updated:
            logger.info(
                "Regulatory publication index claim for %s was superseded.",
                requirement_id,
            )
            return
        logger.info(
            "Regulatory publication index synchronized for %s (%d chunks).",
            requirement_id,
            len(new_ids),
        )

    def _renew_claim(
        self,
        requirement_id: UUID,
        claim_token: UUID,
        stop_event: threading.Event,
    ) -> None:
        while not stop_event.wait(LEASE_SECONDS / 3):
            try:
                if not self._jobs.renew_claim(
                    requirement_id,
                    claim_token,
                    lease_seconds=LEASE_SECONDS,
                ):
                    logger.info(
                        "Regulatory publication index lease for %s is no "
                        "longer active.",
                        requirement_id,
                    )
                    return
            except Exception as exc:
                logger.warning(
                    "Regulatory publication index lease renewal failed for "
                    "%s (%s).",
                    requirement_id,
                    type(exc).__name__,
                )

    @staticmethod
    def _to_index_document(row: dict[str, Any]) -> dict[str, Any]:
        requirement_id = UUID(str(row["id"]))
        source_id = UUID(str(row["source_id"]))
        source_location = row.get("source_location")
        if isinstance(source_location, (dict, list)):
            source_location = json.dumps(
                source_location, ensure_ascii=False, sort_keys=True)
        elif source_location is not None and not isinstance(source_location, str):
            raise DomainValidationError("source location is malformed")
        content = row.get("requirement_text")
        if not isinstance(content, str) or not content.strip():
            raise DomainValidationError(
                "published regulatory requirement text is missing")
        publication_fingerprint = regulatory_publication_fingerprint(row)

        return {
            "id": uuid5(
                NAMESPACE_URL,
                f"xportra:global-regulatory-requirement:{requirement_id}",
            ),
            "tenant_id": GLOBAL_REGULATORY_TENANT_ID,
            "title": row.get("source_title") or "Regulatory requirement",
            "content": content,
            "source_type": "regulation",
            "source_id": str(source_id),
            "source_location": source_location,
            "jurisdiction": row.get("source_jurisdiction"),
            "document_version": row.get("source_version"),
            "metadata": {},
            "index_metadata": {
                "content_scope": "global_regulatory",
                "regulatory_requirement_id": requirement_id,
                "publication_status": "extracted",
                "publication_fingerprint": publication_fingerprint,
            },
        }
