# Phase 4D.10 — Authorization Evidence Procedure

> Status: documented; evidence-retention mechanism proposed but NOT configured.
> No authorization record exists; no evidence file or reference has been created.

## Evidence retention requirement (explicit, unresolved operational configuration)

The independent verification evidence must be stored outside the repository (not in Git, not in `.env`, not in tracked documentation). The repository does not currently specify an organization-controlled evidence store.

**Proposed resolution (not executed — requires product-owner or authorized operator action):**
- Store: an organization-controlled, access-controlled document or secret store separate from this repository (e.g., company document management system, approved secure messaging archive, or designated operational record repository).
- Access: restricted to the product owner (authorizer), the independent verifier, and a designated independent auditor.
- Retention: retained for the duration of the audit retention period (currently provisional 24 months; final retention/deletion policy disabled and unresolved).
- Linkage: the `authorization_ref` stored in `global_staff_authorizations` is a non-empty, verifiable identifier (e.g., `auth-ref-YYYY-MM-DD-<initials>` or a secure reference ID). The auditor verifies authorization by comparing the database `authorization_ref` against the retained evidence record.
- This task does NOT create, configure, or claim the existence of this store. It must be established by an authorized operational action before any authorization record is created.

## Evidence elements required (minimum)

For any initial `grant_manage` authorization to proceed, the following evidence must exist independently of the database and must reference the `authorization_ref`:

1. **Authorizer identity/reference** — the product owner (or designated authority) explicitly named in writing.
2. **Target user identity/reference** — the internal user UUID (`users.id`) resolved via verified mapping (`supabase_uid` → `users.id`); never hardcoded in documentation.
3. **Permission scope** — exactly `grant_manage`; no additional permissions authorized by this procedure.
4. **Independent verifier identity/reference** — a separate individual, not the target, not the authorizer (unless an exception is explicitly authorized with justification and audit linkage).
5. **Verification timestamp** — `verified_at`, recorded by the verifier.
6. **Trusted out-of-band verification method** — the specific channel (e.g., signed message reference, recorded approval meeting, documented operational procedure reference). This must be an explicitly identified channel; a generic statement is insufficient.
7. **Authorization reference (`authorization_ref`)** — non-empty, unique per authorization, verifiable. Must match exactly between the database record and the independent evidence.
8. **Justification** — documented reason for the authorization, not an arbitrary string.
9. **Status and timestamps** — `approved` (or `revoked`/`rejected` as appropriate), `approved_at`, `verified_at`, `consumed_at` (after use), `revoked_by` (if revoked).
10. **Audit reconciliation** — the authorization reference is preserved in `global_staff_audit` (`authorization_ref` column from migration 017) and links the authorization event to the independent evidence.

## What the evidence procedure does NOT authorize

- Creating or approving the initial authorization record (`global_staff_authorizations`).
- Creating the initial `grant_manage` grant (`global_staff_grants`).
- Using the `.env` `postgres` connection as proof of authorization (it is the superuser/admin role, not authorization evidence).
- Inventing a completed verification event, timestamp, or reference.
- Storing evidence in Git, `.env`, or any tracked repository file.

## Next required action (operational, not code)

Before any live authorization can proceed, an authorized operator must:
1. Confirm or establish the organization-controlled evidence store and specify its exact location/access mechanism.
2. Confirm or resolve the database role configuration (`postgres` superuser vs. dedicated `xportra_app` role — see `docs/deployment/bootstrap-authorization-db-role.md`).
3. Complete the independent authorization and verification, recording all ten evidence elements with the `authorization_ref`, retaining the evidence independently.
4. Only then create the authorization record (`global_staff_authorizations`) with `status = 'approved'` using the verified reference.
