# Phase 2.2 — Artifact Parsing & Normalization

> Status: Complete for the approved boundary scope — 2026-09-21

## Purpose

Phase 2.2 builds the next controlled knowledge-processing boundary after
Phase 2.1:

```text
accepted regulatory artifact
    -> explicit artifact parsing
    -> deterministic normalization
    -> stable representation for downstream indexing/retrieval
    -> no compliance reasoning or RAG layer
```

The purpose is to make accepted regulatory artifacts usable without introducing
semantics, retrieval, or LLM behavior. This phase deliberately stops before
chunking, embeddings, retrieval, or regulatory decision logic.

## Scope and boundary

The implemented boundary is intentionally narrow and explicit:

- accept only supported artifact types
- reject unsupported types explicitly
- reject unreadable, malformed, or empty content
- preserve the originating artifact ID and source ID
- normalize parsed content into structured document fields
- preserve headings/sections/paragraph structure when available
- keep normalized content traceable to the source via the artifact relationship
- persist a normalized record without enabling uncontrolled duplicates

This does not implement:
- chunking
- indexing
- vector records
- retrieval
- reranking
- RAG
- LLM calls
- applicability determination
- compliance scoring
- generalized crawling
- workflow orchestration

## Supported artifact types

The explicit parser supports these types:

- `text/plain`
- `text/markdown`
- `application/json`

Unsupported types, including binary or PDF-like content, are rejected with
`ArtifactParseError` before any downstream processing is attempted.

## Parsing design

A small explicit abstraction was introduced in `xportra/domain/ingestion.py`:

- `ArtifactParsingService`
- `ArtifactParseError`

Behavior:
- validates the content type against a small allow-list
- rejects empty, malformed, or unreadable content
- decodes UTF-8 text safely
- handles markdown heading/section extraction
- handles plain-text paragraph segmentation
- handles JSON object/section extraction without trying to infer meaning
- preserves a lightweight document structure, such as headings and sections
- prevents silent empty output by rejecting empty normalized content

## Normalization design

A second explicit abstraction was added:

- `ArtifactNormalizationService`
- `ArtifactNormalizationError`

The normalization step produces a deterministic representation with fields that
match the downstream need without inventing regulatory semantics:

- `id`
- `artifact_id`
- `source_id`
- `document_title`
- `normalized_text`
- `normalized_content`
- `content_type`
- `parser_name`
- `status`
- `normalized_at`
- `created_at`
- `updated_at`

The same parsed input produces the same normalized output because the algorithm:

- normalizes whitespace
- preserves document order
- uses deterministic heading/section extraction
- derives title consistently
- reuses a deterministic UUID identifier based on artifact + source + normalized text

## Structural preservation

Where structure is available, the normalized record preserves it in a minimal,
non-semantic structure:

```json
{
  "mime_type": "text/markdown",
  "structure": [
    {"kind": "heading", "text": "Seed Export Guidance"},
    {"kind": "section", "text": "Scope"},
    {"kind": "section", "text": "Follow the procedure."}
  ]
}
```

This keeps later retrieval phases from receiving a single undifferentiated blob
while avoiding any semantic interpretation of regulatory meaning.

## Provenance design

The normalized representation remains traceable via the existing artifact/source
relationship:

```text
normalized record -> artifact -> source
```

The system does not duplicate the full provenance chain when the existing IDs are
sufficient to establish the relationship. The normalized record stores the
artifact and source IDs directly, which keeps provenance explicit without copying
all source metadata redundantly.

## Persistence design

A new migration was added:

- `migrations/004_regulatory_document_normalizations.sql`
- `migrations/004_regulatory_document_normalizations.down.sql`

The table is:

- `xportra.regulatory_document_normalizations`

Purpose:
- persist normalized document text and structure
- support downstream retrieval/index phases without changing Phase 1 schema
- preserve a unique one-to-one normalized record per artifact
- maintain source and artifact provenance directly

Schema highlights:
- `artifact_id` references `xportra.regulatory_source_artifacts(id)`
- `source_id` references `xportra.regulatory_sources(id)`
- `normalized_content` uses `JSONB`
- `status` is restricted to `('normalized', 'failed', 'rejected')`
- `artifact_id` is unique to prevent uncontrolled duplicates

## Idempotency

The same artifact is not allowed to create uncontrolled duplicates:

- `ArtifactNormalizationService.normalize()` returns the existing normalized row
  if one already exists for the same artifact ID
- the repository enforces a unique `(artifact_id)` constraint
- the idempotency key is tied to the artifact identity rather than arbitrary job
  execution state

This is intentionally simple and does not introduce a distributed job framework or
general deduplication engine.

## Failure handling

Parsing and normalization explicitly fail without persisting a successful record:

- unsupported content type -> `ArtifactParseError`
- malformed JSON -> `ArtifactParseError`
- unreadable UTF-8 -> `ArtifactParseError`
- empty/blank text -> `ArtifactParseError`
- empty normalized text after parsing -> `ArtifactNormalizationError`
- normalization failure -> explicit error path before persistence

A record is only treated as normalized after the parser and normalizer succeed.

## Security

The implementation still treats acquired material as untrusted input:

- no secrets are introduced
- no credentials are logged
- parser behavior cannot silently bypass artifact validation
- no prompt-injection handling is attempted, because LLM/RAG concerns are out of scope
- content is only parsed and normalized as text/document structure; it is not
  interpreted as instructions or operational logic

## Testing

Focused tests were added in `tests/unit/test_parsing_normalization.py`.

Verified with:

```powershell
& "C:/Users/hp/Desktop/AI PROJECTS/Xportra AI/.venv/Scripts/python.exe" -m unittest tests.unit.test_parsing_normalization -v
```

Result:
- 9 tests ran
- all passed

Regression check:

```powershell
& "C:/Users/hp/Desktop/AI PROJECTS/Xportra AI/.venv/Scripts/python.exe" -m unittest discover tests/unit -v
```

Result:
- 58 tests ran
- all passed

PostgreSQL integration tests were not executed because `DATABASE_URL` is not
configured in the current environment. The suite remains environment-gated and
was reported as such rather than treated as passing.

## Documentation / state updates

Updated:
- `ACTIVE_TASK.md`
- `CURRENT_STATE.md`

These reflect the Phase 2.2 boundary, supported content types, persistence
strategy, idempotency, and the fact that Phase 2.3 remains untouched.

## Deferred work

The following remain explicitly deferred:

- chunking
- embeddings
- vector databases
- retrieval
- reranking
- RAG
- LLM calls
- applicability determination
- compliance reasoning
- compliance scoring
- workflow orchestration
- Phase 2.3 and later phases

## Completion status

Phase 2.2 is complete for the approved parsing and normalization boundary. It
stops before Phase 2.3 and does not begin retrieval, RAG, LLM, or compliance
reasoning.
