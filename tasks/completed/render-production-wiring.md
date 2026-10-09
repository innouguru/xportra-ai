# render-production-wiring — Complete

Single scoped task: Render production wiring — lifespan composition,
`GET /health`, SUPABASE_URL production gate, start-command and env-contract
documentation. Complete 2026-10-08.

Origin: `tasks/completed/production-deployment-readiness-audit-render.md`
(blockers B1–B4). Traceability: `REQUIREMENTS.md` R-10.1 (production
security/configuration hardening; no product behavior changed, no boundary
weakened) plus this explicitly assigned deployment task.

## Implementation performed

1. **Lifespan composition** (`xportra/api/dependencies.py`,
   `xportra/api/app.py`):
   - New `ApplicationServices.from_environment_with_capabilities()`:
     database-backed base first (`DATABASE_URL` stays a boot gate),
     then RAG (`compose_rag_stack_from_environment`), object storage
     (`compose_evidence_object_store_from_environment`), and index sync
     (`compose_evidence_index_sync_from_environment`) each attempted
     independently through the EXISTING composers — no second
     implementation, no duplicated config parsing (lazy `importlib`,
     preserving the no-static-`xportra.infrastructure`-dependency
     boundary). Each optional fails closed to `None`, preserving the
     exact per-route 503s. No external call at composition (lazy
     clients, lazy embedding model, `ensure_collection` never invoked).
   - `app.py` lifespan uses it when no services are injected; the
     explicit `from_environment` / `from_environment_with_rag` /
     `from_environment_with_evidence_upload` seams are unchanged.
2. **`GET /health`** (new `xportra/api/health.py`, included in `app.py`):
   unauthenticated, no dependencies, no DB/Supabase/Qdrant/OpenRouter
   access, no config reads; `200 {"status": "ok"}`. Liveness only —
   never a readiness probe. Authenticated behavior unchanged.
3. **No-startup-connectivity fix** (`rag_composition.py`,
   `evidence_upload.py`): both `QdrantClient(...)` constructions now pass
   `check_compatibility=False` with a comment. Reason: the client default
   spawns a background thread that HTTP-probes the server version at
   construction — a startup connectivity check, forbidden by this task.
   Found via a `UserWarning` during test development; verified gone
   afterwards. No functional behavior change (the probe is advisory and
   warn-only; real failures still surface fail-closed per request).
4. **B4 gate** (`xportra/api/runtime.py`): `validate_production_environment`
   now requires non-blank `SUPABASE_URL`, so production always pins the
   `<url>/auth/v1` issuer check. Per-request auth semantics untouched.
5. **No PORT code**, per assignment (Render supplies `$PORT` to the shell
   command).
6. **Docs**: `XPORTA-V1-DEPLOYMENT.md` (§7 Render start command +
   lifespan/capability behavior + `/health`; §3 + §6 SUPABASE_URL
   required; §10 step 0 health; §11 health + start-command checklist
   items); `.env.example` comment (SUPABASE_URL + start command);
   `environment-schema.md` SUPABASE_URL entry (required in production).
   CORS untouched (still `CORS_ALLOWED_ORIGINS`, explicit-only).

Architectural note (no ADR filed): no boundary, structure, data-flow, or
storage contract changed — existing composers wired into the existing
lifespan seam, one dependency-free liveness route consistent with
ADR-0005/ADR-0008, identical fail-closed semantics.

## Tests

- New `tests/unit/test_render_production_wiring.py` (21 tests):
  health (200/stable body, no auth, no DB config, available with docs
  disabled, security headers); core-only composition (boots, optionals
  `None`, health serves, anonymous core route still 401, RAG/upload
  dependencies 503 with established codes, malformed optionals degrade,
  missing DB still fails boot); fully-configured composition against
  unroutable placeholders (all three capabilities wired to production
  classes, embedding not downloaded, zero background threads started,
  app boots); SUPABASE_URL gate (required/blank-rejected in
  production, not required elsewhere, composed-path gate).
- Legitimate existing-test updates for the strengthened contract (not
  weakening): added `SUPABASE_URL` to the two production "accepts" dicts
  (`test_phase_10_1_production_security.py`,
  `test_cors_boundary.py`).
- Results: new file 21/21; focused security+CORS+wiring 82 passed +
  39 subtests; RAG/API/upload/compliance focused 222 passed +
  22 subtests; FULL suite `pytest tests`: **2060 passed, 51 skipped
  (gated integration — no DATABASE_URL/live services), 61 subtests,
  0 failures**. No packages installed. No live credentials, no network
  calls, no secret values in code/docs/tests/logs (placeholders only).

## Remaining blockers / next step

Code complete; NOT deployed, Qdrant NOT provisioned, Supabase unchanged.
Remaining prerequisite before v1 smoke: provision hosted Qdrant
(collection sized to `EMBEDDING_DIMENSIONS`) iff RAG analysis is in v1
scope. Exact next step: configure the Render web service (start command
`uvicorn xportra.api.app:app --host 0.0.0.0 --port $PORT`, §4 production
env contract from the assignment, health check → `/health`), deploy the
backend, then run `XPORTA-V1-DEPLOYMENT.md` §10 smoke from step 0.

## Files changed (this task only)

- `xportra/api/dependencies.py` (+combined composer)
- `xportra/api/app.py` (lifespan + health router)
- `xportra/api/health.py` (new)
- `xportra/api/runtime.py` (SUPABASE_URL production gate)
- `xportra/infrastructure/rag_composition.py` (`check_compatibility=False`)
- `xportra/infrastructure/evidence_upload.py` (`check_compatibility=False`)
- `tests/unit/test_render_production_wiring.py` (new, 21 tests)
- `tests/unit/test_phase_10_1_production_security.py` (+URL in accepts dicts)
- `tests/unit/test_cors_boundary.py` (+URL in valid-boot dict)
- `docs/deployment/XPORTA-V1-DEPLOYMENT.md`, `.env.example`,
  `docs/architecture/environment-schema.md` (contract documentation)
- `ACTIVE_TASK.md`, `CURRENT_STATE.md`, this record (state)

Note: the working tree also holds earlier uncommitted task changes
(pyproject uvicorn dep, phase-10-5 note, CORS-boundary work, prior task
records) — pre-existing, not this task, left untouched per the
no-commit convention. Criterion "diff contains only task-necessary
changes" holds for this task's own hunks.
