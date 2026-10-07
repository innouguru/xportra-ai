# Compliance Workflow Persistence Audit — Complete

End-to-end audit of the workflow persistence contract
with durable shipments. One real correctness gap found
and fixed; no redesign, no new features, no migration,
ADRs unaltered.

## Audit coverage (all ten questions verified)

1. Identity/authority: server-owned
   (tenant, workflow, shipment, case) on every boundary;
   deterministic workflow IDs converge instead of
   duplicating; tenant from membership only.
2. State persistence: every legal transition persists
   through the authoritative-resolve + save path before
   success; nothing terminal lives only in
   sessionStorage when the store is wired.
3. Evidence: uploads content-addressed per tenant with
   compensating storage delete; supply resolves the
   authoritative workflow, rechecks recorded evidence
   ownership, and saves in one step; cross-tenant and
   cross-case attachments fail closed.
4. Analysis cycles: one transaction per round
   (report/analyses/traces/round/workflow); identical
   retries adopt, divergent rounds keep first-writer
   linkage and fail finalization closed; latest round
   deterministic by round index.
5. Reports: tenant-scoped rebuild from stored rows;
   frontend rehydrates via the stored-report endpoint
   with no in-memory dependence.
6. Package/finalization: single write path with atomic
   shipment lock; terminal retry rejected before any
   store write; completion still terminal state plus
   package linkage.
7. Stale snapshots: full-field comparison (identity,
   state, evidence, requirements, rounds) rejects with
   409 on every mutating workflow call; no weakening.
8. Fresh session: dashboard/archive/workspace/report
   resolve from PostgreSQL; server wins on conflict.
9. Cross-tenant: unknown and foreign identities read
   as indistinguishable 404s on all read/mutation
   boundaries; no caller tenant trusted.
10. Transactions: start (shipment + workflow), analysis
    round bundle, and finalize (lock + package +
    workflow) each commit atomically; supply/upload
    steps are single writes or compensated; the
    in-memory finalize path persists nothing by design.

## The one gap (fixed)

Evidence-upload terminal checks validated the
submitted snapshot only, so a stale open snapshot
authorized storage puts and database rows against a
finalized workflow (unattachable later, but storage
and rows were still written, violating the documented
pre-mutation guarantee).

- `ComplianceResultStore.get_workflow_state`: narrow
  tenant-scoped state read without snapshot-equality
  overreach (round drift must not block uploads).
- `EvidenceUploadApplicationService` accepts an
  optional result store (wired in `dependencies.py`);
  the guard enforces the server row where available
  and keeps snapshot behavior where not. No new error
  type; no handler change.

## Tests

- `tests/unit/test_evidence_upload_authoritative.py`
  (new, 5 tests): stale-open vs finalized rejected
  with zero mutations; stale-terminal vs open allowed
  (server wins); unknown row not-found; unwired
  snapshot behavior preserved; workflow-less upload
  unaffected.
- Full backend: 2039 passed + 61 subtests, 0 failures.
- Frontend untouched (no run per task scope).
- Integration: 51 skipped (no `DATABASE_URL`; no live
  coverage claimed). No packages installed.
