BEGIN;

DROP TRIGGER IF EXISTS regulatory_document_normalizations_set_updated_at ON xportra.regulatory_document_normalizations;
DROP TABLE IF EXISTS xportra.regulatory_document_normalizations;

COMMIT;
