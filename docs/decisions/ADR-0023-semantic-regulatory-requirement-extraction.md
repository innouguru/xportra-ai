# ADR-0023: Semantic Regulatory Requirement Extraction

- **Status:** Accepted for Workstream 2 only (2026-11-04)
- **Linked requirements:** TB-5 and the candidate/provenance criteria in
  proposed R-4D, `REQUIREMENTS.md`; explicit scoped Workstream 2 assignment.
- **Linked task:** `tasks/active/workstream-2-fix-requirement-extraction.md`
- **Related decisions:** ADR-0001 (deterministic applicability remains
  authoritative); ADR-0017 (human review and publication gates).

## Context

The active ingestion path calls `RegulatoryRequirementExtractionService`,
which selects sentences using deterministic `shall`/`must`-centered
expressions. It misses semantically binding language without those phrases
and cannot reliably distinguish binding obligations from descriptive or
recommendatory text. The existing LLM protocol and OpenRouter adapter serve
RAG generation, but the regulatory extraction path does not use them.

Workstream 2 explicitly authorizes improving this extraction path. The
authorization does not lift ADR-0017's gates for the rest of Phase 4D, nor
does it authorize automatic approval, publication, or applicability
decisions.

## Decision

1. Replace the active regex-only requirement selection with semantic
   extraction using the existing provider-independent `LLMClient`,
   `EvidencePrompt`, `LLMGenerationConfig`, `LLMResponse`, and the existing
   OpenRouter adapter. Do not add a provider client, model setting, or
   provider SDK.
2. Use the normalized document text as the quotation-verification source.
   Split long documents into ordered, bounded, overlapping chunks; carry
   existing section/page context into each prompt. Failed chunks and rejected
   model items must be reflected as partial or failed outcomes, never silently
   discarded or converted into deterministic-extractor success.
3. Parse a strict structured JSON response and validate its shape, allowed
   requirement type, exact supporting quotation, and any supplied page,
   section, product/category, or effective-date claim against source text and
   available structure.
4. Persist candidates through the existing repository. Keep source,
   artifact, normalized-document, and ingestion-job links unchanged. Store
   supported title, quotation, section/page context, and optional metadata in
   the existing `source_location` JSON field; use `requirement_text` for the
   candidate description. No schema migration is required.
5. Candidates remain reviewable, unapproved records. LLM output never
   determines applicability and never passes either review or publication
   gate.

## Alternatives Considered

- **Expand deterministic phrase matching:** rejected as the primary extractor;
  it retains the confirmed lexical-recall limitation and cannot distinguish
  context reliably.
- **Add a new LLM provider/client or queue:** rejected; existing LLM
  abstractions, configured model, and in-process ingestion path are reused.
- **Add candidate columns or redesign provenance:** deferred; current JSON
  source-location field and existing provenance links represent this bounded
  scope without a migration.
- **Silently fall back to regex extraction when the LLM fails:** rejected;
  provider, parsing, and validation failures must remain explicit and
  retryable/partial as appropriate.

## Consequences

- Regulatory extraction requires the existing `LLM_API_KEY` and
  `LLM_MODEL`; `LLM_BASE_URL` and `LLM_TIMEOUT_SECONDS` retain their existing
  defaults and overrides.
- Scripted LLM responses provide deterministic unit coverage; local database
  integration verifies that validated candidates retain existing
  persistence/provenance behavior. No live provider call is required for
  tests.
- Empty, valid structured output means successful extraction with no
  qualifying requirements. Empty or malformed model output is a failure.
- The broader Phase 4D implementation remains unauthorized except for this
  Workstream 2 scope.
