# ADR-0022: Registration Ingestion Jobs Are Artifact-Optional

**Status:** Accepted

**Date:** 2026-10-31

**Context:** Phase 4D regulatory ingestion completion (milestones M1–M8,
REQUIREMENTS.md R-4D; ADR-0021; INVARIANTS.md rules 2, 8). The intake
service contract (Phase 4D.10 Task 3B) requires
`RegulatorySourceIntakeService.register_source` to create a durable
pending ingestion job for the newly registered source *before any
artifact exists* (`artifact_id=None`). However, migration 018 declared
`xportra.regulatory_ingestion_jobs.artifact_id` as `NOT NULL`, so the
insertion always failed with a `NotNullViolation` wrapped as
`PersistenceIntegrityError`. Source registration was therefore
unreachable against any real database (only unit tests with fake
repositories passed). The E2E workflow suite (M8) exposed this defect.

Alternatives considered:

- *Drop the registration job* — forbidden: it is an approved contract
  (Task 3B) and removing behaviour is not an option.
- *Insert a placeholder artifact* — worse: fabricate
  non-provenanced artifacts, violating the provenance invariants.

## Decision

- Additive migration 033: `ALTER COLUMN artifact_id DROP NOT NULL` on
  `xportra.regulatory_ingestion_jobs`. Registration jobs carry no
  artifact; artifact-bound jobs retain the existing
  `(artifact_id, attempt_number)` uniqueness and attempt accounting.
- The repository `create` accepts the legacy `status` keyword but
  rejects any value other than `'pending'` — jobs are always created in
  the pending state.
- No other job semantics change: extraction, retry, worker lease, and
  publication provenance checks continue to operate on artifact-bound
  jobs (an artifact-NULL job can never satisfy a candidate's extraction
  provenance, because candidates are bound to artifact-backed jobs).

## Consequences

- Source registration works end-to-end on real databases.
- Trades one nullable column for correct contract behaviour; the
  uniqueness constraint and append-only audit trail are unchanged.
- The E2E suite (`tests/integration/`) re-verifies this path on every
  future run.
