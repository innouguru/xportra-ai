-- Down migration for 031: remove the bounded-retry counter column.

BEGIN;

ALTER TABLE xportra.regulatory_ingestion_jobs
    DROP COLUMN IF EXISTS retry_count;

COMMIT;
