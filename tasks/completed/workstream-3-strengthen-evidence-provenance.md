# Workstream 3 — Strengthen Evidence and Provenance

**Status:** Complete — 2026-11-05  
**Authorization:** Explicit scoped assignment, recorded in
`docs/decisions/ADR-0024-regulatory-extraction-provenance-history.md`.

## Confirmed existing provenance

- Candidates store source ID, normalized-document ID, ingestion-job ID,
  parser version, and source-location JSON.
- Normalized documents retain artifact/source IDs and the normalized text and
  structure.
- Artifacts retain source ID, object URI, SHA-256 content hash, and optional
  artifact source version.
- Workstream 2 validates exact supporting quotations and any supplied
  page/section references against normalized source text and structure.
- Candidate detail joins source/artifact/job metadata; candidate listing
  currently omits most of those joins.

## Confirmed gaps

- No persisted extraction-run history records actual model/provider, prompt
  and extraction versions, text fingerprints, outcomes, or changing result
  snapshots.
- Existing candidate reuse does not retain what a later extraction returned.
- Candidate API `source_version` is joined from mutable source metadata,
  rather than the artifact's captured version.
- A null page/section reference does not explain whether source context was
  unavailable or the model supplied no reference.

## Plan

1. Add an additive migration for append-only extraction runs and per-run
   candidate/evidence snapshots, preserving legacy rows without invented
   metadata.
2. Capture exact source/artifact/text fingerprints and actual extraction
   versions, provider/model, outcomes, and candidate snapshots.
3. Retain all run snapshots when candidates are reused; mark each candidate's
   first producing run without changing its evidence on reprocessing.
4. Distinguish verified, model-omitted, and unavailable page/section
   references; preserve exact quote offsets and text.
5. Expose artifact-version/hash and run history through existing staff-only
   candidate APIs; make candidate list provenance consistent with detail.
6. Add focused unit, PostgreSQL, API authorization/schema, and ingestion
   regressions; apply/test the migration only on local `xportra_test`.

## Acceptance criteria

- Every new extracted candidate resolves through source, artifact, artifact
  version/hash, normalization, ingestion job, and an origin extraction run.
- Each semantic extraction run is inspectable with parser/extraction/prompt
  versions, actual model/provider where reported, input fingerprints,
  outcome, exact candidate evidence, and candidate links.
- Reprocessing appends history and never overwrites prior supporting evidence.
- Quotes remain exact and validated against normalized source text; reference
  statuses do not imply values that were not supplied or verifiable.
- Existing artifact storage and source relationships remain intact; ordinary
  processing cannot mutate captured artifact identity or detach candidate
  provenance.
- Authorized candidate list/detail/history APIs expose traceability;
  unauthorized access remains denied.
- Existing rows remain valid; no migration is run outside local `xportra_test`.

## Verification

Completed verification:

- `python -m pytest tests/unit/test_regulatory_candidate_provenance_api.py tests/unit/test_regulatory_candidate_extraction.py tests/unit/test_regulatory_stage_a_review.py tests/unit/test_regulatory_requirements.py tests/unit/test_regulatory_ingestion_worker.py tests/unit/test_regulatory_ingestion_service.py -q --tb=short`
  — 110 passed, 1 dependency deprecation warning, 6 subtests passed.
- With a process-scoped local `DATABASE_URL`:
  `python -m pytest tests/integration/test_regulatory_candidate_extraction_postgresql.py tests/integration/test_regulatory_stage_a_review_postgresql.py tests/integration/test_regulatory_full_workflow_postgresql.py -q --tb=short`
  — 27 passed, 4 subtests passed, 0 skipped.
- Python `compileall` on all changed modules/tests — passed.
- `git -c core.whitespace=cr-at-eol diff --check` — passed.
- PostgreSQL identity verified as PostgreSQL 18.6, database `xportra_test`,
  role `postgres`, on `127.0.0.1:5432`. Migration 035 was applied with the
  documented `psql -v ON_ERROR_STOP=1 -f` procedure.
- After final migration and failure-metadata corrections, the focused
  command passed 43 tests and 4 subtests with no skips. The PostgreSQL test
  verifies a mismatched artifact version is rejected by the composite foreign
  key:
  ```powershell
  $env:DATABASE_URL = 'postgresql://postgres@127.0.0.1:5432/xportra_test'
  & '.venv\Scripts\python.exe' -m pytest tests\unit\test_regulatory_candidate_extraction.py tests\integration\test_regulatory_candidate_extraction_postgresql.py -q --tb=short
  ```
- The system Python 3.13 interpreter lacked an available psycopg wrapper;
  final focused verification used the project `.venv` with psycopg 3.3.6.
- Existing row counts remained at baseline after fixture cleanup: 2 sources,
  1 artifact, 1 normalization, 6 requirements, and 0 ingestion jobs. The
  extraction-run and run-candidate tables were empty after cleanup; all new
  triggers were enabled.
- Production `.env` settings were not changed or used. The Git worktree
  remains unstaged and uncommitted; no push was performed.

## Completion summary

- Added migration 035 with append-only extraction run/evidence tables,
  cross-record and exact artifact-version identity constraints, source
  artifact and normalization immutability guards, and one-time evidence
  resolution.
- Captured artifact/source/document/job identifiers, immutable artifact
  version/hash, normalized-text SHA-256, parser/extraction/prompt versions,
  observed provider/model metadata, outcome, and exact candidate snapshots.
- Failed extraction invocations record metadata from the configured extractor,
  rather than inheriting semantic-LLM defaults for custom extractors.
- Made candidate creation and first-run evidence linking transactional.
  Reused candidates receive a new run snapshot; changed evidence creates a
  separate candidate rather than rewriting the earlier quotation.
- Preserved exact supporting quotations, quote offsets/hash, and distinct
  verified/model-omitted/context-unavailable page and section statuses.
- Exposed artifact version/hash, parser name, source location, and extraction
  history through existing authorized candidate list/detail and Stage A
  detail responses. Unauthorized candidate access remains denied.
- Updated the full-workflow PostgreSQL fixture to clean its run history before
  its existing local-only constraint-bypassing fixture cleanup.
