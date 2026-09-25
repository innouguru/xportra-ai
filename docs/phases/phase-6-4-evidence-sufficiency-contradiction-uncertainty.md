# Phase 6.4 — Evidence Sufficiency, Contradiction & Uncertainty Reasoning

**Status:** Complete and verified (2026-09-24)
**Phase:** Phase 6 — Compliance Reasoning & Decision Support
**Type:** Reasoning/explanation enhancement — transparent evidence-quality
state derived from existing deterministic outcomes; no new decision
engine, no verdict, no risk score, no API, no workflow

> This record describes what was actually implemented and verified.

## Objective

Make the reasoning layer explicitly useful when the available evidence
supports, insufficiently supports, or contradicts the deterministic
assessment — without changing the authoritative deterministic
applicability or assessment state:

```text
applicability + assessment (deterministic, trusted)
    + linked evidence counts (supporting vs conflicting)
    + validated knowledge presence
        ↓
EvidenceSufficiencyService.assess (pure derivation, no decisions)
        ↓
ComplianceReasoningService.analyze (carries derived values)
        ↓
ComplianceAnalysis (+ evidence_sufficiency /
    contradiction_state / sufficiency_explanation /
    missing_items)
```

Explanation is not authority.

## Architecture check outcome (before coding)

All six questions resolved from existing contracts — no new algorithm
invented, no blocking ambiguity:

1. Evidence is `EvidenceRecord` (`tenant_id`, `evidence_id`,
   `evidence_type`, `reference`, optional `requirement_id`,
   `status`, `metadata.supports_requirement`); the Phase 2.7 case view
   exposes only linked items as
   `{evidence_id, evidence_type, reference, status}`.
2. Evidence is associated with a requirement via `requirement_id`;
   the case builder filters to matching items.
3. `RequirementAssessmentService.assess` already defines sufficiency:
   `satisfied` (linked accepted/reviewed + supports flag),
   `not_satisfied` (linked rejected/archived, no supporting),
   `unknown` + `"evidence insufficient"` (linked but inconclusive),
   `unknown` + `"required evidence absent"` (no evidence at all),
   `unknown` + `"requirement cannot yet be assessed"`
   (non-applicable). Phase 6.4 mirrors this rule; it invents none.
4. Conflicting evidence is structurally represented via
   rejected/archived statuses; Phase 6.1 already splits
   supporting/conflicting on `CONFLICTING_EVIDENCE_STATUSES`. The
   domain defines no conflict-resolution semantics, so Phase 6.4
   establishes only the smallest safe representation (presence flag +
   preserved lists), never a verdict rule.
5. Phase 5 retrieval exposes `chunk_id`, `document_id`, `source_id`,
   `source_type`, `source_location`, `document_version`,
   `content_fingerprint`, score, and rank — sufficient provenance for
   contradiction reasoning.
6. No source-authority ordering exists among tenant evidence items
   (ADR-0003 ranks regulatory sources, not tenant evidence), so no
   precedence is applied. No ADR: additive domain derivation only,
   documented here per the Phase 2+ convention.

## Evidence sufficiency semantics

Four states, never collapsed into one generic `"uncertain"` label,
derived from the authoritative outcomes (never re-decided):

- `supported` — applicable with a decisive assessment (`satisfied`
  **or** `not_satisfied`): supplied evidence materially supports the
  deterministic assessment in either direction.
- `missing` — applicable, `unknown` assessment, zero linked tenant
  evidence. Absence of evidence is not a failure finding.
- `insufficient` — applicable, `unknown` assessment, linked evidence
  exists but does not establish the requirement. Never treated as
  satisfied or not satisfied.
- `unknown` — the machinery itself is undecided (`unknown`
  applicability, or non-applicable where no assessment is performed):
  sufficiency is not decidable from the supplied state.

Project vocabulary (`satisfied`/`not_satisfied`/`unknown`,
`"evidence insufficient"`, `"required evidence absent"`) is reused;
`"satisfied"` is never inferred from mere evidence existence and
`"not_satisfied"` never from a missing document.

## Contradiction semantics

- `none` — no conflicting (rejected/archived) evidence linked.
- `present` — at least one conflicting item linked.

Both lists are preserved with identities, source/provenance, and
requirement association intact. The explanation may state that
evidence conflicts (e.g. one document indicates a certificate exists
while another indicates it is expired); it must not decide which is
legally authoritative. The deterministic `sufficiency_explanation`
states the non-resolution explicitly ("no source precedence applied
and no document judged authoritative"). Source identities and existing
authority metadata (`SourceReference`, `KnowledgeReference` with
source id/type/location/version) are carried unchanged — source A
says X, source B says Y, conflict preserved.

## Uncertainty semantics

The Phase 6.1 categorical model (`determined`/`uncertain`/`unknown`)
is unchanged, including its fixed derivation rule. Phase 6.4 adds:

- a deterministic *reason* for the category via
  `sufficiency_explanation` and typed `missing_items`;
- a fail-closed guard (`check_no_numeric_confidence`) rejecting
  numeric confidence claims (percentages/probabilities tied to
  confidence language) in model-sourced strings, surfaced as
  `ComplianceReasoningError`. The guard is deliberately narrow: bare
  quantities (`"Form NXP"`, `"30 days"`, `"[E1]"`) never match, and
  deterministic case content is trusted and never inspected.

No percentages, probability scores, calibrated confidence, numeric
model confidence, or hidden scoring exist anywhere. An unresolved
conflict does not change the deterministic uncertainty category; it
is surfaced via `contradiction_state: present`.

## Missing-information semantics

Typed `MissingInformationItem` values (`requirement_id` + `kind` +
`detail`) so consumers never parse prose. Kinds reuse the
deterministic vocabulary: `applicability_undetermined`,
`assessment_incomplete`, `evidence_absent`,
`evidence_insufficient`, `knowledge_uncited`,
`explanation_absent`, `satisfying_evidence_unestablished`. Items
derive only from the supplied deterministic context (details quote
the case's own reasons); the model invents no required document —
model suggestions travel separately with the `model observation:`
prefix (Phase 6.3). Missing information never becomes
`not_satisfied` by itself.

Every analysis therefore distinguishes: (1) what the requirement
requires, (2) what the deterministic system says, (3) what evidence
supports it, (4) what is insufficient or conflicting, (5) what is
missing, (6) what uncertainty remains.

## Deterministic vs model-generated vs derived fields

- **Deterministic** (computed from trusted domain state):
  requirement/applicability/assessment/evidence/sources/tenant/case
  identity (existing), plus new `evidence_sufficiency`,
  `contradiction_state`, `sufficiency_explanation`, `missing_items`
  (fixed-rule classification of the trusted state).
- **Model-generated** (validated, explanatory only): `explanation`,
  `uncertainty_explanation`, `model observation:`-prefixed missing
  strings. Never authoritative; numeric-confidence claims rejected.
- **Derived** (from validated structured information): `uncertainty`
  category, `knowledge_references` (validated mapping only), report
  aggregates (outcome counts only, never prose).

No model-generated field is authoritative merely by being stored on
`ComplianceAnalysis`.

## Phase 5 boundaries reused

Retrieval, ranking, context selection, citation-aware prompts, LLM
invocation, answer validation, and the Phase 6.3 query
builder/strict parser/validation context are reused unchanged. No
second retriever, LLM client, citation framework, parser, or
prompt-injection system was created; the 6.3 strict parser and
validation boundary are intact (no 6.3 file modified). The
`ComplianceAnalysisReport` (Phase 6.2) is untouched — the extended
analysis remains composable (verified: all 6.2 tests pass
unmodified; report rollups for conflicts/missing/uncertainty
continue to derive from the preserved fields).

## Verification

- Focused Phase 6.4: 51/51 (`test_evidence_sufficiency.py` —
  sufficiency incl. both decisive directions, missing vs
  insufficient, absence-is-not-failure, non-collapsed labels;
  contradiction incl. multi-item, provenance, preservation,
  non-resolution; uncertainty incl. categorical preservation,
  unresolved-conflict behavior, six numeric-guard cases;
  missing-information incl. association, grounding, serialization;
  grounding incl. citation allow-list and invented-identifier
  rejection; security incl. hostile evidence, override resistance,
  tenant determinism; derivation unit cases; framework-boundary AST
  checks).
- Phase 6.1 (35) + 6.2 (39) + 6.3 (37) regressions pass unmodified.
  Full suite: 1351 passed + 37 skipped (gated), 0 failures. Live
  Qdrant/OpenRouter not executed, nothing claimed.

## Explicitly deferred (deliberately NOT built)

Automated legal conflict resolution, source-ranking algorithms,
deterministic assessment rule changes, overall verdicts, risk
scores, API, workflow, UI, vector stores, LLM providers, second RAG
abstractions, retries, new dependencies, refactoring.

## Files created / modified

- Created: `xportra/domain/evidence_sufficiency.py`,
  `tests/unit/test_evidence_sufficiency.py`,
  `docs/phases/phase-6-4-evidence-sufficiency-contradiction-uncertainty.md`.
- Modified (additive only): `xportra/domain/compliance_reasoning.py`
  (three defaulted scalar fields + one defaulted tuple field on
  `ComplianceAnalysis`, derivation + numeric guard in `analyze()`),
  `xportra/domain/__init__.py` (21 additive exports).
- No Phase 1–6.3 behavior file modified; no prior test touched.
