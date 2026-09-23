"""Phase 4.0 - Evidence Corpus Foundation tests."""

import copy
import unittest
from datetime import date, datetime, timezone
from uuid import UUID

from xportra.domain.errors import DomainNotFoundError, DomainValidationError
from xportra.domain.evidence_corpus import (
    DOCUMENT_STATUSES,
    SOURCE_TYPES,
    EvidenceDocument,
    content_fingerprint,
    stable_document_id,
)
from xportra.domain.evidence_service import EvidenceCorpusService
from xportra.persistence.tenant import TenantContext

TENANT_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
OTHER_TENANT_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


class MemoryRepository:
    """In-memory stand-in honoring the corpus repository contract."""

    def __init__(self) -> None:
        self.rows = {}

    def create(self, record):
        key = (record["tenant_id"], record["id"])
        if key in self.rows:
            from xportra.persistence.errors import PersistenceIntegrityError
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


class TestEvidenceCorpus(unittest.TestCase):
    def setUp(self) -> None:
        self.tenant = TenantContext(TENANT_ID)
        self.other = TenantContext(OTHER_TENANT_ID)
        self.repo = MemoryRepository()
        self.service = EvidenceCorpusService(self.repo)

    def _values(self, **kw):
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
        }
        base.update(kw)
        return base

    def test_03_tenant_preserved(self) -> None:
        doc = EvidenceDocument.create(self.tenant, **self._values())
        self.assertEqual(doc.tenant_id, TENANT_ID)
        self.assertEqual(doc.to_record()["tenant_id"], TENANT_ID)

    def test_04_invalid_tenant_rejected(self) -> None:
        with self.assertRaises(Exception):
            self.service.create("bad", **self._values())

    def test_05_cross_tenant_rejected(self) -> None:
        row = self.service.create(self.tenant, **self._values())
        self.assertIsNone(self.repo.get_by_id(self.other, row["id"]))
        with self.assertRaises(DomainNotFoundError):
            self.service.require_active(self.other, row["id"])


    def test_01_valid_creation(self) -> None:
        row = self.service.create(self.tenant, **self._values())
        self.assertEqual(row["tenant_id"], TENANT_ID)
        self.assertEqual(row["status"], "active")

    def test_02_provenance(self) -> None:
        row = self.service.create(self.tenant, **self._values())
        self.assertEqual(row["source_id"], "nafdac/cocoa-guide")

    def test_06_missing_source_id_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.create(self.tenant, **self._values(source_id="  "))

    def test_07_missing_document_identity_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            EvidenceDocument.from_record({"title": "x"})

    def test_08_bad_source_type_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.create(self.tenant, **self._values(source_type="blog"))
        with self.assertRaises(DomainValidationError):
            self.service.create(
                self.tenant, **self._values(source_type="Regulation"))

    def test_09_missing_content_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            self.service.create(self.tenant, **self._values(content="   "))
        with self.assertRaises(DomainValidationError):
            self.service.create(self.tenant, **self._values(title=""))

    def test_10_stable_identity(self) -> None:
        first = EvidenceDocument.create(self.tenant, **self._values())
        second = EvidenceDocument.create(self.tenant, **self._values())
        self.assertEqual(first.document_id, second.document_id)
        self.assertEqual(
            first.document_id,
            stable_document_id(TENANT_ID, "nafdac/cocoa-guide", "v1"))

    def test_11_duplicate_rejected(self) -> None:
        self.service.create(self.tenant, **self._values())
        with self.assertRaises(DomainValidationError):
            self.service.create(self.tenant, **self._values())

    def test_12_same_source_version_same_document(self) -> None:
        first = self.service.create(self.tenant, **self._values())
        found = self.service.get_by_source(
            self.tenant, "nafdac/cocoa-guide", "v1")
        self.assertEqual(found["id"], first["id"])

    def test_13_different_version_distinct(self) -> None:
        first = self.service.create(self.tenant, **self._values())
        second = self.service.create(
            self.tenant, **self._values(document_version="v2"))
        self.assertNotEqual(first["id"], second["id"])

    def test_14_get_by_id(self) -> None:
        row = self.service.create(self.tenant, **self._values())
        found = self.service.get(self.tenant, row["id"])
        self.assertEqual(found["id"], row["id"])
        self.assertEqual(found["title"], "NAFDAC cocoa guidance")

    def test_15_tenant_scoped_lookup(self) -> None:
        row = self.service.create(self.tenant, **self._values())
        self.assertIsNone(self.service.get(self.other, row["id"]))

    def test_16_tenant_scoped_listing(self) -> None:
        self.service.create(self.tenant, **self._values())
        self.service.create(
            self.other,
            **self._values(source_id="nafdac/other-guide"))
        own = self.service.list_for_tenant(self.tenant)
        self.assertEqual(len(own), 1)
        self.assertEqual(own[0]["tenant_id"], TENANT_ID)

    def test_17_cross_tenant_lookup_rejected(self) -> None:
        row = self.service.create(self.tenant, **self._values())
        self.assertIsNone(self.service.get(self.other, row["id"]))
        with self.assertRaises(DomainNotFoundError):
            self.service.require_active(self.other, row["id"])

    def test_18_provenance_preserved(self) -> None:
        row = self.service.create(self.tenant, **self._values())
        doc = EvidenceDocument.from_record(row)
        self.assertEqual(doc.source_id, "nafdac/cocoa-guide")
        self.assertEqual(doc.document_id, row["id"])

    def test_19_location_preserved(self) -> None:
        row = self.service.create(self.tenant, **self._values())
        self.assertEqual(row["source_location"], "https://example.test/guide")

    def test_20_status_preserved(self) -> None:
        row = self.service.create(
            self.tenant, **self._values(status="inactive"))
        self.assertEqual(row["status"], "inactive")

    def test_21_inactive_not_active(self) -> None:
        row = self.service.create(
            self.tenant, **self._values(status="inactive"))
        doc = EvidenceDocument.from_record(row)
        self.assertFalse(doc.is_active)
        with self.assertRaises(DomainValidationError):
            self.service.require_active(self.tenant, row["id"])

    def test_22_metadata_preserved(self) -> None:
        row = self.service.create(self.tenant, **self._values())
        self.assertEqual(row["metadata"], {"authority": "NAFDAC"})

    def test_23_malformed_rejected(self) -> None:
        with self.assertRaises(DomainValidationError):
            EvidenceDocument.from_record("bad")
        with self.assertRaises(DomainValidationError):
            EvidenceDocument.from_record({"title": "x"})

    def test_24_round_trip(self) -> None:
        row = self.service.create(self.tenant, **self._values())
        doc = EvidenceDocument.from_record(row)
        self.assertEqual(doc.to_record()["content_fingerprint"],
                         row["content_fingerprint"])
        self.assertEqual(doc.title, "NAFDAC cocoa guidance")

    def test_25_end_to_end(self) -> None:
        row = self.service.create(self.tenant, **self._values())
        found = self.service.get(self.tenant, row["id"])
        doc = EvidenceDocument.from_record(found)
        self.assertEqual(doc.tenant_id, TENANT_ID)
        self.assertEqual(doc.source_id, "nafdac/cocoa-guide")
        self.assertTrue(doc.is_active)
        listed = self.service.list_for_tenant(self.tenant)
        self.assertEqual([r["id"] for r in listed], [row["id"]])

    def test_26_vocabularies(self) -> None:
        self.assertEqual(
            SOURCE_TYPES,
            {"regulation", "guidance", "certificate", "policy", "other"})
        self.assertEqual(DOCUMENT_STATUSES, {"active", "inactive"})
        self.assertTrue(len(content_fingerprint("abc")) == 64)


if __name__ == "__main__":
    unittest.main()


