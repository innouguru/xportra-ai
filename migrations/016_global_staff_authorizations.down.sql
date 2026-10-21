-- Phase 4D.10 — rollback of global_staff_authorizations.

BEGIN;

DROP TABLE IF EXISTS xportra.global_staff_authorizations;

COMMIT;
