# Production Database Migration 002–013 — Complete

Live database migration (not a docs task): the
Supabase production database was brought from its
001-equivalent state to the current Xportra schema
using the repository files as the sole SQL source.
No repo files changed; nothing committed or pushed
(task rule); connection string never displayed.

## Pre-migration (read-only)

- `DATABASE_URL` present (presence only, value never
  shown); connection succeeded (pooler host,
  `postgres` database, as briefed).
- `xportra.set_updated_at()` present; all 14 original
  tables present.
- Row-state discrepancy vs the brief: not empty.
  `authorities` = 6 (canonical 001 seed, expected);
  plus one active `local-development` bootstrap
  tenant, one active user, one active
  owner-membership. Verified minimal (slug/status/
  role only, no PII dumped). Left untouched per the
  no-delete rule; this database is now the live
  environment with those bootstrap records in it.
- `users.supabase_uid` already existed, so migration
  002's column add was a guarded no-op (index ensured).

## Apply

`002 → 013` in exact numeric order via repo files
(psycopg with script-owned BEGIN/COMMIT ≡
`ON_ERROR_STOP=1`; abort-on-first-error). Migration
001 never executed. Result: all twelve reported
success, zero failures, zero repairs, zero drops.

## Post-migration (read-only)

- All 14 original + 14 newer tables present
  (003–010 tables, `compliance_workflows`,
  `shipments`).
- 8/8 `compliance_evidence` upload columns present.
- `PRIMARY KEY (tenant_id, workflow_id)` and
  `PRIMARY KEY (tenant_id, shipment_id)` confirmed;
  shipment tenant FK confirmed.
- `compliance_workflows_set_updated_at` and
  `shipments_set_updated_at` triggers present (their
  creation also re-proves `set_updated_at()`).
- New indexes present (processing, hash, case,
  tenant keys); `draft|bound|locked` and non-blank
  profile checks confirmed on `shipments`.
- Row counts: only the pre-existing rows above; no
  migration created rows (authorities still exactly 6).

## Files Changed

None. Runner script lives outside the repo in local
temp and is not part of the project.

# Result/Decision

The production database is now at the current Xportra
schema (002–013 applied and verified) with all prior
rows preserved. It is ready for the next production
setup step (Supabase Auth/Storage configuration, then
backend/frontend deployment and live smoke tests).
