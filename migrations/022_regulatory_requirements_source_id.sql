BEGIN;

-- Add source_id to regulatory_requirements for direct source traceability
-- without requiring a join through regulatory_document_normalizations.
ALTER TABLE xportra.regulatory_requirements
    ADD COLUMN source_id UUID
        REFERENCES xportra.regulatory_sources(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS regulatory_requirements_source_id_idx
    ON xportra.regulatory_requirements (source_id);

COMMIT;
