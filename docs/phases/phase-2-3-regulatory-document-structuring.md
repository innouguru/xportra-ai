# Phase 2.3 — Regulatory Document Structuring & Metadata Extraction

> Status: Complete for the approved boundary scope — 2026-09-21

## Purpose

Phase 2.3 converts a normalized regulatory document into explicit, deterministic
metadata and structural sections:

```text
normalized regulatory document
    -> deterministic metadata extraction
    -> conservative document classification
    -> ordered section hierarchy
    -> persisted metadata record
```

The phase preserves the distinction between source, acquired artifact, normalized
document, and extracted structure. It does not implement retrieval, indexing,
chunking, or regulatory reasoning.

## Extracted metadata model

`RegulatoryMetadataExtractionService` produces:

- `normalized_document_id`
- `artifact_id`
- `source_id`
- `document_title`
- `authority_name`
- `document_type`
- `classification`
- `publication_date`
- `effective_date`
- `reference_identifier`
- `version`
- `jurisdiction`
- `language`
- `sections`
- `status`

The artifact and source identifiers come from the normalized document and are
required. No metadata record can be created without the normalized document
identity and its existing provenance identifiers.

Unknown metadata remains `null`. The service does not guess missing authority,
dates, version, jurisdiction, language, or document type values.

## Deterministic extraction rules

Extraction is explicit and deterministic:

- read known metadata keys from `normalized_content`
- fall back to same-named normalized-document fields only when explicitly present
- trim string values
- normalize explicit document type casing
- parse only ISO-8601 calendar dates (`YYYY-MM-DD`)
- extract a title from explicit metadata, then the first reliable heading
- read sections only from the normalized structural representation
- reject missing normalized-document, artifact, or source identity
- reject malformed explicit date values

No document text is interpreted semantically. The service does not infer whether a
requirement applies, whether a party is compliant, or what action should be taken.

## Classification approach

Classification is intentionally minimal. An explicit document type is classified
only when it is one of:

- `regulation`
- `standard`
- `guideline`
- `procedure`
- `notice`
- `form`

Anything else, including missing or ambiguous type metadata, receives
`classification = "unknown"`. The original explicit document type remains
available separately when present.

## Section representation

Sections are structural units, not chunks. Each extracted section contains:

- `order`
- `heading`
- `level`
- `parent_index`
- `text`

Heading levels are read from the normalized structure when available. A simple
stack determines the nearest preceding parent heading with a lower level. Content
following a heading is associated with that section until the next heading.
Document-title headings are excluded from the section list when they match the
explicit document title.

This preserves ordering, parent/child relationships, and structural boundaries
without creating retrieval chunks or semantic units.

## Persistence design

Created:

- `migrations/005_regulatory_document_metadata.sql`
- `migrations/005_regulatory_document_metadata.down.sql`

The new table is:

- `xportra.regulatory_document_metadata`

It stores metadata and JSONB sections and references the normalized document with
`ON DELETE RESTRICT`. The normalized document already points to the acquired
artifact and source, so provenance remains:

```text
metadata -> normalized document -> acquired artifact -> regulatory source
```

The repository is `RegulatoryDocumentMetadataRepository` in
`xportra/persistence/repositories.py`. It uses parameterized SQL and psycopg's
JSONB adapter for section metadata.

## Idempotency

Repeated processing of the same normalized document returns the existing metadata
record. The database also enforces a unique `normalized_document_id` constraint.
No workflow scheduler, distributed lock, or generalized deduplication framework
was introduced.

## Freshness and versions

The explicit `version` and `reference_identifier` values already present in the
normalized document remain available in the extracted metadata. This phase does
not schedule refreshes, fetch new artifacts, or alter source/version identity.

## Security and trust boundary

- document content is never executed
- text is not interpreted as application instructions
- no secrets or credentials are introduced or logged
- metadata remains within the shared regulatory knowledge model
- no tenant-owned metadata path is created
- no LLM, agent, or prompt-processing behavior is introduced

## Testing

Focused tests were added in `tests/unit/test_regulatory_structuring.py`.

Verified with:

```powershell
& "C:/Users/hp/Desktop/AI PROJECTS/Xportra AI/.venv/Scripts/python.exe" -m unittest tests.unit.test_regulatory_structuring -v
```

Result:
- 9 tests ran
- all passed

The focused tests cover:
- successful extraction
- title extraction
- authority/source preservation
- classification
- publication/effective dates
- version/reference identity
- explicit unknown handling
- section hierarchy
- deterministic extraction
- persistence through the service repository boundary
- repeated processing/idempotency
- insufficient identity and malformed date failures

The complete unit regression suite is run after the implementation and recorded
in the completion report.

PostgreSQL integration tests require `DATABASE_URL`. They were not executed in
the current environment because that variable is unavailable.

## Deferred work and limitations

Deferred:

- document chunking
- embeddings
- vector databases
- keyword or vector indexing
- retrieval
- reranking
- RAG
- LLM calls
- agents
- applicability determination
- compliance reasoning and scoring
- recommendation generation
- crawling and scheduled freshness jobs
- frontend/UI
- Phase 2.4

The extractor only recognizes metadata explicitly represented by the normalized
document. It does not attempt OCR, PDF parsing, language detection, date inference,
or taxonomy expansion.

## Completion status

Phase 2.3 is complete for the approved regulatory document structuring and
metadata extraction boundary. Phase 2.4 has not begun.
