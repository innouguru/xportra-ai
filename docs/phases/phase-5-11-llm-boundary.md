# Phase 5.11 — LLM Invocation & Answer Boundary

**Status:** Complete and verified (2026-09-23)
**Phase:** Phase 5 — Retrieval & RAG
**Type:** Provider-independent LLM contract + minimal provider-neutral
infrastructure seam — no vendor SDK, no live API, no answer
validation, no compliance reasoning

> This record describes what was actually implemented and verified.

## Objective

Establish the first explicit boundary between the deterministic
evidence/prompt subsystem (Phases 5.1–5.10) and an external LLM:

```text
EvidencePrompt            (Phase 5.10 — authoritative, structured)
      ↓
LLMClient (protocol)      (provider-independent domain contract)
      ↓
LLMResponse               (normalized, provider-independent)
      ↓
GeneratedAnswer           (application wrapper — answers, not verdicts)
```

Not implemented in this phase: citation correctness validation,
prompt-injection detection, compliance reasoning, tool use,
autonomous actions, API exposure, retries, streaming, agentic loops,
model routing, or any concrete vendor SDK integration.

## Prior-art check

No LLM/provider abstraction existed (verified: no LLM module, class,
or test; the only prior artifacts are the canonical `LLM_API_KEY` /
`LLM_MODEL` environment variables in
`docs/architecture/environment-schema.md`). The repository's
established external-provider pattern — domain protocol
(`EmbeddingProvider`) + infrastructure adapter
(`QdrantEvidenceVectorIndex`) with operation/cause error translation
(`VectorStoreError`) — was followed exactly. No competing
abstraction was created.

## Provider-independent contract

`xportra/domain/llm.py`:

- **`LLMClient`** — runtime-checkable protocol: `generate(prompt, *,
  configuration, tenant_id=None) -> LLMResponse`. Implementations
  live in infrastructure and wrap exactly one provider SDK; the
  domain depends only on this protocol, never a vendor SDK.
- **`LLMGenerationConfig`** — frozen, validated, deliberately
  minimal: `model_identifier` (non-empty string), `temperature`
  (finite, `[0.0, 2.0]` — the range both major provider families
  support), `max_output_tokens` (positive int). Booleans, strings,
  `None`, NaN, and infinities rejected fail-closed via
  `DomainValidationError`. No provider-specific fields (top_p, stop
  sequences, penalties) are invented — adapters translate the
  canonical config into their own request formats.
- **`LLMResponse`** — the canonical crossing representation, never a
  raw SDK object: `generated_text`, `model_identifier`, plus
  explicitly optional `finish_reason`, `usage` (`LLMUsage` with
  optional token counts), and `provider_name`. No secrets, no API
  keys, no request headers are ever stored; the canonical record has
  exactly the canonical keys (frozen slots prevent smuggling
  provider fields).
- **`GeneratedAnswer`** — the answer-boundary wrapper binding the
  authoritative prompt, the untrusted response, and internal tenant
  metadata. `answer_text` / `is_empty` / `to_record()` (which
  re-exposes the citation mapping). It deliberately performs NO
  citation validation — the architecture leaves room for a future
  answer-validation layer.

## Provider adapter boundary

`xportra/infrastructure/llm.py` — the smallest provider-neutral seam
necessary, containing **no vendor SDK and no network I/O**:

- **`LLMSettings`** — canonical credential/model configuration
  (`LLM_API_KEY` secret, `LLM_MODEL`) via the established
  `DatabaseSettings.from_environment` pattern. The secret lives only
  on this frozen settings object — never on responses, answers,
  prompts, or any domain value object (test-proven).
- **`ScriptedLLMClient`** — deterministic `LLMClient` implementation
  holding canned responses and scripted failures, so every domain
  failure semantic is testable without live credentials. It records
  calls, never mutates the prompt, never retries, executes nothing,
  and stores no secrets.
- **`answer_from_response`** — the fail-closed answer-boundary seam
  (thin composition only).
- **`LLMConfigurationError`** — missing canonical environment config.

No concrete vendor adapter (OpenAI/Anthropic/OpenRouter) is
introduced; live provider integration tests are therefore not
applicable, and the default suite requires no credentials. When a
vendor adapter is added later, it must translate provider
request/response formats into the canonical contracts, receive
credentials only through `LLMSettings`, and translate raw SDK
exceptions into `LLMProviderError` — never into empty answers.

## Failure semantics (fail closed)

- **Configuration failure** — `DomainValidationError` at
  construction, before any external call.
- **Provider/infrastructure failure** — network, authentication,
  timeout, and rate-limit errors are translated at the
  infrastructure boundary into `LLMProviderError(operation, cause)`
  (added to `xportra/domain/errors.py`, mirroring
  `VectorStoreError`; original exception preserved as `cause` with
  identity). Never converted into `""`, `None`, or `[]`.
- **Malformed provider response** — `LLMResponse` validation rejects
  malformed text/model/usage/finish-reason/provider-name fail-closed.
- **Empty model output** — documented policy: the adapter returns the
  response as received (the model is the authority on its own
  output) with `is_empty` as an explicit, auditable flag; no answer
  text is fabricated; `GeneratedAnswer.is_empty` lets the future
  answer-validation layer treat emptiness as a distinct state. This
  is a deliberate middle path: fabricating content was rejected
  (fail-closed principle), while raising would conflate "model chose
  to return nothing" with operational failure — operational failures
  already have their own dedicated `LLMProviderError` channel.

## Retry ownership

No automatic retries — none exist project-wide to inherit. A single
failure produces exactly one `generate` call (test-proven). Retries
affect cost, latency, rate limits, and idempotency; they must be
designed deliberately at a future boundary, not hidden inside an
adapter.

## Tenant handling

`tenant_id` travels as **internal invocation metadata only** — it
never enters model-visible text. Test-proven: the tenant UUID and
chunk id appear in none of the model-visible components (system
instructions, information need, evidence context, rendered preview).
The structured `to_record()` provenance legitimately includes tenant
as internal audit metadata — it is not model input. No tenant
identifier is added to prompts unless a future explicit product
requirement demands it.

## Security boundary

All generated model output is untrusted. The adapter only obtains
output — it never executes generated code/SQL, invokes tools,
performs filesystem operations, or triggers external actions
(test-proven: dangerous-looking model text is returned verbatim as
text; the seam's public API surface is `generate` + call records
only). Model output never manufactures citations:
`EvidencePrompt.citations` remain the only authoritative evidence
references; text like `[E7]` in output proves nothing about citation
correctness and is preserved verbatim, unvalidated.

## Prompt immutability

The adapter receives the authoritative structured `EvidencePrompt`
(`assertIs`-verified through the seam) — it is never reconstructed
from `render()`. Prompt, citations, evidence, and provenance are
unchanged after both successful and failed invocations
(snapshot-proven); all objects are frozen.

## Citation limitations

Explicitly out of scope: citation correctness validation, citation
repair, reference resolution from model text, and any claim that a
generated reference maps to real evidence. The `GeneratedAnswer`
record exposes the prompt's citation mapping so the future
answer-validation boundary can compare untrusted output against
authoritative references.

## Purity / dependency separation

- Domain (`xportra/domain/llm.py`): AST-verified to import only
  `dataclasses`/`typing`/`math`/`__future__` plus sibling domain
  modules — no vendor SDK, HTTP, or infrastructure imports.
- Infrastructure (`xportra/infrastructure/llm.py`): no vendor SDK
  (AST-verified) — a provider-neutral seam only.
- No vendor SDK is imported anywhere at runtime (test-proven).

## Test strategy

53 focused tests (`tests/unit/test_llm_boundary.py`), all
deterministic — no live LLM, no network, no credentials: config
validation (model, temperature range, max tokens, bool/None/string
rejection, provider-field rejection), response normalization
(optional fields, malformed rejection, no-leak record keys, empty
flag), invocation forwarding (prompt/config/tenant identity through
the seam, protocol conformance), prompt immutability (success and
failure paths, frozen objects, citation mapping), failure semantics
(provider/timeout/auth/rate-limit translation with cause identity,
single-call no-retry), empty-output policy, answer boundary
(wrapper, malformed inputs, unvalidated citations, record),
credential handling, security (no execution, no execution-capable
API surface, no tenant leakage into model-visible text), and
adapter isolation (AST checks both directions). The prompt under
test is built through the real Phase 5.5/5.7 chain.

## Deferred

- Concrete vendor adapters and live-provider (opt-in) integration
  tests — when added, credentials come only via `LLMSettings`.
- Answer validation: citation correctness, untrusted-output policy,
  hallucination handling.
- Prompt-injection detection/enforcement beyond the Phase 5.10 data
  boundary.
- Retries, streaming, tool use, agentic loops, model routing.
- FastAPI exposure.

## Implementation

- `xportra/domain/llm.py` (new), `LLMProviderError` added to
  `xportra/domain/errors.py`, `xportra/infrastructure/llm.py` (new),
  additive exports in both packages' `__init__.py`.
- `tests/unit/test_llm_boundary.py`: 53 focused tests.
- No Phase 5.1–5.10 behavior file was modified (only the additive
  error class and exports).

## Verification

- Focused Phase 5.11: **53/53**.
- Phase 5.1–5.10 focused re-runs and complete tree: see
  `CURRENT_STATE.md`.
- Import check: all new symbols resolvable from `xportra.domain` and
  `xportra.infrastructure`.

Phase 5 is not marked complete by this phase alone; Phase 5.12 has
not started.
