# tests — Test Organization

Run the scope appropriate to the change:

- `unit/` — isolated logic.
- `integration/` — component interactions.
- `regression/` — previously fixed defects.
- `evaluation/` — retrieval/LLM behaviour assessment.
- `fixtures/` — shared test data and helpers.

Do not create fake tests merely to make directories non-empty.
Per `INVARIANTS.md`, tests must not be bypassed, skipped, faked, or
weakened to make a task appear complete.
