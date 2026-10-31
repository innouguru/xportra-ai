-- Migration 032: append-only wording-correction history for candidate
-- requirements (M5 — candidate review wording correction).
--
-- Invariant 6 requires that ingested content is never silently altered,
-- truncated, or misattributed. Wording corrections therefore record the
-- pre-correction wording verbatim alongside the corrected wording, the
-- reviewer who made the correction, and the rationale — in the same
-- transaction that updates the operative candidate text.

BEGIN;

CREATE TABLE IF NOT EXISTS xportra.regulatory_requirement_wording_corrections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requirement_id UUID NOT NULL REFERENCES xportra.regulatory_requirements(id) ON DELETE RESTRICT,
    source_id UUID REFERENCES xportra.regulatory_sources(id) ON DELETE SET NULL,
    original_text TEXT NOT NULL,
    corrected_text TEXT NOT NULL,
    rationale TEXT NOT NULL,
    reviewer_user_id UUID NOT NULL REFERENCES xportra.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS regulatory_requirement_wording_corrections_requirement_idx
    ON xportra.regulatory_requirement_wording_corrections (requirement_id, created_at);
CREATE INDEX IF NOT EXISTS regulatory_requirement_wording_corrections_reviewer_idx
    ON xportra.regulatory_requirement_wording_corrections (reviewer_user_id, created_at);

-- Append-only protection: historical correction rows are never updated
-- or deleted (enforced by trigger), mirroring regulatory_stage_a_reviews.
CREATE OR REPLACE FUNCTION xportra.regulatory_wording_corrections_reject_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'regulatory_requirement_wording_corrections is append-only; update and delete are not permitted';
END;
$$;

CREATE TRIGGER regulatory_wording_corrections_no_update
    BEFORE UPDATE ON xportra.regulatory_requirement_wording_corrections
    FOR EACH ROW
    EXECUTE FUNCTION xportra.regulatory_wording_corrections_reject_mutation();
CREATE TRIGGER regulatory_wording_corrections_no_delete
    BEFORE DELETE ON xportra.regulatory_requirement_wording_corrections
    FOR EACH ROW
    EXECUTE FUNCTION xportra.regulatory_wording_corrections_reject_mutation();

COMMIT;
