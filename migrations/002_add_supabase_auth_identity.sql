BEGIN;

ALTER TABLE xportra.users ADD COLUMN IF NOT EXISTS supabase_uid UUID;

CREATE UNIQUE INDEX IF NOT EXISTS users_supabase_uid_key
	ON xportra.users (supabase_uid)
	WHERE supabase_uid IS NOT NULL;

COMMIT;