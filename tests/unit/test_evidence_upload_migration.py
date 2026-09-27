"""Phase 10.4 — Evidence-upload migration structural tests.

Verifies migration 011 (and its rollback) statically:
balanced transaction markers, exact column inventory
with symmetric drops, the tenant-scoped content-hash
uniqueness index with symmetric drop, the processing
index, and no other-table changes. Live apply/rollback
coverage stays gated on ``DATABASE_URL``, as elsewhere.
"""

import pathlib
import re
import unittest

MIGRATIONS = (
    pathlib.Path(__file__).resolve().parents[2] / "migrations"
)
UP = MIGRATIONS / "011_evidence_upload_processing.sql"
DOWN = MIGRATIONS / "011_evidence_upload_processing.down.sql"

COLUMNS = (
    "processing_status",
    "processing_step",
    "processing_error",
    "processed_at",
    "original_filename",
    "mime_type",
    "storage_bucket",
    "uploaded_by",
)

INDEXES = (
    "compliance_evidence_tenant_hash_uidx",
    "compliance_evidence_tenant_processing_idx",
)


class MigrationStructureTests(unittest.TestCase):
    def test_migration_files_exist(self):
        self.assertTrue(UP.is_file())
        self.assertTrue(DOWN.is_file())

    def test_transaction_markers_balanced(self):
        for path in (UP, DOWN):
            text = path.read_text(encoding="utf-8")
            self.assertEqual(len(re.findall(r"^BEGIN;$", text, re.M)), 1)
            self.assertEqual(len(re.findall(r"^COMMIT;$", text, re.M)), 1)
            self.assertTrue(
                text.index("BEGIN;") < text.index("COMMIT;"))

    def test_up_adds_exactly_the_upload_columns(self):
        text = UP.read_text(encoding="utf-8")
        added = re.findall(r"ADD COLUMN IF NOT EXISTS (\w+)", text)
        self.assertEqual(tuple(added), COLUMNS)

    def test_up_touches_only_compliance_evidence(self):
        text = UP.read_text(encoding="utf-8")
        tables = set(re.findall(
            r"(?:TABLE|ON)\s+(xportra\.\w+)", text))
        self.assertEqual(tables, {"xportra.compliance_evidence"})

    def test_processing_status_lifecycle_check(self):
        text = UP.read_text(encoding="utf-8")
        self.assertIn(
            "CHECK (processing_status IN "
            "('uploaded', 'processing', 'ready', 'failed'))",
            text)

    def test_content_hash_idempotency_index(self):
        text = UP.read_text(encoding="utf-8")
        self.assertIn(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "compliance_evidence_tenant_hash_uidx",
            text)
        self.assertIn("WHERE content_hash IS NOT NULL", text)

    def test_down_drops_exactly_those_columns(self):
        text = DOWN.read_text(encoding="utf-8")
        dropped = re.findall(r"DROP COLUMN IF EXISTS (\w+)", text)
        self.assertEqual(set(dropped), set(COLUMNS))
        self.assertEqual(len(dropped), len(COLUMNS))

    def test_down_drops_exactly_those_indexes(self):
        text = DOWN.read_text(encoding="utf-8")
        dropped = re.findall(r"DROP INDEX IF EXISTS (\S+);", text)
        self.assertEqual(set(dropped), {
            f"xportra.{name}" for name in INDEXES})

    def test_down_touches_no_other_objects(self):
        text = DOWN.read_text(encoding="utf-8")
        statements = [
            line.strip() for line in text.splitlines()
            if line.strip()
            and not line.strip().startswith("--")
            and line.strip() not in ("BEGIN;", "COMMIT;")
        ]
        self.assertTrue(statements)
        for statement in statements:
            self.assertTrue(
                statement.startswith("DROP INDEX IF EXISTS")
                or statement.startswith("DROP COLUMN IF EXISTS")
                or statement.startswith("ALTER TABLE"),
                statement)


if __name__ == "__main__":
    unittest.main()
