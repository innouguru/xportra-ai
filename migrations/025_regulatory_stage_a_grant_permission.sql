BEGIN;

-- Allow STAGE_A_VERIFY as a valid global staff permission alongside
-- GRANT_MANAGE. The CHECK constraint on global_staff_grants.permission
-- previously only admitted 'grant_manage'.
ALTER TABLE xportra.global_staff_grants
    DROP CONSTRAINT global_staff_grants_permission_check;

ALTER TABLE xportra.global_staff_grants
    ADD CONSTRAINT global_staff_grants_permission_check
        CHECK (permission IN ('grant_manage', 'stage_a_verify'));

COMMIT;
