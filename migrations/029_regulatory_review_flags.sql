BEGIN;

CREATE TABLE IF NOT EXISTS xportra.regulatory_review_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requirement_id UUID REFERENCES xportra.regulatory_requirements(id) ON DELETE SET NULL,
    trigger_source_id UUID REFERENCES xportra.regulatory_sources(id) ON DELETE SET NULL,
    trigger_type TEXT NOT NULL CHECK (trigger_type IN ('supersession', 'version_change', 'material_change', 'stale', 'withdrawal')),
    status TEXT NOT NULL DEFAULT 'pending_review' CHECK (status IN ('pending_review', 'review_completed', 'dismissed')),
    actor_user_id UUID REFERENCES xportra.users(id) ON DELETE SET NULL,
    rationale TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS regulatory_review_flags_requirement_idx
    ON xportra.regulatory_review_flags (requirement_id) WHERE requirement_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS regulatory_review_flags_source_idx
    ON xportra.regulatory_review_flags (trigger_source_id) WHERE trigger_source_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS regulatory_review_flags_status_idx
    ON xportra.regulatory_review_flags (status);
CREATE INDEX IF NOT EXISTS regulatory_review_flags_trigger_idx
    ON xportra.regulatory_review_flags (trigger_type);

COMMIT;
