# ACTIVE_TASK.md — Current Active Task

## Task: organization-registration-startup (Phase 10.11)

**Status:** Source correction verified; production verification blocked
pending Render deployment.

The `5436dc8` source tree contained API wiring for organization
registration but omitted the persistence store, API router, and
supporting migration 014 from the committed tree. The clean-checkout
import failed at `xportra.persistence.organization_registration`.
The correction restores the complete import path and its supporting
files, with coverage for persistence atomicity, retry conflicts,
authorization-derived identity, migration shape, and API startup.

No production database migration has been run. The last recorded
production migration state is 002–013; verify whether migration 014
has already been applied before any operator considers applying it.
After the source is deployed, verify Render starts the expected commit
and serves `/health` before claiming production is fixed.

The prior frontend sign-in deployment and end-to-end checklist remain
documented in its task record; they are not part of this backend task.
