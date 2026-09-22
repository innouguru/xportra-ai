BEGIN;

DROP TRIGGER IF EXISTS regulatory_requirements_set_updated_at ON xportra.regulatory_requirements;
DROP TABLE IF EXISTS xportra.regulatory_requirements;

COMMIT;
