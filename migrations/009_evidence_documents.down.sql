BEGIN;

DROP TRIGGER IF EXISTS evidence_documents_set_updated_at ON xportra.evidence_documents;
DROP TABLE IF EXISTS xportra.evidence_documents;

COMMIT;
