# Regulatory Storage Boundary Audit — Read-Only (2026-10-21)

Verdict: BLOCKED.

## Authorization path
Application layer (`GlobalStaffGrantService.is_granted(actor, GRANT_MANAGE)`) enforces for `start_ingestion` and `claim_job` (`xportra/application/regulatory_ingestion_service.py`). Adapter (`RegulatorySourceStorageAdapter`) provides `put`/`delete`/`create_signed_url` without authorization checks (`xportra/infrastructure/regulatory_artifact_storage.py`). No router endpoint exists for regulatory artifacts; retrieval authorization is unimplemented.

## Bypass paths
- Adapter mutations callable directly without authorization or audit.
- `RegulatoryIngestionService.complete_job` / `fail_job` do not enforce `GRANT_MANAGE`.
- Signed URL issuance (`create_signed_url`) unmediated at adapter boundary.

## Storage boundary
Dedicated bucket `regulatory-source-artifacts` (`REGULATORY_SOURCE_ARTIFACTS_BUCKET`) separate from `tenant-evidence`. Adapter uses `SupabaseEvidenceObjectStore` (HTTPS/service-role key). Basic path validation only; no content-type/size/encryption validation at adapter. No public access exposed by contract.

## Deletion / holds / audit
- Deletion exists only as adapter `delete()` (compensating only); no user-facing endpoint.
- No legal-hold mechanism implemented (documented only in retention policy).
- No artifact-level deletion audit mechanism (`global_staff_audit` covers grants only); fail-closed rollback not implemented.

## Missing deployment / access controls
- Dedicated bucket/access policy unresolved (`docs/decisions/ADR-0018-storage-technology-decision.md`).
- Service identity (`REGULATORY_WORKER_ACTOR_USER_ID`) and active `GRANT_MANAGE` grant not provisioned.
- PDF parser dependency gap (`pyproject.toml`) remains open.
- No separate application DB role configured (observed `postgres` reference; no secret revealed).

## Focused tests needed before deployment
- Authorization on all adapter mutation/retrieval paths.
- Retrieval route authorization before signed URL issuance.
- Deletion audit atomicity and rollback.
- Legal-hold suspension/release mechanism.
- Content validation (type/size/magic bytes) at adapter.
- Service identity/grant provisioning integration.

## Recommended next step (no production change)
Document adapter authorization gap and schedule separately authorized task to wire `require_global_staff` into any future regulatory artifact endpoint, implement audit/hold/deletion logic, and confirm dedicated bucket/access policy deployment before production ingestion.
