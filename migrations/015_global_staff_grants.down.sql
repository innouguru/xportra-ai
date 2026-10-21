-- Phase 4D.10 Task 2 — rollback of global_staff_grants and global_staff_audit.

BEGIN;

DROP TRIGGER IF EXISTS global_staff_audit_no_update ON xportra.global_staff_audit;
DROP TRIGGER IF EXISTS global_staff_audit_no_delete ON xportra.global_staff_audit;
DROP FUNCTION IF EXISTS xportra.global_staff_audit_reject_mutation();

DROP TABLE IF EXISTS xportra.global_staff_audit;
DROP TABLE IF EXISTS xportra.global_staff_grants;

COMMIT;
