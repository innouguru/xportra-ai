"""Evidence retrieval boundary (Phases 5.1–5.3 contracts and semantics).

Retrieval infrastructure only: given an explicit tenant and a query,
return the indexed evidence chunks relevant to that query. Phase 5.1
established the provider-independent ``EvidenceRetriever`` contract and
the ``EvidenceVectorIndex.find`` operation; Phase 5.2 established the
query semantics — deterministic normalization, application retrieval
configuration, descending-score ordering with deterministic ties, and
exact-duplicate collapsing keyed on the Phase 4 document/fingerprint
identity model; Phase 5.3 adds ``EvidenceRetrievalScope`` — explicit,
conjunctive metadata restrictions over canonical indexed fields, with
mandatory tenant isolation kept strictly outside the scope object.
Concrete vector databases stay behind the Phase 4.4 infrastructure
adapter. Query embedding reuses the Phase 4.3
``EmbeddingProvider`` boundary. No compliance reasoning, answer
generation, prompt construction, LLM calls, query rewriting, reranking,
hybrid search, agentic retrieval, conversational memory, or user-facing
RAG responses.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

from .errors import (
    DomainValidationError,
    VectorStoreError,
    require_tenant_context,
)
from .evidence_corpus import SOURCE_TYPES
from .evidence_indexing import (
    EmbeddingModelConfig,
    EmbeddingProvider,
    _validated_embedding,
)

if TYPE_CHECKING:
    from .vector_index import EvidenceVectorIndex

DEFAULT_TOP_K = 5


@dataclass(frozen=True, slots=True)
class EvidenceRetrievalQuery:
    """Validated, normalized representation of an information need.

    Semantic rules (Phase 5.2):

    - deterministic normalization only — surrounding whitespace is
      trimmed and internal whitespace runs collapse to single spaces;
      case, punctuation, wording, and compliance terminology are
      preserved exactly (the retrieval layer never rewrites the
      information need semantically);
    - empty, whitespace-only, or non-string text is rejected with
      ``DomainValidationError``;
    - ``top_k`` must be a positive integer.

    This is the *domain* query representation; the vector-store query
    representation (the embedded vector) never appears here. Tenant
    identity is deliberately NOT part of this value object — it is
    a required keyword of every ``EvidenceRetriever.retrieve`` call, so
    tenant scope can never be omitted, defaulted, or forgotten.
    """

    text: str
    top_k: int = DEFAULT_TOP_K

    def __post_init__(self) -> None:
        if not isinstance(self.text, str):
            raise DomainValidationError("query text is required")
        normalized = " ".join(self.text.split())
        if not normalized:
            raise DomainValidationError("query text is required")
        object.__setattr__(self, "text", normalized)
        if (
            isinstance(self.top_k, bool)
            or not isinstance(self.top_k, int)
            or self.top_k <= 0
        ):
            raise DomainValidationError("top-k must be a positive integer")


@dataclass(frozen=True, slots=True)
class EvidenceRetrievalConfig:
    """Application retrieval configuration: one explicit knob — top-k.

    Reuses the Phase 5.1 ``DEFAULT_TOP_K`` default (no competing
    constant) and deliberately carries no embedding settings and no
    tenant identity: the embedding contract remains the Phase 4.3
    ``EmbeddingModelConfig`` injected into the retriever constructor,
    and tenant scope remains an execution-level keyword.
    """

    top_k: int = DEFAULT_TOP_K

    def __post_init__(self) -> None:
        if (
            isinstance(self.top_k, bool)
            or not isinstance(self.top_k, int)
            or self.top_k <= 0
        ):
            raise DomainValidationError("top-k must be a positive integer")

    def build_query(
        self, information_need: str
    ) -> EvidenceRetrievalQuery:
        """Convert an application information need into a validated,
        normalized retrieval query carrying this configuration's
        top-k."""
        return EvidenceRetrievalQuery(
            text=information_need, top_k=self.top_k)


@dataclass(frozen=True, slots=True)
class EvidenceRetrievalResult:
    """One retrieved evidence chunk with full Phase 4 provenance.

    Mirrors the persisted Phase 4.4 payload fields exactly — identity,
    content, fingerprint, source provenance, document version, and
    embedding contract — plus the similarity ``score`` returned by the
    index. A result is never reduced to text + score alone, so downstream
    compliance reasoning can always determine where the evidence came
    from (INVARIANTS.md 3 and 6).
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
    score: float

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
            "score": self.score,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> "EvidenceRetrievalResult":
        """Fail closed on any malformed retrieval-result representation."""
        if not isinstance(record, dict):
            raise DomainValidationError("retrieval result is malformed")
        tenant_id = record.get("tenant_id")
        if not isinstance(tenant_id, UUID):
            raise DomainValidationError("tenant_id must be a UUID")
        chunk_id = record.get("chunk_id")
        if not isinstance(chunk_id, UUID):
            raise DomainValidationError("chunk identity is malformed")
        document_id = record.get("document_id")
        if not isinstance(document_id, UUID):
            raise DomainValidationError("document identity is malformed")
        chunk_index = record.get("chunk_index")
        if (
            isinstance(chunk_index, bool)
            or not isinstance(chunk_index, int)
            or chunk_index < 0
        ):
            raise DomainValidationError("chunk index is malformed")
        content = record.get("content")
        if not isinstance(content, str) or not content.strip():
            raise DomainValidationError("content is required")
        fingerprint = record.get("content_fingerprint")
        if not isinstance(fingerprint, str) or not fingerprint.strip():
            raise DomainValidationError("content fingerprint is required")
        source_id = record.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise DomainValidationError("source_id is required")
        source_type = record.get("source_type")
        if source_type not in SOURCE_TYPES:
            raise DomainValidationError("unsupported source_type")
        location = record.get("source_location")
        if location is not None and not isinstance(location, str):
            raise DomainValidationError("source_location is malformed")
        version = record.get("document_version")
        if version is not None and not isinstance(version, str):
            raise DomainValidationError("document_version is malformed")
        embedding_model = record.get("embedding_model")
        if not isinstance(embedding_model, str) or not embedding_model.strip():
            raise DomainValidationError(
                "embedding model identifier is required")
        dimensions = record.get("embedding_dimensions")
        if (
            isinstance(dimensions, bool)
            or not isinstance(dimensions, int)
            or dimensions <= 0
        ):
            raise DomainValidationError(
                "embedding dimensions must be a positive integer")
        score = record.get("score")
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not math.isfinite(score)
        ):
            raise DomainValidationError("relevance score is malformed")
        return cls(
            tenant_id=tenant_id,
            chunk_id=chunk_id,
            document_id=document_id,
            chunk_index=chunk_index,
            content=content,
            content_fingerprint=fingerprint,
            source_id=source_id,
            source_type=source_type,
            source_location=location,
            document_version=version,
            embedding_model=embedding_model,
            embedding_dimensions=dimensions,
            score=float(score),
        )


def evidence_duplicate_key(
    result: EvidenceRetrievalResult,
) -> tuple[UUID, str]:
    """Authoritative Phase 5.2 duplicate identity: document + content.

    Two results share a key only when they come from the same document
    (Phase 4.0 identity fixes tenant + source + version) AND carry the
    identical content fingerprint. Differing documents, versions, or
    sources never collide, so provenance-distinct evidence is always
    preserved. Phase 5.4's hybrid candidate union reuses this rule.
    """
    return (result.document_id, result.content_fingerprint)


@dataclass(frozen=True, slots=True)
class EvidenceRetrievalScope:
    """Optional, explicit metadata restrictions for one retrieval call.

    Supported dimensions are exactly the canonical metadata the Phase
    4.4 payload already stores: ``source_id``, ``source_type``,
    ``document_id``, ``document_version``. Every field is optional and
    ``None`` means "no restriction on this dimension". Supplied values
    are validated fail-closed and trimmed. Unsupported/speculative
    dimensions (tenant, jurisdiction, dates, status, commodity, …)
    cannot be expressed — unknown keyword arguments are rejected by the
    dataclass itself.

    Tenant identity is deliberately NOT a field: isolation is a
    mandatory execution-level concern and can never be weakened,
    defaulted, or bypassed through a scope object.

    Semantics: multiple supplied filters are conjunctive (AND) with
    exact equality on the canonical field — a result is in scope only
    if it satisfies every non-``None`` field.
    """

    source_id: str | None = None
    source_type: str | None = None
    document_id: UUID | None = None
    document_version: str | None = None

    def __post_init__(self) -> None:
        if self.source_id is not None:
            if (not isinstance(self.source_id, str)
                    or not self.source_id.strip()):
                raise DomainValidationError(
                    "source_id filter is malformed")
            object.__setattr__(self, "source_id", self.source_id.strip())
        if self.source_type is not None:
            if (not isinstance(self.source_type, str)
                    or self.source_type not in SOURCE_TYPES):
                raise DomainValidationError("unsupported source_type")
        if self.document_id is not None:
            if not isinstance(self.document_id, UUID):
                raise DomainValidationError(
                    "document identity is malformed")
        if self.document_version is not None:
            if (not isinstance(self.document_version, str)
                    or not self.document_version.strip()):
                raise DomainValidationError(
                    "document_version filter is malformed")
            object.__setattr__(
                self, "document_version", self.document_version.strip())

    @property
    def is_empty(self) -> bool:
        """True when no optional metadata restriction is active."""
        return not any((
            self.source_id is not None,
            self.source_type is not None,
            self.document_id is not None,
            self.document_version is not None,
        ))

    def items(self) -> tuple[tuple[str, object], ...]:
        """Active filters as canonical (field, value) pairs, fixed order.

        Field names are the canonical Phase 4.4 payload keys — the
        domain→store contract — never provider-specific identifiers.
        """
        active: list[tuple[str, object]] = []
        if self.source_id is not None:
            active.append(("source_id", self.source_id))
        if self.source_type is not None:
            active.append(("source_type", self.source_type))
        if self.document_id is not None:
            active.append(("document_id", self.document_id))
        if self.document_version is not None:
            active.append(("document_version", self.document_version))
        return tuple(active)

    def accepts(self, result: "EvidenceRetrievalResult") -> bool:
        """AND-semantics membership check used for defense-in-depth
        re-validation of every provider-returned result."""
        if (self.source_id is not None
                and result.source_id != self.source_id):
            return False
        if (self.source_type is not None
                and result.source_type != self.source_type):
            return False
        if (self.document_id is not None
                and result.document_id != self.document_id):
            return False
        if (self.document_version is not None
                and result.document_version != self.document_version):
            return False
        return True


@runtime_checkable
class EvidenceRetriever(Protocol):
    """Domain retrieval contract: tenant-scoped query → ranked results.

    Tenant identity is a required keyword — no retrieve call can omit
    tenant scope — and implementations must never return evidence indexed
    for a different tenant. The contract is provider-independent: callers
    depend on this protocol, never on Qdrant or any vector-store SDK.
    ``scope`` carries optional metadata restrictions only — it can never
    express or weaken tenant isolation.
    """

    def retrieve(
        self,
        query: EvidenceRetrievalQuery,
        *,
        tenant_id: Any,
        scope: EvidenceRetrievalScope | None = None,
    ) -> list[EvidenceRetrievalResult]:
        ...


class VectorIndexEvidenceRetriever:
    """Vector-backed ``EvidenceRetriever`` over the index boundary.

    Embeds the query text through the existing ``EmbeddingProvider``
    boundary with the explicit ``EmbeddingModelConfig`` used for
    indexing, then delegates the tenant-scoped search to
    ``EvidenceVectorIndex.find``. Contains no vector-store logic of its
    own and never imports a provider SDK — the same orchestration style
    as ``EvidenceIndexSyncService`` (Phase 4.5), in reverse.

    Ordering invariant (Phase 5.2): results are returned in descending
    relevance score with ties broken by ascending ``chunk_id``. The sort
    only normalizes output to this documented contract (providers score
    higher = more similar for every configured distance metric) and
    resolves tie order that providers leave unspecified — it never
    recomputes, modifies, or reranks scores.

    Duplicate rule (Phase 5.2): after ordering, a result whose
    (``document_id``, ``content_fingerprint``) already appeared is
    dropped — same document identity (which fixes tenant + source +
    version) AND identical content is redundant. Evidence from
    different documents, versions, or sources is never collapsed, even
    for byte-identical text, because its provenance differs.
    Near-duplicates (non-identical text) are never collapsed — the
    existing identity model provides no safe deterministic rule for
    that, and heuristics are intentionally deferred.

    Scope semantics (Phase 5.3): ``scope`` restricts optional metadata
    (``source_id``, ``source_type``, ``document_id``,
    ``document_version``) with conjunctive (AND) exact-equality
    semantics; an empty or omitted scope means tenant-only retrieval.
    Tenant isolation is mandatory, applied before scope and re-checked
    after it, and can never be expressed through the scope object. Every
    returned result is re-validated against the requested scope — a
    violation raises ``VectorStoreError`` (a retrieval integrity
    failure), never a silent drop or a fake empty result.
    """

    def __init__(
        self,
        *,
        vector_index: EvidenceVectorIndex,
        provider: EmbeddingProvider,
        embedding_config: EmbeddingModelConfig,
    ) -> None:
        # str.find is a false positive for the contract method — reject
        # raw text explicitly so a string can never count as an index.
        if (
            vector_index is None
            or isinstance(vector_index, (str, bytes))
            or not callable(getattr(vector_index, "find", None))
        ):
            raise DomainValidationError("a vector index is required")
        if provider is None or not callable(getattr(provider, "embed", None)):
            raise DomainValidationError("an embedding provider is required")
        if not isinstance(embedding_config, EmbeddingModelConfig):
            raise DomainValidationError(
                "explicit EmbeddingModelConfig is required")
        self._vector_index = vector_index
        self._provider = provider
        self._embedding_config = embedding_config

    def retrieve(
        self,
        query: EvidenceRetrievalQuery,
        *,
        tenant_id: Any,
        scope: EvidenceRetrievalScope | None = None,
    ) -> list[EvidenceRetrievalResult]:
        """Return ranked, duplicate-collapsed evidence for this query.

        ``scope`` carries optional metadata restrictions only — tenant
        isolation is mandatory and never part of scope. Fail closed:
        provider and index failures, and any result that violates the
        requested scope, raise — they are never converted into an empty
        successful retrieval.
        """
        require_tenant_context(tenant_id)
        if not isinstance(query, EvidenceRetrievalQuery):
            raise DomainValidationError(
                "an evidence retrieval query is required")
        if scope is None:
            scope = EvidenceRetrievalScope()
        elif not isinstance(scope, EvidenceRetrievalScope):
            raise DomainValidationError(
                "an evidence retrieval scope is required")
        try:
            embedding = self._provider.embed(query.text)
        except Exception as exc:  # fail closed on provider failure
            raise DomainValidationError(
                f"embedding provider failed: {exc}") from exc
        vector = _validated_embedding(embedding, self._embedding_config)
        try:
            results = self._vector_index.find(
                vector, tenant_id=tenant_id, top_k=query.top_k,
                scope=scope)
        except Exception as exc:
            raise VectorStoreError("evidence retrieval", exc) from exc
        if not isinstance(results, (list, tuple)):
            raise DomainValidationError(
                "vector index produced malformed output")
        if len(results) > query.top_k:
            raise DomainValidationError(
                "vector index produced malformed output")
        validated: list[EvidenceRetrievalResult] = []
        for item in results:
            if not isinstance(item, EvidenceRetrievalResult):
                raise DomainValidationError("retrieval result is malformed")
            if item.tenant_id != tenant_id.tenant_id:
                raise VectorStoreError(
                    "evidence retrieval",
                    ValueError(
                        "vector index returned a cross-tenant result"),
                )
            if not scope.accepts(item):
                raise VectorStoreError(
                    "evidence retrieval",
                    ValueError(
                        "vector index returned a result outside the "
                        "requested scope"),
                )
            validated.append(item)
        ordered = sorted(
            validated, key=lambda item: (-item.score, item.chunk_id))
        return _collapse_exact_duplicates(ordered)


def _collapse_exact_duplicates(
    results: list[EvidenceRetrievalResult],
) -> list[EvidenceRetrievalResult]:
    """Keep the first (best-ranked) result per document + content.

    Two results share a key only when they come from the same document
    (Phase 4.0 identity fixes tenant + source + version) AND carry the
    identical content fingerprint — a safe deterministic duplicate
    rule. Different document identity ⇒ different document, version,
    or source ⇒ both results are kept, even for identical text.
    """
    seen: set[tuple[UUID, str]] = set()
    kept: list[EvidenceRetrievalResult] = []
    for result in results:
        key = evidence_duplicate_key(result)
        if key in seen:
            continue
        seen.add(key)
        kept.append(result)
    return kept
