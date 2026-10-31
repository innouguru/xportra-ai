BEGIN;

-- ADR-0022: registration ingestion jobs are created for a source before
-- any artifact exists (Phase 4D.10 Task 3B contract). Making artifact_id
-- nullable is additive and does not change artifact-bound job semantics.

ALTER TABLE xportra.regulatory_ingestion_jobs
    ALTER COLUMN artifact_id DROP NOT NULL;

COMMIT;
