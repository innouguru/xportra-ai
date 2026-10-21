-- Phase 4D.10 — global staff authorization record (independent verification)
--
-- Dedicated authorization table supporting independently approved bootstrap
-- authorizations, separate from the current-state grants and audit events.

BEGIN;

CREATE TABLE xportra.global_staff_authorizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_user_id UUID NOT NULL REFERENCES xportra.users(id) ON DELETE RESTRICT,
    permission TEXT NOT NULL CHECK (permission = 'grant_manage'),
    authorizer_user_id UUID NOT NULL REFERENCES xportra.users(id) ON DELETE RESTRICT,
    verifier_user_id UUID NOT NULL REFERENCES xportra.users(id) ON DELETE RESTRICT,
    authorization_ref TEXT NOT NULL,
    verification_method TEXT NOT NULL,
    justification TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'approved'
        CHECK (status IN ('approved', 'revoked', 'expired', 'rejected', 'consumed')),
    approved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    verified_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revoked_by UUID REFERENCES xportra.users(id) ON DELETE RESTRICT,
    consumed_at TIMESTAMPTZ,
    consumed_by UUID REFERENCES xportra.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Partial unique index ensures at most one active or consumed
    -- authorization per (target_user_id, permission) combination.
    CONSTRAINT global_staff_authorizations_ref_not_empty
        CHECK (authorization_ref <> ''),
    CONSTRAINT global_staff_authorizations_justification_not_empty
        CHECK (justification <> ''),
    CONSTRAINT global_staff_authorizations_consumed_check
        CHECK ((status = 'consumed') = (consumed_at IS NOT NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS global_staff_authorizations_target_permission_active
    ON xportra.global_staff_authorizations (target_user_id, permission) WHERE status IN ('approved', 'consumed');

CREATE INDEX IF NOT EXISTS global_staff_authorizations_target_idx
    ON xportra.global_staff_authorizations (target_user_id, permission);
CREATE INDEX IF NOT EXISTS global_staff_authorizations_authorizer_idx
    ON xportra.global_staff_authorizations (authorizer_user_id);
CREATE INDEX IF NOT EXISTS global_staff_authorizations_status_idx
    ON xportra.global_staff_authorizations (status);

COMMIT;
