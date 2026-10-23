=== Operator Checklist — `xportra_app` Role Validation ===
Evidence: docs/deployment/bootstrap-authorization-db-role.md; migrations 001–029; xportra/persistence/repositories.py; xportra/application/global_staff.py; CURRENT_STATE.md; ADR-0019.
No `.env` inspected; no hosted DB accessed; no modifications made.

--- 1. ROLE PROVISIONING (manual operator SQL; NOT automated) ---
Reference: docs/deployment/bootstrap-authorization-db-role.md §Dedicated runtime role.
Exact SQL (operator replaces '<strong-password>' with actual secret; never commit):

```sql
CREATE ROLE xportra_app WITH LOGIN PASSWORD '<strong-password>';
ALTER ROLE xportra_app NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT USAGE ON SCHEMA xportra TO xportra_app;
GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES ON ALL TABLES IN SCHEMA xportra TO xportra_app;
-- If future migrations add sequences, also run:
-- GRANT USAGE, SELECT ON SEQUENCE <sequence_name> TO xportra_app;
```

Corrections / clarifications before execution:
- SQL is safe and repeatable: `CREATE ROLE` will fail if role exists (expected; execute once).
- No sequences exist in current migrations (001–028); no sequence grants required now.
- `REFERENCES` is broader than strict runtime need (app uses INSERT/SELECT/UPDATE only) but safe and supports future schema work; keep as documented.
- `DELETE` is included but not used by current repositories; keep for future recovery/revocation operations.
- `TRUNCATE` is correctly excluded.
- `CREATE` on `public` is correctly excluded.

Repeatability note: future migrations (e.g., any table added after 014, or 029 if authorized) must have privileges granted explicitly by the operator applying them (`GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES ON ALL TABLES IN SCHEMA xportra TO xportra_app;` will cover only existing tables at that time).

--- 2. LOCAL APPLICATION CONFIGURATION (separate from role creation) ---
Reference: docs/deployment/bootstrap-authorization-db-role.md §Configuration update.
- Do NOT modify repository `.env` (it must remain unchanged; secrets never committed).
- Update `.env.example` with placeholder only: `DATABASE_URL=` (no real password).
- Actual production/local `.env` must be updated by operator to:
  `DATABASE_URL=postgresql://xportra_app:<strong-password>@<host>:5432/postgres`
- No new environment variables are approved by docs/architecture/environment-schema.md; `DATABASE_URL` remains the only DB variable.

--- 3. MIGRATION EXECUTION (admin/operator role; separate from application runtime) ---
Reference: docs/deployment/XPORTA-V1-DEPLOYMENT.md §4.
- Migration commands must be executed by `postgres` (or a designated `xportra_admin`), NEVER by `xportra_app`.
- Apply in filename order using `psql`:
  `psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f migrations/NNN_name.sql`
- Current verified sequence (through 014): 001 → 014.
- Migration 015–028: applied locally per CURRENT_STATE.md; production application requires separate authorization.
- Migration 029 (`migrations/029_regulatory_review_flags.sql` / `.down.sql`): BLOCKED. See section 5.

--- 4. INITIAL STAFF AUTHORIZATION / BOOTSTRAP (separate from role provisioning) ---
Reference: docs/deployment/bootstrap-authorization-db-role.md §Bootstrap authorization mechanism verification; tasks/blocked/bootstrap-authorization-policy.md.
Prerequisites (all unresolved; must be completed by owner/operator before execution):
- Independent product-owner authorization for initial `grant_manage` grant.
- Verified `authorization_ref` recorded in `global_staff_authorizations` (migration 016 applied; table exists locally after 015–017).
- Independent verification evidence retained in an organization-controlled store (not repository-only).
- Exception authority defined.
- Second operator / grant-manager provisioning plan established.
- Migration 029 provenance resolved (blocked; see section 5).

Execution (only after prerequisites met):
- Execute via `GlobalStaffGrantService.bootstrap()` (xportra/application/global_staff.py), NOT via raw SQL.
- Supply `actor_user_id` (verified active user), `target_user_id`, `justification`, and `authorization_ref`.
- Self-bootstrap (`actor == target` with `grant_manage`) is denied by `_deny_self_managed`.
- Audit event (`global_staff_audit`) must retain `authorization_ref` (migration 017 linkage).

--- 5. MIGRATION 029 — BLOCKED (separate from role/provisioning) ---
Evidence: `migrations/029_regulatory_review_flags.sql` is `??` untracked (`git status`); `git log --all --full-history --` shows no commit linkage; ADR-0019 records provenance gap.
Status: Technical consistency satisfactory (matches repository/services/tests) but historical authorization unverified.
Action: DO NOT apply to hosted or production database. Resolution requires either (a) verified provenance/reconstruction with independent review and ADR, or (b) separate authorized reconstruction/review process.
This is independent of `xportra_app` provisioning; both must be resolved before live deployment, but they must not be combined into a single unverified action.

--- VERIFICATION QUERIES (read-only; safe; run as `xportra_app` in isolated/test env before production) ---
Reference: docs/deployment/bootstrap-authorization-db-role.md §Verification steps; §Required owner read-only verification.

```sql
SELECT current_user, session_user, current_database();
SELECT rolsuper, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = current_user;
SELECT grantee, privilege_type FROM information_schema.table_privileges WHERE table_schema = 'xportra' AND grantee = current_user;
SELECT nspname, nspacl FROM pg_namespace WHERE nspname = 'public';
```

Expected: `rolsuper = false`, `rolcreaterole = false`, `rolcreatedb = false`. Privileges on `xportra`: exactly `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `REFERENCES`. No `CREATE` on `public`.

--- PRIVILEGE VALIDATION AGAINST ACTUAL APPLICATION OPERATIONS ---
Evidence from xportra/persistence/repositories.py and xportra/application/global_staff.py:
- Operations: SELECT (all repositories), INSERT (all repositories, audit, grants, authorization), UPDATE (user identity, grants revocation/reactivation, regulatory requirements stage updates, evidence processing state, source updates), no DELETE (audit is append-only; grants use UPDATE/revocation; no repository performs DELETE).
- Tables used: all `xportra.*` tables (existing through 014; 015–017 add `global_staff_grants`, `global_staff_audit`, `global_staff_authorizations`). Migration 029 table (`regulatory_review_flags`) must be granted explicitly if/when 029 is authorized.
- Functions: `gen_random_uuid()` (available via `pgcrypto` installed by admin in 001); `pg_advisory_xact_lock()` (built-in advisory lock, no EXECUTE grant required); trigger `global_staff_audit_reject_mutation()` (runs automatically on DML, no EXECUTE grant required for `xportra_app`).
- Sequences: none in current schema; no sequence grants needed now.
- Schema access: `USAGE` on `xportra` is sufficient.
- No `CREATE` needed for runtime (migrations executed by admin/operator role).

Conclusion: Documented privileges (`SELECT, INSERT, UPDATE, DELETE, REFERENCES` + `USAGE`) cover current and near-term runtime needs. `DELETE` is slightly broader than current use but safe and supports future recovery; `REFERENCES` is standard practice; no sequence grants needed; no EXECUTE grants needed for triggers/built-ins.

--- SMALLEST SAFE NEXT ACTION ---
Choose ONE (operator/owner action; I will NOT execute):
A) MANUAL ROLE PROVISIONING (least-privilege path):
   1. Execute SQL from section 1 in this checklist against isolated/test DB.
   2. Run verification queries in section 4; confirm `rolsuper = false` and privileges match.
   3. Confirm application tests (`tests/unit/test_global_staff.py` 14 passed; `tests/integration/test_global_staff_postgresql.py` 16 passed) pass with dedicated role locally.
   4. Update `.env` (not `.env.example` with secrets) to `postgresql://xportra_app:<strong-password>@<host>:5432/postgres`; update `.env.example` placeholder only.
   5. Apply migrations 001–014 (admin role); 015–028 only after authorization; NEVER apply 029 until provenance resolved (section 5).

B) EXPLICIT JUSTIFICATION (if `postgres` intended):
   - Product owner/authorized operator documents explicit justification confirming `postgres` as intended application role, with acknowledgment of superuser-level privileges and associated risk.
   - Record justification independently (not only `.env`).

--- WHAT WAS NOT DONE (per instructions) ---
- `.env` not inspected; `.env.example` read only for schema confirmation.
- No hosted database connection or modification.
- No roles created, privileges granted, bootstrap executed, migrations run.
- Migration 029 not applied, not declared safe.
- Unrelated working-tree changes preserved (existing tracked modifications and untracked files untouched, including `migrations/029_regulatory_review_flags.sql`).
- Nothing committed or pushed.
