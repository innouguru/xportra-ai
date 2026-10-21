# ADR-0017: Regulatory Knowledge Administration Boundary

- **Status:** Accepted as the basis for implementation planning only
  (2026-10-20); implementation and exporter-facing publication are not
  authorized.
- **Date:** 2026-10-20
- **Linked requirements:** Proposed R-4D in `REQUIREMENTS.md`.
- **Related decision:** ADR-0001 (deterministic applicability).
- **Plan:** `docs/phases/phase-4d-regulatory-knowledge-administration.md`.
- **Pilot decision record:** `docs/phases/phase-4d-2-sesame-eu-pilot-product-owner-decisions.md`.
- **Readiness assessment:** `docs/phases/phase-4d-4-pilot-scope-and-implementation-readiness.md`.

## Context

Xportra has shared canonical regulatory requirements and sources, separate
extracted regulatory candidates and document artifacts, deterministic
applicability services, and tenant-scoped exporter authentication. The
inspected code does not provide an integrated regulatory ingestion API,
durable attempt/retry workflow, candidate review/publication lifecycle,
global knowledge-administration authorization, or exporter API backed by a
published catalog.

The source, candidate, canonical requirement, and applicability structures
already present are not interchangeable. In particular, the exporter evidence
upload path is not the regulatory source-ingestion workflow. Introducing a
global catalog also creates a security boundary distinct from tenant
membership.

The product owner has accepted this ADR as the basis for implementation
planning only. This acceptance does not authorize runtime behavior or schema
changes, production or infrastructure changes, or exporter-facing
publication. The implementation contracts and technical choices identified
below remain open and must be resolved at their planned gates.

The product owner has agreed with a planning direction of Nigerian
raw/unprocessed food-use sesame, initially sourced operationally in Kano and
Jigawa, for consignments intended for import and customs clearance in the
Netherlands. This agreement does not resolve product classification,
shipment applicability, entry route, BCP, or legal coverage. Staff-upload-only
intake, a two-stage human approval model, and deferral of organization-specific
requirements are agreed planning boundaries. The architecture below is accepted as the
basis for implementation planning only; its detailed implementation
contracts remain open and require resolution at the planned gates.

## Verified repository facts

1. `migrations/001_initial_schema.sql` contains canonical authorities,
   regulatory sources, requirements, requirement-source associations, and
   applicability-related structures.
2. Migrations `003`–`007` add regulatory source artifacts, document
   normalization, metadata, extracted regulatory requirements, and
   candidate-level applicability. Migration `008` adds requirement
   assessment persistence.
3. Regulatory acquisition, parsing, normalization, metadata extraction,
   normative candidate extraction, and applicability services exist under
   `xportra/domain/ingestion.py`, but are not composed into a complete admin
   API workflow.
4. `xportra/persistence/repositories.py` contains partial regulatory
   repositories. There is no complete durable ingestion attempt/retry,
   candidate review, or publication workflow.
   Source and authority repositories currently expose reads; `SourceAcquisitionService`
   validates and records artifact metadata but does not itself retain uploaded
   bytes, create a durable processing job, or compose parsing and extraction.
5. The regulatory parsing service supports text/plain, Markdown, and JSON.
   PDF/DOCX/image support belongs to the separate exporter evidence upload
   path.
6. Tenant authorization in `xportra/api/auth.py` and
   `xportra/api/authorization.py` recognizes tenant owner/member roles. No
   separate global regulatory-administration permission was found.
7. ADR-0001 and the Phase 3 domain flow establish deterministic
   `ComplianceApplicabilityService` evaluation over the
   `RegulatoryRequirementApplicabilityService` evaluator. The current
   assessment path does not load the published canonical catalog.
   The API accepts requirements in the applicability request, and
   `AssessmentApplicationService` evaluates those supplied records. The
   canonical `requirement_applicability` table is tenant/product/destination
   scoped; `regulatory_requirement_applicability` stores tenant-scoped
   evaluation results against extracted candidates. Its repository is
   available to the evaluator as an optional dependency, but the current
   assessment API composition does not wire that repository. Neither table
   represents approval to publish a candidate for the shared pilot catalog.
   The current evaluator has limited text/fact matching for destinations,
   commodities, actors, and quantity thresholds; it does not establish the
   proposed sesame tariff classification, detailed presentation, route/BCP,
   or the full current legal universe.
8. Existing source/artifact records provide some version/status/retrieval
   metadata, but no complete change-to-re-review workflow was found.

## Proposed decisions

Each decision below requires approval as marked. Implementation-specific
schema details must be confirmed against the repository at the time the
corresponding task is authorized.

### 1. Separate global knowledge administration from tenant membership

**Proposal:** Introduce server-side system-level permission grants for
designated Xportra staff, independent of `owner`/`member` tenant roles.
Never grant global access because a user owns or belongs to an organization.
Resolve the authenticated user server-side, check active grants on every
protected read and mutation, and deny by default. Grant and revocation
operations are limited to explicitly authorized platform operators acting
through a controlled process and must have auditable actor attribution.
Global catalog administration does not imply Stage A or Stage B authority;
those remain separately granted permissions.

**Rationale:** Shared regulatory data is not tenant-owned. The current
membership model cannot safely express a global administrative capability.

**Planning direction agreed:** Designate Xportra staff administer the shared
catalog; organization ownership or membership never conveys global access.

**Product-owner direction:** Global access uses restricted,
operator-managed grants. Only explicitly authorized platform operators may
grant/revoke through a controlled, attributable process. Fail closed; tenant
ownership or membership gives no global privilege.

**Approval needed:** Define the bootstrap and trusted operator boundary,
grant/revocation mechanism and process, audit storage, and incident/audit
expectations. Repository review found no existing global permission
mechanism. A server-side grant model linked to the existing user identity is
a proposal, not an accepted schema.

### 2. Separate editing and reviewing capabilities

**Proposal:** Enforce two distinct approval stages:

- **Stage A — requirement verification:** an authorized verifier records
  that the source and artifact provenance are adequate, the exact source
  text/location supports the extracted wording, and the interpretation has
  been reviewed. This does not assert that the requirement applies to the
  pilot or a shipment.
- **Stage B — pilot-applicability approval:** an authorized approver records
  whether the verified requirement applies to the defined pilot scope,
  including supporting rationale and the reviewed scope/version. `unknown`
  or unresolved applicability is not approval as applicable and must remain
  visible rather than being inferred.

Give source/ingestion management, Stage A verification, and Stage B approval
separate permissions. Prefer different people for Stage A and Stage B where
practical. Any small-team same-person exception must be explicit,
permission-controlled where feasible, justified, and auditable. Publication
as an applicable exporter-facing requirement requires both successful stages
and current source/scope state.

**Rationale:** Extraction and source registration are not equivalent to
human verification; source verification does not establish pilot
applicability. A single generic “reviewed” or “active” status cannot stand
in for both decisions.

**Planning direction agreed:** Both decisions are mandatory and separate;
independent actors are preferred, with a controlled exception for a small
team.

**Approval needed:** Approve role assignment, the exception process, the
decision vocabulary, and which non-applicable/unknown outcomes can be
retained without publication.

**Proposed decision record:** Persist each decision as append-only history
with stage, candidate and source/artifact identity (including content hash
and exact location), actor identity and permission, timestamp, outcome,
rationale, and superseded-decision reference where applicable. Stage B also
records the pilot-scope identifier/version and reviewed shipment facts.
Stage A must resolve to verified, rejected, or revision-required; Stage B
must separately resolve to applicable, not-applicable, or unknown. Only a
current Stage A verification followed by an applicable Stage B decision
makes the requirement eligible for the guarded exporter-publication
transition. Unknown, rejected, stale, or revision-required records remain
out of the applicable catalog. A same-person exception is an explicit,
audited authorization—not an implicit status shortcut.

An authorized operator's global catalog-administration grant does not by
itself grant either Stage A verification or Stage B approval permission.
Manual candidate entry is permitted as a recovery path when extraction
fails or is partial, but it records its source/artifact reference, author,
time, exact supporting location where available, and the extraction's
failed/partial status. Manually entered candidates pass the same Stage A and
Stage B transitions as extracted candidates; manual entry cannot convert a
failed extraction into complete success.

### 3. Durable background ingestion

**Product-owner direction:** Processing must be durable and run independently
of a single upload request remaining open. Persist the original artifact and
durable ingestion job before processing starts. Support idempotency, safe
retry, visible failures, recovery after process restart, and attempt history.

**Proposal:** Use a durable background-processing design, with artifact and
job commit preceding dispatch. A worker claims persisted jobs, records
attempts and stage outcomes, and can resume or retry after process restart
without overwriting immutable artifact bytes or prior attempts. The selected
worker/queue/dispatcher and delivery semantics remain open; no new paid
service or infrastructure is approved.

**Repository and hosting evidence:** Regulatory parsing/extraction currently
runs through synchronous domain services; no durable worker, scheduler,
queue, or job record was found. The Render deployment audit documents a
single long-lived web process, ephemeral local filesystem, and no existing
background-job primitive; the repository has no Dockerfile or `render.yaml`.
The approved no-Docker constraint and available budget must be respected.
This evidence does not establish which Render product or external service
should be selected.

**Security/data integrity:** Store the original artifact in durable private
storage and persist the job before enqueue/dispatch so a crash cannot leave a
request appearing successful with no recoverable work. Use an idempotency
key bound to source and byte hash, atomic claim/lease or equivalent recovery
semantics, bounded retries, and safe operator-visible failure details.
Duplicate delivery must not create duplicate candidates or approvals.

**Acceptance:** Tests prove work remains discoverable after process restart,
retries are safe and traceable, duplicate dispatch does not duplicate
effects, failed/partial attempts remain visible, worker errors cannot mark
jobs successful, and orphaned pending/claimed work can be recovered according
to the approved lease/recovery policy.

**Approval needed:** Choose a deployment-compatible background execution
approach after verifying Render hosting options, budget, no-Docker constraint,
and operational ownership. Define queue/dispatch, claim/lease, concurrency,
retry/backoff, idempotency, resource bounds, monitoring, and shutdown/recovery
semantics. Do not assume any worker, queue, scheduler, or paid service is
approved.

### 4. Restrict and verify first-release input

**Proposal:** Accept regulatory PDFs and supported text documents uploaded by
authorized Xportra staff only. Preserve the original artifact and record the
official source URL when known as metadata; do not retrieve that URL from the
server. The regulatory parser currently supports text/plain, Markdown, and
JSON, not PDF. PDF support is a capability gate: verify the parser contract,
dependency policy, parser safety limits, and page-level provenance before
selecting or integrating a PDF library. Defer URL retrieval, OCR, crawling,
and unsupported formats.

Validate content by inspecting bytes as well as declared type and filename;
set approved upload, expansion, page, time, and memory limits; reject
malformed, encrypted, oversized, scanned-without-readable-text, or otherwise
unreadable files with an explicit failure result. Preserve no partial parse as
a successful complete ingestion. Exact limits and error vocabulary must be
approved in the implementation task; do not infer them from tenant evidence
limits.

**Rationale:** TXT, Markdown, and JSON are currently supported by the
regulatory parser; the evidence upload path's PDF logic is separate and uses
a custom extraction function. Project technology-baseline documentation
mentions PyMuPDF, but `pyproject.toml` does not declare it and no integration
was found in the regulatory parser. Remote retrieval would need separate host
allowlisting, redirect/DNS/IP controls, size/time limits, and SSRF-oriented
review. Initial sesame/EU source research and retrieval limitations are
recorded in
`docs/phases/phase-4d-1-sesame-eu-pilot-source-research.md`.

**Planning direction agreed:** Staff upload only; no automated URL retrieval.

**Approval needed:** Confirm the precise supported text formats, whether
PDF is a launch blocker, acceptable PDF parser/dependency after review, and
upload/processing limits. The separate evidence-upload PDF implementation is
not regulatory PDF support.

### 5. Preserve source artifacts and provenance

**Proposal:** Retain immutable original bytes in access-controlled
regulatory-source storage and persist content hash, source identity,
acquisition actor/time, parser/version information, normalized output, and
candidate section/location. Reuse compatible storage abstractions where
possible, but do not place shared regulatory artifacts in tenant evidence
records or expose them through exporter evidence APIs.

**Rationale:** Existing artifact metadata does not itself prove that raw
bytes are retained or immutable. Provenance must survive parsing and
publication.

**Approval needed:** Confirm storage/retention policy and access audience.
The product-owner direction requires an explicit retention period and
version-history policy, but the period, deletion rules, legal/operational
holds, cost limits, and storage backend remain unresolved. Do not choose or
imply a duration until approved.

### 6. Link reviewed candidates to canonical requirements

**Proposal:** Keep extracted candidates distinct from canonical published
requirements and maintain an auditable association between them. Preserve
many-to-many source support if multiple candidate passages support one
canonical requirement or one candidate passage contributes to several
canonical records. Reuse `requirements` and `requirement_sources`; add a
link structure only if the existing schema cannot represent candidate
location and decision history.

**Rationale:** The existing source association does not establish which
reviewed candidate wording/location supports a canonical requirement.

**Approval needed:** Confirm association granularity during schema design.
Keep source, artifact hash/version, normalized document, candidate location,
Stage A decision, Stage B decision, and canonical requirement traceable
without rewriting prior decisions.

### 7. Keep deterministic applicability authoritative

**Proposal:** Retain the accepted Phase 3
`ComplianceApplicabilityService`/`RegulatoryRequirementApplicabilityService`
as the single deterministic
shipment-applicability procedure. For persisted Phase 4D evaluation results,
select `regulatory_requirement_applicability` as the authoritative result
model: it records a tenant, requirement identity, context fingerprint,
tri-state outcome, reason, and context snapshot. The evaluator supports
optional persistence to this repository, but the current assessment API
composition does not wire it. Its present
`requirement_id` foreign key targets an extracted candidate, however, so
implementation must add a safe candidate-to-canonical linkage or equivalent
additive reference before exporter assessments can use it with published
canonical requirements. Preserve existing candidate-based rows as historical
data.

`requirement_applicability` remains a separate tenant-owned,
exporter/product/destination-scoped record. Its domain service validates
those tenant resources, and it has no publisher/reviewer attribution. Do not
use it as the shared catalog approval record, and do not drop, rename, or
silently repurpose it. Trace and preserve its existing service and
persistence consumers; it is not the exporter assessment endpoint's current
catalog source.

Stage B approval is a governance decision, not an evaluator result. Persist
its approved, rejected, or unresolved outcome in append-only review history
linked to the verified candidate, canonical requirement, source/artifact
version, exact evidence location, actor, timestamp, rationale, and versioned
pilot scope. Do not add a third applicability table or overload an
`applicable` evaluation result to mean that a reviewer approved publication.
The selected result model continues to represent runtime `applicable`,
`not_applicable`, or `unknown` outcomes only.

The versioned pilot-scope identity and all known assessment facts must be
included in the evaluated context and fingerprint. Scope limitations and
missing conditions remain explicit in the context/reason; incomplete catalog
coverage is a separate response state and is never encoded as
`not_applicable`. Do not infer CN/TARIC classification, detailed product
presentation, route, BCP, or legal status from free-text matching. Only
server-selected canonical requirements with current publication eligibility
may be evaluated. Preserve `unknown` when necessary shipment facts are
missing.

**Repository evidence and consumers:** Migration `001` defines
`requirement_applicability` with canonical requirement, tenant exporter,
product, destination, effective-window, and status fields
(`required`/`not_required`/`unknown`/`inactive`). Its repository and
`RequirementApplicabilityService` are exercised by domain/persistence
tests. Migration `007` defines
`regulatory_requirement_applicability` with candidate requirement,
tenant/context fingerprint, tri-state outcome, reason, context, and
evaluated/archived status. `RegulatoryRequirementApplicabilityService` evaluates the candidate
semantics; it supports persistence through an optional repository dependency.
`ComplianceApplicabilityService` calls the evaluator, but the current
assessment API composition does not wire that repository and still takes
caller-supplied requirements. It does not load either table as a published
catalog. The two tables therefore have distinct service/test consumers and
semantics; this proposal is not a consolidation or retirement of either.

**Security/data integrity and migration:** Build the catalog lookup in the
application/domain boundary, not the HTTP handler. Tenant result rows must
always derive tenant identity from verified membership context. A migration
must preserve existing candidate foreign keys and rows, define unambiguous
canonical linkage, include pilot-scope version in result identity, and
avoid making a stale result current after a source or scope change. No third
evaluator or applicability table is proposed.

**Acceptance:** Tests prove that (1) only currently published canonical
requirements enter evaluation; (2) arbitrary caller-supplied requirement
objects cannot create or alter the official catalog; (3) result identity
changes when relevant facts or pilot-scope version changes; (4) missing
facts yield `unknown`; (5) incomplete catalog coverage is not represented
as an empty/no-requirements conclusion; (6) Stage B approval, rejection,
and unresolved status remain distinct from runtime outcomes; and (7)
tenant-scoped result reads and writes cannot cross tenants.

**Planning direction agreed:** One deterministic Phase 3 procedure; no
third applicability evaluator/model. Current evaluator coverage is
incomplete for this pilot and needs explicit, tested extension.

**Approval needed:** Approve this choice of
`regulatory_requirement_applicability` for runtime evaluation results,
retention of `requirement_applicability` for its separate tenant workflow,
the additive canonical linkage/scope-version design, the governance-history
boundary, and whether shipment assessment snapshots need durable persistence.
Also approve the server-owned catalog contract. A qualified reviewer must
establish actual law and classification; an architecture decision cannot
supply that legal conclusion.

### 8. Re-review when sources change

**Proposal:** A changed content hash/version, source withdrawal, expiry, or
supersession identifies affected candidates, canonical requirements, and
previously published applicability decisions and flags them for human
re-review. Until the required re-review is complete, affected requirements
must not be treated as current applicable entries; exporters receive an
explicit stale/under-review uncertainty state. Preserve old artifacts,
review decisions, and publication history. A source flag restricts current
use but does not by itself declare every linked requirement legally invalid.
Never automatically revise, approve, or erase an existing requirement
because a source changed. A new source version does not inherit prior
approval.

**Rationale:** Existing version/status fields do not provide a complete
impact/re-review workflow.

**Product-owner direction:** Restrict stale, superseded, or re-review-needed
material from current applicable use, while preserving provenance and
history. Do not infer legal invalidity from a source flag alone.

**Approval needed:** Define freshness thresholds, expiry policy, affected-
record propagation, current-use restriction behavior, and observable
exporter states/wording.

### 9. Exporters consume only published catalog entries

**Proposal:** The exporter application loads requirements server-side from
the canonical catalog, applies deterministic applicability, and excludes
draft, rejected, unreviewed, withdrawn, or superseded records. It reports
missing facts as unknown and catalog/source limitations as incomplete
coverage. An empty matching set is not proof that no obligations exist.

**Rationale:** Current assessment inputs are caller-supplied and the
Requirements page includes editable drafts; neither is a safe global
published-catalog boundary.

**Approval needed:** Approve user-facing wording and how incomplete coverage
is displayed and blocks readiness claims.

### 10. Keep organization-specific requirements separate and defer them

**Proposal:** The shared catalog contains only verified public regulatory
material and approved pilot applicability. Defer organization-managed and
buyer-specific requirement schema/API/UI and workflows from the initial
pilot. If later authorized, represent these in an explicitly separate
tenant-isolated category with distinct provenance and labels; never merge
them indistinguishably with official law.

**Planning direction agreed:** A future organization-internal capability
may exist, but it is not part of the first pilot. Deferring its schema/API
avoids expanding the current scope and does not preclude a separately
designed extension.

**Approval needed:** Confirm that this deferral is included in the final
approved first-release scope. Any later extension needs its own requirements
and tenant-isolation review.

### 11. API and smallest useful administration workspace

**Proposal:** Keep business logic in application/domain services. Provide
separate staff-only API boundaries for:

1. Authority/source registration and metadata maintenance.
2. Artifact upload and ingestion-attempt status/retry.
3. Candidate listing and source-provenance retrieval.
4. Stage A verification and Stage B pilot-applicability approval as
   separately authorized commands.
5. Published-catalog and stale/re-review queue views.
6. A read-only exporter catalog operation that loads eligible canonical
   requirements server-side and returns explicit coverage state.

Use the smallest dashboard that supports overview/coverage status, sources
and upload, attempt detail/failure/retry, candidate evidence and review,
published catalog, and stale/re-review queue. Navigation visibility is only
UX; every operation must enforce the relevant permission on the backend.
Build this UI only after the permission, lifecycle, provenance, and API
contracts are stable.

The proposed end-to-end staff workflow is: register an authority/source;
upload and validate the original artifact; create a durable attempt; parse,
normalize, and extract candidates with explicit partial/failure/zero-
candidate outcomes; complete Stage A verification; separately complete
Stage B pilot-scope applicability approval; link eligible material to a
canonical requirement and publish through a guarded transition; monitor
freshness/supersession and re-review; expose only currently eligible
canonical catalog entries and explicit coverage state to exporters.
Retries create new linked attempts and do not overwrite artifact bytes or
decision history.

**Rationale:** Existing compliance endpoints are tenant-oriented and the
applicability request accepts caller-provided requirements. Existing
requirements UI is not a global approved catalog. Extending either boundary
without a server-owned publication contract would blur tenant and shared
regulatory data.

**Approval needed:** Approve endpoint ownership, API resource/transition
contracts, and the first dashboard workflow before implementation tasks are
created.

## Phase 4D.7 consolidated product-owner directions

The following eight directions were provided by the product owner and remain
the governing requirements for the accepted planning basis. They do not
resolve open technical choices, establish legal applicability, or authorize
implementation or publication.

1. **Global authorization:** Use restricted, operator-managed grants;
   only explicitly authorized platform operators grant or revoke access
   through a controlled, attributed process. Fail closed. Tenant owner/member
   roles confer no global authority, and global administration does not
   automatically grant Stage A or Stage B permissions.
2. **Applicability model:** Propose additive evolution of
   `regulatory_requirement_applicability` for persisted runtime results;
   retain `requirement_applicability` for its separate tenant workflow.
   Verify consumers, constraints, canonical linkage, and scope versioning
   before implementation. Do not add a third model. Stage B approval remains
   separate governance history.
3. **Two-stage governance:** Stage A verifies source and extracted or
   manually entered wording; Stage B separately approves applicability to a
   specific versioned pilot scope. Different authorized reviewers are the
   default. A single-reviewer exception must be authorized, justified, and
   auditable. Preserve distinct decisions, permissions, actors, timestamps,
   and history.
4. **Durable background ingestion:** Persist the original artifact and
   ingestion job before processing. Support idempotency, safe retry, visible
   failures, restart recovery, and attempt history. Select no worker, queue,
   scheduler, or paid service until Render, budget, no-Docker, and operational
   constraints have been reviewed.
5. **Freshness/supersession:** Identify and restrict affected requirements
   from current applicable use when sources become stale, superseded, or
   require review. Preserve history and provenance. A source flag does not
   automatically declare every linked requirement legally invalid.
6. **Unknown and incomplete coverage:** Allow only a clearly qualified
   partial assessment supported by verified requirements in supported
   scope. Explicitly represent unknown applicability, missing facts, stale
   sources, and incomplete coverage; reject requests when no defensible
   limited assessment is possible. Do not imply exhaustiveness, government
   approval, or export clearance; an absent record proves no negative.
7. **Original artifact retention:** Retain original artifacts and version
   history under an explicitly defined policy. Address private storage,
   provenance, auditability, reproducibility, deletion, cost, and Supabase/
   Render constraints. Retention duration and deletion rules remain
   unresolved; new versions do not overwrite history or inherit approval.
8. **Extraction failure/manual candidates:** Permit authorized manual
   candidate entry/review after failed or partial extraction. Preserve the
   artifact, source references, reviewer attribution, and explicit extraction
   outcome. Manual candidates pass the same Stage A and Stage B gates and
   cannot make failed/partial extraction appear successful.

The agreed pilot remains raw/unprocessed sesame for human consumption,
originating in Nigeria, operationally sourced initially in Kano and Jigawa,
and intended for Dutch import/customs clearance. The Netherlands boundary
and route, product classification, BCP, plant-health applicability, Nigerian
source completeness, and buyer-specific requirements remain unresolved.
These directions do not establish legal applicability or exporter
publication approval.

### A. Global staff authorization

- **Evidence/reuse:** Supabase tokens are verified in `xportra/api/auth.py`;
  `AuthenticatedIdentity.subject` is resolved to the internal user through
  `users.supabase_uid` (migration `002`). Existing API authorization derives
  owner/member roles from tenant membership. No global staff grant or
  trusted application configuration for this purpose was found.
- **Decision:** Add a narrowly scoped system-permission grant for named
  internal users, keyed to the resolved internal user ID and permission
  (source administration, Stage A, Stage B). Resolve and check active grants
  server-side on every protected request. Never accept a role, tenant,
  identity, or grant from request data. Keep current tenant-membership
  authorization unchanged for tenant resources.
- **Security/audit:** Unauthenticated calls return authentication failure;
  authenticated users without the exact active grant are denied. Grant and
  revocation commands are restricted to explicitly authorized platform
  operators, record actor/time/reason, and fail closed if identity or grant
  lookup is unavailable. Bootstrap, self-grant prevention, dual-control, and
  break-glass details are implementation decisions still requiring approval;
  none is assumed as an existing control.
- **Alternatives/migration:** Reusing owner/member roles is rejected.
  Environment allowlists are not selected as the durable grant mechanism
  because they lack per-actor revocation and audit history. Additive grant
  and append-only audit persistence is likely; no change to `users` identity
  resolution or tenant membership is proposed.
- **Acceptance:** API tests deny anonymous and ordinary tenant owner/member
  callers on every administrative route; accept only an active server-side
  grant; reject forged client role/tenant fields; verify revocation takes
  effect; verify tenant resource permissions remain unchanged; and assert
  grant/revocation audit attribution and fail-closed repository errors.
- **Approval remaining:** Trusted operator boundary, bootstrap and
  grantor/revoker mechanism, whether dual-control or break-glass is needed,
  audit storage, and incident/audit retention.

### B. Two-stage approval lifecycle

Use durable job/decision records as authoritative history and mutable
candidate/source status only as a current-state projection. Proposed
transitions:

| Current state | Authorized action | Next state | Required record |
|---|---|---|---|
| Source registered | Staff submits supported bytes | Artifact accepted; ingestion pending | Actor, source, immutable artifact URI/hash/size/type, time |
| Ingestion pending | Worker/service claims attempt | Processing | Attempt ID, start time, parser/config version |
| Processing | Parse/extraction completes | Succeeded, partial, failed, or succeeded with no candidates | Completion time, counts, warnings, actionable safe failure |
| Failed/partial | Authorized retry | New processing attempt | New attempt linked to prior attempt and same artifact; no overwrite |
| Candidate extracted or manually entered | Candidate enters review | Awaiting Stage A | Source/artifact hash, extraction outcome, normalized document or manual-entry attribution, exact location where available |
| Awaiting Stage A | Verifier confirms text/provenance | Stage A verified | Actor, time, decision, rationale, quoted location |
| Awaiting Stage A | Verifier rejects or requests correction | Rejected or revision required | Actor, time, reason; no publication |
| Stage A verified | Stage B review begins | Awaiting pilot applicability | Canonical link and versioned scope |
| Awaiting Stage B | Approver finds applicable, not applicable, or unknown | Stage B decided | Actor, time, outcome, scope version, evidence and rationale |
| Applicable and current at both stages | Authorized publisher executes guarded command | Published | Publication event linked to both decisions and exact source version |
| Published | Source/scope changes, expiry, withdrawal, or supersession | Re-review required, withdrawn, or superseded | Trigger, prior state, actor/system event, affected links |
| Re-review required | New review completes | New versioned decisions; republish only by explicit command | New append-only decisions; retain prior history |

For Stage B, an affirmative approval means the requirement is applicable to
the reviewed pilot scope; a decision that it does not apply is recorded as
rejected for that scope; and insufficient evidence or scope facts remain
unresolved. None of these governance outcomes is a shipment-level evaluator
result.

All transitions validate the expected current state and fail with an explicit
conflict on invalid or stale commands. Failed, partial, and zero-candidate
runs are distinct. Rejections and unresolved applicability remain
searchable, but not in the applicable catalog. Each decision records actor,
permission, UTC timestamp, rationale, source/artifact content hash and
location; Stage B also records canonical requirement and pilot-scope version.
Prefer different Stage A and Stage B actors. If staffing makes that
impossible, require a specific exception permission, reason, and audit event;
never silently treat the same actor as independent review.

**Acceptance:** State-machine tests cover every allowed transition, invalid
transition, stale command, retry, duplicate request, partial/no-candidate
result, manual-candidate recovery after partial/failed extraction, actor
separation, the audited exception, immutable prior decisions, and fail-closed
publication when source or scope changes.

**Approval remaining:** Role assignment, transition vocabulary, same-person
exception controls, and retention policy.

### C. One authoritative applicability model

The selected table and its limits are specified in Decision 7 above.
Operationally, `regulatory_requirement_applicability` stores deterministic,
tenant-scoped evaluation snapshots; append-only Stage B review history
stores the pre-publication governance decision. The `context` and context
fingerprint must include the pilot-scope ID/version and all relevant known
facts. Runtime outcomes remain `applicable`, `not_applicable`, or
`unknown`. Reviewer approval/rejection/unresolved, supporting evidence,
reviewer identity, and scope limitations are linked decision-history fields,
not aliases for those runtime outcomes. Incomplete catalog/source coverage
is a separate response field, not a fourth applicability outcome.

**Alternatives:** Using `requirement_applicability` as the shared approval
model is rejected because its records are bound to a tenant exporter,
product, and destination and have no review attribution. Keeping both
tables as competing evaluators or creating a third applicability table is
also rejected. Do not consolidate or delete either current table.

**Acceptance:** In addition to Decision 7 tests, repository tests verify
canonical linkage preserves the extracted candidate provenance, scope
version participates in identity, an old evaluation cannot be reused after
scope/source change, and Stage B decisions never write a runtime
`applicable` result by themselves.

**Approval remaining:** Confirm the selected result table, migration/linkage
approach, pilot-scope version contract, and separate review-history record.

### D. Exporter publication boundary

- **Evidence/reuse:** `POST /compliance/assessments/applicability` currently
  accepts `ApplicabilityRequest.requirements` as arbitrary caller-supplied
  dictionaries. `AssessmentApplicationService` validates and passes them
  to `ComplianceApplicabilityService`; the existing assessment flow does
  not load a global published catalog. Tenant-scoped evidence and existing
  assessment/readiness DTOs remain reusable.
- **Decision:** Add an application-level catalog reader that selects
  canonical records only when publication is current, source and both
  review stages are current, and the record is within approved pilot scope.
  The exporter endpoint accepts shipment facts/IDs, not authoritative
  requirement objects. The service fetches requirements and explicit
  coverage state, then invokes the existing deterministic evaluator.
- **Partial-assessment direction:** A qualified partial assessment may be
  returned only when the request is inside the supported pilot scope and at
  least one current, verified, Stage B-approved requirement can be
  defensibly assessed. The result must identify its limited coverage and
  cannot imply exhaustiveness. Return explicit unknowns for missing facts
  and stale-source uncertainty. Reject requests that fall outside supported
  scope or where no defensible limited assessment can be produced; an empty
  catalog match alone is not evidence that no requirements apply.
- **Security/data integrity:** Derive tenant ID from authenticated membership;
  validate shipment/product ownership server-side; never allow a tenant
  caller to query staff-only artifacts or mutate shared catalog state.
  Tenant-specific requirements stay separate and tenant-isolated. Missing
  catalog rows, partial source coverage, stale sources, and missing shipment
  facts must return explicit incomplete/unknown states, not "no
  requirements." Do not claim government approval, complete coverage, or
  export clearance.
- **Compatibility/alternatives:** The current arbitrary-requirements route
  must not be silently trusted as the new catalog boundary. Migrate the
  frontend/API contract deliberately; any temporary compatibility path must
  be explicitly scoped, non-authoritative, and removed or gated before
  exporter publication. Do not move domain/business logic into handlers.
- **Acceptance:** API/service tests prove a forged request cannot inject,
  suppress, or alter official requirements; only current published canonical
  records are returned; a stale/superseded record is excluded; coverage
  gaps and unknown facts are visible; a partial result is returned only
  where verified current requirements support it and is expressly qualified;
  unsupported or indefensible requests are rejected; tenant data isolation
  holds; and existing evidence workflows remain tenant-scoped.
- **Approval remaining:** Endpoint contract, compatibility/deprecation
  window, observable semantics for unknown/missing facts/stale/
  superseded/incomplete/partial outcomes, and user-facing wording.

### E. Durable ingestion and PDF handling

- **Evidence/reuse:** `SourceAcquisitionService` validates and writes
  artifact metadata but does not store uploaded bytes or create durable
  jobs. `regulatory_source_artifacts` holds an artifact URI/hash/length/type
  and acquisition metadata, but the schema does not establish that the URI
  is immutable storage. `ArtifactParsingService` supports plain text,
  Markdown, and JSON only. The evidence-upload PDF path and its private
  Supabase Storage adapter are tenant evidence capabilities, not regulatory
  PDF support.
- **Decision:** Keep source registry, immutable original object, and each
  processing attempt distinct. Add durable ingestion-job/attempt records
  keyed to source/artifact, and persist the original artifact and job before
  background processing begins. Record status, attempt lineage, processing
  stage, actor, timestamps, parser version, safe error code/message, and
  outcome counts. Hash actual bytes server-side; validate file signature,
  declared MIME/extension consistency, size, page/expansion/time/memory
  bounds, and encryption/readability. Keep artifacts in private durable
  storage with no tenant evidence download path. Record known official URL
  as metadata only; never fetch it.
- **Idempotency/failure:** `(source, content hash)` identifies duplicate
  bytes; a duplicate is not silently reprocessed as a new artifact. Explicit
  retries create a new attempt linked to the prior attempt and same immutable
  artifact. Parse failure, partial extraction, scanned/unreadable PDF, and
  successful extraction with zero candidates remain distinct outcomes.
  Expose warnings and page/section/position provenance to reviewers; never
  mark partial or failed extraction as complete success.
- **Manual recovery:** Authorized staff may enter a candidate manually when
  extraction fails or is partial. Preserve the original artifact, source
  references, reviewer/author and timestamp, and explicit extraction status.
  A manual candidate goes through the same Stage A and Stage B permissions
  and decisions as an extracted candidate; it does not change job outcome.
- **Alternatives/migration:** Reuse the parser/normalizer/candidate services
  and compatible object-storage abstraction, not the evidence-upload
  endpoints or their tenant-facing bucket semantics. Add no PDF package in
  this proposal. Additive artifact storage, ingestion-job/attempt
  persistence, and a deployment-compatible background execution mechanism
  are expected. The Render audit documents ephemeral local files and no
  existing worker, queue, scheduler, or Dockerfile. No concrete worker or
  paid service is selected. Verify hosting, budget, no-Docker, recovery,
  and operational support constraints before implementation.
- **Acceptance:** Tests cover byte/hash identity, MIME spoofing, limits,
  duplicate upload, retry lineage/idempotency, storage failure,
  process restart recovery, duplicate delivery, abandoned-job recovery,
  unsupported/encrypted/scanned PDF, partial extraction, zero candidates,
  manual-candidate recovery through both review stages, safe failure
  reporting, provenance locations, and prevention of cross-tenant artifact
  access.
- **Approval remaining:** Storage backend/bucket, retention/deletion/legal
  hold and duration, supported PDF/text formats, exact limits,
  parser/library choice, worker/queue/dispatch approach, Render compatibility,
  available budget, and operational ownership.

### F. Qualified regulatory-review boundary

Technical architecture may provide versioned scope, source provenance,
state transitions, deterministic evaluation, unknown/incomplete results,
and a publication kill switch now. It cannot decide legal scope.
Publication and applicable exporter presentation must remain blocked until
qualified review establishes enough evidence for each candidate and scope.
Still unresolved are exact CN/TARIC classification and product-form
interpretation; the operative Dutch import/customs-clearance boundary versus
market or first-entry scope; actual EU first-entry route and designated
BCP; plant-health/phytosanitary applicability; current Nigerian NEPC and
NAQS procedures/source completeness; and shipment-specific facts not
established by verified sources. Kano/Jigawa remain operational sourcing
regions unless qualified evidence establishes legal significance.

**Acceptance:** The system can represent "not reviewed", `unknown`,
incomplete coverage, stale/re-review, and a blocked publication state.
Automated tests prove none of these states is converted to a verified
requirement or a negative compliance result. Qualified reviewers must
record evidence, scope, date, and limitations before any applicable
publication decision.

**Approval remaining:** Assign qualified EU customs/regulatory,
classification, plant-health, and Nigerian procedure reviewers and accept
their explicit evidence packages; product owner confirms final operational
scope. No legal finding is implied by approving this architecture.

## Consequences if approved

- Backend authorization, durable lifecycle persistence, and provenance
  constraints must precede admin UI.
- Verification and pilot-applicability approval are distinct, attributed,
  timestamped, auditable transitions; neither alone permits publication.
- Existing source, artifact, candidate, canonical requirement, and
  deterministic applicability components should be extended rather than
  duplicated.
- Additive migration work is likely for global staff grants, durable
  ingestion attempts/retry lineage, decision history, and candidate-to-
  canonical linkage only where the current schema cannot represent them.
  Exact tables/statuses are not accepted by this proposal.
- Exporter integration must fail closed and retain `unknown` and incomplete
  coverage states.
- Organization/buyer-specific management remains deferred and separate from
  the shared catalog.
- No implementation should claim government approval, legal certification,
  or export clearance.

## Risks and migration implications

- **Privilege escalation:** tenant owners/members must not gain shared
  catalog authority. Global grants, provisioning, revocation, and every
  administrative API require server-side checks and auditable actor identity.
- **False approval:** Stage A and Stage B must not collapse into one “reviewed”
  flag. Only current, separately approved decisions can authorize applicable
  exporter presentation; unknown and incomplete states remain explicit.
- **Unsafe or partial intake:** PDF and other uploaded bytes require bounded
  validation and extraction. Partial or unreadable processing must not be
  reported as complete; evidence-upload parsing is not reusable proof of
  regulatory PDF safety.
- **Incorrect legal coverage:** current research is not a complete Dutch
  sesame checklist. Classification, entry/BCP, plant-health, and Nigerian
  source questions remain outside what the architecture can decide.
- **Compatibility:** the current applicability API accepts caller-supplied
  requirements. Introduce the approved server-owned catalog boundary and
  migrate exporter clients deliberately; retain or deprecate legacy behavior
  only through an explicit compatibility plan and tests.
- **Migration:** likely additive schema changes for global staff grants,
  durable ingestion attempts/retry lineage, append-only two-stage decision
  history, and candidate-to-canonical linkage. Reuse source/artifact,
  candidate, canonical requirement, and source-association structures where
  possible. Do not infer Stage A/B approval from existing `active`, `validated`,
  or `extracted` statuses; existing rows require explicit review or remain
  non-published. No production migration is authorized by this proposal.
- **No duplicate applicability model:** Stage B history records governance
  decisions and scope version; it is not another rule evaluator. The existing
  evaluator must be extended and tested for the defined pilot before
  applicable exporter claims are enabled.

## Alternatives not selected for this proposal

1. **Tenant owner implies global administrator — rejected:** violates the
   existing tenant boundary and grants shared knowledge access to unrelated
   organization owners.
2. **Publish extracted candidates directly — rejected:** bypasses human
   verification and canonical catalog controls.
3. **LLM decides applicability — rejected:** conflicts with ADR-0001.
4. **Arbitrary server-side URL fetch in the first cut — deferred:** adds
   remote-fetch security and reliability concerns before an allowlist and
   retrieval policy are approved.
5. **Create parallel requirement and applicability catalogs — rejected:**
   duplicates existing canonical structures without demonstrated need.

## Planning authorization and remaining gates

Acceptance records the architecture boundary and the eight Phase 4D.7
product-owner directions as the basis for planning. It does not finalize
implementation contracts or settle the open technical choices. The
sequenced, bounded work is recorded in
[`phase-4d-regulatory-knowledge-administration.md`](../phases/phase-4d-regulatory-knowledge-administration.md).

The following remain unresolved and must be decided at the relevant planning
or implementation gate:

- Trusted operator boundary, grant bootstrap and revocation process, audit
  storage, and separate source-management, Stage A, and Stage B permissions.
- Additive migration constraints, candidate-to-canonical linkage, and
  versioned pilot-scope identity.
- Durable background dispatch/execution, retry/recovery semantics, limits,
  monitoring, and operational ownership under Render, budget, and no-Docker
  constraints.
- Private artifact storage, retention duration, deletion/legal holds, limits,
  and cost ownership.
- Supported upload formats, extraction limits, and whether PDF support is a
  launch blocker; the current regulatory parser supports text/plain,
  Markdown, and JSON, not PDF.
- Exporter API compatibility and explicit unknown, stale, superseded,
  incomplete-coverage, qualified-partial, and unsupported-request semantics.
- Source-change impact mapping and re-review triggers.

Qualified product/classification, customs, route/BCP, plant-health, and
Nigerian source review also remain open. They are independent of architecture
acceptance and must be satisfied before requirements can be approved as
applicable for publication.

**Implementation authorization: not granted. Exporter-facing publication
authorization: not granted.** Each implementation task requires separate
authorization and a bounded active task. Publication requires verified
implementation, qualified review, and separate explicit authorization.
