# CURRENT_STATE.md — Current Project State

> Source of truth for what is true about Xportra AI right now.
> Updated: 2026-09-24
> Phase: Phase 8 — API & Application Integration
> (Phase 8.5 complete; Phase 8.4 complete; Phase 8.3 complete;
> Phase 8.2 complete; Phase 8.1 complete; Phase 7 COMPLETE;
> Phase 6 COMPLETE; Phase 5 COMPLETE)

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