"""Phase 10.4 — Evidence upload implementation tests.

Covers R-10.4 (U1–U7) against REAL boundary code; only
persistence repositories, the vector/embedding chain,
and the service container are faked/doubled:

- validation (U1/U2): MVP types, declared-type +
  magic-byte inspection, 10 MB cap, filename safety;
- storage (U4): server-composed keys, private-only
  access, opaque signed URLs, no client key control;
- lifecycle: uploaded → processing → ready | failed,
  retry, idempotent duplicates, terminal rejection
  with no mutation;
- tenant isolation + authorization across upload,
  evidence access, download, and workflow association;
- semantics: ready never implies satisfied, failed and
  archived rows are unusable, upload alters no
  applicability/assessment;
- error surface: 413 mapping, production 5xx
  sanitization, no key/URL/content leakage, no delete
  endpoint.

No prior test is modified. Live Supabase
Storage/Postgres/Qdrant paths are NOT executed here
(they remain gated on environment, as elsewhere).
"""

import base64
import io
import os
import struct
import unittest
import zlib
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

from xportra.api.app import create_app
from xportra.api.auth import MemberContext
from xportra.api.dependencies import get_evidence_upload_service
from xportra.application.context import ApplicationContext
from xportra.application.errors import (
    ApplicationNotFoundError,
    ApplicationValidationError,
    EvidenceUploadTooLargeError,
    InfrastructureError,
    TenantMismatchError,
    TerminalWorkflowError,
)
from xportra.application.evidence_upload import (
    EvidenceUploadApplicationService,
)
from xportra.domain.errors import (
    DomainNotFoundError,
    DomainValidationError,
    VectorStoreError,
)
from xportra.domain.evidence_chunking import EvidenceChunkingService
from xportra.domain.evidence_ingestion import (
    EvidenceDocumentIngestionService,
)
from xportra.domain.evidence_storage import (
    EVIDENCE_STORAGE_BUCKET,
    EvidenceObjectStore,
    EvidenceStorageError,
)
from xportra.domain.evidence_upload import (
    MAX_EVIDENCE_UPLOAD_BYTES,
    EvidenceFileTooLargeError,
    EvidenceFileValidationError,
    compose_object_key,
    extract_upload_text,
    is_evidence_usable,
    validate_upload_file,
)
from xportra.domain.ingestion import (
    RequirementAssessmentService,
    EvidenceRecord as AssessmentEvidenceRecord,
    RegulatoryRequirementApplicabilityService,
    ApplicabilityContext,
)
from xportra.infrastructure.evidence_storage import (
    InMemoryEvidenceObjectStore,
    SupabaseEvidenceObjectStore,
    SupabaseStorageSettings,
)
from xportra.persistence.tenant import TenantContext

TENANT_A_ID = UUID("11111111-1111-1111-1111-111111111111")
TENANT_B_ID = UUID("22222222-2222-2222-2222-222222222222")
TENANT_A = TenantContext(TENANT_A_ID)
TENANT_B = TenantContext(TENANT_B_ID)
ACTOR_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CASE_A = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
WORKFLOW_A = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
REQUIREMENT_A = UUID("00000000-0000-0000-0000-000000000001")
EVIDENCE_ID_1 = UUID("66666666-6666-6666-0000-000000000001")
EVIDENCE_ID_2 = UUID("66666666-6666-6666-0000-000000000002")

CTX_A = ApplicationContext(
    actor_id=ACTOR_ID, tenant=TENANT_A, role="owner")
CTX_B = ApplicationContext(
    actor_id=ACTOR_ID, tenant=TENANT_B, role="owner")

HEADER_A = {"X-Development-Tenant-ID": str(TENANT_A_ID)}
HEADER_B = {"X-Development-Tenant-ID": str(TENANT_B_ID)}

FIXED_NOW = datetime(2026, 9, 27, 12, 0, 0, tzinfo=timezone.utc)


@contextmanager
def patched_env(**values):
    previous = {name: os.environ.get(name) for name in values}
    try:
        for name, value in values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


# ------------------------------------------------------------------
# file fixtures (minimal, deterministic)
# ------------------------------------------------------------------

def make_pdf(text="Phytosanitary certificate for cocoa beans"):
    body = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
    blob = (
        "%PDF-1.4\n1 0 obj\n<< /Length "
        + str(len(body))
        + " >>\nstream\n" + body + "\nendstream\nendobj\ntrailer\n<<>>\n"
    )
    return blob.encode("latin-1")


def make_pdf_compressed(text="Compressed sesame inspection report"):
    body = f"BT ({text}) Tj ET".encode("latin-1")
    compressed = zlib.compress(body)
    out = bytearray(b"%PDF-1.4\n1 0 obj\n<< /Length ")
    out += str(len(compressed)).encode("ascii")
    out += b" /Filter /FlateDecode >>\nstream\n"
    out += compressed
    out += b"\nendstream\nendobj\ntrailer\n<<>>\n"
    return bytes(out)


def make_docx(paragraphs=("Cocoa export certificate", "Issued in Lagos")):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/'
            'content-types"><Override PartName="/word/document.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.'
            'wordprocessingml.document.main+xml"/></Types>',
        )
        body = "".join(
            f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
            for text in paragraphs
        )
        archive.writestr(
            "word/document.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/'
            'wordprocessingml/2006/main"><w:body>'
            + body + "</w:body></w:document>",
        )
    return buf.getvalue()


def make_png(text="Cocoa bag label"):
    out = bytearray(b"\x89PNG\r\n\x1a\n")

    def chunk(ctype, data):
        out.extend(struct.pack(">I", len(data)))
        out.extend(ctype)
        out.extend(data)
        out.extend(struct.pack(
            ">I", zlib.crc32(ctype + data) & 0xFFFFFFFF))

    chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    if text is not None:
        chunk(b"tEXt", b"Comment\x00" + text.encode("latin-1"))
    chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
    chunk(b"IEND", b"")
    return bytes(out)


def make_jpeg(comment="Sesame bag photo"):
    out = bytearray(b"\xff\xd8")
    if comment is not None:
        encoded = comment.encode("latin-1")
        out.extend(b"\xff\xfe")
        out.extend(struct.pack(">H", len(encoded) + 2))
        out.extend(encoded)
    out.extend(b"\xff\xd9")
    return bytes(out)


PDF_BYTES = make_pdf()
DOCX_BYTES = make_docx()
PNG_BYTES = make_png()
JPEG_BYTES = make_jpeg()
PLAIN_PNG_BYTES = make_png(text=None)
PLAIN_JPEG_BYTES = make_jpeg(comment=None)

PDF_B64 = base64.b64encode(PDF_BYTES).decode("ascii")

GIF_BYTES = b"GIF89a\x01\x00\x01\x00\x00\x00\x00;"


def workflow_record(state, tenant=TENANT_A):
    return {
        "id": str(WORKFLOW_A),
        "tenant_id": str(tenant.tenant_id),
        "case_id": str(CASE_A),
        "shipment_id": None,
        "state": state,
        "rounds": [],
        "supplied_evidence_ids": [],
        "open_requirements": [],
    }


# ------------------------------------------------------------------
# fakes (repository/vector seams only)
# ------------------------------------------------------------------

class FakeEvidenceService:
    """In-memory stand-in honoring the evidence-service contract."""

    def __init__(self, known_requirements=()):
        self.rows: dict[UUID, dict] = {}
        self.links: dict[UUID, list[UUID]] = {}
        self.known_requirements = set(known_requirements)

    def register_upload(self, tenant, *, evidence_id, **values):
        row = {
            "id": evidence_id,
            "tenant_id": tenant.tenant_id,
            "source_id": None,
            "uploaded_at": FIXED_NOW,
            "created_at": FIXED_NOW,
            "updated_at": FIXED_NOW,
            "processing_step": None,
            "processing_error": None,
            "processed_at": None,
            **values,
        }
        row.setdefault("status", "uploaded")
        row.setdefault("processing_status", "uploaded")
        self.rows[evidence_id] = row
        return dict(row)

    def find_by_content_hash(self, tenant, content_hash):
        for row in self.rows.values():
            if (row["tenant_id"] == tenant.tenant_id
                    and row.get("content_hash") == content_hash):
                return dict(row)
        return None

    def set_processing_state(self, tenant, evidence_id, *,
                             processing_status, processing_step=None,
                             processing_error=None, processed_at=None):
        row = self.rows.get(evidence_id)
        if row is None or row["tenant_id"] != tenant.tenant_id:
            return None
        row.update({
            "processing_status": processing_status,
            "processing_step": processing_step,
            "processing_error": processing_error,
            "processed_at": processed_at,
        })
        return dict(row)

    def get(self, tenant, evidence_id):
        row = self.rows.get(evidence_id)
        if row is None or row["tenant_id"] != tenant.tenant_id:
            return None
        return dict(row)

    def associate_requirement(self, tenant, evidence_id, requirement_id):
        row = self.rows.get(evidence_id)
        if row is None or row["tenant_id"] != tenant.tenant_id:
            raise DomainNotFoundError("evidence was not found")
        if requirement_id not in self.known_requirements:
            raise DomainNotFoundError("requirement was not found")
        self.links.setdefault(evidence_id, [])
        if requirement_id not in self.links[evidence_id]:
            self.links[evidence_id].append(requirement_id)
        return {"evidence_id": evidence_id,
                "requirement_id": requirement_id}


class FakeCorpusRepository:
    """In-memory evidence-document repository (real ingestion above)."""

    def __init__(self):
        self.rows: dict[tuple, dict] = {}

    def get_by_source_identity(self, tenant, source_id, version):
        return self.rows.get(
            (tenant.tenant_id, source_id, version))

    def create(self, record):
        key = (record["tenant_id"], record["source_id"],
               record.get("document_version"))
        stored = dict(record)
        self.rows[key] = stored
        return dict(stored)


class FakeIndexSync:
    """Deterministic stand-in for the Phase 4.5 sync boundary."""

    def __init__(self, failure=None):
        self.calls: list[dict] = []
        self.failure = failure

    def sync(self, document, *, tenant_id):
        if document.get("tenant_id") != tenant_id.tenant_id:
            raise DomainValidationError("tenant identity mismatch")
        self.calls.append(dict(document))
        if self.failure is not None:
            raise self.failure
        return {"status": "complete",
                "document_id": document.get("id")}


def make_service(evidence=None, corpus_repo=None, sync=None,
                 storage=None, evidence_ids=None):
    evidence = evidence or FakeEvidenceService(
        known_requirements=(REQUIREMENT_A,))
    corpus_repo = corpus_repo or FakeCorpusRepository()
    corpus = EvidenceDocumentIngestionService(corpus_repo)
    sync = sync if sync is not None else FakeIndexSync()
    storage = storage if storage is not None else (
        InMemoryEvidenceObjectStore())
    ids = list(evidence_ids or [EVIDENCE_ID_1, EVIDENCE_ID_2])
    service = EvidenceUploadApplicationService(
        evidence_service=evidence,
        corpus_ingestion=corpus,
        index_sync=sync,
        storage=storage,
        clock=lambda: FIXED_NOW,
        evidence_ids=lambda: ids.pop(0) if ids else EVIDENCE_ID_2,
    )
    return service, evidence, corpus_repo, sync, storage


def upload_payload(content=PDF_BYTES, filename="certificate.pdf",
                   content_type="application/pdf", **extra):
    body = {
        "filename": filename,
        "content_type": content_type,
        "content_base64": base64.b64encode(content).decode("ascii"),
    }
    body.update(extra)
    return body


def app_with_service(service):
    app = create_app(services=SimpleNamespace())
    app.dependency_overrides[get_evidence_upload_service] = (
        lambda: service)
    return app


# ------------------------------------------------------------------
# validation boundary (U1/U2)
# ------------------------------------------------------------------

class UploadValidationTests(unittest.TestCase):
    def test_accepts_mvp_types(self):
        cases = (
            ("certificate.pdf", "application/pdf", PDF_BYTES, ".pdf"),
            ("certificate.docx",
             "application/vnd.openxmlformats-officedocument"
             ".wordprocessingml.document", DOCX_BYTES, ".docx"),
            ("photo.jpg", "image/jpeg", JPEG_BYTES, ".jpg"),
            ("photo.jpeg", "image/jpeg", JPEG_BYTES, ".jpg"),
            ("scan.png", "image/png", PNG_BYTES, ".png"),
        )
        for filename, content_type, content, extension in cases:
            with self.subTest(filename=filename):
                validated = validate_upload_file(
                    filename=filename, content_type=content_type,
                    content=content)
                self.assertEqual(validated.extension, extension)
                self.assertEqual(validated.size_bytes, len(content))
                self.assertEqual(len(validated.content_hash), 64)

    def test_rejects_unsupported_types(self):
        for content_type in ("text/plain", "text/markdown",
                             "application/json", "application/x-msdownload",
                             "image/gif"):
            with self.subTest(content_type=content_type):
                with self.assertRaises(EvidenceFileValidationError):
                    validate_upload_file(
                        filename="file.bin", content_type=content_type,
                        content=b"data data data")

    def test_rejects_mime_content_mismatch(self):
        with self.assertRaises(EvidenceFileValidationError):
            validate_upload_file(
                filename="scan.png", content_type="image/png",
                content=PDF_BYTES)
        with self.assertRaises(EvidenceFileValidationError):
            validate_upload_file(
                filename="doc.pdf", content_type="application/pdf",
                content=DOCX_BYTES)
        with self.assertRaises(EvidenceFileValidationError):
            validate_upload_file(
                filename="photo.jpg", content_type="image/jpeg",
                content=GIF_BYTES)

    def test_rejects_extension_mime_mismatch(self):
        with self.assertRaises(EvidenceFileValidationError):
            validate_upload_file(
                filename="certificate.pdf",
                content_type="image/png", content=PNG_BYTES)
        with self.assertRaises(EvidenceFileValidationError):
            validate_upload_file(
                filename="certificate", content_type="application/pdf",
                content=PDF_BYTES)

    def test_rejects_oversize(self):
        oversize = b"%PDF-" + b"x" * MAX_EVIDENCE_UPLOAD_BYTES
        with self.assertRaises(EvidenceFileTooLargeError):
            validate_upload_file(
                filename="big.pdf", content_type="application/pdf",
                content=oversize)

    def test_accepts_exact_limit(self):
        content = PDF_BYTES + b"x" * (
            MAX_EVIDENCE_UPLOAD_BYTES - len(PDF_BYTES))
        validated = validate_upload_file(
            filename="big.pdf", content_type="application/pdf",
            content=content)
        self.assertEqual(validated.size_bytes, MAX_EVIDENCE_UPLOAD_BYTES)

    def test_rejects_empty_and_non_bytes(self):
        with self.assertRaises(EvidenceFileValidationError):
            validate_upload_file(
                filename="a.pdf", content_type="application/pdf",
                content=b"")
        with self.assertRaises(EvidenceFileValidationError):
            validate_upload_file(
                filename="a.pdf", content_type="application/pdf",
                content="text")
        with self.assertRaises(EvidenceFileValidationError):
            validate_upload_file(
                filename="a.pdf", content_type="application/pdf",
                content=None)

    def test_filename_attacks_rejected(self):
        for filename in ("../secret.pdf", "..\\secret.pdf",
                         "/etc/passwd.pdf", "uploads/certificate.pdf",
                         "a/b.pdf", ".", "..", "",
                         "   ", "a\x00.pdf", "a\x01.pdf",
                         "x" * 300 + ".pdf"):
            with self.subTest(filename=repr(filename)):
                with self.assertRaises(EvidenceFileValidationError):
                    validate_upload_file(
                        filename=filename,
                        content_type="application/pdf",
                        content=PDF_BYTES)

    def test_content_type_parameters_and_case_tolerated(self):
        validated = validate_upload_file(
            filename="certificate.PDF",
            content_type="Application/PDF; charset=binary",
            content=PDF_BYTES)
        self.assertEqual(validated.content_type, "application/pdf")

    def test_docx_requires_document_structure(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("random.txt", "not a document")
        with self.assertRaises(EvidenceFileValidationError):
            validate_upload_file(
                filename="fake.docx",
                content_type="application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document",
                content=buf.getvalue())


class TextExtractionTests(unittest.TestCase):
    def test_extracts_docx_paragraphs(self):
        text = extract_upload_text("docx", DOCX_BYTES)
        self.assertIn("Cocoa export certificate", text)
        self.assertIn("Issued in Lagos", text)

    def test_extracts_pdf_literal_text(self):
        text = extract_upload_text("pdf", PDF_BYTES)
        self.assertIn("Phytosanitary certificate", text)

    def test_extracts_compressed_pdf_stream(self):
        text = extract_upload_text("pdf", make_pdf_compressed())
        self.assertIn("Compressed sesame inspection report", text)

    def test_extracts_png_embedded_text(self):
        text = extract_upload_text("png", PNG_BYTES)
        self.assertIn("Cocoa bag label", text)

    def test_extracts_jpeg_comment(self):
        text = extract_upload_text("jpeg", JPEG_BYTES)
        self.assertIn("Sesame bag photo", text)

    def test_images_without_text_fail_extraction(self):
        with self.assertRaisesRegex(Exception, "usable text"):
            extract_upload_text("png", PLAIN_PNG_BYTES)
        with self.assertRaisesRegex(Exception, "usable text"):
            extract_upload_text("jpeg", PLAIN_JPEG_BYTES)

    def test_rejects_docx_with_entity_declarations(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("[Content_Types].xml", "x")
            archive.writestr(
                "word/document.xml",
                '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x "y">]>'
                '<w:document xmlns:w="urn:x"><w:body/></w:document>')
        with self.assertRaises(Exception):
            extract_upload_text("docx", buf.getvalue())


class ObjectKeyTests(unittest.TestCase):
    def test_key_shape_is_server_composed(self):
        key = compose_object_key(
            tenant_id=TENANT_A_ID, evidence_id=EVIDENCE_ID_1,
            content_hash="a" * 64, extension=".pdf")
        self.assertEqual(
            key,
            f"tenant/{TENANT_A_ID.hex}/evidence/"
            f"{EVIDENCE_ID_1.hex}/{'a' * 64}.pdf")

    def test_key_carries_no_client_text(self):
        key = compose_object_key(
            tenant_id=TENANT_A_ID, evidence_id=EVIDENCE_ID_1,
            content_hash="b" * 64, extension=".jpg")
        self.assertNotIn("..", key)
        self.assertNotIn("certificate", key)
        self.assertTrue(key.startswith(f"tenant/{TENANT_A_ID.hex}/"))

    def test_key_rejects_malformed_inputs(self):
        with self.assertRaises(DomainValidationError):
            compose_object_key(
                tenant_id="tenant-a", evidence_id=EVIDENCE_ID_1,
                content_hash="a" * 64, extension=".pdf")
        with self.assertRaises(DomainValidationError):
            compose_object_key(
                tenant_id=TENANT_A_ID, evidence_id=EVIDENCE_ID_1,
                content_hash="short", extension=".pdf")
        with self.assertRaises(DomainValidationError):
            compose_object_key(
                tenant_id=TENANT_A_ID, evidence_id=EVIDENCE_ID_1,
                content_hash="a" * 64, extension=".exe")


# ------------------------------------------------------------------
# storage boundary (U4)
# ------------------------------------------------------------------

class InMemoryStorageTests(unittest.TestCase):
    def test_put_and_signed_url_are_opaque(self):
        store = InMemoryEvidenceObjectStore()
        key = compose_object_key(
            tenant_id=TENANT_A_ID, evidence_id=EVIDENCE_ID_1,
            content_hash="c" * 64, extension=".pdf")
        store.put(key, PDF_BYTES, content_type="application/pdf")
        url = store.create_signed_url(key)
        self.assertNotIn(key, url)
        self.assertNotIn(EVIDENCE_ID_1.hex, url)
        token = url.rsplit("/", 1)[-1]
        self.assertEqual(store.resolve_token(token), PDF_BYTES)

    def test_missing_key_has_no_download(self):
        store = InMemoryEvidenceObjectStore()
        with self.assertRaises(EvidenceStorageError):
            store.create_signed_url(
                "tenant/aaaa/evidence/bbbb/" + "d" * 64 + ".pdf")

    def test_storage_is_a_protocol_implementation(self):
        self.assertIsInstance(
            InMemoryEvidenceObjectStore(), EvidenceObjectStore)

    def test_compensating_delete_removes_object(self):
        store = InMemoryEvidenceObjectStore()
        key = compose_object_key(
            tenant_id=TENANT_A_ID, evidence_id=EVIDENCE_ID_1,
            content_hash="e" * 64, extension=".png")
        store.put(key, PNG_BYTES, content_type="image/png")
        store.delete(key)
        with self.assertRaises(EvidenceStorageError):
            store.create_signed_url(key)

    def test_rejects_malformed_keys_and_ttl(self):
        store = InMemoryEvidenceObjectStore()
        with self.assertRaises(EvidenceStorageError):
            store.put("", PDF_BYTES, content_type="application/pdf")
        with self.assertRaises(EvidenceStorageError):
            store.put("../escape", PDF_BYTES,
                      content_type="application/pdf")
        key = compose_object_key(
            tenant_id=TENANT_A_ID, evidence_id=EVIDENCE_ID_1,
            content_hash="f" * 64, extension=".pdf")
        store.put(key, PDF_BYTES, content_type="application/pdf")
        with self.assertRaises(EvidenceStorageError):
            store.create_signed_url(key, expires_in_seconds=0)
        with self.assertRaises(EvidenceStorageError):
            store.create_signed_url(key, expires_in_seconds=99999)


class SupabaseStorageTests(unittest.TestCase):
    def _transport(self, handler):
        import httpx
        return httpx.MockTransport(handler)

    def test_put_and_signed_url_against_fake_backend(self):
        import httpx
        seen = {}

        def handler(request):
            seen["method"] = request.method
            seen["url"] = str(request.url)
            if request.method == "PUT":
                return httpx.Response(200, json={})
            if request.method == "POST":
                return httpx.Response(
                    200, json={"signedURL": "tenant-evidence/signed/abc"})
            return httpx.Response(404, json={})

        settings = SupabaseStorageSettings(
            base_url="https://project.supabase.co",
            service_role_key="service-key")
        store = SupabaseEvidenceObjectStore(
            settings,
            client=httpx.Client(transport=self._transport(handler)))
        key = ("tenant/aaaa/evidence/bbbb/" + "a" * 64 + ".pdf")
        store.put(key, PDF_BYTES, content_type="application/pdf")
        self.assertIn("/storage/v1/object/", seen["url"])
        url = store.create_signed_url(key)
        self.assertTrue(url.startswith("https://project.supabase.co/"))
        self.assertNotIn("service-key", url)

    def test_failures_are_static_and_key_free(self):
        import httpx

        def handler(request):
            return httpx.Response(500, json={})

        settings = SupabaseStorageSettings(
            base_url="https://project.supabase.co",
            service_role_key="service-key")
        store = SupabaseEvidenceObjectStore(
            settings,
            client=httpx.Client(transport=self._transport(handler)))
        key = ("tenant/aaaa/evidence/bbbb/" + "a" * 64 + ".pdf")
        with self.assertRaises(EvidenceStorageError) as put_raised:
            store.put(key, PDF_BYTES, content_type="application/pdf")
        with self.assertRaises(EvidenceStorageError) as url_raised:
            store.create_signed_url(key)
        for raised in (put_raised.exception, url_raised.exception):
            self.assertNotIn(key, str(raised))
            self.assertNotIn("supabase.co", str(raised))
            self.assertNotIn("service-key", str(raised))

    def test_missing_configuration_fails_closed(self):
        with self.assertRaises(Exception):
            SupabaseStorageSettings(
                base_url="", service_role_key="")
        with self.assertRaises(Exception):
            SupabaseStorageSettings.from_environment({})


# ------------------------------------------------------------------
# upload lifecycle
# ------------------------------------------------------------------

class UploadLifecycleTests(unittest.TestCase):
    def test_successful_upload_reaches_ready(self):
        service, evidence, corpus, sync, storage = make_service()
        dto = service.upload_evidence(
            CTX_A, filename="certificate.pdf",
            content_type="application/pdf", content=PDF_BYTES)
        self.assertFalse(dto.duplicate)
        self.assertEqual(dto.processing_status, "ready")
        self.assertEqual(dto.status, "uploaded")
        self.assertEqual(dto.original_filename, "certificate.pdf")
        self.assertEqual(dto.mime_type, "application/pdf")
        row = evidence.rows[UUID(dto.evidence_id)]
        self.assertEqual(row["tenant_id"], TENANT_A_ID)
        expected_key = compose_object_key(
            tenant_id=TENANT_A_ID,
            evidence_id=UUID(dto.evidence_id),
            content_hash=row["content_hash"],
            extension=".pdf")
        self.assertEqual(row["file_reference_or_uri"], expected_key)
        self.assertIn(expected_key, storage.objects)
        self.assertEqual(row["uploaded_by"], ACTOR_ID)
        self.assertEqual(row["processing_status"], "ready")
        self.assertEqual(len(sync.calls), 1)
        corpus_row = sync.calls[0]
        self.assertEqual(corpus_row["tenant_id"], TENANT_A_ID)
        self.assertIn("Phytosanitary certificate",
                      corpus_row["content"])
        self.assertTrue(corpus_row["source_id"].startswith(
            "tenant-evidence:"))
        self.assertEqual(corpus_row["document_version"],
                         row["content_hash"])

    def test_image_without_text_marks_failed_parse(self):
        service, evidence, _corpus, sync, storage = make_service()
        dto = service.upload_evidence(
            CTX_A, filename="scan.png", content_type="image/png",
            content=PLAIN_PNG_BYTES)
        self.assertFalse(dto.duplicate)
        self.assertEqual(dto.processing_status, "failed")
        self.assertEqual(dto.processing_step, "parse")
        self.assertEqual(sync.calls, [])
        row = evidence.rows[UUID(dto.evidence_id)]
        self.assertIn("tenant/", row["file_reference_or_uri"])
        self.assertIn(row["file_reference_or_uri"], storage.objects)

    def test_failed_processing_is_never_ready(self):
        service, evidence, _corpus, _sync, _storage = make_service()
        dto = service.upload_evidence(
            CTX_A, filename="photo.jpg", content_type="image/jpeg",
            content=PLAIN_JPEG_BYTES)
        self.assertNotEqual(dto.processing_status, "ready")
        self.assertFalse(is_evidence_usable(
            evidence.rows[UUID(dto.evidence_id)]))

    def test_index_failure_propagates_and_marks_failed(self):
        failure = VectorStoreError("test sync", RuntimeError("boom"))
        service, evidence, _corpus, _sync, _storage = make_service(
            sync=FakeIndexSync(failure=failure))
        with self.assertRaises(InfrastructureError):
            service.upload_evidence(
                CTX_A, filename="certificate.pdf",
                content_type="application/pdf", content=PDF_BYTES)
        row = next(iter(evidence.rows.values()))
        self.assertEqual(row["processing_status"], "failed")
        self.assertEqual(row["processing_step"], "sync")

    def test_retry_after_transient_sync_failure_reaches_ready(self):
        flaky = FakeIndexSync(failure=VectorStoreError(
            "test sync", RuntimeError("boom")))
        service, evidence, _corpus, _sync, _storage = make_service(
            sync=flaky)
        with self.assertRaises(InfrastructureError):
            service.upload_evidence(
                CTX_A, filename="certificate.pdf",
                content_type="application/pdf", content=PDF_BYTES)
        failed_id = next(iter(evidence.rows))
        service._sync = FakeIndexSync()
        retry = service.upload_evidence(
            CTX_A, filename="certificate.pdf",
            content_type="application/pdf", content=PDF_BYTES)
        self.assertTrue(retry.duplicate)
        self.assertEqual(retry.evidence_id, str(failed_id))
        self.assertEqual(retry.processing_status, "ready")
        self.assertEqual(len(evidence.rows), 1)

    def test_duplicate_upload_returns_existing_without_new_writes(self):
        service, evidence, _corpus, sync, storage = make_service(
            evidence_ids=[EVIDENCE_ID_1, EVIDENCE_ID_2])
        first = service.upload_evidence(
            CTX_A, filename="certificate.pdf",
            content_type="application/pdf", content=PDF_BYTES)
        puts_before = len(storage.objects)
        second = service.upload_evidence(
            CTX_A, filename="renamed.pdf",
            content_type="application/pdf", content=PDF_BYTES)
        self.assertTrue(second.duplicate)
        self.assertEqual(second.evidence_id, first.evidence_id)
        self.assertEqual(second.processing_status, "ready")
        self.assertEqual(len(evidence.rows), 1)
        self.assertEqual(len(storage.objects), puts_before)
        self.assertEqual(len(sync.calls), 1)

    def test_terminal_workflow_rejected_before_any_mutation(self):
        service, evidence, _corpus, sync, storage = make_service()
        with self.assertRaises(TerminalWorkflowError):
            service.upload_evidence(
                CTX_A, filename="certificate.pdf",
                content_type="application/pdf", content=PDF_BYTES,
                workflow_record=workflow_record(
                    "assessment_package_ready"))
        self.assertEqual(evidence.rows, {})
        self.assertEqual(storage.objects, {})
        self.assertEqual(sync.calls, [])

    def test_open_workflow_association_allowed(self):
        service, evidence, _corpus, _sync, _storage = make_service()
        dto = service.upload_evidence(
            CTX_A, filename="certificate.pdf",
            content_type="application/pdf", content=PDF_BYTES,
            workflow_record=workflow_record("evidence_pending"))
        self.assertEqual(dto.processing_status, "ready")

    def test_requirement_link_recorded_when_known(self):
        service, evidence, _corpus, _sync, _storage = make_service()
        dto = service.upload_evidence(
            CTX_A, filename="certificate.pdf",
            content_type="application/pdf", content=PDF_BYTES,
            requirement_ids=[REQUIREMENT_A])
        self.assertEqual(dto.linked_requirement_ids,
                         (str(REQUIREMENT_A),))
        self.assertEqual(evidence.links[UUID(dto.evidence_id)],
                         [REQUIREMENT_A])

    def test_unknown_requirement_leaves_record_without_link(self):
        service, evidence, _corpus, _sync, _storage = make_service()
        unknown = UUID("00000000-0000-0000-0000-000000000099")
        dto = service.upload_evidence(
            CTX_A, filename="certificate.pdf",
            content_type="application/pdf", content=PDF_BYTES,
            requirement_ids=[unknown])
        self.assertEqual(dto.processing_status, "ready")
        self.assertEqual(dto.linked_requirement_ids, ())
        self.assertEqual(len(evidence.rows), 1)

    def test_storage_failure_leaves_no_row(self):
        class BrokenStorage:
            def put(self, key, content, *, content_type):
                raise EvidenceStorageError("evidence object write failed")

            def delete(self, key):
                pass

            def create_signed_url(self, key, *, expires_in_seconds=300):
                raise EvidenceStorageError("evidence download unavailable")

        service, evidence, _corpus, _sync, _storage = make_service(
            storage=BrokenStorage())
        with self.assertRaises(InfrastructureError):
            service.upload_evidence(
                CTX_A, filename="certificate.pdf",
                content_type="application/pdf", content=PDF_BYTES)
        self.assertEqual(evidence.rows, {})


# ------------------------------------------------------------------
# tenant isolation + download authorization
# ------------------------------------------------------------------

class TenantIsolationTests(unittest.TestCase):
    def test_cross_tenant_download_is_forbidden(self):
        # Lookups are 404-non-leaking per the established
        # semantics: cross-tenant existence is never
        # revealed, and no URL is ever issued.
        service, _evidence, _corpus, _sync, _storage = make_service()
        dto = service.upload_evidence(
            CTX_A, filename="certificate.pdf",
            content_type="application/pdf", content=PDF_BYTES)
        with self.assertRaises(ApplicationNotFoundError):
            service.get_download(CTX_B, UUID(dto.evidence_id))

    def test_cross_tenant_upload_of_identical_bytes_stays_independent(self):
        service, evidence, _corpus, _sync, _storage = make_service(
            evidence_ids=[EVIDENCE_ID_1, EVIDENCE_ID_2])
        first = service.upload_evidence(
            CTX_A, filename="certificate.pdf",
            content_type="application/pdf", content=PDF_BYTES)
        second = service.upload_evidence(
            CTX_B, filename="certificate.pdf",
            content_type="application/pdf", content=PDF_BYTES)
        self.assertFalse(second.duplicate)
        self.assertNotEqual(second.evidence_id, first.evidence_id)
        self.assertEqual(len(evidence.rows), 2)
        for row in evidence.rows.values():
            self.assertEqual(row["content_hash"], first.content_hash)

    def test_cross_tenant_workflow_association_rejected(self):
        service, evidence, _corpus, _sync, storage = make_service()
        with self.assertRaises(TenantMismatchError):
            service.upload_evidence(
                CTX_A, filename="certificate.pdf",
                content_type="application/pdf", content=PDF_BYTES,
                workflow_record=workflow_record(
                    "evidence_pending", tenant=TENANT_B))
        self.assertEqual(evidence.rows, {})
        self.assertEqual(storage.objects, {})

    def test_cross_tenant_evidence_access_is_not_found(self):
        service, _evidence, _corpus, _sync, _storage = make_service()
        dto = service.upload_evidence(
            CTX_A, filename="certificate.pdf",
            content_type="application/pdf", content=PDF_BYTES)
        with self.assertRaises(ApplicationNotFoundError):
            service.get_download(
                CTX_B, UUID("00000000-0000-0000-0000-000000000099"))
        self.assertIsNotNone(dto.evidence_id)


class DownloadAuthorizationTests(unittest.TestCase):
    def test_authorized_download_issues_signed_url(self):
        service, _evidence, _corpus, _sync, storage = make_service()
        dto = service.upload_evidence(
            CTX_A, filename="certificate.pdf",
            content_type="application/pdf", content=PDF_BYTES)
        grant = service.get_download(CTX_A, UUID(dto.evidence_id))
        self.assertEqual(grant.evidence_id, dto.evidence_id)
        self.assertEqual(grant.tenant_id, str(TENANT_A_ID))
        self.assertTrue(grant.download_url)
        self.assertEqual(grant.expires_in_seconds, 300)
        token = grant.download_url.rsplit("/", 1)[-1]
        self.assertEqual(storage.resolve_token(token), PDF_BYTES)

    def test_download_of_unknown_evidence_is_not_found(self):
        service, _e, _c, _s, _st = make_service()
        with self.assertRaises(ApplicationNotFoundError):
            service.get_download(
                CTX_A, UUID("00000000-0000-0000-0000-000000000099"))

    def test_download_without_storage_reference_is_not_found(self):
        evidence = FakeEvidenceService()
        service, _, _, _, _ = make_service(evidence=evidence)
        row = evidence.register_upload(
            TENANT_A, evidence_id=EVIDENCE_ID_1,
            document_title="legacy", document_type="reference",
            file_reference_or_uri="", content_hash="c" * 64)
        self.assertEqual(row["file_reference_or_uri"], "")
        with self.assertRaises(ApplicationNotFoundError):
            service.get_download(CTX_A, EVIDENCE_ID_1)


# ------------------------------------------------------------------
# HTTP boundary: auth, validation mapping, lifecycle
# ------------------------------------------------------------------

class UploadAPIAuthTests(unittest.TestCase):
    def test_unauthenticated_upload_rejected(self):
        service, _, _, _, _ = make_service()
        with TestClient(app_with_service(service)) as client:
            response = client.post(
                "/compliance-evidence/uploads",
                json=upload_payload())
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"],
                         "authentication_required")

    def test_unauthenticated_download_rejected(self):
        service, _, _, _, _ = make_service()
        with TestClient(app_with_service(service)) as client:
            response = client.get(
                f"/compliance-evidence/{EVIDENCE_ID_1}/download")
        self.assertEqual(response.status_code, 401)

    def test_member_may_upload_and_download(self):
        from xportra.api.dependencies import get_member_context
        service, _, _, _, _ = make_service()
        app = app_with_service(service)
        app.dependency_overrides[get_member_context] = (
            lambda: MemberContext(TENANT_A, "member"))
        with TestClient(app) as client:
            upload = client.post(
                "/compliance-evidence/uploads",
                json=upload_payload())
            self.assertEqual(upload.status_code, 201, upload.text)
            evidence_id = upload.json()["evidence_id"]
            download = client.get(
                f"/compliance-evidence/{evidence_id}/download")
            self.assertEqual(download.status_code, 200, download.text)

    def test_unknown_role_is_forbidden(self):
        from xportra.api.dependencies import get_member_context
        service, _, _, _, _ = make_service()
        app = app_with_service(service)
        app.dependency_overrides[get_member_context] = (
            lambda: MemberContext(TENANT_A, "auditor"))
        with TestClient(app) as client:
            response = client.post(
                "/compliance-evidence/uploads",
                json=upload_payload())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"],
                         "permission_denied")

    def test_request_body_cannot_carry_tenant_identity(self):
        service, _, _, _, _ = make_service()
        with TestClient(app_with_service(service)) as client:
            body = upload_payload()
            body["tenant_id"] = str(TENANT_B_ID)
            response = client.post(
                "/compliance-evidence/uploads", headers=HEADER_A,
                json=body)
        self.assertEqual(response.status_code, 422)


class UploadAPILifecycleTests(unittest.TestCase):
    def test_successful_upload_returns_identifiers_only(self):
        service, _, _, _, _ = make_service()
        with TestClient(app_with_service(service)) as client:
            response = client.post(
                "/compliance-evidence/uploads", headers=HEADER_A,
                json=upload_payload(
                    document_title="Phyto certificate",
                    requirement_ids=[str(REQUIREMENT_A)]))
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertEqual(body["processing_status"], "ready")
        self.assertEqual(body["status"], "uploaded")
        self.assertEqual(body["document_title"], "Phyto certificate")
        self.assertEqual(body["original_filename"], "certificate.pdf")
        self.assertFalse(body["duplicate"])
        self.assertEqual(body["linked_requirement_ids"],
                         [str(REQUIREMENT_A)])
        rendered = response.text
        self.assertNotIn("tenant/", rendered)
        self.assertNotIn("signed", rendered.lower())
        self.assertNotIn("BEGIN", rendered)

    def test_oversize_maps_to_413(self):
        service, _, _, _, _ = make_service()
        oversize = b"%PDF-" + b"x" * MAX_EVIDENCE_UPLOAD_BYTES
        with TestClient(app_with_service(service)) as client:
            response = client.post(
                "/compliance-evidence/uploads", headers=HEADER_A,
                json=upload_payload(content=oversize))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"]["code"],
                         "payload_too_large")

    def test_unsupported_type_maps_to_400(self):
        service, _, _, _, _ = make_service()
        with TestClient(app_with_service(service)) as client:
            response = client.post(
                "/compliance-evidence/uploads", headers=HEADER_A,
                json=upload_payload(
                    filename="notes.txt", content_type="text/plain",
                    content=b"hello"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"],
                         "invalid_input")

    def test_malformed_base64_maps_to_422(self):
        service, _, _, _, _ = make_service()
        with TestClient(app_with_service(service)) as client:
            body = upload_payload()
            body["content_base64"] = "!!! not base64 !!!"
            response = client.post(
                "/compliance-evidence/uploads", headers=HEADER_A,
                json=body)
        self.assertEqual(response.status_code, 422)

    def test_terminal_workflow_rejected_with_no_mutation(self):
        service, evidence, _, _, storage = make_service()
        with TestClient(app_with_service(service)) as client:
            response = client.post(
                "/compliance-evidence/uploads", headers=HEADER_A,
                json=upload_payload(workflow=workflow_record(
                    "assessment_package_ready")))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"],
                         "terminal_workflow")
        self.assertEqual(evidence.rows, {})
        self.assertEqual(storage.objects, {})

    def test_cross_tenant_download_forbidden(self):
        service, _, _, _, _ = make_service()
        with TestClient(app_with_service(service)) as client:
            upload = client.post(
                "/compliance-evidence/uploads", headers=HEADER_A,
                json=upload_payload())
            self.assertEqual(upload.status_code, 201)
            evidence_id = upload.json()["evidence_id"]
            response = client.get(
                f"/compliance-evidence/{evidence_id}/download",
                headers=HEADER_B)
        # 404-non-leaking: no access and no existence reveal.
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"],
                         "not_found")

    def test_download_grant_carries_short_lived_url(self):
        service, _, _, _, _ = make_service()
        with TestClient(app_with_service(service)) as client:
            upload = client.post(
                "/compliance-evidence/uploads", headers=HEADER_A,
                json=upload_payload())
            evidence_id = upload.json()["evidence_id"]
            response = client.get(
                f"/compliance-evidence/{evidence_id}/download",
                headers=HEADER_A)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["evidence_id"], evidence_id)
        self.assertEqual(body["tenant_id"], str(TENANT_A_ID))
        self.assertTrue(body["download_url"])
        self.assertEqual(body["expires_in_seconds"], 300)

    def test_download_of_unknown_evidence_is_not_found(self):
        service, _, _, _, _ = make_service()
        with TestClient(app_with_service(service)) as client:
            response = client.get(
                "/compliance-evidence/00000000-0000-0000-0000-"
                "000000000099/download",
                headers=HEADER_A)
        self.assertEqual(response.status_code, 404)

    def test_unwired_service_fails_closed(self):
        with TestClient(
            create_app(services=SimpleNamespace())
        ) as client:
            upload = client.post(
                "/compliance-evidence/uploads", headers=HEADER_A,
                json=upload_payload())
            self.assertEqual(upload.status_code, 503)
            self.assertEqual(upload.json()["error"]["code"],
                             "evidence_upload_not_configured")
            download = client.get(
                f"/compliance-evidence/{EVIDENCE_ID_1}/download",
                headers=HEADER_A)
            self.assertEqual(download.status_code, 503)


# ------------------------------------------------------------------
# production error surface (Phase 10.1 rules hold)
# ------------------------------------------------------------------

class ProductionErrorSurfaceTests(unittest.TestCase):
    def _production_client(self, service):
        with patched_env(APP_ENV="production",
                         SUPABASE_JWT_SECRET="test-secret"):
            return TestClient(app_with_service(service))

    def test_production_503_carries_no_internals(self):
        class BrokenStorage:
            def put(self, key, content, *, content_type):
                raise EvidenceStorageError("evidence object write failed")

            def delete(self, key):
                pass

            def create_signed_url(self, key, *, expires_in_seconds=300):
                raise EvidenceStorageError("evidence download unavailable")

        service, _, _, _, _ = make_service(storage=BrokenStorage())
        with self._production_client(service) as client:
            response = client.post(
                "/compliance-evidence/uploads", headers=HEADER_A,
                json=upload_payload())
        self.assertEqual(response.status_code, 503)
        body = response.json()["error"]
        self.assertEqual(body["code"], "infrastructure_failure")
        self.assertNotIn("details", body)
        rendered = response.text
        self.assertNotIn("tenant/", rendered)
        self.assertNotIn("Traceback", rendered)
        self.assertNotIn("psycopg", rendered.lower())

    def test_production_413_keeps_stable_code(self):
        service, _, _, _, _ = make_service()
        oversize = b"%PDF-" + b"x" * MAX_EVIDENCE_UPLOAD_BYTES
        with self._production_client(service) as client:
            response = client.post(
                "/compliance-evidence/uploads", headers=HEADER_A,
                json=upload_payload(content=oversize))
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.json()["error"]["code"],
                         "payload_too_large")

    def test_failed_upload_response_leaks_nothing(self):
        service, _, _, _, _ = make_service()
        with TestClient(app_with_service(service)) as client:
            response = client.post(
                "/compliance-evidence/uploads", headers=HEADER_A,
                json=upload_payload(
                    filename="scan.png", content_type="image/png",
                    content=PLAIN_PNG_BYTES))
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["processing_status"], "failed")
        self.assertIsNotNone(body["processing_error"])
        rendered = response.text
        self.assertNotIn("tenant/", rendered)
        self.assertNotIn("BEGIN", rendered)


# ------------------------------------------------------------------
# compliance semantics (upload changes nothing by itself)
# ------------------------------------------------------------------

class EvidenceSemanticsTests(unittest.TestCase):
    def _applicable_result(self):
        requirement = {
            "id": REQUIREMENT_A,
            "requirement_text": (
                "The exporter shall present a phytosanitary "
                "certificate for cocoa."),
            "requirement_type": "documentation",
            "condition_metadata": None,
        }
        context = ApplicabilityContext(
            tenant_id=TENANT_A_ID,
            exporter_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            destination_country="NG",
            commodity="cocoa",
            actor_role="exporter",
        )
        service = RegulatoryRequirementApplicabilityService()
        return service.evaluate(requirement, context), requirement

    def test_ready_does_not_imply_satisfied(self):
        service, _evidence, _corpus, _sync, _storage = make_service()
        dto = service.upload_evidence(
            CTX_A, filename="certificate.pdf",
            content_type="application/pdf", content=PDF_BYTES,
            requirement_ids=[REQUIREMENT_A])
        self.assertEqual(dto.processing_status, "ready")
        applicability, _requirement = self._applicable_result()
        assessment = RequirementAssessmentService().assess(
            applicability,
            [AssessmentEvidenceRecord(
                tenant_id=TENANT_A_ID,
                evidence_id=UUID(dto.evidence_id),
                evidence_type="certificate",
                reference="tenant-evidence object",
                requirement_id=REQUIREMENT_A,
                status="uploaded")],
        )
        self.assertNotEqual(assessment["outcome"], "satisfied")

    def test_upload_does_not_alter_applicability(self):
        first, _ = self._applicable_result()
        service, _, _, _, _ = make_service()
        service.upload_evidence(
            CTX_A, filename="certificate.pdf",
            content_type="application/pdf", content=PDF_BYTES)
        second, _ = self._applicable_result()
        self.assertEqual(first["outcome"], second["outcome"])
        self.assertEqual(
            first["context_fingerprint"], second["context_fingerprint"])

    def test_failed_processing_is_not_usable_evidence(self):
        self.assertFalse(is_evidence_usable({
            "status": "uploaded", "processing_status": "failed"}))
        self.assertFalse(is_evidence_usable({
            "status": "uploaded", "processing_status": "processing"}))
        self.assertFalse(is_evidence_usable({
            "status": "uploaded", "processing_status": "uploaded"}))

    def test_inactive_evidence_does_not_participate(self):
        self.assertFalse(is_evidence_usable({
            "status": "archived", "processing_status": "ready"}))
        self.assertFalse(is_evidence_usable({
            "status": "rejected", "processing_status": "ready"}))
        self.assertTrue(is_evidence_usable({
            "status": "uploaded", "processing_status": "ready"}))
        self.assertTrue(is_evidence_usable({
            "status": "accepted", "processing_status": "ready"}))
        self.assertFalse(is_evidence_usable({}))
        self.assertFalse(is_evidence_usable(None))


# ------------------------------------------------------------------
# scope guards: no delete, no raw content, no chat impact
# ------------------------------------------------------------------

class ScopeGuardTests(unittest.TestCase):
    def test_no_delete_endpoint_exists(self):
        service, _, _, _, _ = make_service()
        with TestClient(app_with_service(service)) as client:
            upload = client.post(
                "/compliance-evidence/uploads", headers=HEADER_A,
                json=upload_payload())
            evidence_id = upload.json()["evidence_id"]
            for method in ("delete",):
                response = getattr(client, method)(
                    f"/compliance-evidence/{evidence_id}",
                    headers=HEADER_A)
                self.assertIn(response.status_code, (404, 405))
            response = client.post(
                f"/compliance-evidence/{evidence_id}/delete",
                headers=HEADER_A)
            self.assertIn(response.status_code, (404, 405))

    def test_upload_response_never_carries_raw_content(self):
        service, _, _, _, _ = make_service()
        with TestClient(app_with_service(service)) as client:
            response = client.post(
                "/compliance-evidence/uploads", headers=HEADER_A,
                json=upload_payload())
        body = response.json()
        self.assertNotIn("content", body)
        self.assertNotIn("content_base64", body)
        self.assertNotIn("file_reference_or_uri", body)
        self.assertNotIn("storage_bucket", body)

    def test_conversation_route_untouched_by_upload(self):
        service, _, _, _, _ = make_service()
        with TestClient(app_with_service(service)) as client:
            response = client.post(
                "/conversations/messages", headers=HEADER_A,
                json={
                    "conversation_id": str(UUID(
                        "99999999-9999-9999-9999-999999999999")),
                    "mode": "knowledge",
                    "intent": "answer_regulatory_question",
                    "user_text": "upload a certificate",
                    "information_need": "What rules apply to cocoa?",
                })
        # Unwired RAG fails closed exactly as before Phase
        # 10.4; the upload boundary changed nothing here.
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("upload", response.text.lower())


if __name__ == "__main__":
    unittest.main()