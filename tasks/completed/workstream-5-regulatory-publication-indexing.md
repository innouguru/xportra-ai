# Workstream 5 — Connect Approved Publication to Qdrant

**Status:** Complete — implementation and focused verification passed.

## Authorization

Explicit user authorization on 2026-11-05 supersedes the R-4D planning-only
gate only for this scoped task. See ADR-0025.

## Scope

Connect approved regulatory publication to the existing PostgreSQL, in-process
worker, deterministic evidence chunking/embedding, Qdrant, and retrieval
infrastructure. Preserve the existing architecture and tenant isolation.

## Acceptance criteria

- Publishing an eligible requirement durably schedules indexing without
  making Qdrant availability part of the publication transaction.
- Index work is retryable, recoverable, observable, and safe to repeat.
- Indexed regulatory points are explicitly marked as global regulatory
  content, distinct from tenant-owned evidence.
- Retrieval returns only the requesting tenant's permitted points and
  currently eligible, published global points. It never returns other
  tenants' evidence.
- Unpublished, rejected, withdrawn, superseded, and otherwise ineligible
  regulatory points are excluded using authoritative PostgreSQL state,
  including while asynchronous Qdrant cleanup is pending.
- Publication changes, content changes, and source lifecycle changes
  reconcile the Qdrant representation without overwriting existing tenant
  points.
- Existing tenant-only retrieval and index behavior remain intact.
- Focused unit and database integration tests cover publication scheduling,
  retry/recovery, eligibility and removal, global-plus-tenant retrieval,
  cross-tenant exclusion, and unchanged tenant-only behavior.
- No production database or unverified Qdrant endpoint is used. Live Qdrant
  testing is performed only if an existing development/test collection can
  be identified safely.

## Boundaries

- Reuse existing PostgreSQL, in-process worker, Qdrant collection,
  embeddings, chunking, and retrieval. No new queue or worker framework.
- No OCR, new extraction strategy, Qdrant deployment, RAG redesign, or
  dashboard redesign.
- Do not stage, commit, or push.
- Preserve all unrelated pre-existing modifications and untracked files.

## Verification

Run focused vector-index/retrieval and regulatory publication tests, relevant
ingestion regression tests, local `xportra_test` integration tests for any
schema/persistence changes, and Python compilation/static checks. Report exact
commands and distinguish skipped or blocked live-Qdrant checks.

## Completion record

- Unit tests:
  `.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_regulatory_publication_index_service.py tests/unit/test_evidence_retrieval.py tests/unit/test_evidence_index_sync.py tests/unit/test_regulatory_ingestion_worker.py tests/unit/test_rag_composition.py`
  — 161 passed, 1 Starlette/httpx deprecation warning.
- PostgreSQL integration tests, with
  `DATABASE_URL=postgresql://postgres@127.0.0.1:5432/xportra_test`:
  `.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_regulatory_publication_index_postgresql.py`
  — 6 passed, 0 skipped. This includes a requirement metadata change that
  changes its publication fingerprint and schedules reindexing. Only local
  PostgreSQL 18.6 `xportra_test` was used.
- Python compilation:
  `.\.venv\Scripts\python.exe -m compileall -q xportra tests` — passed.
- `git -c core.whitespace=cr-at-eol diff --check` — passed. No files were
  staged, committed, or pushed.
- Live Qdrant validation was not attempted because no verified development
  or test collection was available.
