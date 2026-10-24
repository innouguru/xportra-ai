BEGIN;

-- Allow STAGE_B_APPROVE as a valid global staff permission alongside
-- GRANT_MANAGE and STAGE_A_VERIFY. The CHECK constraint on
-- global_staff_grants.permission previously only admitted
-- 'grant_manage' and 'stage_a_verify'.
ALTER TABLE xportra.global_staff_grants
    DROP CONSTRAINT global_staff_grants_permission_check;

ALTER TABLE xportra.global_staff_grants
    ADD CONSTRAINT global_staff_grants_permission_check
        CHECK (permission IN ('grant_manage', 'stage_a_verify', 'stage_b_approve'));

COMMIT;
