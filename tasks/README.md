# tasks — Task Lifecycle

Only one task is active at a time (see `ACTIVE_TASK.md` at repo root).
Task files move through these directories:

- `backlog/` — approved but not yet scheduled.
- `active/` — the currently executing task (mirrors `ACTIVE_TASK.md`).
- `completed/` — finished tasks with acceptance criteria verified.
- `blocked/` — tasks that cannot proceed; each must state its blocker.

Moving a task between states requires updating `ACTIVE_TASK.md` and
`CURRENT_STATE.md`.
