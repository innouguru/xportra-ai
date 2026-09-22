# Phase 3.2 — Applicability Integration Boundary

> Status: Implemented and verified — 2026-09-21

## Objective

Phase 3.2 establishes the domain integration boundary that builds an
`ApplicabilityContext` from existing Xportra export-case/domain data.

Before this phase, callers had to manually construct the `ApplicabilityContext`
when the required information already existed in the domain (exporter, product,
destination). This phase removes that manual step.

## Integration boundary introduced

`ApplicabilityContextBuilder` translates existing domain facts into the minimal
tenant-owned context required by deterministic applicability rules.

### Domain inputs consumed

| Domain source | Field used | ApplicabilityContext field |
|---|---|---|
| Exporter | `id` | `exporter_id` |
| Exporter | `legal_name` / `trading_name` | `exporter_name` |
| Exporter | `country_of_registration` | `origin_country` |
| Product | `commodity_code` | `commodity` |
| Product | `description` | `product_category` |
| Destination | `country_code` | `destination_country` |
| Caller | `actor_role` | `actor_role` (defaults to `"exporter"`) |
| Caller | `business_characteristics` | `business_characteristics` |
| Caller | `tenant_id` | `tenant_id` (required) |

### Output/context produced

A fully-formed `ApplicabilityContext` that can be consumed directly by
`ComplianceApplicabilityService.determine()`.

### Missing facts

If an existing export case does not contain a fact required by the applicability
context, the builder leaves it as `None` rather than inventing a default. The
system remains conservative about missing information.

### Tenant isolation

Tenant identity is validated as a required UUID and propagated directly into the
resulting `ApplicabilityContext`. A context created for one tenant cannot
accidentally become associated with another tenant.

## Determinism

- Repeated construction from identical input produces identical output
- No inference or defaulting of missing values
- Exporter name prefers `legal_name` over `trading_name`
- `actor_role` defaults to `"exporter"` when not specified

## Files modified

- `xportra/domain/ingestion.py` — add `ApplicabilityContextBuilder`
- `xportra/domain/__init__.py` — export `ApplicabilityContextBuilder`
- `tests/unit/test_applicability_context_builder.py` — focused Phase 3.2 tests
- `phase-3-2-applicability-integration-boundary.md` — this document
- `ACTIVE_TASK.md` — updated after verification
- `CURRENT_STATE.md` — updated after verification

## Focused tests

The focused Phase 3.2 unit test file is:

- `tests/unit/test_applicability_context_builder.py`

It covers:

1. Complete export-case context translated correctly
2. Missing product fields remain None
3. Missing exporter fields remain None
4. Missing destination remains None
5. All optional fields missing (only tenant_id required)
6. Tenant identity preserved
7. Tenant isolation between different tenants
8. Commodity preserved from product
9. Destination preserved from destination market
10. Deterministic repeated construction
11. Resulting context consumed by ComplianceApplicabilityService
12. Invalid tenant_id raises
13. None exporter/product/destination accepted
14. Actor role override
15. Business characteristics preserved
16. Exporter name falls back to trading_name
17. Exporter name uses legal_name over trading_name

## Verification

Focused Phase 3.2 tests:

- Command: `python -m unittest tests/unit/test_applicability_context_builder.py -v`
- Result: 17 passed, 0 failed, 0 skipped

Full unit suite:

- Command: `pytest tests/unit/ -v`
- Result: 157 passed, 0 failed, 0 skipped, 0 errors

## Regression status

All 140 pre-existing tests remain passing. Phase 2.x and Phase 3.0/3.1 behavior
is intact.

## Deferred

The following functionality is intentionally left for later phases:

- Persistence of built contexts
- Automatic fetching of exporter/product/destination from repositories
  (the builder accepts raw dicts; repository integration belongs to the
  service layer)
- RAG, LLM, embeddings, or vector search
- External regulatory API integration
- New applicability rules