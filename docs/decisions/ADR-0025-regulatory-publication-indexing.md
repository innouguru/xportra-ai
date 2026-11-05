# ADR-0025: Regulatory Publication Indexing and Global Retrieval

- **Status:** Accepted for the scoped Workstream 5 implementation on
  2026-11-05, by explicit user authorization.
- **Requirements:** Workstream 5 assignment; scoped authorization recorded
  in `REQUIREMENTS.md` and `ACTIVE_TASK.md`.
- **Task:** `tasks/active/workstream-5-regulatory-publication-indexing.md`.

## Context

Approved regulatory requirements are stored in PostgreSQL and exposed by the
existing catalog, while the existing Qdrant evidence index and retrieval
pipeline are tenant-scoped. Publication currently does not synchronize
regulatory content into Qdrant. Simply removing the mandatory tenant filter
would expose other tenants' points and stale regulatory content could remain
retrievable after publication eligibility changes.

R-4D and ADR-0017 otherwise remain planning-only. This decision records only
the user's scoped authorization for Workstream 5; it does not approve the
remaining R-4D proposal, deployment, or a new infrastructure service.

## Decision

1. Reuse the existing PostgreSQL publication state, Qdrant collection,
   embedding provider, deterministic chunking/indexing services, and
   in-process worker. PostgreSQL remains authoritative for whether a
   regulatory requirement is currently retrievable.
2. Keep tenant evidence tenant-scoped. Add an explicit global-regulatory
   content scope to indexed regulatory points and a narrow retrieval union:
   points owned by the requesting tenant plus only currently eligible,
   published global regulatory points. Never query or return other tenants'
   points.
3. Keep publication and index synchronization separate but durable. Record
   index work in PostgreSQL so publication can commit independently of
   Qdrant availability and workers can retry, recover, and reconcile.
4. Revalidate global regulatory point eligibility against PostgreSQL at
   retrieval time. Index metadata and asynchronous cleanup alone are not
   authoritative. Unpublished, rejected, withdrawn, superseded, or otherwise
   ineligible requirements must not be returned even while a stale vector
   point awaits cleanup.
5. Synchronize removals and changed content through the durable index-work
   lifecycle. Reuse the existing index; do not introduce a new queue,
   worker framework, vector store, or RAG redesign.
6. Preserve current API authorization and deterministic applicability logic.
   Publication/indexing does not itself decide that a requirement applies to
   a tenant, nor imply legal certification or official approval.

## Alternatives considered

- **Remove tenant filtering for regulatory requests:** rejected because it
  would permit cross-tenant leakage.
- **Treat published Qdrant payload metadata as the sole eligibility check:**
  rejected because source status and governance flags can change in
  PostgreSQL before asynchronous vector cleanup completes.
- **Index synchronously inside the publication request:** rejected because a
  Qdrant outage must not roll back or make publication state ambiguous, and
  durable retry/recovery is required.
- **Create a separate vector database or worker framework:** rejected as an
  unnecessary architectural expansion.

## Consequences

- The Qdrant payload/retrieval contract and PostgreSQL schema may require
  additive changes; these must preserve existing tenant points and tenant-only
  behavior.
- Publication can succeed while indexing is pending or retrying. The
  persistent index state must make that outcome observable.
- Global retrieval must fail closed if current eligibility cannot be
  established.
- Live Qdrant validation is permitted only against a positively identified
  development/test collection. An unknown or remote endpoint is not a test
  target.
