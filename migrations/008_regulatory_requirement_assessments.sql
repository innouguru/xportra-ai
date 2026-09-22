BEGIN;

CREATE TABLE IF NOT EXISTS xportra.regulatory_requirement_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES xportra.tenants(id) ON DELETE RESTRICT,
    requirement_id UUID NOT NULL
        REFERENCES xportra.regulatory_requirements(id) ON DELETE RESTRICT,
    applicability_result_id UUID NOT NULL
        REFERENCES xportra.regulatory_requirement_applicability(id) ON DELETE RESTRICT,
    evidence_fingerprint TEXT NOT NULL,
    evidence_id UUID REFERENCES xportra.compliance_evidence(id) ON DELETE RESTRICT,
    evidence_ids JSONB NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('satisfied', 'not_satisfied', 'unknown')),
    reason TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('assessed', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT regulatory_requirement_assessments_identity_key
        UNIQUE (tenant_id, requirement_id, applicability_result_id, evidence_fingerprint)
);

CREATE INDEX IF NOT EXISTS regulatory_requirement_assessments_tenant_idx
    ON xportra.regulatory_requirement_assessments (tenant_id, created_at, id);

CREATE INDEX IF NOT EXISTS regulatory_requirement_assessments_requirement_idx
    ON xportra.regulatory_requirement_assessments (requirement_id, outcome, created_at);

CREATE TRIGGER regulatory_requirement_assessments_set_updated_at
    BEFORE UPDATE ON xportra.regulatory_requirement_assessments
    FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

COMMIT;
