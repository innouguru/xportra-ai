-- Down migration for 032: remove the append-only wording-correction
-- history table.

BEGIN;

DROP TABLE IF EXISTS xportra.regulatory_requirement_wording_corrections;

DROP FUNCTION IF EXISTS xportra.regulatory_wording_corrections_reject_mutation();

COMMIT;
