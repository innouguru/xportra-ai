BEGIN;

CREATE TABLE IF NOT EXISTS xportra.regulatory_ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES xportra.regulatory_source_artifacts(id) ON DELETE RESTRICT,
    source_id UUID NOT NULL REFERENCES xportra.regulatory_sources(id) ON DELETE RESTRICT,
    status TEXT NOT NULL CHECK (status IN ('pending','claimed','processing','completed','failed','retryable')),
    attempt_number INTEGER NOT NULL DEFAULT 1 CHECK (attempt_number > 0),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_details TEXT,
    parser_version TEXT NOT NULL DEFAULT 'v1',
    actor_user_id UUID REFERENCES xportra.users(id) ON DELETE SET NULL,
    audit_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT regulatory_ingestion_jobs_artifact_attempt_unique UNIQUE (artifact_id, attempt_number)
);

CREATE INDEX IF NOT EXISTS regulatory_ingestion_jobs_artifact_attempt_idx
    ON xportra.regulatory_ingestion_jobs (artifact_id, attempt_number);

CREATE INDEX IF NOT EXISTS regulatory_ingestion_jobs_status_created_idx
    ON xportra.regulatory_ingestion_jobs (status, created_at);

CREATE INDEX IF NOT EXISTS regulatory_ingestion_jobs_source_status_idx
    ON xportra.regulatory_ingestion_jobs (source_id, status);

CREATE INDEX IF NOT EXISTS regulatory_ingestion_jobs_actor_idx
    ON xportra.regulatory_ingestion_jobs (actor_user_id) WHERE actor_user_id IS NOT NULL;

CREATE TRIGGER regulatory_ingestion_jobs_set_updated_at
    BEFORE UPDATE ON xportra.regulatory_ingestion_jobs
    FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

COMMIT;
