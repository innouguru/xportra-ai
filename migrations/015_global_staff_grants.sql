-- Phase 4D.10 Task 2 — initial global staff grant and audit foundation.
--
-- Adds two tables in the existing ``xportra`` schema:
--
--   xportra.global_staff_grants
--     Current-state grant rows, at most one per (user_id, permission)
--     (Model A: current-state grants plus immutable audit events).
--     Revocation UPDATEs the existing row; re-grant reactivates it.
--     Only explicitly defined global staff permissions are admitted
--     (initially ``grant_manage`` only).
--
--   xportra.global_staff_audit
--     Append-only audit of grant, revocation, reactivation, bootstrap,
--     and recovery events. Ordinary application roles cannot UPDATE or
--     DELETE historical rows (enforced by trigger). Absolute immutability
--     against sufficiently privileged database administrators is NOT
--     claimed.
--
-- No email, Supabase UID, internal user ID, or tenant ID is hardcoded.
-- Identity is resolved at runtime via users.supabase_uid -> users.id.

BEGIN;

CREATE TABLE xportra.global_staff_grants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES xportra.users(id) ON DELETE RESTRICT,
    permission TEXT NOT NULL CHECK (permission = 'grant_manage'),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'revoked')),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    granted_by UUID NOT NULL REFERENCES xportra.users(id) ON DELETE RESTRICT,
    revoked_at TIMESTAMPTZ,
    revoked_by UUID REFERENCES xportra.users(id) ON DELETE RESTRICT,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT global_staff_grants_user_permission_key
        UNIQUE (user_id, permission),
    CONSTRAINT global_staff_grants_revoked_consistency
        CHECK ((status = 'revoked') = (revoked_at IS NOT NULL)),
    CONSTRAINT global_staff_grants_revoked_by_required
        CHECK (status <> 'revoked' OR revoked_by IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS global_staff_grants_user_id_idx
    ON xportra.global_staff_grants (user_id);
CREATE INDEX IF NOT EXISTS global_staff_grants_permission_idx
    ON xportra.global_staff_grants (permission);
CREATE INDEX IF NOT EXISTS global_staff_grants_active_idx
    ON xportra.global_staff_grants (user_id, permission)
    WHERE status = 'active';

CREATE TABLE xportra.global_staff_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL
        CHECK (event_type IN ('grant', 'revocation', 'reactivation', 'bootstrap', 'recovery')),
    actor_user_id UUID NOT NULL REFERENCES xportra.users(id) ON DELETE RESTRICT,
    target_user_id UUID NOT NULL REFERENCES xportra.users(id) ON DELETE RESTRICT,
    permission TEXT NOT NULL CHECK (permission = 'grant_manage'),
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS global_staff_audit_target_idx
    ON xportra.global_staff_audit (target_user_id, permission, created_at);
CREATE INDEX IF NOT EXISTS global_staff_audit_actor_idx
    ON xportra.global_staff_audit (actor_user_id, created_at);
CREATE INDEX IF NOT EXISTS global_staff_audit_event_idx
    ON xportra.global_staff_audit (event_type, created_at);

-- Append-only protection: ordinary roles cannot update or delete
-- historical audit rows. Privileged database administrators can still
-- alter or drop the trigger; absolute immutability is not claimed.
CREATE OR REPLACE FUNCTION xportra.global_staff_audit_reject_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'global_staff_audit is append-only; update and delete are not permitted';
END;
$$;

CREATE TRIGGER global_staff_audit_no_update
    BEFORE UPDATE ON xportra.global_staff_audit
    FOR EACH ROW
    EXECUTE FUNCTION xportra.global_staff_audit_reject_mutation();

CREATE TRIGGER global_staff_audit_no_delete
    BEFORE DELETE ON xportra.global_staff_audit
    FOR EACH ROW
    EXECUTE FUNCTION xportra.global_staff_audit_reject_mutation();

COMMIT;
