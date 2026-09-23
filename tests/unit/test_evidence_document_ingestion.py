"""Phase 4.1 - Evidence Document Ingestion Boundary tests."""

import copy
import unittest
from datetime import date, datetime, timezone
from uuid import UUID

from xportra.domain.errors import (
    DomainPersistenceError,
    DomainValidationError,
)
from xportra.domain.evidence_corpus import content_fingerprint
from xportra.domain.evidence_ingestion import EvidenceDocumentIngestionService
from xportra.persistence.errors import PersistenceIntegrityError
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


class MemoryRepository:
    """In-memory stand-in honoring the corpus repository contract."""

    def __init__(self) -> None:
        self.rows = {}
        self.create_calls = 0

    def create(self, record):
        self.create_calls += 1
        key = (record["tenant_id"], record["id"])
        if key in self.rows:
            raise PersistenceIntegrityError("duplicate", ValueError("dup"))
        self.rows[key] = copy.deepcopy(record)
        return copy.deepcopy(record)

    def get_by_id(self, tenant, document_id):
        row = self.rows.get((tenant.tenant_id, document_id))
        return copy.deepcopy(row) if row else None

    def get_by_source_identity(self, tenant, source_id, version):
        norm = version.strip() if isinstance(version, str) else None
        if norm == "":
            norm = None
        for (t_id, _), row in self.rows.items():
            if t_id != tenant.tenant_id:
                continue
            if row["source_id"] != source_id:
                continue
            if (row.get("document_version") or None) != norm:
                continue
            return copy.deepcopy(row)
        return None

    def list_for_tenant(self, tenant):
        return [copy.deepcopy(r) for (t, _), r in self.rows.items()
                if t == tenant.tenant_id]


class TestEvidenceDocumentIngestion(unittest.TestCase):
    def setUp(self) -> None:
        self.tenant = TenantContext(TENANT_ID)
        self.other = TenantContext(OTHER_TENANT_ID)
        self.repo = MemoryRepository()
        self.service = EvidenceDocumentIngestionService(self.repo)

    def _record(self, **kw):
        base = {
            "title": "NAFDAC cocoa guidance",
            "content": "Exporters must hold a valid certificate.",
            "source_type": "guidance",
            "source_id": "nafdac/cocoa-guide",
            "source_location": "https://example.test/guide",
            "jurisdiction": "NG",
            "document_version": "v1",
            "effective_date": date(2026, 1, 1),
            "retrieved_at": datetime(2026, 9, 22, tzinfo=timezone.utc),
            "metadata": {"authority": "NAFDAC"},
            "tenant_id": TENANT_ID,
        }
        base.update(kw)
        return base

    # 01 valid source record ingested
    def test_01_valid_record_ingested(self) -> None:
        row = self.service.ingest(self._record(), tenant_id=self.tenant)
        self.assertEqual(row["tenant_id"], TENANT_ID)
        self.assertEqual(row["source_id"], "nafdac/cocoa-guide")

    # 02 tenant identity preserved
    def test_02_tenant_preserved(self) -> None:
        row = self.service.ingest(self._record(), tenant_id=self.tenant)
        self.assertEqual(row["tenant_id"], TENANT_ID)

    # 03 valid provenance accepted
    def test_03_valid_provenance(self) -> None:
        row = self.service.ingest(self._record(), tenant_id=self.tenant)
        self.assertEqual(row["source_type"], "guidance")
        self.assertEqual(row["source_location"], "https://example.test/guide")
        self.assertTrue(str(row["id"]))

    # 04 missing source ID rejected
    def test_04_missing_source_id_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.ingest(
                self._record(source_id="  "), tenant_id=self.tenant)

    # 05 missing source type rejected
    def test_05_missing_source_type_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.ingest(
                self._record(source_type=None), tenant_id=self.tenant)

    # 06 missing source location rejected
    def test_06_missing_source_location_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.ingest(
                self._record(source_location=" "), tenant_id=self.tenant)

    # 07 unsupported source type rejected (no silent normalization)
    def test_07_unsupported_source_type_rejected(self) -> None:
        for bad in ("REGULATION", "Regulation", "unknown", "blog"):
            with self.assertRaises(DomainValidationError):
                self.service.ingest(
                    self._record(source_type=bad), tenant_id=self.tenant)

    # 08 invalid tenant rejected
    def test_08_invalid_tenant_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.ingest(self._record(), tenant_id="bad")

    # 09 conflicting tenant rejected
    def test_09_conflicting_tenant_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.ingest(
                self._record(tenant_id=OTHER_TENANT_ID),
                tenant_id=self.tenant,
            )

    # 12 metadata validation
    def test_12_metadata_validation(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.ingest(
                self._record(metadata="not-a-dict"), tenant_id=self.tenant)
        row = self.service.ingest(
            self._record(metadata={"authority": "NAFDAC"}),
            tenant_id=self.tenant,
        )
        self.assertEqual(row["metadata"], {"authority": "NAFDAC"})

    # 13 deterministic text normalization
    def test_13_normalization(self) -> None:
        row = self.service.ingest(
            self._record(
                title="  Padded title  ",
                source_location="  https://example.test/p  ",
            ),
            tenant_id=self.tenant,
        )
        self.assertEqual(row["title"], "Padded title")
        self.assertEqual(row["source_location"], "https://example.test/p")

    # 14 source content preserved byte-for-byte
    def test_14_content_preserved(self) -> None:
        content = "  Exporters must hold a valid certificate.  "
        row = self.service.ingest(
            self._record(content=content), tenant_id=self.tenant)
        self.assertEqual(row["content"], content)

    # 15 content fingerprint deterministic
    def test_15_fingerprint_deterministic(self) -> None:
        first = self.service.ingest(self._record(), tenant_id=self.tenant)
        self.repo.rows.clear()
        second = self.service.ingest(self._record(), tenant_id=self.tenant)
        self.assertEqual(first["content_fingerprint"],
                         second["content_fingerprint"])
        self.assertEqual(
            first["content_fingerprint"],
            content_fingerprint("Exporters must hold a valid certificate."))

    # 16 stable document identity reused
    def test_16_stable_identity(self) -> None:
        first = self.service.ingest(self._record(), tenant_id=self.tenant)
        self.repo.rows.clear()
        second = self.service.ingest(self._record(), tenant_id=self.tenant)
        self.assertEqual(first["id"], second["id"])

    # 17 identical duplicate ingestion is idempotent
    def test_17_idempotent_duplicate(self) -> None:
        first = self.service.ingest(self._record(), tenant_id=self.tenant)
        create_calls = self.repo.create_calls
        again = self.service.ingest(self._record(), tenant_id=self.tenant)
        self.assertEqual(first["id"], again["id"])
        self.assertEqual(self.repo.create_calls, create_calls)
        self.assertEqual(len(self.repo.list_for_tenant(self.tenant)), 1)

    # 18 conflicting duplicate content rejected (fail closed)
    def test_18_conflicting_duplicate_content_rejected(self) -> None:
        self.service.ingest(self._record(), tenant_id=self.tenant)
        with self.assertRaises(DomainValidationError):
            self.service.ingest(
                self._record(content="Different substantive content."),
                tenant_id=self.tenant,
            )

    # 19 conflicting duplicate provenance rejected (fail closed)
    def test_19_conflicting_duplicate_provenance_rejected(self) -> None:
        self.service.ingest(self._record(), tenant_id=self.tenant)
        with self.assertRaises(DomainValidationError):
            self.service.ingest(
                self._record(source_type="regulation"),
                tenant_id=self.tenant,
            )

    # 20 document version identity preserved
    def test_20_version_identity(self) -> None:
        row = self.service.ingest(
            self._record(document_version="v2"), tenant_id=self.tenant)
        self.assertEqual(row["document_version"], "v2")

    # 21 different versions produce distinct documents
    def test_21_versions_distinct(self) -> None:
        self.service.ingest(
            self._record(document_version="v1"), tenant_id=self.tenant)
        second = self.service.ingest(
            self._record(document_version="v2"), tenant_id=self.tenant)
        self.assertEqual(len(self.repo.list_for_tenant(self.tenant)), 2)
        self.assertEqual(second["document_version"], "v2")

    # 22 status preserved + unknown status rejected
    def test_22_status_preserved(self) -> None:
        row = self.service.ingest(
            self._record(status="inactive"), tenant_id=self.tenant)
        self.assertEqual(row["status"], "inactive")
        with self.assertRaises(DomainValidationError):
            self.service.ingest(
                self._record(status="approved"), tenant_id=self.tenant)

    # 23 malformed date/version rejected
    def test_23_malformed_date_version_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.ingest(
                self._record(effective_date="2026-01-01"),
                tenant_id=self.tenant,
            )
        with self.assertRaises(DomainValidationError):
            self.service.ingest(
                self._record(retrieved_at={"x": 1}), tenant_id=self.tenant)
        with self.assertRaises(DomainValidationError):
            self.service.ingest(
                self._record(document_version=" v1 "), tenant_id=self.tenant)
        with self.assertRaises(DomainValidationError):
            self.service.ingest(
                self._record(document_version=7), tenant_id=self.tenant)

    # 24 repository is used for persistence
    def test_24_repository_used(self) -> None:
        self.service.ingest(self._record(), tenant_id=self.tenant)
        self.assertEqual(self.repo.create_calls, 1)

    # 25 end-to-end source -> ingestion -> corpus document
    def test_25_end_to_end(self) -> None:
        row = self.service.ingest(self._record(), tenant_id=self.tenant)
        stored = self.repo.get_by_id(self.tenant, row["id"])
        self.assertIsNotNone(stored)
        self.assertEqual(stored["source_id"], "nafdac/cocoa-guide")
        self.assertEqual(stored["tenant_id"], TENANT_ID)
        self.assertEqual(
            stored["content_fingerprint"], row["content_fingerprint"])
        self.assertIsNone(self.repo.get_by_id(self.other, row["id"]))

    # extra: repository integrity error translated to domain error
    def test_extra_integrity_error_translated(self) -> None:
        self.service.ingest(self._record(), tenant_id=self.tenant)
        self.repo.get_by_source_identity = lambda *a, **k: None
        with self.assertRaises(DomainPersistenceError):
            self.service.ingest(self._record(), tenant_id=self.tenant)

    # extra: no compliance/risk/applicability/retrieval fields introduced
    def test_extra_no_inferred_fields(self) -> None:
        row = self.service.ingest(self._record(), tenant_id=self.tenant)
        for forbidden in ("compliance_status", "risk", "applicable",
                          "retrieval_result", "verdict", "satisfied"):
            self.assertNotIn(forbidden, row)

    # extra: malformed source record rejected
    def test_extra_malformed_record_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.ingest("not-a-dict", tenant_id=self.tenant)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()


    # 10 empty title rejected
    def test_10_empty_title_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.ingest(
                self._record(title="   "), tenant_id=self.tenant)

    # 11 empty content rejected
    def test_11_empty_content_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.ingest(
                self._record(content="   "), tenant_id=self.tenant)
