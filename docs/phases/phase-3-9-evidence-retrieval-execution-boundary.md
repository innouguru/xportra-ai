# Phase 3.9 — Evidence Retrieval Execution Boundary

**Status:** Complete and verified (2026-09-22)
**Phase:** Phase 3 — Applicability Engine
**Type:** Domain execution-seam boundary — no retrieval backend

> This record describes what was actually implemented and verified.

## Objective

Establish the execution seam: Retrieval Request → Executor Boundary →
Result Contract. Define how retrieval will be executed and represented
without coupling the domain to any retrieval technology.

## Contracts

`EvidenceRetrievalExecutor` (Protocol) in `xportra/domain/ingestion.py`:
`execute(request, *, tenant_id) -> dict`. Domain depends on the
contract; future vector/keyword/hybrid/PostgreSQL/Qdrant/web/API
backends satisfy it. `EvidenceRetrievalResultBuilder.build_result()`
wraps validated requests + evidence metadata into results carrying
`tenant_id, evidence_requirement_id, requirement_id, gap_kind, query,
reason, priority, status, retrieval_scope, retrieval_executed,
result_count, results[], result_status, empty_result_meaning,
result_not_verdict`. Result items carry metadata only: `source_id,
title, content, source_type, location, relevance`. NoOp executor
validates then returns `retrieval_executed=False, results=[],
result_count=0` without fabricating evidence.

## Validation, identity, determinism

Fail-closed `validate_request()` on malformed identity/gap/query/
priority/status/scope/tenant via `ComplianceSummaryValidationError`.
Identity propagates unchanged for traceability; no UUID4/timestamps.
Deterministic identical output; executor-order results.

## Retrieval vs compliance

Request = what to find; result = what executor returned; compliance =
out of scope. Empty means executor returned nothing, not
inapplicable/non-compliant/non-existent. No verdict fields.

## Non-goals / tests / verification

No Qdrant/vectors/embeddings/chunking/reranking/search/web/crawling/
APIs/LLM/RAG/ingestion/persistence/caching/agents/UI. Tests:
`tests/unit/test_evidence_retrieval_executor.py` — 20 tests. Focused
20/20; full suite 287/287 (267 baseline + 20). Integration not run.
