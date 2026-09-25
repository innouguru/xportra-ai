# Phase 6.1 — Deterministic Compliance Reasoning Contract

**Status:** Complete and verified (2026-09-24)
**Phase:** Phase 6 — Compliance Reasoning & Decision Support
**Type:** First deterministic domain contract for per-requirement
compliance analysis — composition of existing deterministic state
with a validated RAG answer; no new retrieval, no verdict engine,
no API, no workflow

> This record describes what was actually implemented and verified.

## Objective

Combine shipment/export case facts → deterministic applicable
requirements → existing evidence/assessment state → Phase 5
retrieved knowledge → LLM reasoning → structured compliance
analysis, explaining *why* a requirement holds its assessment:

```text
compliance case (Phase 2.7 view)
    + ValidatedAnswer (Phase 5.12)
    ↓
ComplianceReasoningService.analyze (deterministic, pure)
    ↓
ComplianceAnalysis
    (requirement / status / evidence / source / reason /
     missing information / uncertainty)
```

Never a generic `"compliant": true/false`.

## Architecture check (before coding)

All six inputs mapped to existing contracts — no duplicates:

1. Case facts → `ApplicabilityContext` (+ builder inputs).
2. Applicable requirements → applicability result dicts
   (`outcome`/`reason`, Phase 2.5/3.1).
3. Assessment/evidence → assessment dicts
   (`satisfied`/`not_satisfied`/`unknown`, fixed reasons) +
   `EvidenceRecord` (accepted/reviewed vs rejected/archived —
   the existing conflict signal).
4. Decision summary → `ComplianceCaseService.build` case view
   (the direct 6.1 input: requirement/applicability/
   assessment/evidence/source views + provenance).
5. Retrieved evidence/context → `EvidenceContextSelection` /
   `EvidencePrompt` / `PromptCitation` (Phase 5).
6. Validated RAG output → `ValidatedAnswer` (Phase 5.12).

Requirements sufficiency: PI-4, SP-1–SP-4, NG-5/NG-6,
`development_phases.md` Phase 6 output columns, and the task's
explicit contract list fully specify the work. Confidence
semantics were unspecified → conservative categorical states
per the task's explicit permission. No open question blocked
implementation. No ADR: domain-boundary additions have been
documented in phase docs (not ADRs) since Phase 2; no
structural/boundary/data-flow change was made.

## Authoritative-truth boundary

The service COPIES applicability/assessment from the case and
rejects contradictions: a decisive assessment on a
non-applicable requirement fails closed as fabricated state;
`unknown` is never converted; model text (even `"satisfied"`
or `"compliant: true"` verbatim) changes nothing —
test-proven. Citations come only from
`ValidatedAnswer.validated_citations` (reference-identical);
`invalid_citations` input is rejected rather than analyzed.
Tenant is execution-level (`require_tenant_context` + case/
answer UUID equality; empty-knowledge `None` provenance
allowed since it carries no foreign content). The LLM is an
explanation component over supplied facts, never the truth
source — Invariants 1, 2, 3, 7 hold.

## Contract

`xportra/domain/compliance_reasoning.py` (new, frozen values):

- `ComplianceReasoningError(DomainValidationError)` — integrity
  failures, never converted into analysis.
- `EvidenceReference` (id/type/reference/status),
  `KnowledgeReference` (label/rank/chunk/doc/source/...
  fingerprint), `SourceReference` (regulatory_source/document
  pointers) — all with `to_record()` for future UI/API use.
- `ComplianceAnalysis` — requirement id+text, applicability,
  assessment, verbatim `explanation` (the only model-sourced
  field), supporting/conflicting evidence split on the
  existing accepted-vs-rejected statuses, knowledge refs,
  sources, `missing_information` (fixed templates from
  existing reasons: applicability undetermined, assessment
  incomplete, unlinked tenant evidence, uncited knowledge,
  unestablished satisfying evidence, absent explanation),
  `uncertainty` (`determined`/`uncertain`/`unknown` by fixed
  rule), deterministic uuid5 identity, tenant.
- `ComplianceReasoningService` — stateless; `analyze` (pure)
  plus `analyze_with_knowledge` (thin forward to injected
  `rag_service.query`; provider failures propagate unchanged).

No provider LLM fields, no Qdrant/HTTP/DB/SDK in the module
(AST-verified); twelve additive `xportra.domain` exports.

## LLM boundary reuse

No second client, prompt system, citation system, or validator:
retrieval+generation+validation arrive exclusively via the
injected `RAGApplicationService` and the already-validated
answer. Prompt/LLM/validation fail-closed semantics preserved
unchanged.

## Verification

- Focused Phase 6.1: 35/35 (`test_compliance_reasoning.py` —
  valid/serializable/deterministic result; all three
  applicability and assessment states; missing/conflicting
  evidence; provenance; citation integrity incl. verdict-text
  resistance; tenant isolation incl. empty-provenance path;
  six malformed classes; override resistance both directions;
  empty output both states; LLM/vector failure propagation;
  orchestration forwarding; framework-boundary AST checks).
- Phase 2–5 regression: 621/621. Full suite: 1224 passed +
  37 skipped (gated), 0 failures. No prior test touched.
- Live Qdrant/OpenRouter: not executed (gates off), nothing
  claimed.

## Explicitly deferred

API exposure, Phase 7 workflow, UI, verdict engines, score
calibration, multi-requirement reports, agents, memory,
reranking, retries, second providers.

## Files created / modified

- Created: `xportra/domain/compliance_reasoning.py`,
  `tests/unit/test_compliance_reasoning.py`,
  `docs/phases/phase-6-1-compliance-reasoning.md`.
- Modified (additive only): `xportra/domain/__init__.py`
  (imports + `__all__`).
- No Phase 1–5 behavior file modified; no prior test touched.
