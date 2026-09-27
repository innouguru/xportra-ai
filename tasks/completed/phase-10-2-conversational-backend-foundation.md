# Phase 10.2 — Conversational Backend Foundation (Complete, 2026-09-25)

Scope: `REQUIREMENTS.md` R-10.2; decisions in
`docs/decisions/ADR-0010-conversational-backend-foundation.md`;
design in `docs/phases/conversational-product-architecture.md` +
ADR-0009. Stateless, read-only backend contract only.

## Acceptance criteria

- [x] Frozen domain contracts (`xportra/domain/conversation.py`):
  identity separation, modes, roles, messages, citations, status.
- [x] Stateless application use case
  (`xportra/application/conversations.py`): auth actor, tenant
  isolation, context resolution + revalidation, mode validation,
  allow-listed intents, DTO mapping; no compliance-engine
  duplication; no mutations.
- [x] Grounding contract: identifier citations (shipment),
  validated `[En]` citations (regulatory), refused-unknown
  otherwise; no prompt/CoT/secret/provider/raw-content leakage.
- [x] No migration; no transcript store (OQ-C1/OQ-C2 blocked).
- [x] One endpoint (`POST /conversations/messages`) reusing
  existing auth/tenant/permission/error/security boundaries.
- [x] Focused tests: 39/39 passing. Full backend suite: 1823
  passed + 44 skipped (gated), 0 failures; no Phase 1–10.1
  behavior change.
- [x] Phase doc + state updates; no commit until instructed.

## Blockers

- OQ-C1 (retention/audit) and OQ-C2 (visibility): persistence
  deferred, no migration.
