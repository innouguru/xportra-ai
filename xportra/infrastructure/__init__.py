"""Xportra infrastructure layer."""

from xportra.infrastructure.vector_index import (
    EvidenceVectorIndex,
    QdrantEvidenceVectorIndex,
    VectorIndexConfig,
    validate_qdrant_collection_config,
)
from xportra.infrastructure.llm import (
    DEFAULT_LLM_TIMEOUT_SECONDS,
    LLMConfigurationError,
    LLMSettings,
    OPENROUTER_BASE_URL,
    OPENROUTER_PROVIDER_NAME,
    OpenRouterLLMClient,
    ScriptedLLMClient,
    answer_from_response,
)
from xportra.infrastructure.rag_composition import (
    DEFAULT_RAG_SYSTEM_INSTRUCTIONS,
    RAGComposition,
    RAGConfigurationError,
    RAGInfrastructureConfig,
    SentenceTransformerEmbeddingProvider,
    compose_rag_stack,
    compose_rag_stack_from_environment,
)
from xportra.infrastructure.evidence_storage import (
    InMemoryEvidenceObjectStore,
    SupabaseEvidenceObjectStore,
    SupabaseStorageSettings,
)
from xportra.infrastructure.evidence_upload import (
    compose_evidence_index_sync_from_environment,
    compose_evidence_object_store_from_environment,
)

__all__ = [
    "DEFAULT_LLM_TIMEOUT_SECONDS",
    "DEFAULT_RAG_SYSTEM_INSTRUCTIONS",
    "EvidenceVectorIndex",
    "QdrantEvidenceVectorIndex",
    "RAGComposition",
    "RAGConfigurationError",
    "RAGInfrastructureConfig",
    "SentenceTransformerEmbeddingProvider",
    "VectorIndexConfig",
    "validate_qdrant_collection_config",
    "InMemoryEvidenceObjectStore",
    "SupabaseEvidenceObjectStore",
    "SupabaseStorageSettings",
    "compose_evidence_index_sync_from_environment",
    "compose_evidence_object_store_from_environment",
    "LLMConfigurationError",
    "LLMSettings",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_PROVIDER_NAME",
    "OpenRouterLLMClient",
    "ScriptedLLMClient",
    "answer_from_response",
    "compose_rag_stack",
    "compose_rag_stack_from_environment",
]
