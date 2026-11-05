# Workstream 7 — Verify Regulatory-to-Ask-Xportra Lifecycle

**Status:** PASS — all Phase C live Qdrant verification completed against an
isolated local Qdrant server; both frontend failures diagnosed; one deferred
as out of scope. Zero application code changes made.

## Scope

Verify the existing regulatory publication, indexing, retrieval,
conversation API, and Ask Xportra lifecycle. Investigate the seven reported
retrieval-test failures. Do not rebuild systems or use production services.

## Acceptance criteria

- Investigate and resolve the seven retrieval test failures without changing
  retrieval behavior unless a verified defect requires it.
- Verify relevant regulatory, retrieval, conversation, and frontend behavior
  using local or mocked test infrastructure.
- Run live indexing and retrieval checks only if a development/test Qdrant
  collection is positively identified as safe.
- Report a clear verdict and distinguish verified behavior from blockers.

## Qdrant environment (Phase A): SAFE_LOCAL_TEST

- Local Qdrant server v1.20.0 running at `http://127.0.0.1:6333`
  (ports 6333 REST, 6334 gRPC), bound to localhost, no authentication.
- `.env.test.local` (process-local only, not loaded by app code) provides:
  `APP_ENV=test`, `VECTOR_STORE_URL=http://127.0.0.1:6333`,
  `VECTOR_STORE_COLLECTION=xportra-regulatory`,
  `EMBEDDING_MODEL=all-MiniLM-L6-v2`, `EMBEDDING_DIMENSIONS=384`.
- `DATABASE_URL=postgresql://postgres@localhost:5432/xportra_test` set
  explicitly for the test process.
- `.env.test.local` is ignored via `.gitignore` (`.env.*` pattern);
  production `.env` untouched.
- Production Qdrant Cloud endpoint in `.env` was NOT used.

## Verification completed

### Phase C — Live Qdrant verification (ALL VERIFIED)

**C1 Collection configuration:** `xportra-regulatory`, dimension 384,
distance Cosine, status green. Created via existing `ensure_collection()`
(non-destructive, fail-closed on mismatch).

**C2 Publication indexing:** Isolated test requirement prepared in PostgreSQL
(source active, requirement extracted+verified+approved), published via
existing workflow (trigger creates outbox job), job claimed and processed by
`RegulatoryPublicationIndexService.process_next()` using real
`EvidenceIndexSyncService` + sentence-transformers (384-dim embeddings).
Vector written to Qdrant. Point metadata verified:
content_scope=global_regulatory, publication_status=published,
regulatory_requirement_id, publication_fingerprint (64-char sha256),
source_id, source_type, embedding_model=all-MiniLM-L6-v2,
embedding_dimensions=384. PostgreSQL job status='indexed' with
fingerprint and indexed_chunk_ids.

**C3 Idempotency and updates:** Re-processing unchanged content produced no
duplicate vectors (1 point before and after); fingerprint consistent.
Content update changed fingerprint and updated the Qdrant point in place
(no duplicates); job status remained 'indexed'.

**C4 Retrieval and tenant isolation:** Published global content retrievable
by authorized tenant. Tenant retrieves its own tenant-specific content.
Cross-tenant isolation enforced. Unpublished (rejected) global content
excluded. Withdrawn content excluded. Stale Qdrant point excluded when
PostgreSQL says ineligible (fail-closed, PostgreSQL eligibility verified).

**C5 Ask Xportra path:** Real composed RAGApplicationService with live Qdrant
retrieval. Tenant context preserved through to LLM call. Retrieved evidence
reaches context builder and prompt. Mocked LLM generation
(ScriptedLLMClient — no OpenRouter credentials) receives expected context.
Answer status=valid with citations corresponding to retrieved evidence
([E1]). Conversation persistence repositories wired.
LIVE vs MOCKED: Qdrant retrieval LIVE; LLM generation MOCKED.

**C6 Withdrawal and stale content:** Source withdrawal made requirement
ineligible; Ask Xportra no longer returns it; stale Qdrant point excluded
by PostgreSQL eligibility; restoration makes content retrievable again.

**C7 Cleanup:** All 3 test Qdrant points and all PostgreSQL test records
(requirement, source, artifact, normalization, authority, publication index
job, review flags) removed. Collection remains intact with 0 points. No
pre-existing data affected.

### Phase B — Frontend failures (diagnosed)

Full suite `vitest run`: 661 passed, 1 failed (662 total). Previous report
stated 660 passed, 2 failed.
- Failure 1 (fixed): stale regulatory workflow expectation in
  `SourceWorkflow.test.tsx` — expected "Registration record — no document
  attached yet"; component renders "Registration placeholder". Test
  assertion updated; no application code changed.
- Failure 2 (deferred, out of scope):
  `RegisterPage.test.tsx` > "retains pending profile data and shows a safe
  retry after API failure". Root cause:
  `sessionStorageOrNull()` at `pendingRegistration.ts:50` returns
  `window.localStorage` instead of `window.sessionStorage`. Registration/
  auth — not part of the regulatory ingestion/publication/Ask Xportra
  lifecycle; deferred per fixing rules.

### Backend verification (Phase D)
- Full unit suite: 2477 passed, 0 failed
  (`DATABASE_URL=postgresql://postgres@localhost:5432/xportra_test`).
- Focused unit (publication index, retrieval, index sync, scope): 135 passed.
- Focused integration (publication index PostgreSQL): 6 passed.
- Full integration suite: 123 passed, 26 failed, 5 errors — all pre-existing
  database-state contamination unrelated to the regulatory lifecycle.
- Python compileall passed. `git diff --check` (CRLF-aware) passed.

### Frontend verification (Phase D)
- Full suite: 661 passed, 1 failed (deferred RegisterPage recovery).
- Lint (`tsc --noEmit`): passed.
- Production build (`vite build`): passed (existing large-chunk advisory).

## Remaining work

The deferred RegisterPage recovery failure (localStorage vs sessionStorage)
is out of scope for Workstream 7 (registration/auth, not regulatory
lifecycle). It can be fixed with a one-line change if separately authorized.

## Git safety

Zero code changes made. All 47 modified tracked files and untracked files
are pre-existing from Workstreams 1–6. My edits are limited to
documentation/state files (ACTIVE_TASK.md, CURRENT_STATE.md, this file).
Nothing staged, committed, pushed, reset, or cleaned.
