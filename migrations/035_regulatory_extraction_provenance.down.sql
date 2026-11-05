BEGIN;

DROP TRIGGER regulatory_requirement_extraction_run_candidates_resolve_once
    ON xportra.regulatory_requirement_extraction_run_candidates;
DROP TRIGGER regulatory_requirement_extraction_runs_no_mutation
    ON xportra.regulatory_requirement_extraction_runs;
DROP TRIGGER regulatory_document_normalizations_identity_immutable
    ON xportra.regulatory_document_normalizations;
DROP TRIGGER regulatory_source_artifacts_identity_immutable
    ON xportra.regulatory_source_artifacts;

DROP FUNCTION xportra.regulatory_extraction_run_candidate_resolve_once();
DROP FUNCTION xportra.regulatory_extraction_history_reject_mutation();
DROP FUNCTION xportra.regulatory_document_normalization_identity_immutable();
DROP FUNCTION xportra.regulatory_source_artifact_identity_immutable();

DROP TABLE xportra.regulatory_requirement_extraction_run_candidates;
DROP TABLE xportra.regulatory_requirement_extraction_runs;

ALTER TABLE xportra.regulatory_requirements
    DROP CONSTRAINT regulatory_requirements_document_identity_key;
ALTER TABLE xportra.regulatory_ingestion_jobs
    DROP CONSTRAINT regulatory_ingestion_jobs_identity_key;
ALTER TABLE xportra.regulatory_source_artifacts
    DROP CONSTRAINT regulatory_source_artifacts_version_identity_key;
ALTER TABLE xportra.regulatory_source_artifacts
    DROP CONSTRAINT regulatory_source_artifacts_identity_key;
ALTER TABLE xportra.regulatory_document_normalizations
    DROP CONSTRAINT regulatory_document_normalizations_identity_key;

COMMIT;
