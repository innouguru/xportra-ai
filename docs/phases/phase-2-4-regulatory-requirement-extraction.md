# Phase 2.4 — Regulatory Requirement Extraction

> Status: Complete for the approved boundary scope — 2026-09-21

## Implementation summary

Phase 2.4 converts a structured normalized regulatory document into explicit
requirement records:

```text
structured document -> deterministic normative statement extraction -> persisted requirement records
```

The implementation is rule-based and intentionally does not determine whether a
requirement applies to an exporter, commodity, destination, shipment, or business.

## Requirement model

The persisted `xportra.regulatory_requirements` record contains:

- deterministic `id`
- `normalized_document_id`
- `requirement_text`
- `requirement_type`
- `source_location`
- zero-based `position`
- optional explicit `actor`
- optional `condition_metadata`
- `status`
- `created_at`
- `updated_at`

Requirement types are limited to:

- `obligation`
- `prohibition`
- `documentation`
- `procedure`
- `threshold`
- `inspection`
- `certification`
- `labeling`
- `recordkeeping`
- `notification`
- `unknown`

## Extraction design

`RegulatoryRequirementExtractionService` receives the Phase 2.3 normalized
structured document and scans section text sentence by sentence.

It recognizes explicit normative forms such as:

- `shall`, `must`
- `must not`, `shall not`, `may not`
- explicit required/prohibited phrases
- explicit inspection statements such as `may inspect`

Descriptive text and ambiguous advisory language such as `should` are ignored.
When a statement is not an explicit normative candidate, no requirement record is
created. The original sentence is retained as the requirement wording.

Classification is deterministic and conservative. Specific forms are recognized
for prohibition, inspection, notification, labeling, recordkeeping, threshold,
documentation, certification, and procedure; otherwise the candidate is an
`obligation` when it contains an explicit normative form.

## Actor and conditions

An actor is captured only from the explicit subject before the normative verb.
No actor is inferred from source, document title, or business context.

Condition metadata is captured only when explicit:

- threshold phrases such as `at least five years`
- condition phrases beginning with `if`, `when`, `unless`, `provided that`, or
  `where`

No applicability fields or decisions are created.

## Provenance and source location

Each requirement stores the normalized document ID. The normalized document
already references the acquired artifact and source, preserving:

```text
requirement -> normalized document -> acquired artifact -> regulatory source
```

The source location stores section order and heading. Position stores the stable
order of extracted candidates within the document.

## Idempotency and persistence

Created migrations:

- `migrations/006_regulatory_requirements.sql`
- `migrations/006_regulatory_requirements.down.sql`

`RegulatoryRequirementRepository` persists records using parameterized SQL and
JSONB for source location and explicit condition metadata.

Requirement IDs are deterministic UUID5 values derived from normalized document
identity, position, and requirement wording. The database also enforces unique
`(normalized_document_id, position)`. Reprocessing a document returns its existing
records and does not create duplicates.

## Security and exclusions

- no document content is executed
- no secrets or credentials are introduced or logged
- no LLM, agent, embedding, vector, or retrieval component is used
- no applicability, compliance, recommendation, or action decision is produced
- requirements remain shared regulatory knowledge and do not bypass tenant/security
  boundaries

## Testing

Focused tests are in `tests/unit/test_regulatory_requirements.py` and cover:

- obligations, prohibitions, documentation, procedures, thresholds, and
  inspections
- explicit actors and conditions
- descriptive/advisory rejection
- source location and provenance
- deterministic identities
- repeated-processing idempotency
- empty/invalid input
- absence of applicability inference

The focused and complete unit test results are recorded in the completion report.
PostgreSQL integration tests require `DATABASE_URL` and are not run when it is
unavailable.

## Limitations and deferred work

This phase does not parse ambiguous legal language, infer actors or conditions,
perform OCR, map requirements to business entities, or decide applicability.
Chunking, embeddings, vector databases, indexing, retrieval, reranking, RAG, LLMs,
agents, compliance reasoning/scoring, UI, crawling, monitoring, and Phase 2.5
remain deferred.
