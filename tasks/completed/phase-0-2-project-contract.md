# Task: Phase 0.2 — Project Contract (Identity, Principles, Config, Dependencies, Boundaries, ADR)

**Phase:** Phase 0 — Agent Harness & Project Foundation
**Status:** Complete (2026-09-19) — all acceptance criteria verified
**Mirrors:** `ACTIVE_TASK.md` at repo root

## Objective

Establish the Xportra AI project contract — identity, scope, principles,
non-goals, configuration contract, dependency strategy, conceptual
system boundaries, and ADR-0001 — without implementing any application
functionality.

## Scope (from task brief §§1–7)

1. Product identity in `REQUIREMENTS.md` (PI-1..PI-5).
2. System principles in `REQUIREMENTS.md` (SP-1..SP-6).
3. Non-goals in `REQUIREMENTS.md` (NG-1..NG-6).
4. Configuration contract at `docs/architecture/configuration-contract.md`
   (variable names only; inherited `.env` name inventoried, untouched).
5. Dependency strategy at `docs/architecture/dependency-strategy.md`.
6. Conceptual boundaries at `docs/architecture/system-boundaries.md`.
7. `docs/decisions/ADR-0001-deterministic-applicability-authoritative.md`.

## Constraints

- No application functionality, database, APIs, RAG, or agents.
- No package installs; no `.venv` modification.
- No `.env` value exposure (names only); no `.env` modification.
- No invented regulatory requirements or detailed product functionality.
- No silent architectural decisions (ADR-0001 is the only new decision).

## Acceptance Criteria

- [x] `REQUIREMENTS.md` holds PI-1..PI-5, SP-1..SP-6, NG-1..NG-6, CD-1..CD-4.
- [x] Configuration contract documents all seven categories, names only the
      inherited variable, selects no providers.
- [x] Dependency strategy reuses `.venv` without making it source of truth.
- [x] `system-boundaries.md` shows the approved conceptual map as
      non-implementation.
- [x] ADR-0001 follows repo convention (context/decision/alternatives/
      consequences/links).
- [x] New docs do not contradict `REQUIREMENTS.md`, `INVARIANTS.md`,
      boundaries, or config docs.
- [x] Validation: required files exist; no secrets in docs; no app code;
      `.venv` unmodified; `.env` values unexposed; no fake tests.

## Completion

Complete 2026-09-19. All acceptance criteria verified (see `CURRENT_STATE.md`
"Last Verified (Phase 0.2)"). No application code, no installs, no `.venv` /
`.env` modifications, no secret values exposed. Moved to `tasks/completed/`.
