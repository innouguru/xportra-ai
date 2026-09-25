# ADR-0009: Conversational interaction boundary

- Status: Accepted (design only — no implementation)
- Date: 2026-09-25
- Scope: Future conversational assistant; constrains all later chat work

## Context

Phase 10.1 completed production hardening of the existing API. A
product question remained: how conversational interaction fits Xportra
without becoming a generic chatbot that undermines deterministic
compliance authority. The canonical analysis is recorded in
`docs/phases/conversational-product-architecture.md`. The existing UI
spec (`docs/phases/ui-product-architecture.md`) already forbids
exposing raw `POST /rag/query` as a user-facing chatbot screen.

## Decision

1. Conversation is a grounded interface over existing capabilities,
   not a new decision-maker: the model reads deterministic state and
   validated retrieval; it never writes domain state.
2. All conversational actions execute through the existing Phase 8
   use cases and endpoints with unchanged authorization, tenant,
   readiness, and terminal checks; mutating intents require explicit
   user confirmation in the UI.
3. Deterministic compliance authority is absolute over model text:
   applicability, assessment, unknown/missing/contradiction semantics,
   and finalization rules cannot be overridden, re-derived, or
   restyled by the model.
4. Tenant isolation extends to conversation context: one tenant per
   conversation, optional single-shipment pinning, allow-listed
   context, no cross-shipment or cross-tenant access, existing refusal
   semantics.
5. Conversations are not part of the permanent assessment record; the
   final package, history projection, and stored results remain the
   sole record.
6. Raw document/evidence contents and secrets stay out of conversation
   context and logs (Phase 10.1 rules extended).

## Alternatives considered

1. **Raw chat box over `/rag/query`.** Rejected: violates the existing
   UI-spec constraint, bypasses deterministic context, and invites
   unverified claims presented as compliance truth.
2. **Agentic model with state-mutating tools.** Rejected: contradicts
   the application boundary (all writes flow through tenant-validated
   use cases) and would create a second, unaudited authorization path.
3. **No conversation at all (workspace only).** Rejected as a product
   direction because "why is this flagged / what is missing / what
   changed" questions are currently answered only by manual
   cross-screen comparison; a grounded assistant answers them from
   already-stored state. Deferred to post-MVP only if building it
   threatens hardening or determinism work.

## Consequences

- Any future chat implementation must route reads through
  tenant-scoped application paths and writes through existing,
  user-confirmed endpoints; a design that gives the model direct
  mutation tools violates this ADR.
- Future work requires requirements entries, tasks, a conversation
  transcript schema migration, and a Phase 10-style security audit of
  the new endpoints before shipping.
- Linked design doc:
  `docs/phases/conversational-product-architecture.md`.
- No code, schema, or contract changed by this ADR.
