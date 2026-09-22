BEGIN;

DROP TRIGGER IF EXISTS regulatory_requirement_applicability_set_updated_at ON xportra.regulatory_requirement_applicability;
DROP TABLE IF EXISTS xportra.regulatory_requirement_applicability;

COMMIT;
