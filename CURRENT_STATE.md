# CURRENT_STATE.md — Current Project State

> Source of truth for what is true about Xportra AI right now.
> Updated: 2026-09-22
> Phase: Phase 3 — Applicability Engine (Phase 3.6 complete; Phase 3.7 not started)

## Status

Harness initialization (Phase 0.1), project contract (Phase 0.2), canonical
configuration schema resolution (Phase 0.3), Python/dependency policy (Phase
0.4), the approved free-first technology baseline (Phase 0.5), and the
approved source-authority framework for regulatory provenance (Phase 0.6) are
complete and verified. Phase 1.1 through Phase 1.10 are complete for their
documented repository scope: domain model, database schema, initial migration,
persistence layer, persistence and domain-service integration, API/application
boundary, authenticated tenant identity, and tenant-role authorization.
Phase 2.1 through Phase 2.9 are complete: knowledge ingestion, artifact parsing
and normalization, regulatory document structuring, regulatory requirement
extraction, requirement applicability foundation, compliance evidence and
assessment foundation, compliance case read model, compliance decision-support
summary, and compliance risk/priority foundation. Phase 3.0 through Phase 3.6
are complete: compliance action recommendation foundation, compliance
applicability determination, applicability integration boundary,
applicability-to-risk integration, risk-to-action integration, the compliance
decision summary boundary, and the compliance case readiness boundary.
No production environment is configured.
Current verified test state: 222/222 unit tests passing, 0 failures, 0 errors.
This is the verified Phase 3.6 implementation state (20 focused Phase 3.6 tests
plus the 202-test baseline).
Phase 3.6 is complete. Phase 3.7 has not started.

## Current Domain Pipeline (through Phase 3.5)

```text
Export Case Facts
    ↓
Applicability Context
    ↓
Applicability Determination
    ↓
Risk Classification
    ↓
Action Recommendations
    ↓
Compliance Decision Summary
```

- Applicability context: `ApplicabilityContextBuilder` (Phase 3.2) translates
  existing exporter/product/destination domain facts into the minimal
  tenant-owned `ApplicabilityContext`.
- Applicability determination: `ComplianceApplicabilityService` (Phase 3.1)
  evaluates a batch of requirements over that context using the existing
  `RegulatoryRequirementApplicabilityService` (Phase 2.5).
- Risk classification: `ApplicabilityToRiskIntegration` (Phase 3.3) converts an
  applicability report into risk-service cases and delegates to the existing
  `ComplianceRiskService` (Phase 2.9).
- Action recommendations: `RiskToActionIntegration` (Phase 3.4) converts
  risk-classified cases into recommendations via the existing
  `ComplianceActionRecommendationService` (Phase 3.0), and provides the
  end-to-end `full_pipeline()` entry point.
- Decision summary: `ComplianceDecisionSummaryService` (Phase 3.5) joins the
  existing applicability, risk, and action outputs into one deterministic
  structured summary (`summarize()` for existing cases,
  `summarize_from_applicability()` for a pipeline run). It decides nothing,
  reuses the existing services, and preserves unknown/insufficient states
  explicitly.
- The pipeline is deterministic, read-only, tenant-scoped, and in-memory. It
  preserves `applicable`, `not_applicable`, and `unknown` states without silent
  conversion, performs no persistence, makes no external calls, and uses no
  retrieval, RAG, embeddings, or LLM reasoning.

## What Exists

- Reused Python virtual environment at `.venv/` (existing and left unchanged;
  no packages installed or modified for this task).
- Local `.env` file containing only canonical Xportra AI variable names.
- Canonical environment schema: `docs/architecture/environment-schema.md`.
- Repository-authoritative environment template: `.env.example`.
- Python runtime policy: `docs/architecture/python-runtime.md`.
- Repository dependency mechanism: `pyproject.toml`.
- Approved technology baseline: `docs/architecture/technology-baseline.md`.
- Approved source-authority and provenance framework: `docs/architecture/technology-baseline.md` and `docs/decisions/ADR-0003-source-authority-framework.md`.
- ADRs documenting the approved architecture decisions:
  - `docs/decisions/ADR-0001-deterministic-applicability-authoritative.md`
  - `docs/decisions/ADR-0002-free-first-technology-baseline.md`
  - `docs/decisions/ADR-0003-source-authority-framework.md`
- Project contract and architecture docs remain in place:
  - `REQUIREMENTS.md` — product identity, principles, non-goals,
    config/dependency strategy, and OQ-1/OQ-2/OQ-4 resolution plus the
    approved technology baseline.
  - `docs/architecture/configuration-contract.md` — references the canonical
    schema and remains provider-neutral.
  - `docs/architecture/dependency-strategy.md` — repository-owned dependency
    policy and rules for explicit declarations.
  - `docs/architecture/system-boundaries.md` — conceptual boundary map,
    explicitly non-implementation.
  - `docs/decisions/ADR-0001-deterministic-applicability-authoritative.md`
    — accepted decision for deterministic applicability.
- Task record: `tasks/completed/phase-0-5-technology-baseline.md`.
- Phase documentation for completed phases lives under `docs/phases/`
  (Phase 1.1 through Phase 3.4); active project-control documents remain at the
  repository root.
- Phase 1.3 implementation and live-validation record:
  `docs/phases/phase-1-3-database-implementation.md`.
- Deterministic PostgreSQL migration: `migrations/001_initial_schema.sql`.
- Deterministic rollback migration: `migrations/001_initial_schema.down.sql`.
- Database persistence package: `xportra/persistence/`.
- Phase 1.4 implementation record: `docs/phases/phase-1-4-database-persistence.md`.
- Phase 1.5 integration record:
  `docs/phases/phase-1-5-persistence-integration.md`.
- Phase 1.6 domain boundary record:
  `docs/phases/phase-1-6-domain-service-boundary.md`.
- Domain/application services: `xportra/domain/`.
- Phase 1.7 integration record:
  `docs/phases/phase-1-7-domain-service-integration.md`.
- Persistence architecture decision:
  `docs/decisions/ADR-0004-psycopg-persistence-boundary.md`.

## What Does Not Exist

- No frontend/UI, no ORM, and no replacement of the thin `psycopg` persistence
  boundary.
- The API/application layer exists (FastAPI application, authenticated tenant
  identity, tenant-role authorization) limited to the approved Phase 1.8
  through Phase 1.10 scope.
- Domain/application services exist under `xportra/domain/`.
- Database implementation exists as deterministic PostgreSQL migrations plus a
  thin `psycopg` persistence boundary. The Phase 1.3 migration has been
  applied and validated against the Supabase development/test database.
- Regulatory ingestion, parsing, normalization, structuring, requirement
  extraction, applicability, evidence assessment, case read model,
  decision-support summary, risk classification, action recommendation,
  compliance decision summary, and compliance case readiness services exist.
  Retrieval, RAG, vector databases, embeddings, chunking, reranking, LLM
  reasoning, agents, crawling, and UI do not exist.
- No provider-specific implementation details beyond the approved technology
  baseline document.
- No dependency list derived from `.venv` contents.
- No unnecessary dependencies or package installs.
- No Docker requirement and no paid observability requirement.
- No fake tests. Phase 1.4 now contains the approved persistence Python package
  and dependency-free unit tests outside `.venv`.

## Last Verified

### Phase 3.6 implementation state (2026-09-22)

- Unit suite: 222/222 tests passing, 0 failures, 0 errors — 20 new focused
  Phase 3.6 tests plus the 202-test baseline, no regressions.
- Focused Phase 3.6 tests: 20/20 passing
  (`tests/unit/test_compliance_case_readiness.py`).
- Baseline re-confirmed immediately before Phase 3.6 work: 202/202 passing.

### Phase 3.5 implementation state (2026-09-22)

- Unit suite: 202/202 tests passing, 0 failures, 0 errors — 16 new focused
  Phase 3.5 tests plus the 186-test baseline, no regressions.
- Focused Phase 3.5 tests: 16/16 passing
  (`tests/unit/test_compliance_decision_summary.py`).
- Baseline re-confirmed immediately before Phase 3.5 work: 186/186 passing.

### Phase 3.4 implementation state (2026-09-21)

- Unit suite: 186/186 tests passing, 0 failures, 0 errors — the previously
  verified state at Phase 3.4 completion. No test run was performed for this
  project-state documentation update.
- Phase 3.4 focused tests: 15/15 passing.
- Phase 3.3 focused tests: 14/14 passing; full unit regression at that point:
  171/171 passing.
- Phase 3.2 focused tests: 17/17 passing; full unit suite at that point: 157
  passing.
- Phase 3.1 focused tests: 11 passing; full unit suite at that point: 140
  passing.
- Phase 3.0 focused tests: 10 passing; full unit suite at that point: 129
  passing.
- PostgreSQL-backed integration tests were not run because `DATABASE_URL` is
  not configured in the current environment.

### Phase 0.6 verification (2026-09-19)

- Technology baseline: PASS — approved baseline and source-authority policy
  recorded in `docs/architecture/technology-baseline.md`.
- ADRs: PASS — the project documents both the free-first baseline and the
  source-authority hierarchy in ADRs.
- OQ-5: PASS — the authoritative source framework is explicitly resolved.
- Source hierarchy: PASS — primary authorities, official guidance, and
  international authorities are distinguished with jurisdictional role and
  precedence constraints documented.
- Source metadata: PASS — required source fields are documented, including
  status, effective dates, and supersession tracking.
- Origin and destination jurisdiction: PASS — both are represented
  conceptually in the architecture guidance.
- `.venv` safety: PASS — no package installation, upgrade, downgrade, or
  recreation performed.
- App code: PASS — no `.py` files were introduced outside `.venv/`.
- Secrets: PASS — no credential values were written into tracked docs.
- Docs consistency: PASS — requirements, technology baseline, and ADRs all
  agree on the approved stack, scope, and source-authority policy.

## Next

Phase 1, Phase 2, and Phase 3.0 through Phase 3.6 are complete. Phase 3.6 is
complete and Phase 3.7 has not started. Any next step must first be defined in
`REQUIREMENTS.md` and scheduled through `tasks/` and `ACTIVE_TASK.md`; no Phase
3.7 implementation exists in the repository. Retrieval, RAG, embeddings, vector
search, LLM reasoning, and agents are not implemented and must not be treated
as existing.

## Phase 2.2 — Artifact Parsing & Normalization (Complete, 2026-09-21)

- The parsing and normalization boundary turns accepted regulatory artifacts into
  a stable, deterministic document representation without introducing retrieval,
  chunking, or compliance reasoning.
- `ArtifactParsingService` accepts only `text/plain`, `text/markdown`, and
  `application/json`, and explicitly rejects unsupported, malformed, unreadable,
  or empty content.
- `ArtifactNormalizationService` preserves artifact/source provenance while
  producing a normalized text plus lightweight structure (`heading` and
  `section` blocks where available).
- A new `xportra.regulatory_document_normalizations` table persists the
  normalized output with one-to-one uniqueness per artifact and direct artifact
  and source provenance.
- Idempotency is enforced by returning the existing normalized row for an
  artifact and by enforcing a unique artifact constraint.
- Shared regulatory data remains separate from tenant-owned data; this phase does
  not introduce tenant-owned document processing semantics.
- Verification status: the focused Phase 2.2 tests and the complete unit suite
  both passed. PostgreSQL integration tests were not run because
  `DATABASE_URL` is not configured in the current environment.

## Phase 2.3 — Regulatory Document Structuring & Metadata Extraction (Complete, 2026-09-21)

- `RegulatoryMetadataExtractionService` converts a normalized document into
  explicit metadata without semantic inference or LLM calls.
- Supported fields include title, authority name, document type, publication
  date, effective date, reference identifier, version, jurisdiction, language,
  classification, and ordered sections.
- Classification is conservative and limited to `regulation`, `standard`,
  `guideline`, `procedure`, `notice`, `form`, or `unknown`.
- Unknown metadata remains null; invalid explicit ISO dates and insufficient
  normalized-document identity fail explicitly.
- Section structure preserves heading text, level, order, parent index, and
  associated structural text. Sections are not retrieval chunks.
- A new `xportra.regulatory_document_metadata` table stores extracted metadata
  and JSONB section structure with a unique normalized-document key.
- Provenance remains traceable as metadata -> normalized document -> acquired
  artifact -> regulatory source through existing identifiers and foreign keys.
- Verification status: focused Phase 2.3 tests passed. PostgreSQL integration
  tests were not run because `DATABASE_URL` is not configured in the current
  environment.

## Phase 2.4 — Regulatory Requirement Extraction (Complete, 2026-09-21)

- `RegulatoryRequirementExtractionService` converts structured normalized
  document sections into explicit regulatory requirement records using
  deterministic rule-based extraction only.
- Recognized requirement types include obligation, prohibition, documentation,
  procedure, threshold, inspection, certification, labeling, recordkeeping, and
  notification; unsupported or ambiguous candidates are omitted rather than
  converted into invented obligations.
- Explicit actors, threshold phrases, and condition phrases are preserved only
  when directly present in the requirement wording.
- Requirements retain normalized-document provenance and section location. The
  existing relationship preserves the chain to acquired artifact and regulatory
  source.
- `xportra.regulatory_requirements` uses deterministic UUID5 identity and unique
  document-position constraints for idempotent repeated processing.
- No applicability fields or exporter, commodity, destination, shipment, or
  compliance decisions were introduced.
- Verification status: focused Phase 2.4 tests passed and the complete unit
  suite passed. PostgreSQL integration tests were not run because
  `DATABASE_URL` is not configured in the current environment.

## Phase 2.5 — Requirement Applicability Foundation (Complete, 2026-09-21)

- `ApplicabilityContext` represents the minimum tenant-owned facts needed for
  deterministic evaluation: exporter identity, origin, destination, commodity,
  product category, actor role, and optional business characteristics.
- `RegulatoryRequirementApplicabilityService` returns only `applicable`,
  `not_applicable`, or `unknown`, with a concise deterministic explanation.
- Known destination or commodity mismatches produce `not_applicable`; missing
  facts produce `unknown`; explicit matches provide applicable evidence.
- Explicit actors and numeric thresholds are evaluated only when corresponding
  context facts are present. No facts are inferred.
- `xportra.regulatory_requirement_applicability` stores tenant-scoped results
  with unique `(tenant_id, requirement_id, context_fingerprint)` identity.
- Results remain traceable through requirement -> normalized document -> artifact
  -> regulatory source. Applicability is not treated as compliance.
- Verification status: focused Phase 2.5 tests and the complete unit suite passed.
  PostgreSQL integration tests were not run because `DATABASE_URL` is not
  configured in the current environment.

## Phase 2.6 — Compliance Evidence & Assessment Foundation (Complete, 2026-09-21)

- `EvidenceRecord` provides a minimal tenant-owned evidence reference with type,
  location, optional requirement link, status, and explicit metadata.
- `RequirementAssessmentService` evaluates only applicable requirements and
  returns `satisfied`, `not_satisfied`, or `unknown`.
- Category matching alone never satisfies a requirement. Evidence must be
  explicitly linked and marked as supporting the requirement with an accepted or
  reviewed status.
- Missing evidence and insufficient evidence remain `unknown`; rejected linked
  evidence is `not_satisfied`.
- `xportra.regulatory_requirement_assessments` stores tenant-scoped assessment
  results with deterministic evidence-state fingerprints and unique identity.
- Assessment provenance remains traceable through applicability result,
  requirement, normalized document, artifact, and regulatory source.
- Verification status: focused Phase 2.6 tests and the complete unit suite passed.
  PostgreSQL integration tests were not run because `DATABASE_URL` is not
  configured in the current environment.

## Phase 2.7 — Compliance Case Read Model (Complete, 2026-09-21)

- `ComplianceCaseService` composes existing applicability, requirement,
  assessment, and tenant evidence records into a read-only case view.
- The case exposes tenant/context identity, requirement details, applicability and
  assessment states/reasons, linked evidence references, regulatory source and
  document metadata references, timestamps, and provenance IDs.
- Existing states are preserved: unknown applicability does not become satisfied,
  not-applicable remains not-applicable, and missing assessment remains unknown.
- Tenant mismatches across applicability, assessment, and evidence records are
  rejected. Shared regulatory data is referenced through existing IDs.
- No new persistence table was added; the service composes existing records in
  memory to avoid duplicating regulatory data.
- Verification status: focused Phase 2.7 tests and the complete unit suite passed.
  PostgreSQL integration tests were not run because `DATABASE_URL` is not
  configured in the current environment.

## Phase 2.8 — Compliance Decision-Support Summary (Complete, 2026-09-21)

- `ComplianceSummaryService` summarizes existing compliance cases for an exporter.
- Outcome counts (total applicable, satisfied, not_satisfied, unknown) are exposed.
- Not-applicable cases are excluded from applicable totals.
- Missing evidence and unknown applicability are visible for review.
- Affected requirements preserve source/document references and provenance.
- Tenant isolation is enforced for the case set.
- Summary output is deterministic and read-only.
- Verification status: focused Phase 2.8 tests passed. Full unit regression passed.
  PostgreSQL integration tests were not run because `DATABASE_URL` is not
  configured in the current environment.

## Phase 2.9 — Compliance Risk & Priority Foundation (Complete, 2026-09-21)

- `ComplianceRiskService` classifies applicable compliance cases into attention levels
  based only on existing case state, without changing underlying regulatory,
  applicability, or assessment outcomes.
- `high` → `not_satisfied` assessment
- `medium` → `unknown` with missing required evidence
- `low` → `satisfied` assessment
- `unknown` → `unknown` without sufficient evidence
- `not_applicable` → excluded from risk classification
- Each classification includes a deterministic explanation showing which existing
  state produced it
- Affected requirements preserve source/document references and provenance
- Tenant isolation is enforced for the case set
- Summary output is deterministic and read-only
- Verification status: focused Phase 2.9 tests and the complete unit suite passed.
  PostgreSQL integration tests were not run because `DATABASE_URL` is not
  configured in the current environment.

## Phase 2.1 — Knowledge Ingestion Foundation (Complete, 2026-09-21)

- The ingestion foundation establishes the controlled boundary between an
  authoritative regulatory source, the actual acquired artifact, and later
  parsing/indexing/retrieval stages.
- `Authority` and `RegulatorySource` remain distinct from the concrete acquired
  artifact record, preserving the approved provenance hierarchy.
- A new minimal `xportra.regulatory_source_artifacts` table preserves:
  - source ID
  - artifact URI
  - content hash
  - content type and size
  - acquisition channel
  - acquired-by metadata
  - acquisition timestamp
  - source version
  - validation notes
  - status
- The minimal `SourceAcquisitionService` validates required metadata before
  persistence and rejects incomplete or invalid acquisition records.
- Historical artifacts are not silently overwritten; each acquisition is kept as a
  separate artifact record with provenance and version metadata.
- Shared regulatory data remains separate from tenant-owned data, preventing
  tenant-specific contamination of the authoritative knowledge layer.
- Verification status: Phase 2.1 unit tests passed, and the full unit suite
  remained green after the change. PostgreSQL integration tests were not run
  because `DATABASE_URL` is not configured in the current environment.

## Phase 1.10 — Authorization & Tenant Role Boundary (Complete, 2026-09-21)

- Role-aware authorization is enforced at the API/application boundary using the
  existing `user_tenant_memberships.role` field.
- `MemberContext` resolves a tenant-scoped `TenantContext` together with the
  active membership role from server-side membership data.
- The initial policy is intentionally minimal and extensible:
  - `owner` may perform all current tenant operations.
  - `member` may read tenant-owned records and create/associate compliance
    evidence.
  - `member` is denied exporter, product, destination-market, and certification
    creation.
  - unknown or missing roles fail closed with generic `403 permission_denied`.
- The isolated non-production development header remains available only outside
  production and resolves to a synthetic server-side `owner` role.
- Authorization is enforced before domain services are invoked; domain services
  continue receiving only `TenantContext`.
- The role model remains intentionally small and does not introduce enterprise
  RBAC, permission tables, or resource ACLs.
- Verification status: Python unit tests passed; database-backed integration
  suites were exercised where `DATABASE_URL` was configured and are otherwise
  explicitly skipped when the environment is not available.

## Phase 1.1 — Domain Model Definition (Approved, 2026-09-19)

- Canonical domain model design recorded in `domain-model.md`.
- Phase 1.1 design summary recorded in
  `docs/phases/phase-1-1-domain-model.md`.
- This task defines the core domain concepts, tenant boundaries, provenance
  requirements, and business invariants without implementing database tables,
  migrations, ORM models, APIs, or application code.
- The domain model remains intentionally minimal and production-oriented,
  and it is scoped to the established Phase 0 architecture.

## Phase 1.2 — Database Architecture & Schema Design (Approved, 2026-09-19)

- Relational database architecture and canonical schema design recorded in
  `database-schema.md`.
- Phase 1.2 summary recorded in `docs/phases/phase-1-2-database-schema.md`.
- The requirement-tenancy decision remains explicitly deferred; the design uses
  a provisional nullable `tenant_id` placeholder rather than resolving whether
  requirements are global or tenant-local.
- The design records a migration strategy in architectural order and
  dependency order, without creating migration files or implementation code.
- This task translates the approved domain model into a PostgreSQL design
  that preserves tenant isolation, source provenance, referential integrity,
  and historical status tracking without introducing migrations, ORM models,
  or application logic.
- The design remains intentionally limited to architecture and schema design.

## Phase 1.3 — Database Implementation & Initial Migration (Implementation, 2026-09-19)

- The approved Phase 1.2 schema is implemented in
  `migrations/001_initial_schema.sql`.
- Rollback is implemented in `migrations/001_initial_schema.down.sql`.
- The migration creates the 14 approved tables, primary and foreign keys,
  composite tenant-aware foreign keys, checks, lifecycle fields, timestamps,
  indexes, update timestamp triggers, and deferred-requirement consistency
  triggers.
- Only the six already-defined Nigerian authority reference records are
  seeded; no regulatory source or tenant-owned records are seeded.
- Requirement tenancy remains explicitly deferred. The implementation does
  not select global or tenant-local requirements.
- Live Supabase development/test validation passed: 14 expected tables, 26
  foreign keys including 6 composite tenant-aware keys, 13 unique constraints,
  17 check constraints, all 25 migration-defined named indexes, 15 triggers,
  six deterministic authorities, tenant-isolation rejection tests, rollback,
  and re-migration.
- The first live application exposed a missing `UNIQUE (tenant_id, id)` key on
  `products` required by its approved composite foreign key. PostgreSQL rolled
  back the failed transaction; the migration was minimally corrected and all
  validation was rerun successfully.
- Phase 1.3 is complete. Supabase is a development/test database only; no
  production environment is configured.

## Phase 1.4 — Database Access & Persistence Layer (Implemented, 2026-09-19)

- PostgreSQL access uses the explicitly declared `psycopg` 3 driver.
- `DatabaseSettings` reads `DATABASE_URL`; `Database` manages short-lived
  connections and explicit transaction scopes.
- `TenantContext` is required by tenant-owned repository operations.
- Repositories cover all approved core entities and explicit association
  tables without adding domain entities or resolving deferred decisions.
- Integrity failures retain their original database exception as the cause.
- Five dependency-free unit tests pass. Live PostgreSQL migration validation
  is recorded in the Phase 1.3 section above.
- Phase 1.4 implementation is complete for the available repository scope.
  PostgreSQL integration validation is recorded in the Phase 1.5 section.

## Phase 1.5 — Persistence Integration & Domain Integrity Tests (Complete, 2026-09-19)

- Six live integration tests passed against Supabase PostgreSQL using the
  existing `psycopg` persistence layer and repositories.
- Tenant-scoped retrieval, cross-tenant rejection, referential integrity,
  association operations, uniqueness/status/date constraints, transaction
  commit/rollback, connection cleanup, and post-failure connection reuse were
  verified.
- Existing unit tests also pass: 5 tests.
- Cleanup checks confirmed zero Phase 1.5 test tenants, users, or requirements
  remained in the development/test database.
- Requirement tenancy and all other documented deferred decisions remain
  unresolved by design.
- Supabase remains a development/test environment only. Phase 1.6 must not
  begin.

## Phase 1.6 — Domain Service & Business Rule Boundary (Complete, 2026-09-19)

- Domain services under `xportra/domain/` coordinate approved persistence
  operations while requiring explicit tenant context.
- Service-level preconditions cover same-tenant exporter/product ownership,
  context-bound applicability, required evidence associations, and required
  exporter/authority references for certifications.
- Database-owned constraints remain in PostgreSQL; persistence owns SQL,
  transactions, and integrity-error capture.
- Atomic evidence-plus-requirement recording uses one persistence transaction.
- Seven domain-service unit tests pass. Requirement tenancy and all other
  deferred decisions remain unresolved by design.
- No API, authentication, authorization, RAG, LLM, ingestion, retrieval,
  deployment, or new domain entity was added in Phase 1.6. (API, authentication,
  and authorization were subsequently added in Phase 1.8 through Phase 1.10;
  RAG, LLM, retrieval, and ingestion remain outside Phase 1.)

## Phase 1.7 — Domain Service Integration & Integrity Validation (Complete, 2026-09-19)

- Eight live integration tests passed against Supabase PostgreSQL through the
  `TenantContext -> domain service -> repository -> PostgreSQL` path.
- Tenant isolation, business-rule preconditions, evidence associations,
  certification validation, persistence-error translation, transaction
  atomicity, connection reuse, and deterministic cleanup were verified.
- Existing Phase 1.5 live integration tests passed: 6 tests.
- Existing unit tests passed: 12 tests total across domain services and
  persistence.
- Final cleanup reported zero Phase 1.7 tenants, exporters, products,
  destinations, evidence, certifications, or requirements.
- Requirement tenancy and all other deferred decisions remain unresolved by
  design. (At the time of Phase 1.7 completion the next phase was not yet
  authorized; Phase 1.8 through Phase 1.10 have since been completed.)

## Phase 3.0 — Compliance Action Recommendation Foundation (Complete, 2026-09-21)

- `ComplianceActionRecommendationService` translates existing applicability,
  assessment, evidence, and risk state into a possible exporter next action
  without changing any underlying compliance outcome.
- Recommendation rules: `not_satisfied` → `address_requirement`, `unknown` +
  missing evidence → `provide_missing_evidence`, `unknown` without sufficient
  evidence → `review_requirement`, `satisfied` → `no_action_required`,
  `not_applicable` → excluded.
- Where applicability is `unknown`, the recommendation is conservative:
  `review_requirement`.
- Output includes `action_type`, `explanation`, `risk_state`, and full
  provenance links.
- Tenant isolation is enforced across the full case set.
- Output is deterministic and read-only.
- Verification status: focused Phase 3.0 tests (10) and the complete unit suite
  (129) passed. PostgreSQL integration tests were not run because
  `DATABASE_URL` is not configured in the current environment.

## Phase 3.1 — Compliance Applicability Determination (Complete, 2026-09-21)

- `ComplianceApplicabilityService` evaluates a batch of compliance requirements
  against a single `ApplicabilityContext` and produces a structured applicability
  report.
- Each requirement is evaluated independently using the existing
  `RegulatoryRequirementApplicabilityService`.
- Results preserve the distinction between `applicable`, `not_applicable`, and
  `unknown`.
- The report includes counts per outcome, a deterministic context fingerprint,
  and the individual applicability results.
- No new applicability rules, persistence, or regulatory interpretation were
  introduced.
- Verification status: focused Phase 3.1 tests (11) and the complete unit suite
  (140) passed. PostgreSQL integration tests were not run because
  `DATABASE_URL` is not configured in the current environment.

## Phase 3.2 — Applicability Integration Boundary (Complete, 2026-09-21)

- `ApplicabilityContextBuilder` translates existing export-case/domain facts
  (exporter identity and country of registration, product commodity code and
  description, destination country, actor role, business characteristics) into
  the minimal tenant-owned `ApplicabilityContext` consumed by applicability
  determination.
- Missing facts remain `None`; the builder never invents or defaults a missing
  value. Exporter name prefers `legal_name` over `trading_name`, and
  `actor_role` defaults to `"exporter"`.
- Tenant identity is validated as a required UUID and propagated directly, so a
  context built for one tenant cannot become associated with another tenant.
- Construction is deterministic: identical input produces identical output.
- No persistence, retrieval, RAG, embeddings, or external regulatory API
  integration was introduced.
- Verification status: focused Phase 3.2 tests (17) passed and the complete unit
  suite (157) passed. PostgreSQL integration tests were not run because
  `DATABASE_URL` is not configured in the current environment.

## Phase 3.3 — Applicability-to-Risk Integration (Complete, 2026-09-21)

- `ApplicabilityToRiskIntegration.classify_from_applicability()` converts an
  applicability report produced by `ComplianceApplicabilityService` into the
  case format expected by the existing `ComplianceRiskService`, and delegates
  all classification to that service without duplicating risk logic.
- Translated cases carry the report's applicability outcome, requirement
  identity, an explicit `unknown` assessment ("assessment not yet performed"),
  and no evidence; no assessment is invented and no evidence is inferred.
- `applicable`, `not_applicable`, and `unknown` outcomes are preserved.
  Not-applicable and unknown applicability produce no risk row under the
  existing risk-service semantics, and unknown is never silently treated as
  applicable or not_applicable.
- Tenant identity is validated (required UUID and must match the report tenant)
  and written into every constructed case, so risk results cannot cross tenant
  boundaries.
- Output is deterministic; no persistence, external calls, LLM, RAG, retrieval,
  embeddings, or vector database operations were introduced.
- Verification status: focused Phase 3.3 tests (14) passed and the complete unit
  regression (171) passed. PostgreSQL integration tests were not run because
  `DATABASE_URL` is not configured in the current environment.

## Phase 3.4 — Risk to Action Integration (Complete, 2026-09-21)

- `RiskToActionIntegration` establishes the deterministic boundary between risk
  classification and action recommendation, completing the Applicability → Risk →
  Action pipeline.
- The service delegates all action recommendation logic to the existing
  `ComplianceActionRecommendationService` without duplicating logic.
- Two methods are provided: `recommend_from_risk()` for direct risk-to-action
  conversion, and `full_pipeline()` for end-to-end Applicability → Risk → Action
  execution.
- Explicit unknown-state handling preserves unknown/insufficient states without
  silent conversion; unknown assessments never become satisfied or not_satisfied.
- Tenant identity is validated and preserved throughout the entire pipeline;
  results from one tenant cannot leak to another.
- Output is deterministic: identical input always produces identical output,
  actions are ordered by requirement ID, and explanations are fixed strings.
- No persistence, external API calls, LLM, RAG, retrieval, embeddings, or vector
  database operations are introduced.
- Verification status: focused Phase 3.4 tests passed (15/15), full unit suite
  passed (186/186), no regressions detected.
- PostgreSQL integration tests were not run because `DATABASE_URL` is not
  configured in the current environment.

## Phase 3.5 — Compliance Decision Summary (Complete, 2026-09-22)

- `ComplianceDecisionSummaryService` condenses the existing Applicability →
  Risk → Action outputs into a single structured, tenant-scoped Compliance
  Decision Summary for future application/API layers. It is an
  orchestration/representation boundary only: it decides nothing and reuses
  `ComplianceRiskService` (risk), `RiskToActionIntegration` /
  `ComplianceActionRecommendationService` (actions), and the applicability
  data already carried by cases and reports.
- Two entry points: `summarize()` for existing compliance cases, and
  `summarize_from_applicability()` which runs the existing Phase 3.4
  `full_pipeline()` and takes applicability from the report itself.
- The summary represents tenant identity, context fingerprint, applicability
  results and counts, risk classification results with per-state counts,
  action recommendations with per-type counts, per-requirement rows joining
  applicability/assessment/evidence presence/risk state/action type, and an
  explicit `unknown_states` list.
- Unknown/insufficient states are preserved, never converted: applicability
  `unknown` remains `unknown`, assessment `unknown` remains `unknown`, missing
  evidence is reported as `missing_evidence`, unknown risk state is reported
  as `risk_unknown`, and recommendations from the existing action logic are
  passed through unmodified. A pure applicability report carries no assessment
  or evidence, so those fields remain `None` rather than assumed.
- Output is deterministic: identical input produces an identical summary, and
  every section (applicability, risk, actions, requirement rows,
  unknown_states) is ordered by requirement ID.
- No persistence, external calls, LLM, RAG, retrieval, embeddings, vector
  operations, new rules, new risk levels, or new action types were introduced.
  Two latent dict-shape assumptions in `RiskToActionIntegration` were hardened
  defensively (non-dict `requirement` payloads) without behavior change.
- Verification status: focused Phase 3.5 tests passed (16/16), full unit suite
  passed (202/202) against the 186-test baseline, no regressions.
- PostgreSQL integration tests were not run because `DATABASE_URL` is not
  configured in the current environment.

## Phase 3.6 — Compliance Case Readiness / Evidence Coverage (Complete, 2026-09-22)

- `ComplianceCaseReadinessService` evaluates whether existing compliance cases
  carry sufficient known information to support the current Applicability →
  Risk → Action pipeline, exposing evidence/readiness gaps explicitly so future
  retrieval/RAG work can target them. It is a representation/readiness boundary
  only.
- Readiness is information sufficiency, not a compliance verdict: `ready` does
  not mean compliant and `not_ready` does not mean non-compliant. The report
  states this explicitly via a `readiness_not_compliance` field, and no
  compliance verdicts were introduced.
- Exactly three readiness states: `ready` (no missing information),
  `partially_ready` (missing assessment/evidence/risk information but all
  applicability known), `not_ready` (no cases supplied, or any unknown
  applicability). `not_applicable`, `unknown`, and missing evidence remain
  distinct and are never conflated.
- Gap kinds reuse the Phase 3.5 vocabulary: `applicability_unknown`,
  `assessment_unknown`, `missing_evidence`, `risk_unknown`. Missing facts are
  never invented and unknown requirements are never inferred as satisfied or
  unsatisfied.
- Report contains tenant identity, context fingerprint, readiness state,
  required/known/missing information counts, the ordered gap list, per-category
  requirement lists (unknown applicability, unknown assessment, missing
  evidence, unknown risk), and actions requiring evidence derived from the
  existing recommendation output.
- Risk classification and action recommendation are delegated to the existing
  `ComplianceRiskService` and `RiskToActionIntegration`; missing-evidence
  detection reuses the existing risk-service semantics. No applicability, risk,
  or action rule was reimplemented.
- Determinism: identical input produces an identical report; requirements and
  gaps are ordered by requirement ID; counts are reproducible. Empty input is
  handled deterministically (`not_ready` with zero counts).
- Tenant handling: a valid tenant UUID is required, tenant identity is
  preserved in the report, and cases from a different tenant are rejected.
- No persistence, external calls, LLM, RAG, retrieval, embeddings, vector
  operations, API endpoints, UI, crawling, connectors, reranking, agents, or
  automated compliance verdicts were introduced.
- Verification status: focused Phase 3.6 tests passed (20/20), full unit suite
  passed (222/222) against the 202-test baseline, no regressions. The
  `xportra/domain/ingestion.py` change is purely additive (231 insertions, 0
  deletions); existing services were not modified.
- PostgreSQL integration tests were not run because `DATABASE_URL` is not
  configured in the current environment.