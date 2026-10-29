-- Down migration 030: Revert published_at column and status constraint
--
-- Reverts the changes made by migration 030:
--   - Drops the CHECK constraint that includes 'published'
--   - Restores the original CHECK constraint (status IN ('extracted', 'rejected', 'archived'))
--   - Removes the published_at column
--
-- Note: This migration assumes no requirements have been published yet.
-- If any requirements have status 'published', the down migration will
-- fail because the restored CHECK constraint does not allow 'published'.

BEGIN;

-- Drop the updated CHECK constraint (includes 'published')
ALTER TABLE xportra.regulatory_requirements
    DROP CONSTRAINT IF EXISTS regulatory_requirements_status_check;

-- Restore the original CHECK constraint from migration 006
ALTER TABLE xportra.regulatory_requirements
    ADD CHECK (status IN ('extracted', 'rejected', 'archived'));

-- Remove the published_at column
ALTER TABLE xportra.regulatory_requirements
    DROP COLUMN IF EXISTS published_at;

COMMIT;