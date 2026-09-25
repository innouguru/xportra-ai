# Phase 8.4 — Normalized Phase 6 Result Store

**Status:** Complete and verified (2026-09-24)
**Phase:** Phase 8 — API & Application Integration
**Type:** Tenant-safe result persistence + reconstruction;
no new endpoints, no verdict

> This record describes what was actually implemented and verified.

## 1. Result persistence problem

Cross-request finalization needs the reviewed Phase 6
result, but results are in-session objects with
model-text-derived identities (uuid5 over explanation
fingerprints): re-running can fork identities, client
round-trips would make the browser compliance truth,
and globals/sessions/blobs are prohibited. The only
lawful retention is normalized server-side storage.

## 2–3. Normalized schema and table responsibilities

Migration `010` (reversible, schema-only, convention-
following: `BEGIN/COMMIT`, tenants FKs, CHECKs,
indexes, `set_updated_at` triggers):

- `compliance_analysis_reports`: report identity,
  tenant/case/workflow linkage, context fingerprint,
  six carried counts + conflict count, id-list rollups
  and missing entries as JSONB, decision summary
  carried as JSONB reference (no summary table exists
  for an FK; never recomputed, never a second summary).
- `compliance_analyses`: full scalar/state fields as
  columns (position preserves report order),
  requirement as plain UUID (no FK — the requirements
  table is global/shared), fixed-schema typed
  reference lists as JSONB per the `evidence_ids`
  precedent.
- `compliance_analysis_traces`: same treatment plus
  answer/input fingerprints and structured steps;
  record-only provenance, no deliberation storage.
- `compliance_workflow_rounds`: composite PK
  (tenant, workflow, round_index) with full round
  linkage — the anti-forgery anchor, not a second
  history (no states/transitions stored).
- `final_assessment_packages`: linkage only
  (workflow/case/report/round/open-requirements);
  UNIQUE per workflow makes second-finalization
  structurally impossible. Content lives in the
  result tables — zero duplicated truth.

## 4. Authoritative source of every stored field

All values originate from the produced Phase 6
objects (`to_record()` shapes) plus workflow linkage;
counts/aggregates carried, never recomputed in SQL.

## 5–6. Tenant ownership and FK strategy

Mandatory tenant FKs; composite `(tenant_id, id)`
unique keys with tenant-safe FKs (001 pattern):
composition children CASCADE, cross-entity links
RESTRICT. Tenant checks happen in app pre-checks,
repository scoping, and constraints — never trusting
caller IDs; cross-tenant reads return None (404
downstream).

## 7–9. Lifecycle, stale semantics, idempotency

Analyze → atomic single-transaction write → DTO;
later requests resolve server-known latest via round
linkage; readiness still gates every finalize.
Content-derived natural keys make retries converge
(verification before reuse); round slots are
first-writer-wins (divergent losers keep valid client
records but never displace linkage); stale/forged
linkage fails closed.

## 10. Reconstruction

`database record → validated representation →
existing Phase 6 object` (`rebuild_analysis/report/
trace/result`): exact field revival with enum, UUID,
tenant/case/report/analysis cross-link validation;
corrupt rows fail closed. No competing domain classes.
JSONB normalization (UUID→string) applies to the
carried summary only — everything else is already
stringified by domain contracts.

## 11. Finalization safety

Stored finalize path reuses the unchanged 7.3 gate
and `finalize()`; client-vs-server round equality is
checked first (forgery/stale → `StaleAnalysisError`);
existing package row → `TerminalWorkflowError`;
conflict race → constraint → retry converges to
terminal. 7.5 closure holds across requests.

## 12. Package persistence decision

Yes — minimal linkage table, justified: cross-request
terminal enforcement is otherwise impossible (clients
can replay pre-finalize records), package reads need
stable identity, and history needs the reference.
Content is never duplicated.

## 13–14. Migration and repository boundary

`migrations/010_compliance_analysis_results.sql` (+
`.down.sql`, drops exactly the five tables). Five
psycopg/no-ORM repositories (transactional creates +
tenant-scoped reads, existing helper conventions).
`ComplianceResultStore` owns atomicity, idempotency,
and reconstruction — no compliance reasoning.

## 15. Privacy/security

Stored: identities, states, validated finding text,
reference pointers, fingerprints, deterministic
detail. Never stored: prompts, provider responses,
chain-of-thought, secrets, credentials, raw
documents, personal data. Scan-tested.

## 16. API capabilities unblocked

None yet by choice: stored-path use cases
(`finalize_stored_package`, `get_stored_package`,
`describe_stored_report`, `load_current_result`) are
implemented and tested at the application boundary;
HTTP exposure is deferred to Phase 8.5 for a clean
boundary. Finalize/package/report endpoints remain
blocked in the API — unchanged from 8.3.

## 17. Database verification status

No `DATABASE_URL` here: migration/integration suites
report 7 gated skips. Verified without DB: 24 store
unit tests (dict-backed fakes with real-conflict
semantics), 12 migration structural tests, full
regression. Live apply/rollback/repository tests
exist and run wherever `DATABASE_URL` is configured.

## Verification

- Focused Phase 8.4: 24 store unit + 12 migration
  structural (exact round-trips incl. provenance,
  retry convergence, slot conflicts, tenant/case
  isolation, corruption rejection, privacy scans,
  stored finalize/package/report paths, terminal
  enforcement, no-store failure modes).
- Phase 8.1 (31) + 8.2 (29) + 8.3 (32) + 7.1–7.5
  (151) + Phase 6 (247) + Phase 2–5 regressions pass.
  Full suite: 1715 passed + 44 skipped (37 pre-existing
  gated + 7 new DB-gated), 0 failures. No live
  Qdrant/OpenRouter/database execution claimed.
- One prior assertion updated (not weakened):
  8.1's exact collaborator-set test now includes the
  legitimate `_result_store` collaborator; its
  no-workflow-state intent is unchanged and still
  enforced.

## Deliberately outside Phase 8.4

HTTP exposure of stored paths (8.5), UI, provider
wiring, evaluation, production hardening, audit
logging.

## Files created / modified

- Created: `migrations/010_compliance_analysis_results.sql`
  (+ `.down.sql`), `xportra/application/result_store.py`,
  `tests/unit/test_result_store.py`,
  `tests/unit/test_result_store_migration.py`,
  `tests/integration/test_result_store_postgresql.py`,
  `docs/phases/phase-8-4-normalized-result-store.md`.
- Modified (additive): `xportra/persistence/repositories.py`
  (5 repos), `xportra/application/__init__.py` (5
  exports), `xportra/application/analysis.py` (optional
  persist-on-success), `xportra/application/workflows.py`
  (optional store + 4 stored-path use cases),
  `tests/unit/test_application_boundary.py` (one
  collaborator-set assertion extended, same strictness).
- No Phase 1–7 behavior change otherwise.
