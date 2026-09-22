# Python Runtime Policy — Xportra AI

> Repository policy for the project's Python baseline and environment reproduction.
> This document establishes the project baseline without modifying the existing
> local virtual environment.

## Current environment observed

The existing `.venv` was inspected without modification. The interpreter in use is:

- Python 3.13.0b4
- Major version: 3
- Minor version: 13

This version is consistent with a practical Python 3.13 baseline and matches the
current environment in use by the repository. However, the copied `.venv` is
not the authoritative source of truth for project policy; it is only the current
local execution environment available in the workspace.

## Baseline decision

The project baseline is set to Python 3.13.x.

Why this baseline:

- It matches the currently available development environment in `.venv`.
- It is a current Python major/minor line rather than an older compatibility
  target.
- It is suitable as a practical development baseline while the project remains
  in early Phase 0 and before specific application dependencies are introduced.
- It avoids making a broader claim about library compatibility beyond the
  environment actually inspected.

This is a repository-level policy decision, not a claim that every future library
or framework has been validated under every possible configuration.

## Source-of-truth policy

- The repository configuration is the source of truth for the supported Python
  baseline.
- The existing `.venv` is disposable infrastructure reused for convenience only.
- The project must not treat the local copied environment as the canonical record
  of dependencies or runtime policy.
- Future changes to the Python baseline require an explicit project decision and
  documentation update.

## Reproduction guidance for future developers and agents

Future developers and agents should reproduce the project environment by:

1. using the repository configuration as the authority,
2. creating a fresh virtual environment from the project baseline,
3. installing only the dependencies explicitly declared in the repository,
4. validating that the selected interpreter version satisfies the project
  requirement before work begins.

The repository should not rely on the presence of a copied local `.venv` to
establish the approved runtime.

## Boundary and caution

This policy intentionally avoids vendor-specific or application-specific runtime
claims. It is only a minimal, repository-level Python baseline and dependency
policy for early project setup. No application dependencies or provider choices
are introduced by this policy.
