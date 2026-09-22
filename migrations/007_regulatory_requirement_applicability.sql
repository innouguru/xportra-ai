BEGIN;

CREATE TABLE IF NOT EXISTS xportra.regulatory_requirement_applicability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES xportra.tenants(id) ON DELETE RESTRICT,
    requirement_id UUID NOT NULL
        REFERENCES xportra.regulatory_requirements(id) ON DELETE RESTRICT,
    context_fingerprint TEXT NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('applicable', 'not_applicable', 'unknown')),
    reason TEXT NOT NULL,
    context JSONB NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('evaluated', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT regulatory_requirement_applicability_identity_key
        UNIQUE (tenant_id, requirement_id, context_fingerprint)
);

CREATE INDEX IF NOT EXISTS regulatory_requirement_applicability_tenant_idx
    ON xportra.regulatory_requirement_applicability (tenant_id, created_at, id);

CREATE INDEX IF NOT EXISTS regulatory_requirement_applicability_requirement_idx
    ON xportra.regulatory_requirement_applicability (requirement_id, outcome, created_at);

CREATE TRIGGER regulatory_requirement_applicability_set_updated_at
    BEFORE UPDATE ON xportra.regulatory_requirement_applicability
    FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

COMMIT;
