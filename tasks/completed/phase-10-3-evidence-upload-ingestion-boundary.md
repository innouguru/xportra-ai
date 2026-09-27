# Phase 10.3 — Evidence Upload & Ingestion Boundary (Complete, 2026-09-25)

Scope-definition task only. No implementation performed:
no upload code, buckets, migrations, endpoints, frontend
changes, chat upload, retrieval/reasoning changes,
queues, notifications, or deployment work.

## Acceptance criteria

- [x] Complete upload → ingestion → evidence → indexing
  lifecycle mapped to existing services (§1, §5).
- [x] Ownership + tenant-isolation boundaries (§2–§4).
- [x] Storage strategy: one private bucket, server-composed
  keys, signed downloads, no client bucket access (§2).
- [x] Evidence identity: five distinct identities (§4).
- [x] File validation policy + layer placement (§3).
- [x] Ingestion + failure semantics, synchronous MVP (§5, §12).
- [x] Workflow/terminal behavior: 409 before any write,
  no reopen (§7).
- [x] Future API contract incl. forbidden operations (§10).
- [x] Conceptual persistence changes, no migration (§11).
- [x] RAG boundary: raw never reaches LLM (§6).
- [x] Frontend status contract: processing × review axes (§8).
- [x] Security/test matrix (§3, §14).
- [x] Unresolved decisions as OQ-U1–OQ-U7 (§13).
- [x] Implementation scope for the next phase (§15).

## Artifacts

- `docs/phases/phase-10-3-evidence-upload-ingestion-boundary.md`
- `docs/decisions/ADR-0011-evidence-upload-ingestion-boundary.md`
- This record. No `REQUIREMENTS.md` change (no approved
  requirements; OQ-U1–OQ-U7 await product decisions — no
  implementation task may be scheduled for them).

## Resolution addendum (2026-09-27)

OQ-U1–OQ-U7 are RESOLVED by approved product decisions
recorded in `REQUIREMENTS.md` R-10.4 and reflected in
the phase doc (§2, §4, §8, §13) and ADR-0011
(addendum): U1 = PDF/DOCX/JPEG/PNG with
content-type + magic-byte validation; U2 = 10 MB per
file, server-enforced, rejected before storage;
U3 = no delete endpoint, mark inactive/superseded
(`archived`), excluded from new analysis, no
retention period invented; U4 = private Storage,
server-authorized short-lived signed URLs, tenant +
ownership verified; U5 = identifiers/status metadata
only, existing audit structures; U6 = server-generated
deterministic identities, Phase 4/5 authoritative;
U7 = `uploaded → processing → ready | failed`,
separate from compliance state. Phase 10.4
implementation is unblocked.
