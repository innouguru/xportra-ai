# ACTIVE_TASK.md — Current Active Task

## Task: Compliance Workflow Persistence Audit

**Status:** Complete (2026-10-07).

End-to-end audit of the workflow persistence contract:
one real gap found and fixed (evidence-upload terminal
checks now resolve the authoritative server workflow
state instead of trusting the snapshot). All other
boundaries verified holding with no changes.

Verification: backend 2039 passed + 61 subtests;
frontend untouched; integration gated (51 skipped, no
`DATABASE_URL`). Task record:
`tasks/completed/compliance-workflow-persistence-audit.md`.
Committed; push not requested.
