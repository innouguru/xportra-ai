# ACTIVE_TASK.md — Current Active Task

## Task: Phase 3.6 — Compliance Case Readiness / Evidence Coverage Boundary

**Phase:** Phase 3 — Applicability Engine
**Status:** Complete (2026-09-22) — `ComplianceCaseReadinessService` reports whether each case carries sufficient known information for the existing decision pipeline, exposing evidence/readiness gaps explicitly, with 20 focused tests and 222/222 total unit tests passing

## Objective

Build a small deterministic domain boundary that evaluates whether a compliance
case has sufficient known information to support the existing Applicability →
Risk → Action decision pipeline. The purpose is to expose evidence/readiness
gaps explicitly so that future retrieval/RAG phases can target those gaps.
This is a domain representation/readiness boundary only — no retrieval, web
search, RAG, LLM reasoning, embeddings, vector search, crawling, or external
API calls.

## Integration Path
Applicability (Phase 3.1) → Risk (Phase 3.3) → Action (Phase 3.0) → Summary (Phase 3.5) → Readiness (Phase 3.6)

## What Was Implemented

- `ComplianceCaseReadinessService` with a single `assess(cases, *, tenant_id)`
  entry point producing a deterministic readiness report
- Reuse of the existing services as sources of truth: case validation and
  missing-evidence semantics from `ComplianceRiskService`, risk states from
  `ComplianceRiskService.classify()`, actions from
  `RiskToActionIntegration.recommend_from_risk()`
- Minimal readiness state model: `ready`, `partially_ready`, `not_ready`
- Explicit evidence-gap kinds reusing the Phase 3.5 vocabulary:
  `applicability_unknown`, `assessment_unknown`, `missing_evidence`,
  `risk_unknown`, plus `evidence_required_action` for actions that require
  additional evidence
- Information dimensions: applicability (all requirements); assessment,
  evidence, and risk (applicable requirements) — unknown applicability means
  assessment/evidence/risk cannot be judged
- Tenant identity validated (required UUID) and preserved in the report
- Deterministic ordering of requirements, gaps, and sections by stable
  requirement identifier
- No persistence, external calls, LLM, RAG, retrieval, embeddings, or vector
  work; readiness is explicitly not a compliance verdict

## Constraints

- No chunking, vector database, embeddings, reranking, LLM reasoning, or
  retrieval work.
- No compliance scoring or verdicts; readiness is not compliance.
- No frontend or UI work.
- No generalized crawling or arbitrary web ingestion.
- No weakening of authentication, tenant isolation, or authorization
  boundaries.
- Existing applicability, risk, action, and summary services remain the source
  of truth; no applicability, risk, or action rule is re-implemented.
- `not_applicable`, `unknown`, and `missing evidence` are never conflated.
- Unknown states are never silently converted to known states.
- Preserve tenant isolation.
- Output must be deterministic.
- In-memory/read-service layer; no persistence.
- Avoid unrelated refactoring.

## Acceptance Criteria

- [x] Readiness boundary implemented without duplicating business rules
- [x] Applicability, risk, action, and summary semantics remain owned by
      existing services
- [x] Minimal state model: ready / partially_ready / not_ready only
- [x] Evidence gaps explicit (applicability, assessment, evidence, risk)
- [x] `not_applicable`, `unknown`, and `missing evidence` kept distinct
- [x] No compliance verdict introduced; a ready case may still be high risk
- [x] Tenant identity preserved throughout the report
- [x] Deterministic output guaranteed
- [x] Focused unit tests covering Phase 3.6 pass (20/20)
- [x] Full unit regression remains green (222/222 = 202 + 20)
- [x] `docs/phases/phase-3-6-compliance-case-readiness.md`, `ACTIVE_TASK.md`,
      and `CURRENT_STATE.md` updated

## Completion

Complete. Phase 3.6 implemented and verified. Phase 3.7 has not started.
