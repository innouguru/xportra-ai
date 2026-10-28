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

## Production bootstrap procedure (after prerequisites resolved)

Once all prerequisites above are resolved and the production runtime role is confirmed, an authorized operator performs the initial `grant_manage` bootstrap as follows. This procedure is **operator-only** and never connects to production from this task.

### Prerequisites (all must be confirmed before starting)

- Migrations 015–017 applied to the production database (`global_staff_grants`, `global_staff_audit`, `global_staff_authorizations` tables present).
- Authorization record inserted in `xportra.global_staff_authorizations` with:
  - `status = 'approved'`
  - `authorization_ref = 'XPA-GSA-INIT-001'` (or the approved reference; never a different value unless the approved form specifies otherwise)
  - `target_user_id` = verified internal `xportra.users.id` of the target
  - `permission = 'grant_manage'`
  - `authorizer_user_id` = independent authorizer's `xportra.users.id`
  - `verifier_user_id` = independent verifier's `xportra.users.id`
  - `justification` = documented reason (including single-operator exception justification if applicable)
  - `approved_at`, `verified_at` timestamps set
- Uniqueness of `authorization_ref` is **not** enforced by a database
  constraint (migration 016 has no unique index on the ref column). Before
  inserting the authorization record, the operator must run this read-only
  check and confirm it returns zero rows:

  ```sql
  SELECT id, target_user_id, permission, status, consumed_at
  FROM xportra.global_staff_authorizations
  WHERE authorization_ref = 'XPA-GSA-INIT-001';
  ```

  Exactly one row must exist after insertion; never insert a second row
  with the same reference.
- Target user exists in `xportra.users` with `status = 'active'` and `supabase_uid` mapped to their Supabase Auth identity.
- Actor (operator) is an active `xportra.users` row, distinct from the target.
- Evidence retention location established (per prerequisite 1); `authorization_ref` links to retained evidence.

### Configuration and TLS (how the CLI obtains its connection)

The CLI reads configuration from the **process environment only** —
`DatabaseSettings.from_environment` reads exactly one key,
`DATABASE_URL`, and no dotenv loading exists anywhere in the codebase
(`xportra/dev/global_staff_bootstrap.py:213-234`,
`xportra/persistence/database.py:22-31`). A local `.env` file is inert
until its values are exported into the process environment.

The DSN is passed verbatim to libpq via psycopg, so TLS is configured
entirely through the DSN (or standard libpq environment variables) — no
CLI flags and no code changes are involved:

- Append `?sslmode=verify-full` to the production DSN. `verify-full` is
  the only mode that verifies both the certificate chain **and** the
  server hostname; `prefer` and `require` do not verify either.
- Supply the Supabase CA certificate (`cert/prod-ca-2021.crt`, listed
  in `.gitignore`) either as `sslrootcert=<path>` inside the DSN
  (URL-encode a Windows path, e.g. `sslrootcert=C%3A/Users/.../cert/prod-ca-2021.crt`)
  or — simpler and recommended — via the standard libpq variable
  `PGSSLROOTCERT` set to the certificate path (absolute path preferred;
  a relative path resolves against the working directory).

Example operator configuration file (`.env.production-operator` —
already covered by the gitignored `.env.*` rule at `.gitignore:27`;
never commit it, never paste its contents into chat, tickets, or logs):

```text
# .env.production-operator (gitignored) — one KEY=value per line,
# unquoted, no inline comments after values. Lines starting with #
# and blank lines are ignored by the session loader below.
APP_ENV=production

# Supabase Shared Pooler — verified connection pattern (2026-10-28).
# The username MUST stay project-qualified ("<role>.<project-ref>"):
# the shared pooler routes on that suffix. Never shorten it to a bare
# "xportra_app". <pooler-password> is a placeholder — enter the real
# pooler password only inside this file, never on a command line and
# never in a commit. If the password contains URI-reserved characters
# (@ : / ? # %), URL-encode it within the DSN.
DATABASE_URL=postgresql://xportra_app.waugynqpuwsazehsjyvj:<pooler-password>@aws-0-eu-west-2.pooler.supabase.com:5432/postgres?sslmode=verify-full

# Windows certificate path: prefer the absolute path to the local
# repository copy (cert/prod-ca-2021.crt, gitignored) so verify-full
# works regardless of the working directory. Spaces in the path are
# safe as an environment-variable value. If you instead embed
# sslrootcert inside the DSN, URL-encode the path, e.g.
# sslrootcert=C%3A/Users/<you>/Xportra%20AI/cert/prod-ca-2021.crt
PGSSLROOTCERT=C:\absolute\path\to\Xportra AI\cert\prod-ca-2021.crt
```

### Execution

Run on the operator machine against the production database. The
loader below runs in the current PowerShell session only: it first
clears `APP_ENV`, `DATABASE_URL`, and `PGSSLROOTCERT` so a stale
development value can never survive a partial load, assigns the
operator-file values without echoing them, then verifies the effective
environment (PASS/FAIL per check — check names only, never values) and
aborts before the CLI runs if anything is wrong. Nothing is printed or
written to disk by this step. All identity and justification arguments
are non-secret; the DSN never appears in the command line, shell
history, argv, logs, or chat output:

```powershell
# 1) Clear every variable this loader manages so a stale development
#    value can never silently survive a partial load.
Remove-Item Env:APP_ENV, Env:DATABASE_URL, Env:PGSSLROOTCERT -ErrorAction SilentlyContinue

# 2) Load the operator file. KEY=value lines only; this block prints
#    nothing — values are assigned directly to the process environment.
if (-not (Test-Path -LiteralPath '.env.production-operator')) {
  throw 'operator configuration not found: .env.production-operator'
}
Get-Content -LiteralPath '.env.production-operator' -ErrorAction Stop | ForEach-Object {
  if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$') {
    [Environment]::SetEnvironmentVariable($matches[1], $matches[2])
  }
}

# 3) Verify the effective environment BEFORE running the CLI. Prints
#    PASS/FAIL per check (check names only — never values) and throws
#    on any failure, so a wrong environment or database cannot be used
#    silently.
$dsn = [Environment]::GetEnvironmentVariable('DATABASE_URL')
$checks = [ordered]@{
  'APP_ENV is production'    = $env:APP_ENV -eq 'production'
  'DATABASE_URL is set'      = [bool]$dsn
  'DATABASE_URL unquoted'    = $dsn -and ($dsn -notlike '"*')
  'pooler host and database' = $dsn -and ($dsn -match '^[^@]*@aws-0-eu-west-2\.pooler\.supabase\.com:5432/postgres')
  'sslmode is verify-full'   = $dsn -and ($dsn -match '[?&]sslmode=verify-full(&|$)')
  'CA is prod-ca-2021.crt'   = $env:PGSSLROOTCERT -and ($env:PGSSLROOTCERT -like '*prod-ca-2021.crt')
  'CA file exists'           = $env:PGSSLROOTCERT -and (Test-Path -LiteralPath ([string]$env:PGSSLROOTCERT))
}
$checks.GetEnumerator() | ForEach-Object {
  '{0} {1}' -f $(if ($_.Value) { 'PASS:' } else { 'FAIL:' }), $_.Key
}
if ($checks.Values -contains $false) {
  throw 'operator configuration verification failed — not running the bootstrap CLI.'
}

python -m xportra.dev.global_staff_bootstrap `
    --authorization-ref XPA-GSA-INIT-001 `
    --production-confirmation XPA-GSA-INIT-001 `
    --target-user-id <verified-target-user-uuid> `
    --actor-user-id <verified-actor-user-uuid> `
    --justification "<approved justification>"
```

Do **not** inline `DATABASE_URL=... python ...` on the command line:
inline assignment places credentials in shell history. The session
loader assigns values with `[Environment]::SetEnvironmentVariable`,
which does not echo them to the terminal — do not additionally print
the file (`Get-Content`, `type`, `cat`), redirect it to the screen, or
paste it into chat, tickets, or logs. The pooler password exists only
inside the gitignored operator file and the resulting process
environment; the CLI accepts no password argument and never prints the
DSN or SSL configuration (its report is asserted by unit test to
contain no DSN, SSL, or role material). Keep values unquoted and on a
single line — the loader takes everything after the first `=` verbatim.
The pre-load clear plus the PASS/FAIL verification make a wrong file
fail loudly: loading a shared development `.env` — or an operator file
missing a required key, quoting a value, or pointing at the wrong host
— stops with a verification error before the CLI runs instead of
silently targeting the wrong environment or database. Keep the
dedicated operator file above.

The CLI refuses `APP_ENV=production` unless `--production-confirmation` exactly
matches the `--authorization-ref` being consumed. That exact-match flag
is the explicit, one-time production confirmation: the production path
cannot be enabled accidentally, and every service-level authorization
check (approved, unconsumed, target/permission match, actor ≠ target,
atomic grant + authorization consumption + audit) still applies:

**Important:** never emulate production by setting
`APP_ENV=development` or `APP_ENV=test` while pointing `DATABASE_URL`
at the production database. Always run with `APP_ENV=production` and
the explicit confirmation against the production database so the
guard, attribution, and audit trail remain truthful. The CLI does not
bypass `GlobalStaffGrantService.bootstrap`; grant and audit rows are
created exclusively through the service transaction, and the CLI
never prints the DSN or credentials.

### Verification after bootstrap

Confirm (read-only, against production database):

1. `SELECT * FROM xportra.global_staff_grants WHERE permission = 'grant_manage' AND status = 'active'` — exactly one row, `user_id` = target, `granted_by` = actor.
2. `SELECT * FROM xportra.global_staff_authorizations WHERE authorization_ref = 'XPA-GSA-INIT-001'` — `status = 'consumed'`, `consumed_at` set, `consumed_by` = actor.
3. `SELECT * FROM xportra.global_staff_audit WHERE event_type = 'bootstrap' AND authorization_ref = 'XPA-GSA-INIT-001'` — one row linking the authorization to the grant event.

### What this procedure does NOT do

- Does not create the authorization record (must exist before execution, created out-of-band by independent authorizer/verifier).
- Does not create a public API endpoint for bootstrap.
- Does not bypass `GlobalStaffGrantService.bootstrap` (no direct inserts into `global_staff_grants` or `global_staff_audit`).
- Does not embed credentials or secrets in source code, arguments, logs, or documentation.
- Does not apply migrations or change `DATABASE_URL`.

## Addendum (2026-10-28) — production confirmation mechanism

- The CLI production path is `--production-confirmation` exactly matching
  `--authorization-ref` (see Execution above). Without the exact match the
  CLI exits with code 2 before opening any database connection; the guard
  is covered by unit tests in
  `tests/unit/test_global_staff_bootstrap_cli.py`.
- Correction to the 2026-10-23 findings above: the dedicated `xportra_app`
  role has since been created and used locally against the isolated
  `xportra_test` database; the bootstrap integration tests
  (`tests/integration/test_global_staff_bootstrap_postgresql.py`, 7 tests)
  passed as `xportra_app`. Production role configuration remains unchanged.
- Known service-level observation (not a blocker for this bootstrap):
  `GlobalStaffGrantService.bootstrap` does not evaluate the optional
  `expires_at` column even though its error message mentions expiry.
  Authorizations without an `expires_at` value (NULL, the default) are
  unaffected. Do not set `expires_at` on the initial authorization record;
  expiry enforcement remains open follow-up work.

