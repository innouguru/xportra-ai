BEGIN;

CREATE TABLE IF NOT EXISTS xportra.regulatory_document_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    normalized_document_id UUID NOT NULL
        REFERENCES xportra.regulatory_document_normalizations(id) ON DELETE RESTRICT,
    document_title TEXT,
    authority_name TEXT,
    document_type TEXT,
    classification TEXT NOT NULL CHECK (
        classification IN ('regulation', 'standard', 'guideline', 'procedure', 'notice', 'form', 'unknown')
    ),
    publication_date DATE,
    effective_date DATE,
    reference_identifier TEXT,
    version TEXT,
    jurisdiction TEXT,
    language TEXT,
    sections JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('extracted', 'failed', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT regulatory_document_metadata_document_unique UNIQUE (normalized_document_id)
);

CREATE INDEX IF NOT EXISTS regulatory_document_metadata_classification_idx
    ON xportra.regulatory_document_metadata (classification, status, created_at);

CREATE INDEX IF NOT EXISTS regulatory_document_metadata_reference_idx
    ON xportra.regulatory_document_metadata (reference_identifier)
    WHERE reference_identifier IS NOT NULL;

CREATE TRIGGER regulatory_document_metadata_set_updated_at
    BEFORE UPDATE ON xportra.regulatory_document_metadata
    FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

COMMIT;
