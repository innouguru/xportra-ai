BEGIN;

-- Server-owned compliance workflow record.
--
-- Persists the workflow progression that the client used
-- to echo back each request (state, shipment binding,
-- supplied evidence references, open requirements) so the
-- server becomes authoritative for continuity: later
-- requests load this row (plus the existing round
-- linkage) instead of trusting the submitted snapshot.
-- This is a persistence representation of the existing
-- domain workflow record, not a replacement domain
-- model: transition rules stay in the domain service;
-- analysis content stays in the result tables (010).
-- Rounds are deliberately not duplicated here — the
-- compliance_workflow_rounds linkage remains the round
-- authority and is compared alongside this row.
-- No timestamps beyond the standard created_at/
-- updated_at pair carried by every 010 table. No
-- verdict, score, or compliance content lives here.
CREATE TABLE IF NOT EXISTS xportra.compliance_workflows (
    tenant_id UUID NOT NULL REFERENCES xportra.tenants(id),
    workflow_id UUID NOT NULL,
    case_id UUID NOT NULL,
    shipment_id UUID,
    state TEXT NOT NULL CHECK (state IN (
        'created',
        'information_provided',
        'evidence_pending',
        'applicability_determined',
        'analysis_available',
        'review_required',
        'additional_evidence_requested',
        'reanalysis_required',
        'assessment_package_ready'
    )),
    supplied_evidence_ids UUID[] NOT NULL DEFAULT '{}',
    open_requirements UUID[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, workflow_id)
);

-- No secondary index: the only access pattern is the
-- tenant-scoped identity lookup, fully covered by the
-- composite primary key.

CREATE TRIGGER compliance_workflows_set_updated_at
    BEFORE UPDATE ON xportra.compliance_workflows
    FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

COMMIT;
