=== Authorization Record Template (Prepared — Not Executed) ===
Status: Prepared under approved personal-project authorization with single-operator exception explicitly noted. Not inserted into database. Live authorization prerequisites partially resolved; verification evidence retention mechanism remains unspecified and must be established before any authorization record is created in production.

Reference: tasks/blocked/bootstrap-authorization-policy.md (§Prerequisites 47-54); docs/phases/phase-4d-10-authorization-evidence-procedure.md (§Evidence elements 1-10); docs/deployment/bootstrap-authorization-db-role.md (§Prerequisites 138-145); CURRENT_STATE.md (§Phase 4D.10 prerequisites).

--- Single-Operator Exception (Documented Justification) ---
Exception authority: Not fully defined by design (authorization-policy.md §Unresolved operational detail line 19; prerequisites §49). For this initial personal-project release, the single-operator exception applies with the following explicit justification and scope limitations.
- Justification: The initial `grant_manage` authorization is for the designated initial trusted operator (`innouguru@gmail.com` identity mapping verified externally 2026-10-21 per CURRENT_STATE.md §Phase 4D.10) in the isolated development/test environment (`xportra_test`). A second independent operator is unavailable for this minimal release; a second operator provision plan remains an unresolved prerequisite.
- Scope: `grant_manage` only; no additional permissions (`STAGE_A_VERIFY`, `STAGE_B_APPROVE`) authorized by this record. Self-bootstrap (`actor == target` with `grant_manage`) remains denied by service-level check (`_deny_self_managed`, `global_staff.py` line 270-281); this authorization applies only to a different target user designated as the initial operator.
- Actor: Product owner (authorizer and independent verifier combined under exception; never the target user). The authorization record is created by the product owner with justification recorded; the execution operator is the same individual acting in operational capacity. This is explicitly a single-operator exception, not an independent review.
- Authorization reference (`authorization_ref`): A non-empty, unique identifier must be generated (e.g., `auth-ref-2026-<date>-release-001`). It must match exactly between the database record (`global_staff_authorizations.authorization_ref`) and any independent evidence reference.
- Independent verification evidence: The verification mechanism and retention location remain unresolved per prerequisites (§48 line 17; authorization-policy.md §Evidence retention 1-19). Before any live authorization record is inserted, the product owner must establish an organization-controlled, access-controlled evidence store (separate from repository) and specify its exact access mechanism. The authorization reference in the database must link to evidence retained in that store.
- Audit linkage: The authorization reference must be preserved in `global_staff_audit` (`authorization_ref` column, migration 017 linkage, `global_staff_audit_authorization_ref.sql`).
- Status: `approved` initially; `consumed` after bootstrap execution (atomic consumption within transaction, authorization-policy.md §3 line 22-25; `global_staff.py` lines 219-221).
- Timestamps: `approved_at` (when authorization approved), `verified_at` (when verification confirmed — for single-operator exception, this is documented as the same timestamp with exception justification noted), `consumed_at` (after bootstrap execution), `revoked_by` (if revoked).

--- Required Elements Before Database Insertion ---
From authorization-policy.md §Evidence elements (lines 21-30) and prerequisites (§7 lines 47-54):
1. Authorizer identity/reference — product owner (explicitly named).
2. Target user identity/reference — the designated initial operator; resolved via verified identity mapping (`supabase_uid` -> `users.id`). Not hardcoded in documentation.
3. Scope — exactly `grant_manage`.
4. Independent verifier identity/reference — for this exception: same individual as authorizer (product owner), with explicit justification and audit linkage; never target user.
5. Verification timestamp — `verified_at`; same as approval for exception, with justification recorded.
6. Trusted verification method — must be specified (e.g., signed approval message, meeting reference, documented operational procedure reference); generic statement insufficient.
7. Authorization reference (`authorization_ref`) — non-empty, unique, verifiable.
8. Justification — documented reason for authorization; includes explicit single-operator exception justification.
9. Status/timestamps — `approved` initially; `consumed` after bootstrap; `approved_at`, `verified_at`, `consumed_at`, `consumed_by`.
10. Audit reconciliation — authorization reference preserved in `global_staff_audit`; audit event links authorization to bootstrap.

--- Prohibited Actions (Reaffirmed) ---
- Creating authorization record or bootstrap grant without verified authorization reference (`global_staff.py` line 205-207: `ApplicationValidationError` if missing/revoked/expired/consumed/mismatched).
- Self-bootstrap (`actor == target` with `grant_manage`) denied by service (`_deny_self_managed`, `global_staff.py` line 270-278); authorization reference does not override this.
- Using `postgres` superuser as proof of authorization (authorization-policy.md §4 line 32; bootstrap prerequisites §7 line 51).
- Inventing verification evidence, timestamps, or authorization events.
- Applying authorization/bootstrap before prerequisites resolved.

--- Reconstruction Note for Migration 029 ---
Status: Migration 029 (`migrations/029_regulatory_review_flags.sql` / `.down.sql`) remains untracked (`??`); provenance unverified (ADR-0019 §Historical limitation lines 44-52). Reconstruction assessment (technical consistency from ADR-0019 §Technical assessment 34-42; repository/service contracts; schema/repository alignment; rollback coherence): the file aligns with governance contract (`RegulatoryReviewFlagRepository`, `RegulatoryGovernanceService`) and creates `regulatory_review_flags` with expected columns/indexes/constraints. No technical correction required. Historical authorization gap remains separate; must NOT be applied to hosted/prod until provenance/review authorization complete (ADR-0019 §Accountability 70-71; CURRENT_STATE.md §Migration 029 provenance: UNVERIFIED; XPORTA-V1-DEPLOYMENT.md §Migration procedure ends at 014, note at 550-557). If applied, must include explicit privileges grant for new `xportra_app` table (`GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES ON ALL TABLES IN SCHEMA xportra TO xportra_app;` applies only to existing tables; new table requires explicit grant per bootstrap-authorization-db-role.md line 44).
