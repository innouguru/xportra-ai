# Conversational Product Architecture — Xportra AI

> Design/architecture only (2026-09-25). No code written, no backend
> changed, no behavior exists. Every capability below is mapped to an
> already-implemented deterministic service, endpoint, or DTO; anything
> not yet built is marked FUTURE. Nothing here overrides Phases 1–10.1.

## 0. Relationship to existing constraints

`docs/phases/ui-product-architecture.md` states that the RAG machinery
(`POST /rag/query`) "supports analysis internally and must NOT become a
user-facing chatbot screen." This document preserves that constraint:
the proposal is NOT a raw chat box over `/rag/query`. It is a
shipment-grounded assistant whose answers are composed from
deterministic application state first (workflow record, stored report,
readiness, history) and from validated, citation-checked retrieval
second — with the model forbidden from deciding, mutating, or
overriding anything. The raw RAG route stays internal.

## 1. Product value

### Why Xportra instead of a notebook, checklist, or spreadsheet

Each claim below names its mechanism — the existing system that does
the work — so value is traceable, not asserted.

1. **Determining applicable requirements.** A checklist assumes the
   exporter already knows which rules apply. `ComplianceApplicabilityService`
   (Phase 3.1) evaluates each regulatory requirement against the
   exporter's facts (origin, destination, commodity, product category,
   actor role) and returns `applicable` / `not_applicable` / `unknown`
   with a deterministic reason. The exporter answers questions about
   their shipment; the system derives the regulatory universe.
2. **Connecting requirements to authoritative sources.** Spreadsheet
   rows go stale and lose provenance. Every requirement retains the
   chain requirement → normalized document → artifact → regulatory
   source with authority, jurisdiction, version, and status (Phase 0.6
   source framework, Phase 2.x). The assistant cites these instead of
   reciting memorandum text.
3. **Organizing shipment evidence.** Evidence is recorded once as a
   tenant-owned reference and explicitly linked to requirements
   (`record_with_requirements`, Phase 8). The workspace shows, per
   requirement, which evidence supports it and its review status —
   replacing scattered folders and file names.
4. **Identifying missing information.** `AssessmentReadinessService`
   (Phase 7.3) computes structured readiness with typed issue codes
   (`missing_shipment_reference`, `no_analysis`, `analysis_stale`,
   …). "What am I missing?" is a deterministic read, not an LLM guess.
5. **Understanding why something is flagged.** A finding carries its
   full derivation: applicability outcome, assessment state,
   supporting/conflicting evidence, sufficiency, contradiction state,
   uncertainty, and the six-step decision trace (Phase 6.5). The
   assistant explains by walking this chain — every sentence traceable
   to a stored identifier.
6. **Re-evaluating after new evidence.** Supplying evidence and
   re-running analysis is an explicit loop (`supply_evidence` →
   `run_analysis`, Phases 7.1/8), with stale-round detection so a new
   result never silently replaces review of the old one. The assistant
   reports exactly what changed between rounds.
7. **Preserving assessment provenance.** `WorkflowHistoryService`
   (Phase 7.4) projects the full journey (creation, shipment binding,
   supplies, analyses, final package) as identifiers. The terminal
   `AssessmentPackage` plus stored report/analyses/traces (Phase 8.4)
   form a reusable, re-verifiable package — a spreadsheet cannot prove
   what was known, when, and on what basis.
8. **Reducing repeated manual compliance research.** Regulatory
   knowledge questions ("what documents are normally required for
   Nigerian cocoa to the EU?") are answered by the validated RAG chain
   (Phases 5.11–5.16) with citations to indexed authoritative sources,
   instead of re-reading guidance PDFs per shipment.

### Where a checklist remains sufficient

Xportra should not pretend otherwise. A paper checklist or spreadsheet
is sufficient when ALL of these hold: a single stable regulation
governs the shipment; one product and one destination market are
involved; the exporter has done the route before with no changes;
evidence needs are fixed and unambiguous; and no second party (buyer,
bank, regulator) asks for provenance. Xportra earns its place when any
of these break: unfamiliar destination, new product, disputed or
missing evidence, or a need to prove the basis of a decision.

## 2. Product model

| Concept | User-facing? | Persistence | Notes |
|---|---|---|---|
| Organization / tenant | Yes (as "workspace") | Persistent (existing memberships) | Isolation root; never selectable by clients |
| Shipment | Yes | Persistent intent; TODAY the workflow record is client-held (no server workflow store — see ui spec §11.2) | The thing the exporter cares about |
| Compliance assessment | Yes (as "findings review") | Persistent via result store (reports/analyses/traces) | Read-only once produced |
| Evidence | Yes | Persistent (tenant-owned records) | Reference-based, never raw bytes in chat |
| Requirement | Yes (as ledger rows) | Shared regulatory data (not tenant-owned) | Never invented |
| Finding | Yes | Derived per requirement per analysis | applicability + assessment + explanation + provenance |
| Assessment package | Yes (terminal artifact) | Persistent linkage, finalized exactly once | Never versioned or reopened |
| Conversation | Yes (assistant thread) | FUTURE, tenant-owned (see §7) | Proposed persistent; NOT part of the assessment record |

Implementation details that stay hidden: embeddings, chunks, prompts,
fingerprints, round linkage mechanics, retrieval scores, provider
identity, DTO internals.

## 3. Conversational modes

### Mode A — Shipment-aware assistant (core MVP)

The assistant operates inside an active shipment context: it can see
the workflow record, the latest stored report, readiness, and history
for THIS shipment only. Canonical questions:

- "Why is this requirement still open?" → requirement + assessment +
  evidence + reasoning context for that requirement.
- "What evidence am I missing?" → readiness issues + missing-information
  items, quoted verbatim from deterministic state.
- "I just supplied this certificate. What changed?" → round
  comparison: new supplies, re-analysis outcome deltas, staleness
  cleared or introduced.

### Mode B — Regulatory knowledge assistant (constrained MVP)

No active shipment required. Answers general regulatory questions
("what documents are normally required to export Nigerian cocoa to
the EU?") using ONLY the validated RAG chain: retrieved evidence with
`[En]` labels, citation-integrity validation, source pointers. No
shipment data is visible in this mode, and shipment claims are never
made.

### MVP decision

Both modes belong in the MVP because they share one boundary and one
trust model, but with strictly separated contexts: Mode A reads
deterministic shipment state first and retrieval second; Mode B reads
retrieval only. A mode-B conversation can never see shipment data, and
a mode-A conversation can never answer from retrieval what
deterministic state already decides (e.g., applicability outcomes are
quoted, never re-derived by the model).

## 4. Chat responsibilities

### The model MAY

- Explain requirements in plain language, citing the requirement text
  and its authoritative source.
- Summarize findings, readiness, and history by restating deterministic
  outputs (counts, states, reasons) without altering them.
- Explain missing information using the stored missing-items and
  readiness issue codes.
- Retrieve authoritative regulatory information through the validated
  RAG chain and present it with citations.
- Explain evidence relationships (which evidence supports/conflicts
  with which requirement, and its review status).
- Answer questions grounded in the current shipment's stored state.
- Guide the user through the workflow ("the next step is X; it is
  owner-only; the endpoint will enforce readiness").

### The model MUST NOT

- Independently declare a shipment compliant (no verdicts, no scores —
  the system has no verdict field by design).
- Override deterministic applicability or assessment state.
- Convert `unknown` into `satisfied`, or missing evidence into
  non-compliance (missing stays missing; contradictions stay preserved).
- Resolve contradictions (describe both sides with provenance).
- Invent requirements, evidence, regulatory sources, citations,
  identifiers, or timestamps.
- Bypass tenant isolation or cross shipment boundaries.
- Make finalization decisions or claim an assessment is final (only
  the stored package + `is_closed` predicate speak to finality).
- Mutate domain state directly (see §5).

Presentation rule: deterministic states render with their fixed
vocabulary (`unknown` → "Not yet determined — [reason]"); model prose
is visually and structurally separated from quoted system state, and
model text may never be displayed as system state.

## 5. Chat → system action boundary

The model proposes; the application disposes. Conversation maps to the
existing deterministic services through an explicit intent table; every
mutating intent executes as the ALREADY-IMPLEMENTED use case with its
unchanged authz, tenant, readiness, and terminal checks. The model has
no tool that writes domain state.

| User intent (example) | System mapping (existing) | Effect |
|---|---|---|
| "What am I missing?" | `assess_case_readiness` + readiness gate | Read-only answer |
| "Why is requirement R open?" | stored report finding + trace + evidence refs | Read-only answer |
| "What documents do I need for cocoa to the EU?" | validated RAG query (Mode B) | Read-only, cited |
| "Analyze this shipment again." | `AnalysisApplicationService.run_analysis` (owner-only) | Proposed action → explicit user confirmation → existing endpoint |
| "I supplied the phytosanitary certificate." | evidence intake flow (`record` → `supply_evidence`) | Guided steps; each step is the existing endpoint, user-confirmed |
| "Finalize this assessment." | `finalize_stored_package` (review-gated, terminal) | Proposed action → explicit confirmation → existing endpoint enforces readiness/staleness/terminal rules |

Boundary rules:

1. Read intents execute immediately (they only read the caller's own
   tenant data through the same tenant-scoped paths as the UI).
2. Mutating intents NEVER execute from model output alone: the
   assistant presents the exact action with its preconditions
   (permission, readiness) and the user confirms in the UI; execution
   calls the existing endpoint with the existing `ApplicationContext`.
3. The model never sees or handles credentials, tokens, raw document
   bytes, or other tenants' data; tool inputs are identifiers and
   allow-listed parameters only.
4. Failed preconditions (403, 409, terminal) are reported verbatim
   from the endpoint error — the model does not reinterpret or retry
   around them.

## 6. Grounding architecture

Deterministic-first, retrieval-second:

1. **Shipment facts** (status, findings, gaps, history, package):
   deterministic application DTOs are sufficient. No retrieval, no LLM
   judgment. The model restates and explains.
2. **Regulatory knowledge** (what a regulation says, what documents a
   route normally needs): Phase 5 retrieval is REQUIRED — constrained
   to the tenant-filtered corpus, citation-validated (Phase 5.12),
   with source pointers. Unvalidated or empty answers follow the
   existing failure semantics (never silent, never invented).
3. **Evidence content questions** ("what does my certificate say?"):
   answered from stored evidence REFERENCES and linked findings, not
   by dumping raw content into context. Raw document/evidence contents
   stay out of conversation context (Phase 10.1 logging/content rule
   extended to chat context).
4. **Reasoning explanations** ("why was this assessed satisfied?"):
   the stored `ComplianceAnalysis` + decision trace for that
   requirement; the model narrates the chain without adding steps.

Citation/source expectations: every regulatory claim carries its
`[En]` citation + source pointer (as in `RAGQueryResponse`); every
shipment claim carries the identifier it came from
(`requirement_id`, `evidence_id`, `report_id`, `workflow_id`); claims
with neither are forbidden and must be refused with an explicit
"unknown" rather than completed.

## 7. Conversation context and tenant isolation

- **Ownership:** a conversation is tenant-owned and bound to the
  authenticated subject that started it (actor recorded, as in
  `ApplicationContext.actor_id`). FUTURE persistence.
- **Tenant relationship:** exactly one tenant per conversation, resolved
  server-side from membership like every other request. The tenant is
  never a message field, a tool argument, or model-inferred.
- **Shipment relationship:** optional, exactly one workflow per
  shipment-bound conversation. The workflow record is pinned at bind
  time; staleness rules apply (a finalized workflow's conversation
  becomes read-only, mirroring terminal closure).
- **Context boundaries (allow-list):** the pinned workflow record,
  the latest stored report + readiness + history projection for that
  workflow, tenant-filtered retrieval hits for the current question,
  and the conversation's own prior turns. Nothing else enters context:
  no other shipments, no other tenants, no raw blobs, no secrets.
- **Retrieval into conversation:** tenant filter mandatory (as in
  `find`/`find_lexical`); hits carry identifiers + source pointers,
  never raw content beyond the validated answer text.
- **Shipment switch:** changing shipment starts (or resumes) a
  different conversation context explicitly — context is never merged
  across shipments. The UI confirms the switch and shows which
  shipment the assistant is answering from at all times.
- **Resumption:** conversations may be resumed by the same tenant
  (FUTURE: subject-scoped visibility); resumption re-pins and
  re-validates workflow linkage rather than trusting stored context.
- **Assessment record:** conversations are NOT part of the permanent
  assessment record. The final package, history projection, and stored
  results are the record; transcripts are operational data (FUTURE:
  retention policy), exportable on demand but never admissibility
  evidence and never shown as findings.

A conversation must never become a cross-boundary mechanism: any
request for another tenant's or another shipment's data is refused
with the existing `tenant_mismatch`/`not_found` semantics, and such
refusals are not elaborated on (no existence oracle).

## 8. UX architecture

Constraint: do not redesign the Phase 9 workspace; the assistant lives
inside it.

**Recommendation: shipment-scoped chat panel + contextual "Ask Xportra"
actions — no dedicated assistant page.**

- **Shipment chat panel:** a collapsible side panel available on all
  workspace screens for the current shipment (Evidence, Gaps, Analysis,
  Review, History). It inherits the shipment context visibly (header:
  "Answering about shipment …"), so Mode A is the default and there is
  no ambiguous global chat that could mix shipments.
- **Contextual "Ask Xportra" actions:** beside each finding,
  requirement row, gap block, and history entry — deep-linking the
  panel with a preformed, pinned question ("Why is REQ-… still open?")
  whose answer cites exactly that object. This is where "why is this
  flagged" lives closest to the flag.
- **Knowledge questions (Mode B):** asked from the shipment panel with
  an explicit mode indicator, or from a workspace-level entry point
  with NO shipment pinned. The panel always shows which mode and which
  shipment (if any) is active.
- **Action proposals:** rendered as structured cards (action, target,
  preconditions, Confirm/Dismiss) that call existing endpoints —
  never as free-text instructions the user must retype.
- **Mobile behavior:** the panel becomes a bottom sheet over the same
  screens; contextual actions collapse into the finding/gap detail
  views. No separate mobile flow.
- **What is NOT recommended:** a dedicated assistant page (recreates
  the forbidden generic chatbot screen and invites context ambiguity);
  proactive pop-up nudges in MVP (later, §9); model prose rendered
  with system-state styling (forbidden, §4).

## 9. MVP boundary

### MVP (smallest useful slice)

1. Shipment panel + contextual "Ask Xportra" on findings, gaps, and
   requirements (read-only Q&A over deterministic state).
2. Missing-information and why-flagged answers with identifier
   citations (§6).
3. Mode-B knowledge Q&A through the validated RAG chain with `[En]`
   citations and source pointers.
4. Next-action guidance ("run analysis", "supply evidence") as
   proposal cards executed through existing endpoints with
   confirmation (analysis/re-analysis included; finalization proposed
   but gated exactly as today).
5. Tenant/shipment scoping, refusal semantics, and presentation rules
   (§4, §7).

The MVP demonstrates value iff a user can resolve "why is this open,
what is missing, what changed, what does the regulation require" —
each answer traceable to system state or cited sources — without ever
seeing an unverified model claim presented as fact.

### Later (explicitly not MVP)

Proactive nudges and follow-ups; multi-shipment comparison; voice
input; conversation export/attachment to the package; transcript
search and analytics; suggested evidence auto-linking (model proposes
links, user confirms, existing association endpoint executes);
offline/mobile-app chat; cost/latency budgets and streaming controls;
conversation-aware evaluation harness.

## 10. Architecture diagram

```text
User (authenticated subject, tenant membership)
  │
  ▼
Conversational UI (Phase 9 workspace: shipment panel + Ask actions)
  │  shows mode + pinned shipment; proposal cards Confirm/Dismiss
  ▼
Conversation / application boundary (FUTURE, Phase 8-style)
  │  ├── authorization: MemberContext + require_permission (existing)
  │  ├── tenant isolation: server-resolved tenant; shipment pinning;
  │  │   allow-listed context only; refusals = existing error codes
  │  └── intent routing: READ intents answer; MUTATING intents propose
  ▼
Deterministic context / services (existing, authoritative)
  │  ├── workflow record, stored report, readiness, history, evidence
  │  └── use cases: run_analysis, supply/record evidence, finalize…
  │      (unchanged checks: role, tenant, readiness, terminal)
  ▼
Retrieval / reasoning (existing, on demand only)
  │  ├── Phase 5 validated RAG (tenant-filtered, citation-checked)
  │  └── Phase 6 stored reasoning (narrated, never re-decided)
  ▼
Grounded response
   ├── quoted system state (fixed vocabulary) + identifier citations
   ├── cited regulatory claims ([En] + source pointers)
   └── proposal cards for actions (user-confirmed, endpoint-executed)

Deterministic compliance authority sits BELOW the model: the model
reads determinism, never writes it. Citations attach at the boundary,
before rendering. Authorization and tenant isolation wrap every layer.
```

## 11. Phase impact (FUTURE — not implemented)

Items below require `REQUIREMENTS.md` entries and scheduled tasks
before any work begins. No backlog/phase scope is created here.

- **Phase 8 application layer:** new conversation boundary (intent
  routing, context assembly, proposal cards), transcript store use
  cases, citation-assembly rule (deterministic quotes + validated
  citations). Additive; existing use cases unchanged.
- **Phase 9 frontend:** shipment chat panel, "Ask Xportra" actions,
  mode/shipment indicator, proposal-card components, mobile bottom
  sheet. Presentation only.
- **Phase 10 production hardening:** reuse (auth, tenant checks,
  5xx sanitization, header policy); new audit surface for the
  conversation endpoints (prompt/content hygiene, refusal semantics,
  transcript retention). No hardening assumption is weakened.
- **Database schema:** FUTURE migration for `conversations` /
  `conversation_messages` (tenant FK, optional workflow linkage,
  actor, context snapshot references — never raw blobs or secrets).
- **API contracts:** new additive endpoints (start/resume conversation,
  send message, confirm proposal) with tenant/shipment-scoped DTOs;
  no existing contract changes; proposal confirmation reuses existing
  operation endpoints.

## Open questions

- OQ-C1: transcript retention policy and whether transcripts are
  subject to audit/export obligations.
- OQ-C2: per-subject vs per-tenant conversation visibility for
  resumed threads.
- OQ-C3: LLM provider/route for chat turns (reuse the OpenRouter seam
  vs a separate configuration) and cost/latency budgets.
- OQ-C4: whether "suggested evidence links" (model-proposed,
  user-confirmed) belongs in the first MVP increment.
- OQ-C5: evaluation harness for groundedness (citation precision,
  refusal correctness, no-override property) before MVP ships.
