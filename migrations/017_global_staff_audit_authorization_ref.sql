-- Phase 4D.10 — audit authorization reference linkage

BEGIN;

ALTER TABLE xportra.global_staff_audit
ADD COLUMN IF NOT EXISTS authorization_ref TEXT;

CREATE INDEX IF NOT EXISTS global_staff_audit_authorization_ref_idx
    ON xportra.global_staff_audit (authorization_ref)
    WHERE authorization_ref IS NOT NULL;

COMMIT;
