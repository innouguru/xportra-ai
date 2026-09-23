# Phase 5.12 — Answer Validation & Citation Integrity

**Status:** Complete and verified (2026-09-23)
**Phase:** Phase 5 — Retrieval & RAG
**Type:** Deterministic answer-validation boundary — citation
integrity only; no semantic truth verification, no LLM, no API, no
provider adapter

> This record describes what was actually implemented and verified.

## Objective

Establish the deterministic boundary:

```text
GeneratedAnswer / LLMResponse   (Phase 5.11 — untrusted model output)
        ↓
AnswerValidator                 (Phase 5.12 — deterministic, pure)
        ↓
ValidatedAnswer                 (citation integrity + preserved provenance)
```

preventing model-generated answers from being treated as authoritative
merely because they contain citation-looking text.

Not implemented: semantic/legal truth verification, API exposure, a
real provider adapter, agentic behavior, retries, autonomous actions.

## Prior-art check

No validation/result abstraction for answers existed (the only
validation conventions are per-boundary fail-closed
`DomainValidationError` subclasses). This phase extends the error
hierarchy minimally — `AnswerValidationError(DomainValidationError)` —
and adds one module; no competing abstraction was created. The
`AnswerValidator` protocol follows the repository's
runtime-checkable-protocol convention.

## Input / output contract

```python
CitationAwareAnswerValidator(*, fail_on_invalid_citations=True)
    .validate(answer: GeneratedAnswer) -> ValidatedAnswer
```

`ValidatedAnswer` (frozen) preserves:

- `answer` — the original `GeneratedAnswer` **by reference**
  (and through it the `EvidencePrompt`, `PromptCitation` objects,
  and the full Phase 5.9 provenance chain);
- `answer_text` — the original generated text, recoverable verbatim;
- `status` — `valid` | `invalid_citations` | `empty`;
- `extraction` — the deterministic `CitationExtraction`
  (first-occurrence references + every occurrence with position);
- `validated_citations` — the authoritative `PromptCitation`
  objects referenced by the answer, in first-occurrence order
  (`assertIs`-identical to the prompt's objects);
- `invalid_references` — extracted labels absent from the mapping
  (non-raising path only);
- `tenant_id` — from the evidence chain only.

Nothing is copied or reconstructed; the model cannot create
provenance, evidence, or a new citation mapping.

## Citation syntax & extraction rules

Canonical syntax (Phase 5.10): `[E<n>]` — implemented as the exact
regex `\[E(\d+)\]`. Strict rules, no fuzzy matching:

- `[e1]`, `E1`, `[E1`, `[Evidence 1]`, `[E-1]`, `[E 1]`, `[E1.5]`,
  and `[EE1]` are **not** citation references;
- no normalization of arbitrary identifiers into valid ones;
- malformed citation-like text is simply not a match — never
  repaired;
- `references` = unique labels in first-occurrence order;
  `occurrences` = every match with character position (repeated
  citations handled deterministically).

No natural-language parsing; no LLM; no fuzzy matching.

## Authoritative citation mapping

The authoritative citation universe is
`GeneratedAnswer.prompt.citations`. A reference in model text is
valid **only if** the label exists in that mapping. Distinctions:

1. citation label exists in the authoritative mapping — **established**;
2. citation label appears in the generated answer — **established**;
3. the semantic claim is supported by that evidence — **NOT
   established** (future boundary).

## Invalid-citation policy (documented choice)

**Fail closed** (the preferred production behavior): an extracted
reference absent from the authoritative mapping raises
`AnswerValidationError`. Invalid references are never silently
removed, no citation is rewritten, no evidence is fabricated to
satisfy a citation, and the answer is never automatically repaired
or converted into an empty response.

A structured non-raising path exists for callers that need to inspect
integrity without enforcement:
`CitationAwareAnswerValidator(fail_on_invalid_citations=False)`
returns `status="invalid_citations"` with `invalid_references`
populated and the valid part still reported. The two paths are
mutually consistent (same extraction, same classification); the
raising default is production behavior.

Operational/provider failures (Phase 5.11 `LLMProviderError`) remain
a separate error type and channel from answer-validation failures
(test-proven hierarchy check).

## Empty-output behavior

Phase 5.11's policy is respected: an empty generated answer yields
`status="empty"` — a valid, distinguishable state, distinct from
provider failure (`LLMProviderError`), validation failure
(`AnswerValidationError`), and invalid citations
(`invalid_citations` status). An empty answer's extraction is empty
by definition; nothing is fabricated. For a non-empty answer against
an empty prompt, the empty mapping means any extracted reference is
necessarily invalid — handled by the normal invalid-citation policy,
never by fabrication.

## Tenant / provenance guarantees

- Tenant identity is authoritative from the evidence chain only;
  the validator verifies single-tenant provenance fail-closed
  (cross-tenant mapping → `AnswerValidationError`). Model-generated
  text can never establish tenant identity — `tenant_id` on the
  result comes from the evidence, not the answer text.
- Provenance resolution is preserved by reference end to end:
  `ValidatedAnswer → GeneratedAnswer → EvidencePrompt →
  PromptCitation → SelectedEvidence → RankedEvidenceResult →
  EvidenceRetrievalResult`.
- Mapping integrity fails closed: duplicate authoritative labels,
  malformed citation objects, missing mapping, and label/rank
  inconsistency are all rejected before any classification.

## What validation proves — and does not

> Citation validation proves that referenced labels correspond to
> authoritative retrieved evidence supplied to the model. It does
> **not** prove that the model's claim is factually or legally
> supported by that evidence.

No "valid citation ⇒ grounded claim" rule exists anywhere in the
implementation (test-proven: the result record contains no
grounding/support language or semantics). A future semantic
grounding / evidence-entailment layer may be introduced separately.

## Security boundary

The validator is pure domain logic. It never executes code or SQL,
invokes tools, accesses the filesystem, makes network requests,
interprets model output as instructions, modifies evidence, modifies
tenant state, or triggers external actions. AST-verified import
boundary (`re`, `dataclasses`, `typing`, `__future__` + sibling
domain modules only). Dangerous model text (code, SQL) passes
through as inert text with normal citation classification.

## Immutability

All new objects are frozen. The validator mutates nothing
(snapshot-proven for `EvidencePrompt` and `GeneratedAnswer`, even on
the failure path) and preserves authoritative objects by reference
(`assertIs`-verified for citations and the prompt chain).

## Failure semantics (fail closed)

`AnswerValidationError` for: malformed `GeneratedAnswer` input,
missing authoritative citation mapping, duplicate authoritative
labels, malformed citation objects, cross-tenant provenance,
label/rank-inconsistent citations, and invalid citation references
(strict policy). Failures never become `""`, `None`, `[]`, or "no
evidence"; no broad exception catching; no silent repair.

## Test strategy

50 focused tests (`tests/unit/test_answer_validation.py`),
deterministic, no credentials: extraction (valid/multiple/repeated/
adjacent/embedded/no-citation/malformed/positions/non-string/frozen),
validation (valid, highest, `[E7]`, `[E99]`, mixed, repeated,
invalid-only, none), result (immutability, reference identity,
mapping preservation, verbatim text, determinism, invalid-not-removed),
empty answers (all five specified states distinguished), security/
integrity (no model-created provenance/mapping, cross-tenant,
duplicates, malformed inputs, no mutation, tenant-from-chain), and
purity (AST imports, no execution, dedicated error types,
determinism, dangerous-text inertness). The whole chain uses real
Phase 5.5/5.7/5.10 domain logic with fakes only at the
infrastructure edge.

## Future semantic grounding considerations

A later boundary could layer entailment/grounding checks on top of
`ValidatedAnswer` — it would consume the same authoritative citation
mapping and the extracted references established here. This phase
deliberately provides the scaffolding (reference classification +
preserved evidence references) without claiming any of that
semantics.

## Implementation

- `xportra/domain/answer_validation.py` (new):
  `AnswerValidationError`, `AnswerValidator` protocol,
  `CitationAwareAnswerValidator`, `ValidatedAnswer`,
  `CitationExtraction`, `extract_citation_references`, status
  constants.
- `xportra/domain/__init__.py`: nine additive exports.
- `tests/unit/test_answer_validation.py`: 50 focused tests.
- No Phase 5.1–5.11 behavior file was modified.

## Verification

- Focused Phase 5.12: **50/50**.
- Phase 5.1–5.11 focused re-runs and complete tree: see
  `CURRENT_STATE.md`.
- Import check: all nine new symbols resolvable from
  `xportra.domain`.

Phase 5 is not marked complete by this phase alone; no Phase 5.13
exists in the phase plan.
