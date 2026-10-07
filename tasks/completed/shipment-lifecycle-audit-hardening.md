# Shipment Lifecycle Audit and Hardening — Complete

Implementation audit with only minimal correctness
fixes. No redesign, no new features, no migration, no
new fields, no versioning/snapshots/delete semantics,
no FK change, no verdict/score, ADR-0013 unaltered.

## Audit findings

Verified holding across all ten audit questions:
tenant-scoped identity on every boundary (no
client-minted or sessionStorage-only identity trusted);
fresh-session discovery, draft bind, active resume, and
completed report/package reads served from PostgreSQL;
reload/restart converge without duplication or
regression; stale snapshots fail closed (409) and the
server record wins on resume; workflow/shipment
tenant/case binding enforced at every persisted use;
multi-workflow selection deterministic (latest
activity, count surfaced, completion from documented
terminal semantics); single package-write path keeps
the atomic lock boundary unbypassable; sessionStorage
split honored (server truth vs client convenience).

Three small gaps found and fixed:

1. Listing/detail endpoints returned 400 where no
   result store is wired; they now use the stored-path
   dependency and fail closed with 503, matching every
   other stored read.
2. Discovery fetches used the default first page, so
   tenants with more shipments than the page size lost
   history/resume coverage; dashboard, archive,
   workspace, and report reads now use a bounded full
   window (`DISCOVERY_PAGE_SIZE = 100`, documented;
   paged archive UI stays future work).
3. List composition read each shipment's workflows
   twice; it now resolves once per shipment and reuses
   the result for filtering and composition.

## Tests

- New/updated: unwired-store 503 endpoint test;
  existing listing (19), lock (14), persistence,
  workflow-record, stored-API, and closure suites
  re-verified unchanged in intent.
- Full backend: 2034 passed + 61 subtests, 0 failures.
- Frontend: 64 files / 439 tests passing (one
  query-string assertion updated for the bounded
  window); `tsc --noEmit` clean; `npm run build`
  succeeds.
- Integration: 51 skipped (no `DATABASE_URL`; no live
  coverage claimed). No packages installed.
