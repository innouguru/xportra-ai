"""Phase 8.4 — Result-store migration structural tests.

Verifies migration 010 (and its rollback) statically:
balanced transaction markers, exact table inventory
with symmetric drops, tenant ownership, relationships,
constraints, indexes, triggers — and no data
manipulation, seeding, or unrelated-table changes.
Live apply/rollback coverage is gated in
``tests/integration/test_result_store_postgresql.py``.
"""

import pathlib
import re
import unittest

MIGRATIONS = (
    pathlib.Path(__file__).resolve().parents[2] / "migrations"
)
UP = MIGRATIONS / "010_compliance_analysis_results.sql"
DOWN = MIGRATIONS / "010_compliance_analysis_results.down.sql"

TABLES = (
    "xportra.compliance_analysis_reports",
    "xportra.compliance_analyses",
    "xportra.compliance_analysis_traces",
    "xportra.compliance_workflow_rounds",
    "xportra.final_assessment_packages",
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

    def test_up_creates_exactly_five_tables(self):
        text = UP.read_text(encoding="utf-8")
        created = re.findall(
            r"CREATE TABLE IF NOT EXISTS (\S+)", text)
        self.assertEqual(tuple(created), TABLES)

    def test_down_drops_exactly_those_tables(self):
        text = DOWN.read_text(encoding="utf-8")
        dropped = re.findall(r"DROP TABLE IF EXISTS (\S+);", text)
        self.assertEqual(set(dropped), set(TABLES))
        self.assertEqual(len(dropped), len(TABLES))
        for table in TABLES:
            self.assertIn(
                f"DROP TRIGGER IF EXISTS", text)

    def test_down_touches_no_other_tables(self):
        text = DOWN.read_text(encoding="utf-8")
        statements = [
            line.strip() for line in text.splitlines()
            if line.strip()
            and not line.strip().startswith("--")
            and line.strip() not in ("BEGIN;", "COMMIT;")
        ]
        for statement in statements:
            self.assertTrue(
                statement.startswith("DROP TRIGGER IF EXISTS")
                or statement.startswith("DROP TABLE IF EXISTS"),
                statement)

    def test_tenant_ownership_everywhere(self):
        text = UP.read_text(encoding="utf-8")
        self.assertEqual(
            text.count("tenant_id UUID NOT NULL REFERENCES "
                       "xportra.tenants(id) ON DELETE RESTRICT"),
            len(TABLES))

    def test_composite_tenant_identity_keys(self):
        text = UP.read_text(encoding="utf-8")
        for fragment in (
                "UNIQUE (tenant_id, id)",
                "UNIQUE (tenant_id, report_id, position)",
                "PRIMARY KEY (tenant_id, workflow_id, round_index)",
                "UNIQUE (tenant_id, workflow_id)",
        ):
            self.assertIn(fragment, text)

    def test_composition_cascades_and_link_restricts(self):
        text = UP.read_text(encoding="utf-8")
        self.assertEqual(text.count("ON DELETE CASCADE"), 3)
        self.assertGreaterEqual(
            text.count("ON DELETE RESTRICT"),
            len(TABLES) + 2)

    def test_state_check_constraints(self):
        text = UP.read_text(encoding="utf-8")
        for fragment in (
                "applicability IN ('applicable', 'not_applicable', 'unknown')",
                "assessment IN ('satisfied', 'not_satisfied', 'unknown')",
                "evidence_sufficiency IN ('supported', 'insufficient', "
                "'missing', 'unknown')",
                "contradiction_state IN ('none', 'present')",
                "round_index INTEGER NOT NULL CHECK (round_index >= 1)",
        ):
            self.assertIn(fragment, text)

    def test_indexes_and_triggers(self):
        text = UP.read_text(encoding="utf-8")
        self.assertGreaterEqual(
            len(re.findall(r"CREATE INDEX IF NOT EXISTS", text)), 5)
        self.assertEqual(
            len(re.findall(
                r"EXECUTE FUNCTION xportra.set_updated_at\(\)",
                text)),
            len(TABLES))

    def test_schema_only_no_data_changes(self):
        for path, allowed in (
                (UP, {"CREATE", "BEGIN;", "COMMIT;"}),
                (DOWN, {"DROP", "BEGIN;", "COMMIT;"})):
            for line in path.read_text(
                    encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("--"):
                    continue
                self.assertFalse(
                    re.match(
                        r"^(INSERT|UPDATE|DELETE)\b", stripped,
                        re.IGNORECASE),
                    stripped)

    def test_no_workflow_or_requirement_tables(self):
        text = UP.read_text(encoding="utf-8")
        self.assertNotIn("CREATE TABLE", text.replace(
            "CREATE TABLE IF NOT EXISTS", ""))
        for name in ("compliance_workflows", "regulatory_requirements"):
            self.assertNotIn(
                f"REFERENCES xportra.{name}", text)


if __name__ == "__main__":
    unittest.main()
