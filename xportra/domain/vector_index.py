"""Qdrant-independent vector index contract (Phase 4.4; retrieval added 5.1).

The domain depends only on this protocol and configuration object;
concrete vector databases (Qdrant, etc.) live behind an infrastructure
adapter. Persistence operations plus the single tenant-scoped retrieval
operation ``find`` introduced in Phase 5.1. Query embedding stays behind
the domain ``EmbeddingProvider`` boundary; reranking, hybrid search, and
RAG remain out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from .errors import DomainValidationError
from .evidence_indexing import EmbeddingModelConfig
from .evidence_retrieval import (
    EvidenceRetrievalResult,
    EvidenceRetrievalScope,
)

DISTANCE_METRICS = ("cosine", "euclid", "dot")


@dataclass(frozen=True, slots=True)
class VectorIndexConfig:
    """Explicit vector index configuration. Never silently inferred."""

    collection_name: str
    embedding_model: str
    embedding_dimensions: int
    distance_metric: str = "cosine"

    def __post_init__(self) -> None:
        if not isinstance(self.collection_name, str) or (
            not self.collection_name.strip()
        ):
            raise DomainValidationError("collection name is required")
        if not isinstance(self.embedding_model, str) or (
            not self.embedding_model.strip()
        ):
            raise DomainValidationError(
                "embedding model identifier is required")
        if isinstance(self.embedding_dimensions, bool) or not isinstance(
            self.embedding_dimensions, int
        ) or self.embedding_dimensions <= 0:
            raise DomainValidationError(
                "embedding dimensions must be a positive integer")
        if self.distance_metric not in DISTANCE_METRICS:
            raise DomainValidationError("unsupported distance metric")

    @classmethod
    def from_embedding_config(
        cls,
        collection_name: str,
        embedding: EmbeddingModelConfig,
        *,
        distance_metric: str = "cosine",
    ) -> "VectorIndexConfig":
        """Reuse the Phase 4.3 EmbeddingModelConfig boundary instead of
        duplicating model identity and dimensions by hand."""
        if not isinstance(embedding, EmbeddingModelConfig):
            raise DomainValidationError(
                "an explicit EmbeddingModelConfig is required")
        return cls(
            collection_name=collection_name,
            embedding_model=embedding.model_identifier,
            embedding_dimensions=embedding.dimensions,
            distance_metric=distance_metric,
        )


@runtime_checkable
class EvidenceVectorIndex(Protocol):
    """Tenant-scoped vector index contract (persistence + retrieval).

    Every operation requires explicit tenant context. Implementations
    must never expose another tenant's vectors. ``chunk_id`` is the
    canonical point identity (chunk_id → vector point). ``find`` takes an
    already-embedded query vector (never raw text), enforces a mandatory
    tenant filter plus the optional ``scope`` metadata constraints (AND
    semantics), and returns domain ``EvidenceRetrievalResult`` objects —
    never provider-specific response types.
    """

    def upsert(self, chunk: object, *, tenant_id: Any) -> dict[str, Any]:
        ...

    def get(self, *, tenant_id: Any, chunk_id: UUID) -> dict[str, Any]:
        ...

    def delete(self, *, tenant_id: Any, chunk_id: UUID) -> None:
        ...

    def count(self, *, tenant_id: Any) -> int:
        ...

    def find(
        self,
        query_vector: list[float],
        *,
        tenant_id: Any,
        top_k: int,
        scope: EvidenceRetrievalScope | None = None,
    ) -> list[EvidenceRetrievalResult]:
        ...
