# Task: UI / Product Architecture (specification only)

**Status:** Complete (2026-09-24) — specification delivered, no code written, no backend changed.

## Objective

Define the exact UI contract for the exporter journey against the production API before any frontend implementation.

## Deliverable

`docs/phases/ui-product-architecture.md`: 10-screen journey spec (12-step spine), role model, state vocabularies with forbidden-collapse rules, evidence/analysis/finalization UX contracts, full API matrix (every endpoint verified against `xportra/api/`), auth/session assumptions, responsive IA, six documented backend gaps, and implementation prerequisites.

## Verification

Each referenced endpoint checked against route decorators in `xportra/api/compliance.py` and `xportra/api/router.py`; each response field checked against `xportra/api/schemas.py` and `xportra/application/dtos.py`; each state checked against `WORKFLOW_STATES`, `APPLICABILITY_STATES`, `ASSESSMENT_STATES`, readiness codes, and history kinds; roles checked against `xportra/api/authorization.py`; auth flow checked against `xportra/api/dependencies.py`. No backend capability invented — gaps documented in §11 of the spec.

## Result / Decision / Outcome

Frontend implementation may proceed strictly within the spec; anything not traceable to the API matrix needs a backend task first. No backend change required to start. Next genuine task: UI implementation scaffolding.
