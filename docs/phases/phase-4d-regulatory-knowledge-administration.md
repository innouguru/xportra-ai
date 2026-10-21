# Phase 4D — Regulatory Knowledge Administration

- **Status:** Planning approved; pilot direction agreed; implementation and
  exporter-facing publication remain unauthorized.
- **Scope source:** Proposed R-4D in `REQUIREMENTS.md`.
- **Architecture:** ADR-0017 accepted as the basis for implementation
  planning only; its open implementation contracts remain unresolved.
- **Purpose:** Establish a bounded first release for the shared regulatory
  knowledge administration workspace and its exporter-facing publication
  boundary.

No Phase 4A–4C assessment records were found in the repository during this
planning task. Earlier assessment findings are therefore not treated as
repository-authoritative records. The implementation plan below is based on
the currently inspected schema and code, and must be revalidated when its
tasks are approved.

## Proposed first-release scope

Authorized Xportra knowledge staff manage shared authorities and sources,
submit a limited set of supported regulatory document formats, inspect
durable ingestion outcomes, review source-backed extracted candidates, and
control publication and re-review. Exporters see only published requirements
that have been deterministically evaluated against known shipment facts.
Unknown facts and incomplete catalog coverage remain visible as unknown or
incomplete; neither is a negative compliance determination.

The product owner has agreed with the planning direction recorded in
[`phase-4d-2-sesame-eu-pilot-product-owner-decisions.md`](./phase-4d-2-sesame-eu-pilot-product-owner-decisions.md):
raw/unprocessed sesame seeds (*Sesamum indicum*) for human consumption,
originating in Nigeria, with Kano and Jigawa as operational sourcing regions,
for consignments intended for import and customs clearance in the Netherlands.
Product classification, actual first EU entry/BCP/transit route, and shipment
applicability remain unresolved. This direction does not claim legal approval,
certification, government endorsement, or export clearance. See
[`phase-4d-1-sesame-eu-pilot-source-research.md`](./phase-4d-1-sesame-eu-pilot-source-research.md)
and [`phase-4d-4-pilot-scope-and-implementation-readiness.md`](./phase-4d-4-pilot-scope-and-implementation-readiness.md)
for source-by-source retrieval evidence and unresolved legal/applicability
questions.

The agreed governance direction requires two distinct auditable decisions
before an item is presented as applicable to exporters: Stage A human
verification of provenance, wording, and interpretation; then Stage B
approval of applicability to the defined pilot scope. Neither decision is
implemented by this proposal, and neither creates a shipment clearance.

### Proposed exclusions

- Broad multi-country coverage, crawling, arbitrary URL fetching, and
  automatic source discovery.
- Image, OCR, scanned-document, and unsupported binary parsing in the first
  cut. Staff-upload-only intake is agreed; the exact text-format set is
  pending architecture approval. Existing regulatory parsing supports
  text/plain, Markdown, and JSON, not PDF. PyMuPDF is a possible PDF
  extraction option, not an implementation. The separate exporter evidence
  PDF/DOCX/image path is not a regulatory source-ingestion capability.
  Parser-interface, dependency, and PDF safety verification remain required
  before implementation.
- Automatic legal interpretation, automatic publication, or an LLM as the
  applicability authority.
- Organization-managed and buyer-specific rules in the shared regulatory
  catalog or first-pilot schema/API/UI. This capability is deferred; if later
  approved, it must be a separate, tenant-isolated category and must not be
  presented as official law.
- A self-service global administrator provisioning UI.
- Production ingestion or changes to deployed services as part of this
  planning proposal.

## Repository evidence used for planning

- Canonical requirements and source associations are in
  `migrations/001_initial_schema.sql`; source and requirement lifecycle
  fields exist but there is no complete source-administration workflow.
- Regulatory artifact, normalization, metadata, extracted-candidate, and
  applicability structures exist in migrations `003`–`007`. Extracted
  candidates use a distinct `regulatory_requirements` table and do not have a
  complete review/publication lifecycle.
- `xportra/domain/ingestion.py` contains source acquisition, parsing,
  normalization, metadata extraction, candidate extraction, applicability,
  and assessment services. These services are not composed into an
  end-to-end regulatory administration API.
- `xportra/persistence/repositories.py` provides some regulatory reads and
  writes but not a complete ingestion-attempt, retry, review, and publication
  workflow.
- Source and authority repositories currently expose reads; the acquisition
  service validates and records artifact metadata but does not itself retain
  uploaded bytes or create a durable processing job.
- `xportra/api/authorization.py` and `xportra/api/auth.py` enforce
  tenant-membership roles (`owner` and `member`); there is no separate global
  regulatory-administrator permission.
- The exporter assessment path accepts requirements as input and evaluates
  them deterministically; it does not load an approved published catalog.
  The current evaluator covers limited destination, commodity, actor, and
  quantity facts, not the full sesame classification/route/legal scope.
  `regulatory_requirement_applicability` is proposed as the authoritative
  persisted runtime evaluation-result model because its
  `RegulatoryRequirementApplicabilityService` evaluates extracted candidates
  and the model stores a context fingerprint, outcome, reason, and context.
  Persistence is optional in that service and is not wired into the current
  assessment API. Its current foreign key targets extracted candidates, so
  canonical linkage and pilot-scope versioning need an additive migration.
  `requirement_applicability` remains a distinct
  tenant-owned exporter/product/destination record and is not repurposed or
  dropped. Stage B publication approval remains append-only governance
  history, not an evaluator outcome or a third applicability table.
  The exporter Requirements page includes editable requirements and is not a
  published-catalog view.
- ADR-0001 establishes deterministic applicability, not LLM reasoning, as
  authoritative. ADR-0011 establishes an evidence-upload ingestion boundary;
  it does not by itself authorize reusing tenant evidence storage for shared
  regulatory artifacts.

## Architecture planning basis and implementation status

The eight product-owner directions consolidated in Phase 4D.7 are recorded
in [ADR-0017](../decisions/ADR-0017-regulatory-knowledge-administration.md)
and remain the governing planning requirements. ADR-0017 is accepted as the
basis for implementation planning only. This does not accept unmade technical
choices, close legal or pilot-scope gates, or authorize implementation or
publication. No separate Phase 4D.7 decision file was found or created.

The accepted planning basis establishes direction for operator-managed
global grants, separate runtime and Stage B governance records,
independently authorized review,
durable background ingestion, stale-source restriction with preserved
history, qualified partial/unknown/incomplete outcomes, original artifact
and version retention, and manual candidate recovery after extraction
failure. Their technical realization remains subject to the open choices
below.

| Decision | Repository evidence | Accepted planning direction / proposed realization | Status / remaining choices |
|---|---|---|---|
| Global administrator authorization | Only tenant roles are present; no global knowledge-admin permission was found. | Add server-side grants for designated Xportra staff, separate from tenant membership, and enforce deny-by-default checks on every protected operation. Never infer global authority from tenant ownership. | Planning direction accepted; grant bootstrap, trusted-operator boundary, mechanism, and audit owner remain open. |
| Two-stage review and publication governance | Candidate status only includes extracted/rejected/archived; no verification, applicability-approval, or audit trail exists. | Stage A verifies source, provenance, wording, and interpretation. Stage B separately approves applicability to the defined pilot scope. Record distinct permissions, actor, timestamp, rationale, source/scope version, and transitions. Prefer different people; explicitly audit any controlled small-team exception. | Planning direction accepted; permission assignment, exception controls, and persistence contract remain open. |
| Ingestion execution | Regulatory parsing/extraction services are currently synchronous; no durable job, worker, scheduler, or queue was found. The Render deployment audit records one long-lived web process, ephemeral local filesystem, and no Dockerfile/`render.yaml`. | Persist original artifact and durable job before starting durable background processing. Support restart recovery, idempotency, retry, visible failures, and attempt history. Select no worker/queue/paid service until Render, budget, no-Docker, and operations constraints are assessed. | Durable background direction accepted; mechanism, limits, and ownership remain open. |
| Input methods and formats | Regulatory parser supports text/plain, Markdown, and JSON; it does not support PDF. The separate evidence path has custom PDF text extraction. PyMuPDF is not declared in `pyproject.toml` or integrated into the regulatory parser. | Staff upload only; record official URLs as metadata, do not retrieve them. Support PDF only after parser-interface, library, safety, and page-provenance review; no OCR or crawling unless separately approved. | Upload-only and no retrieval accepted; exact formats and PDF implementation gate remain open. |
| Artifact identity, retention, and provenance | Regulatory artifact records can hold metadata/URI, but the current acquisition service does not persist raw bytes or compute content hash itself. Runtime local filesystem is ephemeral per the Render deployment audit. | Store immutable artifacts in private durable storage; preserve source/version, content hash, actor, acquisition time, parser version, normalized artifact, candidate location, and prior review/publication history. New versions never overwrite or inherit approvals. | Retention direction accepted; backend, duration, deletion, legal hold, and costs remain open. |
| Candidate-to-canonical linkage | Extracted candidates and canonical `requirements` are separate; `requirement_sources` links canonical requirements to sources but not candidate locations. | Keep candidate wording and source location immutable; explicitly and audibly associate verified candidate(s) with canonical requirements. Add linkage only if current structures cannot express this provenance. | Planning direction accepted; exact association/cardinality requires schema review. |
| Applicability | ADR-0001 and `ComplianceApplicabilityService` establish a deterministic foundation with limited current matching, not full pilot coverage. `RegulatoryRequirementApplicabilityService` supports optional persistence to `regulatory_requirement_applicability`; the current assessment API does not wire that repository and still accepts caller-supplied records. `requirement_applicability` is a separate tenant/exporter/product/destination record with its own service. Neither is shared publication approval. | Select `regulatory_requirement_applicability` as the persisted runtime evaluation-result model, after additive canonical-requirement linkage and scope-version support. Keep Stage B decision history separate; preserve `requirement_applicability` for its distinct tenant workflow. Do not add a third applicability table or evaluator. | Planning architecture accepted; additive schema, linkage, consumers, and scope identity remain to be verified. |
| Organization/buyer requirements | Existing tenant records do not provide a reviewed organization-specific regulatory workflow. | Defer organization-managed schema/API/UI from the pilot. If later approved, introduce a clearly separated, tenant-isolated extension that cannot be confused with official law. | Pilot deferral accepted; any later extension requires separate scope and isolation approval. |
| Source changes and re-review | Source version/status and acquisition metadata exist, but no workflow flags affected canonical requirements for review. | Resolve changed sources to affected candidates, canonical requirements, and published applicability decisions. Restrict affected records from current applicable use until re-review; preserve history. Do not declare linked rules legally invalid solely from a source flag. | Restriction and preservation direction accepted; freshness thresholds and impact semantics remain open. |
| Exporter visibility | No published-catalog endpoint was found; current assessment requirements are caller-supplied. | Expose only current eligible canonical requirements; distinguish unknown/missing facts, incomplete coverage, stale/re-review, and unverified material. A qualified partial result requires defensible verified requirements in supported scope; otherwise reject unsupported requests. An absent record never proves no requirement. | Principles accepted for planning; state vocabulary, rejection boundary, API contract, and copy remain open. |

## Phase 4D.10 — Sequenced implementation planning

This is the authoritative, repository-grounded dependency breakdown. It
does not authorize implementation, production changes, or exporter-facing
publication. Every implementation task requires separate explicit
authorization and a bounded active task. The eight Phase 4D.7 directions
remain governing requirements; open technical choices and qualified
legal/pilot-scope gates remain at the task gates below.

### Task 1 — Finalize implementation contracts and unresolved decisions

- **Objective/scope:** Resolve the trusted operator boundary, grant and
  revocation process, permission/audit model, additive schema and canonical
  linkage, versioned pilot scope, durable dispatch/recovery, artifact
  retention/deletion, accepted formats, and extraction limits. Do not reopen
  settled product-owner directions.
- **Reuse / expected surfaces:** ADR-0017; existing auth, migrations,
  ingestion, private-storage, Render deployment, and requirements evidence.
  Expected changes are decision/requirements/task records and verified
  operational evidence only; no runtime path is presumed.
- **Dependencies / decisions:** 
  - **Decision A (Global regulatory-administrator authorization):** Bootstrap 
    trusted operator boundary, grant/revocation mechanism, audit storage, and 
    fail-closed checks. Owner: security/identity. Risk: privilege escalation, 
    tenant-role leakage, bootstrap lockout. 
  - **Decision B (Applicability schema and canonical linkage):** Additive 
    linkage model between `regulatory_requirement_applicability` and canonical 
    requirements, scope-version identity, and consumer contract. Owner: data/model. 
    Risk: broken history, duplicate/stale results, coupled approval. 
  - **Decision C (Durable background processing):** Persistence contract for 
    original artifact + durable job before dispatch, idempotency key, attempt 
    lineage, failure recording, restart recovery. Owner: operations/deployment. 
    Risk: orphan jobs/objects, unbounded cost, reliance on ephemeral filesystem. 
  - **Decision D (Artifact retention, deletion, and supported formats):** 
    Supported upload formats (text/plain, Markdown, JSON confirmed; PDF pending 
    parser review), private storage model, access controls, retention/deletion 
    policy unresolved. Owner: product/legal. Risk: public exposure, unbounded 
    cost, regulatory PDF claim without evidence. 
  - **Decision E (Task dependencies and authorization gates):** Mapping of 
    which decisions block which later tasks, owner/approval needs, and 
    resolution timing. Owner: program management.
- **Risks:** Unverified hosting assumptions, unbounded retention, non-additive 
  schema, expanding claims beyond legal evidence, privilege escalation, tenant- 
  role leakage, bootstrap lockout, orphan jobs/objects, public exposure, 
  regulatory PDF claim without evidence.
- **Acceptance / verification:** Each open choice is selected or explicitly 
  deferred with owner, rationale/evidence, affected tasks, and measurable 
  acceptance criteria; no paid service is assumed and all eight Phase 4D.7 
  directions remain intact. Review decision records and run documentation 
  consistency checks. Decision table (see below) confirms blocker status and 
  resolution requirements for each task.
- **Exit / next / authorization:** Gates Tasks 2–10. Requires separate 
  authorization; planning approval itself is not task authorization.

## Task 1 Decision Table

| # | Decision | Blocks Tasks | Later Depends On | Parallel Resolvable | Owner / Approval Needed | Resolution Timing |
|---|----------|-------------|------------------|---------------------|-------------------------|-------------------|
| A | Global regulatory-administrator authorization | 2–8 | Global grants needed for all admin operations | Can parallel B, C, D with coordination | Security/identity owner; product-owner grant/bootstrap approval | Before Task 2 starts; Task 2 explicitly enables Tasks 3–8 |
| B | Applicability schema and canonical linkage | 6, 10 | Applicability API, exporter assessment integration | Can parallel A, C, D with schema coordination | Data/model owner; product-owner approval of additive model; ADR-0017 gate | Before Task 6; Task 6 explicitly enables Tasks 7, 8, 10 |
| C | Durable background processing | 3–5, 7–10 | Task 3 jobs API, Task 4 parsing workflow, Task 5 governance | Can parallel A, B, D with ops coordination | Operations/deployment owner; Render/budget/no-Docker review; product-owner direction accepted | Before Task 3; durable direction is settled but mechanism open |
| D | Artifact retention, deletion, and supported formats | 3–5, 7–10 | Task 3 storage, Task 4 parsing, Task 5 governance | Can parallel A, B, C with product coordination | Product owner; legal/retention review; parser capability review | Before Task 3; upload-only and no-retrieval is agreed, exact limits open |
| E | Task dependencies and authorization gates | All later tasks | Task sequencing, authorization gates | N/A | Program management owner | Completed as part of Task 1 deliverable |

**Key:**
- "Blocks Tasks" = decision must be resolved before the listed tasks can proceed
- "Parallel Resolvable" = can be worked on concurrently with coordination, may have coordination overhead
- Resolution Timing = when the decision must be resolved for the dependent task to start
- All eight Phase 4D.7 directions remain intact and govern planning regardless of Task 1 resolutions

## Decision Resolutions from Repository Evidence

### A. Global regulatory-administrator authorization

**Repository evidence:** No global permission mechanism exists. `xportra/api/auth.py` and `xportra/api/authorization.py` enforce tenant-membership roles (`owner` and `member`). No server-side grants, trusted-operator boundary, or audit storage was found. ADR-0017 §1 identifies this as the top open choice.

**Proposed contract (decided from ADR-0017 + repository evidence):**
- **Initial trusted platform operator establishment:** Server-side grant model linked to existing user identity. No bootstrap UI or self-grant capability. The first grant must be created by an out-of-band process (e.g., product-owner direct database action or environment configuration) and recorded in append-only audit.
- **Who may grant/revoke:** Explicitly authorized platform operators only. Grant and revocation commands are restricted to named roles/identities approved by product owner. No inference from request data (role, tenant, identity).
- **Audit of grants, revocations, and authorization failures:** Append-only audit records identifying actor, action (grant/revoke), target permission, timestamp, and outcome (success/failure). Fail-closed: if audit storage is unavailable, the operation must deny.
- **Global administration kept separate from tenant membership:** Global grants are server-side and independently checked. Tenant `owner`/`member` roles never convey global administration access. Authorization checks first verify tenant membership, then check active global grants. Deny by default if neither holds.
- **How administration permissions differ from Stage A verification and Stage B applicability-approval permissions:** Global administration grants access to staff operations (source registration, artifact upload, ingestion management, review commands). Stage A verification and Stage B approval are separate permission sets that may be granted within global administration or independently. A global catalog-administration grant does not by itself grant Stage A or Stage B permission. Each permission type is checked independently on every protected operation.
- **What must fail closed:** Tenant owner/member calls on administrative routes without active global grant. Grant/revocation identity lookup failures. Any check where the grant state is absent, revoked, or unavailable.

**Remains open (requires future decision/approval):**
- Trusted operator boundary: how the first operator is identified and bootstrap occurs
- Grantor/revoker mechanism: whether dual-control or break-glass is needed
- Audit storage: where append-only audit records are persisted
- Incident/audit retention: how long audit records are kept
- Environment allowlist as grant mechanism: rejected (lacks per-actor revocation and audit history)

**Repository evidence supporting claims:**
- `xportra/api/auth.py` and `xportra/api/authorization.py` enforce tenant-membership roles only (ADR-0017 §67-69)
- No global permission mechanism found in repository inspection (ADR-0017 §60-62)
- ADR-0017 §110-122 proposes server-side grant model linked to user identity

### B. Applicability schema and canonical linkage

**Repository evidence:** 
- `requirement_applicability` table (migration 001): tenant_id, requirement_id, exporter_id, product_id, destination_id, applicability_status ('required'/'not_required'/'unknown'/'inactive'), reason_summary, effective_from/effective_to, version. Unique constraint on (tenant_id, requirement_id, exporter_id, product_id, destination_id).
- `regulatory_requirement_applicability` table (migration 007): stores candidate evaluation results with context fingerprint, tri-state outcome, reason, context, evaluated/archived status. `requirement_id` FK targets extracted candidate.
- `RegulatoryRequirementApplicabilityService` evaluates candidates and supports optional persistence to `regulatory_requirement_applicability`. Current assessment API does not wire that repository; accepts caller-supplied requirements.
- `requirement_applicability` is tenant/product/destination scoped; its service validates tenant resources, has no publisher/reviewer attribution.
- Neither table represents approval to publish for shared pilot catalog (ADR-0017 §73-85).

**Proposed contract (decided from ADR-0017 + repository evidence):**
- **Which model retains its existing responsibility:** `requirement_applicability` remains the tenant-owned, exporter/product/destination-scoped record for its distinct workflow. `regulatory_requirement_applicability` becomes the authoritative persisted runtime evaluation-result model for shared regulatory knowledge administration.
- **How regulatory applicability results link to canonical requirements:** Additive linkage — the `regulatory_requirement_applicability` table's `requirement_id` foreign key must reference a canonical `requirements` row (not an extracted candidate). Implementation must add a safe candidate-to-canonical linkage or equivalent additive reference before exporter assessments can use it with published canonical requirements. Existing candidate-based rows are preserved as historical data.
- **How pilot-scope versions are represented and referenced:** Pilot-scope version identity must be included in the evaluation context/fingerprint. Scope version participates in result identity: an evaluation result with a different scope version is a new result, not a reuse of the old one. Scope limitations and missing conditions remain explicit in context/reason.
- **How Stage B governance approval remains distinct from evaluator results:** Stage B approval is a governance decision recorded in append-only review history linked to the verified candidate, canonical requirement, source/artifact version, exact evidence location, actor, timestamp, rationale, and versioned pilot scope. It is NOT an evaluator outcome or a third applicability table. The runtime `applicable`/`not_applicable`/`unknown` outcomes from `regulatory_requirement_applicability` remain distinct from Stage B decisions.
- **Compatibility risks and future consumer changes:** The `requirement_applicability` table must not be repurposed, dropped, or silently renamed. Its existing service/consumers and persistence must be preserved. Any migration must preserve existing candidate foreign keys and rows, define unambiguous canonical linkage, include pilot-scope version in result identity, and avoid making stale results current after source or scope change. Migrate exporter API contract deliberately; any temporary compatibility path must be explicitly scoped, non-authoritative, and removed or gated before exporter publication.

**Remains open (requires future decision/approval):**
- Exact association granularity/ cardinality between candidates and canonical requirements during schema design
- Migration consumers and rollback behavior for the additive linkage
- Pilot-scope version contract detail (format, storage, comparison semantics)
- API compatibility window and deprecation path for existing `requirement_applicability` consumers
- Whether shipment assessment snapshots need durable persistence separate from evaluation results

**Repository evidence supporting claims:**
- Migration `001` defines `requirement_applicability` with canonical requirement, tenant exporter, product, destination, effective window, and status fields (ADR-0017 §341-344)
- Migration `007` defines `regulatory_requirement_applicability` with candidate requirement, tenant/context fingerprint, tri-state outcome, reason, context, and evaluated/archived status (ADR-0017 §346-350)
- `RegulatoryRequirementApplicabilityService` evaluates candidate semantics; supports persistence through optional repository dependency (ADR-0017 §349-350)
- ADR-0017 Decision 7: `regulatory_requirement_applicability` for runtime results; `requirement_applicability` for separate tenant workflow; no third model (ADR-0017 §297-355)

### C. Durable background processing

**Repository evidence:** No durable worker, scheduler, queue, or job record was found. Regulatory parsing/extraction currently runs through synchronous domain services. The Render deployment audit documents a single long-lived web process, ephemeral local filesystem, and no Dockerfile/`render.yaml`. The repository has no background-job primitive.

**Proposed contract (decided from ADR-0017 + repository evidence):**
- **Persist original artifact and durable job record before processing:** The original uploaded bytes and a durable job record must be committed to private storage before any background processing/dispatch begins. This ensures a crash cannot leave a request appearing successful with no recoverable work.
- **Support safe retries and idempotency:** Idempotency key bound to source and byte hash. A duplicate upload (same source, content hash) must not be silently reprocessed as a new artifact. Explicit retries create a new attempt linked to the prior attempt and same immutable artifact; they do not overwrite prior attempts or artifact bytes.
- **Record processing attempts and expose failures and partial results:** Each attempt records: attempt ID, start time, outcome (pending/processing/completed, partial/failed, completed-with-zero-candidates), safe error code/message, parser/config version, and parser section/position provenance. Failed/partial attempts remain visible and never morph into success-shaped outcomes.
- **Recover jobs after process restarts:** Jobs and artifacts must survive process restart. Pending or abandoned work must be recoverable. The recovery mechanism must distinguish unclaimed work, claimed work (with lease), and completed work.
- **Prevent duplicate processing from creating duplicate candidates or decisions:** Duplicate delivery must not create duplicate candidates or approvals. The idempotency key + artifact hash prevents re-processing. Attempt lineage links new attempts to prior attempts.
- **Preserve original artifacts and provenance:** Original bytes are stored in private durable storage with content hash. Parser version, acquisition time, and actor are recorded. Provenance survives parsing and publication.

**Remains open (requires future decision/approval):**
- Worker/queue/dispatch mechanism: no particular worker, queue, scheduler, or paid service is approved or assumed. The choice must be made after verifying Render hosting options, budget, no-Docker constraint, and operational ownership.
- Exact retry/backoff policy
- Monitoring and shutdown/recovery semantics
- Resource bounds and timeout policies
- Specific Render product or external service selection

**Repository evidence supporting claims:**
- ADR-0017 §181-215: Durable background ingestion proposal with artifact/job commit preceding dispatch
- ADR-0017 §195-202: Render deployment evidence (single web process, ephemeral filesystem, no Dockerfile/render.yaml)
- ADR-0017 §204-215: Security/data integrity requirements (idempotency key, atomic claim/lease, bounded retries)
- No durable job/worker/scheduler found in repository inspection (ADR-0017 §195-199)

### D. Artifact retention, deletion, and supported formats

**Repository evidence:**
- Regulatory parser supports `text/plain`, `Markdown`, and `JSON` only. Does not support PDF.
- PyMuPDF is mentioned in technology-baseline documentation but is not declared in `pyproject.toml` and not integrated into the regulatory parser.
- The separate evidence-upload path has custom PDF text extraction, but this is not regulatory PDF support.
- `compliance_evidence` table holds artifact URI/hash/length/type and acquisition metadata, but the schema does not establish that the URI is immutable storage or that bytes are retained.
- Existing source/artifact records provide some version/status/retrieval metadata but no complete change-to-re-review workflow.

**Proposed contract (decided from ADR-0017 + repository evidence):**
- **Original artifact preservation and version history:** Original artifacts must be retained in access-controlled regulatory-source storage. Each artifact version is immutable — new versions never overwrite or inherit approvals from prior versions. Content hash preserves byte identity. Version history is append-only and auditable.
- **Private storage and access controls:** Artifacts are stored in private durable storage with no tenant evidence download path. Access is server-enforced through authorization checks. No public or exporter-accessible path to uploaded regulatory artifacts.
- **Retention duration and deletion policy:** Retention policy remains unresolved. An explicit retention period and deletion/legal-hold rules must be approved by product owner and qualified legal review before implementation. No duration is assumed or implied.
- **Upload size/type limits and processing resource constraints:** Content-type + magic-byte validation is supported. The evidence-upload boundary established 10 MB per file server-enforced limit (Phase 10.3/U7). Exact type limits and processing resource constraints require implementation-task approval.
- **Plain text, Markdown, and JSON support:** These three formats are confirmed as supported by the regulatory parser. Upload and processing of these formats is accepted for the first pilot.
- **PDF parsing and OCR:** PDF parsing must not be assumed to exist in the regulatory parser. PDF is a capability gate: must verify the parser contract, dependency policy, parser safety limits, and page-provenance before selecting or integrating a PDF library. OCR, scanned/unreadable PDFs, and crawling are deferred; they must be separately approved and are not regulatory parsing capability in the first cut.

**Remains open (requires future decision/approval):**
- Exact retention duration and deletion policy
- Whether PDF support is a launch blocker or can be deferred
- PDF parser/dependency choice after qualified review
- Exact upload size limits (10 MB is established by Phase 10.3 but may need verification)
- Magic-byte validation scope beyond text/plain, Markdown, JSON
- OCR policy and conditions under which scanned PDFs are treated as failures

**Repository evidence supporting claims:**
- Regulatory parser supports text/plain, Markdown, JSON only (ADR-0017 §64-66, §243-244)
- PyMuPDF not declared in pyproject.toml or integrated (ADR-0017 §246-247)
- Evidence-upload boundary: 10 MB per file, content-type + magic-byte validation (Phase 10.3/U7)
- compliance_evidence table: URI/hash/length/type and acquisition metadata (migration 001 §175-188)
- ADR-0017 §224-258: Restrict/verify first-release input proposal

### E. Task dependencies and authorization gates

**Resolution:** This decision documents the dependency map between Task 1 choices and later implementation tasks, identifying blockers, owners/approval needs, and resolution timing. No new technical decisions are introduced; this is a sequencing and governance document.

**Dependencies captured in the decision table (Section A-E above):**
- Decision A (global authorization) blocks Tasks 2–8. Task 2 explicitly enables Tasks 3–8.
- Decision B (applicability schema) blocks Tasks 6 and 10. Task 6 explicitly enables Tasks 7, 8, and 10.
- Decision C (durable processing) blocks Tasks 3–5 and 7–10. Task 3 explicitly enables Tasks 4 and 5.
- Decision D (artifact formats/retention) blocks Tasks 3–5 and 7–10. Task 3 explicitly enables Tasks 4 and 5.
- Decision E (this sequencing map) is the output of Task 1 itself.

**No later task may begin until its blocking decisions from Task 1 are resolved.** However, qualified regulatory/customs/plant-health/Nigerian-procedure reviews (independent legal gates) may proceed in parallel with Tasks 1–9 and do not block technical work that makes no pilot-applicability claim.

**Repository evidence supporting claims:**
- Phase 4D.10 plan Task 1–11 sequence (ADR-0017 §144-404)
- Task dependency blocks documented in each task's "Dependencies / decisions" and "Exit / next / authorization" subsections
- Independent legal gates documented in Phase 4D.10 §406-432

## Summary of Decisions Settled vs. Still Open (Task 1)

**Settled (from repository evidence + ADR-0017 planning direction):**
- Supported upload formats: text/plain, Markdown, JSON confirmed; PDF pending parser review
- Artifacts stored in private durable storage, no tenant evidence download path
- Two-stage governance: Stage A separate from Stage B, separate permissions
- `regulatory_requirement_applicability` as runtime evaluation model; `requirement_applicability` retained for tenant workflow
- No third applicability model
- Durable background direction: persist artifact + job before dispatch; idempotency, retry, failure recording, restart recovery
- Staff upload only; no automated URL retrieval
- Exporter publication fails closed with unknown/incomplete/partial states
- Eight Phase 4D.7 product-owner directions remain intact and governing

**Still open (requires future decision/approval before affected implementation):**
- Global administrator: bootstrap trusted operator boundary, grantor/revoker mechanism, audit storage, incident/audit retention
- Applicability schema: exact association granularity, migration consumers, pilot-scope version contract, API compatibility window
- Durable processing: worker/queue/dispatch mechanism, retry/backoff policy, monitoring/shutdown semantics, Render-specific service selection
- Artifact retention: exact retention duration, deletion/legal-hold policy, PDF parser/dependency choice, exact upload size limits
- Exporter API compatibility: compatibility/deprecation path, observable semantics for unknown/missing/fact states
- Source-change impact mapping and re-review triggers
- Qualified regulatory/customs/plant-health/Nigerian-procedure review boundaries

**Explicit statement:** Task 1 completion does not authorize subsequent implementation tasks (Tasks 2–11). Each task requires separate explicit authorization. The eight Phase 4D.7 directions remain governing planning requirements. Architecture acceptance does not imply implementation or publication approval.

### Task 2 — Global regulatory-administration authorization and audit

- **Objective/scope:** Establish server-side, fail-closed grants for source
  management, Stage A verification, and Stage B approval; record attributable
  grant, revocation, and protected-action audit. Tenant roles never confer
  global access, and the global grant confers neither review permission.
- **Reuse / expected surfaces:** `AuthenticatedIdentity`, `UserRepository`,
  `xportra/api/auth.py`, `xportra/api/authorization.py`,
  `xportra/api/dependencies.py`, repository/migration conventions.
- **Dependencies / decisions:** Task 1 settled the design contract. The six
  policy decisions below are approved **for planning only**; none authorizes
  implementation. Remaining technical/design contracts must be closed through
  documentation and read-only verification before implementation begins.
- **Risks:** Privilege escalation, tenant-role leakage, bootstrap lockout,
  incomplete attribution, migration/rollback hazards, self-grant circumvention,
  unaudited privilege changes, single-operator dependency.
- **Acceptance / verification:** Absent, revoked, or unavailable grant state
  denies; ordinary tenant owners/members are denied; grants authorize only
  named permissions; audit records identify actors and actions. Automated
  unit/API/database tests cover grants, revocation, cross-tenant denial and
  audit; manually verify bootstrap and recovery.
- **Exit / next / authorization:** Enables Tasks 3–8 after all boundary
  tests pass. Separate implementation authorization required.

**Authorization boundary:** All six policy decisions are approved for
**planning and documentation only**. They do not authorize code, migrations,
permission changes, environment or deployment configuration changes, database
mutations, or any part of the regulatory administration system.

#### A. Initial trusted operator and bootstrap (approved for planning)

- **Initial trusted operator:** The product owner's registered account,
  `innouguru@gmail.com`, is the intended initial trusted operator.
  **Repository evidence:** This email does not appear in any repository file.
  Its internal Xportra identity mapping (Supabase Auth subject → `users.id`
  via `users.supabase_uid`, migration 002) has **not been verified** from
  repository evidence. Successful sign-in is reported but not verified.
- **Initial provisioning:** Requires controlled bootstrap and verifiable
  attribution. Not yet implemented; no bootstrap procedure exists in code.
- **Initial authority:** Limited to `grant_manage` only. Does not
  automatically confer `source_admin`, `stage_a_verify`, or
  `stage_b_approve`.
- **Risk of single initial operator:** With only one initial operator, loss
  of that account or its credentials creates bootstrap lockout with no
  alternative grant manager. A second grant manager should be provisioned as
  soon as feasible after initial bootstrap.
- **Status:** Approved for planning. Bootstrap procedure, identity mapping
  verification, and second-operator provisioning remain open before
  implementation.

#### B. Grant and revocation authority (approved for planning)

- **Grant managers:** The product owner is the sole initial grant manager,
  subject to verified identity and controlled bootstrap.
- **Self-granting:** Prohibited through ordinary permission-management
  operations. No application workflow may grant `grant_manage` to the acting
  operator.
- **Self-revocation:** Ordinary application workflows cannot revoke the
  actor's own `grant_manage` permission.
- **Future grant managers:** Require explicit authorization and
  least-privilege assignment. No additional grant managers are designated at
  this time.
- **Tenant boundary:** Tenant ownership, membership, and successful sign-in
  do **not** confer global staff permissions. This is enforced by the
  existing tenant-membership model (`xportra/api/authorization.py` recognizes
  only `owner`/`member` tenant roles).
- **Atomicity:** Grant/revocation and corresponding audit event must commit
  atomically. If either fails, neither takes effect.
- **Status:** Approved for planning. Implementation of grant/revocation
  commands, atomic transaction boundaries, and self-grant prevention remain
  open before implementation.

#### C. Restricted out-of-band administrator recovery (approved for planning)

- **Mechanism:** Documented, owner-controlled manual database/operations
  procedure for the initial release. **Not** an in-product recovery workflow.
  No recovery procedure exists in code yet.
- **Purpose:** Recovery must remain possible if normal global-admin
  permissions are unavailable.
- **Prohibitions:** No permanent recovery token, no hidden backdoor, no
  automatic privilege escalation on sign-in.
- **Attribution:** Every recovery must have independently verifiable
  attribution, authorization, reason, changes, timestamp, and outcome.
- **Audit when normal path unavailable:** If the normal application audit
  path is unavailable, recovery must not silently bypass audit requirements.
- **Status:** Approved for planning. The exact authorization verification
  and independent-recording procedure for manual recovery remain a design
  blocker.

#### D. PostgreSQL audit integrity (approved for planning)

- **Atomic commits:** Permission changes and audit records must commit in the
  same database transaction.
- **Database permissions:** Ordinary application roles must not be able to
  update or delete historical audit records; database permissions should
  reinforce the application contract. Not yet implemented.
- **Recorded fields:** Actor, affected account, permission, action, reason,
  timestamp, and outcome as appropriate to the event.
- **Bootstrap/recovery attribution:** Bootstrap and recovery events must
  identify the actual initiating authority. A generic unexplained `bootstrap`
  actor is insufficient.
- **History preservation:** Grant and revocation history is preserved. An
  old grant is not deleted to re-grant the same permission. Re-granting
  creates a new historical grant record. Grant and revocation events maintain
  an explicit historical relationship.
- **Fail closed:** Fail closed when the atomic permission-and-audit
  transaction cannot commit.
- **Immutability caveat:** Sufficiently privileged database administrators
  may still be able to alter audit data; absolute immutability is **not
  claimed**.
- **Manual recovery recording:** A separate verifiable recording mechanism is
  required for manual recovery when the normal audit path is unavailable.
- **Status:** Approved for planning. Database-level protections, RLS or
  equivalent constraints, and the separate manual-recovery recording mechanism
  remain open before implementation.

#### E. Audit retention (approved for planning)

- **Provisional retention period:** 24 months for global staff permission and
  security audit records.
- **Status of retention period:** A product-design proposal, **not** a
  verified statutory requirement. Legal sufficiency has not been established.
- **Automatic deletion:** Remains disabled until the retention policy and
  deletion controls are explicitly approved.
- **Holds:** Legal, security, and incident-investigation holds suspend
  scheduled deletion.
- **History preservation:** Linked grant, revocation, bootstrap, and recovery
  history and attribution are preserved.
- **Disposal:** Any eventual disposal must be restricted and auditable and
  must account for backup-retention behavior. Not yet implemented.
- **Status:** Approved for planning. Final retention duration, deletion
  controls, hold procedures, and disposal approval remain open before
  implementation.

#### F. Stage A / Stage B small-team exception (approved for planning)

- **Default:** Different authorized reviewers are the default for Stage A
  source/wording verification and Stage B pilot-applicability approval.
- **Same-person exception:** Permitted only when a second qualified reviewer
  is genuinely unavailable **and** the exception is explicitly authorized.
- **Required controls:** Scoped exception, documented justification,
  authorization attribution, timestamps, and an audit record.
- **Disclosure:** Clearly disclose that the same person performed both stages;
  never describe this as independent review.
- **No blanket bypass:** No blanket or permanent bypass of the two-stage
  requirement.
- **Publication gate:** Without the required authority, justification, and
  audit record, the requirement cannot be published as approved for the pilot.
- **Later independent review:** A later independent review must be a new
  event and must not overwrite the earlier decision.
- **Status:** Approved for planning. The exact authority allowed to approve
  an exception and its technical enforcement remain design blockers.

**No exporter-facing publication is authorized as part of this task.**

**Decisions approved for planning (not implementation):**
1. Initial trusted operator identity and bootstrap procedure — `innouguru@gmail.com`
   designated as intended operator; identity mapping not verified from
   repository evidence.
2. Named initial `grant_manage` holders — product owner as sole initial grant
   manager.
3. Grant/revocation authority — no self-grant/self-revoke; atomic commit
   required; tenant boundary preserved.
4. Audit integrity and storage contract — atomic permission+audit commits;
   DB permissions reinforce contract; immutability not absolute.
5. Audit retention policy — 24-month provisional period; automatic deletion
   disabled; holds suspend deletion.
6. Small-team Stage A/Stage B exception — explicit authorization, justification,
   attribution, audit record required; no blank bypass.

**Remaining design blockers (require read-only verification or further approval):**
- Internal identity mapping for `innouguru@gmail.com` → `users.id`
  (Supabase `sub` → `supabase_uid` via migration 002) not verified.
- Bootstrap procedure not implemented; no code exists.
- Grant/revocation commands not implemented.
- Atomic transaction boundaries not implemented.
- Database-level audit protections (RLS/constraints) not implemented.
- Separate manual-recovery recording mechanism not defined.
- Exact authority for approving exceptions not defined.
- Retention policy legal sufficiency not established.
- Automatic deletion controls not implemented.

#### G. Identity-mapping contract verification (read-only verification complete)

**Repository evidence inspected:**
- `xportra/api/auth.py` — `AuthenticatedIdentity.subject` (UUID from JWT `sub`), `SupabaseTokenVerifier.verify()`, `TenantMembershipResolver.resolve_member()`
- `xportra/persistence/repositories.py` — `UserRepository.get_by_supabase_uid()`, `get_by_email()`, `set_supabase_uid()`
- `migrations/001_initial_schema.sql` — `xportra.users` table (`id UUID PRIMARY KEY`, `email TEXT`, `status`)
- `migrations/002_add_supabase_auth_identity.sql` — adds `supabase_uid UUID` column with unique index
- `xportra/api/authorization.py` — `OWNER_ROLE`/`MEMBER_ROLE` only; no global permissions

**Verified facts:**
1. The authenticated Supabase subject (`sub`) is extracted from the verified JWT as a `UUID` in `AuthenticatedIdentity.subject` (auth.py:107-109, 281-313).
2. The mapping chain is: Supabase JWT `sub` → `AuthenticatedIdentity.subject` → `UserRepository.get_by_supabase_uid(subject)` → `users.supabase_uid` → `users.id` (auth.py:403-428, repositories.py:126-131).
3. `users.supabase_uid` has a unique index (migration 002:5-7), so the mapping from `supabase_uid` to `users.id` is at most one row — unambiguous when present.
4. When `get_by_supabase_uid` returns `None` (no user with that `supabase_uid`), `resolve_member` treats `user` as `None`, no active memberships exist, and raises 403 `tenant_membership_required` (auth.py:408-418).
5. The `users` table has an `email TEXT` column with a unique index on non-null email (migration 001:63), so email lookup via `get_by_email()` is unambiguous when present.
6. User status values: `active`, `invited`, `disabled`, `deleted` (migration 001:58). A disabled or deleted user with a valid `supabase_uid` would still be found by `get_by_supabase_uid`; additional status checks would be needed at the grant layer.

**External identity verification (product owner performed, read-only, 2026-10-21):**
- The Supabase Auth account `innouguru@gmail.com` exists.
- Its Auth UID mapped to exactly one `xportra.users` row via `supabase_uid`.
- The matched `users` row has `status = 'active'`.
- `xportra.user_tenant_memberships` returned an active membership with role `owner`.

**Result:** identity mapping and tenant-membership verification passed.
No Auth UID, internal user UUID, tenant UUID, access token, or secret is recorded
in this document. This verification does not itself grant global staff
permissions, and the internal user ID is not provisioned here.

**Checks required before provisioning `innouguru@gmail.com` as initial `grant_manage` operator:**
1. Verify the email exists in Supabase Auth and obtain its `sub` (UUID). — verified by product owner.
2. Verify a `users` row exists with `supabase_uid` matching that `sub`. — verified by product owner.
3. Verify the `users` row has `status = 'active'`. — verified by product owner.
4. Verify at least one active tenant membership exists (if tenant membership is required for grant operations). — verified by product owner (role `owner`).
5. Record the verified `users.id` as the target for the initial `grant_manage` grant. — deferred to runtime bootstrap; not hardcoded.

**Status:** Mapping contract verified from repository code; external identity
mapping and tenant-membership verification passed (product owner performed).
Initial `grant_manage` bootstrap is implemented as a controlled, idempotent,
attributable service operation but is NOT executed against a database as part of
this task (no live provisioning).

#### H. Global-permission architecture confirmation (absence confirmed)

**Repository evidence inspected:**
- `xportra/api/authorization.py` — defines only `OWNER_ROLE`/`MEMBER_ROLE` and tenant-scoped permissions (`READ_TENANT_RESOURCE`, `CREATE_COMPLIANCE_EVIDENCE`, etc.)
- `grep` for `global_staff`, `grant_manage`, `global_admin`, `global_permission`, `regulatory_admin` across `.py` files — **no matches**
- `grep` for `global|staff|grant|admin` across `.sql` migration files — **no matches**
- `grep` for `audit` across `.sql` migration files — **no matches**
- `grep` for `class.*Audit|audit_table|audit_log|audit_event` across `.py` files — only test class names, no production audit infrastructure

**Confirmed absence:**
1. No global staff permission or grant table exists in any migration.
2. No grant/revocation service or endpoint exists in the API layer.
3. No global staff audit table or audit-writing service exists.
4. No database roles, RLS policies, triggers, or constraints related to global staff authorization exist.
5. `xportra/api/authorization.py` recognizes only `owner` and `member` tenant roles — no global staff role.

**Reusable capabilities:**
- `AuthenticatedIdentity` and `SupabaseTokenVerifier` for server-side identity resolution (auth.py).
- `UserRepository.get_by_supabase_uid()` for mapping Supabase subject to internal user ID (repositories.py:126).
- `require_permission()` dependency pattern for enforcing permissions on API routes (authorization.py:42-46, dependencies.py:636-639).
- `Database.transaction()` context manager for atomic commit (used in `set_supabase_uid`, repositories.py:140-142).

**Gaps requiring new design/implementation:**
- Global staff grant table (`global_staff_grants`) — does not exist.
- Global staff audit table (`global_staff_audit`) — does not exist.
- Grant/revocation commands and API endpoints — do not exist.
- Atomic transaction wrapping grant mutation + audit write — not implemented.
- Database-level protections on audit history (RLS, constraints) — not implemented.
- Self-grant/self-revocation prevention logic — not implemented.

#### I. Grant-history model comparison (design, not implementation)

**Inconsistency identified in prior draft:** The earlier draft proposed both (1) revocation inserts a new row without updating or deleting the original grant, and (2) a unique partial index on `(user_id, permission) WHERE revoked_at IS NULL`. These conflict: if revocation inserts a new revoked row while leaving the original grant row with `revoked_at IS NULL`, the index still matches the original "active" row, preventing re-granting after revocation. The original grant row remains permanently "active" from the index's perspective.

**Model A — Current-state grants plus immutable audit events (recommended)**

- `global_staff_grants` table: represents **current grant state only**, not complete grant history. It permits at most one row for each `(user_id, permission)` pair. A grant operation establishes the active state. A revocation updates the current grant state to revoked and records the revocation actor and timestamp. A later re-grant updates the current state back to active. This table alone does not preserve every historical grant period.
- `global_staff_audit` table: records every grant, revocation, bootstrap, and recovery event as a separate historical record. Historical audit records must not be updated or deleted by ordinary application roles. A re-grant creates a new audit event even if the corresponding current-state row already exists; prior grant periods are preserved only in the audit table.
- Grant-state mutation (UPDATE/DELETE on grants table) and audit insertion (INSERT on audit table) commit atomically in the same PostgreSQL transaction. Historical audit events are never rewritten to represent current state.
- A simple unique constraint on `(user_id, permission)` in the grants table enforces at most one active grant per user per permission. No partial index on `revoked_at` is needed because revocation updates the existing row.

**Model B — Immutable grant/revocation events**

- Grant and revocation events are append-only in an events table. No row is ever updated or deleted.
- Current permission state is derived from event history (the latest event per `user_id` + `permission` determines active/inactive) OR maintained in a separately controlled projection table updated atomically with event inserts.
- Cannot claim that an append-only event table alone can enforce uniqueness of current active grants — an explicit state or derivation mechanism is required. A partial index on events cannot distinguish the "latest" event from earlier ones.
- More complex queries to determine current permission state (must scan event history per user/permission).
- Re-granting after revocation is simply a new insert; the derivation logic determines the current state.

**Recommendation: Model A**

- Simpler and more consistent with the existing PostgreSQL architecture (which uses UPDATE/DELETE patterns, e.g., `set_updated_at` triggers).
- Unique constraint on the current-state table naturally enforces uniqueness without complex derivation logic.
- Permission checks are a simple SELECT from the grants table — no event-history derivation needed.
- Clear separation: current state is mutable within transactions (grants table), history is append-only (audit table).
- Model B's derivation approach adds query complexity without compensating benefit for this use case.

**Database integrity controls for Model A (design requirements, not yet implemented):**
- Unique constraint on `global_staff_grants(user_id, permission)` ensures at most one row per user/permission combination.
- Revocation UPDATEs the existing row to set `revoked_at`/`revoked_by`; this releases the uniqueness constraint for re-granting.
- Ordinary application roles have INSERT/SELECT on `global_staff_grants` but UPDATE/DELETE only through controlled application logic.
- `global_staff_audit` is INSERT-only for ordinary application roles; no UPDATE or DELETE.
- Both the grant-state mutation and the corresponding audit insertion commit atomically in the same transaction.
- The exact database constraints, locking strategy, transaction boundaries, and application-role permissions are design requirements for future implementation; they do not exist today.

**Concurrency and duplicate handling (design requirements):**
- Concurrent grant and revocation operations must be serialized or otherwise handled safely so that current permission state and audit history remain consistent.
- Duplicate grant/revocation requests must have explicitly defined behavior and must not produce misleading success events.
- Ordinary self-granting and ordinary self-revocation of `grant_manage` remain prohibited.

**Status:** Design decision documented. No tables, commands, or transaction boundaries exist in code.

#### J. Manual administrator recovery contract (design, not implementation)

**Owner authorization verification (independent of normal global-admin permissions):**
- Recovery is executed through a documented, owner-controlled manual database/operations procedure.
- The product owner (or designated authority) authorizes the recovery out-of-band.
- Authorization evidence must be recorded independently of the application's normal audit path.

**Who may execute:**
- Only the product owner or a explicitly designated operator may execute the manual recovery procedure.
- No application workflow or API endpoint provides recovery; it is strictly a manual database/operations procedure.

**Recording when normal audit path unavailable:**
- If the normal application audit path is unavailable, recovery must not silently bypass audit requirements.
- A separate verifiable recording mechanism must capture: attribution, authorization, reason, changes, timestamp, and outcome.
- The independent record must be reconciled with the primary audit trail when the normal path becomes available.

**Protection and verification:**
- The recovery record must be protected against alteration using the same database permission model as the primary audit table.
- After recovery, the record must be verifiable against both the independent record and (when available) the primary audit trail.

**Failure case:**
- If a trustworthy recovery record cannot be created, the recovery must not proceed — fail closed.

**Status:** Design direction approved for planning. Exact authorization verification procedure and independent-recording mechanism remain design blockers.

#### K. Stage A / Stage B exception contract (design, not implementation)

**Authority to approve exception:**
- The exact authority allowed to approve a same-person exception is not yet defined — design blocker.
- Under a narrowly scoped policy, the product owner may authorize the exception, but this requires explicit product-owner approval.

**Required controls:**
- Explicit authorization for the exception (who authorized, when, under what policy).
- Documented justification (why a second qualified reviewer is genuinely unavailable).
- Affected requirement and scope identification.
- Actor attribution for both Stage A and Stage B actions.
- Timestamps for both review actions.
- An audit record identifying that the exception was used.

**Publication blocking:**
- Without the required authority, justification, and audit record, the requirement cannot be published as approved for the pilot.
- The exception must be explicitly recorded before publication eligibility is evaluated.

**Subsequent independent review:**
- A later independent review must be a new event and must not overwrite the earlier exception-based decision.
- Both records are preserved in history.

**No blanket bypass:**
- No blanket or permanent bypass of the two-stage requirement.
- The exception is scoped, time-bounded, and requires explicit authorization each time.

**Status:** Design direction approved for planning. Exact exception-approving authority and technical enforcement remain design blockers.

#### L. Bootstrap prerequisites (design, not implementation)

**Prerequisites for initial `grant_manage` bootstrap:**

1. **Verified account identity and internal user mapping:**
   - `innouguru@gmail.com` exists in Supabase Auth and its verified `sub` (UUID) is obtained.
   - The `sub` maps to exactly one `xportra.users.supabase_uid`.
   - The mapped `users.id` is recorded as the target for the initial `grant_manage` grant.

2. **Appropriate account status:**
   - The mapped `users` row has `status = 'active'`.
   - The Supabase Auth account is not disabled or deleted.

3. **Explicit product-owner authorization:**
   - The product owner explicitly authorizes `innouguru@gmail.com` as the initial `grant_manage` operator.
   - Authorization is recorded with timestamp, authorizing party, and scope (`grant_manage` only).

4. **Least-privilege initial assignment:**
   - Initial authority is limited to `grant_manage` only.
   - Does not automatically confer `source_admin`, `stage_a_verify`, or `stage_b_approve`.

5. **Attributable bootstrap audit event:**
   - The bootstrap event identifies the actual initiating authority (product owner).
   - A generic unexplained `bootstrap` actor is insufficient.
   - Audit record captures: target user, permissions provisioned, timestamp, justification, provisioning method, and reference to the authorization record.

6. **Safe response if audit record cannot be persisted:**
   - If the audit record cannot be created, the bootstrap grant does not take effect — fail closed.
   - No partial state: either both grant and audit record commit atomically, or neither.

7. **Protection against repeated or ambiguous bootstrap attempts:**
   - If a `grant_manage` row already exists for any user, bootstrap must not create a duplicate.
   - Bootstrap is idempotent: re-running after successful bootstrap is a no-op or fails with an explicit "already bootstrapped" error.

**Status:** Design direction documented. Bootstrap procedure not implemented; no code exists.

### Independent legal and pilot-applicability blockers (do not block Task 2 authorization foundation)

These remain separate from Task 2 and block publication, not global
authorization:
- Exact CN/TARIC classification and product-form interpretation.
- Dutch import/customs-clearance boundary versus market or first-entry scope.
- Actual EU first-entry route and designated BCP.
- Plant-health/phytosanitary applicability.
- Current Nigerian NEPC and NAQS procedures/source completeness.
- Shipment-specific facts not established by verified sources.


### Task 3 — Durable artifact intake and ingestion-job persistence

- **Objective/scope:** Persist authorized staff-uploaded original bytes in
  private storage and commit a durable job before processing/dispatch.
  Provide immutable identity, provenance, idempotency, attempt history,
  visible failure, retry safety, restart recovery, and configured limits.
- **Reuse / expected surfaces:** `RegulatorySourceArtifactRepository`,
  `SourceAcquisitionService`, regulatory artifact metadata; private object
  storage protocol and Supabase adapter in
  `xportra/infrastructure/evidence_storage.py` as patterns only, not an
  assumed regulatory-storage decision.
- **Dependencies / decisions:** Tasks 1–2. Task 1 settles storage, retention,
  hash/idempotency, job/attempt contract, dispatch mechanism, retry/recovery,
  and resource bounds.
- **Risks:** Orphan jobs/objects, overwrite, public exposure, duplicate work,
  unbounded cost, or dependence on Render's ephemeral filesystem.
- **Acceptance / verification:** Rejected submissions create no accepted
  artifact or success state; accepted jobs link source/version, immutable
  bytes/hash, actor, and attempt; persistence precedes dispatch; duplicates
  are safe; restart recovers work. Automated repository/API and restart/retry
  integration tests; manually verify private access and retention/recovery.
- **Exit / next / authorization:** Enables Task 4 and later APIs. Separate
  implementation authorization required.

### Task 4 — Parsing, extraction, and failure recovery

- **Objective/scope:** Compose existing parsing, normalization, metadata,
  and candidate extraction with explicit complete, partial, failed, and
  completed-with-no-candidates outcomes. Allow attributed manual candidate
  entry after partial/failed extraction without changing its outcome.
- **Reuse / expected surfaces:** Existing domain services in
  `xportra/domain/ingestion.py`, repositories in
  `xportra/persistence/repositories.py`, and parsing/normalization/
  structuring/extraction tests. The verified parser supports text/plain,
  Markdown, and JSON, not PDF.
- **Dependencies / decisions:** Task 3 and Task 1's supported-format,
  safety/resource-limit, failure-state, and location-provenance contracts.
  PDF/OCR is a separate decision gate; do not treat the evidence-upload PDF
  extractor as regulatory parsing capability.
- **Risks:** Partial extraction represented as success, resource exhaustion,
  lost source location, unsafe type detection, or manual entry hiding failure.
- **Acceptance / verification:** Every candidate traces to immutable
  source/artifact and available exact location; zero-candidate success differs
  from failure/partial; errors are visible and safe; manual entries retain
  author and extraction outcome. Automated parser/domain/persistence tests
  plus manual malformed, oversized, partial, and approved-format fixtures.
- **Exit / next / authorization:** Enables Task 5 when outcomes and recovery
  are explicit. Separate implementation authorization required.

### Task 5 — Candidate review, provenance, and two-stage governance

- **Objective/scope:** Implement append-only Stage A source/wording
  verification and separate Stage B approval for the versioned pilot scope;
  retain actor, permission, timestamps, rationale, source/version/location,
  candidate-to-canonical linkage, and the controlled same-person exception.
- **Reuse / expected surfaces:** Existing candidate provenance, normalized
  document and canonical requirement/source records, plus Tasks 2 and 4.
  Add governance history without overloading evaluation results or a single
  mutable candidate status.
- **Dependencies / decisions:** Tasks 1, 2, and 4. Settle permission
  assignment, stage outcomes, exception controls, history, linkage cardinality,
  and scope identity.
- **Risks:** Permission confusion, mutable/erased approvals, invalid linkage,
  scope drift, or one stage implying the other.
- **Acceptance / verification:** Stage A cannot approve applicability; Stage
  B cannot bypass Stage A; reviewer separation is default and any exception
  is authorized, justified, and audited; manual candidates use the same gates;
  new versions inherit no approval. Automated transition, authorization,
  and provenance tests plus manual audit-trail walkthrough.
- **Exit / next / authorization:** Enables Tasks 6 and 8 after history and
  gates are verifiable. Separate implementation authorization required.

### Task 6 — Canonical applicability and pilot-scope integration

- **Objective/scope:** Additively link approved canonical requirements to
  deterministic runtime applicability and a versioned pilot scope. Preserve
  `requirement_applicability` for its distinct tenant workflow;
  `regulatory_requirement_applicability` remains the runtime-result model;
  Stage B stays separate; add no third applicability model.
- **Reuse / expected surfaces:** `ComplianceApplicabilityService`,
  `RegulatoryRequirementApplicabilityService`, optional result repository,
  migration `007`, assessment application service, canonical requirements,
  and existing tenant applicability repository/service.
- **Dependencies / decisions:** Tasks 1 and 5. Inspect all consumers, keys,
  foreign keys, constraints, migration and rollback behavior; resolve
  canonical identity and scope-version participation before schema changes.
- **Risks:** Reinterpreting tenant rows, broken history, duplicate/stale
  results, or coupling approval to evaluation.
- **Acceptance / verification:** Existing tenant workflow remains unchanged;
  results reference canonical requirements and explicit scope version;
  evaluator stays deterministic; Stage B is not an evaluation result.
  Migration upgrade/rollback and consumer regression tests pass; manually
  trace a persisted result.
- **Exit / next / authorization:** Enables Tasks 7, 8, and 10. Separate
  implementation authorization required.

### Task 7 — Source freshness, supersession, and re-review

- **Objective/scope:** Identify affected candidates, canonical requirements,
  and prior applicability decisions on source/version change; restrict stale
  material from current applicable use; preserve artifacts and decision
  history through re-review and republication.
- **Reuse / expected surfaces:** Existing source version/status/
  supersession metadata; immutable artifacts (Task 3), review/linkage (Task
  5), and applicability integration (Task 6).
- **Dependencies / decisions:** Tasks 3, 5, and 6; Task 1 freshness,
  impact-mapping, and re-review policy.
- **Risks:** False legal invalidation, missed affected records, approval
  inheritance, or destroyed history.
- **Acceptance / verification:** Changed hash, new version, withdrawal,
  expiry, and supersession yield an auditable affected set; stale items are
  restricted until review; old artifacts/decisions remain; republication
  requires current Stage A and B. Automated impact/restriction tests and
  manual source-change walkthrough.
- **Exit / next / authorization:** Enables Tasks 8 and 10. Separate
  implementation authorization required.

### Task 8 — Regulatory administration API

- **Objective/scope:** Provide authorized operations for source/artifact
  intake, jobs/failures, candidates, decisions, publication, and freshness
  using validated, idempotent, auditable application use cases.
- **Reuse / expected surfaces:** FastAPI dependency/router patterns,
  `xportra/api/compliance.py`, `xportra/api/schemas.py`, application/domain
  services, repositories, router registration, and API tests.
- **Dependencies / decisions:** Tasks 2–7; settle endpoint permissions,
  object checks, idempotency, error semantics, audit, and stale-state
  behavior.
- **Risks:** IDOR, cross-tenant leakage, handler-owned business logic,
  inconsistent transitions, duplicate side effects, or artifact disclosure.
- **Acceptance / verification:** Every read/mutation has server-side
  authorization and audit attribution; invalid transitions fail explicitly;
  tenant owners/members are denied; retries are safe. Automated API tests
  cover authorization, object boundaries, errors and retry; manually inspect
  API documentation and denial behavior.
- **Exit / next / authorization:** Enables Tasks 9 and 10. Separate
  implementation authorization required.

### Task 9 — Regulatory administration UI

- **Objective/scope:** Build a separate staff workspace for overview,
  sources/intake, job/failure states, candidate provenance and review,
  Stage B, publication, and freshness/re-review queues.
- **Reuse / expected surfaces:** Current frontend shell/routing, API client,
  protected-page patterns, design primitives, and component-test setup.
  Exact paths are selected only after implementation-time inspection.
- **Dependencies / decisions:** Task 8's stable API and Task 1's decision
  vocabulary; the staff UI is not a prerequisite for Task 10.
- **Risks:** Tenant navigation exposing staff actions, implying legal
  approval, hiding partial/failure states, or obscuring provenance.
- **Acceptance / verification:** Loading, empty, partial, failed, stale, and
  unauthorized states are clear; provenance precedes decisions; backend
  denial remains authoritative; accessibility and frontend tests pass.
  Manually verify staff and unauthorized journeys.
- **Exit / next / authorization:** Enables Task 11. Separate implementation
  authorization required.

### Task 10 — Exporter assessment integration

- **Objective/scope:** Replace caller-supplied requirement lists with
  server-loaded current canonical publications approved through both stages
  for the relevant pilot scope; evaluate deterministically and expose
  unknown, stale, incomplete, qualified partial, and rejected out-of-scope
  states explicitly.
- **Reuse / expected surfaces:** `AssessmentApplicationService`,
  `ComplianceApplicabilityService`, context builder, runtime result model,
  assessment route/schema, tenant shipment access, and assessment frontend.
- **Dependencies / decisions:** Tasks 5–8, Task 7 freshness rules, approved
  catalog/scope contract, and qualified product/classification, customs,
  route/BCP, plant-health, and source review. Any legal gap preventing a
  defensible in-scope result blocks publication behavior.
- **Risks:** Caller-controlled regulatory universe, omission implying no
  obligations, false completeness/clearance, stale rules, or regression in
  current assessment behavior.
- **Acceptance / verification:** Only current eligible canonical records are
  evaluated; missing facts yield unknown; incomplete coverage is not a
  negative result; unsupported requests are rejected; tenant isolation and
  existing assessments are preserved. Automated domain/API/frontend
  regression tests and manual scenarios against qualified scope evidence.
- **Exit / next / authorization:** Enables Task 11 after verified behavior.
  Requires separate implementation authorization; publication requires a
  further explicit authorization.

### Task 11 — End-to-end verification and controlled release readiness

- **Objective/scope:** Verify authorization, tenant isolation, migrations,
  durable processing/retries/restart recovery, manual recovery, governance,
  provenance, freshness, catalog filtering, qualified partial/unknown
  states, and prohibited claims. Prepare recovery, monitoring, and
  deployment checklist; do not deploy.
- **Reuse / expected surfaces:** Unit/integration/regression/API/frontend
  suites, migration test conventions, and operations/monitoring documentation
  introduced by prior tasks.
- **Dependencies / decisions:** Relevant Tasks 2–10; all technical choices
  closed; qualified legal/pilot-scope and source gates resolved before any
  publication authorization.
- **Risks:** Test-only confidence, untested rollback, unowned retention/
  incident operations, or release claims broader than evidence.
- **Acceptance / verification:** End-to-end tests cover all eight Phase 4D.7
  directions and R-4D criteria; recovery is rehearsed in approved
  non-production environments; manual review confirms no government
  approval, clearance, or completeness claim exceeds evidence. Produce a
  release-readiness package without deployment.
- **Exit / next / authorization:** Readiness does not authorize deployment
  or publication. Each task, deployment, and publication requires separate
  explicit authorization.

## Independent legal and pilot-scope gates

Qualified review can proceed in parallel with Tasks 1–9 and among the
independent questions below. These open questions do not authorize legal
interpretation by the implementation team and do not block technical work
that makes no pilot-applicability claim. They do block approval of actual
pilot applicability and exporter-facing publication:

| Open question | Evidence / owner | Task impact |
|---|---|---|
| Exact intended use, product form, treatment/preparation, and CN/TARIC classification. | Written product specification and qualified customs-classification/regulatory review. | Task 5 cannot record a defensible pilot Stage B decision for affected requirements; Task 6 cannot finalize a legally meaningful pilot scope; Task 10 cannot claim actual pilot applicability; Task 11 publication readiness is blocked. |
| Dutch import/customs clearance versus first EU entry, route, designated BCP, and transit facts. | Shipment route and current official BCP authorization/procedure evidence reviewed by qualified customs/regulatory personnel. | Same gates as above for entry/route-dependent requirements. Keep route facts explicit; Dutch clearance does not establish Dutch first entry. |
| Plant-health and phytosanitary measures. | Qualified plant-health review against current official EU and Dutch sources for the exact product and route. | Blocks Stage B and exporter applicability claims for these measures; technical administration work may continue without representing them as complete. |
| Nigerian exporter procedures and source completeness/currentness. | Retrieve and review current NEPC procedures and complete NAQS material; resolve the recorded access/readability gaps and verify any sesame-specific procedure through qualified review. | Blocks any completeness claim and relevant Stage B decisions; Task 10 must return explicit incomplete coverage or reject an unsupported request until resolved. |
| Actual shipment facts and any later buyer-specific conditions. | Shipment-specific review; buyer-specific conditions remain excluded from this pilot unless separately scoped and approved. | Missing material facts remain unknown; buyer-specific scope cannot be added implicitly. |

Tasks 1–4 and the security/API/UI foundations in Tasks 2–9 may be prepared
against approved contracts and test fixtures while these reviews proceed,
provided no implementation begins without its own authorization and no
fixture is represented as a legal finding. Task 5 may establish governance
mechanics but must not record a real pilot applicability approval before
the applicable review is complete. Task 6 may establish versioned-scope
mechanics, but the production pilot scope remains provisional until qualified
review. Task 10 can only be considered release-ready after relevant reviews
are complete; Task 11 must withhold publication readiness while any required
product, route, plant-health, source-completeness, or shipment-fact gate is
open.

## Superseded preliminary phase sequence

Historical planning context only. The Phase 4D.10 tasks above are the single
authoritative dependency and acceptance breakdown; do not execute the
superseded sequence below.

### 0. Product-owner architecture approval gate

- **Goal/boundary:** Approve or revise the architecture and operational
  controls for the agreed planning direction, and assign remaining legal,
  classification, source, security, and operational questions.
- **Dependencies:** None.
- **Expected documentation:** `REQUIREMENTS.md`, `ROADMAP.md`, proposed
  ADR-0017, and the pilot/source decision record.
- **Database/security:** None.
- **Acceptance:** The agreed planning scope is consistent across Phase 4D
  records; the product owner explicitly approves or revises ADR-0017; and
  remaining legal, classification, route, security, and operational
  conditions are assigned. Architecture approval does not itself authorize
  implementation.
- **Non-goals:** Code changes or production ingestion.

The agreed planning direction is raw/unprocessed food-use sesame
(*Sesamum indicum*) from Nigeria, with Kano and Jigawa as operational
sourcing regions and intended Dutch import/customs clearance. Phase 4D.1
records authentic Official Journal text supporting the listed Nigeria/
*Sesamum* row and its Salmonella/50% controls as legal-text evidence; this
does not establish product classification, shipment applicability, broader
current law, or a complete checklist. NEPC/NAQS source gaps remain. Qualified
review and both human approval stages are required before any applicable
requirement is published.

### 1. Global authorization and lifecycle persistence foundations

- **Goal/boundary:** Define system-level regulatory permissions, actor
  identity, audit requirements, durable ingestion attempt state, review
  decisions, and candidate-to-canonical linkage before exposing operations.
- **Dependencies:** Phase 0 approval.
- **Expected code to inspect/change:** `xportra/api/auth.py`,
  `xportra/api/authorization.py`, `xportra/persistence/repositories.py`,
  `xportra/api/schemas.py`, migrations `001`, `003`–`008`, and related
  migration/repository tests.
- **Database:** Likely required for global permission grants, durable
  ingestion attempts, review history, and candidate/canonical linkage.
  Final schema must reuse current source, artifact, candidate, canonical
  requirement, and source-association records where they satisfy the need.
- **Security:** Backend permission checks; no inference from tenant roles;
  immutable actor/audit attribution; deny by default.
- **Acceptance:** Tenant owners and members are denied; authorized grants
  work independently of tenant membership; schema constraints preserve
  source/artifact/candidate provenance and review history; migration tests
  and repository tests pass.
- **Non-goals:** Admin UI, extraction, or exporter catalog endpoint.

### 2. Source registry and controlled artifact intake API

- **Goal/boundary:** Complete source create/read/update lifecycle and accept
  only approved document types into private regulatory storage.
- **Dependencies:** Phase 1 permissions and persistence contracts.
- **Expected code to inspect/change:** regulatory source/artifact models and
  repositories in `xportra/persistence/repositories.py`,
  schemas/routes in `xportra/api/schemas.py` and `xportra/api/compliance.py`,
  storage adapters from the evidence-upload boundary, and their API tests.
- **Database:** Extend existing source/artifact fields only when verified
  gaps require it; preserve immutable artifact identity and source
  association. Persist the ingestion job before processing can be
  dispatched.
- **Security:** Enforce content size/type limits, safe filenames, private
  storage, source-level access controls, and no arbitrary remote fetch.
- **Acceptance:** Authorized administrators can register/update sources and
  submit supported uploads; the immutable original and durable job are
  persisted before dispatch; malformed/unsupported submissions fail
  explicitly; duplicate content is detected or safely recorded without
  accidental overwrite; tenant users cannot access shared admin operations.
- **Non-goals:** PDF text extraction (handled in Phase 3 after parser
  interface and PyMuPDF approval), OCR, crawler, public artifact access, or
  admin UI. Raw PDF upload/storage is not evidence that the document has been
  successfully parsed.

### 3. Durable background ingestion, extraction, attempts, and retry

- **Goal/boundary:** Compose existing parsing, normalization, metadata, and
  candidate extraction services into a durable background workflow, with
  job state committed before processing starts. Add PDF text extraction for
  approved pilot formats only after verifying the regulatory parser contract
  and approving a parser; retain page-level provenance and make
  scanned/unreadable PDFs explicit failures unless OCR is separately
  approved. Permit controlled manual candidate entry after failed/partial
  extraction without changing the extraction outcome.
- **Dependencies:** Phases 1 and 2.
- **Expected code to inspect/change:** `xportra/domain/ingestion.py`,
  `xportra/domain/services.py`, `xportra/persistence/repositories.py`,
  the approved worker/dispatch boundary, and ingestion/API tests.
- **Database:** Persist durable job/attempt state, stage, timestamps,
  outcome, safe error details, idempotency identity, retry lineage, and
  artifact/parser identity before dispatch.
- **Hosting/operations:** Assess Render execution options against the
  documented single-web-process and ephemeral-filesystem model, the
  no-Docker constraint, budget, service limits, and operational ownership.
  Do not assume or add a paid worker, queue, scheduler, or other service
  before approval.
- **Security:** Bound resource use and retries; do not expose raw stack traces
  or artifact contents to unauthorized tenants. Local ephemeral storage is
  not the durable artifact/job store.
- **Acceptance:** Jobs and artifacts survive process restart; pending or
  abandoned work is recoverable; retries and duplicate delivery are safe
  and traceable; outcomes distinguish pending/processing/completed,
  partial/failed, and completed-with-zero-candidates; failures remain
  visible; provenance is preserved; manual candidates follow both review
  stages; PDF page locations are retained where available; malformed,
  encrypted, oversized, scanned, or unreadable files never receive
  success-shaped outcomes.
- **Non-goals:** Selecting a particular worker/queue/paid service before
  hosting/budget review; automated legal validation.

### 4. Two-stage candidate review, canonical linking, and publication

- **Goal/boundary:** Add human decisions, classification, scope, review
  history, separate Stage A verification and Stage B pilot-applicability
  approval, canonical linkage, and a guarded publication transition.
- **Dependencies:** Phases 1–3 and approved pilot taxonomy/scope.
- **Expected code to inspect/change:** `xportra/domain/ingestion.py`,
  `xportra/domain/services.py`, canonical/candidate repositories,
  `xportra/api/schemas.py`, `xportra/api/compliance.py`, and regulatory
  requirement tests.
- **Database:** Use existing canonical requirements, sources, and candidates;
  add only review history/linkage/status structures shown necessary by the
  authorization and persistence audit.
- **Security:** Stage-specific verification and applicability-approval
  permissions are enforced server-side; publication eligibility fails closed
  unless both decisions and current source/scope conditions hold.
- **Acceptance:** Stage A and Stage B are separately authorized and
  auditable; unresolved candidates remain separate from published
  requirements; publication rejects missing provenance, review, scope, or
  applicability inputs; approval history is append-only and a verified
  wording decision alone never makes a requirement applicable; manually
  entered candidates are held to the same gates and retain extraction status.
- **Non-goals:** LLM auto-approval or legal advice.

### 5. Administrative APIs

- **Goal/boundary:** Expose minimal source, ingestion-attempt, candidate,
  review, and publication operations using existing application/service
  boundaries. Add freshness/re-review operations in Phase 7 after the
  change-impact contract is approved.
- **Dependencies:** Phases 1–4.
- **Expected code to inspect/change:** `xportra/api/compliance.py`,
  `xportra/api/schemas.py`, `xportra/domain/services.py`, router
  registration, repositories, and API tests.
- **Database:** No additional schema unless an API use case reveals a
  documented gap.
- **Security:** Permission checks on every route and object; safe errors;
  audit actor on mutations.
- **Acceptance:** API contract tests cover successful workflow, invalid state
  transitions, denial, idempotency, and tenant isolation.
- **Non-goals:** Browser-only authorization or general-purpose admin
  configuration.

### 6. Minimal administration workspace

- **Goal/boundary:** Deliver the smallest UI that makes the approved API
  workflow usable: overview, source registry/intake, ingestion attempt
  details, candidate review, and published catalog. Add the freshness/
  re-review queue in Phase 7 after its API and stale-state semantics are
  approved. Combine screens where that avoids redundant navigation.
- **Dependencies:** Stable, authorized Phase 5 APIs.
- **Expected code to inspect/change:** Existing frontend routing, role-aware
  page patterns, API client, forms, and component tests; exact paths to be
  selected after inspecting the then-current frontend.
- **Database:** None directly.
- **Security:** Hide navigation for usability but rely on backend
  authorization; never place admin service credentials in the browser.
- **Acceptance:** Authorized staff can complete approved workflows; loading,
  empty, partial, error, and unauthorized states are explicit; candidate
  provenance is visible before a decision; keyboard/accessibility and
  frontend tests pass.
- **Non-goals:** Analytics unrelated to ingestion/review, self-service
  permission provisioning, or exporter-facing UI redesign.

### 7. Freshness, supersession, and re-review

- **Goal/boundary:** Track source/artifact version changes, expiry,
  withdrawal, and supersession; mark linked canonical requirements as
  requiring review; preserve historical artifacts, decisions, and
  publication events; provide the staff stale/re-review queue.
- **Dependencies:** Phases 1–5 and approved freshness/withdrawal policy.
- **Expected code to inspect/change:** Source/artifact repositories,
  candidate-to-canonical linkage, review history, publication service,
  freshness API, and the Phase 6 administration workspace.
- **Database:** Reuse source version/status and content hash where reliable;
  add only the event/linkage fields needed to identify affected
  publications and preserve prior state.
- **Security/data integrity:** No source update silently edits, approves, or
  removes prior decisions. The catalog fails closed for affected
  requirements until required re-review is completed.
- **Acceptance:** Tests prove changed hash, new source version, expiry,
  withdrawal, and supersession identify all linked current publications;
  stale entries are excluded or visibly marked according to the approved
  policy; old artifacts and decisions remain auditable; and re-publication
  requires current Stage A and Stage B decisions. Staff can identify and
  open affected records in the administration queue.
- **Policy boundary:** A source-level stale/review flag restricts current
  applicable use but does not, without qualified review, assert that every
  linked requirement is legally invalid.
- **Non-goals:** Automatic legal determination of whether a change affects
  applicability.

### 8. Exporter published-catalog integration

- **Goal/boundary:** Replace caller-supplied regulatory universe for the
  approved pilot with server-loaded canonical requirements that have passed
  both approval stages, then apply deterministic shipment applicability
  while preserving shipment-owned evidence and assessment.
- **Dependencies:** Phase 4 publication contract, Phase 7 freshness rules,
  approved catalog scope, and phases 1 and 5.
- **Expected code to inspect/change:** `AssessmentApplicationService`,
  applicability services/context builder, exporter API schemas/routes,
  requirements page and API client, and assessment/applicability tests.
- **Database:** Reuse canonical requirements and applicable existing
  workflow persistence; no second applicability model.
- **Security:** Tenant-scoped shipment/evidence access; catalog is read-only
  to exporters; drafts and review candidates are never returned.
- **Acceptance:** Only eligible published requirements enter deterministic
  evaluation; missing shipment facts yield `unknown`; incomplete source or
  catalog coverage is explicit; an empty result cannot be presented as
  proof of no obligations.
- **Non-goals:** Government clearance, automated legal conclusion, or
  unrestricted destination coverage.

### 9. End-to-end verification and operational readiness

- **Goal/boundary:** Verify the lifecycle, authorization boundaries,
  provenance, retry/review behavior, source changes, and exporter
  uncertainty states as one system.
- **Dependencies:** Phases 1–8.
- **Expected code to inspect/change:** Unit, integration, regression, API,
  and frontend suites for each changed boundary; operational logging and
  configuration documentation only where needed.
- **Database/security:** Run migrations only in approved test environments;
  verify role provisioning, retention, backup, and incident/audit visibility.
- **Acceptance:** Automated end-to-end scenarios cover all R-4D criteria;
  tenant members cannot administer; published catalog excludes drafts;
  source updates preserve history; quality checks pass; production remains
  untouched absent separate approval.
- **Non-goals:** Treating an unconfigured external service or unrun live test
  as verified.

## Implementation planning and authorization gates

The pilot direction choices are recorded in
[`phase-4d-2-sesame-eu-pilot-product-owner-decisions.md`](./phase-4d-2-sesame-eu-pilot-product-owner-decisions.md).
The eight Phase 4D.7 product-owner directions are consolidated in ADR-0017
and remain governing requirements for planning. ADR-0017 is accepted as the
planning basis only; it does not authorize code, schema, infrastructure,
production, or publication changes. The following decisions remain open
and must be assigned and resolved before affected implementation work:

1. Staff-only global authorization, grant/revocation ownership, distinct
   permissions for source management, Stage A verification, and Stage B
   applicability approval, plus the small-team exception.
2. A durable background execution/retry approach compatible with Render,
   available budget, no-Docker constraint, and operational ownership.
3. Original-artifact private storage and version history, including
   retention duration, deletion/legal-hold policy, costs, and provenance.
4. Supported text formats and the PDF parser/safety gate; URL retrieval
   remains outside the first-pilot direction.
5. The server-owned canonical catalog and the existing deterministic Phase 3
   evaluator as the only shipment-applicability procedure; its persistence
   model, canonical linkage, and versioned-scope identity.
6. How source changes identify affected candidates, canonical requirements,
   and prior applicability decisions; freshness, supersession, re-review,
   unknown, incomplete, partial, stale, and unsupported-request semantics.
7. Deferral of organization-specific schema/API/UI from this pilot.
8. Controlled manual candidate recovery after partial or failed extraction,
   with the same Stage A and Stage B gates and no false success status.

The directions leave open the grant bootstrap and trusted operator boundary,
actual migration constraints, file limits and PDF/OCR scope, API compatibility,
and exact exporter wording. Durable background processing is the settled
direction; only its dispatch/execution and recovery mechanism remains open.
Do not invent a retention period or select a worker, queue, scheduler, or
paid service before the hosting/budget review.

Qualified regulatory/customs, plant-health, and Nigerian-procedure review
must separately resolve applicable law, classification, entry/BCP facts,
and source gaps before any candidate can be approved for exporter-facing
publication. The active task is the Phase 4D.10 planning breakdown.
Architecture acceptance does not itself authorize implementation or
publication; each implementation task and publication requires separate
explicit authorization.
