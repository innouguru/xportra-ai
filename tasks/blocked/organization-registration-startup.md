# Organization Registration Startup — Blocked

## Scope

Complete the missing committed backend modules for the organization
registration wiring already present at `5436dc8`, and verify that the
FastAPI application starts from a clean checkout.

## Confirmed source defect

At `5436dc8`, `xportra/api/dependencies.py` imports
`xportra.persistence.organization_registration`, but that module is
absent from the Git tree. The same commit's application imports
`xportra.api.organizations`, also absent from the Git tree. Migration
014 and its rollback were present only as untracked local files. The
application service, API dependency wiring, exception mapping, and
request/response schemas were tracked.

The clean-checkout import reproduced the missing persistence module
error. The repository package configuration discovers packages from
the project root, so the missing source files—not package discovery—
caused the failure.

## Remaining blocker

The correction is not production-verified until Render starts the
deployed correction commit. Verify the deployed commit and startup
logs, then verify `/health`. No production database migration was run.
The last recorded production database state was migrations 002–013;
check the current database read-only for migration 014's three tenant
profile columns before deciding whether any migration action is needed.

## Acceptance criteria

- [x] The clean-checkout import failure was reproduced on `5436dc8`.
- [x] The complete registration import path and missing support files
  are included in the correction.
- [x] Targeted and full backend tests pass.
- [x] The corrected app starts with safe test configuration.
- [ ] Render starts the deployed correction commit and serves `/health`.
