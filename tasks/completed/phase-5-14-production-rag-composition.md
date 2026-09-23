# Phase 5.14 — Production RAG Composition & Infrastructure Wiring (Completed 2026-09-23)

Single explicit composition root wiring the Phase 5 chain to real
infrastructure. Mirrors `ACTIVE_TASK.md`; full record in
`docs/phases/phase-5-14-production-rag-composition.md`.

## Scope delivered

- `xportra/infrastructure/rag_composition.py`: `RAGInfrastructureConfig`,
  `SentenceTransformerEmbeddingProvider` (TB-6 baseline, lazy),
  `compose_rag_stack` / `compose_rag_stack_from_environment`,
  `RAGComposition` (+ `ensure_collection`), `RAGConfigurationError`.
- `ApplicationServices.from_environment_with_rag` (opt-in lifecycle
  wiring; default startup unchanged).
- `pyproject.toml` declarations; `EMBEDDING_DIMENSIONS` schema entry.
- `tests/unit/test_rag_composition.py`: 46 focused tests; gated
  `tests/integration/test_rag_qdrant_smoke.py`.

## Acceptance

All Phase 5.14 acceptance criteria verified (see `ACTIVE_TASK.md`
at completion time): focused 46/46; Phase 5.1–5.14 focused
649/649; full suite 1117 passed + 33 skipped
(`DATABASE_URL`/`QDRANT_URL` unconfigured). No Phase 5.1–5.13
behavior modified; no prior test weakened. Phase 5 remains open.
