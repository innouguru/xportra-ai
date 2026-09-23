"""Evidence index synchronization boundary for Phase 4.5.

Coordinates the existing deterministic boundaries:

``EvidenceDocument → EvidenceChunkingService → EvidenceIndexingService
→ EvidenceVectorIndex``

This module contains no chunking, embedding, or vector-store logic of its
own — it orchestrates the established services and returns a deterministic
synchronization report. Fail-closed: any validation, chunking, embedding,
or persistence failure raises through existing domain/infrastructure error
conventions and never yields a success report. No retrieval, search,
query processing, RAG, LLM calls, queues, or background workers.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from .errors import (
    DomainValidationError,
    VectorStoreError,
    require_tenant_context,
)
from .evidence_chunking import EvidenceChunkingService
from .evidence_corpus import EvidenceDocument
from .evidence_indexing import (
    EmbeddingModelConfig,
    EmbeddingProvider,
    EvidenceIndexingService,
)
from .vector_index import EvidenceVectorIndex


class EvidenceIndexSyncService:
    """Deterministically synchronize one evidence document into the index.

    Entry ``sync(document, *, tenant_id)`` validates tenant ownership,
    chunks via ``EvidenceChunkingService``, embeds via
    ``EvidenceIndexingService``, persists each indexable chunk through the
    ``EvidenceVectorIndex`` protocol, and returns a report only on full
    success. Already-persisted points are never rolled back on failure:
    upsert is idempotent and points may pre-date this sync, so a partial
    failure raises ``VectorStoreError`` instead of deleting verified state.
    Re-running after a fix is safe because chunk and point identities are
    deterministic.
    """

    def __init__(
        self,
        *,
        chunking: EvidenceChunkingService,
        indexing: EvidenceIndexingService,
        vector_index: EvidenceVectorIndex,
        provider: EmbeddingProvider,
        embedding_config: EmbeddingModelConfig,
    ) -> None:
        if chunking is None or not callable(
            getattr(chunking, "chunk", None)
        ):
            raise DomainValidationError("an evidence chunking service is required")
        if indexing is None or not callable(
            getattr(indexing, "index", None)
        ):
            raise DomainValidationError("an evidence indexing service is required")
        if vector_index is None or not callable(
            getattr(vector_index, "upsert", None)
        ):
            raise DomainValidationError("a vector index is required")
        if provider is None or not callable(getattr(provider, "embed", None)):
            raise DomainValidationError("an embedding provider is required")
        if not isinstance(embedding_config, EmbeddingModelConfig):
            raise DomainValidationError(
                "explicit EmbeddingModelConfig is required")
        self._chunking = chunking
        self._indexing = indexing
        self._vector_index = vector_index
        self._provider = provider
        self._embedding_config = embedding_config

    def sync(
        self,
        document: EvidenceDocument | dict[str, Any],
        *,
        tenant_id: Any,
    ) -> dict[str, Any]:
        """Synchronize one evidence document; report only on full success."""
        require_tenant_context(tenant_id)
        if isinstance(document, EvidenceDocument):
            record = document.to_record()
        elif isinstance(document, dict):
            record = document
        else:
            raise DomainValidationError("evidence document is required")
        if record.get("tenant_id") != tenant_id.tenant_id:
            raise DomainValidationError("tenant identity mismatch")
        document_id = record.get("id")
        if not isinstance(document_id, UUID):
            raise DomainValidationError("document identity is malformed")

        chunks = self._chunking.chunk(record, tenant_id=tenant_id)
        if not isinstance(chunks, (list, tuple)):
            raise DomainValidationError("chunking produced malformed output")
        if not chunks:
            raise DomainValidationError(
                "document produced no evidence chunks")
        for chunk in chunks:
            if not isinstance(chunk, dict) or (
                chunk.get("tenant_id") != tenant_id.tenant_id
            ):
                raise DomainValidationError("tenant identity mismatch")

        indexed = self._indexing.index(
            chunks,
            tenant_id=tenant_id,
            provider=self._provider,
            config=self._embedding_config,
        )
        if not isinstance(indexed, (list, tuple)):
            raise DomainValidationError("indexing produced malformed output")
        if len(indexed) != len(chunks):
            raise DomainValidationError(
                "indexing produced inconsistent output")
        for item in indexed:
            if not isinstance(item, dict) or (
                item.get("tenant_id") != tenant_id.tenant_id
            ):
                raise DomainValidationError("tenant identity mismatch")

        total = len(indexed)
        indexed_chunk_ids: list[UUID] = []
        for position, item in enumerate(indexed, start=1):
            try:
                self._vector_index.upsert(item, tenant_id=tenant_id)
            except Exception as exc:
                raise VectorStoreError(
                    f"evidence index sync (chunk {position} of {total})",
                    exc,
                ) from exc
            indexed_chunk_ids.append(item["chunk_id"])

        return {
            "tenant_id": tenant_id.tenant_id,
            "document_id": document_id,
            "document_version": record.get("document_version"),
            "chunk_count": len(chunks),
            "indexed_count": total,
            "indexed_chunk_ids": indexed_chunk_ids,
            "status": "complete",
        }
