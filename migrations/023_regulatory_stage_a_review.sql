BEGIN;

-- Stage A review state: verifies source traceability and requirement wording
-- only. Does NOT approve pilot applicability (Stage B) or publish
-- requirements for exporter-facing use.
ALTER TABLE xportra.regulatory_requirements
    ADD COLUMN stage_a_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (stage_a_status IN ('pending', 'verified', 'rejected', 'clarification_required'));

ALTER TABLE xportra.regulatory_requirements
    ADD COLUMN stage_a_reviewer_user_id UUID
        REFERENCES xportra.users(id) ON DELETE SET NULL;

ALTER TABLE xportra.regulatory_requirements
    ADD COLUMN stage_a_reviewed_at TIMESTAMPTZ;

ALTER TABLE xportra.regulatory_requirements
    ADD COLUMN stage_a_rationale TEXT;

CREATE INDEX IF NOT EXISTS regulatory_requirements_stage_a_status_idx
    ON xportra.regulatory_requirements (stage_a_status);

CREATE INDEX IF NOT EXISTS regulatory_requirements_stage_a_reviewer_idx
    ON xportra.regulatory_requirements (stage_a_reviewer_user_id)
    WHERE stage_a_reviewer_user_id IS NOT NULL;

COMMIT;
