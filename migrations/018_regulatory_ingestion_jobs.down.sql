BEGIN;

DROP TRIGGER IF EXISTS regulatory_ingestion_jobs_set_updated_at ON xportra.regulatory_ingestion_jobs;
DROP TABLE IF EXISTS xportra.regulatory_ingestion_jobs;

COMMIT;
