"""Qdrant adapter for the domain EvidenceVectorIndex contract (Phase 4.4/5.1).

This is the only layer allowed to import qdrant_client. Persistence plus
the tenant-scoped ``find`` retrieval operation added in Phase 5.1: raw
query text is never accepted here (query embedding belongs to the domain
``EmbeddingProvider`` boundary), Qdrant response objects are translated
into domain ``EvidenceRetrievalResult`` values before leaving this
layer, and raw Qdrant exceptions are translated into VectorStoreError at
this boundary. Every operation is tenant-scoped; Phase 5.3 adds
translation of the domain ``EvidenceRetrievalScope`` into provider
filter conditions (mandatory tenant condition first, optional scope
conditions appended with AND semantics), and Phase 5.4 adds the
provider-independent lexical path — a full-text match on the stored
content, provisioned with a conservative text payload index, verified
against the domain's exact whole-token rule before results leave this
boundary. No second search system and no new dependency are involved.
"""

from __future__ import annotations

import math
from typing import Any
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from xportra.domain.errors import (
    DomainNotFoundError,
    DomainValidationError,
    VectorStoreError,
    require_tenant_context,
)
from xportra.domain.evidence_corpus import SOURCE_TYPES
from xportra.domain.evidence_hybrid import (
    EvidenceLexicalIndex,
    lexical_matches,
    lexical_relevance_score,
)
from xportra.domain.evidence_indexing import IndexableEvidenceChunk
from xportra.domain.evidence_retrieval import (
    EvidenceRetrievalResult,
    EvidenceRetrievalScope,
)
from xportra.domain.vector_index import (
    EvidenceVectorIndex,
    VectorIndexConfig,
)

__all__ = [
    "EvidenceLexicalIndex",
    "EvidenceVectorIndex",
    "QdrantEvidenceVectorIndex",
    "VectorIndexConfig",
    "validate_qdrant_collection_config",
]

_CONTENT_FIELD = "content"

_QDRANT_DISTANCE: dict[str, qmodels.Distance] = {
    "cosine": qmodels.Distance.COSINE,
    "euclid": qmodels.Distance.EUCLID,
    "dot": qmodels.Distance.DOT,
}

_PAYLOAD_UUID_FIELDS = ("tenant_id", "chunk_id", "document_id")


def validate_qdrant_collection_config(
    config: VectorIndexConfig, current: object
) -> None:
    """Fail closed when an existing collection is incompatible.

    Compatible → return silently (never destroy/recreate). Incompatible
    dimensions, distance, or an unsupported (e.g. named-vectors) layout →
    VectorStoreError. Raw store detail is carried as ``cause``.
    """
    if not isinstance(config, VectorIndexConfig):
        raise DomainValidationError("VectorIndexConfig is required")
    size = getattr(current, "size", None)
    distance = getattr(current, "distance", None)
    if isinstance(size, bool) or not isinstance(size, int) or distance is None:
        raise VectorStoreError(
            "ensure_collection",
            ValueError(
                "existing collection uses an unsupported vector layout"),
        )
    if size != config.embedding_dimensions:
        raise VectorStoreError(
            "ensure_collection",
            ValueError(
                "existing collection dimensions "
                f"{size} do not match configured "
                f"{config.embedding_dimensions}"),
        )
    if distance != _QDRANT_DISTANCE[config.distance_metric]:
        raise VectorStoreError(
            "ensure_collection",
            ValueError(
                "existing collection distance metric does not match "
                f"configured {config.distance_metric}"),
        )


def _validated_index_record(
    chunk: object, tenant_id: Any, config: VectorIndexConfig
) -> tuple[dict[str, Any], list[float], dict[str, Any]]:
    """Fail closed on any malformed IndexableEvidenceChunk.

    Returns (record, vector, payload). Dimensions are always checked
    against the configured index dimensions — never inferred from the
    vector itself.
    """
    if isinstance(chunk, IndexableEvidenceChunk):
        record = chunk.to_record()
    elif isinstance(chunk, dict):
        record = chunk
    else:
        raise DomainValidationError(
            "indexable evidence chunk is malformed")
    if record.get("tenant_id") != tenant_id.tenant_id:
        raise DomainValidationError("tenant identity mismatch")
    chunk_id = record.get("chunk_id")
    if not isinstance(chunk_id, UUID):
        raise DomainValidationError("chunk identity is malformed")
    document_id = record.get("document_id")
    if not isinstance(document_id, UUID):
        raise DomainValidationError("document identity is malformed")
    chunk_index = record.get("chunk_index")
    if isinstance(chunk_index, bool) or not isinstance(
        chunk_index, int
    ) or chunk_index < 0:
        raise DomainValidationError("chunk index is malformed")
    content = record.get("content")
    if not isinstance(content, str) or not content.strip():
        raise DomainValidationError("content is required")
    fingerprint = record.get("content_fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint.strip():
        raise DomainValidationError("content fingerprint is required")
    source_id = record.get("source_id")
    if not isinstance(source_id, str) or not source_id.strip():
        raise DomainValidationError("source provenance is required")
    if record.get("source_type") not in SOURCE_TYPES:
        raise DomainValidationError("unsupported source_type")
    location = record.get("source_location")
    if location is not None and not isinstance(location, str):
        raise DomainValidationError("source_location is malformed")
    version = record.get("document_version")
    if version is not None and not isinstance(version, str):
        raise DomainValidationError("document_version is malformed")
    if record.get("embedding_model") != config.embedding_model:
        raise DomainValidationError(
            "embedding model does not match the index configuration")
    dimensions = record.get("embedding_dimensions")
    if isinstance(dimensions, bool) or not isinstance(
        dimensions, int
    ) or dimensions != config.embedding_dimensions:
        raise DomainValidationError(
            "embedding dimension mismatch with the index configuration")
    raw = record.get("embedding_vector")
    if isinstance(raw, (str, bytes)) or not isinstance(raw, (list, tuple)):
        raise DomainValidationError("embedding is malformed")
    vector = list(raw)
    if not vector:
        raise DomainValidationError("embedding is empty")
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DomainValidationError("embedding values must be numeric")
        if not math.isfinite(value):
            raise DomainValidationError("embedding values must be finite")
    if len(vector) != config.embedding_dimensions:
        raise DomainValidationError(
            "embedding dimension mismatch with the index configuration")
    payload = {
        "tenant_id": str(record["tenant_id"]),
        "chunk_id": str(record["chunk_id"]),
        "document_id": str(record["document_id"]),
        "chunk_index": record["chunk_index"],
        "content": record["content"],
        "content_fingerprint": record["content_fingerprint"],
        "source_id": record["source_id"],
        "source_type": record["source_type"],
        "source_location": record.get("source_location"),
        "document_version": record.get("document_version"),
        "embedding_model": record["embedding_model"],
        "embedding_dimensions": record["embedding_dimensions"],
    }
    return record, [float(v) for v in vector], payload


class QdrantEvidenceVectorIndex:
    """Qdrant-backed implementation of EvidenceVectorIndex.

    ``chunk_id`` is the canonical point ID (chunk_id → vector point);
    repeated upsert of the same chunk leaves exactly one logical point.
    Every operation requires tenant context; cross-tenant reads/deletes
    behave as not-found, and ``find`` applies a mandatory tenant filter
    plus a per-result tenant re-check before any result leaves this
    boundary. Raw Qdrant failures are translated to VectorStoreError and
    never escape.
    """

    def __init__(
        self, client: QdrantClient, config: VectorIndexConfig
    ) -> None:
        if client is None:
            raise DomainValidationError("a Qdrant client is required")
        if not isinstance(config, VectorIndexConfig):
            raise DomainValidationError(
                "an explicit VectorIndexConfig is required")
        self._client = client
        self.config = config

    # ------------------------------------------------------------------
    # collection lifecycle
    # ------------------------------------------------------------------
    def ensure_collection(self) -> None:
        """Create the collection if missing; validate if present.

        Idempotent and non-destructive: a compatible existing collection
        is left intact; an incompatible one fails closed.
        """
        name = self.config.collection_name
        try:
            exists = self._client.collection_exists(name)
        except Exception as exc:
            raise VectorStoreError("ensure_collection", exc) from exc
        if not exists:
            try:
                self._client.create_collection(
                    collection_name=name,
                    vectors_config=qmodels.VectorParams(
                        size=self.config.embedding_dimensions,
                        distance=_QDRANT_DISTANCE[
                            self.config.distance_metric],
                    ),
                )
            except Exception as exc:
                raise VectorStoreError("ensure_collection", exc) from exc
            return
        try:
            info = self._client.get_collection(name)
            current = info.config.params.vectors
        except Exception as exc:
            raise VectorStoreError("ensure_collection", exc) from exc
        validate_qdrant_collection_config(self.config, current)

    # ------------------------------------------------------------------
    # persistence operations
    # ------------------------------------------------------------------
    def upsert(self, chunk: object, *, tenant_id: Any) -> dict[str, Any]:
        require_tenant_context(tenant_id)
        record, vector, payload = _validated_index_record(
            chunk, tenant_id, self.config)
        self.ensure_collection()
        point = qmodels.PointStruct(
            id=str(record["chunk_id"]), vector=vector, payload=payload)
        try:
            self._client.upsert(
                collection_name=self.config.collection_name,
                points=[point],
                wait=True,
            )
        except Exception as exc:
            raise VectorStoreError("upsert", exc) from exc
        return _payload_to_representation(payload)

    def get(self, *, tenant_id: Any, chunk_id: UUID) -> dict[str, Any]:
        require_tenant_context(tenant_id)
        if not isinstance(chunk_id, UUID):
            raise DomainValidationError("chunk identity is malformed")
        if not self._collection_exists("get"):
            raise DomainNotFoundError("vector point not found")
        points = self._retrieve([str(chunk_id)], "get")
        if not points:
            raise DomainNotFoundError("vector point not found")
        payload = dict(getattr(points[0], "payload", None) or {})
        if payload.get("tenant_id") != str(tenant_id.tenant_id):
            raise DomainNotFoundError("vector point not found")
        return _payload_to_representation(payload)

    def delete(self, *, tenant_id: Any, chunk_id: UUID) -> None:
        require_tenant_context(tenant_id)
        if not isinstance(chunk_id, UUID):
            raise DomainValidationError("chunk identity is malformed")
        if not self._collection_exists("delete"):
            raise DomainNotFoundError("vector point not found")
        points = self._retrieve([str(chunk_id)], "delete")
        if not points:
            raise DomainNotFoundError("vector point not found")
        payload = dict(getattr(points[0], "payload", None) or {})
        if payload.get("tenant_id") != str(tenant_id.tenant_id):
            raise DomainNotFoundError("vector point not found")
        try:
            self._client.delete(
                collection_name=self.config.collection_name,
                points_selector=[str(chunk_id)],
                wait=True,
            )
        except Exception as exc:
            raise VectorStoreError("delete", exc) from exc

    def count(self, *, tenant_id: Any) -> int:
        require_tenant_context(tenant_id)
        if not self._collection_exists("count"):
            return 0
        try:
            result = self._client.count(
                collection_name=self.config.collection_name,
                count_filter=qmodels.Filter(
                    must=[_tenant_condition(tenant_id)]
                ),
                exact=True,
            )
        except Exception as exc:
            raise VectorStoreError("count", exc) from exc
        return int(result.count)

    # ------------------------------------------------------------------
    # retrieval operation (Phase 5.1)
    # ------------------------------------------------------------------
    def find(
        self,
        query_vector: object,
        *,
        tenant_id: Any,
        top_k: int,
        scope: EvidenceRetrievalScope | None = None,
    ) -> list[EvidenceRetrievalResult]:
        """Tenant-scoped, scope-filtered search → domain results.

        The mandatory tenant condition plus every optional scope
        condition are applied by the provider call itself, and every
        returned point is re-checked against the tenant AND the
        requested scope before it leaves this boundary (defense in
        depth — an out-of-scope result is an integrity failure, never a
        silent pass-through). An empty scope means tenant-only
        filtering. A missing collection or zero matches yields an empty
        result — never an error. Provider order (best score first) is
        preserved; the provider-specific Qdrant response never escapes.
        """
        require_tenant_context(tenant_id)
        vector = _validated_query_vector(query_vector, self.config)
        if (
            isinstance(top_k, bool)
            or not isinstance(top_k, int)
            or top_k <= 0
        ):
            raise DomainValidationError("top-k must be a positive integer")
        if scope is None:
            scope = EvidenceRetrievalScope()
        elif not isinstance(scope, EvidenceRetrievalScope):
            raise DomainValidationError(
                "an evidence retrieval scope is required")
        if not self._collection_exists("find"):
            return []
        must = [_tenant_condition(tenant_id), *_scope_conditions(scope)]
        try:
            response = self._client.query_points(
                collection_name=self.config.collection_name,
                query=vector,
                limit=top_k,
                query_filter=qmodels.Filter(must=must),
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            raise VectorStoreError("find", exc) from exc
        if response is None:
            raise VectorStoreError(
                "find",
                ValueError("vector search returned no response"),
            )
        points = list(getattr(response, "points", None) or [])
        results: list[EvidenceRetrievalResult] = []
        for point in points:
            payload = dict(getattr(point, "payload", None) or {})
            try:
                representation = _payload_to_representation(payload)
                representation["score"] = float(point.score)
                result = EvidenceRetrievalResult.from_record(representation)
            except Exception as exc:
                raise VectorStoreError("find", exc) from exc
            if result.tenant_id != tenant_id.tenant_id:
                raise VectorStoreError(
                    "find",
                    ValueError(
                        "vector search returned a cross-tenant result"),
                )
            if (
                result.embedding_model != self.config.embedding_model
                or result.embedding_dimensions
                != self.config.embedding_dimensions
            ):
                raise VectorStoreError(
                    "find",
                    ValueError(
                        "retrieved payload does not match the index "
                        "configuration"),
                )
            if not scope.accepts(result):
                raise VectorStoreError(
                    "find",
                    ValueError(
                        "vector search returned a result outside the "
                        "requested scope"),
                )
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # lexical retrieval operation (Phase 5.4)
    # ------------------------------------------------------------------
    def find_lexical(
        self,
        terms: object,
        *,
        tenant_id: Any,
        top_k: int,
        scope: EvidenceRetrievalScope | None = None,
    ) -> list[EvidenceRetrievalResult]:
        """Tenant-scoped, scope-filtered lexical search → domain results.

        Provider filter: the mandatory tenant condition, the optional
        Phase 5.3 scope conditions, and a full-text match on the stored
        content. No vector is involved, and filter-only retrieval carries
        no provider relevance score, so each verified match carries the
        domain's deterministic lexical relevance (total query-term
        occurrences) in ``score``. Provider over-matches (tokenizer or
        prefix artifacts) are narrowed by verifying the domain rule —
        every term present as a whole token. Tenant/scope violations are
        integrity failures. Results are ordered deterministically by
        lexical relevance descending, then ``chunk_id`` ascending. A
        missing collection yields an empty result, never an error.
        """
        require_tenant_context(tenant_id)
        validated_terms = _validated_lexical_terms(terms)
        if (
            isinstance(top_k, bool)
            or not isinstance(top_k, int)
            or top_k <= 0
        ):
            raise DomainValidationError("top-k must be a positive integer")
        if scope is None:
            scope = EvidenceRetrievalScope()
        elif not isinstance(scope, EvidenceRetrievalScope):
            raise DomainValidationError(
                "an evidence retrieval scope is required")
        if not self._collection_exists("find_lexical"):
            return []
        self._ensure_content_text_index()
        must = [_tenant_condition(tenant_id), *_scope_conditions(scope)]
        must.append(
            qmodels.FieldCondition(
                key=_CONTENT_FIELD,
                match=qmodels.MatchText(text=" ".join(validated_terms)),
            )
        )
        try:
            records, _offset = self._client.scroll(
                collection_name=self.config.collection_name,
                scroll_filter=qmodels.Filter(must=must),
                limit=top_k,
                with_payload=True,
                with_vectors=False,
            )
        except Exception as exc:
            raise VectorStoreError("find_lexical", exc) from exc
        results: list[EvidenceRetrievalResult] = []
        for record in list(records):
            payload = dict(getattr(record, "payload", None) or {})
            try:
                representation = _payload_to_representation(payload)
                content = representation.get(_CONTENT_FIELD)
                if not isinstance(content, str) or not content.strip():
                    raise DomainValidationError("content is required")
                if not lexical_matches(content, validated_terms):
                    continue  # provider over-match (e.g. prefix artifact)
                representation["score"] = lexical_relevance_score(
                    content, validated_terms)
                result = EvidenceRetrievalResult.from_record(
                    representation)
            except Exception as exc:
                raise VectorStoreError("find_lexical", exc) from exc
            if result.tenant_id != tenant_id.tenant_id:
                raise VectorStoreError(
                    "find_lexical",
                    ValueError(
                        "lexical search returned a cross-tenant result"),
                )
            if not scope.accepts(result):
                raise VectorStoreError(
                    "find_lexical",
                    ValueError(
                        "lexical search returned a result outside the "
                        "requested scope"),
                )
            if (
                result.embedding_model != self.config.embedding_model
                or result.embedding_dimensions
                != self.config.embedding_dimensions
            ):
                raise VectorStoreError(
                    "find_lexical",
                    ValueError(
                        "retrieved payload does not match the index "
                        "configuration"),
                )
            results.append(result)
        results.sort(key=lambda item: (-item.score, item.chunk_id))
        return results

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _collection_exists(self, operation: str) -> bool:
        try:
            return bool(
                self._client.collection_exists(self.config.collection_name))
        except Exception as exc:
            raise VectorStoreError(operation, exc) from exc

    def _retrieve(self, ids: list[str], operation: str) -> list[Any]:
        try:
            return list(self._client.retrieve(
                collection_name=self.config.collection_name,
                ids=ids,
                with_payload=True,
                with_vectors=False,
            ))
        except Exception as exc:
            raise VectorStoreError(operation, exc) from exc

    def _ensure_content_text_index(self) -> None:
        """Idempotently provision the conservative content text index.

        The lexical path needs a full-text payload index on ``content``.
        Provisioning is additive and non-destructive: a compatible
        existing text index is left untouched and an incompatible one
        fails closed. Creation uses the WORD tokenizer with lowercase and
        no stop-word/stemmer configuration, so the provider tokenizer
        stays as close as possible to the domain's deterministic rule —
        the domain rule is still verified explicitly afterwards.
        """
        name = self.config.collection_name
        field = _CONTENT_FIELD
        try:
            info = self._client.get_collection(name)
        except Exception as exc:
            raise VectorStoreError(
                "ensure_content_text_index", exc) from exc
        schema = getattr(info, "payload_schema", None) or {}
        existing = schema.get(field) if hasattr(schema, "get") else None
        if existing is not None:
            data_type = getattr(existing, "data_type", None)
            if str(getattr(data_type, "value", data_type)) == "text":
                return
            raise VectorStoreError(
                "ensure_content_text_index",
                ValueError(
                    "existing payload index for content is not a "
                    "full-text index"),
            )
        try:
            self._client.create_payload_index(
                collection_name=name,
                field_name=field,
                field_schema=qmodels.TextIndexParams(
                    type=qmodels.TextIndexType.TEXT,
                    tokenizer=qmodels.TokenizerType.WORD,
                    lowercase=True,
                ),
                wait=True,
            )
        except Exception as exc:
            raise VectorStoreError(
                "ensure_content_text_index", exc) from exc



def _tenant_condition(tenant_id: Any) -> qmodels.FieldCondition:
    """The mandatory tenant condition — always present, never optional."""
    return qmodels.FieldCondition(
        key="tenant_id",
        match=qmodels.MatchValue(value=str(tenant_id.tenant_id)),
    )


def _scope_conditions(
    scope: EvidenceRetrievalScope,
) -> list[qmodels.FieldCondition]:
    """Optional Phase 5.3 metadata conditions (AND semantics)."""
    conditions: list[qmodels.FieldCondition] = []
    for key, value in scope.items():
        conditions.append(
            qmodels.FieldCondition(
                key=key,
                match=qmodels.MatchValue(
                    value=str(value) if isinstance(value, UUID) else value),
            )
        )
    return conditions


def _validated_lexical_terms(raw: object) -> tuple[str, ...]:
    """Fail closed on any non-canonical lexical term input.

    Terms must be the canonical output of the domain ``lexical_terms``:
    lowercase alphanumeric tokens, deduplicated, non-empty.
    """
    if isinstance(raw, (str, bytes)) or not isinstance(raw, (list, tuple)):
        raise DomainValidationError("lexical terms are malformed")
    terms = tuple(raw)
    if not terms:
        raise DomainValidationError("lexical terms are required")
    for term in terms:
        if (not isinstance(term, str) or not term
                or term != term.lower() or not term.isalnum()):
            raise DomainValidationError("lexical terms are malformed")
    if len(set(terms)) != len(terms):
        raise DomainValidationError("lexical terms are malformed")
    return terms


def _validated_query_vector(
    raw: object, config: VectorIndexConfig
) -> list[float]:
    """Fail closed on any malformed query embedding.

    Dimensions are checked against the configured index dimensions —
    never inferred from the vector itself (same rule as upsert).
    """
    if isinstance(raw, (str, bytes)) or not isinstance(raw, (list, tuple)):
        raise DomainValidationError("query embedding is malformed")
    vector = list(raw)
    if not vector:
        raise DomainValidationError("query embedding is empty")
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DomainValidationError(
                "query embedding values must be numeric")
        if not math.isfinite(value):
            raise DomainValidationError(
                "query embedding values must be finite")
    if len(vector) != config.embedding_dimensions:
        raise DomainValidationError(
            "embedding dimension mismatch with the index configuration")
    return [float(value) for value in vector]


def _payload_to_representation(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize a persisted payload back into domain-friendly types."""
    out = dict(payload)
    for field in _PAYLOAD_UUID_FIELDS:
        value = out.get(field)
        if isinstance(value, str):
            try:
                out[field] = UUID(value)
            except ValueError:
                raise DomainValidationError(
                    "persisted payload identity is malformed")
    return out
