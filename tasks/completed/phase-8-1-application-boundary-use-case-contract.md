# Phase 8.1 — Application Boundary & Use-Case Contract (Completed 2026-09-24)

Explicit testable boundary UI → API → application →
domain in `xportra/application/`: trusted-context
orchestration of the completed domain services plus
allow-listed DTOs, with no second compliance/workflow
engine. Mirrors `ACTIVE_TASK.md`; full record in
`docs/phases/phase-8-1-application-boundary-use-case-contract.md`.

## Scope delivered

- `context.py`: `ApplicationContext` (actor, effective
  tenant, role; API-built from server membership).
- `errors.py`: HTTP-free taxonomy (auth passthrough,
  tenant mismatch, transition, not-ready/stale,
  terminal, not-found, validation, infrastructure).
- `dtos.py`: 16 frozen DTOs (workflow, shipment,
  evidence, rounds, findings, report, readiness,
  history, package, applicability, case readiness).
- `workflows.py` / `analysis.py` / `assessments.py` /
  `evidence.py`: stateless use-case services;
  record-in/record-out, live results in-session, no new
  persistence.
- `tests/unit/test_application_boundary.py`: 31 tests.

## Acceptance

Focused 31/31; Phase 7.1–7.5 (151) + Phase 6 (247) +
Phase 2–5 regressions pass; full suite 1618 passed +
37 skipped (gated), 0 failures. No prior test weakened.
No endpoints, UI, persistence, or evaluation built.
