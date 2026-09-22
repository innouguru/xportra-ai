BEGIN;

CREATE TABLE IF NOT EXISTS xportra.regulatory_source_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID NOT NULL REFERENCES xportra.regulatory_sources(id) ON DELETE RESTRICT,
    artifact_uri TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content_length INTEGER NOT NULL CHECK (content_length > 0),
    content_type TEXT NOT NULL,
    acquisition_channel TEXT NOT NULL CHECK (acquisition_channel IN ('http_download', 'manual_upload', 'api_export', 'other')),
    acquired_by TEXT,
    acquired_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status TEXT NOT NULL CHECK (status IN ('validated', 'rejected', 'pending_review', 'archived')),
    source_version TEXT,
    validation_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS regulatory_source_artifacts_source_acquired_idx
    ON xportra.regulatory_source_artifacts (source_id, acquired_at, id);

CREATE INDEX IF NOT EXISTS regulatory_source_artifacts_status_idx
    ON xportra.regulatory_source_artifacts (status, acquired_at);

CREATE TRIGGER regulatory_source_artifacts_set_updated_at
    BEFORE UPDATE ON xportra.regulatory_source_artifacts
    FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

COMMIT;
