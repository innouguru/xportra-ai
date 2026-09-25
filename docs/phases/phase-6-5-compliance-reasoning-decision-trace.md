# Phase 6.5 — Compliance Reasoning Decision Trace

**Status:** Complete and verified (2026-09-24)
**Phase:** Phase 6 — Compliance Reasoning & Decision Support
**Type:** Record-only provenance contract — which authoritative
inputs and evidence contributed to an analysis; no chain-of-thought,
no second decision engine, no verdict, no API, no workflow

> This record describes what was actually implemented and verified.

## Objective

Introduce a structured, machine-readable trace answering *"what
inputs and evidence support this result?"* — for provenance,
auditability, reproducibility, evaluation, debugging, and future
API/UI presentation:

```text
compliance case (deterministic facts)
    + ComplianceAnalysis (validated reasoning outcome)
    + ValidatedAnswer (validated model output)
        ↓
DecisionTraceService.trace (records, never decides)
        ↓
DecisionTrace (identity / inputs / typed references /
    observable outcome / steps / fingerprints)
```

Integration boundary: `validated reasoning → ComplianceAnalysis →
DecisionTrace`. The trace never constructs the analysis, makes no
LLM call, and changes no Phase 5 retrieval semantics or Phase
6.1–6.4 contract.

## Architecture check outcome (before coding)

1. Identifiers: tenant (UUID `TenantContext`), case (`case["id"]`
   UUID), requirement (UUID), tenant evidence (`evidence_id`
   UUID), knowledge (`chunk_id`/`document_id` UUIDs + `source_id`
   string), sources (regulatory-source id, document id), analysis
   (uuid5), report (uuid5).
2. All references are already immutable (frozen dataclasses) and
   validated (Phase 6.1–6.4 rule: citations mapping-only, unknown
   UUIDs rejected, tenant execution-level).
3. Safe to expose: stable IDs, citation labels, content
   fingerprints, source metadata, counts, states. Never exposed:
   document/evidence contents (no reference type carries any).
4. No existing audit/event/trace contract: the repository has
   auditability only as provenance-chain and accounting
   properties. Phase 6.5 therefore creates the first trace
   contract and reuses the existing typed references rather than
   new provenance objects — no duplicate system.

## What the trace records

- **Identity:** trace id (deterministic uuid5), tenant, case,
  requirement, analysis, optional report binding,
  `context_fingerprint`.
- **Deterministic inputs:** requirement text, applicability,
  assessment — recorded, cross-checked against the supplied case,
  never determined.
- **Evidence references:** the existing typed
  supporting/conflicting evidence, knowledge, and source
  references (by reference, contents never copied).
- **Reasoning outcome:** validated `explanation`, sufficiency and
  contradiction states, deterministic `sufficiency_explanation`,
  uncertainty category, missing information — the observable
  outcome, not hidden reasoning.
- **Steps:** the six canonical pipeline events in fixed order
  (deterministic state established → evidence selected →
  knowledge retrieved → reasoning generated → reasoning
  validated → analysis constructed), each with stable identifier
  references and small deterministic accounting detail.

## What the trace deliberately does NOT record

Hidden chain-of-thought, internal deliberation, scratchpads,
token streams, system prompts, provider internals, hidden
states, API keys, secrets, raw prompts, or raw unvalidated model
output. None of these are trace inputs, so none can leak —
proven by construction plus negative tests. No timestamps or
random IDs: wall-clock audit time belongs to a future
persistence/API layer, not to this deterministic contract
(documented here instead of invented).

## Deterministic / model-generated / derived classification

- **Deterministic:** identities, requirement text,
  applicability, assessment, typed evidence/knowledge/source
  references, sufficiency/contradiction states and explanation,
  missing information, context fingerprint.
- **Model-generated:** `explanation` only — externally safe text
  already accepted by Phase 6 validation.
- **Derived:** `steps`, `answer_fingerprint` (recomputed via the
  Phase 4/6.3 `content_fingerprint` scheme, never trusted from
  model output), `input_fingerprint`, trace id.

No raw unvalidated model output may enter: non-`ValidatedAnswer`
inputs (including unvalidated `GeneratedAnswer` values and plain
strings/dicts) and non-`ComplianceAnalysis` inputs fail closed,
as do `invalid_citations` answers.

## Provenance invariants (fail closed)

Every evidence reference must belong to the supplied case;
analysis sources must equal the case source views; the analysis
requirement must match the case requirement; analysis
applicability/assessment must equal the case state; every
knowledge label must sit in the answer's authoritative citation
mapping; cross-tenant and foreign-case references are rejected.
The trace reuses Phase 6.1–6.4 validation rather than
reimplementing it.

## Fingerprint semantics

`answer_fingerprint` reuses `content_fingerprint(answer_text)` —
the same scheme as the Phase 6.3 binding. `input_fingerprint`
hashes a canonical JSON payload of stable inputs only (IDs,
texts, states, evidence id+status pairs, knowledge
label+fingerprint pairs, source pairs, answer fingerprint,
outcome fields) — no secrets, prompts, keys, or hidden
reasoning. Semantics: *"was this reasoning generated for these
exact inputs?"* — input-change detection, not model-correctness
proof. Equivalent inputs yield equivalent trace identity;
meaningful changes alter it.

## Security / privacy guarantees

Tenant isolation enforced across case, analysis, and answer
(the empty-knowledge `None`-provenance rule reused from Phase
6.1); no secret-capable parameters exist on the boundary;
serialized output has an exact, fixed key set containing no
prompt/key/deliberation material.

## Verification

- Focused Phase 6.5: 36/36 (`test_decision_trace.py` —
  construction incl. report binding and exact-key
  serialization; provenance incl. case/tenant association;
  integrity incl. unknown-evidence/source rejection,
  divergence rejection, model-supplied-ID rejection, mapping
  mismatch and raw-output rejection; determinism incl.
  equivalence, canonical step order, change detection,
  scheme reuse; security/privacy incl. leakage scan and
  signature inspection; state preservation incl. report
  interop and no-verdict proof; framework-boundary AST
  checks).
- Phase 6.1 (35) + 6.2 (39) + 6.3 (37) + 6.4 (51) regressions
  pass unmodified. Full suite: 1387 passed + 37 skipped
  (gated), 0 failures. Live Qdrant/OpenRouter not executed,
  nothing claimed.

## Explicitly deferred

Chain-of-thought exposure, verdict/risk/action engines,
source ranking, timestamps, API endpoints, UI, public schema,
Phase 7 workflow, Phase 9 evaluation framework, providers,
second RAG abstractions, refactoring.

## Files created / modified

- Created: `xportra/domain/decision_trace.py`,
  `tests/unit/test_decision_trace.py`,
  `docs/phases/phase-6-5-compliance-reasoning-decision-trace.md`.
- Modified (additive only): `xportra/domain/__init__.py`
  (12 additive exports).
- No Phase 1–6.4 behavior file modified; no prior test touched.
