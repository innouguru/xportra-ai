-- Phase 4D.10 authorization hardening — durable deletion-intent table.
-- Tracks authorization, eligibility, hold status, audit linkage,
-- bounded retry, reconciliation, and safe failure states.
-- Deletion of the source artifact remains disabled; storage mutation
-- is not implemented by this migration.

BEGIN;

CREATE TABLE IF NOT EXISTS xportra.regulatory_artifact_deletion_intent (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES xportra.regulatory_source_artifacts(id) ON DELETE RESTRICT,
    content_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'eligible', 'ineligible', 'authorized', 'hold_placed', 'deleting', 'deleted', 'failed', 'reconciled')),
    actor_user_id UUID NOT NULL REFERENCES xportra.users(id) ON DELETE RESTRICT,
    authorization_ref TEXT NOT NULL,
    reason TEXT NOT NULL,
    retention_eligibility TEXT NOT NULL
        CHECK (retention_eligibility IN ('current_published', 'superseded_24mo', 'rejected_24mo', 'withdrawn_24mo', 'manual_recovery', 'ineligible')),
    legal_hold_active BOOLEAN NOT NULL DEFAULT FALSE,
    audit_event_ref TEXT,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    authorized_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    reconciled BOOLEAN NOT NULL DEFAULT FALSE,
    reconciliation_note TEXT,
    retry_attempt INTEGER NOT NULL DEFAULT 0 CHECK (retry_attempt >= 0),
    max_retry_attempt INTEGER NOT NULL DEFAULT 5 CHECK (max_retry_attempt > 0),
    last_retry_at TIMESTAMPTZ,
    last_retry_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT regulatory_artifact_deletion_intent_duplicate_protection
        UNIQUE (artifact_id, authorization_ref, actor_user_id),
    CONSTRAINT regulatory_artifact_deletion_intent_deleted_consistency
        CHECK (status <> 'deleted' OR deleted_at IS NOT NULL),
    CONSTRAINT regulatory_artifact_deletion_intent_reconciled_deleted_consistency
        CHECK (reconciled = FALSE OR status = 'deleted'),
    CONSTRAINT regulatory_artifact_deletion_intent_reconciled_note
        CHECK ((reconciled = TRUE) = (reconciliation_note IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS regulatory_artifact_deletion_intent_artifact_idx
    ON xportra.regulatory_artifact_deletion_intent (artifact_id);
CREATE INDEX IF NOT EXISTS regulatory_artifact_deletion_intent_status_idx
    ON xportra.regulatory_artifact_deletion_intent (status, created_at);
CREATE INDEX IF NOT EXISTS regulatory_artifact_deletion_intent_reconciled_idx
    ON xportra.regulatory_artifact_deletion_intent (reconciled, status, artifact_id);
CREATE INDEX IF NOT EXISTS regulatory_artifact_deletion_intent_actor_idx
    ON xportra.regulatory_artifact_deletion_intent (actor_user_id, created_at);
CREATE INDEX IF NOT EXISTS regulatory_artifact_deletion_intent_authorization_ref_idx
    ON xportra.regulatory_artifact_deletion_intent (authorization_ref);

CREATE TRIGGER regulatory_artifact_deletion_intent_set_updated_at
    BEFORE UPDATE ON xportra.regulatory_artifact_deletion_intent
    FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

COMMIT;
