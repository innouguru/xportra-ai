# Phase 10.6 — Conversational Frontend MVP

> Implemented 2026-09-27 under `REQUIREMENTS.md` R-10.6.
> First user-facing conversational interface over the
> existing Phase 10.2 backend (`POST
> /conversations/messages`). No backend file changed; no
> persistence, mutation, proposal execution, or provider
> work. Task record:
> `tasks/completed/phase-10-6-conversational-frontend-mvp.md`.

## 1. Where conversation appears

One shared shipment-scoped side panel
(`ConversationPanel`), mounted once in the
`WorkspacePage` shell behind a `ConversationProvider`,
so every workspace screen uses the same surface:

- Workspace Overview — "Ask Xportra about this shipment"
- Requirements ledger rows — per-requirement ask
- Gaps gap blocks — per-gap ask
- Findings cards — per-finding ask (optional
  `askAction` prop; Report/Package/FinalReview cards
  unchanged)
- Evidence bottom action row — page-level entry
- Analysis readiness action row — page-level entry

No dedicated `/chat` page exists. No implementation
is duplicated across pages: entry points are one
`AskXportraButton` opening the panel with a seed
(mode, intent, requirement/evidence identity,
suggested text, focus).

## 2. Supported modes

- **This shipment** (`shipment_aware`, primary): sends
  the client-held workflow record plus seeded
  requirement/evidence identities. The panel header
  shows a human shipment label (short reference ·
  workflow state) — never a workflow ID. Unavailable
  without an active shipment.
- **Regulatory knowledge** (`knowledge`, separated):
  mode radio with an explicit "shipment context is
  never sent" description. Switching modes rebuilds
  the request without workflow/requirement/evidence
  fields and resets incompatible intents, so shipment
  context cannot leak into knowledge turns.

## 3. API contract used

Exactly `POST /conversations/messages` with the
backend `ConversationMessageRequest` shape
(`conversation_id` per panel opening, mode, one
allow-listed intent, `user_text`, workflow /
requirement / evidence identities only where
permitted, `information_need` for regulatory
questions; server defaults otherwise). Typed
interfaces in `types/api.ts`; `api/conversations.ts`
transports turns and surfaces errors unchanged; no
`any` anywhere in the feature.

## 4. Context rules

Tenant identity comes only from authenticated
membership (existing auth boundary). Requirement and
evidence identities come only from backend-returned
records (UUID-guarded at entry points; drafts that
are not UUIDs open the panel without an identity).
Knowledge requests carry no workflow, shipment, case,
requirement, or evidence fields — asserted by test.

## 5. Read-only limitation

The panel can only send message turns. No upload,
record, analysis, finalize, applicability, or state
change is reachable: the feature imports no mutating
API module (only `postConversationMessage`), renders
no confirmation cards, and has no tool calling.
Tested: every fetch issued during a turn targets
`/conversations/messages`.

## 6. Presentation and trust

User and Xportra turns are visually distinct in
editorial product language (paper surfaces, teal
user turns, rule lines — no chatbot chrome).
Assistant answers render: verbatim status badge,
"Explanation" (summary text), and "Xportra record"
(identifier chips + `[En]` citations with source
pointers); refusals render the refusal reason with no
fabricated claims. Empty state offers suggestion
chips per mode/focus (prompts only, asserting
nothing). Loading, API, auth, and empty-reference
states all render honestly through existing
`ErrorNotice`/`LoadingState` semantics.

## 7. Accessibility and responsive

Native labeled controls (mode radiogroup, intent
select, labelled textarea, labelled submit);
`role="dialog"` with Escape close, focus trap,
focus-on-open, and focus return; `role="log"`
`aria-live="polite"` message list; text+dot status
badges; inherited focus outlines and control-height
targets; reduced-motion support. Desktop drawer
becomes a bottom sheet under 860px via the same
breakpoint convention; fluid panel width
(`min(26rem, 100%)`), wrapping references, sticky
composer. Verified statically and in jsdom; no
browser engine was available, so no pixel-perfect
claim is made.

## 8. Verification

- Focused: `api/conversations.test.ts` (3),
  `lib/conversation.test.ts` (4),
  `features/conversation/ConversationPanel.test.tsx`
  (17) — 24/24 passing, covering all 16 required
  areas (entry, open/close/Escape, context display,
  shipment vs knowledge payloads, rendering, loading,
  API/401 errors, refusals, empty references,
  contextual seed, drawer structure, read-only fetch
  audit, labels/live-regions/focus).
- Six existing page suites updated only to provide
  the `ConversationProvider` production always
  supplies; one assertion refined to name the
  read-only Ask entry as the sole terminal-screen
  button (same strictness, documented).
- Full frontend suite: **30 files / 181 tests
  passing** (baseline 27/157; +3 files, +24 tests),
  0 failures. `npx tsc --noEmit` clean.
  `npm run build` succeeds.
- Backend untouched (no backend suite re-run
  required): contract re-read, no defect found.
  Live services not executed (no environment), as
  before. No packages installed.

## 9. Explicitly NOT implemented

Persistence, transcript store, migration, tool
calling, mutations, proposal/confirmation cards,
voice, notifications, analytics, multi-shipment
comparison, provider migration, deployment changes,
backend redesign, in-chat upload, unrelated
redesign. OQ-C1/C2 remain blocked; OQ-C3 avoidance,
OQ-C4 out-of-scope, and OQ-C5 deferral all hold
unchanged. No commit/push performed.
