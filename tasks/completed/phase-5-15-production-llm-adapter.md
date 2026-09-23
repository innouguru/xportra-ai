# Phase 5.15 — Production LLM Provider Adapter & Wiring (Completed 2026-09-23)

One real provider adapter behind the existing `LLMClient`
contract. Mirrors `ACTIVE_TASK.md`; full record in
`docs/phases/phase-5-15-production-llm-adapter.md`.

## Scope delivered

- `OpenRouterLLMClient` (OpenRouter/TB-5 over declared `httpx`,
  no vendor SDK) + constants/exports in
  `xportra/infrastructure/llm.py`.
- Composition auto-wiring (`llm_base_url`, `llm_timeout_seconds`;
  explicit injection still wins; fail-closed preserved).
- `LLM_BASE_URL` + `LLM_TIMEOUT_SECONDS` schema entries.
- `tests/unit/test_llm_provider_adapter.py`: 47 focused tests;
  gated `tests/integration/test_llm_openrouter_live.py`.
- Three minimal task-mandated contract corrections (one 5.11
  assertion, two 5.14 tests) — documented, no weakening.

## Acceptance

All Phase 5.15 acceptance criteria verified (see `ACTIVE_TASK.md`
at completion time): focused 47/47; Phase 5.1–5.15 focused
696/696; full suite 1164 passed + 34 skipped (gated integration
tests). No domain behavior modified. Phase 5 remains open.
