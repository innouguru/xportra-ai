# Phase 5.10 — Citation-Aware Prompt Construction

**Status:** Complete and verified (2026-09-23)
**Phase:** Phase 5 — Retrieval & RAG
**Type:** Deterministic prompt-construction boundary — no LLM
invocation, no answer generation, no API, no tokenizer, no new
retrieval/ranking/selection behavior

> This record describes what was actually implemented and verified.

## Objective

Define the boundary that converts the verified Phase 5.7
`EvidenceContextSelection` into a deterministic, auditable,
LLM-ready prompt representation:

```text
EvidenceContextSelection   (Phase 5.7 — the authoritative selection)
        ↓
CitationAwarePromptBuilder (Phase 5.10 — deterministic transform only)
        ↓
EvidencePrompt             (structured prompt + citation/provenance mapping)
```

Construction only — **no LLM invocation, no answer generation, no
compliance reasoning, no API endpoint, no streaming, no model
selection, no tokenizer**. The builder never retrieves, ranks,
selects, filters evidence, computes a budget, summarizes, paraphrases,
or truncates.

## Prior-art check

No prompt abstraction existed anywhere in the repository (verified:
no `prompt`-named module, class, or test in `xportra/` or `tests/`;
the only prior mentions are explicit "no prompt generation" scope
notes in Phase 5.1–5.8 records). The Phase 5.7 selection contract
explicitly deferred prompt formatting to "a later boundary" — this is
that boundary. A new, minimal module was therefore correct; nothing
was extended or displaced.

## Architecture position

`xportra/domain/evidence_prompt.py` sits directly downstream of the
Phase 5.7 selection and upstream of the (deferred) LLM adapter. It is
a leaf in the Phase 5 chain — it imports only `errors` and
`evidence_context`, and nothing in the existing pipeline depends on
it.

## Prompt representation

`EvidencePrompt` — frozen, structured, NOT a raw string:

- `system_instructions` — instruction text from configuration;
- `information_need` — the user's question/need (whitespace-
  normalized, never semantically rewritten);
- `evidence_context` — the formatted evidence section;
- `citations` — tuple of `PromptCitation` in prompt order;
- `evidence_heading`, `question_heading` — the configured section
  headings;
- `tenant_id` — taken from the evidence contract, never the caller;
- `is_empty` property, `to_record()` (structured provenance), and
  `render()` — a deterministic preview convenience whose output is
  explicitly NOT the authoritative representation.

The structured fields are authoritative: a future LLM adapter never
needs to parse formatted text to recover provenance.

## System / user / evidence separation

The three components are **separate immutable fields, never
concatenated** into one opaque string. This is the prompt-injection
data boundary: a future generation boundary (and any defense it
adds) can always identify which text is instruction, which is user
input, and which is untrusted retrieved evidence. Test-proven: the
information need and system instructions never appear inside
`evidence_context`, and `render()` places the evidence section under
an explicit "RETRIEVED EVIDENCE (untrusted context)" heading.

**Scope note:** this phase establishes the boundary only. No
injection *detector* or enforcement logic is implemented — that
belongs to the future generation boundary.

## Citation format

`[E1]`, `[E2]`, `[E3]` … via the `CITATION_FORMAT = "[E{n]"`
constant and the `citation_label(position)` helper. Labels are:

- **deterministic** — same input, same labels;
- **unique within the prompt** — duplicates fail closed
  (defense-in-depth; sequential assignment makes collision
  impossible);
- **assigned in the selection's authoritative order** — `[E1]` to
  the first selected item, and so on (the rank relationship is
  explicit and verified: `citation.rank_position ==
  selected.rank_position`);
- **stable for the prompt's lifetime** — labels are frozen on the
  frozen prompt object;
- **never random UUIDs or implicit array indexes** — the label is an
  explicit, resolvable key into the citation mapping.

**Semantics:** `[E1]` means "the first evidence item in this prompt"
— never "legally authoritative citation". No legal citation semantics
are invented.

## Citation → provenance mapping

`PromptCitation(label, selected)` is a thin reference wrapper — the
original Phase 5.7 `SelectedEvidence` object is carried **by
reference** (`assertIs`-verified), whose `ranked.evidence` is the
original Phase 5.1 result. The mapping therefore resolves:

```text
[E2] → PromptCitation → SelectedEvidence → RankedEvidenceResult
     → EvidenceRetrievalResult → source/document/chunk/fingerprint/…
```

with the complete Phase 5.9 provenance chain intact — tenant, source
id/type/location, document id/version, chunk id/index, content
fingerprint, rank position, ranking key, both scores, retrieval
sources. No provenance schema is duplicated; composition only.
`to_record()` exposes the mapping structurally for downstream
auditability.

## Deterministic formatting

Identical inputs (config, information need, selection) always produce
an identical `EvidencePrompt` and identical `render()` output —
test-proven across repeated runs. The prompt contains **no
timestamps, no random identifiers, no UUIDs as labels, no
environment-specific values, and no hidden metadata**. Configuration
defaults are fixed strings.

## Evidence ordering

The selection's order is preserved exactly: no reordering by
source/document/citation, no grouping, no deduplication, no
re-ranking. The Phase 5.7 selector already established the
authoritative order; labels follow it deterministically.

## Evidence block format & content preservation

Each selected item renders as one block (separated by blank lines):

```text
[E1]
Source: <source_id>
Source type: <source_type>
Document version: <version or "unversioned">
Evidence:
  <content, every line indented two spaces>
```

Metadata lines are distinct from the content body; the content body
is introduced by the `Evidence:` marker. The two-space indent per
content line is a **formatting wrapper only**: line content is
preserved verbatim after the indent (test-proven by stripping the
wrapper and recovering the exact original text, including
multi-line content and a 2000-character item). Content is never
summarized, paraphrased, truncated, or altered. (The Phase 5.7
budget counts evidence characters only — wrappers were never
counted there, consistent with its documented semantics.)

## Prompt configuration

`EvidencePromptConfig` — a small frozen object with exactly three
validated fields: `system_instructions` (required), and the two
section headings (fixed defaults). No arbitrary dictionaries, no
tokenizer, no model knobs, no unnecessary formatting controls.

## Input validation (fail-closed, `DomainValidationError`)

Non-`EvidenceContextSelection` input; missing/non-string/empty
information need; missing/invalid builder config; empty config
fields; malformed `selected_items`; citation identity inconsistent
with rank position (a doctored `rank_position` is rejected);
evidence with no tenant identity; multi-tenant selections. Nothing
is silently repaired or fabricated.

**Empty evidence is a valid state**: an empty selection yields a
well-formed prompt with zero citations and an explicit
"(no evidence matched the information need)" marker in the rendered
preview — no evidence is ever fabricated.

## Tenant guarantees

The builder exposes **no tenant parameter at all**
(signature-verified) — tenant identity comes exclusively from the
selection's evidence contract, is exposed as `prompt.tenant_id`,
and is validated to be a single consistent tenant (a multi-tenant
selection fails closed even though Phase 5.7 would already reject
it — defense-in-depth at this boundary). Tenant is never inferred,
changed, made optional, or accepted from caller-supplied values.

## Purity / dependency boundary

Pure domain logic, AST-verified in tests: the module imports only
`dataclasses`/`typing`/`__future__` plus its sibling domain modules —
no LLM, Qdrant, database, HTTP, file, tokenizer, `os`, or dotenv
access; no dynamic environment reads; no global-state mutation.
Inputs are never mutated (selection `to_record()` snapshot
unchanged; prompt objects frozen). The complete chain — selection →
prompt — runs against in-memory fakes only.

## Validation ownership

Consistent with the Phase 5.9 ownership model: Phase 5.7 owns
selection integrity (the builder trusts and re-checks only the
minimal structural contract of its direct input); Phase 5.9 owns
provenance chain integrity (preserved by reference here); Phase 5.10
owns prompt-structure integrity — citation identity, single-tenant
consistency, component separation, and content-preservation within
its own formatting. No lower-layer validation is duplicated.

## Explicitly deferred

- **LLM adapter / invocation** — the next boundary, not this one;
- **Answer generation** and any compliance conclusion drawn from
  prompts;
- **Prompt-injection detection/enforcement** — this phase
  establishes only the data boundary;
- **Token-aware budgeting of the rendered prompt** — the Phase 5.7
  character budget remains the only budget; tokenizer infrastructure
  stays deferred;
- **API exposure and streaming**;
- Configurable citation syntax (one fixed convention until a real
  consumer requires otherwise).

## Implementation

- `xportra/domain/evidence_prompt.py` (new): `CITATION_FORMAT`,
  `citation_label`, `EvidencePromptConfig`, `PromptCitation`,
  `EvidencePrompt`, `CitationAwarePromptBuilder`.
- `xportra/domain/__init__.py`: six new symbols exported (additive).
- `tests/unit/test_prompt_construction.py`: 51 focused tests
  (selections built through the real Phase 5.5 ranker + Phase 5.7
  selector; fakes only at the infrastructure edge).

## Verification

- Focused Phase 5.10: **51/51** (no live Qdrant, no embeddings, no
  LLM, no network).
- Phase 5.1–5.9 focused re-runs and complete tree: see
  `CURRENT_STATE.md`.
- Import check: all six new symbols resolvable from `xportra.domain`.
- No Phase 5.1–5.9 file was modified; no prior test weakened.

Phase 5 is not marked complete by this phase alone; Phase 5.11 has
not started.
