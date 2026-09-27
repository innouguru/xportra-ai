# ADR-0011: Evidence upload & ingestion boundary

- Status: Accepted (scope definition only — no implementation)
- Date: 2026-09-25
- Addendum: 2026-09-27 — open questions OQ-U1–OQ-U7
  resolved by approved product decisions
  (`REQUIREMENTS.md` R-10.4); the boundary below is
  unchanged and now implementable as Phase 10.4.
- Scope: Future tenant evidence upload; constrains the
  implementation phase that follows
  (`docs/phases/phase-10-3-evidence-upload-ingestion-boundary.md`)

## Context

Evidence intake today is reference-only: `ComplianceEvidenceService`
records title/type/URI plus an optional requirement link
(`compliance_evidence` / `evidence_requirements`), the workflow
recognizes supplied references (Phase 7.2), and the UI spec
(§11.1) confirms no file-upload endpoint exists. The technology
baseline (TB-3) names Supabase Storage Free, but no code uses
object storage. A production upload path must feed the existing
evidence/RAG architecture — never duplicate it.

## Decision

1. **Server-mediated upload only.** Clients never receive bucket
   credentials and never address objects directly. Object keys
   are composed server-side as
   `tenant/{tenant_id}/evidence/{evidence_id}/{content_hash}{ext}`;
   client-supplied paths, keys, and filenames never reach
   storage. Downloads are short-lived server-issued signed
   URLs after an authorization check, never public URLs.
2. **Five distinct identities, never collapsed.**
   `storage object key` ≠ `evidence record id`
   (`compliance_evidence.id`, the compliance anchor) ≠
   `content hash` (sha256, dedup/idempotency) ≠
   `corpus document id` (Phase 4.0 stable identity, only if
   indexed) ≠ `requirement association`
   (`evidence_requirements` row). Convenience joins must not
   merge them.
3. **Upload implies nothing.** A stored file is not parsed,
   sufficient, linked, or assessed by the act of uploading.
   Satisfaction still requires the Phase 2.6 rule (explicit
   link + accepted/reviewed supporting status); applicability
   is untouched by upload; missing stays missing until valid
   evidence is available and assessed.
4. **Synchronous MVP, no queues.** Phase 4.5 already forbids
   background workers for index synchronization; the upload
   implementation stays synchronous (request → validate →
   store → register → parse → ingest → sync, fail-closed at
   each step). Asynchronous processing is deferred until a
   requirement justifies it.
5. **Terminal workflows are immutable.** Uploads bound to a
   finalized workflow are rejected (`terminal_workflow`);
   unbound uploads remain allowed. No reopen/versioning
   mechanism is created (Phase 7.5 holds).
6. **Raw files never reach the LLM.** Only parsed chunks
   passing through the existing chunk → sync → tenant-scoped
   retrieval chain may ground answers. Raw bytes appear in
   no prompt, log, error message, or API response.
7. **Processing state is separate from review state.** The
   existing `compliance_evidence.status`
   (uploaded/reviewed/accepted/rejected/archived) describes
   human review, not pipeline progress; lifecycle tracking
   (`uploaded → processing → ready | failed`, resolved U7)
   belongs in a new field or table defined conceptually
   in the phase doc — no migration is written by this
   task. `ready` means ingestion/indexing passed, never
   compliance.

## Resolved product decisions (addendum 2026-09-27)

- **U1 — MVP file types:** PDF, DOCX, JPG/JPEG, PNG,
  validated by declared content type AND magic-byte/
  content inspection. No additional formats without an
  explicit product decision.
- **U2 — Maximum file size:** 10 MB per file, rejected
  before storage, enforced server-side.
- **U3 — Deletion/retention:** no physical delete, no
  MVP delete endpoint; incorrect/superseded documents
  are marked inactive/superseded (existing `archived`
  review status), excluded from new analysis,
  provenance intact. No retention period invented.
- **U4 — Download/access:** private Supabase Storage,
  server-authorized, short-lived signed URLs where
  appropriate; tenant + ownership verified first.
  Never public buckets/URLs or client-controlled keys.
- **U5 — Audit:** identifiers and status metadata only
  (uploader, tenant, workflow/shipment, upload
  identity, processing/association/superseded status,
  supported timestamps). Never contents, text,
  secrets, signed URLs, or file bytes. Existing
  history/audit structures carry the references.
- **U6 — Corpus/source identity:** server-generated,
  deterministic where fitting; Phase 4/5 contracts
  authoritative. The client never chooses identities.
- **U7 — Processing state:** dedicated lifecycle
  `uploaded → processing → ready | failed`, separate
  from availability/applicability/assessment.

## Alternatives considered

1. **Direct client-to-bucket upload (signed POST).** Rejected:
   surrenders server-side file validation ordering (bytes
   land before policy runs) and invites key-guessing and
   quota abuse; the synchronous MVP keeps bytes flowing
   through the API boundary instead.
2. **Storing parsed content back into `compliance_evidence`.**
   Rejected: collapses the uploaded-file / parsed-document /
   indexed-evidence distinction and duplicates the Phase 4.0
   corpus; parsed/indexed forms live in the existing corpus
   and index, referenced by identity.
3. **New async worker for ingestion.** Rejected: contradicts
   the Phase 4.5 no-queue precedent with no approved
   requirement; retry is idempotent re-invocation of the
   existing sync boundary.

## Consequences

- The implementation phase needs: a storage adapter behind a
  domain protocol, a file-validation boundary, an upload
  orchestration use case, one upload endpoint plus one
  authorized download endpoint, a conceptual (not yet
  written) persistence extension for processing state, and
  the security/test matrix in the phase doc.
- Open questions OQ-U1–OQ-U7 (phase doc §13) were
  resolved by requirements decisions (R-10.4,
  2026-09-27) before implementation; none were
  silently invented.
- No code, schema, bucket, endpoint, or contract changed by
  this ADR.
