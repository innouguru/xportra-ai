-- Phase 4D.10 authorization hardening / deletion design — legal hold table.
-- Creates durable, append-only hold records scoped to one regulatory artifact.
-- A hold must serialize with authorization/deletion progress; an active
-- hold (`status = 'active'`) makes the linked artifact ineligible for deletion.

BEGIN;

CREATE TABLE IF NOT EXISTS xportra.regulatory_artifact_legal_hold (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES xportra.regulatory_source_artifacts(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'released', 'expired')),
    actor_user_id UUID NOT NULL REFERENCES xportra.users(id) ON DELETE RESTRICT,
    authorization_ref TEXT NOT NULL,
    reason TEXT NOT NULL,
    placed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    released_at TIMESTAMPTZ,
    released_by UUID REFERENCES xportra.users(id) ON DELETE RESTRICT,
    release_authorization_ref TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT regulatory_artifact_legal_hold_active_consistency
        CHECK (status <> 'released' OR released_at IS NOT NULL),
    CONSTRAINT regulatory_artifact_legal_hold_release_consistency
        CHECK ((status = 'released') = (released_by IS NOT NULL AND release_authorization_ref IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS regulatory_artifact_legal_hold_artifact_idx
    ON xportra.regulatory_artifact_legal_hold (artifact_id);
CREATE INDEX IF NOT EXISTS regulatory_artifact_legal_hold_status_idx
    ON xportra.regulatory_artifact_legal_hold (artifact_id, status, created_at);
CREATE INDEX IF NOT EXISTS regulatory_artifact_legal_hold_actor_idx
    ON xportra.regulatory_artifact_legal_hold (actor_user_id, created_at);

CREATE TRIGGER regulatory_artifact_legal_hold_set_updated_at
    BEFORE UPDATE ON xportra.regulatory_artifact_legal_hold
    FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

COMMIT;
