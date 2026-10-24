# Regulatory Source Artifact Retention Policy (Product-Owner Approved — Option A)

**Status:** Approved by product owner on 2026-10-21 (Option A). Not implemented as automatic deletion; no production deletion endpoint is enabled.

**Approval does not authorize:** immediate deletion; automatic deletion scheduling; production deployment of deletion; or changes to staff grants (`GRANT_MANAGE`). Deletion must remain explicit, authorized, auditable, and fail-closed.

**Scope:** Original regulatory source artifacts (`regulatory_source_artifacts` table; durable storage in the dedicated private bucket `regulatory-source-artifacts`). Separate from tenant evidence retention (`tenant-evidence` bucket) and separate from provisional audit retention (`global_staff_audit`, `global_staff_grants`).

**Reference:** ADR-0017 §5 (artifact retention, deletion, supported formats); ADR-0017 §8 (re-review when sources change); technology baseline (`docs/architecture/technology-baseline.md`); storage technology review (`docs/decisions/ADR-0018-storage-technology-decision.md`).

## Approved retention rules (2026-10-21)

1. **Current/published regulatory artifacts:** Indefinite retention while the linked regulatory requirement remains published (Stage B applicable/current) and the source is current.
2. **Superseded, rejected, and withdrawn provisional artifacts:** 24 months from supersession, rejection, or withdrawal date.
3. **Legal holds:** Must prevent deletion until explicitly released; hold must be recorded with authorization reference.
4. **Deletion mechanism:** Explicit, auditable mutation only (not automatic or scheduled). Must fail closed if authorization (`GRANT_MANAGE` active grant), hold status, or audit recording (`global_staff_audit`) cannot be verified. Must record `actor_user_id`, `authorization_ref`, timestamp, justification, `artifact_id`, and `content_hash`.
5. **Artifacts linked to unresolved/review-required requirements:** Must not be deleted while unresolved; deletion requires authorization linking to resolved/rejected/review-completed decision.
6. **Manual recovery artifacts:** Preserve original extraction status and audit linkage; same authorization controls apply.
7. **Audit preservation:** Deletion must never erase audit events or historical review decisions.

## Unresolved open questions (not settled by approval)

- Exact storage/access policy configuration for the dedicated private bucket (`regulatory-source-artifacts`) remains open (`ADR-0018-storage-technology-decision.md`).
- Service identity (`REGULATORY_WORKER_ACTOR_USER_ID`) and active `GRANT_MANAGE` grant provisioning are not completed (`tasks/blocked/bootstrap-authorization-policy.md`).
- PDF parser integration (`PyMuPDF`) and dependency declaration remain open (`pyproject.toml` gap).
- Production ingestion and deletion endpoint exposure remain unimplemented; no automatic scheduling is approved.
- Operational ownership, budget/hosting confirmation, and exact audit linkage atomicity verification remain open.

## Operational prerequisites before any deletion is enabled

- Confirm dedicated private storage bucket/access policy (`docs/decisions/ADR-0018-storage-technology-decision.md`).
- Confirm authorization mechanism (`global_staff_grants` + `GRANT_MANAGE`) and service identity are provisioned.
- Confirm audit linkage (`global_staff_audit`) is operational and verified.
- Confirm no deletion endpoint is exposed without authorization checks and that audit insertion is atomic with deletion (fail-closed rollback).
- Confirm legal-hold mechanism is implemented and tested.

Deletion remains blocked until all of the following are implemented and tested: (a) legal-hold mechanism with authorization reference and suspension/release; (b) artifact-level audit event (actor_user_id, authorization_ref, timestamp, justification, artifact_id, content_hash) recorded atomically with the deletion mutation; (c) fail-closed rollback when audit insertion fails; (d) no adapter-level deletion path exposed without application-level authorization and audit verification. The adapter's `delete` method is not exposed through any authorized application service at this time.

This approval does not change repository deletion behavior (`migrations/018_regulatory_ingestion_jobs.sql` contains no deletion logic; `RegulatoryIngestionService` does not implement deletion; `EvidenceObjectStore.delete` remains compensating-only; no deletion endpoint exists in any router).
