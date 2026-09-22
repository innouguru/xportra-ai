# Phase 2.9 — Compliance Risk & Priority Foundation

> Status: Complete for the approved boundary scope — 2026-09-21

## Implementation summary

Phase 2.9 adds `ComplianceRiskService`, a deterministic risk/priority layer over existing
compliance cases. It classifies applicable requirements into explicit attention levels
based only on existing case state — no new regulatory, applicability, or assessment logic
is introduced.

The service is read-only, in-memory, and preserves full tenant isolation and regulatory
provenance.

## Risk classification rules

The `classify` method maps applicable case states to attention levels:

| Existing state | Risk state | Explanation |
|---|---|---|
| `satisfied` | `low` | satisfied assessment |
| `not_satisfied` | `high` | not_satisfied assessment |
| `unknown` + missing required evidence | `medium` | unknown with missing required evidence |
| `unknown` + sufficient evidence present | `unknown` | unknown without sufficient evidence |
| `not_applicable` | excluded | not in any risk output |

A deterministic `explanation` field records which existing state produced the classification.

## Output format

`classify` returns a list of dicts, each with:

- `requirement_id` — UUID of the requirement
- `requirement_text` — requirement text (preserved from case)
- `state` — one of `high`, `medium`, `low`, `unknown`
- `explanation` — deterministic string identifying the producing state
- `regulatory_source` — referenced from the original case
- `document_metadata` — referenced from the original case
- `provenance` — referenced from the original case

Cases with `not_applicable` applicability are excluded from the output entirely.

## State preservation

- Applicability and assessment outcomes remain completely unchanged.
- Risk classification is a derived view only; it does not modify any case data.
- The service does not claim that a risk level is a regulatory determination.
- No severity is inferred from requirement wording unless an explicit deterministic rule
  and existing field support it.
- Tenant isolation is enforced: cross-tenant cases raise `ComplianceSummaryValidationError`.
- Full regulatory provenance (regulatory_source, document_metadata, provenance) is preserved
  in each classification output.

## Determinism

Output is deterministic: cases are sorted by `requirement_id` string, and the same input
always produces the same output. No LLM, agents, embeddings, vector DB, retrieval, RAG,
ranking, or recommendations are used.

## What was NOT implemented

- Regulatory interpretation or new applicability logic
- New evidence assessment logic
- LLM reasoning, agents, or embeddings
- Recommendations, actions, or automated compliance decisions
- Workflows, notifications, or UI
- Crawling, monitoring, or retrieval/RAG
- Persistence or database schema changes
- Any new compliance verdict or scoring

## Tests

Focused Phase 2.9 tests in `tests/unit/test_compliance_risk.py` cover:

1. `satisfied` → `low`
2. `not-satisfied` → `high`
3. `unknown` with missing required evidence → `medium`
4. `unknown` without sufficient evidence → `unknown`
5. `not-applicable` excluded from classification
6. Explanation is deterministic (same input → same output, regardless of input order)
7. Provenance (`regulatory_source`, `document_metadata`, `provenance`) preserved
8. Tenant isolation (cross-tenant rejection)
9. Deterministic repeated output
10. Empty case set returns zero-length list
11. Missing evidence detection by reason + empty evidence list

Full unit regression complements the focused tests.

## Files modified

- `xportra/domain/ingestion.py` — `ComplianceRiskService` class added
- `xportra/domain/__init__.py` — `ComplianceRiskService` imported and exported
- `tests/unit/test_compliance_risk.py` — Phase 2.9 focused unit tests (new file)
- `phase-2-9-compliance-risk-priority-foundation.md` — this documentation file

## PostgreSQL status

PostgreSQL integration tests require `DATABASE_URL` and were not run in this environment.
The risk service is a pure in-memory/read-service layer with no database dependency.
All 109 unit tests (98 existing + 11 new Phase 2.9) pass without PostgreSQL.

## Completion

Phase 2.9 is complete. Phase 3 must not begin.