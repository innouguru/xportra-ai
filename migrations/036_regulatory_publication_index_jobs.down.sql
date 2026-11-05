BEGIN;

DROP TRIGGER IF EXISTS regulatory_review_flag_publication_index_changed
    ON xportra.regulatory_review_flags;
DROP TRIGGER IF EXISTS regulatory_source_publication_index_changed
    ON xportra.regulatory_sources;
DROP TRIGGER IF EXISTS regulatory_requirement_publication_index_changed
    ON xportra.regulatory_requirements;

DROP FUNCTION IF EXISTS
    xportra.regulatory_review_flag_publication_index_changed();
DROP FUNCTION IF EXISTS
    xportra.regulatory_source_publication_index_changed();
DROP FUNCTION IF EXISTS
    xportra.regulatory_requirement_publication_index_changed();
DROP FUNCTION IF EXISTS
    xportra.refresh_regulatory_publication_index_job(UUID);

DROP TABLE IF EXISTS xportra.regulatory_publication_index_jobs;

COMMIT;
