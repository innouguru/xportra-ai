BEGIN;

-- Phase 8.4: normalized tenant-scoped persistence for Phase 6
-- compliance result objects (reports, analyses, traces) plus the
-- round linkage and final-package linkage required for safe
-- cross-request finalization and reads.
--
-- This schema stores already-produced authoritative result
-- representations. It calculates nothing: no applicability,
-- assessment, risk, reasoning, retrieval, sufficiency, verdict,
-- readiness, or workflow-transition logic lives here. Aggregate
-- counts are carried from the composed report, never recomputed
-- in SQL. JSONB holds only fixed-schema typed reference lists
-- (the established evidence_ids convention) and the carried
-- Phase 3.5 decision-summary reference; every identity, state,
-- ordering, and linkage field is a real column.

CREATE TABLE IF NOT EXISTS xportra.compliance_analysis_reports (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES xportra.tenants(id) ON DELETE RESTRICT,
    case_id UUID NOT NULL,
    workflow_id UUID NOT NULL,
    context_fingerprint TEXT,
    total_requirements INTEGER NOT NULL CHECK (total_requirements >= 0),
    applicable_count INTEGER NOT NULL CHECK (applicable_count >= 0),
    satisfied_count INTEGER NOT NULL CHECK (satisfied_count >= 0),
    not_satisfied_count INTEGER NOT NULL CHECK (not_satisfied_count >= 0),
    unknown_count INTEGER NOT NULL CHECK (unknown_count >= 0),
    not_applicable_count INTEGER NOT NULL CHECK (not_applicable_count >= 0),
    conflicting_evidence_count INTEGER NOT NULL CHECK (conflicting_evidence_count >= 0),
    requirements_with_missing_information JSONB NOT NULL,
    uncertain_requirement_ids JSONB NOT NULL,
    requirements_with_conflicting_evidence JSONB NOT NULL,
    missing_information JSONB NOT NULL,
    decision_summary JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT compliance_analysis_reports_tenant_identity_key
        UNIQUE (tenant_id, id)
);

CREATE INDEX IF NOT EXISTS compliance_analysis_reports_tenant_case_idx
    ON xportra.compliance_analysis_reports (tenant_id, case_id);
CREATE INDEX IF NOT EXISTS compliance_analysis_reports_tenant_workflow_idx
    ON xportra.compliance_analysis_reports (tenant_id, workflow_id);

CREATE TRIGGER compliance_analysis_reports_set_updated_at
    BEFORE UPDATE ON xportra.compliance_analysis_reports
    FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

CREATE TABLE IF NOT EXISTS xportra.compliance_analyses (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES xportra.tenants(id) ON DELETE RESTRICT,
    report_id UUID NOT NULL,
    case_id UUID NOT NULL,
    workflow_id UUID NOT NULL,
    requirement_id UUID NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    requirement_text TEXT NOT NULL,
    applicability TEXT NOT NULL CHECK (applicability IN ('applicable', 'not_applicable', 'unknown')),
    assessment TEXT NOT NULL CHECK (assessment IN ('satisfied', 'not_satisfied', 'unknown')),
    explanation TEXT NOT NULL,
    uncertainty TEXT NOT NULL,
    uncertainty_explanation TEXT NOT NULL,
    evidence_sufficiency TEXT NOT NULL CHECK (evidence_sufficiency IN ('supported', 'insufficient', 'missing', 'unknown')),
    contradiction_state TEXT NOT NULL CHECK (contradiction_state IN ('none', 'present')),
    sufficiency_explanation TEXT NOT NULL,
    missing_information JSONB NOT NULL,
    supporting_evidence JSONB NOT NULL,
    conflicting_evidence JSONB NOT NULL,
    knowledge_references JSONB NOT NULL,
    sources JSONB NOT NULL,
    missing_items JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT compliance_analyses_tenant_identity_key
        UNIQUE (tenant_id, id),
    CONSTRAINT compliance_analyses_report_position_key
        UNIQUE (tenant_id, report_id, position),
    CONSTRAINT compliance_analyses_report_fk
        FOREIGN KEY (tenant_id, report_id)
        REFERENCES xportra.compliance_analysis_reports (tenant_id, id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS compliance_analyses_tenant_report_idx
    ON xportra.compliance_analyses (tenant_id, report_id, position);
CREATE INDEX IF NOT EXISTS compliance_analyses_tenant_requirement_idx
    ON xportra.compliance_analyses (tenant_id, requirement_id);

CREATE TRIGGER compliance_analyses_set_updated_at
    BEFORE UPDATE ON xportra.compliance_analyses
    FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

CREATE TABLE IF NOT EXISTS xportra.compliance_analysis_traces (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES xportra.tenants(id) ON DELETE RESTRICT,
    report_id UUID NOT NULL,
    analysis_id UUID NOT NULL,
    case_id UUID NOT NULL,
    workflow_id UUID NOT NULL,
    requirement_id UUID NOT NULL,
    position INTEGER NOT NULL CHECK (position >= 0),
    context_fingerprint TEXT,
    applicability TEXT NOT NULL CHECK (applicability IN ('applicable', 'not_applicable', 'unknown')),
    assessment TEXT NOT NULL CHECK (assessment IN ('satisfied', 'not_satisfied', 'unknown')),
    explanation TEXT NOT NULL,
    evidence_sufficiency TEXT NOT NULL,
    contradiction_state TEXT NOT NULL,
    sufficiency_explanation TEXT NOT NULL,
    uncertainty TEXT NOT NULL,
    missing_information JSONB NOT NULL,
    answer_fingerprint TEXT NOT NULL,
    input_fingerprint TEXT NOT NULL,
    steps JSONB NOT NULL,
    supporting_evidence JSONB NOT NULL,
    conflicting_evidence JSONB NOT NULL,
    knowledge_references JSONB NOT NULL,
    sources JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT compliance_analysis_traces_tenant_identity_key
        UNIQUE (tenant_id, id),
    CONSTRAINT compliance_analysis_traces_report_position_key
        UNIQUE (tenant_id, report_id, position),
    CONSTRAINT compliance_analysis_traces_report_fk
        FOREIGN KEY (tenant_id, report_id)
        REFERENCES xportra.compliance_analysis_reports (tenant_id, id)
        ON DELETE CASCADE,
    CONSTRAINT compliance_analysis_traces_analysis_fk
        FOREIGN KEY (tenant_id, analysis_id)
        REFERENCES xportra.compliance_analyses (tenant_id, id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS compliance_analysis_traces_tenant_report_idx
    ON xportra.compliance_analysis_traces (tenant_id, report_id, position);

CREATE TRIGGER compliance_analysis_traces_set_updated_at
    BEFORE UPDATE ON xportra.compliance_analysis_traces
    FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

CREATE TABLE IF NOT EXISTS xportra.compliance_workflow_rounds (
    tenant_id UUID NOT NULL REFERENCES xportra.tenants(id) ON DELETE RESTRICT,
    workflow_id UUID NOT NULL,
    round_index INTEGER NOT NULL CHECK (round_index >= 1),
    case_id UUID NOT NULL,
    shipment_id UUID,
    report_id UUID NOT NULL,
    analysis_ids JSONB NOT NULL,
    trace_ids JSONB NOT NULL,
    input_fingerprints JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT compliance_workflow_rounds_pkey
        PRIMARY KEY (tenant_id, workflow_id, round_index),
    CONSTRAINT compliance_workflow_rounds_report_fk
        FOREIGN KEY (tenant_id, report_id)
        REFERENCES xportra.compliance_analysis_reports (tenant_id, id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS compliance_workflow_rounds_tenant_workflow_idx
    ON xportra.compliance_workflow_rounds (tenant_id, workflow_id, round_index);

CREATE TRIGGER compliance_workflow_rounds_set_updated_at
    BEFORE UPDATE ON xportra.compliance_workflow_rounds
    FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

CREATE TABLE IF NOT EXISTS xportra.final_assessment_packages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES xportra.tenants(id) ON DELETE RESTRICT,
    workflow_id UUID NOT NULL,
    case_id UUID NOT NULL,
    shipment_id UUID,
    report_id UUID NOT NULL,
    round_index INTEGER NOT NULL CHECK (round_index >= 1),
    open_requirements JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT final_assessment_packages_workflow_key
        UNIQUE (tenant_id, workflow_id),
    CONSTRAINT final_assessment_packages_report_fk
        FOREIGN KEY (tenant_id, report_id)
        REFERENCES xportra.compliance_analysis_reports (tenant_id, id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS final_assessment_packages_tenant_workflow_idx
    ON xportra.final_assessment_packages (tenant_id, workflow_id);

CREATE TRIGGER final_assessment_packages_set_updated_at
    BEFORE UPDATE ON xportra.final_assessment_packages
    FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

COMMIT;
