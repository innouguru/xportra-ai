# ACTIVE_TASK.md — Current Active Task

**Active task:** Phase 4D initial global staff bootstrap — production-readiness review complete (2026-10-28). Verdict READY WITH CONDITIONS. Commit `3819589` implementation re-verified; production execution path resolved: the operator CLI (`xportra/dev/global_staff_bootstrap.py`) now supports an explicit `--production-confirmation` that must exactly equal `--authorization-ref` when `APP_ENV=production` (checked before any DB connection; exit 2 otherwise) — previously no safe production path existed (the doc's production command was refused by design and no alternative was defined). Service authorization checks, single-use atomic consumption, actor ≠ target, atomic grant+audit and audit-linkage are unchanged and re-verified (integration 7/7 as `xportra_app` on local `xportra_test`). Authorization schema (migration 016) matches the approved form fields; `authorization_ref` uniqueness is not DB-enforced (read-only pre-insert check SQL now documented); optional `expires_at` is not evaluated by the service (do not set it on the initial record). Prior context (2026-10-24, retained): hosted migrations 015–018 pre-existing, 016/017/019–028 applied and verified; 029 excluded (ADR-0019); identity mapping verified end-to-end read-only (masked).

**Status:** READY WITH CONDITIONS — no authorization record, grant, or audit row exists in production; this review created/consumed nothing and contacted no production system. Remaining operator prerequisites before executing the approved `XPA-GSA-INIT-001` bootstrap: (1) establish evidence store + trusted verification channel, (2) finalize DB connection identity (`xportra_app` per `docs/deployment/bootstrap-authorization-db-role.md` or documented privileged-role justification), (3) fully define exception authority, (4) provision/identify the distinct active actor and verifier user rows required by the authorization schema and the actor ≠ target rule, (5) insert the approved authorization record out-of-band (with the documented uniqueness check), (6) execute the documented production command with `--production-confirmation XPA-GSA-INIT-001`, (7) verify the three read-only acceptance queries. Verification this task: unit 44 passed (11 new CLI-guard tests + existing global-staff/dev-bootstrap suites); integration bootstrap suite 7 passed. Full detail in `CURRENT_STATE.md` (entry: Initial Global Staff Bootstrap — Production-Readiness Review, 2026-10-28).

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

**2026-10-21 authorization hardening (local, not committed):** `complete_job`/`fail_job` authorization added; `RegulatorySourceStorageApplicationService` created with `GRANT_MANAGE` enforcement; adapter `delete` unexposed; deletion blocker documented (`docs/phases/regulatory-artifact-retention-policy.md`). Focused tests: 12 passed; regression adapter/ingestion/worker tests pass. Integration tests skipped without `DATABASE_URL`.

## Phase 4D.15 — Workstream E Verification (2026-10-22)

Verdict: PASS WITH CONDITIONS. No new defects. End-to-end paths verified locally; pre-existing failures (stage A dsn fixtures, ingestion audit order-dependence, 029 provenance) documented. No files changed. No production smoke executed (staging blocked; no authorization). Next: resolve DB role + 029 provenance, then authorized live verification. Workstream F deferred.
