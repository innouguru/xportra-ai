import pathlib
import re
import unittest

MIGRATIONS = pathlib.Path(__file__).resolve().parents[2] / "migrations"
UP = MIGRATIONS / "014_organization_registration_profile.sql"
DOWN = MIGRATIONS / "014_organization_registration_profile.down.sql"


class OrganizationRegistrationMigrationTests(unittest.TestCase):
    def test_migration_files_exist(self):
        self.assertTrue(UP.is_file())
        self.assertTrue(DOWN.is_file())

    def test_transaction_markers_are_balanced(self):
        for path in (UP, DOWN):
            text = path.read_text(encoding="utf-8")
            self.assertEqual(len(re.findall(r"^BEGIN;$", text, re.M)), 1)
            self.assertEqual(len(re.findall(r"^COMMIT;$", text, re.M)), 1)

    def test_up_adds_only_nullable_organization_profile_columns(self):
        text = UP.read_text(encoding="utf-8")
        added = re.findall(r"ADD COLUMN IF NOT EXISTS (\w+)", text)
        self.assertEqual(
            added, ["organization_type", "country_code", "region"]
        )
        self.assertIn("ALTER TABLE xportra.tenants", text)
        self.assertIn("organization_type IS NULL", text)
        self.assertIn("country_code IS NULL", text)

    def test_down_removes_only_the_added_columns(self):
        text = DOWN.read_text(encoding="utf-8")
        dropped = re.findall(r"DROP COLUMN IF EXISTS (\w+)", text)
        self.assertEqual(
            set(dropped),
            {"organization_type", "country_code", "region"},
        )
        self.assertEqual(len(dropped), 3)


if __name__ == "__main__":
    unittest.main()
