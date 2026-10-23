=== Approved Decisions (Product Owner) ===
- Single-operator exception approved for initial release (justification: unavailable second independent operator; scope: `grant_manage` only; never misrepresented as independent review).
- Self-bootstrap prohibition maintained (`_deny_self_managed` enforced).
- Verification mechanism/retention location: still unresolved (must be specified before any live authorization insertion).
- Exception authority: still unresolved (must be defined before live authorization).
- Retention/deletion policy: provisional 24 months; controls disabled; must be finalized before broadening access.
- Second operator: deferred; exception applies for minimal release.
- Role choice: must be finalized (dedicated `xportra_app` with verification, or explicit `postgres` justification with acknowledgment of superuser privileges) before authorization/bootstrap.
- Migration 029: reconstructed; technical consistency satisfactory; provenance unverified; blocked until separately authorized provenance/review authorization; must include explicit `GRANT ... ON ALL TABLES IN SCHEMA xportra TO xportra_app;` for new table when applied.

--- Authorization / Bootstrap Preparation (Prepared — Not Executed) ===
Status: Prerequisites partially resolved under personal-project authorization (role design validated locally; role cleaned from xportra_test; single-operator exception documented explicitly with justification; verification mechanism and retention location still unresolved; second operator unavailable; retention/deletion policy provisional 24 months, controls disabled; exception authority not fully defined). Not executed against hosted DB. Not inserted into `global_staff_authorizations`. No authorization_ref exists in database.

Reference: tasks/blocked/bootstrap-authorization-policy.md (§Prerequisites 47-54, §Evidence elements 17-30); docs/deployment/bootstrap-authorization-db-role.md (§Prerequisites 138-145); docs/phases/phase-4d-10-authorization-evidence-procedure.md (§Evidence retention 6-15, §Evidence elements 17-30); CURRENT_STATE.md (§Phase 4D.12 prerequisites 3905-3911); ADR-0019 (§Status 3-4, blocked); dependency_summary.md (§Dependencies A-F).

--- Prepared Authorization Template ---
This is a documented template, NOT a database insertion. The product owner must confirm these elements and specify the missing verification mechanism/retention location before any authorization record is inserted.

- Authorizer identity/reference: Product owner (explicitly named; this authorization uses the approved single-operator exception — not an independent review — with justification recorded below; never hardcoded as a UUID in documentation).
- Target user identity/reference: Resolved via verified identity mapping (`supabase_uid` -> `users.id`) at execution time; never hardcoded in documentation or code.
- Permission scope: `grant_manage` only (`GRANT_MANAGE` constant, `global_staff.py` line 33; authorization-policy.md §Evidence elements 17-30 item 3; prerequisites §2 item 3).
- Independent verifier identity/reference: For this exception, the verifier is the same individual as the authorizer (product owner), with explicit justification and audit linkage documented below. Not an independent review.
- Verification method: Must be specified by product owner before live authorization (e.g., signed approval message reference, recorded meeting/minutes, documented operational procedure reference). Currently unresolved (authorization-policy.md §Evidence retention 6-15; prerequisites §48 line 17; authorization-policy.md §Unresolved operational detail 18-19). Not fabricated.
- Authorization reference (`authorization_ref`): Placeholder — must be a non-empty, unique, verifiable identifier (e.g., `auth-ref-2026-<date>-release-001`) matching exactly between database record and independent evidence. Not invented.
- Justification: Initial `grant_manage` authorization for designated initial trusted operator (`innouguru@gmail.com` mapping verified externally 2026-10-21, CURRENT_STATE.md §Phase 4D.10 line 276-309). Single-operator exception applied (independent verifier unavailable for minimal release; second operator provision remains unresolved prerequisite). Scope limited to `grant_manage`.
- Status: Would be `approved` upon insertion; `consumed` after bootstrap execution (atomic consumption within transaction, authorization-policy.md §3 line 22-25; `global_staff.py` lines 219-221).
- Timestamps: `approved_at` (when authorization approved by product owner); `verified_at` (when verification confirmed — for single-operator exception, same timestamp with exception justification); `consumed_at` (after bootstrap); `consumed_by` (operator executing bootstrap); `revoked_by` (if revoked).
- Audit linkage: `global_staff_audit` event must retain `authorization_ref` (migration 017 linkage, `global_staff_audit_authorization_ref.sql`; service inserts audit event atomically with grant creation, `global_staff.py` lines 234-245; authorization-policy.md §Audit and retention 35-37).

--- Validation Evidence (Local Only — Not Independent Evidence) ---
Local role validation completed (`final_validation_report.md`): role created and privileges verified in isolated `xportra_test`; 16 integration tests passed; application SELECT/INSERT/UPDATE/DELETE confirmed as `xportra_app`; admin denial confirmed (`InsufficientPrivilege` for role/schema creation); role safely cleaned up (`DROP ROLE IF EXISTS`). This is technical verification of the design, not authorization evidence for live bootstrap. The verification mechanism for the authorization itself remains unresolved.

--- Missing Operational Prerequisites (Before Any Authorization Record Insertion) ---
From authorization-policy.md §Prerequisites 47-54 and bootstrap prerequisites 138-145:
1. Verification mechanism / retention location (prerequisites §48 line 17; authorization-policy.md §Evidence retention 6-15) — must be specified by product owner.
2. Exception authority (prerequisites §49; authorization-policy.md §Unresolved operational detail 18-19) — must be defined.
3. Final retention/deletion policy (prerequisites §4 line 143; authorization-policy.md §Audit and retention 35-37) — provisional 24 months; controls disabled.
4. Second operator/grant-manager provision (prerequisites §5 line 144) — unavailable for minimal release; single-operator exception applies.
5. Role verification / justification (prerequisites §2 line 141) — documented above; local validation confirms role design sufficient; justification document must be finalized if `postgres` superuser is confirmed as intended role.
6. Independent authorization execution: authorization record must be created with `status='approved'` and verified `authorization_ref` before any bootstrap (`global_staff_authorizations` table from migration 016; service consumes authorization atomically, `global_staff.py` lines 202-225).

--- Bootstrap Execution Steps (Prepared — Not Executed) ---
Only after prerequisites 1-6 above are resolved:
1. Confirm authorization record exists (`global_staff_authorizations`) with verified `authorization_ref`, `status='approved'`, matching `target_user_id`, `permission='grant_manage'`, unconsumed (`consumed_at IS NULL`).
2. Execute `GlobalStaffGrantService.bootstrap()` (`global_staff.py` lines 170-246) with:
   - `actor_user_id`: verified active user (independent operator; for exception: product owner acting as operator, with justification and audit linkage).
   - `target_user_id`: designated initial operator (`users.id` resolved from `supabase_uid` mapping; CURRENT_STATE.md §Phase 4D.10 line 276-309).
   - `justification`: documented justification including single-operator exception justification.
   - `authorization_ref`: verified non-empty reference matching authorization record exactly.
3. Confirm service returns active `grant_manage` row with `status='active'`.
4. Confirm audit event (`global_staff_audit`) includes `authorization_ref` (migration 017 linkage; service inserts audit atomically, `global_staff.py` lines 234-245).
5. Confirm authorization consumed (`global_staff_authorizations.status='consumed'`, `consumed_at` set, `consumed_by` recorded) in same transaction.
6. Confirm `rolsuper=false` and privileges verified as `xportra_app` before live deployment (local verification completed; must be repeated against hosted DB if dedicated role configured).

--- Prohibited Confirmations (Reaffirmed) ---
- Not executed: authorization record creation, authorization insertion (`INSERT INTO global_staff_authorizations`), authorization consumption, bootstrap (`service.bootstrap()`), live grants (`service.grant()` beyond setup fixtures), live revocation.
- Not executed: authorization reference not invented; verification evidence not fabricated.
- Not executed: single-operator exception not misrepresented as independent review; justification clearly documented.
- Migration 029: not executed; provenance unverified; must include explicit privileges for new table (`GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES ON ALL TABLES IN SCHEMA xportra TO xportra_app;` applies to existing tables only; new table requires explicit grant — bootstrap doc line 44).
- Not executed: hosted role provisioned; hosted SQL not executed; `.env` unchanged; hosted environment not modified.

--- Smallest Next Step (Not Executed) ---
Prepare authorization record elements above; confirm prerequisites 1-5 resolved by product-owner/operator; then execute Step 1 (verify authorization record exists) and Step 2 (run `service.bootstrap()` with verified reference) against hosted DB. Role provision (`deployment_next_step_procedure.md`) must be completed before authorization/bootstrap if dedicated role chosen; justification document finalized if `postgres` intended.
