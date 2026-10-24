=== Migration 029 Reconstruction Note (ADR-0020) ===
Status: Provenance unverified (`??` untracked; `git status` shows untracked; `git log --all --full-history --` shows no commit linkage; previous read-only inspection confirmed no authoritative authorization; no ADR previously records decision; no product-owner approval record linking file to governance function). Technical assessment (ADR-0019 §Technical consistency 34-42; repository/services alignment; schema/repository contract; rollback coherence; no dependency conflicts) supports inclusion. Historical authorization gap remains separate. Must NOT be applied to hosted/prod until separately authorized provenance/review/reconstruction authorization resolves gap (ADR-0019 §Accountability 70-72; CURRENT_STATE.md §Migration 029 provenance: UNVERIFIED; XPORTA-V1-DEPLOYMENT.md §Migration list ends at 014 with 029 blocked note 550-557).

Reference: docs/decisions/ADR-0019-migration-029-regulatory-review-flags.md (§Status 3, §Technical assessment 34-42, §Accountability 70-72); migrations/029_regulatory_review_flags.sql / .down.sql; xportra/persistence/repositories.py (`RegulatoryReviewFlagRepository` lines 2532-2623); xportra/application/regulatory_governance_service.py; xportra/application/regulatory_stage_a_review_service.py; docs/phases/phase-4d-regulatory-knowledge-administration.md (§Task 7); docs/decisions/ADR-0017-regulatory-knowledge-administration.md (§Task 7); docs/decisions/ADR-0003-source-authority-framework.md.

--- Reconstructed Purpose ---
Migration 029 creates `xportra.regulatory_review_flags` to support the approved regulatory-knowledge-administration governance contract (REQUIREMENTS.md R-4D; phase-4d-regulatory-knowledge-administration.md §Task 7; ADR-0017 §Task 7; ADR-0003):
- Track explicit governance triggers (supersession, version_change, material_change, stale, withdrawal) rather than inferring freshness from timestamps.
- Prevent superseded or stale sources from being treated as current until independent Stage A verification (`verified`) and Stage B applicability approval (`approved`) occur after the governance flag's `created_at`.
- Link governance flags to regulatory requirements (`requirement_id`) and regulatory sources (`trigger_source_id`) for audit and restriction.
- Provide auditable, append-only governance events (`pending_review`, `review_completed`, `dismissed`) with actor attribution, rationale, and timestamp linkage.
- Support re-publication requirements: supersession/version-change requires renewed Stage A + Stage B decisions that post-date the governance trigger.

--- Technical Consistency Confirmed (No Corrections Needed) ---
From ADR-0019 §Technical assessment 34-42 and static inspection:
- Forward migration (`029_regulatory_review_flags.sql`) creates table with exact columns/types/defaults/nullability expected by `RegulatoryReviewFlagRepository` (`repositories.py` lines 2536-2622): `id`, `requirement_id`, `trigger_source_id`, `trigger_type`, `status`, `actor_user_id`, `rationale`, `created_at`, `updated_at`. Constraints match repository validation (`CHECK` values for `trigger_type` and `status`; `ON DELETE SET NULL` for foreign keys; `NOT NULL` for required fields; `DEFAULT` for timestamps/status).
- Partial indexes (`WHERE` clauses) align with repository query patterns (`list_pending_for_source`, `get_for_requirement`, `get_for_source`, `get_by_id`).
- Rollback (`029_regulatory_review_flags.down.sql`) is coherent (`DROP TABLE IF EXISTS`); no dependency conflicts (other migrations 001-028 do not reference this table; repository constructs lazily and does not assume table at startup unless service invoked); governance service does not implement graceful fallback because design requires durable governance tracking (ADR-0019 §Historical limitation 55-57).
- No schema-level conflicts: no duplicate table names, no conflicting column types, no overlapping sequence/index/trigger names.
- No application-level security defects: authorization mechanism remains sound; authorization/bootstrap prerequisites remain unresolved independently; governance table absence does not weaken authorization boundary.

--- Required Privilege Update (If Applied) ---
If migration 029 is applied to hosted/prod after authorization/reconstruction authorization, explicit table grants must be granted to `xportra_app` (or whatever runtime role is configured) because `GRANT ... ON ALL TABLES IN SCHEMA xportra` applies only to existing tables at time of grant (bootstrap-authorization-db-role.md line 44; checklist section 1). The exact additional SQL:
```sql
GRANT SELECT, INSERT, UPDATE, DELETE, REFERENCES ON ALL TABLES IN SCHEMA xportra TO xportra_app;
```
If `xportra_app` does not exist (e.g., `postgres` superuser intended as application role with documented justification), this grant applies to the application user accordingly.

--- Reconstruction Record ---
Status: Technical assessment supports inclusion (ADR-0019 §Current engineering decision 59-63); historical authorization gap remains separate (ADR-0019 §Accountability 70-72); must NOT be applied to hosted/prod until provenance or separately authorized reconstruction/review authorization resolves gap.
Reconstruction performed: Inspected migration content; verified repository/service alignment (`RegulatoryReviewFlagRepository`, `RegulatoryGovernanceService`, `RegulatoryStageAReviewService`); verified schema/repository/test contracts (`tests/unit/test_regulatory_governance_service.py`, `tests/unit/test_regulatory_governance_postgresql.py`, etc.); confirmed rollback coherence; confirmed no dependency conflicts; confirmed no code corrections needed; confirmed privilege grant requirement for future table.
No original provenance verified; no claim of historical authorization made; reconstruction documented explicitly.
No hosted/prod database modified; no SQL executed against hosted DB; `.env` untouched; unrelated working-tree preserved; nothing committed/pushed.
