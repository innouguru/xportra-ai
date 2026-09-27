# Phase 10.3 — Evidence Upload & Ingestion Boundary

> Scope definition only (2026-09-25). No code written, no
> bucket created, no migration written, no endpoint built,
> no behavior exists. Binding decisions:
> `docs/decisions/ADR-0011-evidence-upload-ingestion-boundary.md`.
> Every capability below maps to an already-implemented
> service, table, or contract; anything not yet built is
> marked NEW. Nothing here overrides Phases 1–10.2.
>
> Update 2026-09-27: open questions OQ-U1–OQ-U7 are
> RESOLVED by approved product decisions (see §13 and
> `REQUIREMENTS.md` R-10.4). No new open questions remain
> for them. Phase 10.4 implements this boundary.

## 0. Governing distinction

```text
uploaded file
  ≠ parsed document
  ≠ indexed evidence
  ≠ sufficient evidence
  ≠ compliant requirement
```

Uploading a document NEVER directly implies requirement
satisfied, shipment compliant, evidence sufficient, or
assessment passed. Satisfaction still requires the Phase
2.6 rule (explicit requirement link + accepted/reviewed
supporting status, evaluated by assessment); applicability
is untouched by upload; missing evidence remains missing
until valid evidence is available and assessed.

## 1. Authoritative lifecycle

```text
Upload request (multipart, member-authorized)
  ↓ ① authenticate actor (existing get_member_context)
  ↓ ② resolve tenant (membership only; never body)
  ↓ ③ optional workflow association check (7.2 handoff rules)
  ↓ ④ file validation (type/size/magic-bytes/filename)
  ↓ ⑤ secure object storage put (server-composed key)
  ↓ ⑥ document registration (compliance_evidence row,
  │     status 'uploaded', file_reference_or_uri = key,
  │     content_hash = sha256)
  ↓ ⑦ parsing (existing parsers; NEW types only as approved)
  ↓ ⑧ normalization (loss-minimizing, existing convention)
  ↓ ⑨ evidence identity (the record id; no new scheme)
  ↓ ⑩ requirement association (existing link, user-chosen)
  ↓ ⑪ evidence index synchronization (4.1 → 4.2 → 4.5)
  ↓ ⑫ evidence sufficiency (existing assessment, on re-analysis)
  ↓ ⑬ analysis / re-analysis (existing endpoint, owner-only)
  ↓ user-visible status (processing state + review state, §8)
```

Exists today: ①, ②, ⑥ (reference form), ⑨, ⑩, ⑫, ⑬, and
the ⑦–⑧–⑪ chain for already-available records.
Missing (NEW): ④ as a file boundary, ⑤ (no object-storage
code exists despite TB-3 naming Supabase Storage Free),
and the orchestration use case binding ③→⑪ in one
fail-closed sequence.

## 2. Storage architecture (NEW, Supabase Storage)

- **Bucket strategy:** one private bucket (e.g.
  `tenant-evidence`). No per-tenant buckets (policy
  sprawl), no public buckets (ever).
- **Key strategy:** server-composed only —
  `tenant/{tenant_id}/evidence/{evidence_id}/{content_hash}{ext}`.
  Tenant prefix gives structural isolation and makes
  arbitrary key access unexpressible; content-hash
  segment gives dedup alignment. Client-supplied paths,
  keys, and filenames never reach storage (filename is
  stored as metadata `original_filename` only, for
  display).
- **Ownership:** the `compliance_evidence` row
  (tenant FK, RESTRICT) owns the object; the object
  never owns the record. Orphan puts (storage write
  without registration) are impossible by ordering:
  validate → put → register in one use-case call, and
  registration failure after a put deletes the put
  object (compensating delete, the only storage
  mutation besides put).
- **Allowed types (MVP, resolved U1):** PDF, DOCX,
  JPG/JPEG, PNG. Validation uses declared content type
  AND authoritative magic-byte/content inspection; the
  client MIME type alone is never trusted. No additional
  formats without an explicit product decision.
- **Size limit (resolved U2):** 10 MB per file, rejected
  before storage, enforced server-side (frontend
  validation alone is insufficient).
- **Duplicates:** same tenant + same content hash →
  idempotent return of the existing evidence record
  (no second object, no second row), mirroring the
  4.1 identical-duplicate rule. Same name + different
  bytes → distinct evidence records (filenames are
  display metadata, never identity).
- **Deletion (resolved U3):** no MVP delete
  endpoint; users cannot physically delete uploaded
  evidence. Evidence remains available for
  provenance/audit. An incorrect or superseded document
  is marked inactive/superseded (existing `archived`
  review status) rather than physically destroyed;
  inactive/superseded evidence must not silently
  participate in new analysis while its historical
  identity/provenance stays intact. No permanent
  retention period is invented; permanent physical
  deletion and formal retention policy remain future
  policy decisions.
- **Access/download (resolved U4):** private Supabase
  Storage only, server-authorized access, short-lived
  signed URLs where appropriate. Never public buckets,
  public object URLs, client-controlled storage keys,
  or unrestricted download URLs. Download
  authorization verifies the requesting actor's tenant
  and evidence ownership/association before issuing
  access.
- **LLM exposure:** raw files NEVER enter prompts,
  context, logs, or responses. Only parsed chunks via
  the existing index → tenant-scoped retrieval chain
  (§7).
- **Retention/audit (resolved U5):** the evidence
  lifecycle is recorded using identifiers and status
  metadata — uploader/actor, owning tenant,
  workflow/shipment association, upload identity,
  processing status, association status,
  superseded/inactive status, and timestamps where the
  persistence conventions support them. Never logged:
  raw document contents, document text, secrets,
  signed URLs, or arbitrary file bytes. No second
  unrelated audit system: the existing
  evidence/workflow/history structures carry the
  required references.

## 3. Security — check placement

Phase 10.1 guarantees hold; no second authorization
system. Placement:

| Check | Layer |
|---|---|
| Bearer/dev-header auth, membership, role (`require_permission`) | HTTP (existing) |
| Tenant from membership; `extra="forbid"` on tenant/path fields | HTTP schemas (existing) |
| Size cap, content-type allow-list, multipart shape | HTTP (NEW) |
| Magic-byte verification, filename sanitization (traversal, null bytes, control chars), extension↔MIME consistency | Domain file-validation boundary (NEW) |
| Malformed-document rejection | Domain parsers (existing convention) |
| Tenant-match on workflow/record/link before any write | Application (existing `ensure_tenant_match`) |
| Key composition, no client paths, signed-URL issuance | Storage adapter (NEW, behind a domain protocol) |
| Terminal-workflow rejection before storage write | Application (existing `is_closed` pre-check) |
| No content/bytes/keys in logs or error messages; 5xx sanitization | Existing 10.1 handlers (unchanged) |

Threat coverage: cross-tenant upload/download/association
(tenant prefix + row FK + re-checks), arbitrary key
access (server-composed keys only), path traversal
(sanitization + keys never contain client text),
spoofed MIME (magic bytes authoritative, header
  advisory), dangerous types (allow-list, resolved U1),
  oversize (10 MB cap per resolved U2, enforced pre-read),
malformed docs (parser fail-closed), unauthorized
workflow association (7.2 tenant/case re-checks),
client tenant control (forbidden fields), URL
exposure (signed, short-lived, authz-gated), log
leakage (identifiers-only logging rule extended to
filenames/hashes).

## 4. Evidence identity (five identities, §ADR-0011)

1. `storage object key` — where bytes live.
2. `compliance_evidence.id` — the compliance anchor;
   the ONLY identity the workflow, links, and
   assessments reference.
3. `content_hash` (sha256) — dedup/idempotency key,
   already a nullable column; becomes mandatory for
   uploaded rows.
4. `corpus document id` — Phase 4.0 stable identity,
   created only when the document is indexed (§7);
   resolved U6: server-generated deterministic
   identities — the tenant-upload `source_id`/version
   scheme is tenant+evidence-derived, never colliding
   with regulatory sources; the client never chooses
   source, evidence, storage-key, or tenant identity.
   The Phase 4/5 corpus and indexing contracts remain
   authoritative.
5. `evidence_requirements` row — the association
   (tenant, evidence, requirement unique).

## 5. Ingestion mapping (all synchronous — ADR-0011 §4)

- Parse: existing `ArtifactParsingService` for MVP
  types; NEW format adapters only per resolved U1.
- Normalize: existing loss-minimizing convention
  (strip, never rewrite; fingerprint reflects source).
- Extract/chunk: existing `EvidenceChunkingService`
  (deterministic, in-memory).
- Sync: existing `EvidenceIndexSyncService`
  (idempotent upsert, no rollback, no queues).
- **Associate-before-index?** Allowed: association
  (⑩) is a compliance link, independent of index
  state; sufficiency/assessment only changes on
  re-analysis, which reads stored state — never
  partial index content. An unindexed document
  therefore cannot silently satisfy anything.
- **Failure/partial:** each step fail-closed; no
  success report for partial work (4.5 rule); retry
  is idempotent re-invocation (same content hash →
  same identities); processing state records the
  failure step for the UI (§8).

## 6. RAG boundary

```text
Raw uploaded file (storage, never retrieved)
  ↓ parse/normalize (domain)
Parsed evidence document (corpus, tenant-scoped)
  ↓ chunk (4.2, deterministic)
Evidence chunks (in-memory)
  ↓ sync (4.5, tenant-checked upsert)
Evidence index (Qdrant, tenant payload condition)
  ↓ Phase 5 retrieval (mandatory tenant + scope dims)
  ↓ Phase 6 reasoning (stored analyses, narrated)
Grounded answer
```

No raw-file bypass exists: `EvidenceVectorIndex.find`
accepts embedded vectors, never text; scope gains no
upload-specific dimension; tenant condition is
mandatory with or without scope (Phase 5.3 holds
unchanged). No Phase 5/6 modification.

## 7. Workflow behavior

- Before applicability / while evidence pending:
  upload → record → supply (7.2 handoff) → analysis;
  the established additional-evidence loop.
- After analysis / when additional evidence
  requested: upload → record → supply →
  `reanalysis_required` → explicit re-run
  (owner-only); staleness rules unchanged.
- After finalization: binding a terminal workflow
  to upload/supply/analysis fails closed with
  `terminal_workflow` (existing 7.5 behavior); the
  check runs BEFORE any storage write so no orphan
  objects or records are created. Continuation is a
  fresh progression (7.5), never mutation. No
  reopen/versioning mechanism is created.
- Uploads with no workflow binding are always
  allowed (record now, supply later).

## 8. User-visible status contract (future frontend)

Two orthogonal axes — never merged:

- **Processing (resolved U7, dedicated lifecycle):**
  `uploaded → processing → ready | failed`.
  This lifecycle is separate from evidence availability,
  requirement applicability, and assessment state, and
  never implies compliance: `ready` means the document
  passed the ingestion/indexing pipeline required for
  use — not that a requirement is satisfied.
- **Review** (existing `compliance_evidence.status`):
  `uploaded / reviewed / accepted / rejected / archived`.

The UI must be able to answer: what was uploaded
(title + original filename + type + time), accepted?
(validation outcome), processing complete? (axis 1),
usable as evidence? (`ready` + linked), linked to
which requirements? (association rows), re-run
needed? (readiness/staleness from existing
endpoints). Status names above are proposed; the
implementation phase adopts them unless existing
architecture suggests better.

## 9. Chat relationship (no conversational upload)

Chat never uploads, records, links, or triggers
ingestion (Phase 10.2 read-only boundary holds).
Future Ask Xportra explains upload state using
existing intents (`explain_evidence_gaps`,
`explain_finding`, `summarize_shipment_state`) over
the evidence record + readiness + history; a future
proposal card may deep-link to the upload UI as a
Later item. Chat bypass of the upload/evidence
boundary is forbidden by construction (no mutating
capability exists in `ConversationApplicationService`).

## 10. Future API surface (minimal, per 8.2 conventions)

```text
POST /compliance-evidence/uploads          (multipart; NEW)
GET  /compliance-evidence/{id}             (exists; carries status)
GET  /compliance-evidence/{id}/download    (signed URL; NEW)
```

Thin handlers (auth → authorize → ApplicationContext
→ one use case → DTO), existing error shape. Upload
permission follows recording (member-allowed);
download requires owning-tenant membership; analysis
stays owner-only. Must NOT exist: client-addressed
object download, bulk export, public/permanent URLs,
delete-in-MVP (OQ-U3), raw-content responses,
workflow-scoped listing (no workflow store exists —
listing stays client-side per UI spec §11.2).

## 11. Persistence (conceptual — no migration this task)

- `compliance_evidence`: make `content_hash`
  mandatory for uploaded rows (CHECK, not
  backfill-breaking); `file_reference_or_uri`
  carries the server-composed object key.
- NEW processing tracking: either a
  `processing_status` (+ `processing_step`,
  `processed_at`) column set on
  `compliance_evidence`, or a
  `evidence_processing_state` table keyed 1–1 to
  the evidence id with tenant FK + composite
  tenant-safe FK (CASCADE). Table preferred if
  retry history is wanted (OQ-U7).
- Indexing adds no tables (4.2 chunks in-memory;
  4.4 vectors in Qdrant). Corpus rows for indexed
  uploads reuse migration 009 per OQ-U6.
- Uniqueness/idempotency: partial unique index on
  `(tenant_id, content_hash)` for uploaded rows.

## 12. Failure semantics (deterministic)

Invalid file / spoofed MIME / unsupported type →
400/422, nothing stored. Oversize → 413-class
rejection pre-read (exact code per framework
convention at implementation). Storage failure →
503, no record. Parse/normalize failure → record
stays, processing=`failed(step)`, retryable.
Index failure → `VectorStoreError` propagates
(never a false `ready`). Association failure →
record stays, link absent. Duplicate → idempotent
existing record. Terminal workflow → 409
`terminal_workflow` before any write.
Cross-tenant → 403/404 per existing semantics
(lookups 404-non-leaking, comparisons 403).
No failure path leaves `ready` unindexed, links
unassessed, or findings altered.

## 13. Open questions — RESOLVED (2026-09-27)

OQ-U1–OQ-U7 are resolved by approved product decisions
(`REQUIREMENTS.md` R-10.4). No new open questions are
created for them.

- U1 (MVP file types): PDF, DOCX, JPG/JPEG, PNG.
  Declared content type AND magic-byte/content
  inspection; client MIME never trusted alone. No
  additional formats without an explicit decision.
- U2 (maximum file size): 10 MB per file, rejected
  before storage, enforced server-side.
- U3 (deletion/retention): no physical delete, no MVP
  delete endpoint; evidence stays for provenance/audit;
  incorrect/superseded documents are marked
  inactive/superseded (existing `archived` review
  status), excluded from new analysis, provenance
  intact. No permanent retention period invented;
  physical deletion and retention policy stay future.
- U4 (download/access): private Supabase Storage,
  server-authorized access, short-lived signed URLs
  where appropriate. No public buckets/URLs,
  client-controlled keys, or unrestricted downloads.
  Tenant + ownership/association verified first.
- U5 (audit): lifecycle recorded via identifiers and
  status metadata (uploader, tenant, workflow/shipment,
  upload identity, processing/association/superseded
  status, timestamps where supported). Never: raw
  contents, text, secrets, signed URLs, file bytes. No
  second audit system; existing history/audit
  structures carry the references.
- U6 (corpus/source identity): server-generated,
  deterministic where fitting; client never chooses
  source/evidence/storage-key/tenant identity. Phase
  4/5 corpus and indexing contracts authoritative.
- U7 (processing state): dedicated lifecycle
  `uploaded → processing → ready | failed`, separate
  from availability/applicability/assessment. `ready`
  means ingestion/indexing passed — never compliance.

## 14. Testing strategy (for implementation)

- Security: cross-tenant upload/download/associate;
  key-guessing; traversal filenames; terminal
  rejection; member/owner matrix; URL unguessability
  + expiry.
- File validation: allow-list, spoofed MIME vs
  magic bytes, oversize, malformed/empty, unicode
  filenames, null bytes.
- Lifecycle: upload→store→register→ready; failure
  at each step; retry idempotency; duplicate
  coalescing; index-sync failure never `ready`.
- Compliance semantics: upload changes no
  applicability/assessment/finding; missing stays
  missing; terminal immutable; association ≠
  satisfaction (needs accepted link + assessment).
- RAG: tenant-scoped indexing; retrieval only
  indexed chunks; raw-file bypass attempts fail.

## 15. Implementation scope (next phase, not this task)

NEW: storage adapter (Supabase Storage, domain
protocol + infra impl), file-validation boundary,
upload orchestration use case (+ DTOs), `POST
uploads` + `GET download` endpoints + schemas,
processing-state persistence (migration), focused
+ regression tests. REUSED unchanged: auth,
tenant, `ComplianceEvidenceService`,
`evidence_requirements`, parsers, chunking, sync,
retrieval, reasoning, workflow/readiness/history,
error mapping, 10.1 hardening. Free-stack only:
no paid storage/queues/parsers/providers.
