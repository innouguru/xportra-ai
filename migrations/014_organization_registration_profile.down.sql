BEGIN;

ALTER TABLE xportra.tenants
    DROP COLUMN IF EXISTS region,
    DROP COLUMN IF EXISTS country_code,
    DROP COLUMN IF EXISTS organization_type;

COMMIT;
