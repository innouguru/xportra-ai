-- Rollback of audit authorization reference linkage.

BEGIN;

DROP INDEX IF EXISTS xportra.global_staff_audit_authorization_ref_idx;
ALTER TABLE xportra.global_staff_audit DROP COLUMN IF EXISTS authorization_ref;

COMMIT;
