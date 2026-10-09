# production-qdrant-provisioning — Complete

Docs + specification task, complete 2026-10-08. No code, corpus,
ingestion, deployment, Supabase, or dependency change. Nothing
provisioned (user provisions via provider UI).

Origin: `tasks/completed/render-production-wiring.md` + assignment.
Traceability: `REQUIREMENTS.md` TB-4 (Qdrant baseline), TB-6
(`all-MiniLM-L6-v2` embeddings), R-10.1 (hardening scope).

## Existing RAG configuration discovered (read-only)

- `VECTOR_STORE_URL`, `VECTOR_STORE_COLLECTION`, `EMBEDDING_MODEL`,
  `EMBEDDING_DIMENSIONS`: all required, no defaults; blank fails
  closed to per-route 503 (`rag_composition.py`). Single collection
  var feeds retrieval AND upload index-sync (always agree).
- Metric: cosine only (no env override — `domain/vector_index.py`).
- Collection auto-created idempotently at first `upsert`
  (`ensure_collection`: create-if-missing, validate-never-destroy);
  reads never create. Lifespan never calls it.
- Payload `content` text index auto-provisioned on first lexical
  query; manual payload indexes forbidden (incompatible ones fail
  closed). Nothing required upfront.
- Auth: app passes NO API key (no `api_key` in `xportra/`, no env
  var); installed client supports it, app does not wire it.
- TLS: transparent via URL string (`https://` supported).
- No Qdrant health endpoint in app code; no live RAG smoke in the
  normal suite (gated `test_rag_qdrant_smoke.py` uses throwaway
  collections under `QDRANT_URL`).

## Production specification (in `XPORTA-V1-DEPLOYMENT.md` §14)

- Render env: endpoint + operator-chosen collection name (no repo
  default) + `all-MiniLM-L6-v2` / `384` (code re-validates both).
- Collection: single unnamed vector, size 384, Cosine; no manual
  payload indexes; may be absent (created at first ingestion).
- Recommendation: **Qdrant Cloud Free Tier** (verified 2026-10-08:
  1 node, 0.5 vCPU/1 GB/4 GB, no card; ample for thousands of
  384-dim chunks; suspends after ~1wk idle, deleted after ~4wks).
  Caveat documented: Cloud mandates API-key auth which current code
  cannot send — path (a) provision now + follow-on key-wiring task,
  path (b) keyless self-host works today but is NOT recommended
  (ops burden, ephemeral-disk risk). Until key support lands, RAG
  paths keep their designed 503 degradation.
- Verification (§14.5, six steps, curl + repo smoke test): 200 on
  `/`, auth-posture check (401 on key-mandated host = stop and
  schedule key wiring), 404-on-collection is the EXPECTED pass
  (empty), dims/metric match if present, count 0, throwaway
  `xportra-smoke-*` live-smoke. Expected end: reachable, correct,
  EMPTY. Provisioning ≠ ingestion (stated explicitly).

## Verification (this task)

- Safe unit suites only: `test_rag_composition`,
  `test_rag_production_verification`, `test_evidence_vector_index`,
  `test_render_production_wiring`, `test_evidence_retrieval_scope`,
  `test_evidence_retrieval` → **237 passed, 0 failures**.
- No OpenRouter call, no model download, no live Qdrant
  (`QDRANT_URL`/`VECTOR_STORE_URL` confirmed unset). No packages.
- No secrets read or written (names/placeholders only).

## Files changed (this task only)

- `docs/deployment/XPORTA-V1-DEPLOYMENT.md` (§2 prereq, §3 RAG rows,
  §11 Qdrant checklist item, new §14 spec/recommendation/verification)
- `ACTIVE_TASK.md`, `CURRENT_STATE.md`, this record (state)

## Next

User action: create the Qdrant Cloud Free Tier cluster in the
provider UI (name + provider + region), note the REST endpoint
(+ API key, stored for the later key-wiring task), run §14.5 and
record results. Exact next Xportra task after provisioning:
Render web-service configuration + backend deploy + §10 smoke
(or the API-key wiring micro-task first, if path (a) and RAG ships
in v1).
