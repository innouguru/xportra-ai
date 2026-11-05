BEGIN;

ALTER TABLE xportra.regulatory_document_normalizations
    ADD CONSTRAINT regulatory_document_normalizations_identity_key
    UNIQUE (id, artifact_id, source_id);

ALTER TABLE xportra.regulatory_source_artifacts
    ADD CONSTRAINT regulatory_source_artifacts_identity_key
    UNIQUE (id, source_id, content_hash);

ALTER TABLE xportra.regulatory_source_artifacts
    ADD CONSTRAINT regulatory_source_artifacts_version_identity_key
    UNIQUE (id, source_id, content_hash, source_version);

ALTER TABLE xportra.regulatory_ingestion_jobs
    ADD CONSTRAINT regulatory_ingestion_jobs_identity_key
    UNIQUE (id, artifact_id, source_id);

ALTER TABLE xportra.regulatory_requirements
    ADD CONSTRAINT regulatory_requirements_document_identity_key
    UNIQUE (id, normalized_document_id);

CREATE TABLE xportra.regulatory_requirement_extraction_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    normalized_document_id UUID NOT NULL,
    artifact_id UUID NOT NULL,
    source_id UUID NOT NULL,
    ingestion_job_id UUID NOT NULL,
    artifact_content_hash TEXT NOT NULL,
    artifact_source_version TEXT,
    normalized_text_sha256 TEXT NOT NULL
        CHECK (normalized_text_sha256 ~ '^[0-9a-f]{64}$'),
    parser_version TEXT NOT NULL,
    extraction_method TEXT NOT NULL,
    extraction_version TEXT NOT NULL,
    prompt_version TEXT,
    configured_model_identifier TEXT,
    model_identifiers JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(model_identifiers) = 'array'),
    provider_names JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(provider_names) = 'array'),
    outcome TEXT NOT NULL
        CHECK (outcome IN ('succeeded', 'partial', 'failed')),
    failed_chunks JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(failed_chunks) = 'array'),
    rejected_candidate_count INTEGER NOT NULL DEFAULT 0
        CHECK (rejected_candidate_count >= 0),
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT regulatory_requirement_extraction_runs_identity_key
        UNIQUE (id, normalized_document_id),
    CONSTRAINT regulatory_requirement_extraction_runs_document_fk
        FOREIGN KEY (normalized_document_id, artifact_id, source_id)
        REFERENCES xportra.regulatory_document_normalizations
                   (id, artifact_id, source_id)
        ON DELETE RESTRICT,
    CONSTRAINT regulatory_requirement_extraction_runs_job_fk
        FOREIGN KEY (ingestion_job_id, artifact_id, source_id)
        REFERENCES xportra.regulatory_ingestion_jobs
                   (id, artifact_id, source_id)
        ON DELETE RESTRICT,
    CONSTRAINT regulatory_requirement_extraction_runs_artifact_fk
        FOREIGN KEY (artifact_id, source_id, artifact_content_hash)
        REFERENCES xportra.regulatory_source_artifacts
                   (id, source_id, content_hash)
        ON DELETE RESTRICT,
    CONSTRAINT regulatory_requirement_extraction_runs_artifact_version_fk
        FOREIGN KEY (artifact_id, source_id, artifact_content_hash,
                     artifact_source_version)
        REFERENCES xportra.regulatory_source_artifacts
                   (id, source_id, content_hash, source_version)
        ON DELETE RESTRICT
);

CREATE INDEX regulatory_requirement_extraction_runs_document_idx
    ON xportra.regulatory_requirement_extraction_runs
       (normalized_document_id, started_at, id);

CREATE INDEX regulatory_requirement_extraction_runs_job_idx
    ON xportra.regulatory_requirement_extraction_runs
       (ingestion_job_id, started_at, id);

CREATE TABLE xportra.regulatory_requirement_extraction_run_candidates (
    extraction_run_id UUID NOT NULL,
    normalized_document_id UUID NOT NULL,
    candidate_index INTEGER NOT NULL CHECK (candidate_index >= 0),
    candidate_id UUID,
    evidence_snapshot JSONB NOT NULL
        CHECK (jsonb_typeof(evidence_snapshot) = 'object'),
    resolution_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (resolution_status IN (
            'pending', 'persisted', 'reused', 'persistence_failed'
        )),
    is_origin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (extraction_run_id, candidate_index),
    CONSTRAINT regulatory_extraction_run_candidate_run_fk
        FOREIGN KEY (extraction_run_id, normalized_document_id)
        REFERENCES xportra.regulatory_requirement_extraction_runs
                   (id, normalized_document_id)
        ON DELETE RESTRICT,
    CONSTRAINT regulatory_extraction_run_candidate_candidate_fk
        FOREIGN KEY (candidate_id, normalized_document_id)
        REFERENCES xportra.regulatory_requirements
                   (id, normalized_document_id)
        ON DELETE RESTRICT,
    CONSTRAINT regulatory_extraction_run_candidate_resolution_check
        CHECK (
            (resolution_status IN ('persisted', 'reused')
                AND candidate_id IS NOT NULL)
            OR (resolution_status IN ('pending', 'persistence_failed')
                AND candidate_id IS NULL)
        ),
    CONSTRAINT regulatory_extraction_run_candidate_origin_check
        CHECK (NOT is_origin OR resolution_status = 'persisted')
);

CREATE UNIQUE INDEX regulatory_extraction_run_candidate_origin_idx
    ON xportra.regulatory_requirement_extraction_run_candidates(candidate_id)
    WHERE is_origin;

CREATE INDEX regulatory_extraction_run_candidate_candidate_idx
    ON xportra.regulatory_requirement_extraction_run_candidates
       (candidate_id, extraction_run_id)
    WHERE candidate_id IS NOT NULL;

CREATE FUNCTION xportra.regulatory_source_artifact_identity_immutable()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF ROW(
        NEW.source_id, NEW.artifact_uri, NEW.content_hash, NEW.content_length,
        NEW.content_type, NEW.acquisition_channel, NEW.acquired_by,
        NEW.acquired_at, NEW.source_version
    ) IS DISTINCT FROM ROW(
        OLD.source_id, OLD.artifact_uri, OLD.content_hash, OLD.content_length,
        OLD.content_type, OLD.acquisition_channel, OLD.acquired_by,
        OLD.acquired_at, OLD.source_version
    ) THEN
        RAISE EXCEPTION 'regulatory source artifact identity is immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER regulatory_source_artifacts_identity_immutable
    BEFORE UPDATE ON xportra.regulatory_source_artifacts
    FOR EACH ROW
    EXECUTE FUNCTION xportra.regulatory_source_artifact_identity_immutable();

CREATE FUNCTION xportra.regulatory_document_normalization_identity_immutable()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF ROW(
        NEW.artifact_id, NEW.source_id, NEW.document_title,
        NEW.normalized_text, NEW.normalized_content, NEW.content_type,
        NEW.parser_name, NEW.normalized_at
    ) IS DISTINCT FROM ROW(
        OLD.artifact_id, OLD.source_id, OLD.document_title,
        OLD.normalized_text, OLD.normalized_content, OLD.content_type,
        OLD.parser_name, OLD.normalized_at
    ) THEN
        RAISE EXCEPTION 'regulatory document normalization identity is immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER regulatory_document_normalizations_identity_immutable
    BEFORE UPDATE ON xportra.regulatory_document_normalizations
    FOR EACH ROW
    EXECUTE FUNCTION xportra.regulatory_document_normalization_identity_immutable();

CREATE FUNCTION xportra.regulatory_extraction_history_reject_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'regulatory extraction history is append-only';
END;
$$;

CREATE TRIGGER regulatory_requirement_extraction_runs_no_mutation
    BEFORE UPDATE OR DELETE
    ON xportra.regulatory_requirement_extraction_runs
    FOR EACH ROW
    EXECUTE FUNCTION xportra.regulatory_extraction_history_reject_mutation();

CREATE FUNCTION xportra.regulatory_extraction_run_candidate_resolve_once()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.resolution_status <> 'pending'
           OR NEW.candidate_id IS NOT NULL
           OR NEW.is_origin THEN
            RAISE EXCEPTION 'regulatory extraction evidence must start pending';
        END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE'
       OR OLD.resolution_status <> 'pending'
       OR NEW.extraction_run_id IS DISTINCT FROM OLD.extraction_run_id
       OR NEW.normalized_document_id IS DISTINCT FROM OLD.normalized_document_id
       OR NEW.candidate_index IS DISTINCT FROM OLD.candidate_index
       OR NEW.evidence_snapshot IS DISTINCT FROM OLD.evidence_snapshot
       OR NEW.created_at IS DISTINCT FROM OLD.created_at
       OR NEW.resolution_status NOT IN (
           'persisted', 'reused', 'persistence_failed'
       ) THEN
        RAISE EXCEPTION 'regulatory extraction evidence is immutable';
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER regulatory_requirement_extraction_run_candidates_resolve_once
    BEFORE INSERT OR UPDATE OR DELETE
    ON xportra.regulatory_requirement_extraction_run_candidates
    FOR EACH ROW
    EXECUTE FUNCTION xportra.regulatory_extraction_run_candidate_resolve_once();

COMMIT;
