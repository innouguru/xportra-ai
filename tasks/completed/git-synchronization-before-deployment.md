# Task: Git Synchronization Before Deployment

**Status:** Completed (2026-10-29). Authorization: explicitly granted by the
user to commit remaining completed work and push to `origin/main`
(`innouguru/xportra-ai`). No force-push. No deployment performed.

## Audit findings

- Local `main` was 12 commits ahead of `origin/main` (12ddfc2..9710a15),
  0 behind at the time of the audit.
- Tracked uncommitted changes: `migrations/030_regulatory_publication.sql`
  (substantive), `xportra/api/app.py` + `xportra/api/schemas.py` (catalog
  wiring — incomplete workstream), plus untracked scripts/artifacts.

## Committed in this pass

1. `migrations/030_regulatory_publication.sql` — the status CHECK constraint
   drop (`DROP CONSTRAINT IF EXISTS regulatory_requirements_status_check`)
   moved from an operator comment into the migration transaction
   (`BEGIN ... COMMIT`), with the new constraint added after the drop.
   Idempotent; migration history not rewritten; safe whether or not an
   operator already applied the manual drop documented earlier.
   - New commit: `fix: apply migration 030 status constraint drop in transaction`

2. Project-state documentation (`CURRENT_STATE.md`, `ACTIVE_TASK.md`, this
   record) describing verification results and the catalog classification.
   - New commit: `docs: record git synchronization audit before deployment`

## Verified before committing/pushing

- Backend focused regulatory suites (Stage A/B, eligibility, intake, worker,
  eligible-requirements endpoint, governance blocks): 112/112 pass.
- Full backend unit suite, excluding the corrupt untracked catalog test
  fragment: 2342 passed / 2 failed / 68 subtests passed — both failures are
  pre-existing and documented (RAG domain IO audit text-scan false positive
  on `fitz.open()`; worker start/stop event-loop flake which passes in
  isolation). The former cross-tenant RAG failure now passes, consistent
  with the committed `12ddfc2` fix.
- Frontend: TypeScript check pass, production build pass (existing
  large-chunk advisory), full suite 582 passed / 1 failed — the single
  failure is the pre-existing `RegisterPage.test.tsx` pending-registration
  expectation (`sessionStorage`) that disagrees with the intentional
  `localStorage` persistence in `app/pendingRegistration.ts`.
- PostgreSQL integration tests remain skipped (no `DATABASE_URL`
  configured); nothing was written to or read from any database in this
  pass. Mocked/unit-level verification only.

## Deliberately NOT committed (preserved unmodified, untracked)

The exporter catalog backend workstream was audited and classified
**incomplete and unverified**:

- `xportra/api/catalog.py` — the service dependency is broken
  (`Depends(lambda s: s)` instead of the established
  `Depends(get_services)` pattern in `regulatory_admin.py`).
- `xportra/application/regulatory_catalog_service.py` — the SQL filters
  omit the required `r.status = 'published'` condition (risk of exposing
  not-yet-published requirements to exporters), and
  `_pending_flags_block` (pending governance-flag enforcement) is dead
  code, so the documented flag policy is not enforced.
- `xportra/api/app.py` / `xportra/api/schemas.py` uncommitted diffs —
  catalog router registration and schemas, coherent only with the above.
- `tests/unit/test_regulatory_catalog.py` — a 9-line syntax-error
  fragment (`UUID(" bbbb...\)`) that poisons pytest collection of
  `tests/unit`; committed as-is it would break every backend unit run.

Correcting these is a separate authorized implementation task, not a
synchronization step. Deployment therefore has no
`GET /catalog/requirements` endpoint until that task lands — identical to
the previously deployed state.

## Preserved untracked files (intentionally not committed)

Investigation scripts and local review artifacts (`check_*.py`,
`tmp_*.py`, `fix_*.py`, `*_output.txt`, `*_diff.txt`, `report.md`,
`investigation_report_xportra_app.md`, `dependency_*.md`,
`phase-4d-authorization-decision-package.md`, `documented_steps_review.md`,
`frontend-ui-source.txt`, `xportra-ui-review.txt`/`.zip`,
`test_regulatory_index_demo.py`, `uv.lock`, `.freebuff/`,
`frontend/t5.txt`, `frontend/test-output.txt`). None contain repository
secrets; they remain on disk untouched.

## Push

`origin/main` (innouguru/xportra-ai) updated with the 12 existing local
commits plus the two new commits above, by ordinary push (no force).
