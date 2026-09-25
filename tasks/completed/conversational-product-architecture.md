# Task: Conversational Product Architecture (specification only)

**Status:** Complete (2026-09-25) — specification delivered, no code written, no backend changed.

## Objective

Define the user-facing product architecture for Xportra AI with a first-class conversational assistant over the existing compliance, evidence, retrieval, and reasoning capabilities — without redesigning Phases 1–10.1.

## Deliverable

`docs/phases/conversational-product-architecture.md`: product value with mechanisms (§1) plus checklist-sufficient cases; user-facing product model (§2); shipment-aware and knowledge modes with MVP decision (§3); model MAY/MUST-NOT with presentation rules (§4); chat→system action boundary with intent table (§5); deterministic-first grounding and citation expectations (§6); tenant/shipment conversation context model (§7); UX recommendation — shipment panel + contextual Ask actions, no dedicated page (§8); MVP vs later scope (§9); text architecture diagram (§10); future phase impact recorded as unapproved proposals (§11); open questions OQ-C1–OQ-C5.

Also `docs/decisions/ADR-0009-conversational-boundary.md`: model-reads/determinism-writes boundary, confirmation-gated actions, tenant/shipment context rules, record exclusion.

## Verification

Every cited capability traced to an implemented contract: Phase 2/3 deterministic services, Phase 5 validated RAG (`RAGQueryResponse` citations), Phase 6 analyses/traces, Phase 7 workflow/history/readiness/terminal rules, Phase 8 endpoints/DTOs/permissions, Phase 9 workspace, Phase 10.1 hardening; raw `/rag/query` stays internal per the existing UI-spec constraint. No backend capability invented — unbuilt items (conversation boundary, transcript store, panel UI) marked FUTURE with required requirements/tasks noted.

## Result / Decision / Outcome

Design input for a future scoped phase. No implementation task is active; no Phase 10.2 started. Anything built later needs `REQUIREMENTS.md` entries and scheduled tasks first.
