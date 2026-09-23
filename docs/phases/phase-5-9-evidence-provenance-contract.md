# Phase 5.9 — Evidence Provenance Chain Audit & Contract

**Status:** Complete and verified (2026-09-23)
**Phase:** Phase 5 — Retrieval & RAG
**Type:** Provenance contract and integrity audit — no new retrieval,
ranking, or selection behavior; no API, no prompt generation, no LLM

> This record describes what was actually audited and verified.
> **No production code was modified in this phase.** The audit found
> the existing provenance architecture coherent; the deliverables are
> the formalized contract (this document) plus a focused invariant
> test suite.

## Objective

Audit and formalize the end-to-end evidence provenance chain:

```text
Source / Document (Phase 4.0)
      ↓
Document Version
      ↓
Evidence Chunk (Phase 4.2)
      ↓
Vector / Lexical Retrieval (Phase 5.1–5.4)
      ↓
Hybrid Candidate
      ↓
Ranked Evidence (Phase 5.5)
      ↓
Selected Evidence (Phase 5.7)
      ↓
Evidence Context (via Phase 5.6/5.8 pipelines)
```

and guarantee that every evidence item reaching
`EvidenceContextSelection` remains traceable to its authoritative
source and original retrieval/ranking identity.

## Canonical provenance identity (derived, not assigned)

The system already has one authoritative, deterministic identity
mechanism — **no second identity system was introduced**:

- **Document identity**: `stable_document_id(tenant_id, source_id,
  version)` — uuid5 over
  `xportra:evidence-document:<tenant>:<source_id>:<version>`.
  Enforced at construction: `EvidenceDocument.__post_init__` rejects
  any `document_id` not equal to the derived value (Phase 4.0).
- **Chunk identity**: `stable_chunk_id(tenant_id, document_id,
  chunk_index, fingerprint)` — uuid5 over
  `xportra:evidence-chunk:<tenant>:<document>:<index>:<fingerprint>`.
  Deterministic, so re-chunking the same document reproduces the same
  chunk ids (Phase 4.2).
- **Content fingerprint**: `content_fingerprint(content)` — sha256
  hex of stripped content (Phase 4.0); the single fingerprint
  mechanism, reused everywhere.
- **Tenant**: `tenant_id` is a UUID mandatory at every boundary
  (`require_tenant_context` convention); it is baked into both
  derived identities, so a chunk id literally cannot belong to two
  tenants.

Because identity is *derived* from `(tenant, source, version)` and
`(tenant, document, index, fingerprint)`, identity drift is
unconstructible at the boundaries that own it.

## The authoritative provenance carrier — no new object

**`EvidenceRetrievalResult` (Phase 5.1) already functions as the
authoritative provenance carrier**: frozen, 13 fail-closed-validated
fields (`tenant_id`, `chunk_id`, `document_id`, `chunk_index`,
`content`, `content_fingerprint`, `source_id`, `source_type`,
`source_location`, `document_version`, `embedding_model`,
`embedding_dimensions`, `score`), with a fail-closed `from_record`
and a complete `to_record`. Per the phase rule — *do not introduce
`EvidenceProvenance` if the existing result already carries the
provenance* — **no new provenance value object was created.**
Duplicating those fields into a parallel object would create a second
representation and a second place to drift.

## Provenance preservation at every transition

Every Phase 5 transition **wraps by reference** — no copying, no
reconstruction anywhere in the chain (all `assertIs`-verified in
tests):

| Transition | Mechanism | What is added |
|---|---|---|
| `EvidenceRetrievalResult` → `HybridRetrievalCandidate` | reference (`candidate.evidence`) | `semantic_score`, `lexical_score`, `retrieval_sources` |
| `HybridRetrievalCandidate` → `RankedEvidenceResult` | reference (`ranked.evidence`) | `rank_position`, `ranking_key` (+ scores/sources re-exposed) |
| `RankedEvidenceResult` → `SelectedEvidence` | reference (`selected.ranked`) | `character_count` |
| `SelectedEvidence` → `EvidenceContextSelection` | tuple membership | `used_budget`, `skipped_rank_positions`, `budget` |

A single `EvidenceRetrievalResult` object survives the entire chain:
`selected.ranked.evidence is candidate.evidence is original_result`
(test-proven). All chain objects are frozen, so provenance cannot be
mutated in place.

## Validation ownership by layer

Each invariant has exactly one owning layer — validation is **not**
duplicated at every boundary:

```text
Phase 4.0 corpus      → document identity derivation (uuid5 check),
                        fingerprint algorithm, source_type vocabulary
Phase 4.2 chunking    → content ↔ fingerprint invariant
                        (EvidenceChunk rejects new content + old fingerprint),
                        chunk id derivation
Phase 5.1 retrieval   → provider payload integrity (from_record fail-closed:
                        types, UUIDs, source_type, embedding contract, score)
Phase 5.2/5.3         → duplicate-key identity (document + fingerprint),
                        scope/tenant filtering integrity
Phase 5.4 hybrid      → candidate source ↔ score consistency
                        (semantic/lexical provenance cannot be fabricated),
                        evidence-reference type integrity
Phase 5.5 ranking     → candidate list integrity, duplicate chunk identity,
                        ranking-order determinism
Phase 5.7 selection   → ranked-evidence integrity at the context boundary:
                        tenant re-validation per item, non-empty content,
                        duplicate chunk identity, ascending rank order
Phase 5.6/5.8 pipelines → composition integrity only (structural
                        defense-in-depth on collaborator output)
```

This is the discovered architecture, documented as-is; no layer was
forced to re-validate fields it does not own.

## Source traceability semantics

Every selected evidence item carries the complete source triple:

- `source_id` — the canonical identifier of the authoritative source
  the document was acquired from (e.g., `sonsa/cert-guide`);
- `source_type` — the controlled vocabulary from Phase 4.0
  (`regulation`, `guidance`, `certificate`, `policy`, `other`);
- `source_location` — the optional acquisition location of the
  document (a URI or reference recorded at ingestion).

Together with `document_id`, `document_version`, `chunk_id`, and
`content_fingerprint`, these fields let a future user-facing system
identify *where the evidence came from*. **What they do NOT
guarantee**: they are provenance pointers, not legal citations — no
field asserts legal authority, current validity, or that the source
is sufficient to prove a compliance requirement. `source_location`
is optional and may be `None`; its absence is preserved as
faithfully as its presence. No URLs are invented anywhere in the
chain.

## Content fingerprint invariant

Owned by Phase 4.2 (`EvidenceChunk.__post_init__`):
`content_fingerprint == sha256(content)`, enforced at construction —
`new content + old fingerprint` is unconstructible at the owning
boundary. Downstream, the fingerprint is carried by reference on the
frozen carrier and never recomputed or altered; Phase 5 boundaries
verify it is *preserved* (equality through the chain, test-proven)
but deliberately do not re-derive it from content at every layer —
re-deriving at retrieval would require treating the Phase 4.4 index
payload as untrusted at the wrong boundary and would duplicate the
Phase 4.2 check. The Phase 5.2 duplicate rule
(`evidence_duplicate_key = (document_id, fingerprint)`) keys
exact-duplicate collapse on this fingerprint: different documents,
versions, or sources never collide. No fingerprint algorithm was
changed; no second hashing scheme was introduced.

## Version semantics

`document_version` is embedded in the derived document identity, so
two versions of the same source are two distinct documents with two
distinct chunk-id namespaces — identical content under different
versions is **never collapsed** (test-proven end to end). Phase 5.3
exposes `document_version` as an explicit scope dimension. No
version ordering or "latest version" semantics exist; distinct
versions are preserved intentionally.

## Tenant invariant

`tenant_id` is preserved unchanged from retrieval through final
selected evidence (assertIs-level object and field equality,
test-proven). It is mandatory at every boundary — never optional,
never defaulted — and is embedded in both derived identities.
Cross-tenant provenance fails closed at the context-selection
boundary (Phase 5.7 re-validates each item) and at every earlier
tenant-checked boundary. No second tenant-authorization mechanism
was introduced.

## Ranking identity

`rank_position` (1-based, explicit) and `ranking_key` (the
structured sort key) are assigned once by Phase 5.5 and re-exposed —
not recomputed — by `SelectedEvidence`. Rank positions remain
strictly ascending in selection input order (violations rejected by
Phase 5.7), so a rank position continues to refer to the same
evidence item through selection.

## Integrity tests (silent-corruption detection)

`tests/unit/test_evidence_provenance.py` attempts the invalid
transformations and confirms fail-closed behavior at the owning
layer: cross-tenant evidence (Phase 5.7), duplicate chunk identity
(Phase 5.5 ranker and Phase 5.7 selector), fabricated
semantic/lexical provenance (Phase 5.4 candidate), malformed
candidate lists (Phase 5.5 defense-in-depth), emptied content
(Phase 5.7), rank-order violations (Phase 5.7), and malformed
provider payloads — bad tenant UUID, unknown `source_type`, zero
embedding dimensions (Phase 5.1 `from_record`). Frozen-value tests
confirm provenance cannot be mutated in place at any transition.

## End-to-end traceability test

The suite drives a real `EvidenceDocument` through the real Phase 4.2
chunking service, converts the chunk records into Phase 5.1 results
(faithful index-payload shape), and runs the real Phase 5.6
`EvidenceRetrievalPipeline` and Phase 5.8 `EvidenceContextPipeline`
(fakes only at the infrastructure edge). Each selected item is traced
back to the exact original chunk: tenant, document_id, version,
chunk_id, chunk_index, source_id/type, content, and fingerprint —
plus consistent rank position and ranking key. A second test proves
two document versions with identical content stay distinct through
the full pipeline; a third verifies the final `to_record()` exposes
the complete source triple for a future citation boundary.

## Discovered gaps

None requiring code changes. One ownership note (documented above):
the content ↔ fingerprint invariant is enforced at Phase 4.2
construction and *preserved-by-reference* downstream rather than
re-derived at every layer — this is deliberate layer ownership, not
a defect. `source_location` optionality is contractual (Phase 4.0),
not a gap.

## Deferred provenance work

- A user-facing citation boundary (translating the source triple into
  human-readable citations) — a later phase; this phase only
  guarantees the inputs survive.
- Provenance of the *query* itself (who asked, when) — retrieval-log
  territory, outside the evidence chain.
- Any API exposure or prompt construction — explicitly out of scope.

## Implementation

- `tests/unit/test_evidence_provenance.py` (new): 31 focused tests.
- **No production file was modified.** No new public symbols; no
  import check required beyond the existing suite passing.

## Verification

- Focused Phase 5.9: **31/31** (fakes only — no live Qdrant, no
  embeddings, no LLM, no network).
- Phase 5.1–5.8 focused re-runs and complete tree: see
  `CURRENT_STATE.md`.
- No Phase 4/5 behavior changed; no prior test weakened.

Phase 5 is not marked complete by this phase alone; no Phase 5.10
exists in the phase plan.
