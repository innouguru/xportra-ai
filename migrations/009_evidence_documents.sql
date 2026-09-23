BEGIN;

CREATE TABLE IF NOT EXISTS xportra.evidence_documents (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES xportra.tenants(id) ON DELETE RESTRICT,
    title TEXT NOT NULL CHECK (char_length(btrim(title)) > 0),
    content TEXT NOT NULL CHECK (char_length(btrim(content)) > 0),
    source_type TEXT NOT NULL
        CHECK (source_type IN ('regulation', 'guidance', 'certificate', 'policy', 'other')),
    source_id TEXT NOT NULL CHECK (char_length(btrim(source_id)) > 0),
    source_location TEXT,
    jurisdiction TEXT,
    document_version TEXT,
    effective_date DATE,
    retrieved_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('active', 'inactive')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    content_fingerprint TEXT NOT NULL CHECK (char_length(btrim(content_fingerprint)) > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT evidence_documents_identity_key
        UNIQUE (tenant_id, source_id, document_version)
);

CREATE INDEX IF NOT EXISTS evidence_documents_tenant_idx
    ON xportra.evidence_documents (tenant_id, created_at, id);

CREATE INDEX IF NOT EXISTS evidence_documents_source_idx
    ON xportra.evidence_documents (tenant_id, source_id, document_version);

CREATE TRIGGER evidence_documents_set_updated_at
    BEFORE UPDATE ON xportra.evidence_documents
    FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

COMMIT;
