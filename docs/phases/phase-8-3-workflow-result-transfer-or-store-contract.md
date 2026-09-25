# Phase 8.3 — Workflow/Result Transfer-or-Store Contract

**Status:** Complete and verified (2026-09-24)
**Phase:** Phase 8 — API & Application Integration
**Type:** Cross-request lifecycle contract + actor
threading; no new persistence, no verdict

> This record describes what was actually implemented and verified.

## Part A — cross-request state problem

Lifecycle: request A starts/progresses/analyzes; the
workflow record and the live Phase 6 result exist;
request B must review/finalize. Per-object mapping
(authoritative source / persists / reconstructible /
transient / must cross / needs persistence / stable id):

- Workflow state, shipment binding, evidence refs,
  rounds: in-memory domain object / no / yes — strict
  rehydration from the client-held record / no / yes as
  record / no / workflow uuid5 id.
- Evidence rows, applicability/assessment rows,
  regulatory records: existing PostgreSQL tables / yes /
  n/a / no / by reference where needed / no / row ids.
- Decision summary: caller-supplied, deterministically
  rebuildable from cases; crosses as plain data (server
  tenant-checks, never reinterprets).
- Compliance analyses / report / traces (the result):
  in-memory Phase 6 object / no / NO — IDs derive from
  model-generated explanation text (uuid5 over its
  fingerprint), so re-running can yield different
  identities, costs provider calls, and is non-hermetic /
  yes (model text) / yes for finalize+reads / see below /
  report/analysis/trace uuid5 ids (exact-match only).
- Readiness: computed on demand from workflow+result;
  never stored (7.3 authority preserved).
- Final package: produced by finalize; needs the result
  again for later reads.

## Part B — strategy per object

- Workflow + shipment + supplies: TRANSFER by
  client-held record (works today; server revalidates
  shape, tenant, transitions).
- Deterministic inputs: TRANSFER by reference to
  persistent rows, or RECONSTRUCTION from them via
  existing deterministic services. No new machinery.
- Results: PERSISTENCE would be required in principle —
  but every compact form is prohibited (client round-trip
  of result objects/traces/fingerprints, globals,
  sessions, JSON blobs of internals, validated-answer
  storage as model output), and normalized Phase 6
  tables would duplicate the provenance system at
  disproportionate size while DB-gated tests cannot run
  here. Verdict below.

## Persistence verdict: deferred, specified, not built

No new persistence in 8.3. Workflow transfer already
satisfies every currently exposed endpoint; result
retention is the sole gap and its only lawful form is a
future normalized result store. That store is a whole
subsystem (analyses/reports/traces tables with tenant
ownership, case/workflow linkage, append-only rounds,
terminal protection, round-linkage stale detection),
not "smallest" for this phase — specified as future
work, not approximated unsafely.

## Part C — authorities preserved

Phase 2–5 inputs, 3.5 summary (by reference, never
recomputed), Phase 6 semantics, Phase 7 process state
(no second machine), 7.3 computed readiness (never
stored), 7.5 terminal closure (no mechanism here can
reopen — verified across transfers). No domain file
modified.

## Part D — actor identity

Additive `get_request_actor`: Bearer → verified subject
UUID; dev header / anonymous non-production → `None`;
production dev-header → 503; garbage Bearer → 401 via
the existing verifier; never raises 401 itself so the
membership boundary cannot be shadowed. All 13
compliance routes thread it into `ApplicationContext`;
tenant/role still come exclusively from `MemberContext`;
bodies cannot supply it (`extra="forbid"`, tested).
Application services accept and carry it; the domain
takes only `TenantContext` (unchanged by design —
actor exists for future audit use, and no audit
logging was added).

## Part F — result identity and stale safety

Round linkage is the stale detector: report id must
equal the latest round's, analysis/trace ids and
fingerprints must match. Proven: R1-finalize-after-R2
fails `analysis_stale`; supply-after-analysis
invalidates the prior result; divergent same-base
analyses produce distinguishable rounds; the 7.3 gate
still fronts every finalization. No competing
fingerprint system invented.

## Part G — concurrency

No locks required: the server holds no mutable
workflow state (all domain updates are `replace()` on
caller-held records), so concurrent same-base analyses
yield divergent client records, never corruption —
and deterministic IDs make identical recomputations
converge safely. Two finalizes: first wins, second
sees terminal (409). Cross-tenant operations stay
isolated by per-call checks. Stale crossovers fail
closed via round linkage. Consistency burden sits
with the record holder, by design.

## Part H — endpoint implications

Newly exposable by 8.3: none at HTTP (actor threading
is plumbing). Still blocked pending the result store:
finalize, package reads, report reads,
result-attached history. Unchanged and safe: all 13
existing endpoints. Compound analyze-and-finalize
remains rejected (would skip mandatory human review).

## Rejected approaches (explicit)

Reconstruction-by-reanalysis (unsafe IDs + cost);
client-held result records/traces/fingerprints
(client as compliance truth); globals/sessions/caches;
JSONB result blobs; validated-answer storage (model
output); normalized Phase 6 tables now
(disproportionate + DB-untestable here); compound
finalize (skips review); second readiness verdict;
reopen-via-persistence.

## Verification

- Focused Phase 8.3: 32/32
  (`test_cross_request_state.py` — actor dependency
  incl. prod/garbage paths; actor flow incl. forgery
  rejection and server-derived tenant/role; record
  transfer incl. tamper closure; lifecycle incl.
  divergence/stale/invalidation/terminal/prior-object
  integrity/linkage; finalization incl. current-only,
  gating, second-attempt; provenance incl. source and
  summary identity; privacy incl. domain-boundary
  proof; tenant matrix incl. no-mutation; concurrency
  incl. divergence, loser-stale, isolation).
- Phase 8.1 (31) + 8.2 (29) + 7.1–7.5 (151) + Phase 6
  (247) + Phase 2–5 regressions pass unmodified. Full
  suite: 1679 passed + 37 skipped (gated), 0 failures.
  No live execution claimed.

## Deliberately outside Phase 8.3

Result store implementation, finalize/package/report
endpoints, UI, provider wiring, evaluation, production
hardening, audit logging.

## Files created / modified

- Created: `tests/unit/test_cross_request_state.py`,
  `docs/phases/phase-8-3-workflow-result-transfer-or-store-contract.md`.
- Modified (additive/minimal): `xportra/api/dependencies.py`
  (`get_request_actor`), `xportra/api/compliance.py`
  (actor threaded through 13 handlers).
- No domain, application-core, persistence, or
  infrastructure behavior change; no prior test touched.
