BEGIN;

DROP TRIGGER IF EXISTS regulatory_source_artifacts_set_updated_at ON xportra.regulatory_source_artifacts;
DROP TABLE IF EXISTS xportra.regulatory_source_artifacts;

COMMIT;
