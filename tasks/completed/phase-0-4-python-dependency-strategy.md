# Task: Phase 0.4 — Python Baseline & Dependency Strategy

**Phase:** Phase 0 — Agent Harness & Project Foundation
**Status:** In progress (2026-09-19)
**Mirrors:** `ACTIVE_TASK.md` at repo root

## Objective

Establish repository-level Python baseline and dependency declaration policy for
Xportra AI without implementing application functionality or modifying the
existing virtual environment.

## Scope

1. Inspect the current Python environment in `.venv` without changing it.
2. Document the selected Python baseline in `docs/architecture/python-runtime.md`.
3. Select a repository-level dependency declaration mechanism and establish the
   minimal project metadata needed for it.
4. Update `docs/architecture/dependency-strategy.md` to codify policy rules.
5. Update `REQUIREMENTS.md` to resolve OQ-2 and OQ-4.
6. Validate the repository state without installing packages or altering `.venv`.

## Constraints

- No application functionality.
- No provider selection for database, vector store, LLM, embedding, or
  observability layers.
- No package installs, upgrades, downgrades, or `.venv` recreation.
- No dependency list created by inspecting installed packages in `.venv`.
- No unnecessary dependencies or speculative package declarations.
- No application code or business logic implementation.

## Acceptance Criteria

- [ ] current Python environment inspected
- [ ] Python baseline documented
- [ ] dependency declaration mechanism selected
- [ ] repository dependency configuration established
- [ ] no unnecessary dependencies added
- [ ] `.venv` unchanged
- [ ] no packages installed
- [ ] no application functionality implemented
- [ ] documentation is internally consistent
- [ ] OQ-2 resolved
- [ ] OQ-4 resolved

## Notes

This task is intentionally policy-only. It establishes reproducible Python and
repository dependency policy for future project work without selecting any
production or application providers.
