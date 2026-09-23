# Phase 5.13 — RAG Application/API Boundary

**Status:** Complete and verified (2026-09-23)
**Phase:** Phase 5 — Retrieval & RAG
**Type:** Thin production-facing request/response boundary over the
completed Phase 5 chain — orchestration only; no retrieval, ranking,
selection, prompting, LLM, or validation logic reimplemented

> This record describes what was actually implemented and verified.

## Objective

Expose the completed Phase 5 RAG chain through one coherent operation:

```text
HTTP Request
    ↓
API/Application Boundary (this phase)
    ↓
Retrieval → Ranking → Context Selection → Prompt Construction
    → LLM → Answer Validation
    ↓
HTTP Response
```

The API orchestrates the existing domain/application contracts rather
than reimplementing them. Not implemented: authentication redesign,
streaming, background jobs, agents, semantic grounding, retries, tool
calling, model routing, or compliance decisions.

## Prior-art check

Minimum inspection found no existing RAG use-case boundary — only the
Phase 5.6/5.8 pipeline orchestrators and the Phase 1.8 resource API.
One stray untracked draft (`xportra/domain/rag_application.py`)
existed with a broken `xportra.domain.infrastructure` import that
prevented the entire `xportra.domain` package from importing; it was
rewritten as the proper pure-orchestration service (no competing
layer was created). The API reuses the Phase 1.8–1.10 application
shape (FastAPI router, `ApplicationServices` container, `MemberContext`
auth, `APIError` mapping) and extends it minimally.

## Application orchestration contract

`xportra/domain/rag_application.py`: `RAGApplicationService`,
`RAGApplicationContract` (runtime-checkable protocol), and
`build_rag_application_service`. One call:

```python
query(information_need, *, tenant_id, mode, context_budget,
      scope=None, top_k=DEFAULT_TOP_K, candidate_pool=None
      ) -> ValidatedAnswer
```

Delegation (each step forwards unchanged to its owning boundary):

1. `EvidenceContextPipeline.select_context` (Phase 5.8) — retrieval,
   ranking, and budgeted selection. Mode/scope/top-k validation
   stays where it already lives; this layer adds no mode and no
   silent conversion.
2. `CitationAwarePromptBuilder.build` (Phase 5.10) — prompt
   construction from the selection plus the normalized need.
3. `LLMClient.generate` (Phase 5.11) — the authoritative structured
   `EvidencePrompt` plus the injected `LLMGenerationConfig`; tenant
   travels as internal metadata only.
4. `GeneratedAnswer` construction — structural fail-closed check
   only (a non-`LLMResponse` return raises `DomainValidationError`;
   the infrastructure `answer_from_response` helper remains for
   standalone use).
5. `AnswerValidator.validate` (Phase 5.12) — citation integrity.
   The invalid-citation policy is owned by the injected validator
   instance, not by per-call flags. The returned `ValidatedAnswer`
   is the exact object the validator produced.

The service never retrieves, ranks, selects, builds prompts, calls
providers, parses citations, touches Qdrant/HTTP/DB, or imports any
infrastructure package (AST-verified). Tenant is a mandatory
execution-level keyword (`require_tenant_context`). No broad
exception handling anywhere: every collaborator failure propagates
unchanged and never becomes an empty success.

## API endpoint and HTTP contract

`POST /rag/query` (`xportra/api/router.py`), following the existing
no-version-prefix route convention. Authorization reuses the
existing boundary: `require_permission(READ_TENANT_RESOURCE)` —
both `owner` and `member` roles may query; unknown roles fail
closed with `403 permission_denied`.

## Request contract

`RAGQueryRequest` (`extra="forbid"` via `APIRequest`):

- `information_need: str` — required, 1–4000 chars (the upper bound
  is an API-layer guard; the domain owns presence/normalization).
- `mode` — `"semantic" | "lexical" | "hybrid"` (Literal allowlist
  mirroring `RETRIEVAL_MODES`), default `"hybrid"` (an API-layer
  default; the domain still validates membership).
- `max_context_characters: StrictInt > 0`, default 4000 (API-layer
  default; `EvidenceContextBudget` owns budget semantics; strict
  ints preserve the domain's bool rejection through the schema).
- `top_k: StrictInt > 0`, default `DEFAULT_TOP_K` (5, reused — no
  competing constant).
- `candidate_pool: StrictInt > 0 | None`, default `None`.
- `scope` — optional object with exactly the four canonical
  `EvidenceRetrievalScope` dimensions (`source_id`, `source_type`,
  `document_id`, `document_version`); unknown dimensions rejected.

Never accepted: tenant identity (body `tenant_id` or
`scope.tenant_id` → 422), provider settings/model routing/API
keys, raw prompts, embedding configuration, vector filters, or
Qdrant parameters.

## Tenant-resolution path

`authenticated principal → MemberContext → member.tenant →
TenantContext → domain chain`. The handler passes `member.tenant`
only; the request body cannot supply or override it. Missing
context → `401 authentication_required` before any service runs.
Cross-tenant domain failures propagate as rejections, never
successes, and error bodies carry no tenant identifiers.

## Dependency injection

`ApplicationServices.rag` holds the `RAGApplicationService` (or a
contract-compatible fake); `get_rag_service` resolves it per
request and fails closed with `503 rag_not_configured` when the
chain is unwired (the default: `from_environment` wires only the
Phase 1.x persistence services — no live Qdrant/LLM construction
happens at startup). No route handler constructs pipelines,
clients, validators, or SDK objects. Tests inject deterministic
fakes through `create_app(services=...)`.

Generation configuration (`LLMGenerationConfig`) is server-side
application configuration, injected at construction — never
caller-controlled. Credentials (`LLM_API_KEY`) stay in
`LLMSettings`/environment and never enter domain values or
responses.

## Response contract

`RAGQueryResponse`: `answer_text` (verbatim), `status`
(`valid | invalid_citations | empty`), `is_empty`,
`extracted_references`, `invalid_references`, and `citations`
(`label`, `rank_position`, plus evidence identifiers/source
pointers: `chunk_id`, `document_id`, `chunk_index`, `source_id`,
`source_type`, `source_location`, `document_version`,
`content_fingerprint`).

Omitted by design: tenant identity, raw evidence content,
embedding contract, scores, secrets, headers, SDK objects, and
vector-store internals. Provenance is never silently discarded —
every validated citation resolves through the domain mapping.

## Citation representation

Built exclusively from `ValidatedAnswer.validated_citations`
(the authoritative `PromptCitation` objects). Nothing is parsed or
reconstructed from answer text in the API layer (`[E1]` text alone
is never treated as authoritative). The `invalid_citations`
structured status (non-raising validator path) is preserved as a
successful response with `invalid_references` populated.

## Error mapping

| Condition | Status | Code |
|---|---|---|
| Malformed body / unknown fields / bad types / oversized need / bad mode / bad ints | 422 | `validation_error` |
| Whitespace-only need / bad scope value / malformed LLM output / cross-tenant domain failure | 409 | `domain_validation_error` |
| Citation-integrity failure (`AnswerValidationError`) | 422 | `citation_integrity_error` |
| Retrieval failure (`VectorStoreError`) | 502 | `vector_store_error` |
| LLM failure (`LLMProviderError`: timeout/auth/rate-limit) | 502 | `llm_provider_error` |
| Missing auth / bad token | 401 | `authentication_required` / `invalid_token` |
| Role not permitted | 403 | `permission_denied` |
| RAG chain unwired | 503 | `rag_not_configured` |
| Unexpected failure | 500 | `internal_error` |

`AnswerValidationError` stays distinguishable from
`LLMProviderError` (separate handlers; MRO lookup keeps the
specific `422` ahead of the generic `409`). Operational failures
never become successful empty answers. Error bodies carry no
traces, credentials, headers, provider text, or infrastructure
details.

## Empty-answer semantics

Phase 5.11/5.12 semantics preserved end to end: empty model output
→ HTTP 200 with `status="empty"`, `is_empty=true`, verbatim
`answer_text` — distinct from provider failure (502), validation
failure (422), and invalid citations. No fallback text fabricated,
no retry, no model substitution.

## Security boundary

Information needs are untrusted input; evidence is untrusted
context; model output is untrusted output returned verbatim as
inert JSON text (never executed, never rendered as HTML). The
Phase 5.10 structural prompt separation is reused as-is — no new
ad-hoc sanitization layer in the route. No filesystem, SQL/code
execution, tool calls, outbound URLs, tenant impersonation, or
credential exposure (response bodies test-scanned for secrets,
SDK names, and tenant identifiers).

## Explicitly excluded

Vendor LLM adapters, streaming/WebSockets, retries, agent loops,
tool calling, semantic entailment/grounding, legal/compliance
decisions, autonomous actions, background processing, arbitrary
model routing, multiple endpoints, and per-phase HTTP endpoints.

## Files created / modified

- Created: `xportra/domain/rag_application.py` (rewrote stray
  broken draft), `tests/unit/test_rag_api_boundary.py`,
  `docs/phases/phase-5-13-api-boundary.md`.
- Modified (additive only): `xportra/domain/__init__.py` (RAG
  exports), `xportra/api/schemas.py` (RAG contracts),
  `xportra/api/errors.py` (three handlers),
  `xportra/api/dependencies.py` (`rag` field + resolver),
  `xportra/api/router.py` (`POST /rag/query`).
- No Phase 5.1–5.12 behavior file modified; no prior test touched.

## Verification

- Focused Phase 5.13: 42/42 passing
  (`tests/unit/test_rag_api_boundary.py`).
- Phase 5.1–5.13 focused: 603/603 passing.
- Full suite: 1071 passed + 32 skipped (`DATABASE_URL`
  unconfigured — PostgreSQL integration, same as baseline), 0
  failures, 0 errors.
- Import checks: `xportra.domain`, `xportra.api.app` (with
  `/rag/query` in the route table) import cleanly; the previous
  broken-import state is resolved.
- Domain purity: AST tests prove `xportra/domain` imports no
  HTTP/provider/infrastructure modules and the API layer contains
  no vector/provider SDK usage.
- Skipped: the 32 `DATABASE_URL`-gated PostgreSQL integration
  tests (environment limitation, not a code gap).
- Unresolved: production wiring of the RAG chain (Qdrant +
  embeddings + LLM adapter in `ApplicationServices`) is future
  work — the route fails closed with 503 until then. Phase 5
  remains open pending the project's phase-completion decision.
