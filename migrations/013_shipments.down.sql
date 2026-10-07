BEGIN;

DROP TRIGGER IF EXISTS shipments_set_updated_at ON xportra.shipments;
DROP INDEX IF EXISTS xportra.shipments_tenant_case_idx;
DROP TABLE IF EXISTS xportra.shipments;

COMMIT;
