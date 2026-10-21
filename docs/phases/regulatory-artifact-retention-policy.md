# Regulatory Source Artifact Retention Policy (Proposed — Awaiting Approval)

**Status:** Proposed. Not implemented as automatic deletion. No approved retention duration exists.

**Scope:** Original regulatory source artifacts (`regulatory_source_artifacts` table; durable storage in the dedicated private bucket `regulatory-source-artifacts`). This policy is separate from tenant evidence retention (`tenant-evidence` bucket) and separate from the provisional 24-month audit retention (`global_staff_audit`, `global_staff_grants` audit events).

**Reference:** ADR-0017 §5 (artifact retention, deletion, and supported formats); ADR-0017 §8 (re-review when sources change); technology baseline (`docs/architecture/technology-baseline.md`); storage technology review (`docs/decisions/ADR-0017-storage-technology-decision.md`).

## Proposed retention rules

1. **Current and verified artifacts:** Retained as long as the linked regulatory requirement remains published (Stage B applicable/current) and the source is current (not superseded, withdrawn, or stale). No automatic expiration.
2. **Superseded/stale artifacts:** Once superseded by a newer version (`supersedes` / `superseded_by` metadata), the older artifact must be preserved for provenance and audit purposes. A recommended provisional retention period is **24 months from supersession date**, matching the provisional audit retention period from Phase 4D.10 authorization readiness (`CURRENT_STATE.md` / `docs/decisions/ADR-0017-regulatory-knowledge-administration.md`). This period must be confirmed by product-owner/operational authority before any deletion is enabled.
3. **Rejected/withdrawn artifacts:** Artifacts linked to rejected requirements or withdrawn sources must be preserved with their audit linkage (rejection/review history, source reference, content hash, exact location). Deletion requires explicit authorization and must record the authorizing actor (`actor_user_id`), authorization reference (`audit_ref`), timestamp, and reason in an append-only audit event (`global_staff_audit`). A recommended provisional retention period is **24 months from withdrawal/rejection date**, subject to approval.
4. **Artifacts linked to published requirements:** Must never be deleted while the linked canonical requirement remains published (Stage B applicable/current). Deletion is permitted only after the requirement is superseded, withdrawn, or explicitly deprecated through a new Stage B decision, with audit linkage preserved.
5. **Artifacts linked to unresolved/review-required requirements:** Must remain available for re-review and must not be deleted while any linked requirement is in an unresolved/review-required state. Deletion requires an explicit authorization event linking to the resolved/rejected/review-completed decision.
6. **Manual recovery artifacts:** Artifacts created through manual candidate entry (after failed/partial extraction) must be preserved with the original extraction status (`failed`, `partial`, `zero_candidates`), reviewer attribution, source/provenance metadata, and audit reference. Deletion requires the same authorization controls as any other artifact.
7. **Deletion mechanism:** Deletion must be an explicit, auditable mutation (not automatic or scheduled). The authorization boundary (`GRANT_MANAGE` active grant) applies. The deletion event must be recorded in the audit mechanism (`global_staff_audit`) with `actor_user_id`, `authorization_ref` (if applicable), timestamp, justification, and a reference to the deleted artifact (`artifact_id`, `content_hash`). Deletion must never erase audit events or historical review decisions.
8. **Retention duration:** The exact duration (e.g., 24 months, 36 months, indefinite) remains **unresolved** and requires product-owner/operational authority approval. The provisional recommendation is **24 months for superseded/rejected artifacts**, **indefinite for current/published artifacts**, with a required authorization for any deletion.
9. **Legal holds:** Any legal or compliance hold (e.g., dispute, audit request, regulatory inquiry) must suspend deletion for the affected artifacts. The hold must be recorded with an authorization reference and must prevent automatic or manual deletion until explicitly released.

## Operational prerequisites before enabling deletion

- Confirm the dedicated private storage bucket/access policy for regulatory artifacts is configured (`docs/decisions/ADR-0017-storage-technology-decision.md`).
- Confirm retention/deletion duration is approved by the product-owner/operational authority.
- Confirm the authorization mechanism for deletion (`global_staff_grants` + `GRANT_MANAGE` active grant) is configured and a service identity is provisioned (Task 2 prerequisites; `tasks/blocked/bootstrap-authorization-policy.md`).
- Confirm audit linkage (`global_staff_audit`) is operational and verified.
- Confirm no deletion endpoint is exposed without authorization checks.
- Confirm the deletion mechanism records audit events atomically with the deletion mutation (fail-closed: if audit insertion fails, the deletion is rolled back).

This policy is a proposal. No automatic deletion mechanism is implemented or enabled in the current repository (`migrations/018_regulatory_ingestion_jobs.sql` contains no deletion logic; `RegulatoryIngestionService` does not implement deletion; `EvidenceObjectStore.delete` exists for compensating deletes only, not user-facing deletion; no deletion endpoint exists in any router).
