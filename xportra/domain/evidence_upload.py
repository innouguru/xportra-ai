"""Evidence file-upload validation boundary for Phase 10.4.

Implements the approved product decisions U1 (MVP file types)
and U2 (10 MB maximum) from ``REQUIREMENTS.md`` R-10.4:

- Accepted types: PDF, DOCX, JPG/JPEG, PNG — and nothing
  else. No additional format is accepted without an
  explicit product decision.
- Every file is validated by BOTH its declared content
  type AND authoritative magic-byte/content inspection.
  The client MIME type alone is never trusted, and the
  filename extension is a consistency check only — never
  the authoritative type.
- Maximum 10 MB per file, enforced here on decoded bytes
  (the API layer additionally bounds the transport shape;
  frontend validation alone is never sufficient).
- Filenames are sanitized for safe handling (no
  directories, null bytes, or control characters survive)
  and are stored as display metadata only — they never
  reach storage keys (see ``evidence_storage``) and never
  influence identity.
- Uploaded files are never executed. Parsing below only
  reads bytes; archives are inspected structurally, XML
  with entity declarations is rejected, and extracted
  text is length-bounded.

This module owns no I/O, no persistence, no retrieval,
and no compliance truth. ``uploaded != ready`` and
``ready != sufficient != satisfied`` hold by construction:
validation success only means the bytes may be stored.
"""

from __future__ import annotations

import hashlib
import io
import re
import struct
import zipfile
import zlib
from dataclasses import dataclass
from typing import Any
from uuid import UUID
from xml.etree import ElementTree as _ElementTree

from .errors import DomainValidationError

#: R-10.4 U2: maximum upload size, 10 MB per file.
MAX_EVIDENCE_UPLOAD_BYTES = 10 * 1024 * 1024

#: R-10.4 U1: the closed set of accepted evidence file kinds.
UPLOAD_KIND_PDF = "pdf"
UPLOAD_KIND_DOCX = "docx"
UPLOAD_KIND_JPEG = "jpeg"
UPLOAD_KIND_PNG = "png"

#: Canonical declared content type per kind (the only
#: accepted ``Content-Type`` values, parameters stripped).
CANONICAL_UPLOAD_CONTENT_TYPES = {
    UPLOAD_KIND_PDF: "application/pdf",
    UPLOAD_KIND_DOCX: (
        "application/vnd.openxmlformats-officedocument"
        ".wordprocessingml.document"
    ),
    UPLOAD_KIND_JPEG: "image/jpeg",
    UPLOAD_KIND_PNG: "image/png",
}

#: Filename extensions accepted per kind. Extensions are a
#: consistency check only — magic bytes are authoritative.
UPLOAD_EXTENSIONS = {
    UPLOAD_KIND_PDF: (".pdf",),
    UPLOAD_KIND_DOCX: (".docx",),
    UPLOAD_KIND_JPEG: (".jpg", ".jpeg"),
    UPLOAD_KIND_PNG: (".png",),
}

#: Canonical extension used in server-composed object keys.
CANONICAL_UPLOAD_EXTENSION = {
    UPLOAD_KIND_PDF: ".pdf",
    UPLOAD_KIND_DOCX: ".docx",
    UPLOAD_KIND_JPEG: ".jpg",
    UPLOAD_KIND_PNG: ".png",
}

#: Bound on extracted text (zip-bomb / decompression guard).
MAX_EXTRACTED_TEXT_CHARACTERS = 1_000_000

#: Bound on sanitized display filenames.
MAX_FILENAME_CHARACTERS = 255

_PDF_MAGIC = b"%PDF-"
_ZIP_MAGIC = b"PK\x03\x04"
_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

_PDF_LITERAL_STRING = re.compile(rb"\((?:[^()\\]|\\.)*\)")


class EvidenceFileValidationError(DomainValidationError):
    """An uploaded file violates the MVP type/identity policy."""


class EvidenceFileTooLargeError(EvidenceFileValidationError):
    """An uploaded file exceeds the 10 MB per-file limit."""


class EvidenceTextExtractionError(DomainValidationError):
    """No usable text could be extracted from a valid file.

    The file itself passed validation; extraction failure is
    a *processing* outcome (``processing = failed`` with the
    parse step), never a validation rejection.
    """


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    """A file that passed the validation boundary.

    Carries identifiers and policy outcomes only — never
    the file bytes.
    """

    content_hash: str
    detected_kind: str
    content_type: str
    extension: str
    original_filename: str
    size_bytes: int


def validate_upload_file(
    *,
    filename: Any,
    content_type: Any,
    content: Any,
) -> ValidatedUpload:
    """Validate one uploaded file against the MVP policy.

    Order is deterministic: shape → size → filename →
    declared type → extension consistency → magic bytes.
    Oversize is reported distinctly so callers can map it
    to a 413-class response; every other violation is a
    plain validation failure.
    """
    if not isinstance(content, (bytes, bytearray)):
        raise EvidenceFileValidationError(
            "evidence file content must be bytes")
    raw = bytes(content)
    if not raw:
        raise EvidenceFileValidationError(
            "evidence file is empty")
    if len(raw) > MAX_EVIDENCE_UPLOAD_BYTES:
        raise EvidenceFileTooLargeError(
            "evidence file exceeds the 10 MB per-file limit")

    safe_name = sanitize_filename(filename)
    declared = _normalize_content_type(content_type)
    kind = _kind_for_content_type(declared)
    _require_extension_consistency(safe_name, kind)
    _require_magic_bytes(kind, raw)

    return ValidatedUpload(
        content_hash=hashlib.sha256(raw).hexdigest(),
        detected_kind=kind,
        content_type=declared,
        extension=CANONICAL_UPLOAD_EXTENSION[kind],
        original_filename=safe_name,
        size_bytes=len(raw),
    )


def sanitize_filename(filename: Any) -> str:
    """Reduce a client filename to a safe display name.

    Strips directory components (both separators), rejects
    null bytes and control characters, and rejects empty,
    dot-only, or over-long names. The result is display
    metadata only — never identity, never a storage path.
    """
    if not isinstance(filename, str):
        raise EvidenceFileValidationError(
            "evidence filename is required")
    if "\x00" in filename:
        raise EvidenceFileValidationError(
            "evidence filename is malformed")
    if "/" in filename or "\\" in filename:
        raise EvidenceFileValidationError(
            "evidence filename must not contain path separators")
    candidate = filename.strip()
    if not candidate or candidate in (".", ".."):
        raise EvidenceFileValidationError(
            "evidence filename is malformed")
    if any(ord(char) < 32 or ord(char) == 127 for char in candidate):
        raise EvidenceFileValidationError(
            "evidence filename is malformed")
    if len(candidate) > MAX_FILENAME_CHARACTERS:
        raise EvidenceFileValidationError(
            "evidence filename is too long")
    return candidate


def compose_object_key(
    *,
    tenant_id: UUID,
    evidence_id: UUID,
    content_hash: str,
    extension: str,
) -> str:
    """Compose the server-side storage object key.

    ``tenant/{tenant_id}/evidence/{evidence_id}/{hash}{ext}``.
    Only server-held values participate — client-supplied
    paths, keys, and filenames can never reach storage.
    """
    if not isinstance(tenant_id, UUID):
        raise DomainValidationError("tenant identity is required")
    if not isinstance(evidence_id, UUID):
        raise DomainValidationError("evidence identity is required")
    if (not isinstance(content_hash, str)
            or not re.fullmatch(r"[0-9a-f]{64}", content_hash)):
        raise DomainValidationError("content hash is malformed")
    if extension not in (".pdf", ".docx", ".jpg", ".png"):
        raise DomainValidationError("extension is not an MVP type")
    return (
        f"tenant/{tenant_id.hex}/evidence/"
        f"{evidence_id.hex}/{content_hash}{extension}"
    )


def _normalize_content_type(content_type: Any) -> str:
    if not isinstance(content_type, str):
        raise EvidenceFileValidationError(
            "evidence content type is required")
    normalized = content_type.split(";")[0].strip().lower()
    if not normalized:
        raise EvidenceFileValidationError(
            "evidence content type is required")
    return normalized


def _kind_for_content_type(declared: str) -> str:
    for kind, canonical in CANONICAL_UPLOAD_CONTENT_TYPES.items():
        if declared == canonical:
            return kind
    raise EvidenceFileValidationError(
        f"unsupported evidence content type: {declared}")


def _require_extension_consistency(filename: str, kind: str) -> None:
    lowered = filename.lower()
    if not any(lowered.endswith(ext) for ext in UPLOAD_EXTENSIONS[kind]):
        raise EvidenceFileValidationError(
            "filename extension does not match the declared content type")


def _require_magic_bytes(kind: str, raw: bytes) -> None:
    if kind == UPLOAD_KIND_PDF:
        valid = raw.startswith(_PDF_MAGIC)
    elif kind == UPLOAD_KIND_DOCX:
        valid = raw.startswith(_ZIP_MAGIC) and _is_docx_archive(raw)
    elif kind == UPLOAD_KIND_JPEG:
        valid = raw.startswith(_JPEG_MAGIC)
    elif kind == UPLOAD_KIND_PNG:
        valid = raw.startswith(_PNG_MAGIC)
    else:  # pragma: no cover - closed kind set above
        raise EvidenceFileValidationError("unsupported evidence file kind")
    if not valid:
        raise EvidenceFileValidationError(
            "file content does not match the declared content type")


def _is_docx_archive(raw: bytes) -> bool:
    """Confirm the zip archive has the DOCX document structure."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            names = set(archive.namelist())
    except (zipfile.BadZipFile, ValueError, EOFError):
        return False
    return (
        "[Content_Types].xml" in names
        and "word/document.xml" in names
    )


def extract_upload_text(kind: str, content: bytes) -> str:
    """Extract indexable text from validated file bytes.

    stdlib-only, best-effort adapters for the MVP types:
    DOCX document paragraphs, PDF content-stream literal
    strings (including zlib-compressed streams), and
    embedded PNG/JPEG metadata text. Raises
    ``EvidenceTextExtractionError`` when no usable text is
    found — the caller records ``processing = failed`` at
    the parse step; the file itself was valid.
    """
    if not isinstance(content, (bytes, bytearray)):
        raise EvidenceTextExtractionError("evidence content is required")
    raw = bytes(content)
    if kind == UPLOAD_KIND_DOCX:
        text = _extract_docx_text(raw)
    elif kind == UPLOAD_KIND_PDF:
        text = _extract_pdf_text(raw)
    elif kind in (UPLOAD_KIND_JPEG, UPLOAD_KIND_PNG):
        text = _extract_image_text(kind, raw)
    else:
        raise EvidenceTextExtractionError("unsupported evidence file kind")
    cleaned = text.strip()
    if not cleaned:
        raise EvidenceTextExtractionError(
            "document produced no usable text content")
    if len(cleaned) > MAX_EXTRACTED_TEXT_CHARACTERS:
        raise EvidenceTextExtractionError(
            "extracted document text exceeds the processing bound")
    return cleaned


def _extract_docx_text(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            try:
                document_xml = archive.read("word/document.xml")
            except KeyError as cause:
                raise EvidenceTextExtractionError(
                    "document is not a readable docx archive"
                ) from cause
    except (zipfile.BadZipFile, ValueError, EOFError) as cause:
        raise EvidenceTextExtractionError(
            "document is not a readable docx archive") from cause
    if b"<!DOCTYPE" in document_xml or b"<!ENTITY" in document_xml:
        raise EvidenceTextExtractionError(
            "document contains forbidden markup declarations")
    try:
        root = _ElementTree.fromstring(document_xml)
    except _ElementTree.ParseError as cause:
        raise EvidenceTextExtractionError(
            "document markup is malformed") from cause
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        runs = [
            node.text
            for node in paragraph.findall(".//w:t", namespace)
            if node.text
        ]
        joined = "".join(runs).strip()
        if joined:
            paragraphs.append(joined)
    if not paragraphs:
        # Fallback for documents that carry text outside paragraphs.
        runs = [
            node.text
            for node in root.iter()
            if node.tag.endswith("}t") and node.text
        ]
        paragraphs = [text for text in ("".join(runs).strip(),) if text]
    return "\n\n".join(paragraphs)


def _extract_pdf_text(raw: bytes) -> str:
    if not raw.startswith(_PDF_MAGIC):
        raise EvidenceTextExtractionError("document is not a PDF file")
    pieces: list[str] = []
    for match in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.DOTALL):
        blob = match.group(1).strip()
        try:
            decoded = zlib.decompress(blob)
        except zlib.error:
            decoded = blob
        pieces.extend(_pdf_literal_strings(decoded))
    if not pieces:
        pieces.extend(_pdf_literal_strings(raw))
    return "\n".join(piece for piece in pieces if piece)


def _pdf_literal_strings(blob: bytes) -> list[str]:
    found: list[str] = []
    for match in _PDF_LITERAL_STRING.finditer(blob):
        literal = match.group(0)[1:-1]
        literal = (
            literal.replace(b"\\(", b"(")
            .replace(b"\\)", b")")
            .replace(b"\\\\", b"\\")
            .replace(b"\\n", b"\n")
            .replace(b"\\r", b"\r")
            .replace(b"\\t", b"\t")
        )
        text = literal.decode("latin-1").strip()
        if text:
            found.append(text)
    return found


def _extract_image_text(kind: str, raw: bytes) -> str:
    if kind == UPLOAD_KIND_PNG:
        return _extract_png_text(raw)
    return _extract_jpeg_text(raw)


def _extract_png_text(raw: bytes) -> str:
    if not raw.startswith(_PNG_MAGIC):
        raise EvidenceTextExtractionError("document is not a PNG file")
    texts: list[str] = []
    offset = len(_PNG_MAGIC)
    while offset + 8 <= len(raw):
        (length,) = struct.unpack(">I", raw[offset:offset + 4])
        chunk_type = raw[offset + 4:offset + 8]
        data = raw[offset + 8:offset + 8 + length]
        if len(data) != length or offset + 8 + length + 4 > len(raw):
            break
        if chunk_type == b"tEXt" and b"\x00" in data:
            _, _, text = data.partition(b"\x00")
            decoded = text.decode("latin-1").strip()
            if decoded:
                texts.append(decoded)
        offset += 8 + length + 4
        if chunk_type == b"IEND":
            break
    return "\n".join(texts)


def _extract_jpeg_text(raw: bytes) -> str:
    if not raw.startswith(_JPEG_MAGIC):
        raise EvidenceTextExtractionError("document is not a JPEG file")
    texts: list[str] = []
    offset = 2
    while offset + 4 <= len(raw):
        if raw[offset] != 0xFF:
            break
        marker = raw[offset + 1]
        if marker == 0xD9:  # EOI
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            offset += 2
            continue
        (length,) = struct.unpack(">H", raw[offset + 2:offset + 4])
        if length < 2 or offset + 2 + length > len(raw):
            break
        if marker == 0xFE:  # COM segment
            decoded = raw[offset + 4:offset + 2 + length].decode(
                "latin-1").strip()
            if decoded:
                texts.append(decoded)
        offset += 2 + length
    return "\n".join(texts)


#: R-10.4 U7: dedicated processing lifecycle, separate from
#: evidence availability, requirement applicability, and
#: assessment state. ``ready`` means the document passed
#: the ingestion/indexing pipeline required for use —
#: never compliance.
PROCESSING_UPLOADED = "uploaded"
PROCESSING_PROCESSING = "processing"
PROCESSING_READY = "ready"
PROCESSING_FAILED = "failed"

EVIDENCE_PROCESSING_STATES = frozenset({
    PROCESSING_UPLOADED,
    PROCESSING_PROCESSING,
    PROCESSING_READY,
    PROCESSING_FAILED,
})

#: Pipeline steps recorded on processing failure (retry affordance).
PROCESSING_FAILURE_STEPS = frozenset({"parse", "ingest", "sync"})


def is_evidence_usable(row: Any) -> bool:
    """Whether an evidence row may participate in new analysis.

    Usable means ``processing = ready`` AND not
    inactive/superseded (R-10.4 U3: the existing
    ``archived`` review status hides without removing).
    ``ready`` alone never implies sufficiency or
    satisfaction — those still require the Phase 2.6
    rule (explicit link + accepted/reviewed supporting
    status, evaluated by assessment). Malformed rows
    fail closed to unusable.
    """
    if not isinstance(row, dict):
        return False
    if row.get("processing_status", PROCESSING_UPLOADED) != PROCESSING_READY:
        return False
    return row.get("status") not in ("archived", "rejected")


__all__ = [
    "CANONICAL_UPLOAD_CONTENT_TYPES",
    "CANONICAL_UPLOAD_EXTENSION",
    "EVIDENCE_PROCESSING_STATES",
    "MAX_EVIDENCE_UPLOAD_BYTES",
    "MAX_EXTRACTED_TEXT_CHARACTERS",
    "MAX_FILENAME_CHARACTERS",
    "PROCESSING_FAILED",
    "PROCESSING_FAILURE_STEPS",
    "PROCESSING_PROCESSING",
    "PROCESSING_READY",
    "PROCESSING_UPLOADED",
    "UPLOAD_EXTENSIONS",
    "UPLOAD_KIND_DOCX",
    "UPLOAD_KIND_JPEG",
    "UPLOAD_KIND_PDF",
    "UPLOAD_KIND_PNG",
    "EvidenceFileTooLargeError",
    "EvidenceFileValidationError",
    "EvidenceTextExtractionError",
    "ValidatedUpload",
    "compose_object_key",
    "extract_upload_text",
    "is_evidence_usable",
    "sanitize_filename",
    "validate_upload_file",
]
