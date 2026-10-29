# CURRENT_STATE.md — Current Project State

> Source of truth for what is true about Xportra AI right now.
> Updated: 2026-10-24
>
> Regulatory ingestion-to-EvidenceDocument linkage implemented locally
> (`regulatory_ingestion_evidence_linkage_service.py` + focused tests 6/6 pass);
> idempotency uses `EvidenceDocumentRepository.get_by_source_identity` (source + version);
> provenance preserved (`artifact_id`, `content_hash`, `parser_version`, `ingestion_job_id` in metadata);
> failed/partial ingestion blocked from linkage (`ApplicationValidationError`).
> Regulatory publication eligibility endpoint implemented (`GET /regulatory/eligible-requirements`,
> `RegulatoryPublicationEligibilityService`, repository `get_eligible_for_publication()`);
> retrieval-time filter corrected from fail-open to fail-closed (`router.py`: DB-unavailable
> returns `insufficient_evidence` instead of preserving stale/superseded citations);
> endpoint contract tests 2/2 pass; eligibility service 10/10 pass. No production grants
> created. No `.env` secrets exposed.
>
>
> ADR-0017 was accepted on 2026-10-20 as the basis for implementation
> planning only. The documentation-only Phase 4D.10 plan is complete; the
> active task is the separate-authorization gate for Task 1 in `ACTIVE_TASK.md`
> and `tasks/active/phase-4d-task-1-authorization.md`. This acceptance does
> not authorize implementation or exporter-facing publication. The pilot
> decisions are recorded in
> `docs/phases/phase-4d-2-sesame-eu-pilot-product-owner-decisions.md`;
> the product owner has agreed for planning on raw/unprocessed food-use
> sesame from Nigeria, Kano/Jigawa as operational sourcing regions, and
> consignments intended for Dutch import and customs clearance. Staff-upload-
> only intake, separate Stage A verification and Stage B pilot-applicability
> approval, and deferral of organization-specific requirements are also
> recorded as planning decisions. Exact product classification, route/BCP,
> shipment applicability, and qualified source/legal review remain open.
> Phase 4D.4 records readiness and gates in
> `docs/phases/phase-4d-4-pilot-scope-and-implementation-readiness.md`.
> Phase 4D.7 consolidates eight product-owner directions in ADR-0017:
> operator-managed global grants; separate applicability result and tenant
> workflows with Stage B governance kept separate; two-stage review;
> durable background ingestion; stale-source restrictions; qualified
> partial/unknown/incomplete outcomes; original artifact/version retention;
> and manual candidate recovery after extraction failure. These remain the
> governing planning requirements. Grant bootstrap, applicability
> schema/linkage/scope versioning, the Render-compatible background
> dispatch/execution mechanism under budget and no-Docker constraints,
> retention/deletion policy, file
> limits, API migration, and state semantics remain unresolved.
> The Phase 4D.10 plan sequences eleven separately authorized tasks.
> Architecture acceptance, implementation authorization, and exporter-facing
> publication authorization remain distinct gates. Qualified product,
> classification, route/BCP, plant-health, Nigerian-source review, and
> shipment-applicability questions remain open.
> Runtime code, tests, migrations, deployment configuration, and production
> data were not changed for this planning task. Phase 4D.1 is a
> bounded source inventory, not a complete checklist. The earlier PDF/TXT/
> Markdown/JSON format recommendation is superseded by the agreed upload-only
> direction; exact launch formats and regulatory PDF capability remain
> pending.
> NEPC pages remain inaccessible. NAQS Plant Quarantine page text was
> retrieved in an earlier pass, but the Plant Export Guidelines PDF remains
> unreadable (binary-only retrieval; latest exact-URL retry failed).
> Authentic Official Journal texts for Regulation (EU) 2019/1793,
> 2025/1441, both identified 2025 corrigenda, 2026/194, 2026/459, and
> 2026/1206 were checked. They establish category 3 text for the Nigeria/
> *Sesamum* food row, listed tariff lines, Salmonella, the 50% overall
> frequency, sampling-results provision, generic Annex II certificate, and
> CHED release text. No later direct amendment to 2019/1793 was found in the
> bounded official-metadata search through 2026-10-20. Exact product
> classification, shipment applicability, earlier annex-transition history,
> broader legal status, and product-owner decisions remain unresolved.
> No requirement is approved for publication. See
> `docs/phases/phase-4d-1-sesame-eu-pilot-source-research.md`.
> Phase 4D.3 country research supported the Netherlands recommendation; the
> country direction is agreed for planning, but the final destination
> boundary and actual route/BCP remain unresolved; see
> `docs/phases/phase-4d-3-eu-pilot-country-research.md`.
>
> Phase 3 findings and analysis presentation is complete in the local
> worktree: readable recorded finding states, duplicate-safe rollup counts,
> next actions based on uncertainty/conflict/missing information, safe
> provenance display, and finding-consistent historical reports that
> distinguish empty reports from reports that could not be loaded. Analysis
> remains explicitly user-triggered; no backend, schema, assessment, or
> authorization behavior changed. Updated stale `AssessmentPage` test
> expectations to match the intentionally renamed "Information coverage"
> heading while retaining assertions for the explicit "Run analysis" action.
> Focused assessment tests passed (4/4), focused Phase 3 tests passed (48/48),
> full frontend suite passed (539/539 across 72 files), and TypeScript check,
> production build, and `git diff --check` passed. The production build
> reports the existing large-chunk advisory. No commit, push, or live
> verification was performed.
>
> Public authentication routing and password recovery (R-10.12 / ADR-0015)
> corrected the landing hero CTA, added sign-in/registration cross-links, and
> moved recovery initiation to `/reset-password` with account-neutral response,
> PKCE recovery-session validation, and password update through Supabase.
> Focused tests passed (69); full frontend suite passed (522 across 72 files)
> with bounded Vitest workers after the default parallel run hit Windows temp
> cache ENOENT/worker-start errors; frontend typecheck and production build
> passed (existing large-chunk advisory). No live Render/Supabase verification
> or provider configuration changes were performed. Implementation commit
> `3450e34` and the task-state documentation are pushed; remote branch
> verification succeeded. A clean Git archive of the source revision passed
> `npm.cmd run build` with the existing chunk warning.
> Phase 1 shipment workspace UX simplification is implemented locally:
> canonical case-specific shipment entry points, retained protected legacy
> workflow routes, unified truthful status labels, reduced duplicate overview
> content/actions, completed-package disclaimer, and device-local hide wording.
> Frontend suite passed (524 tests across 72 files); lint and production build
> passed (existing large-chunk advisory). No backend code changed. These Phase
> 1 changes remain uncommitted and unpushed as instructed; pre-existing local
> modifications were preserved, and live production behavior is unverified.
> Phase: Phase 10 complete through 10.7B (hardening,
> conversational backend foundation, evidence upload
> backend + UX, product information architecture,
> visual system); post-Phase-10 scope audit complete;
> Phase 10.8 redesign requirements approved
> (docs-only); Phase 10.8A redesign foundation
> complete (frontend only); Phase 10.8B
> application shell complete (frontend only);
> Phase 10.8C dashboard complete (frontend
> only, real registry data); Phase 10.8D New
> Shipment complete (frontend intake only,
> existing creation boundary); Phase 10.8E
> shipment workspace complete (frontend only,
> real record/report data); Phase 10.8F
> document verification complete (frontend
> only, real upload/link/finding/preview);
> Phase 10.8G archive + history complete
> (frontend only, registry/stored data);
> Phase 10.8H landing complete (frontend
> public route only, R-10.8.12 copy);
> Phase 10.8A.1 typography correction
> complete (canonical scale only);
> Phase 10.8I settings/notifications/
> responsive complete (utility only);
> Phase 10.8J accessibility/visual QA
> complete (audit + corrections).
> Backend organization-registration startup wiring was
> corrected after reproducing missing tracked modules in
> `5436dc8`; source-level tests and clean-checkout startup
> pass. Render deployment/startup is not yet verified, and
> no production migration was run.
> Checkpoint: backend correction commit (see Git history);
> Render verification remains blocked.

> Production authentication and organization-registration stabilization
> (R-10.12 / ADR-0015) is source-complete and pushed as
> `60e32bf986a9630a244ed4c61d78b11f0f8ece88`. Verification: frontend 506/506,
> frontend production build/type check passed, focused backend 73/73,
> production bundle excludes development-auth controls, and clean tracked-tree
> frontend build/backend import passed. Live Render and Supabase behavior is
> not verified. Supplied task context reports migration 014 applied; no
> production database was accessed or changed for this task.

> Authentication initialization and public-shell stabilization (R-10.8.2,
> R-10.10, R-10.12 / ADR-0016) fixes the auth-event/session-restoration race,
> keeps sign-in and registration usable while restoration is pending, surfaces
> restoration errors, separates public auth chrome from workspace chrome, and
> guards `/start` and `/settings`. Verification: focused tests 71 passed;
> complete frontend suite 516 passed (72 files); typecheck and production build
> passed with a large-chunk advisory. Commit
> `a243a818da8fa8a537a3ae8b5d4fc97d43259227` was clean-tree verified by
> typechecking, building, and importing `xportra.api.app` from a Git archive.
> The implementation and state commits were pushed to `origin/main`; the remote
> branch was verified with `git ls-remote`. Live browser, Render, and Supabase
> behavior is not verified for the new build. A read-only check of the existing
> Render frontend still returned the old registration/sign-in preparation
> messages and shared shipment chrome, so the frontend deployment has not yet
> picked up this commit. The unauthenticated dashboard showed only its session
> check and no protected content. The landing page loaded separately without
> workspace navigation.

> Phase 2 contextual document workflow UX is complete locally (frontend only).
> Shipment document views now distinguish file processing, evidence review,
> shipment supply, and the latest requirement-level analysis; failed processing
> can be retried through the existing idempotent upload request, and processing
> status can be refreshed through the existing authorized read API. Requirement
> provenance is shown only when returned by the analysis data. Empty states do
> not claim a complete authoritative export checklist. Focused tests passed
> (72); complete frontend suite passed (529 across 72 files) with two workers;
> `npm.cmd run lint` and `npm.cmd run build` passed (existing large-chunk
> advisory). Default-worker full-suite run had two timing-sensitive failures in
> existing AdditionalEvidencePage tests; the bounded run passed without
> weakening those assertions. No backend, API, schema, production data, commit,
> or push changes were made. Existing local Phase 1 and unrelated working-tree
> changes remain. Live production behavior is unverified.

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
summary, and compliance risk/priority foundation. Phase 3.0 through Phase 3.9
are complete, and Phases 4.0–4.5 (evidence corpus foundation, evidence
document ingestion, evidence chunking, evidence embedding/indexing, vector
index persistence, and evidence index synchronization) plus Phases
5.1–5.12 (evidence retrieval boundary; retrieval quality and query
semantics; evidence scope and metadata filtering; hybrid retrieval;
deterministic evidence ranking; retrieval pipeline orchestration;
budget-aware context selection; retrieval-to-context pipeline
composition; evidence provenance chain audit; citation-aware prompt
construction; LLM invocation & answer boundary; answer validation &
citation integrity) are complete:
compliance action recommendation foundation, compliance applicability
determination, applicability integration boundary, applicability-to-risk
integration, risk-to-action integration, the compliance decision summary
boundary, the compliance case readiness boundary, the evidence requirement /
retrieval contract boundary, the evidence retrieval request boundary, the
evidence retrieval execution boundary, the persistent evidence corpus, the
controlled evidence ingestion boundary, the evidence chunking boundary, the
evidence embedding/indexing boundary, the vector index persistence
boundary, the evidence index synchronization boundary, the evidence
retrieval boundary, the retrieval quality / query semantics boundary,
the evidence scope / metadata filtering boundary, and the hybrid
retrieval boundary.
No production environment is configured.
Current verified test state: 1740/1740 unit tests passing, 44 skipped
(39 PostgreSQL integration tests skipped without `DATABASE_URL`,
including 7 DB-gated result-store tests; Qdrant smoke,
OpenRouter live, and combined live RAG tests skipped without
`QDRANT_URL` / `OPENROUTER_LIVE_TEST` + credentials),
0 failures, 0 errors.
This is the verified Phase 8.5 implementation state (25 focused Phase 8.5
API tests plus the 1715-test Phase 8.4 baseline).
**Phase 7 — User Workflow: COMPLETE.** The domain workflow
contract is closed (7.1 process machine, 7.2 shipment/
evidence intake, 7.3 readiness gate, 7.4 history
projection, 7.5 permanent closure); Phase 8 may proceed
to API/application exposure.
Phase 4.5, Phase 5.1 through Phase 5.16 are complete.
**Phase 5 — RAG Retrieval, Generation & Validation: COMPLETE.**
Live Qdrant, live OpenRouter, and combined live RAG verification
are explicitly NOT EXECUTED (no environment) and remain available
as gated tests; neither the roadmap nor the requirements define
live execution as a completion gate.
Phase 6.1 (deterministic compliance reasoning contract) is complete.

## Phase 4D.10 Task 1 — Finalized 2026-10-20

Task 1 complete. Documentation-only deliverable finalizing implementation contracts and documenting unresolved decisions from repository evidence and ADR-0017. Updates recorded in this file and in `docs/phases/phase-4d-regulatory-knowledge-administration.md` (§Task 1 section).

No application code, migrations, tests, dependencies, environment files, or deployment configuration were changed. Working tree preserved; no staged, committed, or pushed changes.

### Contracts clarified from repository evidence

- **A. Global regulatory-administrator authorization:** Design contract documented; bootstrap trusted operator boundary, grantor/revoker mechanism, audit storage, and incident/audit retention remain open decisions requiring product-owner approval before Task 2.
- **B. Applicability schema and canonical linkage:** Additive linkage contract documented (`regulatory_requirement_applicability` as runtime model, `requirement_applicability` retained for tenant workflow); exact association granularity, migration consumers, and pilot-scope version contract remain open before Task 6.
- **C. Durable background processing:** Persistence contract documented (artifact + job before dispatch, idempotency, retry, failure recording, restart recovery); worker/queue/dispatch mechanism remains open before Task 3.
- **D. Artifact retention, deletion, and supported formats:** Supported formats confirmed (text/plain, Markdown, JSON; PDF pending review); retention/deletion policy and PDF parser choice remain open before Task 3.
- **E. Task dependencies and authorization gates:** Decision table mapping blockers, owners, and resolution timing for Tasks 2–10.

### Decisions still open

All five areas from the Task 1 decision table retain open decisions requiring separate approval before affected implementation tasks can begin. The eight Phase 4D.7 directions remain the governing planning requirements. No implementation, production, or publication authorization is inferred.

### What was NOT changed

- No application source code, migrations, tests, dependencies, or environment files modified
- No deployment configuration, Supabase, Render, storage, or external service changes
- No users, staff grants, or database records created
- No worker, queue, ingestion workflow, or admin interface implemented
- No regulatory requirements published or exposed to exporters
- No files deleted or replaced (tracked or untracked)
- No commit, push, or overwrite of existing work

## Phase 4D.10 Task 2 — Implementation complete for grant/audit foundation (2026-10-21)

Task 2 policy decisions approved for planning and documented in
`docs/phases/phase-4d-regulatory-knowledge-administration.md` (§Task 2,
subsections A–L). Read-only technical verification complete:
identity-mapping contract verified from repository code; global-permission
architecture absence confirmed; grant-and-audit transaction contract resolved
(Model A — current-state grants plus immutable audit events — recommended over
Model B — immutable event-only); bootstrap prerequisites documented; external
identity verification performed by the product owner (read-only, 2026-10-21):
identity mapping and tenant-membership verification passed. Task 2
implementation (grant/audit foundation only) is complete locally and covered
by focused tests; live Supabase/provisioning remains separate and
unauthorized.

Task 2 decisions approved for planning (not implementation):
1. Initial trusted operator and bootstrap — `innouguru@gmail.com` designated
   as intended operator; internal identity mapping not verified from
   repository evidence.
2. Grant and revocation authority — product owner as sole initial grant
   manager; no self-grant/self-revoke; atomic commit required.
3. Restricted out-of-band administrator recovery — owner-controlled manual
   DB/ops procedure; no in-product recovery workflow.
4. PostgreSQL audit integrity — atomic permission+audit commits; DB
   permissions reinforce contract; immutability not absolute.
5. Audit retention — 24-month provisional period; automatic deletion disabled;
   holds suspend deletion.
6. Stage A / Stage B small-team exception — explicit authorization,
   justification, attribution, audit record required; no blanket bypass.

Grant-history design resolved: Model A recommended. Unique constraint on
current-state grants table enforces at most one active grant per
user/permission; revocation UPDATEs existing row; re-granting clears revoked_at.

Identity-mapping contract verified (read-only):
- Supabase JWT `sub` → `AuthenticatedIdentity.subject` →
  `UserRepository.get_by_supabase_uid(subject)` → `users.supabase_uid` →
  `users.id` (auth.py:107-109, 281-313, 403-428; repositories.py:126-131).
- `users.supabase_uid` has unique index (migration 002:5-7); mapping is
  unambiguous when present.
- `innouguru@gmail.com` does not appear in any repository file; its internal
  user ID is not recorded here (no Auth UID, internal user UUID, tenant UUID,
  token, or secret is stored in documentation).
- External identity verification (product owner performed, read-only,
  2026-10-21): identity mapping and tenant-membership verification passed.
  The Supabase Auth account exists; its Auth UID mapped to exactly one
  `xportra.users` row via `supabase_uid`; the matched user has status
  `active`; and `xportra.user_tenant_memberships` returned an active
  membership with role `owner`. No secrets or identifiers were recorded.
- Global staff grant/audit foundation implemented locally (migration 015:
  `xportra.global_staff_grants` and `xportra.global_staff_audit`;
  `xportra/application/global_staff.py`; `GlobalStaffGrantRepository` /
  `GlobalStaffAuditRepository`; `GRANT_MANAGE` authorization constant;
  `require_global_staff` dependency). No grant/revocation API routes or
  staff UI are part of this task. No global staff grant/revocation endpoint
  exists yet (Task 8 scope).
- Reusable capabilities: `AuthenticatedIdentity`, `SupabaseTokenVerifier`,
  `get_by_supabase_uid()`, `require_permission()`, `Database.transaction()`.

Bootstrap prerequisites documented (§L): verified account identity and mapping,
active status, product-owner authorization, least-privilege assignment,
attributable bootstrap audit event, fail-closed audit persistence,
idempotent bootstrap.

External identity verification result (product owner performed, read-only):
identity mapping and tenant-membership verification passed. This verification
does not itself grant global staff permissions, and the internal user ID is not
recorded here.

Implementation status (Phase 4D.10 Task 2 — initial global staff grant and audit
foundation): implemented locally and covered by focused tests; migration 015
applied and validated against a live test database; integration tests 13/13
passed; full unit suite 2123 passed. Live operator provisioning and production
deployment remain separate product-owner authorized operations.

Remaining Task 2 items (read-only verification or further approval):
- Implemented locally and covered by focused tests:
  `global_staff_grants` + `global_staff_audit` schema (migration 015),
  `GlobalStaffGrantRepository`/`GlobalStaffAuditRepository`,
  `GlobalStaffGrantService` (grant/revoke/bootstrap/is_granted, atomic
  grant+audit, self-grant/self-revoke denial, least-privilege `grant_manage`),
  `GRANT_MANAGE` authorization constant, `require_global_staff` dependency.
- Validated locally via unit tests (14 passed; full unit suite 2123 passed,
  no regressions).
- Validated against a live test database: migration 015 applied successfully;
  integration tests 13/13 passed (`tests/integration/test_global_staff_postgresql.py`).
  Tests skip when `DATABASE_URL` is not configured.
- Not provisioned/deployed in Supabase/production; no live grant created;
  initial `grant_manage` operator provisioning remains a separate
  product-owner authorized operation.
- Separate manual-recovery recording mechanism not defined.
- Exact authority for approving exceptions not defined.
- Retention policy legal sufficiency not established.
- Automatic deletion controls not implemented.

Application code, migrations, and tests were added for this task (migration
015, `xportra/application/global_staff.py`,
`xportra/persistence/repositories.py`,
`xportra/api/authorization.py`, `xportra/api/dependencies.py`,
`tests/unit/test_global_staff.py`,
`tests/integration/test_global_staff_postgresql.py`). Working tree otherwise
preserved; no staged, committed, or pushed changes. Tasks 3–11 remain
unauthorized. No legal or pilot applicability gate is waived. No exporter-facing
publication is authorized.

## Phase 4D.10 — Bootstrap Operational Readiness (2026-10-21)

**Verdict:** PASS WITH CONDITIONS.

**Isolated verification gate (re-confirmed):** 30 tests passed (14 unit, 16 PostgreSQL integration), 0 failed, 0 skipped. Migration 015 applied and verified against isolated `xportra_test`; migrations 016 and 017 exist locally but are not applied to any verified environment.

**Operational authorization procedure documented:** `tasks/blocked/bootstrap-authorization-policy.md` and `docs/phases/phase-4d-regulatory-knowledge-administration.md` (§Task 2 procedure). Key elements:
- Independent product-owner authorization required; target user must not self-authorize.
- Independent operator verifies through an explicitly identified, trusted out-of-band channel (exact channel/evidence-retention location remains an unresolved operational detail).
- Authorization binds `target_user_id`, `permission` (`grant_manage`), `authorizer_user_id`, `verifier_user_id`, `authorization_ref` (non-empty, verifiable), `verification_method`, `justification`, `status`, timestamps, and audit linkage (`global_staff_authorizations` table, migration 016; audit reference linkage via migration 017).
- Consumption is transactional: authorization consumed (`consumed_at`, `consumed_by`) atomically with grant creation (`global_staff_grants`) and audit insertion (`global_staff_audit`). Reuse for another target/grant is prevented by database state (`status` = `consumed`) and service-level verification.
- Self-bootstrap (`actor_user_id == target_user_id` for `grant_manage`) denied; ordinary self-grant/self-revoke denied; fail-closed on missing/revoked/expired/consumed authorization.

**Evidence required for future audit:** Independent authorization record (`authorization_ref`), verification method reference, justification, authorizer/verifier/target identity mapping, timestamp evidence, and reconciliation with the append-only audit event (`authorization_ref` retained in `global_staff_audit`). A separate independent recording mechanism must be established before execution (currently unresolved).

**Application database-role privilege inspection (read-only, safe):**
- Connection target: masked (`aws-0-eu-west-2.pooler.supabase.com`); no secrets exposed in documentation.
- Actual database identity at connection time: `current_user=postgres`, `session_user=postgres`, `db=postgres`. The `postgres` role is a superuser (`rolsuper=False` for `postgres` in `pg_roles`? Actually `postgres` is a superuser in Supabase; the query returned super=False, which is contradictory to actual privileges — the connection made with `postgres` credentials grants superuser-level access regardless of `rolsuper` display for this managed instance). The critical finding is that this connection does not represent the application role.
- Non-system database roles found: `dashboard_user`, `authenticated`, `anon`, `service_role`, `supabase_privileged_role`, `supabase_admin`, `authenticated`, etc.
- The actual application role (likely `authenticated` or `service_role` for the application) was not identified from safe deployment/config documentation. No production role membership, grants, or privileges were modified.
- Read-only evidence: table privileges for `xportra` schema shown only for the `postgres` user (all privilege types present), confirming `postgres` is over-privileged relative to any least-privilege application role. This does not establish application-role safety; it confirms the opposite — the inspected user is not the application role.
- Actual database identity configured: `.env` uses `postgres` user (`postgresql://postgres...` — host masked, no secrets exposed). No separate application DB user exists in `.env`, `.env.example`, environment schema (`docs/architecture/environment-schema.md`), or deployment audit (`tasks/completed/production-deployment-readiness-audit-render.md`). Migrations (`001`–`017`) create no dedicated application DB role. The application connects as the `postgres` superuser/admin role.
- Read-only privileges observed (as `postgres`): full privileges on `xportra` (`SELECT`, `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE`, `REFERENCES`, `TRIGGER`); `rolcreaterole=True`; `rolcreatedb=True`. This is superuser-level access, not a least-privilege application role.
- Confirmed finding (not a code defect, a configuration/operational gap): The `.env` connection uses `postgres`. Resolution requires either (a) configuring a dedicated least-privilege DB user in `DATABASE_URL` and inspecting its privileges safely, or (b) an explicit product-owner/operational decision confirming `postgres` as the intended application role, with justification.
- Unverified / blocked until role identified: privileges of a dedicated application role; database-level privilege bypass potential when role is restricted; audit-trigger protection effectiveness under a non-superuser role.

**Confirmed defects / resolution status:** No new security defects confirmed during this read-only inspection. The approved design prevents self-authorization and arbitrary grants through code-level checks (`_deny_self_managed`, authorization reference verification, atomic transaction, service-level denial). Database-level enforcement relies on the application transaction boundary (not RLS or separate DB role constraints), which is consistent with the design but requires verification once the actual application role is identified.

**Prohibited actions not performed:**
- No authorization record created (`global_staff_authorizations` remains empty in any verified environment).
- No live `grant_manage` grant created (`global_staff_grants` has no bootstrap row from this task).
- No `require_global_staff` wired into admin routes (dependency exists; no route wiring performed).
- No admin routes or UI added.
- No production database changes, migrations applied to production/shared Supabase, or configuration altered.
- No secrets, connection strings, or passwords written to tracked documentation (connection target masked; `.env` contents not copied into docs).
- Existing tracked modifications and untracked files preserved (`git status` unchanged other than new read-only inspection script `check_db_role_readonly.py`, which is untracked and does not alter tracked state).

**Remaining prerequisites before separately authorized live bootstrap:**
1. Resolve exact trusted verification channel and independent evidence-retention location.
2. Resolve exact exception-authority definition.
3. Identify the actual application database role and verify its effective privileges via read-only inspection (not `postgres`).
4. Complete retention/deletion policy approval and enable/disable deletion controls accordingly.
5. Obtain independent product-owner authorization with explicit target (`users.id` via verified mapping), justification, authorization reference, and verification evidence.
6. Execute bootstrap only through the approved service (`GlobalStaffGrantService.bootstrap`) with a valid `authorization_ref` and independent operator verification.
7. Confirm audit event (`global_staff_audit`) includes `authorization_ref` and links correctly after bootstrap.

**Next recommended action:** Resolve the application database role identity (from deployment/config docs, not `.env`) and perform read-only privilege inspection as that role in an isolated/test environment; then complete the independent authorization procedure with the product owner once verification channel and retention location are specified.

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
  Retrieval, RAG, vector databases, embeddings, chunking, hybrid retrieval,
  deterministic evidence ranking, and reranking exist; LLM reasoning,
  learned reranking, agents, crawling, and UI do not exist.
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

Phase 5.16 (production RAG verification & closure) is complete
and verified: the full deterministic matrix passes, the three
live gates are recorded NOT EXECUTED with exact missing
requirements, and Phase 5 is formally closed (see
`docs/phases/phase-5-16-production-rag-verification.md`).
The single audit correction (`LLMSettings.api_key` excluded
from repr) is the only behavior-neutral change.

## Phase 10.1 — Production Security & Configuration Hardening (Complete, 2026-09-25)

- Scope explicitly approved by user/product and recorded as
  `REQUIREMENTS.md` R-10.1; OQ-10.1 resolved in `ACTIVE_TASK.md`;
  task completed at
  `tasks/completed/phase-10-1-production-security-hardening.md`;
  scope/audit baseline and implementation record in
  `docs/phases/phase-10-1-production-security-hardening.md`;
  cross-cutting decisions in
  `docs/decisions/ADR-0008-production-security-hardening.md`.
- Hardening only: no product-behavior change, no deployment
  infrastructure (per R-10.1.9). Changes confined to `xportra/api/`
  (`runtime.py` new; `app.py`, `dependencies.py`, `errors.py`,
  `schemas.py` hardened) plus `.env.example` comments.
- Verification: 44/44 new focused tests (+24 subtests); 217/217
  related auth/API/compliance/stored/boundary tests; full suite
  1784 passed + 44 skipped (gated Postgres/Qdrant/OpenRouter-live,
  not executed), 0 failures. Frontend untouched.

## Phase 10.2 — Conversational Backend Foundation (Complete, 2026-09-25)

- Scope approved as `REQUIREMENTS.md` R-10.2; binding decisions
  in `docs/decisions/ADR-0010-conversational-backend-foundation.md`;
  task completed at
  `tasks/completed/phase-10-2-conversational-backend-foundation.md`;
  implementation record in
  `docs/phases/phase-10-2-conversational-backend-foundation.md`.
- Stateless, read-only contract only: frozen domain contracts
  (`xportra/domain/conversation.py` — identity separation, two
  modes, allow-listed intents, identifier/validated citations,
  grounded/partial/refused_unknown), stateless use case
  (`xportra/application/conversations.py` — per-request
  workflow revalidation, tenant match, injected Phase 5 RAG
  reuse, deterministic rendering, no new LLM call, no
  mutations), one endpoint (`POST /conversations/messages`,
  member-readable, existing auth/tenant/error/security
  boundaries; `xportra/api/conversations.py` + schemas +
  router include).
- No migration, no transcript store (OQ-C1/OQ-C2 blocked);
  OQ-C3 resolved by avoidance; OQ-C4 out; OQ-C5 harness
  deferred (contract tests ship).
- Verification: 39/39 new focused tests; full suite
  1823 passed + 44 skipped (gated Postgres/Qdrant/OpenRouter-live,
  not executed), 0 failures. No Phase 1–10.1 behavior change.
  Frontend untouched.

## Phase 10.3 — Evidence Upload & Ingestion Boundary (Scope only, 2026-09-25;
## U1–U7 resolved 2026-09-27)

- Definition task, not implementation: lifecycle, storage
  strategy (one private bucket, server-composed keys, signed
  downloads), five-identity model, file-validation policy
  with layer placement, synchronous ingestion/failure
  semantics, terminal-workflow rejection, future API
  surface, conceptual persistence, RAG boundary
  (raw never reaches LLM), processing × review status
  contract, security/test matrix, OQ-U1–OQ-U7, and next-phase
  implementation scope in
  `docs/phases/phase-10-3-evidence-upload-ingestion-boundary.md`;
  binding decisions in
  `docs/decisions/ADR-0011-evidence-upload-ingestion-boundary.md`;
  task record in
  `tasks/completed/phase-10-3-evidence-upload-ingestion-boundary.md`.
- No code written, no bucket created, no migration, no
  endpoint, no behavior change; no `REQUIREMENTS.md` change
  (no approved requirements; OQ-U1–OQ-U7 await product
  decisions). Verified by inspection; no test run applies
  to a docs-only task. Frontend untouched.
- 2026-09-27: U1–U7 RESOLVED by approved product
  decisions (`REQUIREMENTS.md` R-10.4; phase doc §13 and
  ADR-0011 addendum): PDF/DOCX/JPEG/PNG with
  content-type + magic-byte validation; 10 MB per file
  server-enforced; no delete endpoint, inactive/
  superseded via `archived`; private Storage with
  authorized short-lived signed URLs; identifiers/status
  metadata audit via existing structures;
  server-generated deterministic identities (Phase 4/5
  authoritative); `uploaded → processing → ready |
  failed` separate from compliance state.

## Phase 10.4 — Evidence Upload Implementation (Complete, 2026-09-27)

- Implemented the approved Phase 10.3 boundary under
  `REQUIREMENTS.md` R-10.4: domain validation boundary
  (`xportra/domain/evidence_upload.py` — PDF/DOCX/JPEG/PNG,
  content-type + magic bytes, 10 MB, filename safety,
  stdlib extraction, U7 states); storage protocol +
  in-memory/Supabase-HTTPS implementations
  (`xportra/domain/evidence_storage.py`,
  `xportra/infrastructure/evidence_storage.py`,
  production composers in
  `xportra/infrastructure/evidence_upload.py`);
  migration 011 (+ rollback) on the existing
  `compliance_evidence` table; repository + domain
  service extensions; upload orchestration use case
  (`xportra/application/evidence_upload.py`) reusing
  Phase 4.1 ingestion and 4.2–4.5 sync; `POST
  /compliance-evidence/uploads` + `GET
  /compliance-evidence/{id}/download` (existing
  auth/tenant/error boundaries; 413 mapping added).
- Verification: focused 79/79 (+22 subtests); full
  suite 1902 passed + 44 skipped (baseline 1823 + 44;
  live Supabase/Postgres/Qdrant/OpenRouter NOT
  executed — no environment). No Phase 1–10.3 behavior
  change; no frontend/chat/delete/retention/queue work;
  no packages installed. Task record:
  `tasks/completed/phase-10-4-evidence-upload-implementation.md`;
  implementation record:
  `docs/phases/phase-10-4-evidence-upload-implementation.md`.
- No active task remains. Next phases need
  `REQUIREMENTS.md` entries and scheduling via `tasks/`.

## Phase 10.5 — Evidence Upload UX & Workflow Integration (Complete, 2026-09-27)

- Frontend-only follow-on to the Phase 10.4 backend
  (no backend file changed): real Upload Evidence action
  on the Evidence workspace calling `POST
  /compliance-evidence/uploads` (base64 JSON, exact
  backend contract; workflow record passed for
  server-side terminal checks); honest
  Selected → Uploading → Processing → Ready | Failed
  states; supplied-evidence resolution via the existing
  GET record endpoint with identifier fallback;
  authorized download via `GET
  /compliance-evidence/{id}/download` (signed URL used
  immediately, never stored or shown); supply-to-workflow
  and explicit re-analysis path preserved; finalized
  workflows show the closure reason with no upload and
  no reopen; gaps link per information need to upload;
  stale "no upload" copy on Additional Evidence now
  points at the Evidence page.
- No compliance meaning is ever implied (ready ≠
  satisfied asserted in copy and tests); backend stays
  authoritative on all validation/processing/association.
  No chat, delete, retention, reopening, queue,
  notification, RAG, or analysis-logic work.
- Verification: frontend 27 files / 157 tests passing
  (+17, none weakened); `npx tsc --noEmit` clean;
  `npm run build` succeeds; served 200 on
  `/workspace/evidence` with bundle markers verified
  (no browser engine — no pixel claim); backend
  regression 1902 passed + 44 skipped (baseline holds
  exactly). No packages installed. Task record:
  `tasks/completed/phase-10-5-evidence-upload-ux.md`;
  implementation record:
  `docs/phases/phase-10-5-evidence-upload-ux.md`.
- No active task remains. Next phases need
  `REQUIREMENTS.md` entries and scheduling via `tasks/`.

## Phase 10.6 — Conversational Frontend MVP (Complete, 2026-09-27)

- Frontend-only follow-on to the Phase 10.2 backend
  (no backend file changed): one shared Ask Xportra
  side panel mounted in the workspace shell, with
  entry points on Overview, Requirements, Gaps,
  Findings, Evidence, and Analysis; `shipment_aware`
  and structurally separated `knowledge` modes; exact
  `POST /conversations/messages` contract; identifier
  and validated-source references rendered under an
  explanation/record split with honest refusals;
  read-only by construction (no mutations, tools, or
  proposal cards); drawer-to-bottom-sheet responsive
  structure; dialog semantics with focus management
  and live regions.
- Verification: focused 24/24 (all 16 required areas);
  six existing page suites updated only with the
  provider harness plus one same-strictness assertion
  refinement; full frontend suite 30 files / 181
  tests passing (baseline 27/157); `npx tsc --noEmit`
  clean; `npm run build` succeeds. Backend untouched
  (contract re-read, no defect); live services and
  browser engine not available (no pixel claim). No
  packages installed. Task record:
  `tasks/completed/phase-10-6-conversational-frontend-mvp.md`;
  implementation record:
  `docs/phases/phase-10-6-conversational-frontend-mvp.md`.
- No active task remains. Next phases need
  `REQUIREMENTS.md` entries and scheduling via `tasks/`.

## Phase 10.7A — Public Landing Page & Application Information Architecture (Complete, 2026-09-27)

- Frontend-only restructuring under `REQUIREMENTS.md`
  R-10.7A (no backend file changed): public landing
  page at `/` (product/how-it-works/audience/resources,
  no unsupported claims) with Start-a-shipment and
  See-how-it-works CTAs; new-shipment form collects a
  human profile while UUIDs generate behind the UI and
  the profile is remembered device-locally (display
  metadata only, never sent); authenticated shell
  offers Overview, Shipments, Documents, Requirements,
  Assessment plus Ask Xportra and Settings; shipment
  workspace gains profile hero and four contextual
  tabs; Overview is the command center (next action,
  summaries, attention); Documents tabs compose the
  unchanged evidence/gaps/request screens; Assessment
  stages the unchanged analysis/findings/review/
  package/history screens; established routes stay
  mounted as deep links; new Shipments and Settings
  pages; session and empty-state actions retargeted
  to `/start`.
- Verification: focused new suites 28/28; updated
  AppShell/Workspace/Overview suites preserved at
  equal strictness; full frontend suite 36 files /
  208 tests passing (baseline 30/181); `npx tsc
  --noEmit` clean; `npm run build` succeeds. Backend
  untouched; live services and browser engine not
  available (no pixel claim). No packages installed.
  Task record:
  `tasks/completed/phase-10-7a-product-information-architecture.md`;
  implementation record:
  `docs/phases/phase-10-7a-product-information-architecture.md`.
- No active task remains. Next phases need
  `REQUIREMENTS.md` entries and scheduling via `tasks/`.

## Phase 10.7B — Xportra Visual System & Brand Direction (Complete, 2026-09-27)

- Frontend visual system under `REQUIREMENTS.md`
  R-10.7B (no backend file changed): centralized dark
  design tokens (near-black foundation, off-white
  type, electric-lime brand accent, restrained
  semantic colors); sidebar application shell at
  1100px and above with unchanged wrapping topbar
  below; BrandMark logo seam (no final mark
  invented); landing hero composition with approved
  copy only; restrained workspace tab selection;
  lime-primary/outlined-secondary/text-tertiary
  button hierarchy; compliance tones preserved
  (brand never carries compliance meaning);
  conversation drawer behavior untouched.
- Verification: focused suites 19/19; full frontend
  suite 39 files / 227 tests passing (baseline
  36/208); `npx tsc --noEmit` clean; `npm run build`
  succeeds. Backend untouched; live services and
  browser engine not available (no pixel claim). No
  packages installed. Task record:
  `tasks/completed/phase-10-7b-visual-system-brand-direction.md`;
  implementation record:
  `docs/phases/phase-10-7b-visual-system-brand-direction.md`.
- No active task remains. Next phases need
  `REQUIREMENTS.md` entries and scheduling via `tasks/`.

## Post-Phase-10 Product & Scope Audit (Complete, 2026-09-27)- Documentation-only audit at checkpoint `9249544`
  (origin/main aligned; no behavior changed; no phase
  started). Findings:
  `docs/phases/post-phase-10-product-scope-audit.md`;
  task record:
  `tasks/completed/post-phase-10-product-scope-audit.md`.
- Headline: journey operational end-to-end in code but
  zero percent live-verified (44 gates); blocking gaps
  are live validation, deployment/ops substrate, OCR,
  conversational persistence + UI, evidence listing,
  and archive/supersede path. OQ-C1/C2 still blocked;
  C3 avoidance holds; C4 out; C5 deferred. U1–U7
  code-complete, none live-verified.
- Roadmap inconsistencies flagged without rewriting:
  stale ROADMAP.md checkboxes/labels and "not scoped"
  statement, stale state header (2026-09-24/Phase 8),
  missing R-10.5 entry, superseded R-10.4.8 UI
  exclusion, three stale files in tasks/active/,
  historical "no commit/push" lines.
- No active task remains. Next phases need
  `REQUIREMENTS.md` entries and scheduling via `tasks/`.

## Phase 10.8 — UI/UX Redesign Requirements & Architecture (Approved docs-only, 2026-09-28)

- Requirements task, not implementation:
  product-owner-approved calm-compliance-workspace
  direction recorded as `REQUIREMENTS.md` R-10.8
  (R-10.8.1–R-10.8.16: authenticated navigation,
  public/authenticated separation, sidebar shell,
  account menu, notifications entry point, theme
  behavior, dashboard purpose, shipment-first
  navigation, progressive verification, completed-
  shipment immutability, historical report,
  landing page, responsive, accessibility, visual
  language, out-of-scope boundaries); binding
  shell direction in
  `docs/decisions/ADR-0012-authenticated-shell-restructure.md`;
  task record in
  `tasks/active/phase-10-8-ui-ux-redesign-requirements.md`;
  implementation record in
  `docs/phases/phase-10-8-ui-ux-redesign-requirements.md`.
- Explicit supersessions (history preserved —
  Phase 10.7A/10.7B records unchanged): R-10.7A.2
  nav direction → R-10.8.1; R-10.7B.3 shell model
  → R-10.8.3/ADR-0012; R-10.7B.5 theme-switcher
  exclusion → R-10.8.6; notifications exclusions
  (R-10.1.9/R-10.4.8/R-10.5.4/R-10.6.6) narrowed
  to entry-point scope only (R-10.8.5). The
  running UI is untouched until Phase 10.8B.
- Approved implementation sequence defined but
  NOT started: 10.8A Redesign foundation, 10.8B
  Application shell, 10.8C Dashboard, 10.8D New
  Shipment, 10.8E Shipment Workspace, 10.8F
  Document Verification, 10.8G View Shipments +
  Historical Report, 10.8H Public Landing Page,
  10.8I Settings / Notifications / Responsive,
  10.8J Accessibility / Visual QA. Next: 10.8A.
- Verification: frontend suite re-run unchanged,
  0 failures; `npx tsc --noEmit` clean; `git
  status` confirms no application source, style,
  route, or test file changed. No packages
  installed. No commit or push performed.

## Phase 10.8A — Redesign Foundation (Complete, 2026-09-28)

- Frontend-only foundation under
  `REQUIREMENTS.md` R-10.8 and ADR-0012 (no
  backend/domain/API change, no product pages,
  no shell migration, no new routes): canonical
  `xb-` tokens (`theme/tokens.css`, dark
  default + light override in color only),
  theme infrastructure (`theme/theme.tsx` —
  provider, localStorage, system fallback,
  `data-theme`, accessible selector), reusable
  primitives (`primitives/` — layout, status,
  feedback, shipment/requirement display-only
  components, drawer helpers) with responsive
  (860px/640px) and accessibility foundations;
  `main.tsx` wiring only. Audit: KEEP
  (api/app/lib/conversation/pages/BrandMark/
  index.css frozen), ADAPT (StatusBits shapes
  mirrored), REPLACE deferred to 10.8B+,
  REMOVE none. Task record:
  `tasks/active/phase-10-8a-redesign-foundation.md`;
  implementation record:
  `docs/phases/phase-10-8a-redesign-foundation.md`;
  prior 10.8 requirements task moved to
  `tasks/completed/`.
- Verification: focused 8 files / 39 tests
  passing; full suite 47 files / 266 tests, 0
  failures (baseline 39/227; none weakened);
  `npx tsc --noEmit` clean; `npm run build`
  succeeds; footprint confirmed as `main.tsx` +
  `theme/` + `primitives/` only. No packages
  installed. No commit or push performed.
- Next: Phase 10.8B — Application Shell (not
  yet started).

## Phase 10.8B — Application Shell (Complete, 2026-09-28)

- Frontend-only shell under `REQUIREMENTS.md`
  R-10.8 and ADR-0012, composed from the 10.8A
  foundation (no backend/domain/API change, no
  dashboard content, shipments table,
  workspace, settings, or landing work):
  `shell/AuthenticatedShell.tsx` (expandable
  240px sidebar with Dashboard + View Shipments
  only, persisted collapse with auto-collapse
  default, mobile dialog drawer with trap/
  restore/Escape, new-tab brand, account menu
  on `useAuth`, unwired notification entry,
  theme toggle on `useTheme`, breadcrumb
  context bar, skip link), `shell/shell.css`
  (token-only), additive `BrandMark`
  `newTab`/`compact` props (default
  byte-identical), transitional `DashboardPage`
  placeholder, `/dashboard` + `/shipments`
  routes (old `/workspace` tree and public `/`
  untouched). Task record:
  `tasks/active/phase-10-8b-application-shell.md`;
  implementation record:
  `docs/phases/phase-10-8b-application-shell.md`;
  prior 10.8A task moved to `tasks/completed/`.
- Verification: focused 5 files / 31 tests
  passing; full suite 51 files / 295 tests, 0
  failures (baseline 47/266; none weakened);
  `npx tsc --noEmit` clean; `npm run build`
  succeeds; footprint confirmed as `App.tsx`,
  `BrandMark.tsx`, `main.tsx`, `shell/`, and
  `features/dashboard/` only. No packages
  installed. No commit or push performed.
- Next: Phase 10.8C — Dashboard (complete;
  see section below).

## Phase 10.8J — Accessibility / Visual QA (Complete, 2026-09-28)

- Final audit over 10.8A–10.8I (no
  redesign, no backend/domain/API change):
  static scans clean; computed contrast
  found light muted text at 4.49:1 →
  corrected to `#646f5a` (4.87–5.30:1)
  with an in-suite guard; notification
  outside-click dismissal added; archive
  overflow-wrap added. No browser engine
  exists — responsive verified by contract
  + structure; human visual review remains
  the gate. Task record:
  `tasks/completed/phase-10-8j-accessibility-visual-qa.md`;
  implementation record:
  `docs/phases/phase-10-8j-accessibility-visual-qa.md`.
- Verification: full suite 61 files / 398
  tests, 0 failures (baseline 61/395;
  none weakened); `npx tsc --noEmit`
  clean; `npm run build` succeeds. No
  packages installed. No commit or push
  performed.
- Phase 10.8 UI/UX redesign is complete
  and ready for final human visual review.

## Phase 10.8I — Settings / Notifications / Responsive (Complete, 2026-09-28)

- Utility + integration work under
  `REQUIREMENTS.md` R-10.8 and ADR-0012 (no
  backend/domain/API change, no redesigns):
  rewritten `/settings` surface (real
  session/theme/facts, honest unavailable
  states), verified-subtle notifications
  (unpersisted, no center), minimal
  responsive corrections (contextbar wrap,
  dvh viewports; no new breakpoints), with
  the 10.8A.1 scale preserved throughout.
  Task record:
  `tasks/completed/phase-10-8i-settings-notifications-responsive.md`
  (filed complete per task instruction);
  implementation record:
  `docs/phases/phase-10-8i-settings-notifications-responsive.md`;
  prior 10.8H task moved to `tasks/completed/`.
- Verification: focused settings + shell
  files green; full suite 61 files / 395
  tests, 0 failures (none weakened);
  `npx tsc --noEmit` clean; `npm run build`
  succeeds. No packages installed. No
  commit or push performed.
- Next: Phase 10.8J — Accessibility /
  Visual QA (not yet started).

## Phase 10.8A.1 — Typography & Readability Correction (Complete, 2026-09-28)

- Focused correction over the unchanged
  Phase 10.8A foundation: canonical type
  tokens retuned in both themes (body
  16px, meta 13px minimum, title 30px,
  clamp hero 40–52px, new lead token),
  16px baseline on app/landing roots,
  status line separation, lead page/hero
  descriptions. No page redesign,
  navigation, routes, colors, spacing, or
  backend change. Task record:
  `tasks/completed/phase-10-8a-1-typography-readability-correction.md`
  (filed complete per task instruction);
  implementation record:
  `docs/phases/phase-10-8a-1-typography-readability-correction.md`.
- Verification: focused 13 files green;
  full suite 60 files / 388 tests, 0
  failures (baseline 60/383; none
  weakened); `npx tsc --noEmit` clean;
  `npm run build` succeeds. No packages
  installed. No commit or push performed.
- Next: Phase 10.8I — Settings /
  Notifications / Responsive (not yet
  started).

## Phase 10.8H — Public Landing Page (Complete, 2026-09-28)

- Frontend public-route work under
  `REQUIREMENTS.md` R-10.8 and ADR-0012 (no
  auth/backend/domain/API change, no
  unsupported claims): rewritten
  `LandingPage` with dedicated chrome
  (identical signed in or out — the old
  `AppShell` leaked workspace nav when a
  record existed), R-10.8.12 hero/steps/
  CTAs, value/trust/audience sections,
  captioned static preview from real
  primitives, quiet CTA, minimal footer,
  token-only `landing.css`. Copy notes:
  four steps over the brief's three
  (canonical R-10.8.12 wins); "Start a
  Shipment"/"Sign In" labels likewise.
  Task record:
  `tasks/active/phase-10-8h-public-landing-page.md`;
  implementation record:
  `docs/phases/phase-10-8h-public-landing-page.md`;
  prior 10.8G task moved to `tasks/completed/`.
- Verification: focused 12/12 passing; full
  suite 60 files / 383 tests, 0 failures
  (baseline 59/376; none weakened);
  `npx tsc --noEmit` clean; `npm run build`
  succeeds; footprint confirmed as
  `main.tsx` + `features/landing/` only. No
  packages installed. No commit or push
  performed.
- Next: Phase 10.8I — Settings /
  Notifications / Responsive (not yet
  started).

## Phase 10.8G — View Shipments + Historical Report (Complete, 2026-09-28)

- Frontend-only archive/history under
  `REQUIREMENTS.md` R-10.8 and ADR-0012 (no
  backend/domain/API change, no mutations,
  scores, or PDF invention):
  `shipmentsArchive.ts` (local search/
  honest filters/stable order),
  rewritten `ShipmentsPage` (table + mobile
  cards, contextual opens, device-only
  forget), token-only `shipments.css`,
  `HistoricalReportPage` at
  `/shipments/:caseId/report` (profile,
  final result, requirements, evidence,
  safe-string sources, round-count
  completion; active/unknown refs get
  honest notices), terminal report links
  retargeted from dashboard + workspace.
  No timestamps/activity exist — omitted;
  no PDF boundary — control omitted and
  pinned absent. Task record:
  `tasks/active/phase-10-8g-view-shipments-historical-report.md`;
  implementation record:
  `docs/phases/phase-10-8g-view-shipments-historical-report.md`;
  prior 10.8F task moved to `tasks/completed/`.
- Verification: focused 29/29 passing; full
  suite 59 files / 376 tests, 0 failures
  (baseline 56/351; none weakened);
  `npx tsc --noEmit` clean; `npm run build`
  succeeds; footprint confirmed as
  `App.tsx`, `main.tsx`,
  `features/shipment/`,
  `features/dashboard/`,
  `features/workspace/` only. No packages
  installed. No commit or push performed.
- Next: Phase 10.8H — Public Landing Page
  (not yet started).

## Phase 10.8F — Document Verification (Complete, 2026-09-28)

- Frontend-only verification under
  `REQUIREMENTS.md` R-10.8 and ADR-0012 (no
  backend/domain/API change, no invented
  capabilities): `features/verification/`
  (verdict mapping over recorded findings),
  rewritten `DocumentDrawer` (real upload
  with backend constraints, per-document
  Verify via `supply-evidence` + finding
  lookup, missing/explanation rendering,
  on-demand preview and authorized open,
  human errors, terminal read-only),
  `requirementId` threading. No verify/
  extract/OCR endpoint exists — analysis
  runs stay explicit on their route; sync =
  `setRecord` on the supply response.
  Task record:
  `tasks/active/phase-10-8f-document-verification.md`;
  implementation record:
  `docs/phases/phase-10-8f-document-verification.md`;
  prior 10.8E task moved to `tasks/completed/`.
- Verification: focused suites passing; full
  suite 56 files / 349 of 351 in parallel
  (known pre-existing flake in unrelated
  evidence tests — 6/6 serially, none
  weakened); `npx tsc --noEmit` clean;
  `npm run build` succeeds; footprint
  confirmed as `features/verification/` +
  `features/workspace/` only. No packages
  installed. No commit or push performed.
- Next: Phase 10.8G — View Shipments +
  Historical Report (not yet started).

## Phase 10.8E — Shipment Workspace (Complete, 2026-09-28)

- Frontend-only workbench under `REQUIREMENTS.md`
  R-10.8 and ADR-0012 (no backend/domain/API
  change, no verification/archive/report/
  settings/scores): `features/workspace/`
  (`workspace.ts` mapping over record +
  profile + case-matched report,
  `ShipmentWorkspacePage` at
  `/shipments/:caseId`, `DocumentDrawer`
  10.8F seam, token-only `workspace.css`),
  dashboard entry opens retargeted to the new
  route, additive `RequirementCard` children.
  Findings render only when case-matched;
  sources/activity/timestamps omitted (no
  safe source); completed records read-only.
  Task record:
  `tasks/active/phase-10-8e-shipment-workspace.md`;
  implementation record:
  `docs/phases/phase-10-8e-shipment-workspace.md`;
  prior 10.8D task moved to `tasks/completed/`.
- Verification: focused 16/16 passing; full
  suite 54 files / 334 tests, 0 failures
  (baseline 52/318; none weakened);
  `npx tsc --noEmit` clean; `npm run build`
  succeeds; footprint confirmed as `App.tsx`,
  `main.tsx`, `features/workspace/`,
  `features/dashboard/`,
  `primitives/shipment.tsx` only. No packages
  installed. No commit or push performed.
- Next: Phase 10.8F — Document Verification
  (not yet started).

## Phase 10.8D — New Shipment (Complete, 2026-09-28)

- Frontend-only intake under `REQUIREMENTS.md`
  R-10.8 and ADR-0012 (no backend/domain/API
  change, no workspace/verification/archive/
  dashboard work): rewritten `NewShipmentPage`
  (product + country first, details second, no
  port; device-honest datalists; explicit
  unknown for optional fields; field-level
  validation + focus; BackButton + crumbs;
  unchanged `startWorkflow` + registry +
  `/workspace` completion), additive token-only
  `xb-form` family in `primitives.css`.
  Catalog/country-list/port/questionnaire
  omitted (none exist); draft autosave absent
  by guardrail (no backing boundary — only
  submitted shipments persist, resumable from
  dashboard). Task record:
  `tasks/active/phase-10-8d-new-shipment.md`;
  implementation record:
  `docs/phases/phase-10-8d-new-shipment.md`;
  prior 10.8C task moved to `tasks/completed/`.
- Verification: focused 16/16 passing; full
  suite 52 files / 318 tests, 0 failures
  (baseline 52/313; none weakened);
  `npx tsc --noEmit` clean; `npm run build`
  succeeds; footprint confirmed as
  `NewShipmentPage.*` + `primitives.css` /
  `primitives.test.ts` only. No packages
  installed. No commit or push performed.
- Next: Phase 10.8E — Shipment Workspace (not
  yet started).

## Phase 10.8C — Dashboard: Your Shipments (Complete, 2026-09-28)

- Frontend-only resumption workspace under
  `REQUIREMENTS.md` R-10.8 and ADR-0012 (no
  backend/domain/API change, no New Shipment
  form, workspace, verification, archive, or
  analytics): `features/dashboard/dashboard.ts`
  (pure mapping over `lib/shipments` +
  `lib/workflow` — greeting, plain-English
  status/attention/action per state, 3-item
  recent partition, defensive load, existing
  open mechanism), rewritten `DashboardPage`
  (counts, attention above recent, actionable
  cards, honest empty/loading/error), additive
  `ShipmentCard.onSelect`. Unavailable facts
  (timestamps, detail counts, scores) omitted,
  never fabricated. Task record:
  `tasks/active/phase-10-8c-dashboard.md`;
  implementation record:
  `docs/phases/phase-10-8c-dashboard.md`;
  prior 10.8B task moved to `tasks/completed/`.
- Verification: focused 26/26 passing; full
  suite 52 files / 313 tests passing (51/307
  parallel + 6 serially for a pre-existing
  parallel-timing flake in unrelated
  `AdditionalEvidencePage` tests — none
  weakened); `npx tsc --noEmit` clean;
  `npm run build` succeeds; footprint
  confirmed as `primitives/shipment.*` +
  `features/dashboard/` only. No packages
  installed. No commit or push performed.
- Next: Phase 10.8D — New Shipment (not yet
  started).

## Conversational Product Architecture (Design only, 2026-09-25)

- Canonical design doc:
  `docs/phases/conversational-product-architecture.md` (product value,
  product model, two conversational modes, model MAY/MUST-NOT,
  chat→system action boundary, grounding, tenant/shipment context,
  UX recommendation, MVP vs later, diagram, future phase impact,
  OQ-C1–OQ-C5). No code written, no behavior exists.
- Constraining decision:
  `docs/decisions/ADR-0009-conversational-boundary.md`.
- Task record:
  `tasks/completed/conversational-product-architecture.md`.
- No implementation task is active; no Phase 10.2 started. Future
  chat work needs `REQUIREMENTS.md` entries and scheduled tasks.

## Phase 9 — Frontend Redesign Pass C (Complete, 2026-09-25)

- Verification pass with minimal corrections:
  responsive static audit (no browser engine available,
  honestly reported), journey trace, 9-state audit,
  contradiction semantics resolved against backend
  source (rollup ≡ finding-level metric; filter honors
  either + wording clarified), empty/loading/error and
  accessibility audits, artifact consistency audit.
  Fixes: Requirements terminal gate, filter-group note,
  chip touch target, one new test.
- Verification: `npx tsc --noEmit` clean; `npx vitest run`
  27 files / 140 tests passing (139 carried, 1 new);
  `npm run build` succeeds. Backend untouched. See
  `docs/phases/phase-9-frontend-redesign-pass-c.md`.

## Phase 9 — Frontend Redesign Pass B (Complete, 2026-09-25)

- Detail-screen recomposition: requirements ledger
  (joined breakdown + findings), three-area evidence
  workspace, information-needed gap blocks, analysis
  intro, findings group filters + evidence-linked
  records, additional-evidence context strip,
  final-review checkpoint. Package/Report/History and
  backend untouched; no invented data or scores.
- Verification: `npx tsc --noEmit` clean; `npx vitest run`
  27 files / 139 tests passing (135 carried, 4 new);
  `npm run build` succeeds; dev source-mode serves 200 on
  all 13 routes with Pass B markers verified. Backend
  untouched; no live integration claimed. See
  `docs/phases/phase-9-frontend-redesign-pass-b.md`.

## Phase 9 — Frontend Redesign Pass A (Complete, 2026-09-25)

- Composition redesign of shell + workspace only:
  application vs current-shipment navigation, `/workspace`
  shipment overview (identity, five-area status strip,
  attention/next-action, area index, technical details),
  six-step diagram removed from the shell, operational
  flat-hierarchy CSS. Detail screens, API layer, and
  backend untouched; no invented attributes or scores.
- Verification: `npx tsc --noEmit` clean; `npx vitest run`
  27 files / 135 tests passing (125 carried, 10 new);
  `npm run build` succeeds; dev source-mode serves 200 on
  all checked routes with new-system markers verified.
  Backend untouched; no live integration claimed. See
  `docs/phases/phase-9-frontend-redesign-pass-a.md`.

## Phase 9.5 — Product UI Refinement (Complete, 2026-09-25)

- Visual/UX-only recomposition of the Phase 9 frontend:
  stacked brand shell, grouped Workspace/Assessment nav
  with latest-report link, editorial journey spine with
  stage descriptions, shipment hero, establishment
  checklist, ledger tables, supplied-first evidence
  layout, numbered report-style findings, artifact
  running heads, wider measure, responsive collapse.
  No contract, semantic, or behavior change.
- Verification: `npx tsc --noEmit` clean; `npx vitest run`
  26 files / 125 tests passing (119 carried, 6 new);
  `npm run build` succeeds; dev source-mode serves 200 on
  all 12 workspace routes with new-system markers
  verified in served modules. Backend untouched. See
  `docs/phases/phase-9-5-frontend-product-refinement.md`.

## Phase 9 — Frontend Pass 3 (Complete, 2026-09-25)

- Terminal workflow, frontend only, on the Pass 2.5
  visual baseline: additional-evidence loop (request →
  reference intake → supply → explicit re-run, no
  uploads, no auto-analysis), final review (read-only,
  no verdicts/scores), two-step `POST
  /compliance/workflows/finalize` with permanent-closure
  copy and 409 blocker rendering, `FinalPackageResponse`
  package artifact, `GET /compliance/reports/{report_id}`
  report view, and grouped history projection (no
  invented timestamps). Journey nav extended with an
  assessment tail (Final review · Assessment package ·
  History); UUID/URI wrapping fixed; `useAuth` no longer
  throws when unconfigured (was crashing the shell for
  signed-out users).
- Verification: `npx tsc --noEmit` clean; `npx vitest run`
  26 files / 119 tests passing (82 carried, 37 new);
  `npm run build` succeeds; dev serves 200 on all
  Pass 3 routes. Backend untouched; no live backend
  integration performed. See
  `docs/phases/phase-9-frontend-pass-3.md`.

## Phase 9 — Frontend Pass 2.5 (Complete, 2026-09-24)

- Visual/product refinement only across the Pass 1–2
  tree: teal-on-warm-neutral system, editorial type
  scale, brand/session/nav polish, shipment hero
  identity, numbered stepper with terminal state,
  restructured New Shipment hierarchy, case-record
  findings, consistent controls, responsive tightening.
  No new capabilities, no backend changes.
- Verification: `npx tsc --noEmit` clean; `npx vitest run`
  19 files / 82 tests passing (73 carried, 9 new);
  `npm run build` succeeds; dev + preview serve 200.
- Next: Pass 3 (Additional Evidence, Finalize, Package,
  Report, History). See
  `docs/phases/phase-9-frontend-pass-2-5.md`.

## Phase 9 — Frontend Pass 2 (Complete, 2026-09-24)

- `frontend/` routes `/workspace/{evidence,gaps,analysis,review}`:
  reference-based evidence intake (no uploader — none
  exists server-side), supplied-evidence tracking,
  case-readiness gaps rendered verbatim, analysis
  run/re-run with single-flight guard, and the Findings
  Review centerpiece (requirement, applicability,
  assessment, explanation, evidence, sufficiency,
  missing information, sources, uncertainty;
  contradictions preserved). Reports in memory only;
  identifiers + process state in sessionStorage.
- Verification: `npx tsc --noEmit` clean; `npx vitest run`
  18 files / 73 tests passing (35 carried, 38 new);
  `npm run build` succeeds. Backend untouched.
- Next: Pass 3 (Additional Evidence, Finalize, Package,
  Report, History). See
  `docs/phases/phase-9-frontend-pass-2.md`.

## Phase 9 — Frontend Pass 1 (Complete, 2026-09-24)

- `frontend/` — Vite + React + TypeScript SPA foundation
  (strict, 0 errors), app shell, centralized typed API
  client, auth/context plumbing, shipment workspace, New
  Shipment, Shipment Information, Requirements. Presentation
  only: no compliance logic, no verdicts, backend statuses
  rendered verbatim. Backend untouched.
- Verification: `npx tsc --noEmit` clean; `npx vitest run`
  7 files / 35 tests passing; `npm run build` succeeds.
- Next: Pass 2 (Evidence, Gaps, Analysis, Findings Review),
  then Pass 3 (Additional Evidence, Finalize, Package,
  Report, History). See
  `docs/phases/phase-9-frontend-pass-1.md`.

## UI / Product Architecture (Spec, 2026-09-24)

- `docs/phases/ui-product-architecture.md` (specification
  only — no frontend code, no backend changes): 10-screen
  exporter journey contract verified endpoint-by-endpoint
  against the production API, with role model, state
  vocabularies, evidence/analysis/finalization UX rules,
  full API matrix, auth assumptions, responsive IA, and
  six documented backend gaps (no file upload; no
  workflow listing/resume; no standalone readiness read;
  no role introspection; no notifications/dashboards;
  no reopen/versioning).
- Frontend implementation may proceed strictly within
  that contract; no backend change is required to start.

## Phase 8.5 — Stored-Path HTTP Exposure (Complete, 2026-09-24)

- `POST /compliance/workflows/finalize` (201),
  `POST /compliance/workflows/package` (200),
  `GET /compliance/reports/{report_id}` (200): thin
  routes over the 8.4 stored use cases, one use case
  each. Finalize resolves the server-known latest
  (review-gated, stale/terminal enforced); reads are
  tenant-scoped by membership identity.
- Additive only: store container field + real wiring +
  passthrough + 503 dependency (`dependencies.py`);
  `FinalPackageResponse` / `FinalizeWorkflowResponse`
  (`schemas.py`); analyze passes the optional store
  (unwired behavior unchanged). Existing error/status
  mapping reused; no compound endpoint; history
  endpoint unchanged (round→report references already
  present).
- Verification: focused 25/25; Phase 8.1–8.4 + 7.1–7.5
  + Phase 6 + Phase 2–5 regressions pass; full suite
  1740 passed + 44 skipped (gated), 0 failures. No
  Phase 1–7 behavior change; no prior test touched.
  No UI or evaluation built.

## Phase 8.4 — Normalized Phase 6 Result Store (Complete, 2026-09-24)

- Migration `010` (reversible, schema-only): 5 tables —
  `compliance_analysis_reports` (counts carried, summary
  as carried JSONB reference), `compliance_analyses`
  (scalar/state columns; fixed-schema typed reference
  lists as JSONB per `evidence_ids` precedent),
  `compliance_analysis_traces` (+ fingerprints/steps),
  `compliance_workflow_rounds` (composite PK
  tenant/workflow/round_index; linkage anchor, not a
  second history), `final_assessment_packages`
  (linkage only; UNIQUE per workflow makes second
  finalization structural). Tenant FKs, composite
  tenant-safe FKs (CASCADE for composition, RESTRICT
  for links), CHECKs, indexes, triggers.
- `ComplianceResultStore` (`application/result_store.py`):
  atomic single-transaction writes, idempotent retry by
  content-derived keys (first-writer-wins round slots),
  exact reconstruction with tenant/case/report/analysis
  linkage validation, fail-closed corruption handling.
- App integration: persist-on-analysis (optional store),
  stored finalize/package/report/current-result use
  cases. No new endpoints in 8.4 (8.5 decides exposure).
- Verification: 24 store unit + 12 migration structural
  focused tests; 7 DB-gated live tests skip without
  `DATABASE_URL` (apply/rollback/repo coverage written
  and gated, not claimed). Phase 8.1–8.3 + 7.1–7.5 +
  Phase 6 + Phase 2–5 regressions pass; full suite 1715
  passed + 44 skipped, 0 failures. One 8.1
  collaborator-set assertion extended (same strictness;
  documented). No Phase 1–7 behavior change. No UI or
  evaluation built.

## Phase 8.3 — Workflow/Result Transfer-or-Store Contract (Complete, 2026-09-24)

- Lifecycle answer: workflow records transfer
  client-side today (server revalidates); deterministic
  inputs reconstruct from authoritative records; live
  Phase 6 results are in-session only — reconstruction
  unsafe (IDs derive from model text), client round-trip
  / globals / sessions / blobs / answer storage all
  prohibited, normalized Phase 6 tables disproportionate
  and DB-untestable here → result persistence specified
  but deferred; finalize/package/report endpoints remain
  blocked (reported, not worked around).
- Stale safety via round linkage; terminal closure and
  tenant isolation hold across transfers; concurrency
  safe through server statelessness (all updates are
  `replace()` on caller-held records).
- Actor threading: additive `get_request_actor`
  (Bearer subject, else `None`) threaded through all 13
  compliance routes into `ApplicationContext.actor_id`;
  tenant/role still server-derived; bodies cannot forge
  it; domain still takes only `TenantContext`; no audit
  logging added.
- Verification: focused 32/32; Phase 8.1 (31) +
  8.2 (29) + 7.1–7.5 (151) + Phase 6 (247) + Phase 2–5
  regressions pass; full suite 1679 passed + 37 skipped
  (gated), 0 failures. No domain/application-core/
  persistence behavior change; no prior test touched.
  No UI or evaluation built.

## Phase 8.2 — HTTP Endpoint Exposure (Complete, 2026-09-24)

- `xportra/api/compliance.py` (new, 13 thin endpoints):
  workflow progression/status/history/closure/analyze
  plus applicability and case-readiness reads; each
  handler does auth → authorize → ApplicationContext →
  one use case → DTO serialization. Per-request service
  construction; no container surgery; no session or
  process-global state.
- Additive only: 2 owner-only permissions
  (`authorization.py`), centralized type-based app-error
  → HTTP mapping reusing the existing error shape
  (`errors.py`: 401/403/400/404/409/422/503/500),
  compliance request/response models (`schemas.py`,
  incl. fingerprint-free round shape), router include
  (`app.py`).
- Application wire translation (mechanical, in-session
  behavior unchanged): UUID coercion for
  JSON-transported case views incl. provenance and
  summary scope (`_guards.py`, `analysis.py`,
  `assessments.py`).
- Result-dependent operations (finalize, package/report
  reads, result-attached history) deliberately unexposed:
  live Phase 6 results cannot cross HTTP and no
  transfer/store contract exists — reported gap, no
  fake persistence. Compound analyze-and-finalize
  rejected (would skip required human review).
  Recommended next: Phase 8.3 result/workflow
  transfer-or-store contract (+ subject threading).
- Verification: focused 29/29; Phase 8.1 (31) +
  7.1–7.5 (151) + Phase 6 (247) + Phase 2–5 regressions
  pass; full suite 1647 passed + 37 skipped (gated),
  0 failures. No Phase 1–7 behavior change; no prior
  test touched. No UI or evaluation built.

## Phase 8.1 — Application Boundary & Use-Case Contract (Complete, 2026-09-24)

- `xportra/application/` (new package, 33 exports):
  `ApplicationContext` (actor, effective tenant, role —
  API-built from server-resolved membership, never from
  client IDs); HTTP-free error taxonomy (auth
  passthrough, tenant mismatch, transition,
  not-ready/stale, terminal, not-found, validation,
  infrastructure); 16 frozen allow-listed DTOs
  (workflow, shipment, evidence, rounds, findings,
  report, readiness, history, package, applicability,
  case readiness — fingerprints, prompts, model
  internals, and secrets excluded; Phase 6 provenance
  selected not remodeled; Phase 3.5 summary carried by
  reference in the package DTO only).
- Use cases (stateless, record-in/record-out, live
  results in-session, no new persistence):
  `WorkflowApplicationService` (7.x journey incl.
  finalize/history/closure), `AnalysisApplicationService`
  (run/re-run with injected RAG), `AssessmentApplicationService`
  (applicability + evidence-coverage reads),
  `EvidenceApplicationService` (recording over the
  injected existing service). Tenant pre-checks,
  terminal pre-checks, and structured readiness are
  deterministic, never message-parsed.
- Verification: focused 31/31; Phase 7.1–7.5 (151) +
  Phase 6 (247) + Phase 2–5 regressions pass; full
  suite 1618 passed + 37 skipped (gated), 0 failures.
  No domain/API/persistence/infrastructure file touched;
  no prior test touched. No endpoints, UI, persistence,
  or evaluation built.

## Phase 7.5 — Workflow Closure/Reopening Policy (Complete, 2026-09-24)

- Decision: `assessment_package_ready` is permanently
  closed — no reopen transition, no second finalization,
  no package versioning. Iteration belongs
  pre-finalization (7.1 loop); continuation is a fresh
  progression, never mutation. Finding-neutral; no
  verdict/score introduced.
- Contract: `WORKFLOW_TERMINAL_STATES` constant plus
  tenant-validated `ComplianceWorkflowService.is_closed`
  predicate (one additive export). Zero behavior change:
  terminal already had no outgoing edges and every
  mutating op (7.1 transitions, re-analysis with
  zero-call, second finalize, 7.2 supply/switch handoff)
  already failed closed — now explicitly locked.
- Prior packages stay valid; 7.4 history model unchanged.
- Verification: focused 19/19; Phase 7.1 (32) + 7.2 (32)
  + 7.3 (33) + 7.4 (35) + Phase 6 (247) + Phase 2–5
  regressions pass; full suite 1587 passed + 37 skipped
  (gated), 0 failures. No prior test touched.
- With 7.5 the workflow contract is closed:
  **Phase 7 COMPLETE** — Phase 8 may proceed.

## Phase 7.4 — Workflow History & Audit View (Complete, 2026-09-24)

- `xportra/domain/workflow_history.py` (new):
  `WorkflowHistoryService.project` (pure, stateless) plus
  frozen `WorkflowHistoryView` / `WorkflowHistoryEntry` /
  `FinalPackageReference`, five entry kinds
  (`workflow_created`, `shipment_bound`,
  `evidence_supplied`, `analysis_completed`,
  `final_package_ready`), and fail-closed
  `WorkflowHistoryError`. Derives only from retained
  workflow state: creation identity, shipment
  association, supplies in append order, rounds in round
  order, current state/requirements, plus re-validated
  optional result/package shown by reference (readiness
  computed on demand via Phase 7.3, never stored).
  Grouped presentation order; cross-group interleaving
  and timestamps explicitly not claimed (none exist).
  Reasoning content never copied; output is identifiers
  only. Eleven additive `xportra/domain` exports.
- Verification: focused 35/35; Phase 7.1 (32) + 7.2 (32)
  + 7.3 (33) + Phase 6 (247) + Phase 2–5 regressions
  pass; full suite 1568 passed + 37 skipped (gated),
  0 failures. No Phase 1–7.3 behavior file modified; no
  prior test touched. No API, UI, events, persistence,
  or evaluation built. No open prerequisite blocks
  Phase 7.5.

## Phase 7.3 — Workflow-to-Assessment Readiness & Final Packaging Trigger (Complete, 2026-09-24)

- `xportra/domain/assessment_readiness.py` (new):
  `AssessmentReadinessService.check` (pure, deterministic)
  plus frozen `AssessmentReadiness` / `ReadinessIssue` and
  seven issue codes (`tenant/case_mismatch`,
  `invalid_workflow_state`, `missing_shipment_reference`,
  `no_analysis`, `analysis_stale`,
  `analysis_integrity_failure`). Gates what `finalize()`
  left implicit: bound shipment, latest-round freshness,
  and analysis/report/trace linkage (ids, fingerprints,
  trace report/analysis references, tenant scope). Absent
  decision summaries and unresolved findings (missing,
  unknown, not-satisfied, contradiction, uncertainty)
  never block — readiness is process completion, not
  regulatory truth. Trace `case_id` intentionally
  uncompared (Phase 6.5 scopes traces to
  requirement-level case views).
- `compliance_workflow.py` (minimal): `finalize()`
  validates via the gate (structured
  `ComplianceWorkflowError`, no package, state untouched
  when not ready); package construction unchanged;
  optional `readiness_service` seam. Ten additive
  `xportra/domain` exports.
- Verification: focused 33/33; Phase 7.1 (32) + 7.2 (32)
  + Phase 6 (247) + Phase 2–5 regressions pass; full
  suite 1533 passed + 37 skipped (gated), 0 failures.
  No prior test touched. No API, UI, verdict, score,
  persistence, or evaluation built. No open prerequisite
  blocks Phase 7.4.

## Phase 7.2 — Shipment & Evidence Intake Formalization (Complete, 2026-09-24)

- `xportra/domain/shipment_intake.py` (new):
  `ShipmentIntakeService` plus frozen `ShipmentReference`
  (tenant + shipment + case, identity only — no shipment
  table/object exists to reuse) and
  `SuppliedEvidenceReference` (existing evidence identity +
  scope, never bytes). Once-early shipment binding
  (identical rebind idempotent; switches, late binding, and
  tenant/case mismatches fail closed); supply handoff
  re-checks tenant/case and delegates transitions to the
  unchanged 7.1 service. Recording and requirement linking
  stay authoritative outside (`ComplianceEvidenceService`);
  upload/record vs supply separated; no second
  persistence/assessment system. Four additive
  `xportra/domain` exports.
- Verification: focused 32/32; Phase 7.1 (32) + Phase 6
  (247) + Phase 2–5 regressions pass; full suite 1500
  passed + 37 skipped (gated), 0 failures.
  `compliance_workflow.py` untouched; no prior test
  touched. No API, UI, persistence, verdict, or evaluation
  built. No open prerequisite blocks Phase 7.3.

## Phase 7.1 — Compliance User Workflow Contract (Complete, 2026-09-24)

- `xportra/domain/compliance_workflow.py` (new):
  `ComplianceWorkflowService` — pure nine-state process
  machine (`created` → … → `assessment_package_ready`,
  terminal) over existing Phase 1–6 contracts. Coordinates
  without reimplementing: no applicability/assessment/risk/
  action/reasoning/retrieval/LLM/provenance logic of its own.
  Explicit evidence loop (`request_additional_evidence` →
  `supply_evidence` → `run_analysis`) with non-mutating,
  ID-distinguishable rounds; `run_analysis` delegates to
  `ComplianceReasoningApplication` after state/tenant
  validation; `finalize` aggregates the latest Phase 6
  result plus the untouched decision summary into a
  verdict-free `AssessmentPackage`. Fail-closed tenant/case
  isolation and deterministic-first failure behavior.
  Fifteen additive `xportra/domain` exports.
- Verification: focused 32/32; Phase 6 (247) + Phase 2–5
  regressions pass; full suite 1468 passed + 37 skipped
  (gated), 0 failures. No prior test touched. No Phase 1–6
  behavior modified. No API, UI, persistence, verdict, or
  evaluation built. No open prerequisite blocks Phase 7.2.

## Phase 6.6 — End-to-End Compliance Reasoning Composition (Complete, 2026-09-24)

- `xportra/domain/reasoning_application.py` (new):
  `ComplianceReasoningApplication` — pure orchestration over
  the five existing Phase 6 services plus the RAG boundary
  (deterministic-first validation with zero provider calls
  on defect, requirement-ID-ordered processing, fail-closed
  partial semantics: failures propagate, never convert to
  compliance states, no partial result) and verdict-free
  `ComplianceReasoningResult` (ordered analyses + report +
  per-analysis traces + referenced decision summary; fixed
  serialization keys). Determines nothing; parses no prose;
  constructs no provenance. Three additive `xportra/domain`
  exports.
- Additive 6.3 accessor `analyze_with_reasoning_and_answer`
  (existing method delegates, behavior identical) so traces
  reuse the validated answer without duplicating the
  single-call orchestration.
- Verification: focused 49/49; Phase 6.1–6.5 (198) + Phase
  2–5 regressions pass; full suite 1436 passed + 37 skipped
  (gated), 0 failures. No prior test touched. No API,
  workflow, UI, verdict, or evaluation built.
- **Phase 6 — Compliance Reasoning & Decision Support is
  COMPLETE**: composition exists; deterministic truth
  authoritative; retrieval grounded; reasoning bounded and
  validated; uncertainty/conflicts/missing explicit;
  case-level composition and decision trace exist; failure
  semantics safe; isolation preserved; serializable result
  ready for Phase 7/8; no unresolved prerequisite remains.

## Phase 6.5 — Compliance Reasoning Decision Trace (Complete, 2026-09-24)

- `xportra/domain/decision_trace.py` (new): canonical six-step
  vocabulary (`deterministic_state_established` →
  `analysis_constructed`), frozen `TraceStep` / `DecisionTrace`
  reusing the existing typed evidence/knowledge/source
  references (contents never copied), and pure
  `DecisionTraceService.trace` — records which authoritative
  inputs and evidence contributed to an analysis, never
  decides. Fail-closed tenant/case/evidence/source/citation
  checks; answer fingerprint recomputed and canonical input
  fingerprint on the reused `content_fingerprint` scheme
  (exact-input change detection, not correctness proof); no
  chain-of-thought, prompts, provider internals, secrets,
  timestamps, or raw unvalidated output. No infra imports
  (AST-verified). Twelve additive `xportra/domain` exports.
- Integration boundary `Analysis → Trace`: no Phase 6.1–6.4
  behavior modified, no Phase 5 change, no LLM call, report
  interop verified, serializable with an exact fixed key set.
- Verification: focused 36/36; Phase 6.1 (35) + 6.2 (39) +
  6.3 (37) + 6.4 (51) + Phase 2–5 regressions pass; full
  suite 1387 passed + 37 skipped (gated), 0 failures. No
  prior test touched. No verdict/risk/action engine, API,
  workflow, UI, or evaluation framework built. Phase 6
  remains open.

## Phase 6.4 — Evidence Sufficiency, Contradiction & Uncertainty Reasoning (Complete, 2026-09-24)

- `xportra/domain/evidence_sufficiency.py` (new):
  sufficiency (`supported`/`insufficient`/`missing`/`unknown`)
  + contradiction (`none`/`present`) + missing-kind vocabularies,
  frozen `MissingInformationItem` /
  `EvidenceSufficiencyAssessment`, pure
  `EvidenceSufficiencyService` derivation mirroring the existing
  `RequirementAssessmentService` semantics (no new algorithm), and
  a narrow numeric-confidence guard for model-sourced text only.
  No infra imports (AST-verified); no retrieval/LLM/DB calls.
- Minimal 6.1 adaptation: `ComplianceAnalysis` gains four
  defaulted fields (`evidence_sufficiency`,
  `contradiction_state`, `sufficiency_explanation`,
  `missing_items`); `analyze()` derives them by fixed rules from
  the trusted state and rejects numeric confidence claims in
  model text as `ComplianceReasoningError`. All 6.1–6.3 tests
  pass unmodified; `compliance_report.py` and
  `reasoning_generation.py` untouched.
- Trust boundary enforced: conflicts preserved with provenance
  (described, never resolved, no precedence invented);
  categorical uncertainty unchanged (guard only); missing items
  typed and grounded (no invented documents); hostile evidence
  stays data. Twenty-one additive `xportra/domain` exports.
- Verification: focused 51/51; Phase 6.1 (35) + 6.2 (39) +
  6.3 (37) + Phase 2–5 regressions pass; full suite 1351 passed
  + 37 skipped (gated), 0 failures. No prior test touched. No
  verdict engine, ranking algorithm, risk score, API, workflow,
  or UI built. Phase 6 remains open.

## Phase 6.3 — Structured Compliance Reasoning Generation Boundary (Complete, 2026-09-24)

- `xportra/domain/reasoning_generation.py` (new):
  `ReasoningGenerationError`, `ReasoningPromptContext` (+
  case extractor), `ReasoningQuery`/`ReasoningQueryBuilder`
  (deterministic FACTS + untrusted-DATA notice + explain-only
  TASK + exact FORMAT), `ReasoningValidationContext` (+
  case/answer allow-list builder),
  `StructuredReasoning` (explanation, suggested missing,
  categorical uncertainty + statement, answer-fingerprint
  binding), `StructuredReasoningParser` (strict section
  protocol with legacy plain-text compatibility; rejects
  unknown citations, invented UUIDs, non-categorical
  confidence, stray/verdict headers, malformed sections),
  `StructuredReasoningService` (single-call orchestration via
  injected RAG service). Fifteen additive domain exports.
- Minimal 6.1 adaptation: `ComplianceAnalysis` gains
  `uncertainty_explanation: str = ""`;
  `analyze(..., reasoning=None)` defaults to exact 6.1
  behavior, otherwise binds fingerprints, prefixes model
  items as observations, and carries the uncertainty
  statement. All 6.1/6.2 tests pass unmodified.
- Trust boundary enforced: deterministic state trusted;
  model text untrusted until validated; validated content
  usable only in permitted fields. Single RAG call; full
  Phase 5 boundary reuse; no parallel system.
- Verification: focused 37/37; Phase 6.1 + 6.2 + Phase 2–5
  regressions pass; full suite 1300 passed + 37 skipped
  (gated), 0 failures. No prior test touched. API,
  workflow, UI, verdict engines explicitly deferred. Phase 6
  remains open.

## Phase 6.2 — Compliance Analysis Report Composition (Complete, 2026-09-24)

- `xportra/domain/compliance_report.py` (new):
  `ComplianceReportError`, frozen
  `RequirementMissingInformation` /
  `ComplianceAnalysisReport` (ordered analyses, exact aggregate
  counts, association-preserving missing/uncertainty/conflict
  rollups, referenced decision summary, deterministic identity,
  `to_record()`, `is_empty`), and stateless
  `ComplianceReportService.compose`. Four additive
  `xportra/domain` exports.
- Composition only: no overall verdict field exists (a new
  verdict algorithm is structurally unrepresentable); the
  Phase 3.5 decision summary is carried by reference and its
  content never alters aggregates; counts derive from analysis
  outcomes alone (never prose); ordering by stringified
  requirement ID; duplicates/cross-tenant/malformed fail
  closed; empty input yields a valid verdict-free report.
- Verification: focused 39/39; Phase 6.1 + Phase 2–5
  regression 592/592; full suite 1263 passed + 37 skipped
  (gated), 0 failures. No prior test touched; no Phase 1–6.1
  behavior modified. API, workflow, UI, verdict engines, and
  calibration explicitly deferred. Phase 6 remains open.

## Phase 6.1 — Deterministic Compliance Reasoning Contract (Complete, 2026-09-24)

- `xportra/domain/compliance_reasoning.py` (new):
  `ComplianceReasoningError`, frozen `EvidenceReference` /
  `KnowledgeReference` / `SourceReference` /
  `ComplianceAnalysis` (requirement, applicability, assessment,
  verbatim explanation, supporting/conflicting evidence,
  knowledge refs, sources, missing information, categorical
  uncertainty, deterministic identity, `to_record()`), and
  stateless `ComplianceReasoningService` (`analyze` pure +
  `analyze_with_knowledge` thin RAG delegation). Twelve
  additive `xportra/domain` exports.
- Deterministic truth authoritative: state copied from the
  Phase 2.7 case view, contradictions fail closed, `unknown`
  never converted, model verdict text changes nothing,
  citations only from the validated mapping,
  `invalid_citations` rejected, tenant execution-level.
- LLM boundary fully reused (injected `RAGApplicationService`;
  no second client/prompt/citation/validation system).
- Verification: focused 35/35; Phase 2–5 regression 621/621;
  full suite 1224 passed + 37 skipped (gated), 0 failures.
  No prior test touched; no Phase 1–5 behavior modified.
  API, workflow, UI, verdict engines, and calibration
  explicitly deferred. Any next step
must first be defined in `REQUIREMENTS.md` and scheduled
through `tasks/` and `ACTIVE_TASK.md`. Phase 6 is not started.

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

## Phase 3.7 — Evidence Requirement / Retrieval Contract (Complete, 2026-09-22)

- `EvidenceRequirementPlanService.plan(readiness_report, *, tenant_id)`
  converts Phase 3.6 readiness gaps into an evidence requirement plan:
  Applicability → Risk → Action → Summary → Readiness → Evidence Plan.
- One requirement per gap, traceable via `requirement_id`, stable ID
  `<requirement_id>:<gap_kind>`; gap kinds preserved; unknowns kept
  distinct; no compliance asserted.
- Priority from existing `risk_state` else neutral `unknown`; existing
  action preserved as `triggering_action`; only `required` items emitted.
- Deterministic ordering; tenant UUID required; no rule reimplemented.
- No persistence, retrieval, RAG, LLM, embeddings, vectors, API, UI,
  crawling, connectors, agents, or verdicts introduced.
- Verification: focused 20/20, full suite 242/242, no regressions;
  additive-only change to `xportra/domain/ingestion.py`.
- PostgreSQL integration tests not run (`DATABASE_URL` unconfigured).

## Phase 3.8 — Evidence Retrieval Request (Complete, 2026-09-22)

- `EvidenceRetrievalRequestService.build(plan, *, tenant_id)` converts the
  Phase 3.7 plan into retrieval requests: Plan → Retrieval Request.
- One request per plan item; identity reuses `evidence_requirement_id`;
  query from existing requirement text only; no fact invention.
- Gaps/priority/status preserved exactly; fixed scope
  `requirement_evidence`; deterministic ordering; tenant UUID required.
- Malformed plan items fail closed via `ComplianceSummaryValidationError`
  (never silently skipped); no partial request set on corruption.
- No retrieval executed; no business rules reimplemented.
- Verification: focused 25/25, full suite 267/267, no regressions;
  additive-only change.
- PostgreSQL integration tests not run (`DATABASE_URL` unconfigured).

## Phase 3.9 — Evidence Retrieval Execution (Complete, 2026-09-22)

- Executor contract + result builder + NoOp implementation.
- Fail-closed request validation; traceable identity; empty-means-empty.
- Verification: focused 20/20, full suite 287/287, no regressions.
- No concrete retrieval backend implemented.
- PostgreSQL integration tests not run (`DATABASE_URL` unconfigured).

## Phase 4.0 — Evidence Corpus Foundation (Complete, 2026-09-22)

- `EvidenceDocument` + `EvidenceCorpusService` + `EvidenceDocumentRepository`
  + migration `009_evidence_documents` (+ down).
- Stable uuid5 identity; tenant+source+version dedup; provenance required.
- Verification: focused 26/26, full suite 313/313, no regressions.
## Phase 4.5 — Evidence Index Synchronization Boundary (Complete, 2026-09-22)

- `EvidenceIndexSyncService.sync(document, *, tenant_id)` orchestrates
  EvidenceChunkingService → EvidenceIndexingService → EvidenceVectorIndex;
  no chunking/embedding/vector logic of its own, no Qdrant import.
- Deterministic report (tenant, document id/version, chunk_count,
  indexed_count, indexed_chunk_ids, status "complete") returned only on
  full success; partial upsert failure raises VectorStoreError (no false
  success; no rollback — idempotent upsert, safe re-run).
- Tenant checked at document, chunk, and indexable-chunk stages; document
  version preserved; deterministic identities, no duplicate points on repeat.
- Verification: focused 30/30 (fakes, no live Qdrant), full suite 468/468
  (438 + 30), no regressions. Live Qdrant integration not run (no server
  configured). No retrieval/search/RAG/query API introduced.


- No search/retrieval/RAG/embeddings implemented.
- PostgreSQL integration tests not run (`DATABASE_URL` unconfigured).

## Phase 5.1 — Evidence Retrieval Boundary (Complete, 2026-09-22)

- `xportra/domain/evidence_retrieval.py`: `EvidenceRetrievalQuery`
  (text + configurable top-k; tenant never a field — required keyword of
  every call), `EvidenceRetrievalResult` (full Phase 4.4 payload +
  score, fail-closed `from_record`), `EvidenceRetriever` protocol, and
  `VectorIndexEvidenceRetriever` (embeds the query via the existing
  `EmbeddingProvider`/`EmbeddingModelConfig`, delegates to
  `EvidenceVectorIndex.find`; no Qdrant import).
- `EvidenceVectorIndex.find(query_vector, *, tenant_id, top_k)` added to
  the Phase 4.4 contract (no second vector-store abstraction);
  `QdrantEvidenceVectorIndex.find` applies a mandatory tenant metadata
  filter and translates `query_points` responses into domain results,
  with a per-result tenant re-check (cross-tenant → fail closed).
- Provenance/version preserved exactly (identity, content, fingerprint,
  source, document_version, embedding contract + score); errors reuse
  `DomainValidationError`/`VectorStoreError(operation, cause)`;
  empty query / invalid top-k → `DomainValidationError`; top-k larger
  than available, no matches, nonexistent tenant, missing collection →
  fewer/zero results, never an error.
- Verification: focused 56/56 (fakes, no live Qdrant), full suite 524/524
  (468 + 56), no regressions; Phase 4 tests unmodified. Live Qdrant
  integration not run (no server configured). No LLM, prompt, answer
  generation, compliance decision, query rewriting, reranking, hybrid
  search, agentic retrieval, memory, or UI/API endpoint introduced.
  Phase 5.2 has not started; Phase 5 is not complete.

## Phase 5.2 — Retrieval Quality & Query Semantics (Complete, 2026-09-22)

- Query semantics: information need → `EvidenceRetrievalConfig(
  top_k=DEFAULT_TOP_K).build_query()` / `EvidenceRetrievalQuery` →
  normalized text → `EmbeddingProvider` → query vector →
  `EvidenceVectorIndex.find` → ordered, deduplicated results. Tenant
  stays execution-level; config carries only `top_k`; embedding config
  remains the Phase 4.3 `EmbeddingModelConfig` (no second system, no
  competing default constant).
- Normalization: trim + collapse internal whitespace runs;
  empty/whitespace-only/non-string rejected; case, punctuation, and
  wording preserved — no semantic rewriting; the normalized text is
  what gets embedded.
- Ordering contract: descending relevance score, ties broken by
  ascending `chunk_id`; scores are never recomputed or reranked.
- Duplicate rule: after ordering, keep only the first result per
  (`document_id`, `content_fingerprint`); evidence from different
  documents/versions/sources never collapsed (even for identical
  text); near-duplicates deferred and documented (no heuristics);
  result count may fall below top-k after collapse.
- Fail closed: embedding/index/malformed/config failures raise
  (`DomainValidationError`/`VectorStoreError`) and are never converted
  into empty successful retrievals; `[]` means "no matching evidence".
- Verification: focused 40/40; Phase 5.1 focused re-run 56/56 (one
  fixture fingerprint corrected to honor the Phase 4 sha256(content)
  invariant — no assertion weakened); full suite 564/564 (524 + 40),
  no regressions. No LLM, prompt, answer generation, compliance
  conclusion, reranking, hybrid search, agentic retrieval, memory, or
  UI introduced. Phase 5.3 has not started; Phase 5 is not complete.

## Phase 5.3 — Evidence Scope & Metadata Filtering (Complete, 2026-09-22)

- `EvidenceRetrievalScope` (frozen value object): optional, explicit,
  conjunctive (AND) restrictions over the four canonical indexed
  dimensions — `source_id`, `source_type`, `document_id`,
  `document_version`; values validated fail-closed and trimmed.
  Unsupported/speculative dimensions (tenant, jurisdiction, dates,
  status, commodity, `filters` dicts) cannot be expressed; non-canonical
  keyword arguments are rejected.
- Tenant isolation is separate from and prior to scope: the scope has no
  tenant field, `require_tenant_context` still runs first, the adapter's
  provider filter always starts with the mandatory tenant condition, and
  empty/omitted scope means tenant-only retrieval — never all tenants.
- Provider translation: the Qdrant adapter converts canonical scope
  pairs into provider filter conditions (UUIDs encoded per the Phase 4.4
  payload); no Qdrant filter objects appear in domain models, services,
  or domain-semantics tests.
- Defense in depth preserved: every returned result is re-checked
  against the tenant and then against the requested scope; an
  out-of-scope or malformed-metadata result raises
  `VectorStoreError` (integrity failure) — never a silent drop and never
  an empty success. Filtering never strips provenance: results remain
  complete 13-field `EvidenceRetrievalResult` values.
- Compatibility: `scope` is an optional keyword (`None` ≡ empty scope)
  on `EvidenceRetriever.retrieve` and `EvidenceVectorIndex.find`; Phase
  5.1/5.2 call sites and semantics are unchanged (test doubles' `find`
  signatures were extended mechanically — no assertion weakened).
- Verification: focused 41/41; Phase 5.1 re-run 56/56; Phase 5.2 re-run
  40/40; full suite 605/605 (564 + 41), no regressions. Live Qdrant
  integration not run (no server configured). No LLM query rewriting,
  reranking, hybrid search, agentic retrieval, answer generation,
  compliance reasoning, legal interpretation, citation generation,
  conversational retrieval, or heuristic query classification
  introduced. Phase 5.4 has not started; Phase 5 is not complete.

## Phase 5.13 — RAG Application/API Boundary (Complete, 2026-09-23)

- `xportra/domain/rag_application.py` (rewritten from a stray
  untracked draft whose broken `xportra.domain.infrastructure`
  import prevented the entire domain package from importing):
  `RAGApplicationService`, `RAGApplicationContract`
  (runtime-checkable protocol), `build_rag_application_service` —
  pure orchestration composing Phase 5.8 context pipeline → Phase
  5.10 prompt builder → Phase 5.11 `LLMClient` + injected
  `LLMGenerationConfig` → `GeneratedAnswer` (structural
  fail-closed check only) → Phase 5.12 validator, returning the
  validator's exact `ValidatedAnswer`. No retrieval/ranking/
  selection/prompt/LLM/validation logic of its own; no
  infrastructure imports (AST-verified); tenant is a mandatory
  execution-level keyword; no broad exception handling. Three
  additive exports in `xportra/domain/__init__.py`.
- `POST /rag/query` (`xportra/api/router.py`, existing
  no-version-prefix convention) behind the existing auth boundary
  (`require_permission(READ_TENANT_RESOURCE)`; owner + member may
  query). Tenant comes exclusively from `MemberContext` — the body
  cannot supply or override it (`tenant_id` anywhere in the body →
  422); missing context fails closed with 401 before any service
  runs.
- Request (`RAGQueryRequest`, `extra="forbid"`): required
  `information_need` (1–4000 chars, API-layer guard); optional
  `mode` Literal allowlist defaulting to `"hybrid"` (API-layer
  default, domain still validates), `max_context_characters`
  (StrictInt, default 4000), `top_k` (StrictInt, default
  `DEFAULT_TOP_K`), `candidate_pool` (StrictInt|None), and `scope`
  limited to the four canonical `EvidenceRetrievalScope`
  dimensions. No provider settings, raw prompts, embedding config,
  vector filters, or Qdrant parameters exposed.
- DI: `ApplicationServices.rag` + `get_rag_service` (fails closed
  with 503 `rag_not_configured` when unwired — the default, since
  `from_environment` wires only Phase 1.x persistence; no live
  Qdrant/LLM constructed at startup). Generation config is
  server-side; credentials never enter domain values or responses.
- Response (`RAGQueryResponse`): verbatim `answer_text`, `status`
  (`valid`/`invalid_citations`/`empty`), `is_empty`,
  `extracted_references`, `invalid_references`, and citations with
  identifiers/source pointers only (no tenant, content, scores,
  embeddings, secrets, or SDK objects). Citations come solely from
  the validated mapping — never parsed from text.
- Errors: 422 `validation_error` (malformed body/unknown fields),
  409 `domain_validation_error` (whitespace need, bad scope, malformed
  LLM output, cross-tenant), 422 `citation_integrity_error`
  (distinguishable from provider failures), 502
  `vector_store_error`/`llm_provider_error` (never empty
  successes), 401/403 via the existing boundary, 503 when unwired,
  500 otherwise — all API-safe with no leaks.
- Empty answers preserved end to end (200, `status="empty"`,
  verbatim text; nothing fabricated, no retries). Model output
  stays inert JSON text.
- Verification: focused 42/42; Phase 5.1–5.13 focused 603/603;
  full suite 1071 passed + 32 skipped (`DATABASE_URL`
  unconfigured), 0 failures. No Phase 5.1–5.12 behavior file
  modified; no prior test touched. Production RAG-chain wiring,
  vendor adapters, streaming, retries, agents, and semantic
  grounding explicitly deferred. Phase 5 remains open.

## Phase 5.14 — Production RAG Composition & Infrastructure Wiring (Complete, 2026-09-23)

- `xportra/infrastructure/rag_composition.py` — the single explicit
  composition root: `RAGInfrastructureConfig` (one authoritative
  config path: `VECTOR_STORE_URL`, `VECTOR_STORE_COLLECTION`,
  `EMBEDDING_MODEL`, new `EMBEDDING_DIMENSIONS`, `LLM_API_KEY`,
  `LLM_MODEL`; `RAGConfigurationError` on missing/invalid; secret
  holder excluded from repr), `SentenceTransformerEmbeddingProvider`
  (the single approved TB-6 baseline implementation; lazy load on
  first `embed()` — composition/import never download; fail-closed
  input/dimension validation), `compose_rag_stack` (real graph:
  `QdrantClient` → one `QdrantEvidenceVectorIndex` serving both
  semantic and lexical paths → `VectorIndexEvidenceRetriever` →
  retrieval pipeline → context pipeline → prompt builder →
  `RAGApplicationService` with fail-closed validator; injected
  `LLMClient` seam required, no vendor adapter vendored),
  `RAGComposition` (service + index + `ensure_collection()`
  lifecycle hook), `compose_rag_stack_from_environment`.
- `ApplicationServices.from_environment_with_rag(*, llm_client,
  embedding_provider=None)` — opt-in once-per-lifecycle wiring;
  `from_environment()` unchanged (`rag=None` → 503 preserved).
  Resolved via lazy `importlib` so `xportra/api` keeps zero static
  infrastructure imports (Phase 5.13 boundary test preserved
  unmodified).
- `pyproject.toml` declares `qdrant-client` + `sentence-transformers`
  (CD-12; declaration only); `EMBEDDING_DIMENSIONS` added to
  `environment-schema.md` + `.env.example`.
- `tests/unit/test_rag_composition.py` (46 tests: graph, config,
  infra selection, deterministic HTTP e2e through the real domain
  graph, tenant isolation, failures, security/observability) plus
  gated `tests/integration/test_rag_qdrant_smoke.py` (skipped
  without `QDRANT_URL`).
- Verification: focused 46/46; Phase 5.1–5.14 focused 649/649;
  full suite 1117 passed + 33 skipped, 0 failures. No Phase
  5.1–5.13 behavior modified; no prior test weakened. Vendor LLM
  adapter, production LLM wiring, and live Qdrant verification
  explicitly deferred. Phase 5 remains open.

## Phase 5.15 — Production LLM Provider Adapter & Wiring (Complete, 2026-09-23)

- `OpenRouterLLMClient` (`xportra/infrastructure/llm.py`, TB-5):
  the single production `LLMClient` speaking OpenRouter's
  OpenAI-compatible chat completions over `httpx` (declared
  dependency; no vendor SDK). Structured `EvidencePrompt` →
  system + deterministically built user message (need, evidence,
  labels, order preserved verbatim; no tenant content);
  `LLMGenerationConfig` → `model`/`temperature`/`max_tokens`
  only. Provider payload → canonical `LLMResponse`
  (`""` preserved as valid empty; `None`/missing content is a
  failure). Every provider/network/shape failure → 
  `LLMProviderError("generate", cause)` (401/429/5xx, timeout,
  connect, bad JSON/shapes); malformed our-side inputs stay
  `DomainValidationError`. Exactly one POST per call (no
  retries/fallback); explicit finite timeout (default 60 s).
  Per-request Bearer headers (secret-free client); logs carry
  provider/model/latency/outcome only.
- Composition: `RAGInfrastructureConfig` gains `llm_base_url`
  (default OpenRouter endpoint, `LLM_BASE_URL` override) and
  `llm_timeout_seconds` (default 60, `LLM_TIMEOUT_SECONDS`
  override); `compose_rag_stack` auto-builds the adapter when no
  explicit client is given (explicit injection still wins);
  missing LLM credentials still fail closed at configuration.
  `.env.example` + `environment-schema.md` document the two new
  optional variables.
- Tests: `tests/unit/test_llm_provider_adapter.py` (47:
  contract, response, 12 failure cases, single-attempt proofs,
  security, immutability, composition, HTTP e2e) via
  `httpx.MockTransport` — no network/credentials; gated
  `tests/integration/test_llm_openrouter_live.py` (skipped
  without `OPENROUTER_LIVE_TEST=1` + credentials).
- Minimal task-mandated contract corrections (no weakening):
  one 5.11 assertion now allows the sanctioned `httpx`
  transport in the seam (vendor SDKs stay forbidden); two 5.14
  tests updated to the specified auto-wiring behavior
  (non-client seam still fails closed; entry point wires the
  adapter). No domain behavior modified.
- Verification: focused 47/47; Phase 5.1–5.15 focused 696/696;
  full suite 1164 passed + 34 skipped, 0 failures. Live
  provider test skipped (gate off). Streaming, tools, agents,
  retries, grounding, and combined live Qdrant+LLM
  verification explicitly deferred. Phase 5 remains open.

## Phase 5.16 — Production RAG Verification & Phase Closure (Complete, 2026-09-23)

- Verification-only phase: `tests/unit/test_rag_production_verification.py`
  (25 deterministic tests: configuration audit, security audit,
  performance sanity, full §11 failure-closed matrix through
  HTTP) + gated `tests/integration/test_rag_combined_live.py`
  (real API → isolated tenant → real Qdrant + real embeddings
  of controlled evidence → real OpenRouter → real validation;
  structural assertions only; tenant isolation + invalid-
  credential probes included).
- Audits executed: config contract complete (placeholders only,
  no obsolete vars, dimension/timeout consistency, no hidden
  fallback); secrets absent from package/logs/responses/reprs;
  domain free of IO/network/SDK imports; API builds no
  transports; adapter executes nothing; model loads once;
  single retrieval per path; stable clients across requests;
  budget-bounded context; no retries.
- Single audit correction: `LLMSettings.api_key` excluded from
  repr (`field(repr=False)`; value still usable; test-locked).
  Noted for Phase 10: `DatabaseSettings` (Phase 1.x) untouched.
- Verification: focused 25/25; Phase 5.1–5.16 focused 721/721;
  full suite 1189 passed + 37 skipped, 0 failures. Live gates
  NOT EXECUTED (`QDRANT_URL`, `OPENROUTER_LIVE_TEST` +
  credentials unset; ports 6333/6334 unreachable).
- **Phase 5 — RAG Retrieval, Generation & Validation: COMPLETE.**
  No mandatory live gate exists in roadmap/requirements; live
  tests remain available gated. No new functionality; Phase 6
  not started.

## Phase 5.12 — Answer Validation & Citation Integrity (Complete, 2026-09-23)

- `xportra/domain/answer_validation.py`:
  `AnswerValidationError(DomainValidationError)`, `AnswerValidator`
  protocol, `CitationAwareAnswerValidator`, `ValidatedAnswer`
  (frozen, reference-preserving), `CitationExtraction`,
  `extract_citation_references`, status constants. Nine additive
  exports; no Phase 5.1–5.11 behavior file modified.
- Contract: `GeneratedAnswer → AnswerValidator → ValidatedAnswer` —
  deterministic, pure, provider-independent. The original answer,
  prompt, and citations are carried by reference (assertIs-proven);
  original text recoverable verbatim; the model cannot create
  provenance, evidence, or a new citation mapping.
- Citation syntax: exact `[E<n>]` regex; strict extraction (no fuzzy
  matching, no normalization; `[e1]`, `[E1`, `[Evidence 1]`, `[E-1]`,
  `[EE1]` etc. never match); first-occurrence unique references plus
  full occurrence/position trace; repeated and adjacent citations
  deterministic.
- Authoritative universe: `GeneratedAnswer.prompt.citations`.
  Establishes (1) label exists in mapping + (2) label appears in
  answer; explicitly NOT semantic grounding. Documented statement:
  validation proves referenced labels correspond to authoritative
  retrieved evidence supplied to the model — not that the claim is
  factually or legally supported.
- Invalid-citation policy (fail closed, production default):
  unknown labels raise `AnswerValidationError`; nothing silently
  removed/rewritten/repaired; never an empty response. Optional
  structured non-raising path (`fail_on_invalid_citations=False`)
  yields status `invalid_citations` + `invalid_references`, mutually
  consistent with the raising path.
- Integrity checks fail closed: malformed answers, missing mapping,
  duplicate authoritative labels, malformed citation objects,
  cross-tenant provenance, label/rank-inconsistent citations.
  Operational `LLMProviderError` stays a separate channel.
- Empty answers: `status="empty"` — valid and distinguishable from
  provider failure, validation failure, and invalid citations
  (Phase 5.11 policy respected; nothing fabricated).
- Tenant: from the evidence chain only, single-tenant verified fail
  closed; model text can never establish tenant identity.
- Purity: AST-verified (`re`/`dataclasses`/`typing`/`__future__` +
  sibling domain modules only); no execution/tools/filesystem/
  network/LLM; no input mutation (snapshot-proven even on failure
  paths); dangerous model text inert.
- Verification: focused 50/50; whole chain (document → retrieval →
  ranking → selection → prompt → answer → validation) through real
  Phase 5.5/5.7/5.10 domain logic. Semantic grounding, vendor
  adapter, API exposure, retries explicitly deferred. Phase 5 is not
  complete.

## Phase 5.11 — LLM Invocation & Answer Boundary (Complete, 2026-09-23)

- First explicit boundary between the deterministic evidence/prompt
  subsystem and an external LLM, following the established
  domain-protocol + infrastructure-adapter pattern:
  `xportra/domain/llm.py` (`LLMClient` runtime-checkable protocol,
  `LLMGenerationConfig`, `LLMResponse`, `LLMUsage`,
  `GeneratedAnswer`) plus `xportra/infrastructure/llm.py`
  (`LLMSettings` via the canonical `LLM_API_KEY`/`LLM_MODEL`
  environment contract, provider-neutral `ScriptedLLMClient` test
  seam, `answer_from_response`, `LLMConfigurationError`).
  `LLMProviderError(operation, cause)` added to
  `xportra/domain/errors.py` mirroring `VectorStoreError`. No vendor
  SDK, no network I/O, no live credentials anywhere; six + four
  additive exports.
- Generation config: frozen/validated — non-empty model identifier,
  finite temperature in [0.0, 2.0], positive int max_output_tokens;
  bool/string/None/NaN/inf rejected fail-closed; no provider-specific
  fields invented.
- Response: canonical, provider-independent — generated text + model
  identifier, explicitly optional finish_reason/usage/provider_name;
  frozen slots prevent provider-field leakage; no secrets, keys, or
  headers ever stored (test-proven).
- Failure semantics fail closed: config validation before any
  external call; provider/timeout/auth/rate-limit failures translated
  to `LLMProviderError` with cause identity — never `""`/`None`/`[]`;
  malformed responses rejected; single call, NO automatic retry.
  Empty model output policy: returned as received with explicit
  `is_empty` flag — never fabricated, never an exception (operational
  failures have their own channel).
- Prompt immutability: the authoritative structured `EvidencePrompt`
  crosses the seam by reference (assertIs-proven), never reconstructed
  from `render()`; unchanged after success and failure; citations are
  the only authoritative evidence references — model text like `[E7]`
  is untrusted and unvalidated.
- Tenant: internal invocation metadata only — never in model-visible
  text (test-proven against system instructions, information need,
  evidence context, and rendered preview).
- Security: model output is untrusted — no execution, no tools, no
  filesystem, no external actions; the seam exposes only
  `generate` + call records (test-proven).
- Verification: focused 53/53; AST-verified adapter isolation both
  directions (domain imports no SDK/HTTP; seam contains no vendor
  SDK). Answer validation, citation correctness, injection detection,
  vendor adapters, retries, streaming, and API exposure explicitly
  deferred. Phase 5 is not complete; Phase 5.12 has not started.

## Phase 5.10 — Citation-Aware Prompt Construction (Complete, 2026-09-23)

- `xportra/domain/evidence_prompt.py`: `CitationAwarePromptBuilder`,
  `EvidencePrompt` (frozen structured prompt), `EvidencePromptConfig`,
  `PromptCitation`, `CITATION_FORMAT`, `citation_label` — the
  deterministic boundary converting the Phase 5.7
  `EvidenceContextSelection` into an LLM-ready prompt representation.
  Construction only: no LLM invocation, no answer generation, no
  retrieval/ranking/selection, no budget arithmetic, no
  summarizing/paraphrasing/truncation. No Phase 5.1–5.9 file was
  modified; six additive exports in `xportra/domain/__init__.py`.
- Prompt representation: structured and immutable —
  `system_instructions`, `information_need`, `evidence_context`,
  `citations`, headings, `tenant_id`, plus `is_empty`, `to_record()`,
  and a deterministic `render()` preview. The three components stay
  separate fields (never one opaque string) — the prompt-injection
  DATA boundary; detection/enforcement deferred to the future
  generation boundary.
- Citations: `[E1]`…`[E3]`… assigned in the selection's
  authoritative order — deterministic, prompt-locally unique,
  stable for the prompt lifetime; explicit rank relationship verified
  (`citation.rank_position == selected.rank_position`).
  `PromptCitation` carries the original `SelectedEvidence` by
  reference (`assertIs`-proven), so the full Phase 5.9 provenance
  chain resolves by reference — no schema duplication. `[E1]` means
  "first evidence item in this prompt", never "legally authoritative
  citation".
- Determinism: identical inputs → identical prompt and rendering;
  no timestamps, random ids, environment values, or hidden metadata.
  Evidence order preserved exactly (no reordering/grouping/dedup).
- Content integrity: two-space indent per evidence line is a
  formatting wrapper only — original content recovered verbatim
  after stripping it (multi-line and 2000-char items test-proven);
  metadata lines (Source/Source type/Document version/Evidence:
  marker) distinct from the content body.
- Tenant: builder exposes no tenant parameter (signature-verified);
  identity from the evidence contract only, validated single-tenant
  (multi-tenant fails closed as defense-in-depth).
- Validation (fail-closed): non-selection input, empty/non-string
  information need, invalid config, malformed selected items,
  rank/citation inconsistency, tenant-less evidence, multi-tenant
  selection. Empty evidence is a valid prompt (zero citations,
  explicit "no evidence matched" marker in render) — nothing
  fabricated.
- Purity: AST-verified — only dataclasses/typing/__future__ + sibling
  domain imports; no LLM/Qdrant/DB/HTTP/file/tokenizer/os/dotenv; no
  input mutation (frozen objects, snapshot-tested).
- Verification: focused 51/51 (selections built through the real
  Phase 5.5 ranker + Phase 5.7 selector); no Phase 5.1–5.9 behavior
  changed. LLM adapter, answer generation, injection detection,
  tokenizer budgeting, and API exposure explicitly deferred.
  Phase 5 is not complete; Phase 5.11 has not started.

## Phase 5.9 — Evidence Provenance Chain Audit & Contract (Complete, 2026-09-23)

- Audit-only phase — **no production code modified**. Formalized the
  end-to-end provenance chain (Phase 4.0 document identity → 4.2
  chunking → 5.1 retrieval → 5.4 hybrid → 5.5 ranking → 5.7 selection
  → 5.6/5.8 pipelines) in `docs/phases/phase-5-9-evidence-provenance-contract.md`
  and verified it with 31 focused tests in
  `tests/unit/test_evidence_provenance.py`.
- Canonical identity: derived uuid5 `stable_document_id(tenant, source,
  version)` and `stable_chunk_id(tenant, document, index, fingerprint)`
  plus sha256 `content_fingerprint` — one authoritative mechanism,
  no second identity system introduced. Identity drift is
  unconstructible at the owning boundaries (construction-enforced).
- No new provenance value object: `EvidenceRetrievalResult` (Phase 5.1,
  frozen, 13 fail-closed fields) already is the authoritative
  provenance carrier; every Phase 5 transition wraps it by reference
  (assertIs-verified: one object survives candidate → ranked →
  selected). All chain objects frozen — in-place provenance mutation
  impossible.
- Validation ownership documented per layer (4.2 owns
  content↔fingerprint; 5.1 owns provider payload integrity; 5.4 owns
  candidate source↔score consistency; 5.5 owns duplicate chunk
  identity; 5.7 owns tenant/content/rank-order integrity at the
  context boundary; 5.6/5.8 own composition integrity only). No
  validation duplicated across layers.
- Integrity tests prove fail-closed behavior for cross-tenant
  evidence, duplicate chunk identity, fabricated retrieval-source
  provenance, malformed candidates/payloads, emptied content, and
  rank-order violations — each detected at its owning layer.
- End-to-end traceability: real document → real chunking → real
  5.6/5.8 pipelines → selected items traced back to exact original
  chunk (tenant, document, version, chunk, source, fingerprint, rank,
  key); distinct document versions with identical content never
  collapse.
- Source traceability semantics documented: `source_id`/`source_type`/
  `source_location` are provenance pointers, NOT legal citations;
  `source_location` optionality preserved faithfully; no URLs
  invented.
- Verification: focused 31/31; no Phase 4/5 behavior changed; no
  prior test weakened. Phase 5 is not complete; no Phase 5.10 exists
  in the phase plan.

## Phase 5.8 — Retrieval-to-Context Pipeline Composition (Complete, 2026-09-23)

- `xportra/domain/evidence_context_pipeline.py`:
  `EvidenceContextPipelineContract` (runtime-checkable protocol),
  `EvidenceContextPipeline`, and `build_evidence_context_pipeline` —
  the second application-facing orchestration boundary, composing the
  Phase 5.6 retrieval pipeline and the Phase 5.7 context selector into
  one call (`select_context(information_need, *, tenant_id, mode,
  context_budget, scope=None, top_k=DEFAULT_TOP_K,
  candidate_pool=None) -> EvidenceContextSelection`). No Phase 5.1–5.7
  file was modified; only additive exports in
  `xportra/domain/__init__.py`.
- Composition only — reimplements nothing: retrieval is delegated
  unchanged to the injected `RetrievalPipeline` (never
  `ComposedHybridEvidenceRetriever` or `EvidenceRanker` directly);
  selection is delegated unchanged to the injected `ContextSelector`
  with the caller's `EvidenceContextBudget`. No budget arithmetic, no
  pre-filtering, no truncation, no token estimation, no score
  inspection, no oversized-item policy at this layer.
- Dependency injection: both collaborators injected explicitly, with
  fail-closed construction validation (`DomainValidationError`);
  no DI framework, no infrastructure construction. The factory wires
  the Phase 5.6 factory + Phase 5.7 `DeterministicContextSelector`
  default — construction consistency only.
- Tenant/scope/mode: `tenant_id` mandatory at this API boundary via
  `require_tenant_context` (no second isolation mechanism); `scope`
  forwarded with object identity preserved (assertIs-tested); `mode`
  forwarded unchanged — Phase 5.6 owns validation, no silent
  conversion. `top_k`/`candidate_pool` forwarded per the Phase 5.6
  contract.
- Result integrity: the returned `EvidenceContextSelection` is the
  exact object produced by the selector (assertIs-tested); ranked
  results reach the selector in retrieval order, unmodified, no
  premature truncation; full provenance survives by reference end to
  end. Structural defense-in-depth on the retrieval pipeline's output
  only (malformed output fails closed).
- Empty behavior: empty ranked evidence flows to the selector and
  returns its established successful empty selection — never an
  error, never a fabricated result.
- Failure semantics: fail-closed, no broad exception handling —
  retrieval and selection failures propagate with exception identity
  (RuntimeError/KeyError/DomainValidationError all test-proven); the
  selector is never invoked after a retrieval failure; validation
  failures fail closed before any collaborator runs.
- Purity: AST-verified — only sibling domain imports plus
  typing/__future__; no Qdrant/HTTP/embedding/LLM/tokenizer/database
  SDK; no network I/O; no mutation of inputs or global state; no
  prompts, answers, or compliance decisions.
- Verification: focused 41/41; Phase 5.1–5.7 focused re-runs and
  complete tree recorded below (see Phase 5.8 verification state in
  the Status section). Import check: all three new symbols resolvable
  from `xportra.domain`. Phase 5 is not complete; no Phase 5.9 exists
  in the phase plan.

## Phase 5.7 — Budget-Aware Context Selection (Complete, 2026-09-23)

- `xportra/domain/evidence_context.py`: `EvidenceContextBudget`
  (frozen, strict value object), `SelectedEvidence` (thin frozen
  wrapper carrying the `RankedEvidenceResult` by reference +
  `character_count`), `EvidenceContextSelection` (selected items +
  `used_budget`/`remaining_budget`/`skipped_rank_positions` +
  `to_record()`), `ContextSelector` protocol, and
  `DeterministicContextSelector` — the deterministic boundary between
  Phase 5.6 ranked output and downstream context use. No Phase 5.1–5.6
  file was modified.
- Budget semantics: content-characters-only accounting — the budget
  bounds the sum of `len(content)` over selected items; separators,
  labels, wrappers, and prompt scaffolding are NOT counted (prompt
  formatting is a later boundary). Explicitly documented as a
  deterministic approximation, NOT an exact LLM token count;
  tokenizer-based accounting deliberately deferred, no tokenizer
  dependency introduced. Strict validation: zero/negative/bool/float/
  str/None all rejected fail-closed.
- Selection algorithm: greedy single pass in given (Phase 5.5 rank)
  order; include iff `used + len(content) <= budget`; deterministic
  skip-and-continue when an item exceeds the remaining budget (rank
  gap recorded in `skipped_rank_positions`); no reordering, no
  rescoring, no dedup, no balancing.
- Oversized-item policy: an item larger than the TOTAL budget is
  rejected fail-closed (production chunking bounds content at 1200
  chars, so this indicates corruption/misuse, not a normal skip); an
  item exceeding only the REMAINING budget is skipped and selection
  continues. Content is never truncated. Empty selection is a valid
  successful outcome (empty input, or nothing fits).
- Ordering/provenance/tenant: selected items retain rank order with
  explicit gaps (never independently sorted); every item preserves
  tenant, chunk/document/version, source, content, fingerprint,
  embedding contract, scores, retrieval sources, and ranking key by
  reference; tenant context mandatory and re-validated per item
  (cross-tenant fails closed; no second isolation mechanism).
- Integrity (fail-closed `DomainValidationError`): malformed ranked
  input, non-`RankedEvidenceResult` items, empty/malformed content,
  duplicate chunk identity, non-positive/non-ascending rank positions,
  cross-tenant results, items over total budget, invalid budgets.
  Nothing silently repaired, dropped, or truncated.
- Purity: no Qdrant/HTTP/embedding/LLM/tokenizer/database access; no
  infrastructure imports (AST-verified); no mutation of inputs or
  global state; no compliance decisions, answers, or prompts.
- Verification: focused 45/45; Phase 5.1–5.6 focused re-runs 251/251
  (56+40+41+58+56+39); complete tree 803 passed + 32 skipped
  (`DATABASE_URL` unconfigured, as every prior phase). Import check:
  all five new symbols resolvable from `xportra.domain`.
  Phase 5 is not complete; Phase 5.8 has not started.

## Phase 5.6 — Retrieval Pipeline Orchestration (Complete, 2026-09-23)

- `xportra/domain/evidence_pipeline.py`: `RetrievalPipeline` protocol
  (runtime-checkable, application-facing), `EvidenceRetrievalPipeline`,
  and `build_evidence_retrieval_pipeline` — the first application-facing
  orchestration boundary composing Phase 5.4 hybrid retrieval and Phase
  5.5 deterministic ranking into one call
  (`retrieve(information_need, *, tenant_id, mode, scope=None,
  top_k=DEFAULT_TOP_K, candidate_pool=None)`).
- Composition only — reimplements nothing: it constructs the Phase 5.2
  `EvidenceRetrievalQuery` (normalization semantics for free), forwards
  `tenant_id` (mandatory `TenantContext` via `require_tenant_context`,)
  and `scope` (identity-preserved; `None`/empty = tenant-only) unchanged
  to the Phase 5.4 retriever, and returns Phase 5.5
  `RankedEvidenceResult[]` verbatim. No competing query/scope/candidate/
  result model was created.
- Mode is explicit and required (`semantic` | `lexical` | `hybrid`,
  validated against `RETRIEVAL_MODES` before any retriever call); no
  silent default (omitting `mode` raises `TypeError`); invalid modes fail
  closed.
- Top-k ownership: exactly ONE authoritative final top-k — the Phase 5.5
  ranker's post-ordering truncation, driven by the pipeline's `top_k`.
  `candidate_pool` (default `top_k`) is the separate explicit per-path
  retrieval bound inside the Phase 5.4 query, so the ranker sees the full
  merged pool (up to 2 × candidate_pool before Phase 5.2 duplicate
  collapse); the pipeline never truncates before ranking and never
  multiplies top-k by a hidden constant.
- Failure propagation: no broad exception handling — embedding,
  vector-store, lexical, and ranking failures propagate unchanged;
  `[]` still means exactly "successful retrieval, no evidence matched".
- Result integrity: ranked results returned as produced (identity
  asserted) — rank positions, scores, retrieval-source provenance, and
  ranking keys untouched; dependency results never mutated. Structural
  defense-in-depth on the injected ranker's output only.
- Purity: no LLM, embedding, Qdrant, lexical-matching, score-computation,
  or compliance-decision logic; AST-verified stdlib + intra-domain
  imports only. Explicit structural constructor validation keeps the
  pipeline fake-testable; the factory composes
  `ComposedHybridEvidenceRetriever` + `DeterministicEvidenceRanker`
  (default ranker) with no DI framework and no startup wiring.
- Verification: focused 39/39; Phase 5.1–5.5 focused re-runs 251/251
  (56+40+41+58+56); complete tree 758 passed + 32 skipped (`DATABASE_URL`
  unconfigured, as every prior phase). No LLM, context selection, prompt
  generation, answer generation, or compliance reasoning introduced.
  Phase 5 is not complete; Phase 5.7 has not started.

## Phase 5.5 — Retrieval Ranking & Reranking (Complete, 2026-09-23)

- `xportra/domain/evidence_ranking.py`: `EvidenceRanker` protocol
  (runtime-checkable, provider-independent), `DeterministicEvidenceRanker`,
  and `RankedEvidenceResult` — a thin frozen wrapper carrying an explicit
  1-based `rank_position`, the unchanged Phase 5.1 `EvidenceRetrievalResult`
  by reference (no second evidence representation), both per-path scores,
  retrieval sources, and a structured `ranking_key` (the explicit sort
  tuple) for explainability without natural-language generation.
- Ranking policy (deterministic, explainable): provenance tier first
  ({"semantic","lexical"} > {"semantic"} > {"lexical"} — an informational
  agreement signal, not a score combination), then descending semantic
  score, then descending lexical score, then ascending `chunk_id`. Semantic
  and lexical scores are never added, weighted, normalized, or fused: their
  contracts (similarity value vs term-frequency count) are not comparable
  and no normalization is justified by the actual score contracts.
- Deterministic tie-breaking by ascending canonical `chunk_id`; no set/dict
  iteration order, provider ordering, or object identity participates.
  Repeated ranking of the same candidate set — in any input order —
  produces the identical order (test-proven).
- Top-k is applied at the ranking layer after ordering: the ranker sees the
  full Phase 5.4 candidate pool (up to 2 × top_k before Phase 5.2 duplicate
  collapse), and the final `top_k` truncates ranked results only;
  retrieval candidate count and final ranked result count stay explicit and
  distinct.
- Provenance preservation: ranking changes order, not evidence identity.
  Every result preserves chunk/document identity, document version, source,
  content, fingerprint, tenant, both scores, and retrieval sources (the
  same evidence object, not a copy; inputs are never mutated).
- Purity: no network, Qdrant, embedding, or LLM call; no mutation. The
  module's imports are verified stdlib + intra-domain only (AST test). No
  compliance or legal-authority signal (no source type, reputation,
  jurisdiction, or age) — the repository has no domain authority model to
  justify one; ranking is retrieval relevance, not legal authority.
- Fail-closed validation: duplicate chunk identity, both-scores-missing,
  non-finite (NaN/inf) or bool/str scores, source/score inconsistency,
  malformed sources, and invalid top-k (zero/negative/bool/float/str/None)
  raise `DomainValidationError`; an empty candidate list returns `[]`.
  Phase 5.4's candidate invariant is re-checked as defense in depth rather
  than re-derived.
- Verification: focused 56/56; Phase 5.1 56/56, Phase 5.2 40/40,
  Phase 5.3 41/41, Phase 5.4 58/58 re-runs (195 focused, no regressions);
  full suite 719/719 (663 + 56), 0 failures. No LLM, learned reranker,
  cross-encoder, answer generation, or compliance reasoning introduced.
  Phase 5 is not complete; Phase 5.6 has not started.

## Phase 5.4 — Hybrid Retrieval Boundary (Complete, 2026-09-22)

- `xportra/domain/evidence_hybrid.py`: `RETRIEVAL_MODES`/`RETRIEVAL_SOURCES`;
  deterministic `lexical_tokens`/`lexical_terms`/`lexical_matches`/
  `lexical_relevance_score` (lowercase alphanumeric tokens, no stemming/
  stop-words/fuzzy matching, exact whole-token AND semantics);
  `EvidenceLexicalIndex` protocol (`find_lexical`); `HybridRetrievalCandidate`
  (wraps the existing `EvidenceRetrievalResult` plus per-path scores and
  source labels — never a fused/combined score); `HybridEvidenceRetriever`
  protocol + `ComposedHybridEvidenceRetriever` with explicit, required
  `mode` (`semantic` | `lexical` | `hybrid`).
- Semantic mode composes the unchanged Phase 5.1 retriever (embedded
  query → vector search); lexical mode uses terms derived from the
  normalized query and never embeds; hybrid runs both and merges by
  canonical `chunk_id`, preserving both scores and both source labels.
- Qdrant adapter: `find_lexical` via `scroll` with the mandatory tenant
  condition + scope conditions + `MatchText(content)`; conservative text
  payload index provisioned idempotently (WORD tokenizer, lowercase, no
  stop-words/stemmer); provider over-matches narrowed by explicit
  verification of the domain whole-token rule; lexical relevance
  (term occurrences) computed in the domain; deterministic ordering
  (relevance desc, `chunk_id` asc). No new dependency; no second search
  system.
- Tenant/scope: both paths enforce the Phase 5.1/5.3 invariants, and the
  merged candidate set is re-validated; cross-tenant or out-of-scope
  results raise `VectorStoreError` (integrity failure), never a silent
  drop or empty success. Phase 5.2's provenance-aware duplicate rule
  (`evidence_duplicate_key`) remains authoritative across the union.
- Failure behavior: fail closed with **no degraded mode** — a hybrid call
  raises if either branch fails (lexical failures are wrapped as
  `VectorStoreError("hybrid evidence retrieval (lexical path)")`);
  empty lexical queries are rejected; `[]` remains reachable only for
  genuine "no evidence" outcomes.
- Verification: focused 58/58 (fakes only, no live Qdrant); Phase 5.1
  re-run 56/56, Phase 5.2 40/40, Phase 5.3 41/41; full suite 663/663
  (605 + 58), no regressions. No LLM query rewriting, generated terms,
  reranking/cross-encoder, hybrid fusion ranking, answer generation,
  compliance reasoning, citation generation, agentic retrieval,
  conversational memory, or query classification introduced.
  Phase 5.5 has not started; Phase 5 is not complete.

## Phase 4.4 — Vector Index Persistence Boundary (Complete, 2026-09-22)

- `xportra/domain/vector_index.py`: `EvidenceVectorIndex` protocol
  (upsert/get/delete, tenant-scoped) + `VectorIndexConfig`; domain imports
  no Qdrant types.
- `xportra/infrastructure/vector_index.py`: `QdrantEvidenceVectorIndex` —
  idempotent `ensure_collection`, canonical `chunk_id` point IDs, idempotent
  upsert, provenance payload with `tenant_id`, tenant-scoped get/delete,
  fail-closed validation, `VectorStoreError` translation.
- Fixed broken `xportra.infrastructure.vector_index` imports in both
  `__init__.py` files; `VectorStoreError` added to domain errors.
- Verification: focused 48/48, full suite 438/438, imports verified
  (infrastructure + domain), no regressions.
- Real Qdrant integration NOT run: no configured Qdrant instance
  (`QDRANT_URL`/`QDRANT_HOST` unset, connection timed out); unit tests use a
  fake client. No search/retrieval/RAG API introduced.

## Phase 4.1 — Evidence Document Ingestion Boundary (Complete, 2026-09-22)

- `EvidenceDocumentIngestionService.ingest(source_record, *, tenant_id)`:
  validates provenance/source type/tenant/content/metadata/dates/version,
  normalizes title/source_location only, preserves content byte-for-byte,
  persists via `EvidenceDocumentRepository` only.
- Idempotent identical re-ingestion; conflicting duplicates rejected
  (no overwrite); stable Phase 4.0 identity reused; no acquisition and no
  retrieval/RAG/LLM implemented.
- Verification: focused 26/26, full suite 339/339, no regressions.
- PostgreSQL integration tests not run (`DATABASE_URL` unconfigured).

## Phase 4.2 — Evidence Chunking Boundary (Complete, 2026-09-22)

- `EvidenceChunk` + `EvidenceChunkingService.chunk(document, *, tenant_id)`:
  blank-line paragraph segmentation with deterministic
  `MAX_CHUNK_CHARACTERS = 1200` bound; oversized paragraphs split at the
  last whitespace per window; chunk content always an exact substring.
- Stable uuid5 chunk identity (tenant + document + index + content
  fingerprint); provenance/tenant propagated unchanged; sections never
  inferred; in-memory representation only (no repository/migration).
- Verification: focused 25/25, full suite 364/364, no regressions.
- No embeddings/retrieval/RAG/persistence implemented.

## Local-Development Bootstrap (Complete, 2026-09-27)

- Development-only utility `python -m xportra.dev.bootstrap`
  (`xportra/dev/bootstrap.py`): idempotently provisions
  tenant `local-development`, user
  `local-developer@xportra.local`, and one active owner
  membership; refuses `APP_ENV=production` before any
  DB use; optional `--supabase-uid` links a real Auth
  identity, never mints tokens. New natural-key lookups
  `get_by_slug` / `get_by_email` / `set_supabase_uid`;
  no auth/tenant-isolation/production behavior changed.
- Verification: 20/20 focused tests; full suite 1922
  passed + 44 skipped (1902 + 20 new), 0 failures.
- Guide: `docs/local-development.md`. No secrets
  committed; no commit/push performed.

## Secure CORS Boundary for Local Frontend ↔ API Development (Complete, 2026-09-27)

- Explicit CORS boundary at the FastAPI application
  layer (R-10.1.6): `CORSMiddleware` wired in
  `xportra/api/app.py` with origins resolved by
  `cors_allowed_origins()` in `xportra/api/runtime.py`.
  Development/test permit exactly `http://localhost:5173`
  and `http://127.0.0.1:5173`; production uses only
  `CORS_ALLOWED_ORIGINS` (fail-closed when empty) with
  wildcards and malformed values rejected at startup.
  Exact methods (`GET`, `POST`) and headers
  (`Content-Type`, `Authorization`,
  `X-Development-Tenant-ID`); credentials support stays
  disabled. No auth/tenant-isolation change, no frontend
  change, no other behavior change.
- Verification: 17/17 focused tests (+15 subtests);
  related API/security suites 175/175; full suite 1939
  passed + 44 skipped (1922 + 17 new), 0 failures.
  Manual preflight check: `OPTIONS
  /compliance/workflows/start` returns 200 with correct
  `access-control-allow-origin` for both loopback
  origins, 400 with no permissive headers for
  disallowed origins. Note: a running uvicorn process
  serves pre-change code until restarted.
- Config documented in `.env.example` and
  `docs/architecture/environment-schema.md`. No secrets
  committed; no commit/push performed.

## Approved-Reference Frontend Convergence (Complete, 2026-09-28)

- Frontend-only convergence of the shipped
  application onto the approved visual/UX
  reference (`docs/design/xportra-ui-redesign.html`
  + `docs/design/xportra-ui-redesign.txt`), preserving
  all real functionality, data boundaries,
  routing, authorization, workflow semantics,
  and backend/API contracts. No backend,
  domain, API, migration, or compliance-logic
  file changed.
- Tokens: dark `xb-` values retargeted to the
  reference palette (`#0D1512` foundation,
  `#C7F464` lime, five semantic colors);
  Inter + Source Serif stacks; 3px/6px radii.
  Light theme kept (color-only override).
  In-suite WCAG AA guards green.
- Landing: nav offers only Sign In (`/session`,
  also `/signin`) and Get Started (`/start`,
  also `/signup`); no public Start-a-Shipment
  CTA; single-sentence serif hero with no
  forced breaks; hairline strip + three text
  columns + minimal footer.
- Dashboard "Your shipments": attention block
  + recent worklist (dot/name/route/state) +
  View all; no greeting, counts, cards, or
  analytics. Recent limit 3 → 5 (reference:
  last 4–6).
- New Shipment: centered 560px column, "What
  are you exporting?" + "Where is it going?"
  first, follow-up fields in an adaptive inset;
  same validation/creation/registry logic.
- Workspace: vertical identity → state →
  briefing → attention → full ledger; rows
  open the 460px drawer (back-link close,
  dot+word status, focus trap/return);
  no parallel Documents section, no cards.
- Archive: search + All/Active/Incomplete/
  Completed chips, grouped worklist rows,
  dimmed completed history, device-only
  Forget preserved. Historical report: exact
  persistent read-only banner, static final-
  state ledger, readable documents, no pills,
  no invented dates. Settings: quiet two-
  column nav + label/value rows, real
  controls only.
- Verification: full frontend suite 61 files /
  398 tests passing (none weakened);
  `npx tsc --noEmit` clean; `npm run build`
  succeeds. Legacy `/workspace/*` deep-link
  tree preserved untouched for compatibility.
  No browser/pixel review available — human
  visual review remains the gate. No commit
  or push performed.

## Landing Page Motion & Sticky Header (Complete, 2026-09-28)

- Public landing page only: sticky header
  (`position: sticky`, page-background base,
  quiet `--xb-surface` + stronger border once
  scrolled past 8px, smooth token-timed
  transition, no blur/glass); one-shot hero
  entrance (heading → paragraph → CTAs →
  strip, 90ms staggers, 10px rise + fade);
  IntersectionObserver viewport reveal with
  stagger for the "Three things" columns
  (immediate-visible fallback where
  unsupported); editorial workflow diagram
  (Shipment → Requirements → Evidence →
  Ready) as an ordered list on one hairline
  with a slow 12s dot/name highlight walking
  the stages (lime = active stage only).
  Public nav, routes, copy, and all other
  screens untouched; no new dependencies; no
  metrics, scores, or invented claims.
- Reduced motion: entrance/reveal/workflow
  transforms and loops disabled with content
  immediately visible; sticky header retained
  (layout, not decoration).
- Verification: full frontend suite 62 files /
  410 tests passing (none weakened);
  `npx tsc --noEmit` clean; `npm run build`
  succeeds; production preview serves `/` at
  200. No browser/pixel review available —
  human visual review remains the gate. No
  commit or push performed.

## Server-Persisted Workflow Record (Complete, 2026-10-03)

- Implements the Phase 8 integration-audit blocker:
  `xportra.compliance_workflows` through migration
  012 (plus rollback) makes the workflow record
  (`state`, `shipment_id`, `supplied_evidence_ids`,
  `open_requirements`) server-owned. Mutations load
  the authoritative row, reject stale/forged snapshots
  (`StaleAnalysisError` with field-level reasons),
  apply the unchanged domain transition, and persist
  the outcome; result/package writes carry the
  workflow update in the same transaction. Tenant
  scoping enforced on every read/write;
  `supply_evidence` additionally requires
  tenant-owned recorded evidence when both
  boundaries are wired. No transition-rule,
  contract, frontend, or result-architecture change.
- Verification: new unit suite 15/15
  (`tests/unit/test_workflow_record_persistence.py`);
  new DATABASE_URL-gated HTTP end-to-end suite skips
  without a live database
  (`tests/integration/test_workflow_record_postgresql.py`);
  full backend 1954 passed + 46 skipped (gated
  Postgres/Qdrant/OpenRouter-live), 0 failures. One
  existing assertion updated for the intended new
  evidence-lookup collaborator (statelessness intent
  preserved). Frontend untouched.
- Task record:
  `tasks/completed/server-persist-workflow-record.md`.
  Deferred (not implemented): `requirement_id`
  linkage, read-projection anchoring, shipment
  modeling, frontend registry/fallback/duplication.

## Persisted Report Rehydration (Complete, 2026-10-03)

- Frontend-only follow-on to server-owned workflow
  and result persistence: shared `useStoredReport`
  hook (`frontend/src/app/useStoredReport.ts`)
  resolves the effective report (in-memory first,
  else the latest recorded round's report fetched
  once through the existing
  `GET /compliance/reports/{report_id}` endpoint
  and adopted into `AnalysisContext`), so
  FindingsPage and the shipment workspace render a
  persisted report after reload. Distinct loading
  ("Reading the stored analysis…"), genuine
  absence ("No analysis yet"), stored-but-missing
  ("Report unavailable" on 404-shaped errors), and
  failure (`ErrorNotice`) states; one fetch per
  report; never clobbers a newer in-memory report;
  nothing duplicated into browser persistence. No
  UI redesign, no backend/API change, no
  data-model change.
- Verification: new hook suite 4/4; FindingsPage
  +4, workspace +1; full frontend suite 63 files /
  426 tests, 0 failures; `npx tsc --noEmit` clean;
  `npm run build` succeeds.
- Task record:
  `tasks/completed/persisted-report-rehydration.md`.

## Shipment Aggregate Architecture Decision (Docs only, 2026-10-07)

- Shipment Persistence Boundary Audit completed (starting evidence):
  commercial shipment/profile facts live only in frontend
  state/sessionStorage; case_id and shipment_id intentionally
  distinct; compliance_workflows persists process state with no
  commercial profile fields; exporters/products/destination_markets
  are reusable master data, not shipment instances.
- Dedicated tenant-scoped first-class Shipment aggregate selected
  over workflow-column, master-reuse, and client-only alternatives;
  recorded in `docs/decisions/ADR-0013-shipment-aggregate-boundary.md`.
- Implementation intentionally not started: no migration 013, no
  repository/service/schema/frontend/transition/test change.
  Task record:
  `tasks/completed/shipment-aggregate-architecture-decision.md`.

## Shipment Persistence Boundary (Implemented, 2026-10-07)

- ADR-0013 implemented as the minimum v1 aggregate:
  migration 013 (`migrations/013_shipments.sql` +
  `.down.sql`) creates tenant-scoped `xportra.shipments`
  (`PRIMARY KEY (tenant_id, shipment_id)`, profile
  facts, `draft | bound | locked` status, standard
  timestamps); no FK from `compliance_workflows` (would
  reject existing client-generated identities on real
  data — enforced in the application/store boundary
  instead); no profile columns in `compliance_workflows`.
- Domain `Shipment` + `ShipmentService`
  (`xportra/domain/shipment.py`): validation, record
  round-trip, `draft → bound → locked`, draft-only
  edits (bound/locked reject — no reanalysis path
  invented). `bind_shipment` now resolves against the
  server-owned row; arbitrary UUIDs fail closed (404).
- `POST /compliance/workflows/start` accepts the
  already-collected profile (`shipment: {product,
  origin_country, destination_country, quantity, unit,
  shipment_date}`); shipment + workflow persist in one
  transaction with adopt-on-retry (profile/case
  mismatch → 409, never silent replace). Frontend New
  Shipment flow sends the profile (no new UI);
  sessionStorage remains display metadata only.
- Compliance input precedence explicit → server
  shipment → error at applicability (`shipment_id`
  default); analysis verifies the bound shipment
  resolves without rewriting caller cases (no analysis
  redesign). ADR-0013 open questions OQ-S1–OQ-S6
  remain open.
- Verification: backend 2001 passed + 61 subtests;
  frontend 63 files / 427 tests, `tsc` clean, build
  succeeds; PG integration gated (48 skipped, no
  `DATABASE_URL`).
- Task record:
  `tasks/completed/shipment-persistence-implementation.md`.

## Durable Shipment Listing and History (Implemented, 2026-10-07)

- Server-backed discovery: `ShipmentRepository.list_for_tenant`
  (newest-first, limit/offset, plus count) and
  `ComplianceWorkflowRepository.list_for_shipment`
  (recency order, multiplicity preserved); read-only
  `ShipmentListingService` composes shipment + latest
  workflow summary (`is_closed`, counts, round count,
  `latest_report_id`, full workflow record,
  `workflow_count`); `GET /compliance/shipments`
  (paginated, `all|active|completed`) and
  `GET /compliance/shipments/{shipment_id}` (404 for
  unknown/cross-tenant). No new migration, no new
  aggregate, no state machine change.
- Completion stays workflow/package based (terminal
  state + package linkage); shipment `locked` is never
  read as completed (finalization still does not enact
  it — future lifecycle task).
- Frontend history/resume reads are server-backed:
  dashboard, archive, workspace reload, and historical
  report resolve the durable list (server wins over
  stale snapshots); drafts bind through the existing
  start endpoint; `forgetShipment` stays device-local
  hiding (new hide-set, never server deletion);
  `useStoredReport` unchanged. sessionStorage remains
  as UI cache/mutation continuity/suggestions only.
- Verification: backend 2019 passed + 61 subtests;
  frontend 64 files / 439 tests, `tsc` clean, build
  succeeds; PG integration gated (51 skipped, no
  `DATABASE_URL`).
- Task record:
  `tasks/completed/shipment-listing-history-implementation.md`.

## Shipment Lock on Finalization (Implemented, 2026-10-07)

- Terminal finalization atomically locks the shipment:
  `ComplianceResultStore.store_package_linkage` now
  resolves the workflow's shipment `(tenant, shipment)`,
  verifies case match and `bound` status through existing
  domain rules, and writes `bound → locked` in the same
  transaction as the package linkage + terminal workflow
  row (new `ShipmentRepository.get_in_transaction`).
  Any terminal-write failure rolls all three back
  together; package-conflict retry keeps terminal state
  without reopening; unknown/cross-tenant/case-mismatch/
  draft fail closed with existing errors.
- Workflow completion remains independently represented
  by `assessment_package_ready` + package linkage;
  listing/detail semantics unchanged; `locked` is now
  the truthful commercial closed state, not a
  completion signal.
- Verification: backend 2033 passed + 61 subtests;
  frontend untouched; PG integration gated (51 skipped,
  no `DATABASE_URL`).
- Task record:
  `tasks/completed/shipment-lock-finalization.md`.

## Shipment Lifecycle Audit and Hardening (Complete, 2026-10-07)

- Focused end-to-end audit of the persisted lifecycle
  (`draft → bound → workflow → package → locked`) and
  its API/frontend contract: no broad redesign, fixes
  only where correctness required.
- Findings fixed: listing/detail endpoints now fail
  closed with 503 (stored-path convention) where no
  result store is wired; discovery fetches use a bounded
  full window (`DISCOVERY_PAGE_SIZE = 100`) so large
  histories are not truncated at the default page;
  list composes each shipment's workflows in a single
  read pass. No migration, no new fields, no
  versioning/snapshots/delete semantics, no FK change.
- Verified holding: server-authoritative identity on
  every boundary; fresh-session discovery/resume/report
  from PostgreSQL; stale snapshots rejected (409) and
  never overwrite server state; deterministic
  latest-activity selection with surfaced multiplicity;
  atomic lock + package + terminal persistence with no
  API bypass; completion still `assessment_package_ready`
  + package linkage.
- Verification: backend 2034 passed + 61 subtests;
  frontend 64 files / 439 tests, `tsc` clean, build
  succeeds; PG integration gated (51 skipped, no
  `DATABASE_URL`).
- Task record:
  `tasks/completed/shipment-lifecycle-audit-hardening.md`.

## Compliance Workflow Persistence Audit (Complete, 2026-10-07)

- Focused end-to-end audit of the workflow persistence
  contract with shipment durable: one real gap found
  and fixed — evidence-upload terminal checks read the
  client snapshot only, so a stale open snapshot could
  authorize storage/DB writes against a finalized
  workflow. The upload service now resolves the
  authoritative server workflow state (new narrow
  `ComplianceResultStore.get_workflow_state` read, no
  snapshot-equality overreach) before any mutation;
  unwired deployments keep snapshot behavior.
- Verified holding: server-owned identity everywhere;
  every legal transition persisted before success;
  evidence/supplied/open-requirement durability with
  cross-tenant and cross-case rejection; round
  first-writer-wins with deterministic latest; report
  rehydration from stored rows; single package-write
  path with atomic lock; full-snapshot 409 comparison
  on all mutating workflow calls; fresh-session
  recovery from server state; per-operation
  transactions with no partial persistence.
- Verification: backend 2039 passed + 61 subtests;
  frontend untouched; PG integration gated (51 skipped,
  no `DATABASE_URL`).
- Task record:
  `tasks/completed/compliance-workflow-persistence-audit.md`.

## Production-Readiness Audit (Complete, 2026-10-07)

- Sixteen-concern audit (config, auth, tenancy, DB/
  migrations, API errors, transactions, evidence,
  logging, runtime, CORS/HTTP, frontend contract,
  dev-leakage, hygiene, CI/CD, deployment, recovery):
  **no code defects found, no code changed.**
- Verdict: no code-level blocker; deployable after
  operational prerequisites (production env + secrets,
  ordered psql migrations 001–013, `VITE_API_BASE_URL`
  production build, Supabase Auth/Postgres/private
  bucket, explicit CORS origins; Qdrant/OpenRouter only
  for analysis/RAG paths).
- Accepted v1 limits: no CI, no Dockerfile/pooling,
  stdlib logging only, in-memory frontend session,
  untracked local artifacts left for operator cleanup.
- Verification: focused prod/security/auth 77 passed +
  24 subtests; full backend 2039 passed + 61 subtests;
  frontend untouched; integration gated (51 skipped).
- Task record:
  `tasks/completed/production-readiness-audit.md`.

## v1 Deployment Preparation (Complete, 2026-10-07)

- Deployment preparation only (no deploy performed,
  no live results claimed): concrete checklist for
  provisioning, configuration, migration 001→013 via
  existing `psql` tooling, Supabase setup, backend/
  frontend deployment, CORS, 15-step authenticated
  smoke procedure, verification gate, and
  failure/recovery notes in
  `docs/deployment/XPORTA-V1-DEPLOYMENT.md`.
- Env contract verified: `.env.example` covers every
  variable the code reads; no undocumented variables;
  no secrets in tracked files (secret-pattern scan
  clean; `.env` ignored/untracked). Migrations 001–013
  (+ down-migrations) present and ordered; no runner
  introduced; no migration modified.
- Untracked local artifacts documented for operator
  cleanup, left untouched per scope
  (`xportra-ui-review.*`, `frontend/t5.txt`,
  `test-output.txt`, `.freebuff/`, `uv.lock`,
  CORS scratch test/task).
- Baselines stand (no code changed, no suite rerun
  for docs): backend 2039 passed + 61 subtests;
  frontend 64 files / 439 tests, `tsc` clean, build
  succeeds; integration gated (51 skipped).
- Task record:
  `tasks/completed/v1-deployment-preparation.md`.

## v1 Staging Deployment (Blocked, 2026-10-07)

- Staging cannot proceed: zero deployment credentials
  exist in the environment (`DATABASE_URL`,
  Supabase URL/JWT secret/service key, Qdrant,
  OpenRouter all absent). No migration, deployment, or
  UAT attempted; no production resources touched.
- Staging isolation spec + missing-prerequisite list +
  BLOCKED UAT table recorded in
  `docs/deployment/XPORTA-V1-STAGING.md`.
- Backend suite rerun for currency: 2039 passed +
  61 subtests. Frontend untouched (standing 64 files /
  439 tests).
- Result: **STAGING NOT VERIFIED — PRODUCTION
  BLOCKED.** Next action is operational: provision
  staging per the staging document, then re-run.
- Task record:
  `tasks/completed/v1-staging-deployment.md`.

## v1 Production Deployment (Blocked, 2026-10-07)

- Direct-production task stopped at the §1 credential
  gate: no production configuration exists (no
  Supabase URL/JWT secret/service key, no production
  database designation, no hosts/CORS/API-URL, no
  Qdrant/OpenRouter). Local `.env` is dev-subset only
  and was left unprobed. Nothing migrated, deployed,
  or smoke-tested; no data touched; all UAT NOT RUN.
- Baselines stand (docs-only outcome, no rerun):
  backend 2039 passed + 61 subtests; frontend 64 files
  / 439 tests; integration gated.
- Result: **PRODUCTION DEPLOYMENT BLOCKED** pending
  the prerequisites listed in the record.
- Task record:
  `tasks/completed/v1-production-deployment.md`.

## Production Database Migrated 002–013 (Live, 2026-10-07)

- Live migration executed against the Supabase
  production database via repo files only (psycopg
  equivalent of `psql ON_ERROR_STOP=1`, sequential,
  001 skipped): 002–013 all succeeded first-try, no
  errors, no repairs, nothing dropped or deleted.
- Pre-existing rows preserved untouched: 6 canonical
  authorities (001 seed), plus the `local-development`
  bootstrap tenant/user/owner-membership (active) —
  the brief's "empty" claim was inaccurate; recorded
  here instead of cleaned.
- Noted: `users.supabase_uid` already existed (002
  applied idempotently: column no-op, index ensured).
- Post-verified read-only: all 14 original + 14 newer
  tables present; 8 upload columns; composite PKs;
  shipment tenant FK; both `set_updated_at` triggers;
  new indexes; `draft|bound|locked` checks; no new
  rows created by migrations. No repo files changed,
  nothing committed (task rule).
- Task record:
  `tasks/completed/production-database-migration.md`
  (uncommitted).

## Production Deployment Readiness Audit — Render target (Complete, 2026-10-08)

- Read-only audit for the first hosted production deploy
  (staging skipped; Supabase production per brief taken
  as given, not redone). No code, dependency,
  architecture, or Supabase change; no deployment; no
  external calls; no secrets read or printed.
- Code-level verdict unchanged (no behavior defects);
  four wiring/operations blockers: B1 no `$PORT`/bind
  handling (start command must supply
  `--host 0.0.0.0 --port $PORT`); B2 no `/health`
  endpoint (interim: unauthenticated
  `GET /compliance/shipments` 401-probe); B3 default
  lifespan composition leaves RAG/analysis/uploads at
  503 (opt-in composers dead in production, no combined
  composer); B4 `SUPABASE_URL` needed for issuer
  verification. Hosted Qdrant required iff analysis/
  knowledge-chat/uploads in scope; core flows run
  without it. Single stateless web service sufficient
  (no workers/queues/sockets). Frontend needs only a
  `VITE_API_BASE_URL` rebuild (no code change).
- Verification: production-security 44 + 24 subtests;
  RAG composition 46; live OpenAPI/grep probes
  (33 paths, no `/health`; no `PORT`/`sslmode`
  handling; `APP_NAME`/`LOG_LEVEL` unread by code).
- Task record:
  `tasks/completed/production-deployment-readiness-audit-render.md`
  (uncommitted). Next: `render-production-wiring`
  (composition + `/health` + start command).

## render-production-wiring (Complete, 2026-10-08)

- Lifespan composes RAG/storage/index-sync through the existing
  Phase 5.14 / Phase 10.4 composers (new
  `from_environment_with_capabilities`; per-route 503s preserved;
  DB + JWT secret remain boot gates); dependency-free
  `GET /health` (`200 {"status": "ok"}`); SUPABASE_URL required
  in production (issuer pin); Qdrant background version probe
  disabled at composition (no startup connectivity); Render start
  command `uvicorn xportra.api.app:app --host 0.0.0.0 --port $PORT`
  and env contract documented; CORS unchanged. No deploy, no
  Qdrant, no Supabase change, no new dependency, no auth change.
- Verification: new 21/21; full `pytest tests` 2060 passed,
  51 skipped (gated, no DATABASE_URL/live services), 61 subtests,
  0 failures. No secrets committed or printed (placeholders only).
- Task record: `tasks/completed/render-production-wiring.md`
  (uncommitted). Next: hosted Qdrant iff RAG in v1 scope, then
  Render service configuration + §10 smoke.

## production-qdrant-provisioning (Complete, 2026-10-08)

- Repo-derived spec: cosine-only, 384-dim `all-MiniLM-L6-v2`
  baseline, collection auto-created at first ingestion (may be
  absent), no manual payload indexes, NO API-key wiring in current
  code (library supports it, app passes none), TLS via URL string.
- Recommended: Qdrant Cloud Free Tier (0.5 vCPU/1 GB/4 GB, no card;
  ample headroom) with documented caveat — Cloud mandates API-key
  auth, so either provision now + follow-on key-wiring task, or
  keyless self-host (not recommended). Provisioning ≠ ingestion:
  expected end state is reachable, correct, and EMPTY.
- Documented in `XPORTA-V1-DEPLOYMENT.md` §14 (spec + provider +
  six-step verification) plus §2/§3/§11 updates. Safe RAG suites:
  237 passed, 0 failures; no live calls, no secrets.
- Task record: `tasks/completed/production-qdrant-provisioning.md`
  (uncommitted). Next: user provisions via provider UI + records
  §14.5, then Render configuration + deploy + §10 smoke.

## qdrant-api-key-support (Complete, 2026-10-08)

- Optional `QDRANT_API_KEY` wired through one shared parsing path
  (`qdrant_api_key_from_environment`) to both `QdrantClient`
  constructions (RAG stack + upload index-sync); absent = exactly
  keyless behavior; never a boot gate; URL/collection fail-closed
  unchanged; key `repr=False`, never logged, never in errors.
  Required for Qdrant Cloud, optional otherwise. No architecture,
  collection, embedding, Supabase, or dependency change.
- Verification: new 13 tests + 2 subtests (mocks only); full
  `pytest tests` 2073 passed, 51 skipped (gated), 63 subtests,
  0 failures; no live services, no secrets (sentinel placeholders
  only).
- Task record: `tasks/completed/qdrant-api-key-support.md`
  (uncommitted). Next: user provisions cluster + records §14.5,
  then Render configuration + deploy + §10 smoke.

## production-wiring-release (Complete, 2026-10-08)

- Diagnosed Render `/health` 404: pushed `86f1aca` lacked
  `health.py`/registration (reproduced 404 from a pristine
  worktree; boot itself fast, no startup exception — timeout was
  the health-grace period expiring).
- Committed + pushed the coherent release with no implementation
  changes: commit `e7cb844`
  (`fix(deploy): include production runtime wiring`), 18 files,
  verified `main == origin/main`. Gates: targeted 145 passed;
  full suite 2077 passed, 51 skipped, 0 failures.
- Task record: `tasks/completed/production-wiring-release.md`
  (uncommitted). Next (operator): Render Clear build cache &
  deploy from `e7cb844`, then Qdrant §14.5 + §10 smoke.

## uvicorn-runtime-dependency (Complete, 2026-10-08)

- Root cause of Render `uvicorn: command not found`: git HEAD
  `pyproject.toml` declares no Uvicorn — the
  `uvicorn[standard]>=0.30,<1.0` line existed only uncommitted, so
  Render's committed-tree build installed FastAPI without the
  console script (local venv healthy: dist 0.54.0, script on PATH).
- Kept the existing range-pinned declaration (no duplication, no
  new mechanism); new `test_production_runtime_dependencies.py`
  pins declared + range-pinned + unique + console-script-exposed;
  §7 documents deploy-from-a-commit + clear-build-cache.
- Verification: new 4/4; full `pytest tests` 2077 passed,
  51 skipped (gated), 63 subtests, 0 failures.
- Task record: `tasks/completed/uvicorn-runtime-dependency.md`
  (uncommitted). Next (operator): commit + push, Render Clear
  build cache & deploy, then Qdrant §14.5 + deploy + §10 smoke.

## frontend-supabase-sign-in / Phase 10.10 (Implementation complete, not deployed, 2026-10-12)

- Replaced the manual bearer-token paste with Supabase
  email magic-link sign-in (R-10.10, ADR-0014) after the
  Phase 10.9 backend verifier passed production-token
  verification (HTTP 200): `@supabase/supabase-js`
  singleton (explicit PKCE, manual code exchange, no
  double-consume), session bootstrap/subscribe/refresh/
  sign-out in `AuthContext` (existing manual-state API
  preserved), reworked `/session`, new `/auth/callback`,
  `RequireAuth` on dashboard/shipments/workspace routes
  (settings/start/landing stay public), Supabase
  sign-out in shell + settings. `apiFetch` and backend
  untouched; dev-tenant header still backend-rejected
  in production.
- Verification: frontend suite 69 files / 471 tests
  passing (64 new, mocked Supabase client, zero
  network; no suite weakened); `tsc --noEmit` clean;
  `npm run build` succeeds. No secrets in code or
  bundle; no tenant/user/membership changes.
- Task record:
  `tasks/completed/frontend-supabase-sign-in.md`
  (uncommitted). Next (operator): Supabase dashboard
  redirect URLs (§8A, NOT verified), frontend rebuild
  with the three build variables, static redeploy
  (SPA fallback must cover `/auth/callback`), then
  end-to-end smoke. Production authentication is NOT
  claimed working until that smoke passes.

## Phase 4D.10 Security Remediation (2026-10-21)

Remediation completed for the existing global staff grant/audit foundation
(per security review findings):

- A. Bootstrap serialization: `pg_advisory_xact_lock` added in service;
  transaction-scoped advisory lock serializes bootstrap attempts across
  connections for `grant_manage`.
- B. Self-bootstrap prohibited: `_deny_self_managed` applied to bootstrap;
  integration test updated to use independent authorizer/operator users.
- C. Target account validation: `_require_active_user(target_user_id)` added
  to both `grant()` and `revoke()` operations.
- D. Audit authorization reference: approved contract does not specify a
  verifiable authorization mechanism; no fake authorization table or reference
  was fabricated. Blocked task file created at
  `tasks/blocked/bootstrap-authorization-policy.md` with product-owner
  decision request, recommended option, alternatives, trade-offs, and
  testable acceptance criteria.
- E. Real PostgreSQL rollback coverage: integration test added
  (`test_grant_rollback_when_audit_fails`) that injects a failing audit
  repository and verifies the grant mutation rolls back; not executed against
  production/shared database.
- F. Concurrency integration coverage: sequential and thread-based concurrency
  tests added (`test_concurrent_grant_revoke_serialized`); actual concurrent
  execution requires isolated test database.
- G. Database role verification: read-only query against configured
  `DATABASE_URL` confirms `postgres` role owns/protects `global_staff_grants`
  and `global_staff_audit`; audit immutability relies on trigger + role
  privileges rather than role-level UPDATE/DELETE restriction. No secrets
  exposed. Ordinary application role privileges remain unverified (no separate
  application role identified in current environment).

No administrative routes wired; `require_global_staff` remains unwired.
No production provisioning, deployment, commit, push, or migration applied.
Migration 015 remains unverified against production; `DATABASE_URL` points
  to Supabase (shared), not an isolated test database, so PostgreSQL
  integration tests were NOT executed.

## Task 12 — Hosted Qdrant Collection Restoration Preflight (Read-only, 2026-10-21)

**Verdict:** PASS WITH CONDITIONS — collection confirmed absent (expected end state per deployment spec); populated-restore blocked pending separately authorized ingestion path and approved source documents.

**Endpoint verification (masked, read-only):** Configured VECTOR_STORE_URL is a Qdrant Cloud HTTPS endpoint (us-west-2 AWS region, cluster ID starting 683-; masked here, host contains no credentials). GET root returned HTTP 200 with server version 1.19.2. GET /collections with the configured API key (sent only as the pi-key header, never displayed) returned HTTP 200 with an EMPTY list (collections=[]). Endpoint posture matches docs/deployment/XPORTA-V1-DEPLOYMENT.md §14.2 (Qdrant Cloud, API-key mandated). Cluster-intent match (that this exact cluster is the intended Xportra vector store) cannot be proven from the repository — the endpoint is operator-chosen and must be confirmed by the operator in the Qdrant Cloud console; this remains an open operator item.

**Collection state:** xportra-regulatory does not exist. Exact API result: GET /collections/xportra-regulatory returned HTTP 404 with body {"status":{"error":"Not found: Collection `xportra-regulatory` doesn't exist!"},"time":...} — the expected pass per §14.5 step 3 (absent = nothing ingested yet).

**Schema required by the existing implementation** (xportra/domain/vector_index.py, xportra/infrastructure/vector_index.py, xportra/infrastructure/rag_composition.py):
- Name: VECTOR_STORE_COLLECTION value — xportra-regulatory per local env; Render value to be recorded at configuration time, never in the repo.
- Vectors: single unnamed vector per point, size 384, distance Cosine (VectorIndexConfig default; ensure_collection creates or validates; alidate_qdrant_collection_config fails closed on dimension/distance mismatch and rejects named-vector layouts).
- Point ID: chunk_id (string UUID; deterministic uuid5 from document_id + content fingerprint).
- Required payload fields per point: tenant_id, chunk_id, document_id (string UUIDs); chunk_index (int); content; content_fingerprint; source_id; source_type (must be in SOURCE_TYPES); source_location (optional str); document_version (optional str); embedding_model (ll-MiniLM-L6-v2); embedding_dimensions (384). Upsert re-checks embedding model/dimension match, finite 384-dim float vectors; find/find_lexical re-check payload-model match.
- Payload indexes: NO manual payload indexes required (§14.3); the code provisions the content full-text payload index idempotently on first lexical use (WORD tokenizer, lowercase) and fails closed if an incompatible index exists.
- Pre-creation with 384/Cosine is allowed but optional; ensure_collection creates the missing collection on startup verification or first ingestion.

**Approved source documents available for indexing:** NONE. No raw regulatory source artifacts (PDF/TXT corpora) are stored in the repository. docs/phases/phase-4d-1-sesame-eu-pilot-source-research.md records verified source facts and an inventory (NEPC pages inaccessible, NAQS Plant Export Guidelines PDF unreadable, EU Official Journal texts for Regulations 2019/1793, 2025/1441, the two 2025 corrigenda, 2026/194, 2026/459, 2026/1206 verified as category-3 facts), but no Stage A-verified or Stage B-approved document exists, and the staff-upload regulatory ingestion path (Phase 4D.10 Tasks 3+) is unauthorized and unimplemented. Synthetic fixtures are explicitly NOT authoritative. Nothing may be indexed yet.

**Exact steps to restore and populate (separately authorized future work):** (1) Operator confirms the intended cluster in the Qdrant Cloud console (or provisions/notes the correct endpoint). (2) Set Render (and local, when needed) env: VECTOR_STORE_URL, VECTOR_STORE_COLLECTION=xportra-regulatory, QDRANT_API_KEY (secret), EMBEDDING_MODEL=all-MiniLM-L6-v2, EMBEDDING_DIMENSIONS=384 — note local .env EMBEDDING_DIMENSIONS and LLM_API_KEY/LLM_MODEL are currently empty, so local composition fails closed; no deployment exists to verify Render values. (3) Verify per §14.5 six-step non-destructive procedure (optionally pre-create the collection 384/Cosine, or let ensure_collection create it). (4) Populate only after the Phase 4D.10 staff ingestion path (source management, Stage A verification, Stage B approval) is implemented and authorized: upload → normalize → deterministic chunking → embed (all-MiniLM-L6-v2/384) → EvidenceIndexSyncService.sync → QdrantEvidenceVectorIndex.upsert under tenant context; content text index provisions automatically. (5) Record env values at configuration time, never in the repo.

**Unresolved risks / missing decisions:** cluster-intent confirmation (operator console check); empty local EMBEDDING_DIMENSIONS/LLM vars so 503 degradation persists locally; no approved source documents; global vs tenant-scoped identity for regulatory content in the vector index remains an unresolved contract question (upsert path currently requires tenant context while regulatory knowledge is operator-global per ADR-0017 planning direction); Qdrant Cloud free-tier suspension (~1 week)/deletion (~4 weeks) calendar risk applies to the empty cluster; all Phase 4D.10 authorization gates remain separate and ungranted.

**No changes performed:** read-only GET requests only, via a masked script in the pre-approved temp directory (outside the repo); no collection create/delete/reset/reindex/set payload/poke; local .env byte-identical (last write 2026-10-09, unchanged); no repository files modified by this task beyond this CURRENT_STATE.md entry; no staging, commit, push, deploy, or destructively destructive Git operations; all prior tracked modifications and untracked files preserved (git status pre-existing 46-file diff untouched).


## Phase 4D.10 Task 3 — Durable Regulatory Artifact Intake and Ingestion Jobs (2026-10-21)

**Verdict:** PASS WITH CONDITIONS — durable ingestion job contract implemented; authorization enforced; repository/migration/service/test files added; no hosted/prod/deployment changes made; unresolved operational prerequisites documented.

**What was implemented (confined to architecture-bound contracts):**
1. Migration 018 (`regulatory_ingestion_jobs.sql` / `.down.sql`): durable job/attempt table with lifecycle states (`pending`, `claimed`, `processing`, `completed`, `failed`, `retryable`), attempt numbering, timestamps, safe error details (no secrets), parser version, actor reference (`actor_user_id`), audit reference (`audit_ref`), and idempotency constraint `(artifact_id, attempt_number)`. No new payload indexes; no collection changes.
2. Repository (`xportra/persistence/repositories.py`): `RegulatoryIngestionJobRepository` with create/get/get_by_artifact_attempt/list_for_artifact/list_for_source/claim/complete/fail operations; atomic claim/completion/transition; fail-closed on repository errors.
3. Application service (`xportra/application/regulatory_ingestion_service.py`): `RegulatoryIngestionService` enforcing server-side `GlobalStaffGrantService.is_granted(actor_user_id, GRANT_MANAGE)` before any mutation (start/claim/complete/fail); never substitutes tenant membership; fails closed when grant missing/revoked. Audit linkage preserved through `audit_ref` field (linked to `global_staff_audit` mechanism from migration 017) and actor attribution (`actor_user_id`).
4. Focused tests (`tests/unit/test_regulatory_ingestion_service.py`): 5 passed — authorization denial (non-granted actor denied), authorization success path holds, lifecycle contract assertions (claim/complete/fail/retry methods exist; authorization enforced), retry/idempotency contract noted. Integration against PostgreSQL skipped when `DATABASE_URL` not configured.

**What was explicitly NOT implemented (documented blockers, per ADR-0017):**
- No background worker mechanism selected or deployed (ADR-0017 §3: worker/queue/dispatch mechanism remains unresolved under Render/no-Docker/budget constraints; repository audit `XPORTA-V1-DEPLOYMENT.md` §14 notes single long-lived web process, no Dockerfile, no existing worker).
- No PDF parser/library integrated (ADR-0017 §4: regulatory parser supports text/plain, Markdown, JSON; PDF support is a capability gate with unresolved parser choice; `pyproject.toml` does not declare PDF library; evidence-upload PDF path is separate and not reused here).
- No storage backend choice made for durable regulatory artifacts beyond the artifact reference (ADR-0017 §5: private storage/retention/deletion policy unresolved; `tenant-evidence` bucket is tenant-scoped evidence storage, not regulatory-source storage; no new bucket or retention duration created).
- No actual parsing/extraction/normalization workflow implemented (Task 3 scope is intake/job contract only; Stage A verification and Stage B approval are later tasks).
- No new authorization/grant/bootstrap created; `require_global_staff` dependency remains unwired to admin routes (Task 8 scope); `ACTIVE_TASK.md` records this remains deferred.

**Files changed (only for this task):**
- `migrations/018_regulatory_ingestion_jobs.sql` (new)
- `migrations/018_regulatory_ingestion_jobs.down.sql` (new)
- `xportra/persistence/repositories.py` (+ `RegulatoryIngestionJobRepository`)
- `xportra/application/regulatory_ingestion_service.py` (new)
- `tests/unit/test_regulatory_ingestion_service.py` (new; 5 passed; no regression against `test_global_staff.py` 14 passed; no fake tests; no skipped gated tests executed; live DB integration skipped per convention when `DATABASE_URL` absent)
- `ACTIVE_TASK.md` (updated active task line)
- `CURRENT_STATE.md` (this entry)

**No changes made:** `.env` unchanged; `.env` variables (`LLM_API_KEY` empty, `LLM_MODEL` empty, `VECTOR_STORE_COLLECTION` set, `VECTOR_STORE_URL` masked in previous preflight, `EMBEDDING_DIMENSIONS` empty — remains empty); no production Supabase/Qdrant data modified; no hosted Qdrant collection created/reset/reindexed; no authorization/grant/bootstrap created or consumed; no Render/deployment/commit/push; all prior tracked modifications (46 file diff) and untracked files preserved (`git status --porcelain` unchanged from pre-existing state except newly tracked files listed above; no staged/committed changes from this task).

**Next single task in approved Phase 4D.10 sequence (per ADR-0017 §11 / ADR-0017 planning gates):** Resolve the durable background-execution mechanism (Task 3 operational prerequisite — worker/queue/dispatch under Render/no-Docker/budget constraints) before any ingestion process can actually claim/persist/retry durable jobs; or proceed to Task 4/5 (artifact storage policy, PDF parser decision) if operational prerequisites are resolved separately by product-owner/authorized operator.

---

## Phase 4D.12 — Workstream B: Bootstrap and Runtime Security Foundation (2026-10-22)

**Verdict:** PASS WITH CONDITIONS — no application-level security defect remains; acceptance is conditional on authorized operational provisioning (dedicated DB role, operator-applied authorization record, live staff identity). No production access, no schema changes, no live grants.

**1. Runtime database role (verified from repository evidence only):**
- Runtime role = whatever credentials `DATABASE_URL` carries; the app resolves a single DSN via `DatabaseSettings.from_environment` (`xportra/persistence/database.py:22-31`). No separate role variable exists in the architecture schema.
- Repository evidence (`docs/deployment/bootstrap-authorization-db-role.md`): the live `.env` uses the `postgres` superuser (masked in docs; never read or printed by this task); the dedicated least-privilege role `xportra_app` is fully documented (required privileges, explicit exclusions, migration-role separation, operator verification SQL) but NOT provisioned anywhere. Migrations 001-028 create no DB role.
- NOT verified (requires authorized hosted inspection): actual privileges of the runtime role in the hosted database. Migration/app-role separation remains an operational prerequisite.

**2. Bootstrap authorization (verified in code + tests):**
- `GlobalStaffGrantService.bootstrap` (`xportra/application/global_staff.py:170-246`) fails closed: a missing/None `authorization_ref`, a revoked/expired/consumed authorization, or a mismatched target/permission raises before any grant. Authorization consumption is single-use and race-safe (`consume_in_transaction` updates `WHERE status='approved' AND consumed_at IS NULL`, `repositories.py:2234-2255`). Advisory lock serializes concurrent bootstrap attempts; idempotent re-run returns the existing grant; a pre-existing `grant_manage` holder for a different user raises `AlreadyBootstrappedError`. Actor and target must be active users; self-bootstrap of `grant_manage` denied. Grant + audit insert commit atomically (rollback if the audit insert fails); audit event records `authorization_ref` (append-only audit table, trigger-rejected mutations).
- `xportra/dev/bootstrap.py` (local development only) refuses `APP_ENV=production` before opening any connection; idempotent; refuses conflicting state; never prints credentials/DSN.
- Design gap-by-intent: no application path creates `global_staff_authorizations` rows; they are provisioned out-of-band by an authorized operator (documented prerequisite). Not a code defect.

**3. Staff permissions (GRANT_MANAGE, STAGE_A_VERIFY, STAGE_B_APPROVE):**
- Server-side enforcement wired: `require_global_staff` / `require_stage_a_verify` / `require_stage_b_approve` (`xportra/api/dependencies.py:649-767`) resolve the actor from the verified JWT -> `users.supabase_uid` -> `users.id`, then check the active grant server-side; fail closed on unauthenticated/unknown/inactive users and missing/revoked grants (and 503 when the database is unavailable). The dependencies are wired to 17 admin routes in `xportra/api/regulatory_admin.py` (11 grants, 3 Stage A, 3 Stage B). Tenant membership never substitutes a global grant (`xportra/api/authorization.py`).
- Grant/revoke restricted to `grant_manage` holders (`_require_actor_can_manage`); self-grant/self-revoke/self-bootstrap of `grant_manage` denied. Permissions remain distinct (`is_granted(user, permission)` checks the exact permission name against a 3-element frozenset). Revocation sets `status='revoked'` with `revoked_at`/`revoked_by`; `is_granted` filters `status='active'`, so revocation is effective for all subsequent protected operations. Historical grant periods live only in the append-only audit table.
- Confirmed defect fixed (test-only): two stale assertions in `tests/unit/test_global_staff.py` (`test_global_staff_permissions`, `test_invalid_permission_is_rejected`) held pre-migration-028 expectations that `stage_b_approve` is not a defined permission. Migration 028 explicitly approved `stage_b_approve` in the DB CHECK constraint and the service matched; only the test expectations were stale. Updated both assertions; no production code changed.
- NOT verified (requires authorized access): live staff identities/grants in the hosted database; no live grant, revocation, or bootstrap was created, altered, or inspected.

**4. Tests (exact commands, local xportra_test only):**
- DB identity verified before integration writes: `current_database=xportra_test current_user=postgres`.
- `.venv\Scripts\python.exe -m pytest tests/unit/test_global_staff.py tests/unit/test_dev_bootstrap.py -q` -> initially 2 failed / 32 passed; after the stale-assertion fix -> **34 passed**.
- `DATABASE_URL=postgresql://postgres:postgres@localhost:5432/xportra_test .venv\Scripts\python.exe -m pytest tests/integration/test_global_staff_postgresql.py -q` -> **16 passed** (grant/revoke/audit-atomicity, bootstrap idempotency/refusal/serialization, revoked/missing-grant denial).
- `.venv\Scripts\python.exe -m pytest tests/unit/test_phase_10_1_production_security.py -q` -> **44 passed** + 24 subtests (production auth/dev-header rejection, boot gates).
- `.venv\Scripts\python.exe -m pytest tests/unit/test_regulatory_ingestion_worker.py -q` -> **5 passed** (worker authorization fail-closed).
- Pre-existing unrelated failures: `tests/unit/test_regulatory_stage_a_review.py` / `test_regulatory_stage_b_review.py` dsn fixture failures (11 total) remain recorded from Phase 4D.11 — test-infrastructure configuration issue, not repaired here, not a security defect.

**5. Files changed (this task):**
- `tests/unit/test_global_staff.py` — corrected 2 stale permission-set assertions to match approved migration 028 (only change; application/service/migration code already correct).
- `tmp_verify_db_identity.py` — scratch verification script (untracked, local only).
- `ACTIVE_TASK.md`, `CURRENT_STATE.md` — this acceptance record.
- Everything else preserved: `.env` untouched, no production writes, no migrations applied, no git stage/commit/push/reset, no live grants/revocations.

**6. Outstanding operational prerequisites (requiring authorized action, per `docs/deployment/bootstrap-authorization-db-role.md`):**
1. Provision the dedicated `xportra_app` runtime role (or record an explicit product-owner justification for `postgres` as the application role), update `DATABASE_URL`, and verify privileges via `pg_roles`/`information_schema.table_privileges`.
2. Re-grant privileges on `xportra` objects created by future migrations.
3. Operator-applied `global_staff_authorizations` record (approved, unconsumed, target/permission-bound).
4. Authorized live staff identity, then bootstrap only through `GlobalStaffGrantService.bootstrap` with a valid `authorization_ref`.
5. Audit-event verification after live bootstrap (`global_staff_audit.authorization_ref` linkage).

**7. Workstream B decision:** PASS WITH CONDITIONS. The application security foundation (server-side permission checks, fail-closed bootstrap, atomic grant/audit, append-only audit, revoked-grant enforcement) is verified in code and tests. The smallest remaining acceptance step is authorized operational provisioning of the dedicated DB role + authorization record + live staff bootstrap (items 1, 3, 4 above) with the documented verification SQL. No Workstream C work was started.


---

## Phase 4D.13 — Workstream C: Regulatory Administration Interface (2026-10-22)

**Verdict:** PASS WITH CONDITIONS — the administration interface existed only as an authorized backend API; a UI did not exist at all. A minimal coherent slice was implemented reusing existing endpoints, components, and auth conventions, plus two additive read-only backend exposures (source list, governance-flag reads) that the required workflow demands but no endpoint supplied. No governance contract, schema, or state semantics were changed.

**1. Existing interface verified (UI-to-API trace, not endpoint-only):**
- Backend: 17 authorized routes in `xportra/api/regulatory_admin.py` (11 GRANT_MANAGE: sources register/get, supersession, artifacts upload/list, ingestion-jobs get/list, extract, manual candidate, candidates list/get; 3 STAGE_A_VERIFY: stage-a post/get/history; 3 STAGE_B_APPROVE: stage-b post/get/history) — all server-side enforced (Workstream B evidence).
- Frontend before this task: NO regulatory administration surface existed (no API client for `/regulatory/*`, no admin page, no route). Confirmed via full frontend tree inspection.
- Confirmed UI-blocking API gaps in the required workflow: (a) no source-list endpoint (sources fetchable only by UUID); (b) no governance-flag read endpoints (pending flags unreadable from any API path). Both were additive read-only exposures of existing services/repos.

**2. Workflow coverage as implemented:**
- Sources: list + detail with full provenance (authority, jurisdiction, version, status, effective/publication dates, source URL marked metadata-only, retrieval timestamp shown as "Unknown — not recorded" when absent), supersession links displayed verbatim as "as recorded" (never inferred).
- Ingestion jobs: list with recorded status/attempt/timestamps; failures remain visible with `error_details`.
- Candidates: list + detail showing requirement text/type, source location, status, extraction outcome, extracted/manual entry, artifact reference, reviewer attribution.
- Stage A and Stage B: separate forms, separate routes (`/stage-a` vs `/stage-b`), required rationale; decision histories displayed (append-only records reshown after each action); reviewer attribution displayed.
- Governance: source-level and requirement-level pending flags displayed with recorded rationale, `trigger_type`, and status verbatim; explicit notices that pending flags cannot be cleared from the view and completion follows governance rules only.
- Publication state: static notice that neither extraction nor Stage A/B decisions publish a requirement or make it exporter-applicable; no publication transition exists (none invented); no freshness/supersession inference.
- Retry: NO retry endpoint exists in the backend — none was invented. Failed jobs remain visible with failure details; re-attempt paths remain the existing safe operations only.

**3. Backend changes (additive, read-only for reads; smallest safe fixes only):**
- `xportra/persistence/repositories.py` — `RegulatorySourceRepository.list_all()` (read-only listing, ordered by created_at).
- `xportra/application/regulatory_source_intake_service.py` — `list_sources()` read method.
- `xportra/api/schemas.py` — `RegulatorySourceListResponse`, `RegulatoryGovernanceFlagResponse`, `RegulatoryGovernanceFlagListResponse` (fields mirror migration 029 columns exactly).
- `xportra/api/regulatory_admin.py` — governance service dependency + 3 routes: GET `/regulatory/sources`, GET `/regulatory/sources/{id}/governance-flags`, GET `/regulatory/requirements/{id}/governance-flags` — all GRANT_MANAGE-gated like the existing routes; flags shown for all statuses (pending AND resolved).
- Rationale: these were confirmed UI-blocking gaps in the REQUIRED workflow items "List regulatory sources" and "Display pending governance flags and their reasons" — additive read-only exposure of already-supported service capabilities; no state semantics or governance rules changed.

**4. Frontend changes:**
- `frontend/src/api/regulatory.ts` (new) — typed client for all covered routes via the central `apiFetch`; no raw fetch, no invented states.
- `frontend/src/features/regulatory/RegulationAdminPage.tsx` (new) — `/regulatory` administration page in existing visual conventions (StatusBits primitives, ledger pattern, honest loading/empty/error states); Stage A/B rationale validation messages rendered directly (role=alert), backend errors via `ErrorNotice` with `userFacingErrorMessage`.
- `frontend/src/App.tsx` — `/regulatory` route behind `RequireAuth` + `AuthenticatedShell` breadcrumbs. Sidebar untouched (ADR-0012 contract: exactly two primary nav destinations — reachable by direct URL; report: nav entry is a deliberate design-contract decision for the product owner).
- `ui permission checks`: the frontend deliberately does not fabricate a "can I administer" probe (no such endpoint exists); authorization failure surfaces as an explicit error state. The server remains the authority, as required.

**5. Tests:**
- Backend: `tests/unit/test_regulatory_governance_service.py` + `test_regulatory_source_intake.py` — 50 passed (incl. new: source read-only listing, verbatim pending+resolved flag reads; FakeReviewFlagRepo now generates unique flag ids — test-double fix, no production change).
- Frontend typecheck: `npm run lint` (tsc --noEmit) — clean.
- Frontend targeted: `npx vitest run src/api/regulatory.test.ts src/features/regulatory/RegulationAdminPage.test.tsx` — 18 passed (list/detail/provenance/failed-job/403-as-error/empty/distinct Stage A+B/pending-flag un-bypassable/no-publication copy/rationale-required/refresh-after-action).
- Frontend full: `npx vitest run` — **74 files, 557 tests passed**, no regressions.
- Backend full unit: `python -m pytest tests/unit -q` — **2265 passed / 13 failed**: 10 pre-existing Stage A `dsn` fixture failures (same `AttributeError: 'object' object has no attribute 'dsn'` at database.py:51 — test-infrastructure configuration only) + 2 pre-existing working-tree failures unrelated to this task (`test_rag_production_verification` domain `open(` audit finding in `xportra/domain/ingestion.py`, untouched here; `test_regulatory_ingestion_worker` start-stop — passes standalone, order-dependent suite flakiness) — none introduced by this task.

**6. Safety:** `.env` never read/printed; no production access; no migrations; no schema change; no git stage/commit/push/reset; no live grants; prior tracked/untracked work preserved; no scratch files deleted.

**7. Known limitations (evidenced):**
- Manual candidate entry and supersession recording remain API-only (existing endpoints; not added to the UI in this minimal slice).
- No ingestion retry operation exists server-side; failed work beyond idempotent artifact re-upload has no retry path (reported gap, not invented).
- No "who am I / my grants" endpoint exists, so the page cannot pre-gate rows by permission; unauthorized users see explicit denial errors (server-enforced).
- `xportra_app` runtime role provisioning and live-staff bootstrap remain Workstream B operational prerequisites.

**8. Workstream C decision:** Accepted with conditions above; smallest remaining UI step: add source/jobs navigation polish + review determinations on real data after authorized staff identity exists. No Workstream D started.

\n## Phase 4D.15 Workstream E Verification (2026-10-22)\nVerdict PASS WITH CONDITIONS. No new defects; 364 focused tests passed; known failures documented (stage A fixture, ingestion audit, order-dependency, 029 provenance unverified); no code/test/file changes; no live smoke/deployment; xportra_app DB role remains prerequisite; Workstream F deferred.

---

## Phase 4D — Hosted Migration Execution + Initial Operator Authorization Verification (2026-10-24)

**Verdict:** BLOCKED (fail-closed). Hosted migration execution PASSED and was independently verified. Initial operator authorization and bootstrap were NOT executed: required operational prerequisites remain unestablished, and creating the authorization record now would fabricate evidence linkage and actor attribution. No `global_staff_authorizations` row, no `global_staff_grants` row, and no `global_staff_audit` row was created; zero writes were made to authorization state.

**1. Hosted migration execution (completed, verified):**
- Applied 12 pending migrations in order against the live database: 016, 017, 019, 020, 021, 022, 023, 024, 025, 026, 027, 028 — all succeeded (runner exit 0).
- Already applied before this session (verified via migration-state inspection): 015, 018.
- Excluded by design: **029** — provenance UNVERIFIED (ADR-0019 / ADR-0020 reconstruction note); NOT applied; `regulatory_review_flags` table confirmed absent.
- Independent post-execution verification (read-only, repeated): PostgreSQL 17.6; schema `xportra` = 36 tables; `regulatory_requirements` = 27 columns; `global_staff_grants.permission` CHECK = exactly `grant_manage`, `stage_a_verify`, `stage_b_approve`; `global_staff_audit.authorization_ref` present (migration 017); audit immutability triggers intact; core row counts unchanged (users 2, tenants 2, shipments 2, compliance_workflows 2, authorities 6); authorization tables all 0 rows.

**2. Identity resolution (read-only, masked; no identifiers recorded):**
- The documented initial-operator identity matched exactly 1 active `xportra.users` row carrying `supabase_uid`. Independent `auth.users` cross-check: 1 confirmed account, `auth_uid == users.supabase_uid` TRUE, exactly 1 users row keyed by that uid → mapping chain (`supabase_uid` → `users.id`) verified end-to-end; active `owner` tenant membership.
- Second live user row: the `local-developer@xportra.local` development seed identity created by `xportra/dev/bootstrap.py`, active, without `supabase_uid` → development seed, not a person; cannot authenticate.

**3. Prerequisite assessment (`tasks/blocked/bootstrap-authorization-policy.md` §7/§8 + evidence procedure + db-role doc + authorization template):**
Satisfied for the minimal release: approved single-operator exception with recorded justification (scope `grant_manage`); self-bootstrap denial preserved; provisional 24-month audit retention approved (finalization required only before broadening); grant/revocation authority and audit-storage contract implemented and verified (atomic grant+audit, append-only trigger, single-use authorization consumption).

BLOCKERS — all must be resolved by the product owner / authorized operator before any authorization record is created or bootstrap executed:
1. **Evidence store and verification channel not established** — organization-controlled evidence store location/access mechanism unspecified; trusted out-of-band verification method (specific channel) unspecified; `authorization_ref` not generated. Evidence-procedure status: "proposed but NOT configured; must be established before any authorization record is created."
2. **Database connection identity not finalized** — `xportra_app` not provisioned (role absent, verified); no documented `postgres` justification. Newly recorded live properties: `current_user=postgres`, `rolsuper=false` but `rolcreaterole=rolcreatedb=rolbypassrls=rolreplication=true`, member of `supabase_privileged_role`, `service_role`, `pg_read_all_data` (privileged identity; documentation wording "superuser" is imprecise for hosted Supabase; explicit risk acknowledgment/decision still required per policy §7/§8).
3. **Exception authority only partially defined** — authorization template records "not fully defined by design"; manual-recovery exception rules and exception-audit procedure undefined; Stage A/B same-person exception approved for planning only.
4. **No legitimate distinct bootstrap actor/verifier identity** — `GlobalStaffGrantService.bootstrap` denies `actor == target` (`_deny_self_managed`, `xportra/application/global_staff.py:190`); `authorizer_user_id`/`verifier_user_id` FKs require real active user rows; only 2 active users exist (target + development seed) → executing now would require false attribution, which is prohibited.
5. (Partial) Second-operator provision: deferral and minimal-release mitigation documented; future-broadening provision plan not stated (policy §8).

**4. Verification performed (this task):**
- Read-only identity/role/state inspection scripts in the pre-approved temp directory (DSN loaded programmatically from `.env` inside the scripts; never printed; no `.env` content in any output).
- Focused unit tests: `.venv\Scripts\python.exe -m pytest tests/unit/test_global_staff.py tests/unit/test_dev_bootstrap.py -q` → **34 passed**.
- Bootstrap contract re-verified in code (`xportra/application/global_staff.py:170-246`): fail-closed on missing/mismatched/non-approved authorization, single-use atomic consumption, advisory-lock serialization, atomic grant+audit, `authorization_ref` retained in the audit event; no application path creates authorization rows (out-of-band provisioning by design).

**5. Safety:** no `.env` output; no DB writes; no migration re-run; no authorization record; no grant; no role/privilege change; no git stage/commit/push/reset; migration 029 still untracked and not applied; all prior tracked and untracked work preserved.

**6. Next required actions (operational, outside agent authority):** establish the evidence store and specify the verification channel → finalize DB connection identity (provision `xportra_app` per `docs/deployment/bootstrap-authorization-db-role.md` OR document an explicit privileged-role justification using the live properties recorded above) → fully define exception authority (incl. manual recovery) → provision/identify a second legitimate active user for actor/verifier attribution → generate `authorization_ref`, insert the approved authorization record out-of-band, execute `GlobalStaffGrantService.bootstrap` with actor ≠ target, then verify audit-linkage (`global_staff_audit.authorization_ref`) and the documented bootstrap acceptance checks.\n

---

## Account Identity Display (frontend + backend, implemented and verified)

**Verdict:** PASS. Authenticated users can now see who is signed in and which organization they are working under, consistently across the shared authenticated layout (`AuthenticatedShell`) — dashboard, shipments, settings, and all `AuthenticatedShell`-framed pages.

**Sources of each identity field:**
- **Person's display name:** `xportra.users.display_name` (provisioned at organization registration via `OrganizationRegistrationService`, from `contact_name` falling back to the organization name). Never fabricated from an email.
- **Authenticated email:** `xportra.users.email` (authoritative application record), falling back to the Supabase JWT `email` claim only when the DB email is absent.
- **Organization/company name:** `xportra.tenants.legal_name` resolved through the authenticated user's active `user_tenant_memberships` membership (tenant `status='active'`, membership `status='active'`). Never inferred from email domain; never hardcoded; no arbitrary organization selected when the user has multiple active memberships (organization is `null` until an explicit tenant selection is made).

**Backend changes:**
- `xportra/persistence/repositories.py` — `UserTenantMembershipRepository.list_active_for_user` now also returns `tenants.legal_name AS tenant_legal_name` (read-only, no schema change).
- `xportra/api/schemas.py` — new `IdentityResponse` (user_id, display_name, email, organization_id, organization_name, role).
- `xportra/api/identity.py` (new) — `GET /me`, authenticated only, resolves the user exclusively from the verified Supabase JWT subject (`users.supabase_uid` → `users.id`), returns only identity fields, enforces tenant isolation (memberships scoped to the authenticated user; no cross-tenant data; no arbitrary org selection).
- `xportra/api/app.py` — wires `identity_router`.
- Tests: `tests/unit/test_identity_api.py` (9 tests pass).

**Frontend changes:**
- `frontend/src/types/api.ts` — `Identity` type.
- `frontend/src/api/identity.ts` (new) — `fetchIdentity` over `/me`.
- `frontend/src/app/IdentityContext.tsx` (new) — `IdentityProvider` / `useIdentity`; loading/error/idle states; clears on sign out so no stale identity is shown for a different account.
- `frontend/src/App.tsx` — mounts `IdentityProvider` inside `AuthProvider`.
- `frontend/src/shell/AuthenticatedShell.tsx` — active organization name in the sidebar brand header ("Organization unavailable" when none); account menu shows name, email, organization, Settings, and Sign out (existing `useSignOut`), with loading/error/empty states; keyboard accessible, works desktop + mobile.
- `frontend/src/shell/shell.css` — token-styled identity display with ellipsis for long names/emails.
- Tests: updated `AuthenticatedShell.test.tsx` (24 pass); full frontend suite `npx vitest run` — 570 passed / 1 failed (pre-existing RegisterPage timing flake, unrelated to identity — RegisterPage is a public route that never touches identity or `AuthenticatedShell`); `tsc --noEmit` clean; `npm run build` succeeds (existing large-chunk advisory only).

**Tenant isolation:** preserved. Identity is resolved server-side from the trusted JWT subject; only the authenticated user's active memberships are returned; no request-supplied user/tenant id is accepted as proof of access; no RLS or authorization was weakened; no migration added.

**Safety:** no `.env` read/printed; no production writes; no secrets exposed; no git push; unrelated tracked/untracked work preserved.

---

## Initial Global Staff Grant Bootstrap Provisioning (implemented and verified locally)

**Verdict:** PASS WITH CONDITIONS. The operator-facing provisioning path for the initial `grant_manage` global staff grant is implemented and verified locally against `xportra_test` using the dedicated `xportra_app` runtime role. Production bootstrap remains blocked until prerequisites are resolved (see below).

**What was implemented:**

- `xportra/dev/global_staff_bootstrap.py` (new) — operator-facing CLI for invoking `GlobalStaffGrantService.bootstrap()` locally. Follows the existing `xportra/dev/bootstrap.py` pattern: refuses `APP_ENV=production`, requires explicit `--authorization-ref`, `--target-user-id`, `--actor-user-id`, `--justification`, never hardcodes identities, prints only identifiers/status (no secrets), and does not bypass the application service.
- `tests/integration/test_global_staff_bootstrap_postgresql.py` (new) — 7 focused integration tests run as `xportra_app` against local `xportra_test`:
  1. Bootstrap consumes authorization, creates grant + audit with `authorization_ref` linkage
  2. Invalid authorization ref rejected (fail closed)
  3. Mismatched target rejected
  4. Already-consumed authorization rejected (single-use consumption)
  5. Self-bootstrap denied (`actor == target`)
  6. Audit insert failure rolls back grant mutation (atomic transaction)
  7. Inactive target rejected

**Test results (all local `xportra_test`, no production):**

- `tests/unit/test_global_staff.py`: **14 passed** (unit, no database)
- `tests/integration/test_global_staff_bootstrap_postgresql.py`: **7 passed** (as `xportra_app` role)

**How the approved form maps to the authorization schema:**

| Form field | Schema column | Source |
|---|---|---|
| Approval reference | `authorization_ref` | `XPA-GSA-INIT-001` (approved form value) |
| Target user | `target_user_id` | Verified `xportra.users.id` from identity mapping |
| Permission | `permission` | `grant_manage` (only defined permission) |
| Authorizer | `authorizer_user_id` | Independent product owner's `xportra.users.id` |
| Verifier | `verifier_user_id` | Independent verifier's `xportra.users.id` |
| Justification | `justification` | Documented reason from approved form |
| Status | `status` | `approved` (set by authorizer, consumed by bootstrap) |

**How validation, consumption, and atomicity are preserved:**

- `bootstrap()` verifies the authorization reference exists, matches target/permission/scope, has `status='approved'`, and is not consumed — before any state change.
- `consume_in_transaction()` atomically sets `status='consumed'`, `consumed_at`, `consumed_by` within the same transaction as grant creation.
- `insert_in_transaction()` for grants and audit runs in the same transaction; audit failure rolls back everything.
- Advisory lock (`pg_advisory_xact_lock`) serializes concurrent bootstrap attempts.
- Self-bootstrap denied (`_deny_self_managed`).
- No direct table inserts — all mutations through `GlobalStaffGrantService.bootstrap`.

**Production steps remaining (operator-only, not performed in this task):**

1. Resolve evidence retention mechanism and trusted verification channel (prerequisite 1).
2. Resolve database role decision: configure `xportra_app` with least-privilege grants OR document explicit justification for `postgres` (prerequisite 2).
3. Define exception authority (prerequisite 3).
4. Finalize retention/deletion policy (prerequisite 4).
5. Provision second operator / grant-manager plan (prerequisite 5).
6. Independent authorizer inserts authorization record (`global_staff_authorizations`, `status='approved'`, `authorization_ref='XPA-GSA-INIT-001'`) with verified target/actor/verifier IDs.
7. Independent operator executes `GlobalStaffGrantService.bootstrap()` against production with `actor ≠ target`.
8. Verify audit linkage (`global_staff_audit.authorization_ref = 'XPA-GSA-INIT-001'`).

**Safety:** no production writes; no authorization record created or consumed; no grant created or revoked; no `.env` secrets read/printed; no migrations applied; no production DATABASE_URL changed; no push/deploy.

---

## Initial Global Staff Bootstrap — Production-Readiness Review (2026-10-28)

**Verdict:** READY WITH CONDITIONS. Narrow review of commit `3819589`
(bootstrap CLI, service, integration tests, deployment doc, migrations
015–017) against the approved authorization `XPA-GSA-INIT-001`
(permission `grant_manage`). The owner has confirmed the authorization
form was approved and verified; the production authorization record and
grant still do not exist and were not created by this review.

**Confirmed findings (code/docs verified):**
- `GlobalStaffGrantService.bootstrap` (`xportra/application/global_staff.py:170-246`)
  correctly enforces: active actor and target users; actor ≠ target
  (self-bootstrap denied); authorization ref must exist, match
  target/permission, and be `approved`; single-use consumption
  (`status='consumed'`, `consumed_at`, `consumed_by`) inside the same
  transaction as grant insert and audit insert (rollback on any failure);
  advisory-lock serialization; audit event retains `authorization_ref`
  (migration 017). Covered by 7/7 passing integration tests
  (`tests/integration/test_global_staff_bootstrap_postgresql.py`).
- Authorization schema (migration 016) contains every required field
  (`target_user_id`, `permission`, `authorizer_user_id`,
  `verifier_user_id`, `authorization_ref`, `status`) plus
  `verification_method`/`justification` NOT NULL; the deployment doc's
  prerequisite list matches the schema.
- **Gap fixed this task:** the CLI refused `APP_ENV=production`
  outright, and the deployment doc showed a production command that the
  CLI would deterministically reject while defining no alternative
  procedure — no safe production execution path existed. The CLI now
  accepts a narrowly scoped `--production-confirmation` that must
  exactly equal `--authorization-ref` when `APP_ENV=production`
  (checked before any DB connection; exit 2 otherwise). All service
  checks unchanged; not a general escalation mechanism (still requires
  an approved, unconsumed, out-of-band authorization record).
- **Known observations (not blockers):** (a) `authorization_ref`
  uniqueness is not DB-enforced (no unique index on the ref column);
  operator must run the read-only uniqueness check now documented in
  `docs/deployment/bootstrap-authorization-db-role.md` before inserting.
  (b) The service never evaluates the optional `expires_at` column
  despite its error message mentioning expiry — do not set `expires_at`
  on the initial record; enforcement is open follow-up. (c) The older
  `tests/integration/test_global_staff_postgresql.py` suite requires
  table-owner privileges (`ALTER TABLE ... DISABLE TRIGGER`) and errors
  when run as `xportra_app` — pre-existing, unrelated to the CLI.
- Database-role doc accurately describes the `xportra_app`
  least-privilege design and minimum production steps; production role
  configuration remains unchanged.

**Verification this task:** unit
`tests/unit/test_global_staff_bootstrap_cli.py` (new, 11 tests) +
`tests/unit/test_global_staff.py` + `tests/unit/test_dev_bootstrap.py`
→ **44 passed**; integration
`tests/integration/test_global_staff_bootstrap_postgresql.py` → **7
passed** against local `xportra_test` as `xportra_app`. No production
contact; no authorization/grant/audit row created or consumed; no
migrations; no `.env` read or exposed; no secrets in docs.

**Remaining operator prerequisites before executing the approved
bootstrap** (unchanged operational items, now with a defined production
invocation): establish evidence store + verification channel; finalize
DB connection identity (`xportra_app` or documented privileged-role
justification); define exception authority; provision/identify the
distinct actor/verifier user rows required by the authorization schema
and actor ≠ target rule; insert the approved authorization record
out-of-band; then run the documented production command with
`--production-confirmation XPA-GSA-INIT-001`; verify the three
read-only acceptance queries in the deployment doc.

---

## Production Bootstrap Configuration Readiness — xportra_app + TLS (2026-10-28)

**Verdict:** READY WITH CONDITIONS (documentation + test hardening only;
no functional code changed; nothing committed; no production contact).

Context: the production Supabase connection was successfully tested from
Windows as `xportra_app` with SSL certificate verification (temporary
test script deleted; CA certificate stored at `cert/prod-ca-2021.crt`,
gitignored via an operator `.gitignore` change preserved uncommitted).

**Confirmed how configuration works:** the CLI and the whole application
read configuration from the process environment only —
`DatabaseSettings.from_environment` reads exactly one key,
`DATABASE_URL` (`xportra/persistence/database.py:22-31`); the CLI passes
`os.environ` (`xportra/dev/global_staff_bootstrap.py` `main()`); no
dotenv loading exists anywhere in `xportra/` and `python-dotenv` is not
a dependency. A local `.env` is inert until exported into the process
environment. The DSN is passed verbatim to libpq via psycopg 3.3.6, so
TLS is fully configured in the DSN itself: `?sslmode=verify-full` plus
`sslrootcert=<path>` (URL-encoded) or the standard libpq
`PGSSLROOTCERT` variable — no CLI flags or code changes required.
`verify-full` is the only mode verifying both certificate chain and
hostname.

**Changes made (uncommitted, this task):**
- `docs/deployment/bootstrap-authorization-db-role.md` — new
  "Configuration and TLS" section (process-environment-only semantics;
  SSL via DSN/`PGSSLROOTCERT`; hostname verification via
  `sslmode=verify-full`) and a rewritten Execution section: dedicated
  gitignored `.env.production-operator` file (`APP_ENV=production`,
  production DSN with `sslmode=verify-full`, `PGSSLROOTCERT`), loaded
  into the PowerShell session only via a non-echoing regex loader —
  DSN never appears in command history, argv, logs, or chat; explicit
  warning against inline `DATABASE_URL=... python ...` and against
  loading a shared dev `.env` without re-asserting production values.
  The `--production-confirmation` exact-match safeguard is unchanged.
  Corrected (same day) to the verified Supabase Shared Pooler pattern:
  project-qualified username `xportra_app.waugynqpuwsazehsjyvj`
  (qualification must never be stripped), host
  `aws-0-eu-west-2.pooler.supabase.com:5432/postgres`,
  `sslmode=verify-full`, password as a `<pooler-password>` placeholder
  only (never real, never on a command line; URI-encoding note), and
  Windows absolute-path guidance for `cert/prod-ca-2021.crt`.
- `xportra/dev/global_staff_bootstrap.py` — docstring only: documents
  process-environment-only configuration and DSN-based TLS. No
  functional change.
- `tests/unit/test_global_staff_bootstrap_cli.py` — 2 new unit tests:
  SSL parameters in `DATABASE_URL` reach the connection factory
  verbatim (capturing factory, scripted routes, no real connection);
  output contains no DSN/SSL/role material.
- `CURRENT_STATE.md` / `ACTIVE_TASK.md` — state updates.

**Verification this task:** unit 46 passed (44 baseline + 2 new);
integration `tests/integration/test_global_staff_bootstrap_postgresql.py`
7/7 passed against local `xportra_test` as `xportra_app`
(command-scoped DSN). No production connection; no CLI execution
against any database as a real bootstrap; no authorization/grant/audit
row created or consumed; no migrations; no `.env` read; no secrets in
docs or chat; nothing staged or committed; the operator `.gitignore`
change and all pre-existing untracked files preserved.

**Remaining operator prerequisites** are unchanged from the entry above
(evidence store, DB-role decision now satisfied for connectivity but
still requiring the documented justification/retention items, exception
authority, distinct actor/verifier identities, out-of-band authorization
insert, then the documented session-loaded execution and the three
read-only acceptance queries).

## Production Bootstrap Operator Loader Validation (2026-10-28)

**Verdict:** VALIDATED WITH ONE NARROW DOC CORRECTION (documentation
only; no code changed; nothing staged or committed; dummy values only,
no production contact).

The documented PowerShell session loader in
`docs/deployment/bootstrap-authorization-db-role.md` was executed
against a dummy `.env.production-operator` fixture (temp directory;
fake password; dummy CA file) and measured against seven checks:
(1) all three variables (`APP_ENV`, `DATABASE_URL`, `PGSSLROOTCERT`)
load into the current process — PASS; (2) the loader emits zero output,
no values/credentials echoed — PASS; (3) a Windows cert path with
spaces is preserved byte-exact and resolves — PASS; (4) pre-existing
stale `APP_ENV`/`DATABASE_URL` values **silently survived a partial
load** with the previous loader — GAP CONFIRMED; (5) missing/malformed
config now fails safely — PASS after correction; (6) the CLI
`--production-confirmation` exact-match safeguard is untouched (unit
suite includes the mismatched-refusal tests) — PASS; (7) no production,
Supabase, Render, or network side effects (dummy fixture, no CLI run
against any database) — PASS.

**Correction made (uncommitted, this task):** the loader block was
hardened in place — (a) pre-load clear of the three managed variables
so stale development values cannot survive a partial load, (b) missing
operator file throws before anything else, (c) a post-load verification
step prints PASS/FAIL per check (check names only, never values) and
throws before the CLI runs unless: `APP_ENV=production`, `DATABASE_URL`
set/unquoted, pooler host + `/postgres` database matched, `sslmode=
verify-full` present, CA named `prod-ca-2021.crt` and file exists.
Prose updated to match; the `--production-confirmation` safeguard text
is unchanged.

**Verification this task:** corrected loader harness 18/18 checks
passed (full load, partial load, missing file, quoted value + bash
`export` line all fail safely; no secret fragments in any output);
prior loader harness confirmed the gap it was meant to prove; unit 46
passed; integration 7/7 passed (local `xportra_test`, command-scoped
DSN). Nothing staged or committed; all pre-existing uncommitted changes
and untracked files preserved.

## Regulatory Administration Backend — Milestone 1 (2026-10-29)

**Verdict:** IMPLEMENTED AND VERIFIED (unit tests only; integration
tests require an isolated `xportra_test` database and were not run
against the configured shared `DATABASE_URL`).

Implemented the staff-only regulatory ingestion administration API,
building on the existing Phase 4D.10 foundation (migrations 018–029,
source intake/candidate extraction/ingestion services, worker,
`global_staff_grants` + `global_staff_audit`). No new migration was
required — the existing schema already supports the requirement.

### Endpoints (all staff-only, `GRANT_MANAGE` via `require_global_staff`)

- `POST /regulatory/sources/{source_id}/artifacts` — staff-uploaded
  artifact; accepts `text/plain`, `text/markdown`, `application/json`,
  `application/pdf` (PDF previously rejected at the application layer;
  domain parsing already supported it). Validates content type, 10 MB
  size, base64 content; stores original bytes in the private regulatory
  source-artifact storage; persists artifact row + durable pending
  ingestion job. Idempotent on identical content hash. Returns
  artifact + job; no storage credentials or paths exposed.
- `POST /regulatory/sources/{source_id}/artifacts/text` — staff-entered
  inline text; accepts `text/plain`, `text/markdown` (no file upload).
  Same storage, artifact, job, and idempotency guarantees.
- `POST /regulatory/sources` — source registration (existing).
- `GET /regulatory/sources` (paginated), `GET /regulatory/sources/{source_id}`,
  `GET /regulatory/ingestion-jobs/{job_id}`,
  `GET /regulatory/sources/{source_id}/ingestion-jobs` (paginated) —
  processing status, safe error information, metadata; no secret leakage.
- `POST /regulatory/ingestion-jobs/{job_id}/extract`,
  `GET /regulatory/sources/{source_id}/candidates`,
  `GET /regulatory/candidates/{candidate_id}` — extraction outcomes with
  provenance (`ingestion_job_id`, `artifact_id`, `source_id`,
  `normalized_document_id`).

### Authorization and audit

- `GRANT_MANAGE` required for all mutating and read-only regulatory-admin
  routes; actor resolved from verified JWT subject → `users.id`;
  tenant membership never substitutes; fail-closed on missing/invalid
  identity or grant.
- Audit through existing `GlobalStaffAuditRepository` /
  `global_staff_audit` mechanism.
- No hard-coded staff user, no automatic grants, no bypass.

### Files changed

- `xportra/application/regulatory_source_intake_service.py` — accept
  `application/pdf`; shared `_store_artifact`; new `enter_text_artifact`.
- `xportra/api/schemas.py` — `RegulatoryTextEntryRequest`,
  `RegulatoryArtifactTextResponse`.
- `xportra/api/regulatory_admin.py` — `POST
  /regulatory/sources/{source_id}/artifacts/text` route; upload docstring.
- `tests/unit/test_regulatory_source_intake.py` — PDF acceptance +
  10 staff-text tests.

### Tests

- Focused: 44/44 pass (`test_regulatory_source_intake.py`).
- Regulatory + API regression: 192 passed.
- Full unit suite: 2325 passed; 3 pre-existing failures unrelated to
  this change (RAG domain IO audit, RAG cross-tenant matrix, worker
  event-loop flake — all pass in isolation or are untouched).
- Integration tests skipped (no isolated `xportra_test` database;
  not run against shared `DATABASE_URL`).

### Limitations

- Bootstrap (`XPA-GSA-INIT-001`) production grant state cannot be
  verified from this environment (no `DATABASE_URL`, no production
  contact). The local test database has no `grant_manage` rows
  (expected). Per tasking, bootstrap is NOT re-executed and no
  production grants are created or revoked.
- Stage A/B review, publication eligibility, and exporter-facing
  behavior exist in code but are gated behind separate grants and are
  not part of this milestone.
- No artifact deletion endpoint (blocked by retention policy; deliberate).

### Next recommended milestone

Phase 4D task 3/4 — durable ingestion pipeline execution (worker
dispatch, parsing/extraction wiring) and Stage A/B review API wiring,
pending separate authorization.


## Regulatory Ingestion Execution Path — Milestone 2 (2026-10-29)

**Verdict:** IMPLEMENTED AND VERIFIED (unit tests only; integration
tests require an isolated `xportra_test` database and were not run
against the configured shared `DATABASE_URL`).

Made the durable ingestion pipeline work end to end: a pending
ingestion job is now discovered and claimed by the worker, driven
through parse → normalize → extract → persist, and marked completed or
failed/retryable with safe error information. Previously the worker
claimed jobs and marked them completed without running extraction.

### What already worked (Milestone 1 foundation)

- Source registration, artifact upload (PDF + text), staff-entered text,
  durable pending job creation, content-hash idempotency.
- Candidate extraction service with full provenance
  (`source_id`, `artifact_id`, `ingestion_job_id`, `normalized_document_id`).
- Job lifecycle: pending → claimed → completed/failed/retryable.
- Worker startup/shutdown integrated into FastAPI lifespan.

### Actual gaps discovered

1. **Worker auto-completed jobs without extraction** — `_poll_cycle`
   marked every pending/retryable job `completed` without calling the
   extraction pipeline, so candidates were never produced automatically.
2. **`claim_job` only accepted `status='pending'`** — `retryable` jobs
   (set by `_mark_job_failed` after parse/extract failure) could never
   be reclaimed, so retries were dead-ended.
3. **No race-condition guard on `claim_job`** — if `claim_job` returned
   `None` (another worker already claimed), `extract_candidates` still
   called `complete_job`, potentially completing another worker's job.

### Code and schema changes

- `xportra/application/regulatory_ingestion_worker.py` — `_poll_cycle`
  reserves a job via `SELECT ... FOR UPDATE SKIP LOCKED` (no status
  change), then `_process_job` delegates to
  `RegulatoryCandidateExtractionService.extract_candidates()`, which
  performs the atomic claim and drives the job to completion or failure.
  Jobs without `artifact_id` (source-registration placeholders) are
  skipped. Extraction failures are logged; the job is not falsely
  completed. `extraction_service` and `job_repo` constructor injection
  added for testability. Removed unused `signal` import.
- `xportra/persistence/repositories.py` —
  `RegulatoryIngestionJobRepository.claim` now matches
  `status IN ('pending', 'retryable')` so failed jobs can be retried.
- `xportra/application/regulatory_candidate_extraction_service.py` —
  `extract_candidates` checks `claim_job` return value; `None` (already
  claimed) returns `duplicate=True` as an idempotent no-op.
- No migration added — existing 018–029 schema suffices; the `claim`
  change is data-access only.

### Verified ingestion lifecycle

1. Staff uploads/enters artifact → `POST /regulatory/sources/{id}/artifacts`
   (or `/artifacts/text`) → artifact stored in private regulatory
   source-artifact storage → durable pending job created.
2. Worker polls `regulatory_ingestion_jobs`, claims pending/retryable job
   atomically (`pending`/`retryable` → `claimed`).
3. Worker calls `extract_candidates` → reads original artifact bytes from
   private storage (no credentials exposed) → parses (PDF/text/JSON)
   within 10 MB limit → normalizes → extracts candidates → persists
   candidates with provenance → claims + completes job (`completed`).
4. On parse/extract failure → job marked `retryable` (or `failed`), safe
   error recorded, no candidates, no false completion.
5. Retry: `retryable` job is reclaimed by `claim` and re-processed.
6. Candidates remain unreviewed; no automatic publication.

### Authorization and audit

- Worker requires `REGULATORY_WORKER_ACTOR_USER_ID` with an active
  `GRANT_MANAGE` grant; fail-closed otherwise (worker skips execution).
- `extract_candidates` requires `GRANT_MANAGE` via
  `GlobalStaffGrantService`.
- Read-only and mutating regulatory-admin routes require `GRANT_MANAGE`.
- No hard-coded staff user, no automatic grants, no bypass.
- No production grant created or revoked.

### Tests

- Focused worker tests: 12/12 pass (new).
- Source intake + candidate extraction + ingestion service: 81 passed.
- Full unit suite: 2332 passed; 3 failed.
- The 3 failures are pre-existing and unrelated to this change:
  1. `test_domain_has_no_io_or_network_surface` — false positive:
     `xportra/domain/ingestion.py` uses `fitz.open()` (PyMuPDF), which
     the test's text scan flags as `"open("`. Not Python's `open()`.
  2. `test_cross_tenant_result_rejected` — RAG test expects 502, gets 200.
     Pre-existing, not touched by this change.
  3. `test_start_stop_contract_exists` — event-loop flake; passes in
     isolation (5/5), fails intermittently in full-suite parallel context.
- Integration tests skipped (no isolated `xportra_test` database;
  not run against shared `DATABASE_URL`).

### Bootstrap discrepancy (Phase 4)

- Task context states bootstrap was completed under `XPA-GSA-INIT-001`.
- Repository documentation (CURRENT_STATE.md §Bootstrap Readiness Review)
  states the production authorization record and grant "still do not
  exist and were not created by this review" — remaining operator
  prerequisites are listed.
- Resolution: the local test database has no grants (expected), and
  production grant state cannot be verified from this environment (no
  `DATABASE_URL`, no production contact). Per tasking, bootstrap is NOT
  re-executed and no production grants are created or revoked.
- Documented as unresolved verification rather than guessed.

### Next recommended milestone

Stage A/B review API wiring and publication-eligibility exposure,
pending separate authorization. The ingestion pipeline now runs
end-to-end through the worker.


