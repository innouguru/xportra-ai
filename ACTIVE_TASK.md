# ACTIVE_TASK.md — Current Active Task

## Task: Phase 3.5 — Compliance Decision Summary

**Phase:** Phase 3 — Applicability Engine
**Status:** Complete (2026-09-22) — `ComplianceDecisionSummaryService` condenses the existing Applicability → Risk → Action outputs into a single deterministic, tenant-scoped decision summary, with 16 focused tests and 202/202 total unit tests passing

## Objective

Create the next minimal deterministic domain boundary that converts the existing
Applicability → Risk → Action outputs into a single structured Compliance
Decision Summary suitable for consumption by future application/API layers —
an orchestration/representation boundary only.

## Integration Path
Applicability (Phase 3.1) → Risk (Phase 3.3) → Action (Phase 3.0) → Summary (Phase 3.5)

## What Was Implemented

- `ComplianceDecisionSummaryService` with two methods:
  - `summarize()` — joins existing compliance cases with the existing risk and
    action outputs
  - `summarize_from_applicability()` — runs the existing Phase 3.3/3.4
    pipeline over an applicability report and summarizes its output
- Delegation to existing `ComplianceRiskService` and
  `RiskToActionIntegration`/`ComplianceActionRecommendationService` — no
  business rule duplicated
- Explicit unknown-state index (`applicability_unknown`, `assessment_unknown`,
  `missing_evidence`, `risk_unknown`) — descriptive labels only, never decisions
- Tenant identity validated and preserved throughout the summary
- Deterministic ordering of every section
- No persistence, external calls, LLM, RAG, or retrieval

## Constraints

- No chunking, vector database, embeddings, reranking, LLM reasoning, or
  retrieval work.
- No compliance scoring or decision support beyond existing services.
- No frontend or UI work.
- No generalized crawling or arbitrary web ingestion.
- No weakening of authentication, tenant isolation, or authorization
  boundaries.
- Existing applicability, risk, and action services remain the source of truth.
- No new risk levels or action types.
- Unknown states are never silently converted to known states.
- Preserve tenant isolation.
- Output must be deterministic.
- In-memory/read-service layer; no persistence.
- Avoid unrelated refactoring.

## Acceptance Criteria

- [x] Decision-summary boundary implemented without duplicating business rules
- [x] Applicability, risk, and action semantics remain owned by existing services
- [x] No new risk levels or action types introduced
- [x] Unknown/insufficient states preserved explicitly (no silent conversion)
- [x] Tenant identity preserved throughout the summary
- [x] Deterministic output guaranteed
- [x] Focused unit tests covering Phase 3.5 pass (16/16)
- [x] Full unit regression remains green (202/202 = 186 + 16)
- [x] `docs/phases/phase-3-5-compliance-decision-summary.md`, `ACTIVE_TASK.md`,
      and `CURRENT_STATE.md` updated

## Completion

Complete. Phase 3.5 implemented and verified. Phase 3.6 has not started.
