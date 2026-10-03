# ACTIVE_TASK.md — Current Active Task

## Task: Server-Persist the Compliance Workflow Record

**Status:** Complete (2026-10-03).

Implements the Phase 8 integration-audit blocker:
`xportra.compliance_workflows` (migration 012) makes
the workflow record server-owned; mutations load,
verify (stale/forged snapshots rejected), transition
via the unchanged domain, and persist. Analysis/result/
finalization persistence unchanged; tenant isolation
server-side; frontend contract unchanged.

Verification: new unit suite 15/15; gated HTTP
integration suite skips without `DATABASE_URL`;
required existing groups green; full backend
1954 passed + 46 skipped (gated), 0 failures.
Frontend untouched. Task record:
`tasks/completed/server-persist-workflow-record.md`.
Committed; push not requested.
