BEGIN;

-- Restore NOT NULL; requires registration jobs (artifact_id IS NULL)
-- to be deleted first.

DELETE FROM xportra.regulatory_ingestion_jobs
WHERE artifact_id IS NULL;

ALTER TABLE xportra.regulatory_ingestion_jobs
    ALTER COLUMN artifact_id SET NOT NULL;

COMMIT;
