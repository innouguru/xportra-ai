# AGENTS.md — Permanent Operating Instructions for Xportra AI

This file is the authoritative operating contract for all coding agents
(human or automated) working on Xportra AI. It must be read first, before
any other project file or implementation work.

## 1. Source of Truth

Repository documentation is the source of truth for project continuity,
not chat history.

- `AGENTS.md` — permanent operating instructions (this file).
- `CURRENT_STATE.md` — what is true about the project right now.
- `ACTIVE_TASK.md` — the single task currently in progress.
- `REQUIREMENTS.md` — approved requirements; the only valid origin for work.
- `INVARIANTS.md` — architectural invariants that must never be violated.
- `ROADMAP.md` — approved development phases.
- `docs/architecture/` — system design and component contracts.
- `docs/decisions/` — Architecture Decision Records (ADRs).
- `tasks/` — lifecycle of discrete work items.

Every future implementation task must be traceable to a documented
requirement in `REQUIREMENTS.md` or an approved decision recorded in
`docs/decisions/`.

## 2. Required Workflow

Every task MUST follow this sequence:

```text
Read AGENTS.md
        ↓
Read CURRENT_STATE.md
        ↓
Read ACTIVE_TASK.md
        ↓
Read relevant REQUIREMENTS.md sections
        ↓
Read relevant architecture documentation / ADRs
        ↓
Inspect the existing implementation
        ↓
Create a concise implementation plan
        ↓
Implement only the active task
        ↓
Run appropriate tests and quality checks
        ↓
Update project state
        ↓
Report what changed, tests run, and remaining issues
```

Do not skip steps. Do not combine unrelated changes into one task.

## 3. Operating Rules

1. Do not implement application/business features unless they are defined
   in `REQUIREMENTS.md` or explicitly assigned via `ACTIVE_TASK.md`.
2. Do not invent requirements. If a requirement is missing or ambiguous,
   stop and record it as an open question instead of assuming an answer.
3. Do not install packages unless absolutely necessary for the task itself.
   Never modify `.venv` destructively (no deletion, recreation, or upgrade
   without an approved task).
4. Never expose, print, commit, or copy secret values from `.env` or any
   secret store. Configuration changes must reference variable names only.
5. Do not delete existing files unless explicitly instructed.
6. Use Markdown documentation for persistent project state. State that only
   exists in chat is considered lost.
7. Do not make architectural decisions silently. Any change to structure,
   boundaries, data flow, storage, or cross-cutting concerns requires an
   ADR in `docs/decisions/` before implementation.
8. Do not mark work complete unless its acceptance criteria have been
   satisfied and verified.
9. Keep unrelated changes out of each task. One active task = one scoped
   change.
10. Business logic must not be moved into API handlers merely for
    convenience (see `INVARIANTS.md`).
11. Tests must not be bypassed, skipped, faked, or weakened to make a task
    appear complete.

## 4. Task Lifecycle

- Only one task is active at a time, described in `ACTIVE_TASK.md`.
- Task files live under `tasks/`:
  - `tasks/backlog/` — approved but not yet scheduled.
  - `tasks/active/` — the currently executing task (mirrors `ACTIVE_TASK.md`).
  - `tasks/completed/` — finished tasks with acceptance criteria verified.
  - `tasks/blocked/` — tasks that cannot proceed; must state the blocker.
- Moving a task between states requires updating `ACTIVE_TASK.md` and
  `CURRENT_STATE.md`.

## 5. Testing and Quality

- Run the appropriate test scope for the change:
  - `tests/unit/` for isolated logic.
  - `tests/integration/` for component interactions.
  - `tests/regression/` for previously fixed defects.
  - `tests/evaluation/` for retrieval/LLM behaviour assessment.
- Do not create fake tests merely to make directories non-empty.
- Report tests run, results, and any remaining issues at the end of
  every task.

## 6. State Updates

After completing work on the active task:

1. Update `CURRENT_STATE.md` to reflect what was actually done and verified.
2. Update `ACTIVE_TASK.md` — mark complete only if all acceptance criteria
   pass; otherwise record remaining work.
3. Move the task file to `tasks/completed/` or `tasks/blocked/` as
   appropriate.
4. Ensure no secrets were written into documentation or logs.

## 7. Continuity Contract

A new agent with no prior context must be able to reconstruct project
status solely from this repository. If it cannot, documentation is
incomplete and fixing it takes priority over new work.
