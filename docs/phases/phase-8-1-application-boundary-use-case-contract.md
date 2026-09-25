# Phase 8.1 — Application Boundary & Use-Case Contract

**Status:** Complete and verified (2026-09-24)
**Phase:** Phase 8 — API & Application Integration
**Type:** Application-layer contract over the completed
domain; no endpoints, no UI, no verdict

> This record describes what was actually implemented and verified.

## Objective

Make the future boundary testable and real:

```text
UI → FastAPI API → application use cases → existing domain
```

`xportra/application/` (new; the directory existed empty,
so no convention was displaced) orchestrates the
completed domain services and translates results into
allow-listed DTOs. It cannot become a second
compliance/workflow engine: transitions, applicability,
assessments, reasoning, retrieval, readiness, and closure
all stay owned by the domain services it calls.

## Application-layer responsibility

User-facing use cases, orchestration in the correct
sequence, trusted tenant propagation, and domain-result
translation. Nothing else.

## Use-case inventory (12 items → 4 services)

- `WorkflowApplicationService` (`workflows.py`): start
  (begin + 7.2 bind), provide information, mark evidence
  pending, record applicability, submit for review,
  supply evidence (7.2 handoff), request additional
  evidence, readiness check, finalize, workflow/history/
  package reads, closure query.
- `AnalysisApplicationService` (`analysis.py`):
  run/re-run analysis (the state machine distinguishes
  passes, not this layer) plus report reads. RAG service
  injected (production wiring in
  `xportra/infrastructure/`); budget/mode/top-K as
  validated primitives.
- `AssessmentApplicationService` (`assessments.py`):
  applicability determination over caller-supplied
  requirement records and shipment facts; case
  evidence-coverage reads. Unknown/missing pass through
  untouched.
- `EvidenceApplicationService` (`evidence.py`): artifact
  recording/reads over the injected persistence-backed
  evidence service (identity DTOs only, never contents).

## Domain/application boundary

Application calls domain; never the reverse. Domain
failures propagate categorized with detail and cause
preserved. No domain file modified; no domain behavior
changed.

## API/application boundary

API owns HTTP, token verification, membership
resolution, per-endpoint `authorize()`, parsing, and
serialization. It builds `ApplicationContext` from
server-resolved membership
(`actor=identity.subject`, `tenant=member.tenant`,
`role=member.role`) and passes it as the first use-case
argument. Use cases declare the flow; the API enforces
permissions with the unchanged Phase 1 policy.

## Tenant/auth context

`ApplicationContext` (frozen: actor, effective tenant,
role). Tenant is propagated, never trusted: record
tenants are compared against the context tenant before
any domain call; supply references are built from
context tenant plus workflow case. Role is carried
informationally; enforcement stays in the API layer.

## DTO/read-model strategy

Frozen allow-listed DTOs built from domain records
(plus live in-session result/package objects where the
domain holds no record form). Preserved: workflow
state/closure, shipment/evidence/requirement/report/
trace/history/package identities, counts, findings with
carried Phase 6 provenance, uncertainty/contradiction/
missing information, and the Phase 3.5 summary carried
by reference in the final package DTO only. Excluded:
fingerprints, prompts, model identifiers, raw provider
output, secrets, and database internals. Nested Phase 6
provenance sections are selected, never remodeled.

## Error taxonomy (HTTP-free)

Authentication/authorization (API-raised, propagated
untouched), tenant mismatch (deterministic comparison),
invalid input, not-found, invalid transition (domain
detail + cause), not-ready with structured reasons,
stale analysis (code-based subcategory), terminal
workflow (explicit 7.5 predicate pre-check),
infrastructure (sanitized one-line detail). No message
parsing anywhere; no HTTP codes (API mapping is later
Phase 8 work).

## Persistence/I-O boundary

No new persistence and no repository abstractions: no
workflow store exists, so use cases are stateless
(record-in/record-out) with live result/package objects
traveling in-session. Callers supply requirement/case
records from the regulatory store; evidence recording
uses the injected existing service. A future Phase 8
store can persist records without contract change —
explicitly deferred, not designed here.

## Explicit non-responsibilities

Transitions, applicability/assessment/risk/reasoning/
retrieval/readiness/closure logic; verdicts and scores;
authorization policy; persistence; HTTP; UI.

## Frontend consumption

UI calls HTTP endpoints; endpoints authorize, build the
context, invoke one use case, and serialize the
returned DTO/record. The UI never sees domain objects,
fingerprints, prompts, or provider internals.

## Verification

- Focused Phase 8.1: 31/31
  (`test_application_boundary.py` — context; HTTP
  independence via AST scan; tenant propagation incl.
  zero-cost rejection; domain authority incl.
  structured reasons/stale/terminal; DTO privacy incl.
  no-verdict and translator rejection; full journey +
  rerun + determinism + statelessness; evidence fake
  incl. not-found/cross-tenant; assessments incl.
  unknown preservation; error taxonomy incl.
  sanitization).
- Phase 7.1–7.5 (151) + Phase 6 (247) + Phase 2–5
  regressions pass unmodified. Full suite: 1618 passed
  + 37 skipped (gated), 0 failures. No live execution
  claimed.

## Deliberately outside Phase 8.1

Endpoints, HTTP mappings, UI, persistence/stores,
provider wiring, evaluation, production hardening.

## Files created / modified

- Created: `xportra/application/{__init__,context,errors,
  dtos,workflows,analysis,assessments,evidence}.py`
  (33 exports), `tests/unit/test_application_boundary.py`,
  `docs/phases/phase-8-1-application-boundary-use-case-contract.md`.
- Modified: none outside `xportra/application/` (no
  domain, API, persistence, or infrastructure file
  touched); no prior test touched.
