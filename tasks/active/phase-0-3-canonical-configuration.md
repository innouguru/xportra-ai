# Task: Phase 0.3 — Canonical Configuration Schema

**Phase:** Phase 0 — Agent Harness & Project Foundation
**Status:** In progress (2026-09-19)
**Mirrors:** `ACTIVE_TASK.md` at repo root

## Objective

Establish the canonical Xportra AI environment-variable schema and the
repository-authoritative `.env.example` template without implementing any
application functionality.

## Scope

1. Create `docs/architecture/environment-schema.md` defining the canonical
   environment variables.
2. Create `.env.example` as the repository-authoritative template for the
   required environment configuration.
3. Clean the inherited `.env` to the approved Xportra AI schema while
   preserving only values that map directly to canonical variables.
4. Update `REQUIREMENTS.md` and `docs/architecture/configuration-contract.md`
   to reflect the canonical schema and the repository authority of
   `.env.example`.
5. Verify `.gitignore` protects `.env` while allowing `.env.example` to be
   tracked.
6. Validate the repository state without exposing secret values.

## Constraints

- No application functionality, database, API, vector-store, or provider
  implementation work.
- No provider-specific configuration variables are introduced.
- No package installs or `.venv` changes.
- No secrets are printed, copied, or committed.
- `.env.example` remains safe and contains only placeholder values.

## Acceptance Criteria

- [ ] canonical environment schema exists
- [ ] `.env.example` exists
- [ ] `.env.example` contains no secrets
- [ ] `.env` contains only canonical variable names
- [ ] obsolete inherited variable names are removed
- [ ] `.env` remains ignored
- [ ] `.env.example` remains trackable
- [ ] documentation is internally consistent
- [ ] no application functionality is implemented
- [ ] `.venv` is unchanged

## Notes

This task resolves OQ-1 without selecting production providers. The schema
is intentionally minimal and provider-neutral, in line with the approved
project contract and dependency strategy.
