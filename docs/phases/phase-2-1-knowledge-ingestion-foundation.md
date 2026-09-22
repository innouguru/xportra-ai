# Phase 2.1 — Knowledge Ingestion Foundation

> Status: Complete for the approved foundation scope — 2026-09-21

## Purpose

Phase 2.1 establishes the controlled boundary for introducing external
regulatory knowledge into Xportra without letting untrusted or weakly
characterized material silently become operational compliance knowledge.

This phase does not implement parsing, normalization, retrieval, or reasoning.
It only establishes the source-to-artifact boundary, provenance, and validation
requirements needed for later ingestion phases.

## Ingestion boundary

The implemented boundary is:

```text
External regulatory source
    -> source registration
    -> source metadata / authority / provenance
    -> acquisition of concrete artifact
    -> validation of artifact metadata and integrity identity
    -> persisted artifact record
    -> later parsing / normalization / indexing / reasoning phases
```

The architecture keeps the following distinct:

1. Source registration
   - an authoritative external source record (`regulatory_sources`)
2. Acquisition
   - a concrete artifact acquisition event or record
3. Validation
   - checks that required metadata is present and structurally usable
4. Persistence
   - stores the acquired artifact metadata and provenance in the repository
5. Later transformation
   - parsing, normalization, chunking, extraction, indexing, and reasoning

## Models reused

The following existing domain and schema concepts are retained without redesign:

- `Authority` — the government or recognized authority responsible for a source
- `RegulatorySource` — the official source record, including jurisdiction,
  publication data, version, status, source URL, and supersession metadata
- `RequirementSource` — the link between a requirement and a source
- `Tenant` and tenant-owned records remain separate from shared regulatory data

This preserves the existing distinction between shared/reference regulatory data
and tenant-owned business records.

## New model added

A minimal `regulatory_source_artifacts` table was introduced to keep the source
record and the acquired artifact separate.

### `xportra.regulatory_source_artifacts`

Purpose:
- capture the concrete acquired artifact associated with a source
- preserve provenance and acquisition metadata
- support future checksum-based validation and freshness logic

Key fields:
- `id`
- `source_id` (FK to `xportra.regulatory_sources`)
- `artifact_uri`
- `content_hash`
- `content_length`
- `content_type`
- `acquisition_channel`
- `acquired_by`
- `acquired_at`
- `status`
- `source_version`
- `validation_notes`
- `created_at`
- `updated_at`

This avoids conflating a source publication with an acquired file and keeps the
historical provenance trail intact.

## Provenance model

The Phase 2.1 provenance model preserves:

- which authority owns the source
- which source record the artifact belongs to
- where the artifact was acquired from
- who or what acquired it
- when it was acquired
- how it was obtained
- whether it was structurally validated
- the source version identity used during acquisition
- a deterministic content hash for artifact identity

This is the minimum metadata necessary for later freshness and trust checks,
without building a full trust-scoring engine.

## Artifact identity and version strategy

The foundation uses a deterministic content hash (`content_hash`) and a
source-version field (`source_version`) instead of relying on the URL alone.

Rules:
- a URL is not treated as sufficient identity
- a newly acquired artifact is not silently replacing the previous artifact
- each acquisition event is recorded as a distinct artifact version record
- later phases can compare hashes, versions, and acquisition timestamps to detect
  supersession, stale artifacts, or duplicate acquisition events

## Acquisition abstraction

A minimal, reusable `SourceAcquisitionService` was introduced in
`xportra/domain/ingestion.py` and backed by a repository in
`xportra/persistence/repositories.py`.

It is intentionally narrow and supports only the controlled acquisition boundary:
- validate that a source exists
- validate required metadata
- register the artifact without silent overwrite
- preserve provenance and acquisition metadata

It deliberately does not implement:
- crawling
- scraping arbitrary websites
- broad document-management flows
- parsing or normalization
- vectorization or retrieval

## Validation behavior

The validation boundary rejects incomplete or structurally unusable acquisition
records before they are persisted. Required fields include:

- `artifact_uri`
- `acquisition_channel`
- `source_version`
- `content_hash`
- `content_length`
- `content_type`

If data is missing or malformed, `AcquisitionValidationError` is raised.

## Trust boundary

The implementation treats acquired external material as untrusted until it
passes the validation boundary. This preserves metadata needed for future
freshness and authority evaluation without asserting the content is authoritative
just because it was retrieved successfully.

The system does not implement a trust-scoring mechanism or assume a URL itself is
authoritative.

## Storage decisions

- Shared regulatory source and artifact records remain in the shared/reference
  PostgreSQL layer; they are not mixed into tenant-owned tables.
- Tenant-owned data remains tenant-scoped and does not contaminate shared
  regulatory knowledge.
- The source and artifact are deliberately separated because one can describe the
  source and another can describe the actual acquired document or artifact.

## Migrations

Created:
- `migrations/003_regulatory_source_artifacts.sql`
- `migrations/003_regulatory_source_artifacts.down.sql`

The migration adds the `xportra.regulatory_source_artifacts` table and its
indexes and trigger. No Phase 1 table was altered.

## Testing

Focused tests were added in `tests/unit/test_ingestion.py`.

Verified with:

```powershell
& "C:/Users/hp/Desktop/AI PROJECTS/Xportra AI/.venv/Scripts/python.exe" -m unittest tests.unit.test_ingestion -v
```

Result:
- 4 tests ran
- all passed

Regression check:

```powershell
& "C:/Users/hp/Desktop/AI PROJECTS/Xportra AI/.venv/Scripts/python.exe" -m unittest discover tests/unit -v
```

Result:
- 49 tests ran
- all passed

PostgreSQL integration tests were not executed because `DATABASE_URL` is not
configured in the current environment. The suite was not silently treated as
passing; it was reported as environment-gated and therefore not run.

## Security and logging

The implementation intentionally avoids exposing secrets or sensitive content in
logs. It does not introduce service-role credentials, and it does not weaken the
existing Supabase Auth, membership, tenant-isolation, or authorization boundary.

## Deferred decisions

The following remain explicitly deferred:

- document parsing and normalization
- chunking and indexing
- embeddings or vector search
- RAG or retrieval layers
- LLM usage or reasoning
- applicability determination
- compliance scoring or decision support
- regulatory dashboards or UI work
- generalized source crawling
- any full-end ingestion pipeline

## Limitations

This is a foundational boundary only. It preserves provenance and source
identity, but it does not yet infer regulatory meaning, establish compliance
outcomes, or operationalize regulation processing beyond storage and validation.

## Completion status

Phase 2.1 is complete for the approved foundation scope and intentionally stops
before Phase 2.2. No RAG, embedding, vector store, LLM, applicability engine,
frontend, or unrelated functionality was introduced.
