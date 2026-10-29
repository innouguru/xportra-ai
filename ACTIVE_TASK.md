# ACTIVE_TASK.md — Current Active Task

**Active task:** Phase 4D — Regulatory Administration Backend — Milestone 1
(staff-only regulatory ingestion administration API).

**Status:** In progress — implementation complete, tests passing, documentation
pending, commit pending.

**Authorization basis:** Explicitly assigned by user tasking. The existing
bootstrap task (initial `grant_manage` provisioning under `XPA-GSA-INIT-001`)
remains a separate, not-yet-executed track described in
`CURRENT_STATE.md` and `tasks/active/phase-4d-task-1-authorization.md`; it is
not part of this milestone and no bootstrap is executed here.

## Implemented (this milestone)

1. **Source-ingestion operation**
   - `POST /regulatory/sources/{source_id}/artifacts` — staff-uploaded artifact;
     accepts `text/plain`, `text/markdown`, `application/json`, `application/pdf`
     (PDF previously rejected; now accepted — domain parsing already supported it).
     Validates file type, size (10 MB), base64 content, required metadata via the
     source pre-check. Stores original bytes in the private regulatory
     source-artifact storage; persists artifact row + durable pending ingestion job.
     Idempotent on identical content hash (no duplicate artifacts/jobs).
   - `POST /regulatory/sources/{source_id}/artifacts/text` — staff-entered inline
     text; accepts `text/plain`, `text/markdown` (no file upload). Same storage,
     artifact, job, and idempotency guarantees.
   - `POST /regulatory/sources` — source registration (existing; requires grant).

2. **List and inspect sources/jobs**
   - `GET /regulatory/sources` (paginated), `GET /regulatory/sources/{source_id}`,
     `GET /regulatory/ingestion-jobs/{job_id}`,
     `GET /regulatory/sources/{source_id}/ingestion-jobs` (paginated).
   - Processing status, safe error information, metadata included. No credentials
     or storage paths returned.

3. **Extraction outcomes** (existing, re-exposed)
   - `POST /regulatory/ingestion-jobs/{job_id}/extract`, `GET
     /regulatory/sources/{source_id}/candidates`, `GET /regulatory/candidates/{candidate_id}`.
   - Candidate provenance traces to source/artifact/ingestion job via
     `ingestion_job_id`, `artifact_id`, `source_id`, `normalized_document_id`.

4. **Safe retry** — reuses existing job lifecycle (`pending` → claimed →
   completed/failed/retryable) and idempotency (content-hash dedup, advisory
   locks). No duplicate jobs/artifacts from repeated requests. No new queue
   service.

## Authorization and audit

- All mutating and read-only regulatory-admin routes require `GRANT_MANAGE`
  via `require_global_staff` (actor resolved from verified JWT subject →
  `users.supabase_uid` → `users.id`; tenant membership never substitutes).
- Fail-closed on missing/invalid authentication, inactive/unknown user, or
  missing/revoked grant.
- Audit through existing `GlobalStaffAuditRepository` / `global_staff_audit`
  mechanism at the service layer.
- No hard-coded staff user, no automatic permission grants, no bypass.

## Files changed

- `xportra/application/regulatory_source_intake_service.py` — accept `application/pdf`;
  extract shared `_store_artifact`; add `enter_text_artifact`.
- `xportra/api/schemas.py` — add `RegulatoryTextEntryRequest`,
  `RegulatoryArtifactTextResponse`.
- `xportra/api/regulatory_admin.py` — add `POST
  /regulatory/sources/{source_id}/artifacts/text` route; update upload docstring.
- `tests/unit/test_regulatory_source_intake.py` — PDF acceptance test; 10 staff-text
  tests (accept, markdown, empty/whitespace rejection, pdf type rejection,
  unsupported type rejection, unauthorized denial, nonexistent source, idempotency,
  size limit).

## Migration

None added. Existing migrations 018–029 (ingestion jobs, candidate extraction,
stage A/B, legal hold, deletion intent, review flags) already support the
requirement. No schema change needed.

## Remaining work / limitations

- Bootstrap (`XPA-GSA-INIT-001`) not executed; no `grant_manage` grant exists,
  so the endpoints cannot be exercised end-to-end against a live database until
  bootstrap is separately authorized and performed.
- Integration (PostgreSQL) tests skipped without an isolated `xportra_test`
  database; not run against the configured `DATABASE_URL` (shared/production).
- Stage A/B review, publication eligibility, and exporter-facing behavior exist
  in code but are gated behind `STAGE_A_VERIFY`/`STAGE_B_APPROVE` grants and are
  not part of this milestone.
- No deletion endpoint for artifacts (blocked by retention policy; deliberate).

## Next recommended milestone

Phase 4D task 3/4 — durable ingestion pipeline execution (worker dispatch,
parsing/extraction wiring) and Stage A/B review API wiring, pending separate
authorization.
