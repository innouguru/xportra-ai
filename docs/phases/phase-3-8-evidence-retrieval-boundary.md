# Phase 3.8 — Evidence Retrieval Boundary

**Status:** Complete and verified (2026-09-22)
**Phase:** Phase 3 — Applicability Engine
**Type:** Domain representation / retrieval-request boundary — no retrieval

> This record describes what was actually implemented and verified.

## Objective

Define the structured contract a future retrieval/RAG implementation
receives: Evidence Requirement Plan → Evidence Retrieval Request. Answer
"what exactly should the retrieval layer be asked to find?" without
executing retrieval.

## Service

`EvidenceRetrievalRequestService` in `xportra/domain/ingestion.py`,
entry `build(plan, *, tenant_id)`. Consumes Phase 3.7 plan items only.

## Input / output

Input: plan with `status == "evidence_requirement_plan"`, `tenant_id`,
`context_fingerprint`, `readiness_state`, `items[]`. Output:
`tenant_id, context_fingerprint, status ("evidence_retrieval_request"),
readiness_state, request_count, requests[], retrieval_not_executed,
request_not_verdict`. Each request: `tenant_id,
evidence_requirement_id, requirement_id, gap_kind, query, reason,
priority, status, retrieval_scope`.

## Identity, query, gaps, priority, scope

Identity reuses `evidence_requirement_id` (no UUID4/timestamps/secrets).
Query = stripped requirement text, else deterministic
`"<gap_kind> evidence for requirement <id>"`; no exporter/authority/date
invention. Gaps preserved exactly; no reinterpretation. Priority/status
preserved exactly; ready plan yields zero requests. Scope fixed
`requirement_evidence` (extension point). Ordering by (requirement ID,
gap kind, evidence requirement ID). Tenant UUID required; cross-tenant
rejected via `ComplianceSummaryValidationError`.

## Malformed input is rejected, not skipped

`build()` is fail-closed: any malformed plan item raises
`ComplianceSummaryValidationError` instead of producing a partial
request set. Rejected: non-dict items; items missing `requirement_id`,
`evidence_requirement_id`, or `gap_kind`; non-string or unknown
`gap_kind`; `evidence_requirement_id` values that are not strings or
that do not equal `"<requirement_id>:<gap_kind>"`; per-item tenant
values that do not match the plan tenant.

## Non-goals

No vectors, embeddings, chunking, reranking, search, web, crawling, LLM,
RAG, APIs, connectors, ingestion, persistence, caching, agents, UI, or
compliance/risk/action decisions.

## Tests

`tests/unit/test_evidence_retrieval_request.py` — 25 tests covering the
required contract, five malformed-input rejections, plus Phase 3.7
unchanged.

## Verification

Focused 25/25; full suite 267/267 (242 baseline + 25). Integration tests
not run (`DATABASE_URL` unconfigured).
