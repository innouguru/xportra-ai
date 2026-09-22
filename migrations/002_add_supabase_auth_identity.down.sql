BEGIN;

DROP INDEX IF EXISTS xportra.users_supabase_uid_key;

ALTER TABLE xportra.users DROP COLUMN IF EXISTS supabase_uid;

COMMIT;