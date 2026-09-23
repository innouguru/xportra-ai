"""Evidence chunking boundary for Phase 4.2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from xportra.persistence.tenant import TenantContext

from .errors import DomainValidationError, require_tenant_context
from .evidence_corpus import (
    SOURCE_TYPES,
    EvidenceDocument,
    content_fingerprint,
)

MAX_CHUNK_CHARACTERS = 1200


def stable_chunk_id(
    tenant_id: UUID,
    document_id: UUID,
    chunk_index: int,
    fingerprint: str,
) -> UUID:
    """Stable uuid5 from tenant hex + document hex + index + fingerprint.

    No secrets, no timestamps, no random values.
    """
    key = ":".join([
        "xportra:evidence-chunk",
        tenant_id.hex,
        document_id.hex,
        str(chunk_index),
        fingerprint,
    ])
    return uuid5(NAMESPACE_URL, key)


def _segment_paragraphs(content: str) -> list[tuple[int, int]]:
    """Deterministic blank-line paragraph segmentation.

    Returns ``(start, end)`` offsets into the original content. Blank-line
    separators are the only structural delimiters removed; paragraph text
    itself is preserved exactly as a substring of the document content.
    Whitespace-only paragraphs produce no segment.
    """
    bounds: list[tuple[int, int]] = []
    start: int | None = None
    end = 0
    pos = 0
    for line in content.split("\n"):
        line_start = pos
        line_end = pos + len(line)
        pos = line_end + 1
        if line.strip() == "":
            if start is not None:
                bounds.append((start, end))
                start = None
            continue
        if start is None:
            start = line_start
        end = line_end
    if start is not None:
        bounds.append((start, end))
    return bounds


def _split_oversized(
    content: str, start: int, end: int
) -> list[tuple[int, int]]:
    """Deterministically split one oversized paragraph.

    Cuts at the last whitespace inside each maximum-size window; if the
    window contains no whitespace (a single oversized word), cuts at the
    exact window boundary. The single whitespace character at a cut is the
    only character dropped. Every slice is an exact substring.
    """
    slices: list[tuple[int, int]] = []
    cursor = start
    while cursor < end:
        if end - cursor <= MAX_CHUNK_CHARACTERS:
            slices.append((cursor, end))
            break
        window_end = cursor + MAX_CHUNK_CHARACTERS
        window = content[cursor:window_end]
        cut = None
        for offset in range(len(window) - 1, 0, -1):
            if window[offset].isspace():
                cut = offset
                break
        if cut is None:
            slices.append((cursor, window_end))
            cursor = window_end
        else:
            slices.append((cursor, cursor + cut))
            cursor = cursor + cut + 1
    return slices


@dataclass(frozen=True)
class EvidenceChunk:
    """Bounded, traceable, deterministic unit of an evidence document."""

    tenant_id: UUID
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    content: str
    content_fingerprint: str
    source_id: str
    source_type: str
    source_location: str | None = None
    document_version: str | None = None
    start_offset: int = 0
    end_offset: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.tenant_id, UUID):
            raise DomainValidationError("tenant_id must be a UUID")
        if not isinstance(self.chunk_id, UUID):
            raise DomainValidationError("chunk_id must be a UUID")
        if not isinstance(self.document_id, UUID):
            raise DomainValidationError("document_id must be a UUID")
        if not isinstance(self.chunk_index, int) or self.chunk_index < 0:
            raise DomainValidationError("chunk_index is malformed")
        if not isinstance(self.content, str) or not self.content.strip():
            raise DomainValidationError("chunk content is required")
        if self.content_fingerprint != content_fingerprint(self.content):
            raise DomainValidationError("chunk content fingerprint mismatch")
        if self.source_type not in SOURCE_TYPES:
            raise DomainValidationError("unsupported source_type")
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise DomainValidationError("source_id is required")
        if (not isinstance(self.start_offset, int)
                or not isinstance(self.end_offset, int)
                or self.start_offset < 0
                or self.end_offset <= self.start_offset):
            raise DomainValidationError("chunk offsets are malformed")

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
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
        }


class EvidenceChunkingService:
    """Transform an evidence document into deterministic evidence chunks.

    Entry ``chunk(document, *, tenant_id)`` segments persisted document
    content into bounded ``EvidenceChunk`` records. Content is never
    rewritten: no summarizing, paraphrasing, translation, or LLM use. The
    only normalization is deterministic blank-line paragraph segmentation.
    Provenance and tenant identity are propagated unchanged; sections,
    headings, and authorities are never inferred. No persistence, no
    embeddings, no retrieval, no RAG.
    """

    def chunk(
        self,
        document: EvidenceDocument | dict[str, Any],
        *,
        tenant_id: TenantContext,
    ) -> list[dict[str, Any]]:
        """Return deterministic chunk records for one evidence document."""
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
        content = record.get("content")
        if not isinstance(content, str) or not content.strip():
            raise DomainValidationError("content is required")
        source_id = record.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise DomainValidationError("source_id is required")
        source_type = record.get("source_type")
        if source_type not in SOURCE_TYPES:
            raise DomainValidationError("unsupported source_type")
        version = record.get("document_version")
        if version is not None and not isinstance(version, str):
            raise DomainValidationError("document_version is malformed")
        chunks: list[dict[str, Any]] = []
        for start, end in _segment_paragraphs(content):
            if end - start <= MAX_CHUNK_CHARACTERS:
                bounds = [(start, end)]
            else:
                bounds = _split_oversized(content, start, end)
            for piece_start, piece_end in bounds:
                piece = content[piece_start:piece_end]
                if not piece.strip():
                    continue
                fingerprint = content_fingerprint(piece)
                chunk = EvidenceChunk(
                    tenant_id=tenant_id.tenant_id,
                    chunk_id=stable_chunk_id(
                        tenant_id.tenant_id,
                        document_id,
                        len(chunks),
                        fingerprint,
                    ),
                    document_id=document_id,
                    chunk_index=len(chunks),
                    content=piece,
                    content_fingerprint=fingerprint,
                    source_id=source_id,
                    source_type=source_type,
                    source_location=record.get("source_location"),
                    document_version=version,
                    start_offset=piece_start,
                    end_offset=piece_end,
                )
                chunks.append(chunk.to_record())
        return chunks
