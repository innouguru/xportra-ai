# Workstream 2 — Diagnose and Fix Existing Extraction Functionality

**Status:** Complete  
**Authorization:** Explicit scoped assignment, recorded in
`docs/decisions/ADR-0023-semantic-regulatory-requirement-extraction.md`.

## Scope

Repair the existing regulatory requirement extraction path. Reuse the
existing LLM protocol/OpenRouter implementation, normalized-document
pipeline, candidate repository, and provenance fields. Do not rebuild the
ingestion pipeline or begin Workstream 3 or later work.

## Confirmed diagnosis

The active extractor in `xportra/domain/ingestion.py` emits sentence-level
candidates only when a small deterministic expression matches terms such as
`shall`, `must`, or `may inspect`. The application service passes the
normalized document into this extractor and persists its results, but it does
not use the existing LLM client. Existing candidates are persisted with
source/artifact/job links; the repository stores location in JSON, so the
existing schema can retain supported source context without new columns.

## Implementation plan

1. Implement bounded overlapping chunks with section/page context and stable
   source offsets.
2. Use the configured existing LLM client for structured semantic
   requirement extraction; validate output and evidence against normalized
   source text.
3. Preserve explicit success, partial, failed, and manual-entry semantics;
   never fall back silently to deterministic extraction.
4. Wire the existing OpenRouter client through application/worker
   composition and persist valid candidates through the existing repository.
5. Add scripted-LLM unit tests and run extraction, ingestion, worker, and
   local `xportra_test` PostgreSQL regression tests.

## Acceptance criteria

- Requirements without `shall` or `must` can be extracted; explanatory,
  recommendatory, definitional, and irrelevant content is not returned as a
  binding obligation.
- Chunking preserves document order, source context, and exact quotation
  evidence; overlap duplicates are removed; failed chunks are visible.
- Malformed/empty model responses, unsupported quotations/references, API
  errors, timeouts, rate limits, and persistence failures never become
  success-shaped results.
- Valid candidates preserve existing provenance, remain unapproved, and are
  idempotent on retry.
- No migration, new provider, OCR, provenance redesign, or later workstream.

## Verification

Acceptance criteria were verified as follows:

- Semantic extraction tests cover requirements that lack `shall`/`must`,
  source-grounded quotes and context, chunk overlap, deduplication, malformed
  and empty responses, invalid source references, and provider failures.
- Candidate-service tests cover empty success, partial retry recovery,
  provenance, idempotency, and candidate persistence failure.
- PostgreSQL candidate-extraction and full-workflow integrations use the
  isolated local PostgreSQL 18.6 database `xportra_test` at
  `127.0.0.1:5432`; the database identity was checked before testing.
- No migration was added or applied. A SQL UUID cast was added to the
  existing job-creation query so registration placeholders with NULL
  `artifact_id` work correctly.

Commands and results:

```text
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_regulatory_requirements.py tests/unit/test_regulatory_candidate_extraction.py tests/unit/test_regulatory_ingestion_worker.py tests/unit/test_regulatory_ingestion_service.py tests/unit/test_global_staff.py tests/unit/test_identity_api.py
108 passed, 25 warnings, 6 subtests passed

$env:DATABASE_URL = 'postgresql://postgres@127.0.0.1:5432/xportra_test'
& '.\.venv\Scripts\python.exe' -m pytest -q tests/integration/test_regulatory_candidate_extraction_postgresql.py tests/integration/test_regulatory_full_workflow_postgresql.py
$code = $LASTEXITCODE
Remove-Item Env:DATABASE_URL
exit $code
15 passed, 0 skipped
```

The unit warnings are existing Starlette/httpx deprecation and short test JWT
key warnings; no test failed. Live OpenRouter/provider behavior was not called;
LLM behavior was verified with the existing scripted client. No new
limitations were found beyond the lack of a live-provider integration test.
`compileall` on changed Python files passed. Whitespace validation passed
with Git's `cr-at-eol` setting to account for the existing CRLF line endings
in the state documentation.

Relevant implementation and test files include:

- `xportra/domain/ingestion.py`
- `xportra/application/regulatory_candidate_extraction_service.py`
- `xportra/application/regulatory_ingestion_service.py`
- `xportra/application/regulatory_ingestion_worker.py`
- `xportra/infrastructure/rag_composition.py`
- `xportra/api/app.py`, `xportra/api/dependencies.py`,
  `xportra/api/regulatory_admin.py`, and `xportra/api/schemas.py`
- `xportra/persistence/repositories.py`
- `tests/unit/test_regulatory_requirements.py`,
  `tests/unit/test_regulatory_candidate_extraction.py`,
  `tests/unit/test_regulatory_ingestion_worker.py`,
  `tests/integration/test_regulatory_candidate_extraction_postgresql.py`,
  and `tests/integration/test_regulatory_full_workflow_postgresql.py`
- `ACTIVE_TASK.md`, `CURRENT_STATE.md`, and the ADR index

The worktree remains uncommitted on branch `fix/register-source-500` at
`d96280fe16ee923c96b684a50d0333df100df9ed`. No files were staged, committed,
or pushed. Pre-existing unrelated modifications and untracked files were
preserved.
