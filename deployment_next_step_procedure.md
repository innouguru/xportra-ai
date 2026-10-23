=== Next Step Toward Deployment — Operator Procedure (Not Executed) ===
Context: local validation complete (`final_validation_report.md`); role cleaned from `xportra_test`. Two independent blockers remain unresolved (authorization/bootstrap prerequisites; 029 provenance in ADR-0019). This document records the exact hosted action required from the authorized operator; it is NOT executed by this agent.

--- SEPARATION: SAFE LOCAL PREPARATION vs HOSTED OPERATOR ACTION ---

SAFE LOCAL PREPARATION (agent can prepare; does not modify hosted DB):
- Confirm `.env` remains unchanged (documented original state: `postgres` superuser, masked; never inspected for secrets).
- Confirm `.env.example` remains placeholder only (`DATABASE_URL=` empty; no secrets added).
- Confirm `docs/deployment/bootstrap-authorization-db-role.md` SQL is the exact reference for provisioning.
- Confirm `docs/deployment/XPORTA-V1-DEPLOYMENT.md` §4 is the reference for migration execution order and admin-role separation.
- Confirm `operator_checklist_xportra_app.md` and `local_test_procedure.md` are preserved (review artifacts, not production instructions).
- Confirm unrelated tracked/untracked changes preserved (same as before this session).
- Confirm temporary execution scripts removed; no new tracked changes besides procedure/review files.

HOSTED OPERATOR ACTION (requires authorized operator; NOT executed by this agent; depends on unresolved prerequisites):
Target: hosted Supabase PostgreSQL (production/staging environment). Connection must use the DB administrator role (`postgres` or a designated `xportra_admin`) — NEVER `xportra_app`.
Step A — Role provisioning (execute only after authorization/bootstrap prerequisites resolved separately, unless operator explicitly chooses the justification path):
```sql
CREATE ROLE xportra_app WITH LOGIN PASSWORD '<strong-password-set-by-operator>';
ALTER ROLE xportra_app NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT USAGE ON SCHEMA xportra TO xportra_app;
GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES ON ALL TABLES IN SCHEMA xportra TO xportra_app;
-- If future migrations add sequences:
-- GRANT USAGE, SELECT ON SEQUENCE <sequence_name> TO xportra_app;
```
Note: operator replaces `<strong-password-set-by-operator>`; never write real value into tracked documentation. `.env` updated by operator separately (line below). `.env.example` must remain placeholder only.

Step B — Verification (run against hosted DB as `xportra_app` after Step A):
```sql
SELECT current_user, session_user, current_database();
SELECT rolsuper, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = current_user;
SELECT grantee, privilege_type FROM information_schema.table_privileges WHERE table_schema = 'xportra' AND grantee = current_user;
SELECT nspname, nspacl FROM pg_namespace WHERE nspname = 'public';
```
Expected (documented): `rolsuper = false`, `rolcreaterole = false`, `rolcreatedb = false`; privileges exactly `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `REFERENCES`; no `CREATE` on `public`.

Step C — Migration execution (hosted, admin role `postgres` or `xportra_admin`, NOT `xportra_app`):
Apply in order: 001 → 014 (verified). 015–028 applied only if separately authorized (local evidence shows 015–028 exist and pass; production application requires authorization). 029: BLOCKED (ADR-0019 provenance gap; `??` untracked; NOT applied).

Step D — Environment update (operator updates `.env` locally or on host; NOT committed with secrets; `.env.example` placeholder only):
`DATABASE_URL=postgresql://xportra_app:<strong-password-set-by-operator>@<host>:5432/postgres`

Step E — Authorization/bootstrap prerequisites (must be resolved BEFORE live bootstrap; NOT executed by this agent; documented prerequisites preserved):
From `docs/deployment/bootstrap-authorization-db-role.md` lines 138-145 and `tasks/blocked/bootstrap-authorization-policy.md`:
- Independent authorization record (`global_staff_authorizations`) with verified `authorization_ref`, justification, approved status, unconsumed.
- Independent verification evidence retained in organization-controlled store (separate from repository).
- Exception authority defined.
- Final retention/deletion policy approved.
- Second operator/grant-manager provisioned.
Only after these are resolved: execute `GlobalStaffGrantService.bootstrap()` (never raw SQL) with `actor_user_id`, `target_user_id`, `justification`, `authorization_ref`.

Step F — Post-bootstrap verification (operator action):
- Confirm `global_staff_grants` has exactly one active `grant_manage` row for target.
- Confirm `global_staff_audit` contains bootstrap event with `authorization_ref` (migration 017 linkage).
- Confirm application starts with `DATABASE_URL` pointing to `xportra_app`.

Step G — Migration 029 resolution (independent blocker; NOT combined with role/bootstrap):
Documented action in ADR-0019: either (a) verify provenance/reconstruct with independent review and record ADR, or (b) separately authorized reconstruction/review. Only after resolution: apply `migrations/029_regulatory_review_flags.sql` (with explicit grants for new table), then verify privileges include new table.

--- WHAT WAS NOT DONE (per instructions) ---
- `.env` not inspected or modified; `.env.example` unchanged.
- No hosted database accessed (Supabase not accessed; Render not accessed).
- No SQL executed against hosted DB.
- Role cleaned from local `xportra_test` safely; no production role created.
- Migration 029 not applied or declared safe.
- Bootstrap/auth prerequisites not executed or fabricated.
- Unrelated working-tree changes preserved; new files are procedure/review artifacts only; no tracked source/test/migration files modified; nothing committed or pushed.

--- NEXT SMALLEST ACTION (operator decision, not executed) ---
Choose ONE:
A) Proceed with hosted role provisioning (Step A above) only if authorization/bootstrap prerequisites are resolved independently first; OR
B) Defer hosted provisioning until prerequisites (authorization record, verification evidence, retention policy, exception authority, second operator, 029 provenance) are resolved; document justification for `postgres` superuser as intended application role with acknowledged risk if role deferred.
The validation confirms the design works; the remaining gate is operational authorization, not technical correctness.
