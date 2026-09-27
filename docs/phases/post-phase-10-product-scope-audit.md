# Post-Phase-10 Product & Architecture Scope Audit

> Analysis/documentation only (2026-09-27). No
> functionality implemented; no behavior changed; no
> open question answered by assumption; no new phase
> created. Task record:
> `tasks/completed/post-phase-10-product-scope-audit.md`.
>
> Basis: `CURRENT_STATE.md`, `ACTIVE_TASK.md`,
> `ROADMAP.md`, `REQUIREMENTS.md`, `INVARIANTS.md`,
> `AGENTS.md`, phase docs 10.1–10.5,
> `conversational-product-architecture.md`, ADRs
> 0008–0011, plus targeted implementation checks to
> verify documented claims (routes, 413 mapping,
> migration files, stdlib-only imports, retry/
> idempotency paths, frontend download handling,
> skip composition). Checkpoint `9249544` (origin/main
> aligned): frontend 157/157, tsc clean, build green,
> backend 1902 passed + 44 skipped.

## 1. What is actually complete

| Area | State | Evidence |
|---|---|---|
| Domain/compliance foundation (Phases 0–3) | Complete | `REQUIREMENTS.md` R-0/TB/SA; deterministic applicability, assessment, case model in `xportra/domain/ingestion.py` |
| Evidence ingestion/indexing/retrieval (Phases 4–5) | Complete in code; live gates NOT executed | Corpus/ingestion/chunking/indexing/sync boundaries; 5.16 closure records Qdrant/OpenRouter/combined gates not executed |
| Compliance reasoning (Phase 6) | Complete in code | 6.1–6.6 composition, verdict-free result, decision trace |
| Workflow lifecycle (Phase 7) | Complete, closed | Nine-state machine, terminal `assessment_package_ready` immutable (7.5), history projection |
| API/application boundary (Phase 8) | Complete | 8.1 use cases, 8.2 endpoints, 8.3 transfer contract, 8.4 result store (migration 010), 8.5 stored-path exposure |
| Frontend workflow (Phase 9) | Complete | 27 files / 157 tests, tsc + build green; static/served verification only (no browser engine) |
| Production security/configuration (10.1) | Complete as hardening | `runtime.py`, dev-header rejection, docs lockdown, 5xx sanitization, headers; R-10.1.9 exclusions stand |
| Conversational backend (10.2) | Contract-complete, read-only, stateless | `POST /conversations/messages`, frozen contracts, no store, no new LLM call |
| Evidence upload/storage/processing (10.3–10.4) | Code-complete, contract-complete | Validation, private Storage protocol + Supabase adapter, orchestration use case, migration 011 + rollback, 79 focused tests |
| Evidence upload UX (10.5) | Complete | Real upload/download/supply/re-run UI, honest states, finalized lockout; +17 tests, none weakened |

## 2. What a real user can do today

End-to-end journey, as implemented:

```text
New shipment → shipment information → requirements →
evidence (upload real files: PDF/DOCX/JPEG/PNG, watch
uploaded → processing → ready | failed) → supply to
workflow → analysis (rounds) → findings review →
additional evidence (reference or upload) → re-analysis
→ final review → finalize (permanent) →
package / report / history.
```

- **Genuinely operational in the codebase:** the full
  journey above, tenant isolation, terminal closure,
  idempotent re-upload, retry-by-re-invocation,
  authorized signed downloads, deterministic
  applicability/assessment, grounded RAG answers with
  citation validation, stateless conversational answers
  over own-tenant state.
- **Present as architecture/contracts only:** chat UI
  (no surface exists), transcript store/resumption
  (no tables, no endpoints), archive/supersede action
  (status value exists, no API path), `is_evidence_usable`
  enforcement in analysis wiring (predicate exists,
  zero callers — exclusion currently rests only on the
  accepted/reviewed assessment rule), evidence listing
  (per-ID GET only; session upload list in-memory).
- **Gated on unexercised live infrastructure:** every
  Postgres read/write (incl. applying migration 011),
  every Supabase Storage put/signed URL, every Qdrant
  upsert/query (so no uploaded file is actually indexed
  anywhere live), every OpenRouter call. The 44 skips
  are exactly these gates. Readiness is therefore
  **code-complete, zero percent live-verified**.

## 3. Actual product gaps

### Blocking (product unusable in production until resolved)

1. **No live backend validation.** No Postgres, Storage,
   Qdrant, or OpenRouter path has ever executed;
   migration 011 was never applied to a real database;
   the signed-URL flow never completed against real
   Storage. Nothing production can run on.
2. **No deployment/operations substrate.** No prod
   environment, migration-execution path, backup/
   recovery, or monitoring — R-10.1.9 explicitly
   excluded these, so the gap is scope-acknowledged,
   still prerequisite.
3. **No OCR.** JPG/PNG without embedded metadata text
   deterministically fail processing — two of four MVP
   formats are near-unusable as evidence (documented
   in 10.4 §8, still a user-facing hole).
4. **No conversational persistence or UI.** OQ-C1/C2
   block stored conversations; no chat surface exists
   at all — the conversational architecture has no
   user-facing capability.
5. **No evidence listing/continuity.** No workflow-
   or tenant-scoped listing endpoint (explicitly
   absent per UI-spec §11.2); the session upload list
   is in-memory, so cross-session evidence discovery
   is per-ID resolution only.
6. **No archive/supersede path.** U3 marking has no
   API endpoint (database-direct only), so incorrect
   documents cannot be retired through the product.

### Important but not blocking

- No upload progress percentage (fetch limitation;
  honest spinner ships).
- `is_evidence_usable` unenforced in analysis wiring
  (mitigated today by the accepted/reviewed rule).
- Synchronous processing only: large-file latency,
  no resumable/interrupted-upload recovery beyond
  full re-invocation; failed-row objects accumulate
  (compensating delete covers registration failure
  only).
- Stale-record hygiene items in §7 (header, roadmap,
  active-dir leftovers, "no commit/push" lines).

### Future / product expansion

OQ-C4 suggested links, OQ-C5 full harness, OQ-C3
budgets/streaming, retention + physical-deletion
policy, background queue, notifications, multi-shipment
chat, voice, analytics, proposal-card execution UI,
model/embedding/provider migration.

## 4. Conversational open questions (OQ-C1–C5)

- **OQ-C1 transcript retention/audit: still genuinely
  open (BLOCKED).** No policy approved; no tables
  (verified: migrations end at 011); nothing implicitly
  resolved it.
- **OQ-C2 per-subject vs per-tenant visibility: still
  genuinely open (BLOCKED).** Moot without persistence;
  only the authorization direction (members over own
  tenant, actor recorded) is established.
- **OQ-C3 chat LLM route/budgets: resolved by avoidance
  for 10.2, still open for any real chat.** No new LLM
  call exists; knowledge answers reuse Phase 5 RAG.
  A dedicated route, budgets, and streaming stay
  deferred — safely deferrable until a chat surface
  is approved.
- **OQ-C4 suggested evidence links: resolved as out
  (Later).** No link proposal exists anywhere
  (AST-verified in 10.2 tests). Product decision
  required to revive.
- **OQ-C5 groundedness evaluation: harness still open
  (DEFERRED).** Contract tests (citation presence,
  refusal correctness, no-override) ship; precision/
  refusal/no-override measurement at scale does not.
  Blocked only by scope approval, not by another
  decision.

## 5. Evidence-upload residuals (U1–U7, Phase 10.3)

All seven are **code-complete** (verified: validation
boundary, 10 MB + 413 mapping, no-delete (route scan
clean), tenant-verified signed downloads with
404-non-leaking lookups, identifier-only audit,
deterministic server identities, persisted
`uploaded → processing → ready | failed`). **None is
live-verified.** Residuals:

- **Processing reliability:** synchronous in-request
  pipeline; no timeout/backpressure characterization;
  retry is full re-invocation (idempotent, not
  resumable).
- **Persistence:** migration 011 + rollback exist and
  are structurally tested; never applied to a live DB.
- **Signed downloads:** issuance + expiry modeled and
  unit-covered (incl. opaque in-memory tokens); never
  completed against Supabase.
- **Storage lifecycle:** compensating delete covers
  register-failure only; no orphan-reaping, no
  retention enforcement, no lifecycle policy.
- **Auditability:** identifier/status metadata only,
  as decided — sufficient per U5, with no second
  system.
- **OCR:** absent by design decision (stdlib-only);
  the two image formats fail closed without embedded
  text — documented limitation, user-visible gap.
- **Duplicates:** deterministic per-tenant coalescing
  verified; cross-tenant independence verified.
- **Sketch deviations (all documented in 10.4 §8):**
  base64 JSON transport instead of the §1/§10
  "multipart" sketch; stdlib extraction instead of
  named PDF/Office parsers. The boundary sketch
  itself was not amended — readers must follow the
  10.4 deviation record.

## 6. Production-readiness gaps

Passing tests are not readiness. Concrete,
scope-supported prerequisites, all unexecuted:

- Live Supabase Postgres validation (incl. applying
  migrations 001–011) and live Storage validation
  (put, compensating paths, signed-URL completion).
- Live Qdrant validation (collection compatibility,
  tenant-filtered upsert/find at real embeddings).
- Live OpenRouter validation (keyed call, timeout/
  rate-limit behavior, citation path on real output).
- Deployment/runtime configuration (environment
  composition beyond `from_environment*` helpers,
  migration execution procedure, secret provisioning).
- Backup/recovery and monitoring/observability:
  unspecified (R-10.1.9 exclusion) — required before
  any production claim.

## 7. Roadmap consistency findings

Do not rewrite scope; flag only:

1. **ROADMAP.md is stale (highest-visibility).**
   Phases 1–4 and 6–10 remain unchecked although
   `CURRENT_STATE.md` + task records mark their
   substance complete; "No phase beyond Phase 0 has
   been scoped or started" is false. Labels also
   drifted: Phase 9 reads "Evaluation & Reliability"
   but delivered the frontend; Phase 10 reads
   "Production Hardening" but delivered
   security + chat foundation + upload + upload UX.
2. **CURRENT_STATE.md header stale:** "Updated:
   2026-09-24 / Phase: Phase 8 …" while the body
   records through 10.5.
3. **REQUIREMENTS.md has no R-10.3 (correct —
   scope-only) and no R-10.5.** Phase 10.5 was
   assigned via `ACTIVE_TASK.md`, which AGENTS.md
   permits, but the "R-1..R-10" section still states
   only 10.1/10.2/10.4 are approved — inconsistent
   with a completed 10.5.
4. **R-10.4.8 lists "frontend upload UI" as
   excluded.** Phase-scoped and true at the time,
   but now reads as a standing prohibition
   contradicting 10.5. Needs a scope-clarifying
   note, not a silent edit.
5. **tasks/active/ holds three stale files**
   (phase-0-3, phase-1-8, phase-1-10) while
   AGENTS.md allows exactly one active task —
   completed ancient work never moved out.
6. **"No commit/push performed" lines** in phase
   docs 10.4 §9 and 10.5 §9 are stale after
   checkpoint `9249544`. Historical verification-time
   statements — leave intact, note here.
7. **ADR-0011 Consequences / Decision-7** still say
   "not yet written" persistence extension — true of
   the ADR's constraining scope (10.4 implemented
   it); readers must follow the addendum. No change
   recommended beyond this note.
8. No unapproved future scope found in docs; no
   completed capability lacks a task record
   (completed/ holds 10.1–10.5); no live execution
   is falsely claimed anywhere reviewed.

## 8. Audit verification

- Documents internally consistent; no live service
  claimed tested (all live paths recorded NOT
  EXECUTED / gated).
- Implementation files untouched — confirmed via
  `git status` / `git diff --stat`: only
  `ACTIVE_TASK.md`, `CURRENT_STATE.md`, and the two
  new audit documents differ from checkpoint
  `9249544`. Pre-existing untracked scratch
  (`.freebuff/`, `frontend/t5.txt`,
  `frontend/test-output.txt`) and a `uv.lock`
  (not produced by any audit command) remain
  uncommitted and untouched.
- No implementation phase started; no roadmap phase
  created; no open question answered.
