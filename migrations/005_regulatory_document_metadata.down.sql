BEGIN;

DROP TRIGGER IF EXISTS regulatory_document_metadata_set_updated_at ON xportra.regulatory_document_metadata;
DROP TABLE IF EXISTS xportra.regulatory_document_metadata;

COMMIT;
