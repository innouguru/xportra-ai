"""Evidence-upload production composition for Phase 10.4.

The single explicit place where the upload path is wired
to real infrastructure — mirroring the Phase 5.14 RAG
composition precedent:

```text
canonical environment
    ↓
SupabaseEvidenceObjectStore (private Storage, httpx)
EvidenceIndexSyncService (chunking → indexing → Qdrant)
```

Composition only: no validation, parsing, tenant, or
error policy lives here. Missing configuration fails
closed (``EvidenceStorageConfigurationError`` /
``RAGConfigurationError``); callers translate that to
an unwired-service 503 raised BEFORE any storage or
database mutation. Secrets are never logged — only
bucket/collection/model names.
"""

from __future__ import annotations

import logging
import os
from typing import Mapping

from qdrant_client import QdrantClient

from xportra.domain.evidence_chunking import EvidenceChunkingService
from xportra.domain.evidence_index_sync import EvidenceIndexSyncService
from xportra.domain.evidence_indexing import (
    EmbeddingModelConfig,
    EvidenceIndexingService,
)
from xportra.domain.vector_index import VectorIndexConfig

from .evidence_storage import (
    SupabaseEvidenceObjectStore,
    SupabaseStorageSettings,
)
from .rag_composition import (
    RAGConfigurationError,
    SentenceTransformerEmbeddingProvider,
)
from .vector_index import QdrantEvidenceVectorIndex

logger = logging.getLogger(__name__)


def compose_evidence_object_store_from_environment(
    environment: Mapping[str, str] | None = None,
) -> SupabaseEvidenceObjectStore:
    """Build the private-Storage adapter from canonical variables.

    Requires ``SUPABASE_URL`` plus ``SUPABASE_SERVICE_ROLE_KEY``
    (and optional ``EVIDENCE_STORAGE_BUCKET``). Raises
    ``EvidenceStorageConfigurationError`` when absent —
    the upload path then fails closed as unconfigured.
    """
    from xportra.domain.evidence_storage import (
        EvidenceStorageConfigurationError,
    )

    values = os.environ if environment is None else environment
    try:
        settings = SupabaseStorageSettings.from_environment(values)
    except EvidenceStorageConfigurationError:
        raise
    except Exception as cause:
        raise EvidenceStorageConfigurationError(
            "evidence object storage is not configured") from cause
    logger.info(
        "Evidence object storage configured (bucket=%s)",
        settings.bucket,
    )
    return SupabaseEvidenceObjectStore(settings)


def compose_evidence_index_sync_from_environment(
    environment: Mapping[str, str] | None = None,
) -> EvidenceIndexSyncService:
    """Build the Phase 4.5 index-sync chain from canonical variables.

    Reuses ``VECTOR_STORE_URL``, ``VECTOR_STORE_COLLECTION``,
    ``EMBEDDING_MODEL``, and ``EMBEDDING_DIMENSIONS`` — the
    same collection/model the retrieval boundary reads, so
    uploaded evidence is indexed exactly where Phase 5
    looks. No new collection, scope dimension, or pipeline:
    chunking, indexing, and the vector index are the
    existing boundaries. Raises ``RAGConfigurationError``
    when absent.
    """
    values = os.environ if environment is None else environment
    qdrant_url = _required(values, "VECTOR_STORE_URL")
    collection = _required(values, "VECTOR_STORE_COLLECTION")
    embedding_model = _required(values, "EMBEDDING_MODEL")
    dimensions = _required_int(values, "EMBEDDING_DIMENSIONS")
    embedding = EmbeddingModelConfig(
        model_identifier=embedding_model, dimensions=dimensions)
    vector_config = VectorIndexConfig.from_embedding_config(
        collection, embedding)
    vector_index = QdrantEvidenceVectorIndex(
        QdrantClient(url=qdrant_url), vector_config)
    logger.info(
        "Evidence index sync configured (collection=%s model=%s)",
        collection,
        embedding_model,
    )
    return EvidenceIndexSyncService(
        chunking=EvidenceChunkingService(),
        indexing=EvidenceIndexingService(),
        vector_index=vector_index,
        provider=SentenceTransformerEmbeddingProvider(
            embedding_config=embedding),
        embedding_config=embedding,
    )


def _required(values: Mapping[str, str], name: str) -> str:
    value = values.get(name, "")
    value = value.strip() if isinstance(value, str) else ""
    if not value:
        raise RAGConfigurationError(f"{name} is required")
    return value


def _required_int(values: Mapping[str, str], name: str) -> int:
    raw = _required(values, name)
    try:
        parsed = int(raw)
    except (TypeError, ValueError) as cause:
        raise RAGConfigurationError(
            f"{name} must be a positive integer") from cause
    if isinstance(parsed, bool) or parsed <= 0:
        raise RAGConfigurationError(
            f"{name} must be a positive integer")
    return parsed


__all__ = [
    "compose_evidence_index_sync_from_environment",
    "compose_evidence_object_store_from_environment",
]
