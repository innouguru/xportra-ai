"""Evidence embedding/indexing boundary for Phase 4.3.

Turns deterministic Phase 4.2 chunks into indexable vector
representations. Retrieval (similarity search, top-k, reranking, RAG,
query embedding) is explicitly out of scope.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from .errors import DomainValidationError, require_tenant_context
from .evidence_corpus import SOURCE_TYPES


@dataclass(frozen=True, slots=True)
class EmbeddingModelConfig:
    """Explicit embedding model contract. Never silently inferred."""

    model_identifier: str
    dimensions: int

    def __post_init__(self) -> None:
        if not isinstance(self.model_identifier, str) or (
            not self.model_identifier.strip()
        ):
            raise DomainValidationError(
                "embedding model identifier is required")
        if isinstance(self.dimensions, bool) or not isinstance(
            self.dimensions, int
        ) or self.dimensions <= 0:
            raise DomainValidationError(
                "embedding dimensions must be a positive integer")


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Provider boundary: substitution point for embedding backends.

    Implementations may wrap local models or hosted APIs; the domain
    depends only on this contract, never on a specific vendor SDK.
    """

    def embed(self, text: str) -> list[float]:
        ...


@dataclass(frozen=True)
class IndexableEvidenceChunk:
    """Chunk identity + provenance + the embedding of its exact content.

    ``chunk_id`` remains the canonical identity; no new random identity
    is generated. Traceable: tenant → source → document → chunk →
    embedding.
    """

    tenant_id: UUID
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    content_fingerprint: str
    source_id: str
    source_type: str
    source_location: str | None
    document_version: str | None
    embedding_model: str
    embedding_dimensions: int
    embedding_vector: list[float]

    def to_record(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "content": self.content,
            "content_fingerprint": self.content_fingerprint,
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_location": self.source_location,
            "document_version": self.document_version,
            "embedding_model": self.embedding_model,
            "embedding_dimensions": self.embedding_dimensions,
            "embedding_vector": list(self.embedding_vector),
        }


def _validated_embedding(
    raw: object, config: EmbeddingModelConfig
) -> list[float]:
    """Fail closed on any malformed provider output."""
    if isinstance(raw, (str, bytes)) or not isinstance(
        raw, (list, tuple)
    ):
        raise DomainValidationError("embedding is malformed")
    vector = list(raw)
    if not vector:
        raise DomainValidationError("embedding is empty")
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DomainValidationError("embedding values must be numeric")
        if not math.isfinite(value):
            raise DomainValidationError(
                "embedding values must be finite")
    if len(vector) != config.dimensions:
        raise DomainValidationError(
            "embedding dimensions are inconsistent with the model config")
    return [float(value) for value in vector]


class EvidenceIndexingService:
    """Prepare deterministic chunks for a future vector store.

    Entry ``index(chunks, *, tenant_id, provider, config)`` validates each
    chunk, requests an embedding through the provider boundary, validates
    the returned embedding, and returns index records that preserve chunk
    identity, content, fingerprint, and provenance exactly. Malformed
    chunks or embeddings fail closed; nothing is silently skipped. No
    retrieval, no vector-store writes, no LLM calls.
    """

    def index(
        self,
        chunks: list[dict[str, Any]] | tuple[dict[str, Any], ...],
        *,
        tenant_id: Any,
        provider: EmbeddingProvider,
        config: EmbeddingModelConfig,
    ) -> list[dict[str, Any]]:
        require_tenant_context(tenant_id)
        if not isinstance(config, EmbeddingModelConfig):
            raise DomainValidationError(
                "explicit EmbeddingModelConfig is required")
        if provider is None or not callable(
            getattr(provider, "embed", None)
        ):
            raise DomainValidationError(
                "an embedding provider is required")
        if not isinstance(chunks, (list, tuple)):
            raise DomainValidationError("chunks must be a sequence")
        indexed: list[dict[str, Any]] = []
        for chunk in chunks:
            indexed.append(
                self._index_one(
                    chunk,
                    tenant_id=tenant_id,
                    provider=provider,
                    config=config,
                )
            )
        return indexed

    def _index_one(
        self,
        chunk: object,
        *,
        tenant_id: Any,
        provider: EmbeddingProvider,
        config: EmbeddingModelConfig,
    ) -> dict[str, Any]:
        if not isinstance(chunk, dict):
            raise DomainValidationError("evidence chunk is malformed")
        if chunk.get("tenant_id") != tenant_id.tenant_id:
            raise DomainValidationError("tenant identity mismatch")
        chunk_id = chunk.get("chunk_id")
        document_id = chunk.get("document_id")
        if not isinstance(chunk_id, UUID):
            raise DomainValidationError("chunk identity is malformed")
        if not isinstance(document_id, UUID):
            raise DomainValidationError("document identity is malformed")
        chunk_index = chunk.get("chunk_index")
        if isinstance(chunk_index, bool) or not isinstance(
            chunk_index, int
        ) or chunk_index < 0:
            raise DomainValidationError("chunk index is malformed")
        content = chunk.get("content")
        if not isinstance(content, str) or not content.strip():
            raise DomainValidationError("content is required")
        fingerprint = chunk.get("content_fingerprint")
        if not isinstance(fingerprint, str) or not fingerprint.strip():
            raise DomainValidationError("content fingerprint is required")
        source_id = chunk.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise DomainValidationError("source_id is required")
        source_type = chunk.get("source_type")
        if source_type not in SOURCE_TYPES:
            raise DomainValidationError("unsupported source_type")
        version = chunk.get("document_version")
        if version is not None and not isinstance(version, str):
            raise DomainValidationError("document_version is malformed")
        try:
            embedding = provider.embed(content)
        except Exception as exc:  # fail closed on provider failure
            raise DomainValidationError(
                f"embedding provider failed: {exc}") from exc
        vector = _validated_embedding(embedding, config)
        return IndexableEvidenceChunk(
            tenant_id=tenant_id.tenant_id,
            chunk_id=chunk_id,
            document_id=document_id,
            chunk_index=chunk_index,
            content=content,
            content_fingerprint=fingerprint,
            source_id=source_id,
            source_type=source_type,
            source_location=chunk.get("source_location"),
            document_version=version,
            embedding_model=config.model_identifier,
            embedding_dimensions=config.dimensions,
            embedding_vector=vector,
        ).to_record()
