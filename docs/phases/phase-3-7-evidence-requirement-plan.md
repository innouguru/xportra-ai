# Phase 3.7 — Evidence Requirement / Retrieval Contract Boundary

**Status:** Complete and verified (2026-09-22)
**Phase:** Phase 3 — Applicability Engine
**Type:** Domain representation / retrieval-contract boundary — no new compliance rules

> This record describes what was actually implemented and verified in Phase 3.7.

## Objective

Build a small deterministic domain boundary that converts the existing
compliance case readiness/evidence gaps (Phase 3.6) into a structured
**Evidence Requirement Plan** — the contract a future retrieval/RAG layer
would consume:

```text
Applicability -> Risk -> Action -> Summary -> Readiness -> Evidence Plan
```

The service answers "what evidence do we need to obtain or verify?" and
never obtains it. No retrieval, search, crawling, embeddings, vector work,
RAG, LLM reasoning, external calls, or persistence.


## Abstraction

`EvidenceRequirementPlanService` in `xportra/domain/ingestion.py`, entry
point `plan(readiness_report, *, tenant_id)`. It consumes the Phase 3.6
`readiness_report` (gaps, requirement views, actions requiring evidence)
and emits one evidence requirement per gap. It never re-runs applicability,
risk, action, or readiness rules.

## Input / output

Input: `readiness_report` with `status == "readiness_report"`,
`tenant_id`, `context_fingerprint`, `readiness_state`, `gaps`,
`requirements`, `actions_requiring_evidence`. Output:

```text
tenant_id, context_fingerprint, status ("evidence_requirement_plan"),
readiness_state, required_count, items[], retrieval_boundary,
plan_not_verdict
```

Each item: `tenant_id`, `requirement_id`, `evidence_requirement_id`,
`gap_kind`, `requirement` (requirement text), `reason`, `priority`,
`status` ("required"), `triggering_action` (existing action type or None).
Traceable to the causing compliance requirement via `requirement_id`.

## Identity, mapping, priority, status

Identity: `"<requirement_id>:<gap_kind>"` — deterministic, stable, unique
(no randomness, timestamps, generated IDs, secret hashes). Mapping: one
item per readiness gap, kinds `applicability_unknown`,
`assessment_unknown`, `missing_evidence`, `risk_unknown` preserved without
meaning change. Priority: existing `risk_state` preserved when `high`,
`medium`, or `low`; neutral `unknown` otherwise — no ranking invented;
existing evidence action preserved as `triggering_action`. Status: only
`required` items emitted; ready case yields empty `items`; nothing
fabricated. Unknown states stay distinct; plan asserts neither compliance
nor non-compliance. Ordering `(requirement_id, gap_kind,
evidence_requirement_id)`; tenant UUID required and cross-tenant rejected.

## No duplicated logic / retrieval boundary

Reuses existing gap kinds, reasons, requirement views, risk states, and
action signals read from the readiness report. No retrieval, search,
embeddings, reranking, chunking, RAG, LLM, crawling, connectors, APIs,
ingestion changes, persistence, UI, agents, or verdicts.

## Tests

`tests/unit/test_evidence_requirement_plan.py` — 20 tests: ready-empty,
each gap kind, multi-gap, IDs, ordering, determinism, tenant
preserve/reject, no inference, kind/ID/action preserved, empty input, no
verdict, readiness unchanged, summary unchanged, end-to-end.

## Verification

Focused 20/20; full suite 242/242 (222 baseline + 20). Integration tests
not run (`DATABASE_URL` unconfigured).

## Deferred

API, UI, persistence, connectors, ingestion changes, crawling,
embeddings, vectors, retrieval, reranking, RAG, LLM, agents, verdicts.
