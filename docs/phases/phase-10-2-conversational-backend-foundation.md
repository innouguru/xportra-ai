# Phase 10.2 — Conversational Backend Foundation

> Implementation record (2026-09-25). Stateless, read-only backend
> contract only. No migration, no transcript store, no new LLM
> route, no mutations, no frontend. Binding decisions:
> `docs/decisions/ADR-0010-conversational-backend-foundation.md`;
> requirement: `REQUIREMENTS.md` R-10.2.

## Scope resolution (OQ-C1–OQ-C5)

No open question was answered by invention. Disposition:

- OQ-C1 (transcript retention/audit): BLOCKED — no retention
  policy approved, therefore no persistence and no migration.
- OQ-C2 (per-subject vs per-tenant visibility): BLOCKED — moot
  without persistence; authorization rule established (members
  converse over their own tenant's data; actor recorded).
- OQ-C3 (chat LLM route and budgets): resolved for this phase
  by avoidance — no new LLM invocation exists; knowledge
  answers reuse the injected Phase 5 RAG chain with its
  existing budgets/configuration. A separate chat route stays
  deferred.
- OQ-C4 (suggested evidence links): OUT — Later per the
  approved architecture; no link proposal exists.
- OQ-C5 (groundedness evaluation): full harness DEFERRED;
  contract-level tests ship here (citation presence, refusal
  correctness, no-override).

## What was built

- `xportra/domain/conversation.py` (new): frozen contracts —
  `ConversationIdentity` (correlation only, never a record
  key), `ConversationContext` (knowledge mode structurally
  forbids shipment identity), `UserMessage` (one allow-listed
  intent, never parsed), `ShipmentCitation` (identifier-only
  shipment claims), `CitationReference` (validated `[En]`
  mapping: identifiers + source pointers, no content/scores),
  `AssistantResponse` (`grounded` / `partial` /
  `refused_unknown`; refused carries a reason and no
  references). Conversation identity ≠ case ≠ workflow ≠
  assessment-result identity by construction.
- `xportra/application/conversations.py` (new):
  `ConversationApplicationService.handle_message` — the
  Phase 10.2 message flow (context → mode/intent validation →
  per-request workflow revalidation → tenant match →
  optional injected RAG → deterministic rendering →
  grounding validation). Shipment answers quote the
  revalidated workflow record; regulatory answers carry the
  validated RAG answer through unchanged; empty retrieval is
  refused as unknown. No mutating import or identifier exists
  in the module (AST-verified in tests).
- HTTP: `POST /conversations/messages`
  (`xportra/api/conversations.py` new; schemas in
  `xportra/api/schemas.py`; router included in
  `xportra/api/app.py`). Member-readable
  (`READ_TENANT_RESOURCE`), `ApplicationContext` from
  server-resolved membership + actor, one use-case call,
  existing error mapping. Stored-conversation endpoints
  deliberately absent (nothing is stored).
- Additive exports in `xportra/domain/__init__.py` and
  `xportra/application/__init__.py`. No existing file's
  behavior changed (`app.py` include, `schemas.py`
  additions only).

## Verification

- Focused: `tests/unit/test_conversational_backend.py` —
  39/39 passing (domain contracts, isolation, context
  binding, mode separation, lifecycle, grounding,
  authorization, error mapping, cross-tenant rejection,
  malformed input, no-mutation incl. AST check).
- Full backend suite: 1823 passed + 44 skipped (gated
  Postgres/Qdrant/OpenRouter-live, not executed), 0
  failures — the 1784-test Phase 10.1 baseline plus 39 new,
  no regressions.
- Invariants hold: deterministic state authoritative (quoted,
  never re-derived); unknown/missing/contradiction semantics
  untouched (no verdict text exists); tenant isolation
  server-side; chat mutates nothing; transcripts are not
  records (none exist); Phase 5/6 contracts unchanged;
  Phase 10.1 security in force (central handlers reused).

## Explicitly not implemented

Frontend chat UI; persistence/migration; stored-conversation
endpoints; proposal/confirmation execution; autonomous tool
calling; conversational mutations; suggested evidence links;
voice/notifications/analytics; multi-shipment conversations;
provider changes; deployment/Docker/hosting; dashboards;
full groundedness harness.

## Remaining blockers

OQ-C1 and OQ-C2 block stored conversations, resumption
semantics, and transcript export. Any such work requires new
requirements, a migration, and a Phase 10-style audit.
