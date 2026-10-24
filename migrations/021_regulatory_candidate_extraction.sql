BEGIN;

-- Link each extracted candidate to the durable ingestion job that produced it,
-- preserving traceability from candidate -> artifact -> source -> job.
ALTER TABLE xportra.regulatory_requirements
    ADD COLUMN ingestion_job_id UUID
        REFERENCES xportra.regulatory_ingestion_jobs(id) ON DELETE SET NULL;

-- Record how each candidate was produced: succeeded / partial / failed / manual.
-- 'manual' marks candidates entered by an authorized reviewer after extraction
-- failure or partial extraction (never a substitute for verified extraction).
ALTER TABLE xportra.regulatory_requirements
    ADD COLUMN extraction_outcome TEXT NOT NULL DEFAULT 'succeeded'
        CHECK (extraction_outcome IN ('succeeded', 'partial', 'failed', 'manual'));

-- Extractor/parser version used to produce the candidate, for reproducibility
-- and re-review when the parser changes.
ALTER TABLE xportra.regulatory_requirements
    ADD COLUMN parser_version TEXT;

-- Flag candidates entered manually by an authorized reviewer (recovery path
-- after failed/partial extraction). Manual candidates pass the same Stage A
-- and Stage B gates as extracted candidates.
ALTER TABLE xportra.regulatory_requirements
    ADD COLUMN manual_entry BOOLEAN NOT NULL DEFAULT FALSE;

-- Reviewer attribution for manual entries and Stage A verification.
ALTER TABLE xportra.regulatory_requirements
    ADD COLUMN reviewer_user_id UUID
        REFERENCES xportra.users(id) ON DELETE SET NULL;

ALTER TABLE xportra.regulatory_requirements
    ADD COLUMN reviewed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS regulatory_requirements_ingestion_job_idx
    ON xportra.regulatory_requirements (ingestion_job_id);
CREATE INDEX IF NOT EXISTS regulatory_requirements_extraction_outcome_idx
    ON xportra.regulatory_requirements (extraction_outcome, status);
CREATE INDEX IF NOT EXISTS regulatory_requirements_reviewer_idx
    ON xportra.regulatory_requirements (reviewer_user_id)
    WHERE reviewer_user_id IS NOT NULL;

COMMIT;
