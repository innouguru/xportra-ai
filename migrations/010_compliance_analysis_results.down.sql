BEGIN;

DROP TRIGGER IF EXISTS final_assessment_packages_set_updated_at ON xportra.final_assessment_packages;
DROP TABLE IF EXISTS xportra.final_assessment_packages;
DROP TRIGGER IF EXISTS compliance_workflow_rounds_set_updated_at ON xportra.compliance_workflow_rounds;
DROP TABLE IF EXISTS xportra.compliance_workflow_rounds;
DROP TRIGGER IF EXISTS compliance_analysis_traces_set_updated_at ON xportra.compliance_analysis_traces;
DROP TABLE IF EXISTS xportra.compliance_analysis_traces;
DROP TRIGGER IF EXISTS compliance_analyses_set_updated_at ON xportra.compliance_analyses;
DROP TABLE IF EXISTS xportra.compliance_analyses;
DROP TRIGGER IF EXISTS compliance_analysis_reports_set_updated_at ON xportra.compliance_analysis_reports;
DROP TABLE IF EXISTS xportra.compliance_analysis_reports;

COMMIT;
