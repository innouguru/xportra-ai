BEGIN;

DROP TRIGGER IF EXISTS compliance_workflows_set_updated_at ON xportra.compliance_workflows;
DROP TABLE IF EXISTS xportra.compliance_workflows;

COMMIT;
