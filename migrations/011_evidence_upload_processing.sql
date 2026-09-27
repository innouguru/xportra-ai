BEGIN;

-- Phase 10.4 — evidence upload lifecycle (R-10.4 U3/U5/U7).
--
-- Adds processing-state and upload-provenance columns to the
-- existing compliance_evidence table (no second evidence
-- table). Review status (uploaded/reviewed/accepted/
-- rejected/archived) is untouched: processing_status tracks
-- the dedicated ingestion pipeline lifecycle
-- (uploaded → processing → ready | failed), separate from
-- human review and from compliance assessment state.
-- processing_error carries static step codes only — never
-- document contents, stack traces, URLs, or secrets.
-- uploaded_by records the initiating actor subject where
-- the API provides one (NULL for unauthenticated
-- development identities). content_hash stays nullable so
-- pre-existing reference rows are unaffected; upload rows
-- always carry one (enforced in the domain boundary).
ALTER TABLE xportra.compliance_evidence
    ADD COLUMN IF NOT EXISTS processing_status TEXT NOT NULL DEFAULT 'uploaded'
        CHECK (processing_status IN ('uploaded', 'processing', 'ready', 'failed')),
    ADD COLUMN IF NOT EXISTS processing_step TEXT,
    ADD COLUMN IF NOT EXISTS processing_error TEXT,
    ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS original_filename TEXT,
    ADD COLUMN IF NOT EXISTS mime_type TEXT,
    ADD COLUMN IF NOT EXISTS storage_bucket TEXT,
    ADD COLUMN IF NOT EXISTS uploaded_by UUID;

-- Idempotency: one evidence row per tenant per content hash
-- (cross-tenant identical hashes stay independently owned).
CREATE UNIQUE INDEX IF NOT EXISTS compliance_evidence_tenant_hash_uidx
    ON xportra.compliance_evidence (tenant_id, content_hash)
    WHERE content_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS compliance_evidence_tenant_processing_idx
    ON xportra.compliance_evidence (tenant_id, processing_status);

COMMIT;
