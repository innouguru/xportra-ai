BEGIN;

-- Add processing-stage tracking to regulatory ingestion jobs.
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
            'failed'
        ));

-- Record when the current processing stage was last updated.
ALTER TABLE xportra.regulatory_ingestion_jobs
    ADD COLUMN stage_updated_at TIMESTAMPTZ;

COMMIT;