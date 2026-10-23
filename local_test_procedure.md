=== Local Isolated Test Procedure — `xportra_app` Validation ===
Based on: docs/deployment/bootstrap-authorization-db-role.md; operator_checklist_xportra_app.md; CURRENT_STATE.md; migrations 001-029; integration/unit test references.
NOT executed. No SQL run. No `.env` inspected (only `.env.example` and test references). No Supabase accessed.

--- PREREQUISITES / CONTEXT (evidence-based) ---
- Local DB: `postgresql://postgres:postgres@localhost:5432/xportra_test` (evident from tests/integration/test_global_staff_postgresql.py line 49; CURRENT_STATE.md line 370; checklist; `tests/unit/test_dev_bootstrap.py` line 43 uses `postgresql://localhost/xportra_test` as placeholder). This is an isolated/test database, NOT production.
- Status: migrations 001-014 applied; 015-017 applied locally (CURRENT_STATE.md line 370, bootstrap doc line 89); 029 (`??` untracked, ADR-0019 blocked) NOT applied.
- Existing connection role for local DB: `postgres` superuser/admin (evident from test fixtures and docs; `.env` uses `postgres`; not inspected directly for secrets).
- No `xportra_app` role exists locally (bootstrap doc line 87-88: "No. (documented only)").
- Required migrations for test: 001-014 base schema; 015-017 for global staff (integration tests require 015). If testing full app operations, 011 (evidence upload processing) and 014 (organization profile) must be present; they are part of 001-014.
- Missing prerequisites reported (not assumed): dedicated role does not exist; authorization/bootstrap prerequisites unresolved (independent authorization, verification evidence retention, retention policy, second operator). Reported rather than invented.

--- DOCUMENTED SQL EXECUTION CONTEXT ---
Reference: docs/deployment/bootstrap-authorization-db-role.md §Dedicated runtime role (line 30-42).
Execution role: admin (`postgres` or designated `xportra_admin`), NEVER `xportra_app` (doc line 54; migration separation).
Target database: isolated local `xportra_test` (line 79: "locally (`postgresql://localhost/xportra_test` or an isolated test environment)").

Step 1 — Provision role (admin connection):
```sql
CREATE ROLE xportra_app WITH LOGIN PASSWORD '<strong-password>';
ALTER ROLE xportra_app NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT USAGE ON SCHEMA xportra TO xportra_app;
GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES ON ALL TABLES IN SCHEMA xportra TO xportra_app;
```
Note: operator replaces `<strong-password>`; never commit real value. SQL safe: `CREATE ROLE` fails if exists (execute once). `GRANT ... ON ALL TABLES` applies to existing tables only; future tables must be granted explicitly (line 44).

Step 2 — Verify as `xportra_app` (run these queries connected as `xportra_app` against `xportra_test`):
Reference: lines 71-75 (verification steps) and 109-121 (required owner read-only verification).
```sql
SELECT current_user, session_user, current_database();
SELECT rolsuper, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = current_user;
SELECT grantee, privilege_type FROM information_schema.table_privileges WHERE table_schema = 'xportra' AND grantee = current_user;
SELECT nspname, nspacl FROM pg_namespace WHERE nspname = 'public';
```
Expected (documented line 123-126): `rolsuper = false`, `rolcreaterole = false`, `rolcreatedb = false`. Privileges on `xportra`: exactly `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `REFERENCES`. No `CREATE` on `public`.

--- TEST APPLICATION ACCESS WITHOUT ADMIN PRIVILEGES ---
Method (documented line 79-80): update `.env` (local only; do NOT commit secrets) to point to `xportra_test` with `xportra_app` user; confirm application connects and executes required operations; confirm unit (14 passed) and integration (16 passed) pass with dedicated role locally.
Specific operations to verify (derived from repositories/application, NOT new assumption):
- SELECT from `xportra.tenants`, `users`, `compliance_evidence`, etc. (repositories show SELECT statements).
- INSERT into `global_staff_grants`, `global_staff_audit`, `global_staff_authorizations` (migration 015-017; repositories confirm INSERT via `_insert` and `_insert_in_transaction`).
- UPDATE on `users` (`set_supabase_uid`), `global_staff_grants` (revocation/reactivation), `regulatory_sources`, `compliance_evidence` (`set_processing_state`), `regulatory_requirements` (`update_stage_a`/`update_stage_b`).
- No DELETE performed by repositories (audit is append-only; grants use UPDATE/revocation). `DELETE` privilege granted but not exercised by current code.
- No sequences used (migrations use UUID with `gen_random_uuid()` from `pgcrypto`, installed by admin via 001; no `CREATE SEQUENCE` in any migration file).
- Advisory lock (`pg_advisory_xact_lock`) is a built-in function; no EXECUTE grant required for `xportra_app` to call it via `cursor.execute` (global_staff.py line 198).
- Trigger `global_staff_audit_reject_mutation()` runs automatically on DML to audit table; no EXECUTE grant required (standard PostgreSQL behavior; trigger executes with privileges of invoking user; `INSERT` on table is sufficient).
- Migration execution remains separate: must use `postgres`/`xportra_admin` connection, never `xportra_app` (line 54, checklist section 3).

--- ADMINISTRATIVE PRIVILEGE SEPARATION CHECK ---
Documented exclusions (line 46-51): `SUPERUSER`, `CREATEDB`, `CREATEROLE` must NOT be granted. `CREATE` on `public` excluded. Migration commands (`CREATE TABLE`, `ALTER TABLE`, etc.) must never be executed by `xportra_app`.
Verification query (documented line 120): `SELECT nspname, nspacl FROM pg_namespace WHERE nspname = 'public';` — confirm no unexpected `CREATE` for `xportra_app`.

--- CLEANUP / REVERT (only if safe; documented and standard practice) ---
If validation fails and role must be removed (not required by doc but standard safe procedure):
`DROP ROLE IF EXISTS xportra_app;` (standard PostgreSQL; not documented in bootstrap file but safe; no production impact since role was test-only).
Revert `.env` to original `postgres` connection (documented original state line 12, checklist section 2).
Restore `.env.example` placeholder (line 64).
Migration rollback: `.down.sql` files exist for 001-029; apply in reverse order if needed (XPORTA-V1-DEPLOYMENT.md §4 notes `.down.sql` rolls a single migration back for diagnosis, not routine use). For test isolation, if 015-017 were applied specifically for test and need removal: apply `.down.sql` for 017, 016, 015 in reverse order (this is standard PostgreSQL rollback, not a new assumption).
Note: authorization/bootstrap rollback is separate; authorization consumption is atomic (global_staff.py line 219-221); audit records are append-only (trigger prevents UPDATE/DELETE; rollback of authorization does not delete audit entries per design contract line 71-91 of migration 015 and bootstrap doc line 130-136).

--- PREREQUISITES CHECKED / MISSING REPORT ---
Present: local isolated DB (`xportra_test`); migrations through 014 applied; 015-017 present locally; `pgcrypto` installed (001); repositories/services verified against schema.
Reported missing (not invented): `xportra_app` role does not exist locally; authorization/bootstrap prerequisites unresolved (independent authorization record, verification evidence store, retention policy, exception authority, second operator); migration 029 provenance unverified (`??` untracked, ADR-0019); dedicated DB role not configured in `.env`.
Not performed: `.env` not inspected (only `.env.example`); `.env` not modified; SQL not executed; hosted Supabase not accessed; no roles created/granted; no bootstrap executed; no migrations applied/reverted; no files changed (only this review file added); nothing committed/pushed.

--- DISTINCTION: DOCUMENTED VS ADDITIONAL ---
Documented only: prerequisites, SQL, verification queries, expected results, admin separation, local test reference, `.env` rules, authorization prerequisites, 029 blocked status (bootstrap doc + CURRENT_STATE.md + ADR-0019 + checklist).
Additional recommendations (from checklist/review, clearly labeled): clarification that `REFERENCES`/`DELETE` are safe but slightly broader than current runtime; clarification that future tables/sequences need explicit grants; clarification that trigger/advisory lock require no EXECUTE grants; clarification that rollback uses standard PostgreSQL `.down.sql`/`DROP ROLE` (not documented explicitly in bootstrap file but standard safe procedure); clarification that authorization rollback preserves audit entries (derived from code and migration design, consistent with documented contract).

--- SMALLEST SAFE NEXT ACTION ---
Choose ONE (operator action; no execution performed here):
A) Execute section 2 SQL against local `xportra_test` as admin (`postgres`); run section 3 verification queries as `xportra_app`; confirm expected results; test app access locally; then either (i) proceed with role provisioning for production (after resolving authorization/bootstrap prerequisites separately) or (ii) drop test role (`DROP ROLE IF EXISTS xportra_app;`) and revert `.env`.
B) Do NOT create/test role until authorization/bootstrap prerequisites (independent authorization, evidence retention, exception authority, retention policy, second operator) and 029 provenance are resolved per documented prerequisites (bootstrap doc line 138-145, checklist section 4, ADR-0019). Document explicit justification for `postgres` if role is deferred.

No actions executed. No hosted DB modified. `.env` untouched. Unrelated working tree preserved.
