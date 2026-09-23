# Phase 5.15 — Production LLM Provider Adapter & Wiring

**Status:** Complete and verified (2026-09-23)
**Phase:** Phase 5 — Retrieval & RAG
**Type:** One real provider adapter behind the existing
`LLMClient` contract, plus composition wiring — no contract
redesign, no second provider, no retries

> This record describes what was actually implemented and verified.

## Selected provider

OpenRouter (TB-5 baseline), spoken to through its
OpenAI-compatible `POST {base}/chat/completions` API over
`httpx` — an already-declared project dependency. No vendor SDK
was introduced, honouring the Phase 5.11 "no SDK in domain or
seam" direction as far as the task permits (see contract
corrections below).

## Adapter boundary

`OpenRouterLLMClient` (`xportra/infrastructure/llm.py`)
implements `generate(prompt, *, configuration, tenant_id=None)
-> LLMResponse`. The transport is a small explicit boundary: an
`httpx.Client` may be injected (deterministic tests use
`MockTransport`); otherwise one finite-timeout client is built
for the adapter's lifetime (`close()` releases owned clients).

## Request translation

The structured `EvidencePrompt` is translated field by field
inside the adapter: `system_instructions` → system message; a
deterministically built user message carrying
`question_heading`, the verbatim information need,
`evidence_heading`, and the verbatim evidence context (or the
explicit no-evidence marker when empty). Preserved exactly:
system text, need, evidence, citation labels, evidence order.
Never summarized, truncated, reordered, rewritten, or
tenant-tagged. `LLMGenerationConfig` maps to `model`,
`temperature`, `max_tokens` — no other parameter exists on the
wire; `top_p`/stops/reasoning controls were not added.

## Response translation

Provider payload → canonical `LLMResponse`: `content` (string;
`""` preserved as valid empty per Phase 5.11), `model`
(preferred when a non-empty provider string, else the
configured identifier), `finish_reason` (optional),
`prompt_tokens`/`completion_tokens`/`total_tokens` → `LLMUsage`
(optional), `provider_name="openrouter"`. The raw payload never
escapes.

## Error translation

Every listed failure becomes `LLMProviderError("generate",
cause)` with the underlying cause preserved: 401/429/5xx via
`raise_for_status`, timeouts, connection errors, invalid JSON,
missing/empty choices, missing/non-dict message, missing/
non-string content (`None` is a failure; `""` is empty
success), unexpected root shapes, malformed usage/finish
fields. Never an empty answer, `None`, or `[]`. Malformed
*our-side* inputs (non-prompt, non-config) stay
`DomainValidationError`, preserving the Phase 5.11 split.

## Timeout / retry behavior

One `generate` call performs exactly one POST (test-counted on
success, HTTP-error, and timeout paths). No retry loops,
backoff, failover, or model substitution; httpx performs no
implicit retries. Explicit finite timeout (default 60 s,
`LLM_TIMEOUT_SECONDS` override); a timeout is an
`LLMProviderError`, delivered to the existing 502 mapping.

## Credential handling

`LLM_API_KEY` from the canonical boundary only (still the only
key variable). Sent per-request as a Bearer header on a
secret-free shared client; never in `LLMResponse`/repr/logs/
API responses/snapshots (test-asserted on bodies, captured
logs, and reprs).

## Tenant handling

Tenant UUID never enters system/user content (test-asserted on
the serialized body); it remains internal invocation metadata,
and the provider never establishes identity.

## Security

Provider output is untrusted inert text: no execution, tools,
files, URLs, or state mutation; no citation validation in the
adapter (Phase 5.12 owns it). Logs carry provider name, model,
latency, finish, and emptiness only.

## Deterministic testing

`tests/unit/test_llm_provider_adapter.py` (47 tests): contract,
response, 12 failure cases, single-attempt proofs, security,
prompt-snapshot immutability (success AND failure paths),
frozen response, composition wiring, and two HTTP end-to-end
tests (valid cited answer with provenance + provider-500 →
502) through the real domain graph with a `MockTransport`
adapter. No network, no credentials, no downloads.

## Optional live integration testing

`tests/integration/test_llm_openrouter_live.py`: gated on
`OPENROUTER_LIVE_TEST=1` plus `LLM_API_KEY`/`LLM_MODEL`; builds
a real selection through ranker/selector/builder (no Qdrant),
calls the live provider with `max_output_tokens=64`, and
asserts canonical shape + validator mechanics (status in
`valid|invalid_citations|empty`) rather than model wording. No
hardcoded credentials; skipped in ordinary runs.

## Limitations / explicitly deferred

Single provider only (no routing/failover); no streaming, tool
calling, agents, retries/backoff policy, semantic grounding,
answer rewriting, or compliance decisions. Live Qdrant + live
LLM combined verification still awaits a live Qdrant
environment.

## Composition wiring

`RAGInfrastructureConfig` gains `llm_base_url` (default
`https://openrouter.ai/api/v1`, `LLM_BASE_URL` override) and
`llm_timeout_seconds` (default 60, `LLM_TIMEOUT_SECONDS`
override, validated). `compose_rag_stack` auto-builds the
production adapter when no explicit client is given (explicit
injection still wins); missing LLM credentials still fail
closed at configuration. `from_environment_with_rag()` needs
no client argument anymore. `ScriptedLLMClient` remains for
deterministic tests; the API layer still constructs no
transport (AST-verified).

## Configuration

`.env.example` + `environment-schema.md` gained `LLM_BASE_URL`
(optional) and `LLM_TIMEOUT_SECONDS` (optional, default 60).
No other configuration changed; no credentials committed.

## Prior-test contract corrections (minimal, task-mandated)

Phase 5.15 §§2/7/14 explicitly require the httpx-based
production adapter and its auto-wiring, superseding three
assertions of the pre-adapter contract:

- `test_llm_boundary.py::test_infrastructure_seam_has_no_vendor_sdk`:
  `httpx` (declared generic transport, not a vendor SDK)
  removed from the forbidden set; `openai`/`anthropic`/
  `requests`/`urllib` stay forbidden.
- `test_rag_composition.py::test_missing_llm_client_fails_clearly`
  → `test_invalid_llm_client_fails_clearly` (non-client seam
  object still fails closed).
- `test_wiring_entry_point_rejects_missing_llm` →
  `test_wiring_entry_point_autowires_production_llm` (entry
  point wires the adapter; missing-credential fail-closed
  remains covered by config tests).

No assertion was weakened: every corrected test still proves
its original guarantee (no vendor SDK; fail-closed seams)
under the new specified behavior. All other prior tests pass
unmodified.

## Files created / modified

- Modified (additive): `xportra/infrastructure/llm.py`
  (adapter + constants), `xportra/infrastructure/__init__.py`
  (exports), `xportra/infrastructure/rag_composition.py`
  (base-URL/timeout config + auto-wiring),
  `xportra/api/dependencies.py` (optional client docstring/
  signature), `.env.example`, `environment-schema.md`.
- Created: `tests/unit/test_llm_provider_adapter.py`,
  `tests/integration/test_llm_openrouter_live.py`,
  `docs/phases/phase-5-15-production-llm-adapter.md`.
- Corrected per above: one assertion in
  `test_llm_boundary.py`, two tests in
  `test_rag_composition.py`. No domain behavior modified.

## Verification

- Focused Phase 5.15: 47/47 passing.
- Phase 5.1–5.15 focused: 696/696 passing.
- Full suite: 1164 passed + 34 skipped (32 `DATABASE_URL` +
  Qdrant smoke + live-LLM gate), 0 failures, 0 errors.
- Import/export checks pass; domain purity CLEAN (domain
  imports no HTTP/SDK/infrastructure); API builds no
  provider transport (AST).
- Live provider test: skipped (gate off) — not run, no
  credentials present.
- Unresolved: live-provider verification against real
  credentials; combined live Qdrant + live LLM verification.
  Phase 5 remains open pending the phase-completion decision.
