BEGIN;

DROP TRIGGER IF EXISTS regulatory_requirement_assessments_set_updated_at ON xportra.regulatory_requirement_assessments;
DROP TABLE IF EXISTS xportra.regulatory_requirement_assessments;

COMMIT;
