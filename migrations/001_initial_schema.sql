BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS xportra;

CREATE TABLE xportra.authorities (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	name TEXT NOT NULL,
	jurisdiction TEXT NOT NULL,
	authority_type TEXT NOT NULL CHECK (authority_type IN ('government', 'international', 'industry', 'other')),
	status TEXT NOT NULL CHECK (status IN ('active', 'historical', 'archived')),
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	CONSTRAINT authorities_name_jurisdiction_key UNIQUE (name, jurisdiction)
);

CREATE TABLE xportra.regulatory_sources (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	authority_id UUID NOT NULL REFERENCES xportra.authorities(id) ON DELETE RESTRICT,
	jurisdiction TEXT NOT NULL,
	title TEXT NOT NULL,
	publication_date DATE,
	effective_date DATE,
	version TEXT,
	status TEXT NOT NULL CHECK (status IN ('draft', 'active', 'superseded', 'withdrawn', 'archived')),
	source_url TEXT,
	retrieval_timestamp TIMESTAMPTZ,
	supersedes_source_id UUID REFERENCES xportra.regulatory_sources(id) ON DELETE RESTRICT,
	superseded_by_source_id UUID REFERENCES xportra.regulatory_sources(id) ON DELETE RESTRICT,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	CONSTRAINT regulatory_sources_not_self_superseding CHECK (
		supersedes_source_id IS DISTINCT FROM id
		AND superseded_by_source_id IS DISTINCT FROM id
	),
	CONSTRAINT regulatory_sources_active_not_superseded CHECK (
		superseded_by_source_id IS NULL OR status <> 'active'
	)
);

CREATE UNIQUE INDEX regulatory_sources_identity_key
	ON xportra.regulatory_sources (authority_id, title, version, effective_date)
	WHERE version IS NOT NULL;

CREATE TABLE xportra.tenants (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	legal_name TEXT NOT NULL,
	slug TEXT NOT NULL UNIQUE,
	status TEXT NOT NULL CHECK (status IN ('active', 'suspended', 'archived')),
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE xportra.users (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	display_name TEXT NOT NULL,
	email TEXT,
	status TEXT NOT NULL CHECK (status IN ('active', 'invited', 'disabled', 'deleted')),
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX users_email_key ON xportra.users (email) WHERE email IS NOT NULL;

CREATE TABLE xportra.user_tenant_memberships (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	tenant_id UUID NOT NULL REFERENCES xportra.tenants(id) ON DELETE CASCADE,
	user_id UUID NOT NULL REFERENCES xportra.users(id) ON DELETE CASCADE,
	role TEXT NOT NULL,
	status TEXT NOT NULL CHECK (status IN ('active', 'revoked', 'archived')),
	added_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	removed_at TIMESTAMPTZ,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	CONSTRAINT memberships_tenant_user_key UNIQUE (tenant_id, user_id),
	CONSTRAINT memberships_removed_after_added CHECK (removed_at IS NULL OR removed_at >= added_at)
);

CREATE TABLE xportra.exporters (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	tenant_id UUID NOT NULL REFERENCES xportra.tenants(id) ON DELETE RESTRICT,
	legal_name TEXT NOT NULL,
	trading_name TEXT,
	registration_number TEXT,
	country_of_registration TEXT,
	status TEXT NOT NULL CHECK (status IN ('active', 'inactive', 'archived')),
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	CONSTRAINT exporters_tenant_id_id_key UNIQUE (tenant_id, id)
);

CREATE UNIQUE INDEX exporters_registration_key
	ON xportra.exporters (tenant_id, registration_number)
	WHERE registration_number IS NOT NULL;

CREATE TABLE xportra.products (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	tenant_id UUID NOT NULL REFERENCES xportra.tenants(id) ON DELETE RESTRICT,
	exporter_id UUID NOT NULL,
	product_name TEXT NOT NULL,
	commodity_code TEXT,
	description TEXT,
	status TEXT NOT NULL CHECK (status IN ('active', 'inactive', 'archived')),
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	CONSTRAINT products_tenant_id_id_key UNIQUE (tenant_id, id),
	CONSTRAINT products_tenant_exporter_name_key UNIQUE (tenant_id, exporter_id, product_name),
	CONSTRAINT products_tenant_exporter_fk FOREIGN KEY (tenant_id, exporter_id)
		REFERENCES xportra.exporters (tenant_id, id) ON DELETE RESTRICT
);

CREATE TABLE xportra.destination_markets (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	tenant_id UUID NOT NULL REFERENCES xportra.tenants(id) ON DELETE RESTRICT,
	country_code TEXT NOT NULL,
	market_name TEXT NOT NULL,
	regulatory_context TEXT,
	status TEXT NOT NULL CHECK (status IN ('active', 'archived')),
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	CONSTRAINT destination_markets_tenant_country_key UNIQUE (tenant_id, country_code),
	CONSTRAINT destination_markets_tenant_id_id_key UNIQUE (tenant_id, id)
);

CREATE TABLE xportra.requirements (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	tenant_id UUID REFERENCES xportra.tenants(id) ON DELETE RESTRICT,
	requirement_code TEXT NOT NULL,
	title TEXT NOT NULL,
	description TEXT NOT NULL,
	applicability_logic_ref TEXT,
	status TEXT NOT NULL CHECK (status IN ('draft', 'active', 'superseded', 'archived')),
	effective_date DATE,
	version TEXT,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	CONSTRAINT requirements_tenant_id_id_key UNIQUE (tenant_id, id)
);

CREATE TABLE xportra.requirement_sources (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	tenant_id UUID REFERENCES xportra.tenants(id) ON DELETE RESTRICT,
	requirement_id UUID NOT NULL REFERENCES xportra.requirements(id) ON DELETE CASCADE,
	source_id UUID NOT NULL REFERENCES xportra.regulatory_sources(id) ON DELETE RESTRICT,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	CONSTRAINT requirement_sources_requirement_source_key UNIQUE (requirement_id, source_id)
);

CREATE TABLE xportra.requirement_applicability (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	tenant_id UUID NOT NULL REFERENCES xportra.tenants(id) ON DELETE RESTRICT,
	requirement_id UUID NOT NULL REFERENCES xportra.requirements(id) ON DELETE RESTRICT,
	exporter_id UUID NOT NULL,
	product_id UUID NOT NULL,
	destination_id UUID NOT NULL,
	applicability_status TEXT NOT NULL CHECK (applicability_status IN ('required', 'not_required', 'unknown', 'inactive')),
	reason_summary TEXT,
	effective_from TIMESTAMPTZ NOT NULL,
	effective_to TIMESTAMPTZ,
	version TEXT,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	CONSTRAINT requirement_applicability_context_key UNIQUE (tenant_id, requirement_id, exporter_id, product_id, destination_id),
	CONSTRAINT requirement_applicability_effective_window CHECK (
		effective_to IS NULL OR effective_to >= effective_from
	),
	CONSTRAINT requirement_applicability_exporter_fk FOREIGN KEY (tenant_id, exporter_id)
		REFERENCES xportra.exporters (tenant_id, id) ON DELETE RESTRICT,
	CONSTRAINT requirement_applicability_product_fk FOREIGN KEY (tenant_id, product_id)
		REFERENCES xportra.products (tenant_id, id) ON DELETE RESTRICT,
	CONSTRAINT requirement_applicability_destination_fk FOREIGN KEY (tenant_id, destination_id)
		REFERENCES xportra.destination_markets (tenant_id, id) ON DELETE RESTRICT
);

CREATE TABLE xportra.compliance_evidence (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	tenant_id UUID NOT NULL REFERENCES xportra.tenants(id) ON DELETE RESTRICT,
	source_id UUID REFERENCES xportra.regulatory_sources(id) ON DELETE RESTRICT,
	document_title TEXT NOT NULL,
	document_type TEXT NOT NULL,
	file_reference_or_uri TEXT NOT NULL,
	content_hash TEXT,
	status TEXT NOT NULL CHECK (status IN ('uploaded', 'reviewed', 'accepted', 'rejected', 'archived')),
	uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	CONSTRAINT compliance_evidence_tenant_id_id_key UNIQUE (tenant_id, id)
);

CREATE TABLE xportra.evidence_requirements (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	tenant_id UUID NOT NULL REFERENCES xportra.tenants(id) ON DELETE RESTRICT,
	evidence_id UUID NOT NULL,
	requirement_id UUID NOT NULL,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	CONSTRAINT evidence_requirements_key UNIQUE (tenant_id, evidence_id, requirement_id),
	CONSTRAINT evidence_requirements_evidence_fk FOREIGN KEY (tenant_id, evidence_id)
		REFERENCES xportra.compliance_evidence (tenant_id, id) ON DELETE CASCADE,
	CONSTRAINT evidence_requirements_requirement_fk FOREIGN KEY (requirement_id)
		REFERENCES xportra.requirements(id) ON DELETE CASCADE
);

CREATE TABLE xportra.certification_permit_licenses (
	id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
	tenant_id UUID NOT NULL REFERENCES xportra.tenants(id) ON DELETE RESTRICT,
	exporter_id UUID NOT NULL,
	issuing_authority_id UUID NOT NULL REFERENCES xportra.authorities(id) ON DELETE RESTRICT,
	title TEXT NOT NULL,
	issue_date DATE,
	expiry_date DATE,
	status TEXT NOT NULL CHECK (status IN ('issued', 'active', 'expired', 'revoked', 'archived')),
	document_reference TEXT,
	created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
	CONSTRAINT certification_exporter_fk FOREIGN KEY (tenant_id, exporter_id)
		REFERENCES xportra.exporters (tenant_id, id) ON DELETE RESTRICT
);

CREATE INDEX authorities_status_jurisdiction_idx ON xportra.authorities (status, jurisdiction);
CREATE INDEX regulatory_sources_authority_status_effective_idx ON xportra.regulatory_sources (authority_id, status, effective_date);
CREATE INDEX regulatory_sources_status_effective_idx ON xportra.regulatory_sources (status, effective_date);
CREATE INDEX users_status_idx ON xportra.users (status);
CREATE INDEX memberships_tenant_status_idx ON xportra.user_tenant_memberships (tenant_id, status);
CREATE INDEX memberships_user_status_idx ON xportra.user_tenant_memberships (user_id, status);
CREATE INDEX exporters_tenant_status_idx ON xportra.exporters (tenant_id, status);
CREATE INDEX exporters_tenant_legal_name_idx ON xportra.exporters (tenant_id, legal_name);
CREATE INDEX products_tenant_exporter_status_idx ON xportra.products (tenant_id, exporter_id, status);
CREATE INDEX products_tenant_name_idx ON xportra.products (tenant_id, product_name);
CREATE INDEX destination_markets_tenant_status_idx ON xportra.destination_markets (tenant_id, status);
CREATE INDEX requirements_tenant_status_effective_idx ON xportra.requirements (tenant_id, status, effective_date);
CREATE INDEX requirement_sources_requirement_source_idx ON xportra.requirement_sources (requirement_id, source_id);
CREATE INDEX requirement_sources_source_idx ON xportra.requirement_sources (source_id);
CREATE INDEX requirement_applicability_context_status_idx ON xportra.requirement_applicability (tenant_id, exporter_id, product_id, destination_id, applicability_status);
CREATE INDEX requirement_applicability_requirement_effective_idx ON xportra.requirement_applicability (tenant_id, requirement_id, effective_from);
CREATE INDEX compliance_evidence_tenant_source_status_idx ON xportra.compliance_evidence (tenant_id, source_id, status);
CREATE INDEX compliance_evidence_tenant_uploaded_idx ON xportra.compliance_evidence (tenant_id, uploaded_at);
CREATE INDEX evidence_requirements_evidence_idx ON xportra.evidence_requirements (tenant_id, evidence_id);
CREATE INDEX evidence_requirements_requirement_idx ON xportra.evidence_requirements (tenant_id, requirement_id);
CREATE INDEX certification_exporter_status_idx ON xportra.certification_permit_licenses (tenant_id, exporter_id, status);
CREATE INDEX certification_authority_idx ON xportra.certification_permit_licenses (tenant_id, issuing_authority_id);

CREATE FUNCTION xportra.set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
	NEW.updated_at = now();
	RETURN NEW;
END;
$$;

CREATE FUNCTION xportra.enforce_requirement_tenant_consistency()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
	requirement_tenant_id UUID;
BEGIN
	SELECT r.tenant_id
	  INTO requirement_tenant_id
	  FROM xportra.requirements AS r
	 WHERE r.id = NEW.requirement_id;

	IF requirement_tenant_id IS NOT NULL AND requirement_tenant_id IS DISTINCT FROM NEW.tenant_id THEN
		RAISE EXCEPTION 'requirement % belongs to tenant %, not tenant %', NEW.requirement_id, requirement_tenant_id, NEW.tenant_id;
	END IF;

	RETURN NEW;
END;
$$;

CREATE TRIGGER authorities_set_updated_at BEFORE UPDATE ON xportra.authorities FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();
CREATE TRIGGER regulatory_sources_set_updated_at BEFORE UPDATE ON xportra.regulatory_sources FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();
CREATE TRIGGER tenants_set_updated_at BEFORE UPDATE ON xportra.tenants FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();
CREATE TRIGGER users_set_updated_at BEFORE UPDATE ON xportra.users FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();
CREATE TRIGGER memberships_set_updated_at BEFORE UPDATE ON xportra.user_tenant_memberships FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();
CREATE TRIGGER exporters_set_updated_at BEFORE UPDATE ON xportra.exporters FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();
CREATE TRIGGER products_set_updated_at BEFORE UPDATE ON xportra.products FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();
CREATE TRIGGER destination_markets_set_updated_at BEFORE UPDATE ON xportra.destination_markets FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();
CREATE TRIGGER requirements_set_updated_at BEFORE UPDATE ON xportra.requirements FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();
CREATE TRIGGER requirement_applicability_set_updated_at BEFORE UPDATE ON xportra.requirement_applicability FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();
CREATE TRIGGER compliance_evidence_set_updated_at BEFORE UPDATE ON xportra.compliance_evidence FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();
CREATE TRIGGER certification_set_updated_at BEFORE UPDATE ON xportra.certification_permit_licenses FOR EACH ROW EXECUTE FUNCTION xportra.set_updated_at();

CREATE TRIGGER requirement_sources_tenant_check
	BEFORE INSERT OR UPDATE ON xportra.requirement_sources
	FOR EACH ROW EXECUTE FUNCTION xportra.enforce_requirement_tenant_consistency();
CREATE TRIGGER requirement_applicability_tenant_check
	BEFORE INSERT OR UPDATE ON xportra.requirement_applicability
	FOR EACH ROW EXECUTE FUNCTION xportra.enforce_requirement_tenant_consistency();
CREATE TRIGGER evidence_requirements_tenant_check
	BEFORE INSERT OR UPDATE ON xportra.evidence_requirements
	FOR EACH ROW EXECUTE FUNCTION xportra.enforce_requirement_tenant_consistency();

INSERT INTO xportra.authorities (id, name, jurisdiction, authority_type, status)
VALUES
	('00000000-0000-0000-0000-000000000001', 'NAFDAC', 'NG', 'government', 'active'),
	('00000000-0000-0000-0000-000000000002', 'Nigeria Customs Service', 'NG', 'government', 'active'),
	('00000000-0000-0000-0000-000000000003', 'Nigerian Export Promotion Council', 'NG', 'government', 'active'),
	('00000000-0000-0000-0000-000000000004', 'Standards Organisation of Nigeria', 'NG', 'government', 'active'),
	('00000000-0000-0000-0000-000000000005', 'Federal Ministry of Agriculture and Food Security', 'NG', 'government', 'active'),
	('00000000-0000-0000-0000-000000000006', 'Nigeria Agricultural Quarantine Service', 'NG', 'government', 'active')
ON CONFLICT (id) DO NOTHING;

COMMIT;
