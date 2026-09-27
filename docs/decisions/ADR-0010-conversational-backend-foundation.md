# ADR-0010: Conversational backend foundation (Phase 10.2)

- Status: Accepted (implementation scope for Phase 10.2)
- Date: 2026-09-25
- Scope: Stateless, read-only conversational backend boundary; no
  persistence, no new LLM route, no mutations, no frontend

## Context

ADR-0009 and `docs/phases/conversational-product-architecture.md`
define conversation as a grounded interface over the existing
deterministic system, with open questions OQ-C1 (transcript
retention/audit), OQ-C2 (per-subject vs per-tenant visibility), OQ-C3
(chat LLM route and budgets), OQ-C4 (suggested evidence links in the
first increment), and OQ-C5 (groundedness evaluation before MVP).
Phase 10.2 must convert that design into a production backend
contract without silently inventing answers to those questions, and
without weakening Phases 1–10.1.

Two existing-architecture facts constrain the shape:

1. No workflow store exists: workflow records travel client-side and
   the server revalidates per request (Phase 8.2/8.3). A stateless
   per-request conversation contract follows the same precedent.
2. The validated Phase 5 RAG chain already answers grounded
   regulatory questions with citation-integrity validation
   (Phases 5.11–5.16). A second LLM/generation route is unjustified
   for a read-only foundation.

## Decision

1. **No conversation persistence in Phase 10.2.** No migration, no
   `conversations` / `conversation_messages` tables. The backend
   contract is stateless: conversation identity (a client-supplied
   correlation UUID) is validated for shape, never dereferenced, and
   never trusted as a record. OQ-C1 and OQ-C2 are therefore
   recorded as blocked (see below), not guessed.
2. **No new LLM invocation.** Shipment/compliance answers are
   deterministic renderings of already-authoritative state (fixed
   vocabulary, identifier citations). Regulatory answers reuse the
   injected Phase 5 RAG chain unchanged (existing budgets and
   configuration). OQ-C3 is resolved for this phase by avoidance; a
   separate chat route/budgets remain deferred.
3. **Read-only intents only, explicitly enumerated — never parsed
   from prose.** The request carries one allow-listed intent
   (`explain_requirement_state`, `explain_evidence_gaps`,
   `explain_finding`, `summarize_shipment_state`,
   `answer_regulatory_question`). No free-text intent classification
   exists. No mutating capability exists anywhere in the boundary
   (no upload/record/analyze/finalize/applicability/state change);
   OQ-C4 (suggested evidence links) is resolved as out of scope.
4. **Strict mode/context separation.** `shipment_aware` requires
   exactly one workflow record per request and revalidates it
   (shape + tenant match) on every call; `knowledge` forbids any
   workflow record structurally, so knowledge mode can never gain
   shipment context silently. Knowledge intent reuses tenant-scoped
   retrieval; shipment claims never appear in knowledge mode.
5. **Single stateless HTTP endpoint** (`POST
   /conversations/messages`, member-readable) reusing the existing
   auth, tenant, permission, and error boundaries. Stored-conversation
   endpoints (`POST /conversations`, `GET
   /conversations/{id}`) are deferred until persistence is approved.
6. **Grounding contract.** Shipment claims cite Xportra identifiers;
   regulatory claims carry the validated `[En]` citation mapping;
   anything established by neither is refused as unknown — never
   fabricated. No prompts, chain-of-thought, secrets, provider
   internals, raw evidence content, or cross-tenant data enter the
   response. OQ-C5's full harness stays deferred; contract-level
   tests (citation presence, refusal correctness, no-override) ship
   in this phase.

## Alternatives considered

1. **Persist conversations now (migration 011).** Rejected:
   retention/audit (OQ-C1) and visibility (OQ-C2) have no approved
   answers, and inventing a retention policy would create audit
   obligations by accident.
2. **Dedicated chat LLM call with new budgets.** Rejected: a second
   generation route duplicates the Phase 5 boundary, needs OQ-C3
   answers that do not exist, and is unnecessary for read-only
   deterministic-first answers.
3. **HTTP only after persistence.** Rejected: the stateless
   message contract is safely expressible per request (workflow
   precedent), and deferring all of HTTP would leave the application
   boundary unverified against the production error/security
   surface.

## Consequences

- Phase 10.2 adds `xportra/domain/conversation.py` (frozen
  contracts), `xportra/application/conversations.py` (stateless
  use case), one endpoint plus schemas, and focused tests. No
  existing behavior changes.
- Stored conversations, resumption, transcript export/search, and
  proposal/confirmation execution require future requirements
  resolving OQ-C1/OQ-C2 plus a migration and a Phase 10-style
  audit before any work begins.
- Blockers recorded (not guessed): OQ-C1, OQ-C2, full OQ-C5
  harness, OQ-C3 separate route/budgets.

## Open questions / blockers

- BLOCKED (persistence): OQ-C1 transcript retention/audit policy.
- BLOCKED (persistence): OQ-C2 per-subject vs per-tenant
  conversation visibility.
- DEFERRED: OQ-C3 separate chat LLM route and cost/latency
  budgets (not needed while no new LLM call exists).
- RESOLVED (out of scope): OQ-C4 suggested evidence links — Later.
- DEFERRED: OQ-C5 full groundedness evaluation harness (contract
  tests ship in 10.2).
