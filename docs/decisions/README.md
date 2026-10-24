# docs/decisions — Architecture Decision Records (ADRs)

This directory holds Architecture Decision Records. Per `INVARIANTS.md`,
any change to structure, boundaries, data flow, storage, or cross-cutting
concerns requires an ADR here **before** implementation.

- Status: 20 ADR files recorded as of 2026-10-24 (ADR-0001 through
  ADR-0020; no gaps). ADR-0017 is accepted as the basis for
  implementation planning only. ADR-0018 is a completed technology
  review with unresolved prerequisites. ADR-0019 records the migration
  029 engineering disposition (technical consistency satisfactory;
  historical provenance unverified; blocked from production
  application). ADR-0020 is the migration 029 reconstruction note
  (provenance remains UNVERIFIED).
- Naming: `ADR-0001-short-title.md`, incrementing.
- Each ADR must record: context, decision, alternatives considered,
  consequences, and linked requirements/tasks.

## Current ADR set

- `ADR-0001-deterministic-applicability-authoritative.md`
- `ADR-0002-free-first-technology-baseline.md`
- `ADR-0003-source-authority-framework.md`
- `ADR-0004-psycopg-persistence-boundary.md`
- `ADR-0005-fastapi-application-boundary.md`
- `ADR-0006-supabase-authenticated-tenant-boundary.md`
- `ADR-0007-tenant-role-authorization-boundary.md`
- `ADR-0008-production-security-hardening.md`
- `ADR-0009-conversational-boundary.md`
- `ADR-0010-conversational-backend-foundation.md`
- `ADR-0011-evidence-upload-ingestion-boundary.md`
- `ADR-0012-authenticated-shell-restructure.md`
- `ADR-0013-shipment-aggregate-boundary.md`
- `ADR-0014-es256-jwks-verification-supabase-signin.md`
- `ADR-0015-production-auth-registration-stabilization.md`
- `ADR-0016-auth-initialization-and-public-shell.md` (accepted)
- `ADR-0017-regulatory-knowledge-administration.md` (accepted for planning only)
- `ADR-0018-storage-technology-decision.md` (technology review complete;
  storage/access policy and PDF parser integration unresolved;
  in-process worker conditionally approved)
- `ADR-0019-migration-029-regulatory-review-flags.md` (technical
  consistency satisfactory; provenance unverified; blocked from
  production application)
- `ADR-0020-reconstruction-note.md` (reconstruction note for migration
  029; provenance UNVERIFIED; not an authorization to apply the
  migration)
