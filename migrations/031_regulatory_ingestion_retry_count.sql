-- Migration 031: bounded ingestion retry accounting.
--
-- Adds an explicit per-row retry counter to durable ingestion jobs so
-- that the worker's bounded-retry contract is operative: each time an
-- attempt is marked retryable the counter increments; when the bound is
-- reached the next failure is terminal (status = 'failed'). A terminal
-- failure can only be retried again through the separate authorized
-- staff retry control, which records a NEW attempt row (new
-- attempt_number) and resets the counter — prior attempts remain
-- immutable history.

BEGIN;

ALTER TABLE xportra.regulatory_ingestion_jobs
    ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0
        CHECK (retry_count >= 0);

COMMIT;
