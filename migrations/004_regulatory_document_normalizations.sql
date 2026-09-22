BEGIN;

CREATE TABLE IF NOT EXISTS xportra.regulatory_document_normalizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES xportra.regulatory_source_artifacts(id) ON DELETE RESTRICT,
    source_id UUID NOT NULL REFERENCES xportra.regulatory_sources(id) ON DELETE RESTRICT,
    document_title TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    normalized_content JSONB NOT NULL,
    content_type TEXT NOT NULL,
    parser_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('normalized', 'failed', 'rejected')),
    normalized_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT regulatory_document_normalizations_artifact_unique UNIQUE (artifact_id)
);

CREATE INDEX IF NOT EXISTS regulatory_document_normalizations_source_status_idx
    ON xportra.regulatory_document_normalizations (source_id, status, normalized_at);

CREATE INDEX IF NOT EXISTS regulatory_document_normalizations_artifact_idx
    ON xportra.regulatory_document_normalizations (artifact_id, source_id);

CREATE TRIGGER regulatory_document_normalizations_set_updated_at
    BEFORE UPDATE ON xportra.regulatory_document_normalizations
    FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

COMMIT;
