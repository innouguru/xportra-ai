# Phase 6.3 — Structured Compliance Reasoning Generation Boundary

**Status:** Complete and verified (2026-09-24)
**Phase:** Phase 6 — Compliance Reasoning & Decision Support
**Type:** Production-safe seam between deterministic facts and
LLM-generated explanatory content — strict section protocol,
allow-list output validation, minimal 6.1 adaptation; no second
LLM system, no verdict engine, no API

> This record describes what was actually implemented and verified.

## Architecture check outcome

Phase 5 provides LLM invocation (`LLMClient`), generation
configuration, citation-aware prompts, citation/integrity
validation, and provider-failure propagation — but NO
structured-output/JSON contract (free text + citation regex
only). All of it is reused unchanged. The only new capability
is the 6.3 section parser and its allow-list validation — a
new check, not a parallel system. No missing contract blocked
the work.

## Trust boundary

**Deterministic structured state → trusted.** Requirement and
case identity, applicability, assessment, evidence/source
identity and provenance, tenant identity, decision state.

**LLM-generated explanation → untrusted until validated.**

**Validated explanation → usable only** as verbatim
`explanation`, `model observation:`-prefixed missing items,
and a carried uncertainty statement. The deterministic
`uncertainty` category, every state, and every reference stay
authoritative.

Single-call flow: the reasoning query travels as the RAG
information need, so EvidencePrompt keeps system/need/evidence
structurally separate. Per-call system override is unsupported
by the RAG contract, so all reasoning instructions travel
inside the labeled need — documented, not a limitation
workaround.

## Contracts (`xportra/domain/reasoning_generation.py`, new)

- `ReasoningGenerationError(DomainValidationError)` — never
  converted into content.
- `ReasoningPromptContext` + `reasoning_prompt_context_from_case`
  (facts only: no tenant/case identity, no retrieved content).
- `ReasoningQuery` + `ReasoningQueryBuilder` — deterministic
  AUTHORITATIVE FACTS / untrusted-DATA notice / explain-only
  TASK / exact FORMAT sections.
- `ReasoningValidationContext` +
  `reasoning_validation_context_from_case_and_answer` —
  UUID allow-list (requirement/tenant/case/evidence/chunk/doc
  + UUIDs quoted from the requirement text itself),
  citation-label allow-list from the authoritative mapping.
- `StructuredReasoning` (explanation, suggested missing,
  optional categorical uncertainty + statement, answer
  fingerprint binding, cited labels).
- `StructuredReasoningParser` — strict protocol: legacy
  plain-text mode preserves exact 6.1 semantics (backward
  compatible); structured mode enforces fixed order, required
  non-empty explanation, `- `-only missing items, exact-token
  uncertainty (numerics rejected), mapping-only citations,
  allow-listed UUIDs, no duplicate/stray/header-shaped
  sections. Empty output stays the valid empty state.
- `StructuredReasoningService.analyze_with_reasoning` —
  query → injected RAG service → parse → existing
  `analyze(reasoning=...)`; failures propagate unchanged.

Machine-actionable smuggling (identifiers, citations,
verdict/state headers) is rejected; inert prose is neutralized
by construction (analysis fields never derive from text).

## Phase 6.1 minimal adaptation

`ComplianceAnalysis` gains `uncertainty_explanation: str = ""`
(default preserves all existing constructions);
`analyze(..., reasoning=None)` defaults to exact 6.1 behavior
and otherwise binds fingerprints, prefixes model items, and
carries the uncertainty statement. All 35 existing 6.1 tests
and every 6.2 construction pass unmodified.

## Verification

- Focused Phase 6.3: 37/37 (`test_structured_reasoning.py` —
  structured/empty/legacy outputs; nine authoritative-field
  resistances; citation/provenance incl. compromised-upstream
  defense; prompt/data separation with multi-pattern hostile
  evidence; seven failure modes; single-call orchestration;
  adaptation preservation; framework-boundary AST checks).
- Phase 6.1 (35) + 6.2 (39) + Phase 2–5 regressions pass
  unmodified. Full suite: 1300 passed + 37 skipped (gated),
  0 failures. Live Qdrant/OpenRouter not executed, nothing
  claimed.

## Explicitly deferred

API, workflow, UI, verdict engines, score calibration,
multi-case rollups, agents, memory, retries, new providers.

## Files created / modified

- Created: `xportra/domain/reasoning_generation.py`,
  `tests/unit/test_structured_reasoning.py`,
  `docs/phases/phase-6-3-structured-reasoning-generation.md`.
- Modified: `xportra/domain/compliance_reasoning.py`
  (additive optional input + one defaulted field),
  `xportra/domain/__init__.py` (15 additive exports).
- No other behavior file modified; no prior test touched.
