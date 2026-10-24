BEGIN;

-- Append-only record of Stage A review decisions. Each row is one review
-- event; prior decisions are never overwritten. This preserves the auditable
-- history of who verified/rejected/clarified each candidate and why.
CREATE TABLE IF NOT EXISTS xportra.regulatory_stage_a_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requirement_id UUID NOT NULL REFERENCES xportra.regulatory_requirements(id) ON DELETE RESTRICT,
    stage_a_status TEXT NOT NULL CHECK (stage_a_status IN ('verified', 'rejected', 'clarification_required')),
    reviewer_user_id UUID NOT NULL REFERENCES xportra.users(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    rationale TEXT NOT NULL,
    source_id UUID REFERENCES xportra.regulatory_sources(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS regulatory_stage_a_reviews_requirement_idx
    ON xportra.regulatory_stage_a_reviews (requirement_id, created_at);
CREATE INDEX IF NOT EXISTS regulatory_stage_a_reviews_reviewer_idx
    ON xportra.regulatory_stage_a_reviews (reviewer_user_id, created_at);
CREATE INDEX IF NOT EXISTS regulatory_stage_a_reviews_status_idx
    ON xportra.regulatory_stage_a_reviews (stage_a_status, created_at);

-- Append-only protection: ordinary roles cannot update or delete historical
-- review rows (enforced by trigger).
CREATE OR REPLACE FUNCTION xportra.regulatory_stage_a_reviews_reject_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'regulatory_stage_a_reviews is append-only; update and delete are not permitted';
END;
$$;

CREATE TRIGGER regulatory_stage_a_reviews_no_update
    BEFORE UPDATE ON xportra.regulatory_stage_a_reviews
    FOR EACH ROW
    EXECUTE FUNCTION xportra.regulatory_stage_a_reviews_reject_mutation();
CREATE TRIGGER regulatory_stage_a_reviews_no_delete
    BEFORE DELETE ON xportra.regulatory_stage_a_reviews
    FOR EACH ROW
    EXECUTE FUNCTION xportra.regulatory_stage_a_reviews_reject_mutation();

COMMIT;
