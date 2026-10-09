# qdrant-api-key-support — Complete

Single scoped task: minimal backwards-compatible `QDRANT_API_KEY`
support for Qdrant Cloud authentication. Complete 2026-10-08.

Origin: `tasks/completed/production-qdrant-provisioning.md` (§14.4
path (a)) + this explicitly assigned task. Traceability:
`REQUIREMENTS.md` TB-4 (Qdrant baseline), R-10.1 (hardening scope;
no behavior change except the additive optional key, no boundary
weakened).

## Implementation performed

- `xportra/infrastructure/rag_composition.py`:
  - `QDRANT_API_KEY_ENV = "QDRANT_API_KEY"` constant (exported).
  - `qdrant_api_key_from_environment()` — single parsing path:
    blank/missing/non-mapping → `None`; otherwise stripped value.
    Never raises, never logs, value never in any message.
  - `RAGInfrastructureConfig.qdrant_api_key: str | None`
    (`repr=False`, default `None`), populated in `from_environment`.
  - `compose_rag_stack` passes `api_key=config.qdrant_api_key`
    (`None` = exactly keyless behavior, verified against the
    installed client: accepted, no threads, no probe).
- `xportra/infrastructure/evidence_upload.py`:
  `compose_evidence_index_sync_from_environment` reads the same
  helper and passes it to its `QdrantClient` — both key-requiring
  paths (retrieval + upload indexing) stay in agreement via the one
  variable; no second config path, no duplicated parsing.
- No startup gate change: key absence never fails boot; missing URL
  / collection keep the exact existing fail-closed errors; no new
  connectivity (probe stays disabled); no architecture, collection,
  embedding, Supabase, or dependency change.

## Configuration

- `docs/architecture/environment-schema.md`: `QDRANT_API_KEY` entry
  (optional, secret, placeholder-only).
- `.env.example`: `QDRANT_API_KEY=` with keyless-default comment.
- `XPORTA-V1-DEPLOYMENT.md`: §3 new row, §14.1 auth row rewritten
  (wired-optional), §14.2 config block (+ key line), §14.4 caveat
  rewritten (support exists; set the key for Cloud), §14.5 step 2
  (key-header verification, wrong-key handling).
- Contract: required for Qdrant Cloud, optional for keyless
  deployments/development. No real key anywhere.

## Tests

- New `tests/unit/test_qdrant_api_key.py` (13 tests + 2 subtests,
  mocks only): key parsed/stripped/None-cases; config carries key
  with repr clean; both composers pass `api_key` through (present
  and `None` cases, `check_compatibility` still false); missing
  URL/collection still fail closed with key absent from messages;
  non-mapping safe.
- Regression: focused Qdrant/RAG/wiring/security/upload suites
  236 passed + 63 subtests; FULL `pytest tests`: **2073 passed,
  51 skipped (gated), 63 subtests, 0 failures**. No Qdrant Cloud
  contact, no model download, no OpenRouter, no packages.

## Files changed (this task only)

- `xportra/infrastructure/rag_composition.py`
- `xportra/infrastructure/evidence_upload.py`
- `tests/unit/test_qdrant_api_key.py` (new)
- `docs/architecture/environment-schema.md`
- `.env.example`
- `docs/deployment/XPORTA-V1-DEPLOYMENT.md`
- `ACTIVE_TASK.md`, `CURRENT_STATE.md`, this record (state)

Note: the tree also holds earlier uncommitted task changes — prior
work, untouched per the no-commit convention; this task's hunks are
limited to the list above.

## Remaining deployment steps

Qdrant Cloud auth is now supported — nothing further blocks on code.
User: create the Free Tier cluster via provider UI, set the four RAG
vars + `QDRANT_API_KEY` at Render-config time, run §14.5 (expect
reachable/correct/EMPTY), then Render service configuration +
backend deploy + §10 smoke. Ingestion-pipeline design remains a later
phase; no corpus exists by design.
