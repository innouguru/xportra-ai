BEGIN;
DROP TRIGGER IF EXISTS regulatory_artifact_legal_hold_set_updated_at ON xportra.regulatory_artifact_legal_hold;
DROP TABLE IF EXISTS xportra.regulatory_artifact_legal_hold;
COMMIT;
