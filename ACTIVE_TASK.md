# ACTIVE_TASK.md — Current Active Task

**Active task:** Phase 4D.10 Storage Technology Review (Task 1 — inspect technology baseline; Task 2 — decision record created; prerequisites unresolved: dedicated storage/access policy, service identity/grant, PDF parser integration).

**Status:** Phase 4D.10 Task 2 complete locally; operational-readiness documentation updated (`tasks/blocked/bootstrap-authorization-policy.md`, `docs/phases/phase-4d-regulatory-knowledge-administration.md`). Independent authorization procedure defined with concrete binding rules (`global_staff_authorizations`, `authorization_ref`, atomic consumption, audit linkage). Evidence-retention mechanism proposed (organization-controlled store separate from repository) but remains unresolved until product owner/operational authority specifies exact channel and retention location. Actual DB role identified from `.env`: `postgres` superuser/admin role; no separate application DB user configured. Read-only inspection confirms superuser-level privileges. PASS WITH CONDITIONS — independent authorization execution and DB role resolution (either dedicated app user or explicit superuser justification) remain prerequisites before any separately authorized live bootstrap.

**Authorization scope:** Initial global staff permission grant and audit
foundation only, per ADR-0017 and the approved Phase 4D.10 Task 2 decisions
(subsections A–L). Subsequent Phase 4D.10 tasks (Task 3 and later) are NOT
authorized. Regulatory administration workflow, source management, Stage A/B,
publication, and exporter-facing behavior are NOT part of this task.

**Implemented, unit-tested, and validated against a live database:**
1. Migration 015: `xportra.global_staff_grants` (current-state grants, unique
   constraint on `(user_id, permission)`, revocation UPDATEs existing row,
   re-grant reactivates it) and `xportra.global_staff_audit` (append-only;
   update/delete rejected by trigger). Down migration included. Migration
   applied and verified against the live test database.
2. `GlobalStaffGrantRepository` and `GlobalStaffAuditRepository` in
   `xportra/persistence/repositories.py`.
3. `GlobalStaffGrantService` in `xportra/application/global_staff.py`:
   grant/revoke/bootstrap/is_granted, atomic grant+audit in one transaction,
   fail-closed on audit failure, self-grant/self-revocation of `grant_manage`
   denied, self-bootstrap denied (applies approved self-management policy),
   target account status validated on grant/revoke (active only), advisory-lock
   serialization for bootstrap, least-privilege (`grant_manage` only),
   idempotent bootstrap, authorization-reference verification for bootstrap
   (`global_staff_authorizations`), authorization consumption in transaction,
   audit event retains authorization reference.
4. `GRANT_MANAGE` authorization constant in `xportra/api/authorization.py`;
   `require_global_staff` dependency in `xportra/api/dependencies.py` (actor
   resolved from verified JWT subject → `users.supabase_uid` → `users.id`;
   tenant membership never substitutes).
5. Unit tests `tests/unit/test_global_staff.py` (14 passed); full focused
   suite passed. Integration tests `tests/integration/test_global_staff_postgresql.py`
   updated (rollback coverage, concurrency coverage, self-bootstrap fix,
   separate operator user for bootstrap); NOT executed because `DATABASE_URL`
   points to a production/shared database, not an isolated test database.
6. Migration 016 (`global_staff_authorizations`) and 017
   (`global_staff_audit_authorization_ref`) created; not applied to any
   verified environment. `GlobalStaffAuthorizationRepository` added;
   audit repository supports `authorization_ref`.
7. Integration tests `tests/integration/test_global_staff_postgresql.py`
    (13 passed) against a live test database with migration 015 applied.
    Tests are skipped when `DATABASE_URL` is not configured.

**Not implemented / deferred in this task:**
- Execution of the initial bootstrap against a database (no live provisioning;
  initial operator provisioning remains a separate product-owner authorized
  operation; internal user ID never hardcoded).
- Grant/revocation API routes and staff administration UI (Task 8 scope).
- Manual-recovery recording mechanism, exception authority, retention deletion
  controls, and Stage A/B permissions.
- Bootstrap authorization mechanism implemented (table, verification,
  audit linkage, service integration); initial live authorization record
  creation and initial operator provisioning remain deferred (separate
  product-owner authorized operation); see `tasks/blocked/bootstrap-authorization-policy.md`.

**External identity verification (product owner performed, read-only):**
- Supabase Auth account `innouguru@gmail.com` exists.
- Its Auth UID matched exactly one `xportra.users` row via `supabase_uid`.
- Matched user status: `active`.
- `user_tenant_memberships`: active membership, role `owner`.
- No Auth UID, internal UUID, tenant UUID, token, or secret is recorded.

**Verification:** identity-mapping contract verified from repository code
(auth.py, repositories.py, migration 002). No global permission mechanism
previously existed in any migration or `.py` file.

**No changes staged, committed, pushed, deployed, or made to production.**
