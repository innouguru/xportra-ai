BEGIN;

-- Stage B review state: approves applicability to the defined Nigerian export
-- pilot scope. Does NOT publish requirements or mark them exporter-ready.
-- Stage B approval requires a separate Stage A-verified candidate and is a
-- governance decision distinct from runtime applicability evaluation.
ALTER TABLE xportra.regulatory_requirements
    ADD COLUMN stage_b_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (stage_b_status IN ('pending', 'approved', 'rejected', 'clarification_required'));

ALTER TABLE xportra.regulatory_requirements
    ADD COLUMN stage_b_reviewer_user_id UUID
        REFERENCES xportra.users(id) ON DELETE SET NULL;

ALTER TABLE xportra.regulatory_requirements
    ADD COLUMN stage_b_reviewed_at TIMESTAMPTZ;

ALTER TABLE xportra.regulatory_requirements
    ADD COLUMN stage_b_rationale TEXT;

ALTER TABLE xportra.regulatory_requirements
    ADD COLUMN stage_b_pilot_scope TEXT;

CREATE INDEX IF NOT EXISTS regulatory_requirements_stage_b_status_idx
    ON xportra.regulatory_requirements (stage_b_status);
CREATE INDEX IF NOT EXISTS regulatory_requirements_stage_b_reviewer_idx
    ON xportra.regulatory_requirements (stage_b_reviewer_user_id)
    WHERE stage_b_reviewer_user_id IS NOT NULL;

COMMIT;
