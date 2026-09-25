# Phase 8.2 — HTTP Endpoint Exposure

**Status:** Complete and verified (2026-09-24)
**Phase:** Phase 8 — API & Application Integration
**Type:** Thin FastAPI adapter over 8.1 use cases; no
domain logic in routes, no verdict

> This record describes what was actually implemented and verified.

## Objective

Expose the stateless-safe 8.1 use cases through stable
FastAPI routes, preserving the adapter shape:

```text
HTTP request → auth → authorize → ApplicationContext
→ exactly one use case → DTO serialization → response
```

## Endpoint inventory (13)

Workflow (`/compliance/workflows/`): `start` (201),
`provide-information`, `note-evidence-pending`,
`record-applicability`, `submit-for-review`,
`request-additional-evidence`, `supply-evidence`,
`status`, `history` (without live result), `is-closed`,
`analyze` (run and re-run — the state machine routes
passes). Assessments (`/compliance/assessments/`):
`applicability`, `case-readiness`. Evidence recording
stays on the existing `/compliance-evidence` routes —
no second recording endpoint was created.

## Route → application mapping

Each handler builds `ApplicationContext` from the
authorized `MemberContext`, validates request shape
only, invokes one use-case method, and returns its
DTO/record. App services are constructed per request
(pure defaults; RAG resolved through the existing
unwired-503 dependency; evidence service from the
container). No container surgery was needed.

## Authentication/authorization flow

Unchanged Phase 1 boundary: dev header or Bearer token
→ `MemberContext` → per-endpoint `require_permission`.
Two additive owner-only permissions
(`PROGRESS_COMPLIANCE_WORKFLOW`, `RUN_COMPLIANCE_ANALYSIS`);
existing rules untouched; reads reuse
`READ_TENANT_RESOURCE`; evidence recording keeps its
Phase 1 permission. The resolver drops the raw subject,
so routes pass `actor_id=None` (documented; threading
the subject is deferred work).

## Tenant isolation

Effective tenant comes only from membership. Record
tenants are re-checked in the application boundary
(403 `tenant_mismatch`); server-looked-up evidence
stays 404-non-leaking via the existing route.

## Request/response schemas

`schemas.py` (additive): record-carrying requests
(workflow records travel in-body — no server session,
no globals) and response models mirroring the DTO
contracts, including a fingerprint-free round shape
for client summaries.

## Error/status mapping

Centralized by exception type (never message parsing),
reusing the existing `{"error": {"code", "message",
"details"?}}` shape: 401 auth, 403
denied/tenant-mismatch, 400 app input, 404 not-found,
409 transition/not-ready (reasons in details)/
stale/terminal, 422 HTTP-shape validation, 503
infrastructure (sanitized) and unwired-RAG, 500
unexpected. No traces, credentials, provider errors,
prompts, or internals leak.

## OpenAPI contract

Auto-generated schema lists all 13 paths with
operation names and request/response models (locked
by test) — the stable frontend contract.

## Intentionally unexposed capabilities

`finalize_package`, readiness-with-result,
result/package-attached history, package/report reads:
live Phase 6 result objects cannot cross HTTP, and
this layer invents neither a transfer encoding nor a
store. Evidence `get` via the app layer is redundant
with the existing route. Compound analyze-and-finalize
was rejected — it would skip the human review the
journey requires. No debug/RAG-passthrough/state-
mutating endpoints exist.

## Persistence limitations (reported gap)

No workflow/result store exists, so multi-request
sequences spanning analysis → finalization cannot
complete over HTTP yet. Per the task rule this is
reported, not worked around: no session globals, no
fake persistence, no client round-trip of result
internals. Recommended Phase 8.3: a workflow/result
transfer-or-store contract, plus subject threading.

## Wire translation found at integration

HTTP JSON carries UUIDs as strings while the domain
requires UUID objects. The application layer now
coerces documented identity fields in case views
(including provenance) and summary tenant IDs —
mechanical translation, no facts invented; unparseable
shapes still fail in the domain with its own errors.
(8.1 in-session behavior unchanged.)

## Verification

- Focused Phase 8.2: 29/29
  (`test_compliance_api.py` — auth incl. dev behavior;
  owner/member authorization; tenant isolation incl.
  body-tenant rejection; journey, invalid-transition,
  malformed-body, closure query; supply incl. empty-list
  rejection; analysis incl. delegation, wrong-state,
  unwired-503, provider-503, no-verdict; assessments;
  terminal mapping via genuinely finalized records;
  privacy scans; route-boundary AST scan; OpenAPI
  path lock).
- Phase 8.1 (31) + 7.1–7.5 (151) + Phase 6 (247) +
  Phase 2–5 regressions pass unmodified. Full suite:
  1647 passed + 37 skipped (gated), 0 failures. No live
  execution claimed.

## Deliberately outside Phase 8.2

Finalize/package/report endpoints (blocked, see gap),
UI, persistence/stores, provider wiring, evaluation,
production hardening.

## Files created / modified

- Created: `xportra/api/compliance.py`,
  `tests/unit/test_compliance_api.py`,
  `docs/phases/phase-8-2-http-endpoint-exposure.md`.
- Modified (additive/minimal): `xportra/api/authorization.py`
  (2 permissions), `xportra/api/errors.py` (app-error
  mapping), `xportra/api/schemas.py` (compliance models),
  `xportra/api/app.py` (router include),
  `xportra/application/_guards.py` +
  `analysis.py` + `assessments.py` (wire UUID coercion —
  in-session behavior unchanged).
- No Phase 1–7 behavior change; no prior test touched.
