# ADR-0024: Regulatory extraction provenance history

- **Status:** Accepted for Workstream 3 only (2026-11-04)
- **Linked requirements:** Candidate/source traceability and source-preservation
  criteria in proposed R-4D, `REQUIREMENTS.md`; explicit scoped Workstream 3
  assignment.
- **Linked task:** `tasks/active/workstream-3-strengthen-evidence-provenance.md`
- **Related decisions:** ADR-0003 (source authority and freshness),
  ADR-0017 (immutable source history and human review), ADR-0023 (validated
  semantic extraction).

## Context

The existing candidate schema already links candidates to a normalized
document, source, and ingestion job; normalization links to an artifact.
Artifacts already carry a content hash and optional `source_version`.
Candidate `source_location` contains a supporting quote, page/section
references, and the surrounding structured context. Workstream 2 validates
the quote exactly against normalized text and validates supplied references.

The schema does not record an extraction invocation separately. Candidate
rows do not retain the provider, actual model, prompt version, extraction
version, or the exact result of subsequent runs. Reprocessing a document can
reuse existing candidates, so the latest job alone cannot establish what each
run returned. Candidate detail also reports `source.version` rather than the
artifact's captured `source_version`; list responses do not join the
provenance metadata shown by detail responses. A NULL reference does not say
whether structured source context was unavailable or the model returned no
reference.

## Decision

1. Keep the existing ingestion, normalization, candidate, and storage
   boundaries. Do not copy artifact bytes, source IDs, normalized-document
   IDs, or job IDs into candidate columns that already have a relationship.
2. Add an append-only extraction-run record containing the existing source,
   artifact, normalized-document, and job IDs; captured artifact hash and
   normalized-text hash; parser/extraction/prompt versions; observed provider
   and model identifiers; outcome; and safe failure/rejection counts.
3. Add append-only per-run candidate evidence records. Each record stores the
   exact validated candidate snapshot and its stable candidate link after
   persistence. A candidate may be linked to more than one run; an origin
   marker identifies its first producing run. Legacy candidates remain
   valid and explicitly have no reconstructed run history.
4. Record reference status in `source_location`: verified references,
   references not returned by the model despite supplied context, and
   references unavailable in the supplied structured context are distinct.
   Never infer or repair a missing reference.
5. Preserve source quotes and offsets exactly. Store the normalized-text
   fingerprint and captured artifact hash with every run. Keep source and
   artifact versions distinct; expose the artifact's captured version/hash,
   not a mutable source version as historical artifact provenance.
6. Prevent normal database updates/deletes from rewriting captured artifact
   identity or extraction history. Permit only one pending-to-final update
   of a run-candidate link while the application resolves a persisted or
   reused candidate.
7. Extend the existing authorized candidate detail/history responses and
   candidate list provenance joins; do not introduce a new authorization
   model or dashboard workflow.

## Alternatives considered

- **Put model and prompt fields only in `source_location`:** rejected because
  repeated extraction would overwrite/omit history and could not reliably
  associate one candidate with multiple runs.
- **Add more mutable candidate columns:** rejected because a single row
  cannot preserve changed evidence across reprocessing.
- **Create a separate audit application or storage system:** rejected; the
  existing PostgreSQL and Supabase Storage boundaries are sufficient.
- **Backfill guessed run metadata for legacy candidates:** rejected; historic
  provider/model/prompt details are not present and must remain unknown.

## Consequences

- One additive migration creates run and run-candidate history tables and
  immutable-history guards. Existing candidate rows remain valid and are not
  assigned invented model or prompt data.
- Every semantic extraction invocation, including valid empty/partial/failed
  model outcomes, can be inspected independently of the current candidate
  row.
- A second run records its exact result even when a candidate is reused or
  its quote changes. Candidate source evidence is not silently replaced.
- Local PostgreSQL 18.6 `xportra_test` is the only database permitted for
  migration and integration verification in this workstream.
- This ADR does not authorize OCR, parser replacement, quality scoring,
  publication/indexing changes, RAG changes, or dashboard redesign.
