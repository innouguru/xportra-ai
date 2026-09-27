BEGIN;

DROP INDEX IF EXISTS xportra.compliance_evidence_tenant_processing_idx;
DROP INDEX IF EXISTS xportra.compliance_evidence_tenant_hash_uidx;

ALTER TABLE xportra.compliance_evidence
    DROP COLUMN IF EXISTS uploaded_by,
    DROP COLUMN IF EXISTS storage_bucket,
    DROP COLUMN IF EXISTS mime_type,
    DROP COLUMN IF EXISTS original_filename,
    DROP COLUMN IF EXISTS processed_at,
    DROP COLUMN IF EXISTS processing_error,
    DROP COLUMN IF EXISTS processing_step,
    DROP COLUMN IF EXISTS processing_status;

COMMIT;
