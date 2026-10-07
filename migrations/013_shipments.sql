BEGIN;

-- Server-owned commercial shipment aggregate (ADR-0013).
--
-- Owns the tenant-scoped commercial shipment/profile facts
-- (product, origin, destination, quantity, unit, shipment
-- date) that the frontend previously held only in
-- sessionStorage. The compliance workflow references a
-- shipment row through its existing (tenant_id,
-- shipment_id, case_id) association; no profile field is
-- duplicated into compliance_workflows and no workflow
-- state lives here.
--
-- Identity: PRIMARY KEY (tenant_id, shipment_id).
-- case_id is the reasoning/case grouping reference, never
-- the primary identity. status tracks the shipment-only
-- lifecycle draft → bound → locked, distinct from the
-- compliance workflow lifecycle.
--
-- Relationship integrity is enforced by the
-- application/store boundary (shipment resolved under the
-- request tenant before any workflow row is written),
-- not by a database foreign key from
-- compliance_workflows: existing deployments already hold
-- workflow rows carrying client-generated shipment
-- identities with no shipment row, so a validating FK
-- would reject the migration on real data. No timestamps
-- beyond the standard created_at/updated_at pair.
-- No verdict, score, or compliance content lives here.
CREATE TABLE IF NOT EXISTS xportra.shipments (
    tenant_id UUID NOT NULL REFERENCES xportra.tenants(id),
    shipment_id UUID NOT NULL,
    case_id UUID NOT NULL,
    product TEXT NOT NULL CHECK (char_length(product) > 0),
    origin_country TEXT NOT NULL CHECK (char_length(origin_country) > 0),
    destination_country TEXT NOT NULL CHECK (char_length(destination_country) > 0),
    quantity TEXT,
    unit TEXT,
    shipment_date TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
        'draft',
        'bound',
        'locked'
    )),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, shipment_id)
);

-- Case-grouping lookup for future durable history reads;
-- the only access patterns are the tenant-scoped identity
-- lookup (covered by the composite primary key) and this
-- case grouping.
CREATE INDEX IF NOT EXISTS shipments_tenant_case_idx
    ON xportra.shipments (tenant_id, case_id);

CREATE TRIGGER shipments_set_updated_at
    BEFORE UPDATE ON xportra.shipments
    FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

COMMIT;
