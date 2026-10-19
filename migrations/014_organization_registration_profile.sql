BEGIN;

-- Organization-level self-service registration (Phase 10.11).
--
-- The organization IS the existing tenant row: no second
-- organization table is introduced. Registration collects a
-- small organization profile that has no home in the Phase 1
-- tenant model, so three NULLABLE columns are added:
--
--   organization_type — the supported registered category
--                       (farmer, cooperative, exporter,
--                       service_provider, other);
--   country_code      — ISO-3166 alpha-2 country of the
--                       organization;
--   region            — state/region where applicable.
--
-- All three are nullable and default to NULL, so every
-- pre-existing tenant row, membership, shipment, evidence
-- record, and authorization rule is unaffected. Registration
-- status is deliberately NOT modelled here: registering on
-- Xportra is not regulatory verification or approval, and the
-- existing tenant `status` vocabulary
-- (active | suspended | archived) is reused unchanged.
ALTER TABLE xportra.tenants
    ADD COLUMN IF NOT EXISTS organization_type TEXT
        CHECK (
            organization_type IS NULL
            OR organization_type IN (
                'farmer',
                'cooperative',
                'exporter',
                'service_provider',
                'other'
            )
        ),
    ADD COLUMN IF NOT EXISTS country_code TEXT
        CHECK (
            country_code IS NULL
            OR country_code ~ '^[A-Z]{2}$'
        ),
    ADD COLUMN IF NOT EXISTS region TEXT;

COMMIT;
