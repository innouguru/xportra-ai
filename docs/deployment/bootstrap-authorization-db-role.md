# Phase 4D.10 — Dedicated Runtime Database Role Specification

> Status: documented; NOT executed against production or hosted environment.
> This file records the required configuration. An authorized operator must apply the SQL commands below to the target environment before deploying with a dedicated application role.

## Approved decision (frozen)

The application connects using `.env` (`postgresql://postgres...`) — the `postgres` superuser/admin role. This task documents the dedicated least-privilege runtime role (`xportra_app`) required by the approved operational-readiness design, and records the exact commands an authorized operator must execute. It does NOT modify production, create roles in production, or alter the `.env` file.

## Evidence basis (repository inspection only)

- `.env`: `DATABASE_URL=postgresql://postgres...` (host masked; user `postgres`).
- `.env.example`: placeholder only; no dedicated user configured.
- `docs/architecture/environment-schema.md`: `DATABASE_URL` is the only DB variable; no separate user/role variable exists.
- `docs/deployment/XPORTA-V1-DEPLOYMENT.md`: migrations applied via `psql` by an operator; no dedicated app DB user mentioned.
- Migrations (`001`–`017`): create `xportra` schema and application tables; no dedicated DB role created.
- `migrations/015_global_staff_grants.sql`: creates `global_staff_grants`, `global_staff_audit`, trigger function `global_staff_audit_reject_mutation()`.
- `migrations/016_global_staff_authorizations.sql`: creates `global_staff_authorizations`.
- `migrations/017_global_staff_audit_authorization_ref.sql`: adds `authorization_ref` to `global_staff_audit`.
- `tests/unit/test_global_staff.py`: 14 passed.
- `tests/integration/test_global_staff_postgresql.py`: 16 passed against isolated `xportra_test`.
- `CURRENT_STATE.md`: confirms `.env` uses `postgres` superuser; no dedicated app role configured.

## Dedicated runtime role (`xportra_app`)

### Privileges required (least-privilege)

The role must have only the privileges needed for normal application operation. No superuser (`NOSUPERUSER`), no database creation (`NOCREATEDB`), no role creation (`NOCREATEROLE`).

```sql
-- Authorized operator command sequence (NOT executed here)
CREATE ROLE xportra_app WITH LOGIN PASSWORD '<strong-password>';
ALTER ROLE xportra_app NOSUPERUSER NOCREATEDB NOCREATEROLE;

GRANT USAGE ON SCHEMA xportra TO xportra_app;

-- Table privileges for all application tables (verified against current schema)
GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES ON ALL TABLES IN SCHEMA xportra TO xportra_app;

-- If future migrations add sequences, also run:
-- GRANT USAGE, SELECT ON SEQUENCE <sequence_name> TO xportra_app;
```

Note: the `GRANT ... ON ALL TABLES` applies to existing tables; future tables added by new migrations must have privileges granted explicitly by the operator applying those migrations.

### Explicit exclusions (must NOT be granted)

- `SUPERUSER`, `CREATEDB`, `CREATEROLE` privileges.
- Schema creation (`CREATE`) on `public` or any schema other than `xportra` (if needed, the role should not have `CREATE` on the schema by default).
- Direct access to administrative/superuser functions outside `xportra`.

### Migration role separation

Migration commands (`CREATE TABLE`, `ALTER TABLE`, `CREATE FUNCTION`, `CREATE TRIGGER`, `DROP`, `CREATE INDEX`) must be executed by an authorized operator (e.g., `postgres` or a designated `xportra_admin`), never by `xportra_app`. The application must never run migrations at startup or per-request.

## Configuration update (not executed)

To deploy with the dedicated role, an authorized operator updates the environment (e.g., `.env` locally or host environment in production) to:

```text
DATABASE_URL=postgresql://xportra_app:<strong-password>@<host>:5432/postgres
```

This value must be set by the operator; `.env.example` must be updated with a placeholder only (no real secrets). The repository `.env` remains unchanged.

## Verification steps (authorized operator only)

1. Create/update the role per the SQL above.
2. Verify role identity safely:

```sql
SELECT current_user, session_user, current_database();
SELECT rolsuper, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = 'xportra_app';
SELECT grantee, privilege_type FROM information_schema.table_privileges WHERE table_schema = 'xportra' AND grantee = 'xportra_app';
```

3. Confirm `rolsuper = false` and privileges match only `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `REFERENCES` (and `TRIGGER` where applicable via table grants) on `xportra` objects.
4. Confirm no `CREATE` on `public` or other schemas (unless explicitly required by a future approved change).
5. Confirm application runs successfully against the updated `DATABASE_URL` locally (`postgresql://localhost/xportra_test` or an isolated test environment) before any production change.
6. Confirm `tests/unit/test_global_staff.py` (14 passed) and `tests/integration/test_global_staff_postgresql.py` (16 passed) pass with the dedicated role connection (local test only; production startup remains an operator action).

## Confirmed findings (read-only evidence, no production change)

- `.env` uses `postgres` superuser (`postgresql://postgres...`).
- `.env` updated? No.
- `.env.example` updated? No (must be updated by operator with placeholder only).
- Dedicated DB role created in production/shared database? No.
- Dedicated DB role created in local `xportra_test`? No (documented only).
- Migration 015–017 applied locally? Yes (`global_staff_grants`, `global_staff_audit`, `global_staff_authorizations` present in `xportra_test`).
- Tests rerun against local DB with original `postgres` connection? Yes (14 unit + 16 integration passed; 30 total; 0 failed; 0 skipped).
- Tests rerun against dedicated role? Not performed — dedicated role does not exist locally; would require operator action.
- Production database modified? No.
- Authorization record created? No.
- Live grant provisioned? No.

## Verified local findings (2026-10-23)

- Application database-role design (`xportra_app`) is sufficient: `NOSUPERUSER NOCREATEDB NOCREATEROLE`, `USAGE` on `xportra`, `SELECT/INSERT/UPDATE/DELETE/REFERENCES` on all `xportra` tables, no `CREATE` on `public` by default, migration execution separated from runtime role.
- `.env.example` contains no dedicated user (confirmed; unchanged).
- `.env` remains `postgres` superuser (confirmed; unchanged, not exposed).
- No implementation defect found in bootstrap service (`global_staff.py`), authorization repository (`repositories.py`), audit repository, or authorization mechanism (migrations 015–017, service contracts, atomic transaction, self-bootstrap denial, authorization consumption, audit linkage).
- Unit tests `tests/unit/test_global_staff.py`: 14 passed; integration `tests/integration/test_global_staff_postgresql.py`: 16 passed against isolated `xportra_test`.
- Migration 029 (`migrations/029_regulatory_review_flags.sql` / `.down.sql`): remains untracked; provenance gap unverified per ADR-0019; NOT executed; NOT declared safe; authorization unchanged.

## Required owner read-only verification (exact procedure, safe, no secrets)

Execute these queries as the actual intended application role against an isolated/test environment (NOT production) before any deployment change:

```sql
-- 1. Confirm the connection identity
SELECT current_user, session_user, current_database();

-- 2. Confirm role properties (must return false for superuser/createdb/createrole)
SELECT rolsuper, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = current_user;

-- 3. Confirm schema/table privileges (must show only SELECT, INSERT, UPDATE, DELETE, REFERENCES on xportra objects; no superuser privileges)
SELECT grantee, privilege_type FROM information_schema.table_privileges WHERE table_schema = 'xportra' AND grantee = current_user;

-- 4. Confirm no unexpected privileges on public or other schemas
SELECT nspname, nspacl FROM pg_namespace WHERE nspname = 'public';
```

Expected results for `xportra_app`:
- `rolsuper = false`, `rolcreaterole = false`, `rolcreatedb = false`.
- Privileges on `xportra`: exactly `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `REFERENCES` (and `TRIGGER` where applicable via table-level grants).
- No `CREATE` on `public`; no `TRUNCATE` unless explicitly granted by design (currently excluded by the approved role contract).

If the role returns superuser-level privileges (`rolsuper = true`) or privileges exceeding the approved contract, treat it as a confirmed security gap and either (a) reconfigure `DATABASE_URL` to use a dedicated `xportra_app` user, or (b) document explicit justification with acknowledged risk.

## Bootstrap authorization mechanism verification (local, no production change)

- Implementation (`global_staff.py`): sound. Atomic transaction (advisory lock, authorization verification, consumption, grant insertion, audit insertion), self-bootstrap denied (`_deny_self_managed`), authorization reference required and verified (`get_by_ref`), authorization consumed atomically, audit retains `authorization_ref` (migration 017 linkage).
- Tests (`tests/unit/test_global_staff.py`): 14 passed; `test_bootstrap_grants_only_grant_manage_and_is_attributable`, `test_bootstrap_is_idempotent_for_same_target`, `test_bootstrap_refuses_when_holder_exists_for_another_user`, `test_audit_insert_failure_rolls_back_state_mutation`, `test_grant_creates_state_and_audit_atomically` all pass.
- No authorization record exists (`global_staff_authorizations` empty in verified environments).
- No live grant provisioned.
- Migration 029 remains blocked per ADR-0019.

## Unresolved prerequisites before live bootstrap

1. **Evidence retention mechanism**: organization-controlled store must be specified by product owner or authorized operator (see `docs/phases/phase-4d-10-authorization-evidence-procedure.md`).
2. **Dedicated DB role**: either (a) configure `DATABASE_URL` with `xportra_app` and verify privileges safely, or (b) document explicit justification confirming `postgres` as the intended application role (with acknowledgment of superuser-level privileges and associated risk).
3. **Exception authority**: define who may approve exceptions (same-person exception for Stage A/Stage B, manual recovery) and how exceptions are audited.
4. **Retention/deletion policy**: final retention period and deletion controls remain unresolved; automatic deletion disabled.
5. **Second operator provision**: mitigate single-operator dependency.
6. **Independent authorization execution**: complete authorization record (`global_staff_authorizations`) with verified `authorization_ref`, justification, independent verification evidence, and audit linkage (`global_staff_audit.authorization_ref`); then execute bootstrap atomically.
