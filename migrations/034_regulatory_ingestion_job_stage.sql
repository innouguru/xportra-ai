BEGIN;

-- Migration 034: ingestion job processing stage tracking.
--
-- Adds ``current_stage`` and ``stage_updated_at`` columns to
-- ``regulatory_ingestion_jobs`` so that the worker can persist
-- genuine processing progress and the dashboard can display it.
-- Both columns are nullable and have no default for existing records
-- (backward compatible — they remain NULL until a worker sets them).

ALTER TABLE xportra.regulatory_ingestion_jobs
    ADD COLUMN current_stage TEXT
        CHECK (current_stage IS NULL OR current_stage IN (
            'queued',
            'retrieving_artifact',
            'validating_document',
            'extracting_text',
            'normalizing_content',
            'extracting_requirements',
            'saving_candidates',
            'completed',
            'failed',
        ));

ALTER TABLE xportra.regulatory_ingestion_jobs
    ADD COLUMN stage_updated_at TIMESTAMPTZ;

COMMIT;