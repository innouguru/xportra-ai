# ADR-0021: Regulatory Administration — Bounded Retry Control, Wording
# Correction, and Authorized Source Withdrawal

**Status:** Accepted

**Date:** 2026-10-31

**Context:** Phase 4D regulatory ingestion completion (milestones M1–M8,
REQUIREMENTS.md R-4D; phase-4d-regulatory-knowledge-administration.md;
ADR-0017 §Task directions; INVARIANTS.md rules 2, 6, 7, 8). The existing
implementation provided source registration, artifact intake, durable
PostgreSQL-backed ingestion jobs with a polling worker, Stage A/B review,
publication eligibility, supersession, and governance flags. Audit against
the actual repository state identified three missing administration
capabilities that the task assignment requires:

1. **Authorized retry/recovery control for terminally failed ingestion
   jobs (M4).** Automatic retries were unbounded: a persistently failing
   attempt was re-marked `retryable` on every failure, and no staff
   control could record a recovery attempt for a terminal `failed` job.
   Job attempt rows (`regulatory_ingestion_jobs.attempt_number`, unique
   per artifact) already model attempts; staff retry should reuse them,
   not introduce new infrastructure.

2. **Wording correction during candidate review (M5).** Reviewers could
   record Stage A decisions and rationale but had no traceable way to
   correct extracted wording. Invariant 6 forbids silently altering
   ingested content, so any correction must be recorded with the
   retained original text, the reviewer, and the rationale.

3. **Authorized source withdrawal (M7).** Supersession exists with
   governance flags, but there was no staff action to withdraw an
   obsolete/incorrect source while preserving history; withdrawn
   sources must stop eligibility automatically (existing rule).

## Decision

### 1. Bounded retries and staff retry control (M4)

- Additive migration 031: `retry_count INTEGER NOT NULL DEFAULT 0`
  (CHECK ≥ 0) on `xportra.regulatory_ingestion_jobs`.
- Each retryable failure increments `retry_count`; when a further
  failure would exceed `MAX_RETRY_ATTEMPTS = 5`, the failure is
  terminal (`status = 'failed'`). This makes the worker's bounded-retry
  contract operative without new infrastructure.
- A separately authorized staff control
  (`POST /regulatory/ingestion-jobs/{job_id}/retry`, active
  `GRANT_MANAGE`) records a NEW attempt row for the same artifact
  (`attempt_number` = next after the recorded maximum; bound checked
  before insertion; concurrent duplicates resolved idempotently via the
  existing `(artifact_id, attempt_number)` uniqueness). Prior attempts
  stay immutable history.
- Worker lease recovery was corrected to pass its timeout as a bound
  parameter (`make_interval(secs => %s)`), replacing malformed
  string-spliced SQL.

### 2. Wording correction (M5)

- Additive migration 032: append-only
  `xportra.regulatory_requirement_wording_corrections`
  (`id`, `requirement_id`, `original_text`, `corrected_text`,
  `rationale`, `reviewer_user_id`, `source_id`, timestamps) with
  update/delete rejection triggers, mirroring
  `regulatory_stage_a_reviews`.
- Corrections are performed as part of a Stage A decision
  (`POST .../stage-a` with optional `corrected_requirement_text`),
  require the `STAGE_A_VERIFY` grant, and are only permitted for the
  `verified` decision. The atomic Stage A transaction records the
  append-only correction row (original + corrected text, reviewer,
  rationale) and updates the operative `requirement_text`.
- A correction is refused when the candidate currently holds a Stage B
  approval: corrected wording requires fresh Stage B applicability
  approval before publication (fail-closed; prevents publishing
  wording Stage B never reviewed).
- `requirement_text` remains the operative exporter-facing wording;
  the pre-correction wording stays recoverable verbatim from the
  correction history. History is exposed read-only to authorized
  reviewers.
- This is a managed administration capability, not a general edit
  function: corrections are attribution-bearing, auditable, and cannot
  detach from the candidate's source/artifact provenance.

### 3. Authorized source withdrawal (M7)

- `POST /regulatory/sources/{source_id}/withdrawal` with an active
  `GRANT_MANAGE` grant and a mandatory rationale: sets source status to
  `withdrawn` (existing validated status), records governance flags
  (`trigger_type = 'withdrawal'`) for every requirement linked to the
  source, atomically, reusing `update_source_in_transaction` and
  `RegulatoryReviewFlagRepository`.
- Withdrawal preserves prior artifacts, candidate decisions, and
  history (no deletion); eligibility already treats non-`active`/
  non-`draft` sources as ineligible, so withdrawn material is never
  presented as currently verified and applicable.
- Re-activation is covered by source status semantics already in the
  intake service; withdrawal itself is one-way for this release
  (re-review flow governs recovery).

## Consequences and invariants

- No Docker, no paid queue, no infra changes; both mechanisms reuse the
  durable PostgreSQL jobs/tables and existing grant/audit authority.
- Existing global `GRANT_MANAGE` / `STAGE_A_VERIFY` / `STAGE_B_APPROVE`
  authorization unchanged; all new mutations fail closed.
- Oversight preserved: corrections do not bypass review gates; attempts
  preserve history; withdrawal attaches to the existing governance-flag
  re-review flow.
- R-4D criteria covered: 18 (survivable restart/retry), 20 (manual
  recovery candidates — handled in the same milestone batch via the
  eligibility fix), 7 (traceable wording), 9/13 (source change →
  re-review; withdrawal preserved history), 25 (state semantics).

**Linked:** `REQUIREMENTS.md` R-4D;
`docs/phases/phase-4d-regulatory-knowledge-administration.md`;
ADR-0017; ADR-0003; INVARIANTS.md.
