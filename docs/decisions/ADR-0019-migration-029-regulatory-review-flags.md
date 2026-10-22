# ADR-0019: Migration 029 Engineering Disposition for Regulatory Review Flags

- **Status:** Technical consistency satisfactory; historical provenance unverified; blocked from production application until provenance or separately authorized reconstruction/review resolves the gap.
- **Date:** 2026-10-22
- **Linked:** `REQUIREMENTS.md` R-4D; `docs/phases/phase-4d-regulatory-knowledge-administration.md` (Task 7); ADR-0017; `docs/decisions/ADR-0003-source-authority-framework.md`.
- **Migration files:** `migrations/029_regulatory_review_flags.sql`, `.down.sql`.
- **Related repositories/services:** `RegulatoryReviewFlagRepository` (`xportra/persistence/repositories.py`); `RegulatoryGovernanceService` (`xportra/application/regulatory_governance_service.py`); `RegulatoryStageAReviewService` (`xportra/application/regulatory_stage_a_review_service.py`).
- **Related tests:** `tests/unit/test_regulatory_governance_service.py`, `tests/unit/test_regulatory_governance_postgresql.py`, `tests/unit/test_regulatory_stage_a_review.py`, `tests/unit/test_regulatory_source_intake.py`, integration tests (`test_regulatory_governance_postgresql.py`, `test_regulatory_stage_a_review_postgresql.py`, `test_assessment_regulatory_integration_postgresql.py`).
- **Current engineering fix:** `tests/unit/test_regulatory_stage_a_review.py` fixture isolation corrected (`DatabaseSettings` + `connection()` override) — commit `3070d4d`. No production behavior changed.

## Context

The repository includes `migrations/029_regulatory_review_flags.sql` (untracked in Git; no commit provenance in `main` branch or any branch; `git reflog` shows no entry referencing it by name; `git rev-list --objects --all --` returns only file-object hashes without authoritative commit linkage; `git status` shows `??` untracked status for both `.sql` and `.down.sql`).

The file's content creates a governance-tracking table (`regulatory_review_flags`) that supports supersession, version change, material change, stale-source tracking, and withdrawal-triggered re-review. The rollback (`DROP TABLE IF EXISTS`) is coherent. The schema aligns with the application's current repositories (`RegulatoryReviewFlagRepository`), governance service (`RegulatoryGovernanceService`), stage-review services (`RegulatoryStageAReviewService`), and supported tests.

A previous read-only provenance investigation (`docs/decisions/ADR-0018-storage-technology-decision.md`; `tasks/completed/production-deployment-readiness-audit-render.md`; `CURRENT_STATE.md` §Phase 4D.12–4D.14) confirmed that no authoritative historical authorization or provenance record exists for migration 029. The file was not included in the commit `7a65e120b...` whose message references regulatory PDF parsing (`git show --stat --format=fuller 7a65e120b...` does not list `migrations/029_regulatory_review_flags.sql`).

## Requirement evidence

The governance mechanism is explicitly required by the approved regulatory-knowledge-administration plan (`REQUIREMENTS.md` R-4D; `docs/phases/phase-4d-regulatory-knowledge-administration.md` §Task 7):

- Source/version supersession and material change must be tracked explicitly (not inferred from timestamps) to prevent superseded material from being treated as current.
- Stale or withdrawn sources must be restricted from current applicable use until independent Stage A verification and Stage B applicability approval confirm renewed validity.
- Governance-flag events (`pending_review`, `review_completed`, `dismissed`) must be auditable and linked to sources, requirements, actors, and rationales.
- Re-publication after supersession or version change requires renewed Stage A and Stage B decisions that post-date the governance trigger.

The technology baseline (`docs/architecture/technology-baseline.md`) distinguishes source authority from source freshness and requires explicit tracking of status, supersession, effective dates, and withdrawal. The source-authority framework (`ADR-0003`) mandates that superseded or stale sources do not silently remain current.

The governance service (`regulatory_governance_service.py`) relies on `RegulatoryReviewFlagRepository` to enforce these rules: pending flags prevent `complete_review` unless `stage_a_status == "verified"` and `stage_b_status == "approved"` occur after the flag's creation timestamp. Without the table, the repository would fail (`list_pending_for_source` would raise `RuntimeError` or `ApplicationNotFoundError` depending on the database state) and the governance contract would be broken.

## Technical consistency findings

Static inspection of `migrations/029_regulatory_review_flags.sql` and `migrations/029_regulatory_review_flags.down.sql` shows:

- Forward migration creates the `xportra.regulatory_review_flags` table with the exact columns, types, nullability, and defaults that the repository and service expect (`id`, `requirement_id`, `trigger_source_id`, `trigger_type`, `status`, `actor_user_id`, `rationale`, `created_at`, `updated_at`).
- Constraints match repository expectations (`CHECK` for `trigger_type` values; `CHECK` for `status` values; `ON DELETE SET NULL` for foreign keys; `DEFAULT` for timestamps; `NOT NULL` where required by service validation).
- Indexes (`WHERE` clauses for partial indexes) align with repository query patterns (`list_pending_for_source`, `get_for_requirement`, `get_for_source`, `get_by_id`).
- The rollback (`DROP TABLE IF EXISTS`) cleanly removes all objects and does not break dependencies (other migrations 001–028 do not reference this table; the governance service constructs its repository lazily and does not assume the table exists at startup unless the service is invoked).
- The migration introduces no schema-level conflicts with existing migrations (no duplicate table names, no conflicting column types, no overlapping sequence or trigger names).

No technical defect was identified in the SQL or its relationship to the current application code.

## Historical limitation

- The file has no authoritative commit provenance (`git log --all --full-history -- migrations/029_regulatory_review_flags.sql` produces no commit message; `git rev-list --objects --all --` returns only object hashes without commit linkage; `git ls-tree -r 7a65e120b...` does not include the file; the file is untracked — `git status` reports `??`).
- The commit message of the commit where `git show` associates the file (`Add bounded regulatory PDF parsing`) does not reference regulatory review flags, governance, supersession, or freshness tracking.
- No ADR (`docs/decisions/ADR-0019-Regulatory...`) previously records the decision to introduce this migration.
- No product-owner approval record or independent review record linking this specific file to its intended governance function has been found.

This is a provenance gap, not proof that the file is unnecessary, incorrect, or malicious. The current engineering assessment is that the file's content aligns with the established requirements, architecture, and application contracts; however, the repository does not contain authoritative historical authorization for it.

## Technical dependency verification

The repository's `RegulatoryReviewFlagRepository` (`repositories.py` line 2532+) creates, reads, updates, and deletes records through the exact schema defined by the migration. The governance service creates flags (`flag_review_required`) with validated `trigger_type`, verifies source existence, validates rationale, and links optional requirements. It completes reviews (`complete_review`) only when the linked requirement has verified (`verified`) Stage A status and approved (`approved`) Stage B status that post-date the governance flag's `created_at`. It exposes `get_flags_for_source`, `get_flags_for_requirement`, `list_pending_for_source`, and reads via `get_by_id`. These behaviors depend on the table and its indexes to function correctly and to enforce the governance contract (fail-closed on missing flags or unresolved requirements).

Without the table, the repository would either fail at database connection time (if a `connection()` call tries to query a missing table) or at query execution time (if the query references a nonexistent table). The governance contract requires the table's existence; the service does not implement a graceful fallback for missing governance state because the design explicitly requires durable audit and restriction.

## Current engineering decision

The current engineering disposition, based on the established requirements, architecture, code contracts, and safe local verification, is that the migration is functionally appropriate and technically consistent with the application's governance needs. The historical authorization gap remains separate from the technical assessment and must be resolved through an authorized review process (either verification of the provenance, or a separately documented reconstruction/review with independent technical verification and an ADR record) before any production application.

This ADR records the current technical assessment and the explicit operational boundary: the migration is not claimed as historically authorized, and it remains blocked from any hosted or production database until provenance or a separately authorized reconstruction/review resolves the gap.

## Accountability and operational boundary

- Functional assessment: based on `REQUIREMENTS.md` R-4D, `docs/phases/phase-4d-regulatory-knowledge-administration.md` (§Task 7: supersession/review/stale/withdrawal tracking; re-publication requires current Stage A and Stage B; old artifacts/history preserved), `docs/decisions/ADR-0017-regulatory-knowledge-administration.md` (§Task 7), `docs/decisions/ADR-0003-source-authority-framework.md` (freshness/supersession tracking independent of authority), and `docs/architecture/technology-baseline.md`.
- Technical assessment: based on `migrations/029_regulatory_review_flags.sql` and `.down.sql` (static inspection); `RegulatoryReviewFlagRepository` (`repositories.py`); `RegulatoryGovernanceService` (`xportra/application/regulatory_governance_service.py`); `RegulatoryStageAReviewService` (`xportra/application/regulatory_stage_a_review_service.py`); existing governance/regulatory tests (`tests/unit/test_regulatory_governance_service.py`, `tests/unit/test_regulatory_governance_postgresql.py`, `tests/unit/test_regulatory_stage_a_review.py`, `tests/unit/test_regulatory_stage_b_review.py`, `tests/unit/test_regulatory_source_intake.py`, `tests/unit/test_regulatory_index_demo.py`, `tests/unit/test_regulatory_candidate_extraction.py`, `tests/unit/test_assessment_regulatory_integration.py`, integration tests `test_regulatory_governance_postgresql.py`, `test_regulatory_stage_a_review_postgresql.py`, `test_regulatory_stage_b_review_postgresql.py`, `test_assessment_regulatory_integration_postgresql.py`).
- Provenance assessment: based on `git log --all --full-history --`, `git reflog --all`, `git ls-tree -r`, `git rev-list --objects --all --`, `git status`, and absence of ADR/provenance documentation. The gap is documented explicitly; no historical authorization is claimed.
- Current decision: the current engineering assessment supports the migration's technical inclusion and documentation, but its application to any hosted or production database requires a separately authorized provenance review or reconstruction/review process.
- No production application, live smoke test, database write, migration execution, or schema change was performed as part of this assessment.

## References

- `migrations/029_regulatory_review_flags.sql`
- `migrations/029_regulatory_review_flags.down.sql`
- `REQUIREMENTS.md` (§R-4D)
- `docs/phases/phase-4d-regulatory-knowledge-administration.md` (§Task 7, §Task 3)
- `docs/decisions/ADR-0017-regulatory-knowledge-administration.md`
- `docs/decisions/ADR-0003-source-authority-framework.md`
- `docs/decisions/ADR-0018-storage-technology-decision.md` (§Task 3B authorization boundary, §Migration prerequisites)
- `xportra/persistence/repositories.py` (`RegulatoryReviewFlagRepository`)
- `xportra/application/regulatory_governance_service.py`
- `xportra/application/regulatory_stage_a_review_service.py`
- Related governance/test files listed above.
