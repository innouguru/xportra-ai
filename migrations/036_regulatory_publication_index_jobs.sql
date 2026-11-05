BEGIN;

CREATE TABLE xportra.regulatory_publication_index_jobs (
    requirement_id UUID PRIMARY KEY
        REFERENCES xportra.regulatory_requirements(id) ON DELETE RESTRICT,
    desired_state TEXT NOT NULL
        CHECK (desired_state IN ('published', 'removed')),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN (
            'pending', 'processing', 'retryable', 'indexed', 'removed',
            'failed'
        )),
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    claim_token UUID,
    lease_expires_at TIMESTAMPTZ,
    indexed_chunk_ids UUID[] NOT NULL DEFAULT '{}',
    publication_fingerprint TEXT,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT regulatory_publication_index_job_claim_check
        CHECK (
            (status = 'processing'
                AND claim_token IS NOT NULL
                AND lease_expires_at IS NOT NULL)
            OR (status <> 'processing'
                AND claim_token IS NULL
                AND lease_expires_at IS NULL)
        )
);

CREATE INDEX regulatory_publication_index_jobs_poll_idx
    ON xportra.regulatory_publication_index_jobs
       (status, next_attempt_at, created_at);

CREATE INDEX regulatory_publication_index_jobs_lease_idx
    ON xportra.regulatory_publication_index_jobs
       (lease_expires_at)
    WHERE status = 'processing';

CREATE FUNCTION xportra.refresh_regulatory_publication_index_job(
    target_requirement_id UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    currently_eligible BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM xportra.regulatory_requirements AS r
        JOIN xportra.regulatory_sources AS s ON s.id = r.source_id
        WHERE r.id = target_requirement_id
          AND r.status = 'published'
          AND r.stage_a_status = 'verified'
          AND r.stage_b_status = 'approved'
          AND s.status = 'active'
          AND NOT EXISTS (
              SELECT 1
              FROM xportra.regulatory_review_flags AS f
              WHERE f.status = 'pending_review'
                AND (
                    f.requirement_id = r.id
                    OR f.trigger_source_id = r.source_id
                )
          )
    ) INTO currently_eligible;

    IF currently_eligible THEN
        INSERT INTO xportra.regulatory_publication_index_jobs (
            requirement_id, desired_state, status, attempt_count,
            next_attempt_at, claim_token, lease_expires_at, last_error,
            updated_at
        )
        VALUES (
            target_requirement_id, 'published', 'pending', 0,
            now(), NULL, NULL, NULL, now()
        )
        ON CONFLICT (requirement_id) DO UPDATE
        SET desired_state = 'published',
            status = 'pending',
            attempt_count = 0,
            next_attempt_at = now(),
            claim_token = NULL,
            lease_expires_at = NULL,
            last_error = NULL,
            updated_at = now();
    ELSE
        UPDATE xportra.regulatory_publication_index_jobs
        SET desired_state = 'removed',
            status = 'pending',
            attempt_count = 0,
            next_attempt_at = now(),
            claim_token = NULL,
            lease_expires_at = NULL,
            last_error = NULL,
            updated_at = now()
        WHERE requirement_id = target_requirement_id;
    END IF;
END;
$$;

CREATE FUNCTION xportra.regulatory_requirement_publication_index_changed()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM xportra.refresh_regulatory_publication_index_job(NEW.id);
    RETURN NEW;
END;
$$;

CREATE TRIGGER regulatory_requirement_publication_index_changed
    AFTER INSERT OR UPDATE OF
        status, requirement_text, source_id, normalized_document_id,
        source_location, position, parser_version, stage_a_status,
        stage_b_status
    ON xportra.regulatory_requirements
    FOR EACH ROW
    EXECUTE FUNCTION
        xportra.regulatory_requirement_publication_index_changed();

CREATE FUNCTION xportra.regulatory_source_publication_index_changed()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    affected_requirement RECORD;
BEGIN
    FOR affected_requirement IN
        SELECT id
        FROM xportra.regulatory_requirements
        WHERE source_id = NEW.id
    LOOP
        PERFORM xportra.refresh_regulatory_publication_index_job(
            affected_requirement.id);
    END LOOP;
    RETURN NEW;
END;
$$;

CREATE TRIGGER regulatory_source_publication_index_changed
    AFTER UPDATE OF status, title, version, jurisdiction
    ON xportra.regulatory_sources
    FOR EACH ROW
    EXECUTE FUNCTION
        xportra.regulatory_source_publication_index_changed();

CREATE FUNCTION xportra.regulatory_review_flag_publication_index_changed()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    affected_requirement_id UUID;
    affected_source_id UUID;
BEGIN
    IF TG_OP <> 'INSERT' THEN
        affected_requirement_id := OLD.requirement_id;
        affected_source_id := OLD.trigger_source_id;
        IF affected_requirement_id IS NOT NULL THEN
            PERFORM xportra.refresh_regulatory_publication_index_job(
                affected_requirement_id);
        END IF;
        IF affected_source_id IS NOT NULL THEN
            PERFORM xportra.refresh_regulatory_publication_index_job(id)
            FROM xportra.regulatory_requirements
            WHERE source_id = affected_source_id;
        END IF;
    END IF;

    IF TG_OP <> 'DELETE' THEN
        affected_requirement_id := NEW.requirement_id;
        affected_source_id := NEW.trigger_source_id;
        IF affected_requirement_id IS NOT NULL THEN
            PERFORM xportra.refresh_regulatory_publication_index_job(
                affected_requirement_id);
        END IF;
        IF affected_source_id IS NOT NULL THEN
            PERFORM xportra.refresh_regulatory_publication_index_job(id)
            FROM xportra.regulatory_requirements
            WHERE source_id = affected_source_id;
        END IF;
        RETURN NEW;
    END IF;

    RETURN OLD;
END;
$$;

CREATE TRIGGER regulatory_review_flag_publication_index_changed
    AFTER INSERT OR UPDATE OF
        requirement_id, trigger_source_id, status
    OR DELETE
    ON xportra.regulatory_review_flags
    FOR EACH ROW
    EXECUTE FUNCTION
        xportra.regulatory_review_flag_publication_index_changed();

DO $$
DECLARE
    published_requirement RECORD;
BEGIN
    FOR published_requirement IN
        SELECT id
        FROM xportra.regulatory_requirements
        WHERE status = 'published'
    LOOP
        PERFORM xportra.refresh_regulatory_publication_index_job(
            published_requirement.id);
    END LOOP;
END;
$$;

COMMIT;
