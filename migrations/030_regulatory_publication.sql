BEGIN;

-- Add published_at column to existing regulatory_requirements table
ALTER TABLE xportra.regulatory_requirements
    ADD COLUMN published_at TIMESTAMPTZ NULL;

-- Update the status CHECK constraint to include 'published'
ALTER TABLE xportra.regulatory_requirements
    ADD CHECK (status IN ('extracted', 'rejected', 'archived', 'published'));

COMMIT;