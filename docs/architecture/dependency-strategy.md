# Dependency Strategy — Xportra AI

> Repository-managed dependency policy for Xportra AI.
> No packages were installed or modified in `.venv` for this task.

## Position

1. The repository configuration is the source of truth for dependencies.
2. `.venv` is disposable infrastructure and may be recreated or replaced
   without changing the project contract.
3. Dependencies must be explicitly declared before they become project
   dependencies.
4. Transitive packages must not be manually treated as direct dependencies.
5. Dependency versions must be controlled.
6. Adding a dependency requires a project task and justification.
7. Dependency upgrades should be deliberate and validated.
8. Production dependencies and development/test dependencies should be
   distinguishable.
9. The existing copied `.venv` may contain packages that Xportra AI does not
   use.
10. No package should be considered part of Xportra AI merely because it
    exists in `.venv`.

## Selected mechanism

The repository uses `pyproject.toml` as the standard Python project metadata
and dependency declaration mechanism.

This choice is appropriate because it is:

- standard modern Python project configuration,
- explicit and repository-owned,
- suitable for version constraints,
- capable of distinguishing project metadata from dependencies,
- compatible with future development and production environment creation.

The project metadata is intentionally minimal and limited to what is already
established for this phase.

## Minimal repository metadata

The repository declares the project identity and Python baseline in
`pyproject.toml`:

- project name: `xportra-ai`
- version: `0.0.0` (minimal placeholder only; no release strategy is
  being invented)
- Python requirement: `>=3.13,<3.14`

This is the minimal configuration necessary to establish a reproducible,
repository-based Python policy without claiming support for dependency sets
that have not yet been intentionally selected.

## Rules for future work

- A package is added only when a scoped task requires it and the need is
  documented in `REQUIREMENTS.md` or an ADR.
- Direct dependencies are declared in project configuration; transitive
  dependencies remain implicit unless the project later explicitly
  requires them.
- Environment recreation must use the repository configuration, not the
  contents of `.venv`.
- `.venv` reuse remains a temporary convenience only; it is not a source of
  truth for the project.
- No dependency is considered valid merely because it exists in the copied
  local environment.
