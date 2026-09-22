BEGIN;

CREATE TABLE IF NOT EXISTS xportra.regulatory_requirements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    normalized_document_id UUID NOT NULL
        REFERENCES xportra.regulatory_document_normalizations(id) ON DELETE RESTRICT,
    requirement_text TEXT NOT NULL,
    requirement_type TEXT NOT NULL CHECK (
        requirement_type IN (
            'obligation', 'prohibition', 'documentation', 'procedure',
            'threshold', 'inspection', 'certification', 'labeling',
            'recordkeeping', 'notification', 'unknown'
        )
    ),
    source_location JSONB NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    actor TEXT,
    condition_metadata JSONB,
    status TEXT NOT NULL CHECK (status IN ('extracted', 'rejected', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT regulatory_requirements_document_position_key
        UNIQUE (normalized_document_id, position)
);

CREATE INDEX IF NOT EXISTS regulatory_requirements_document_position_idx
    ON xportra.regulatory_requirements (normalized_document_id, position);

CREATE INDEX IF NOT EXISTS regulatory_requirements_type_status_idx
    ON xportra.regulatory_requirements (requirement_type, status, created_at);

CREATE TRIGGER regulatory_requirements_set_updated_at
    BEFORE UPDATE ON xportra.regulatory_requirements
    FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

COMMIT;
