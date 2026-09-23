# Phase 5.3 — Evidence Scope & Metadata Filtering

**Status:** Complete and verified (2026-09-22)
**Phase:** Phase 5 — Retrieval & RAG
**Type:** Retrieval-scope boundary — explicit metadata filtering only;
no retrieval intelligence

> This record describes what was actually implemented and verified.

## Objective

Let retrieval express *"search only the evidence that belongs to the
permitted retrieval scope"* — semantic similarity alone is insufficient
once evidence comes from multiple sources. The boundary is deliberately
safe and extensible, using only metadata the system already stores.

## Supported scope dimensions (canonical, indexed)

`EvidenceRetrievalScope` supports exactly the four dimensions whose
canonical values already exist in the Phase 4.4 vector payload and the
`EvidenceRetrievalResult`:

| Dimension | Type | Canonical source |
|---|---|---|
| `source_id` | non-empty string | Phase 4.0/4.1 source identity (trimmed) |
| `source_type` | one of `SOURCE_TYPES` | closed set: regulation, guidance, certificate, policy, other |
| `document_id` | UUID | Phase 4.0 `uuid5(tenant, source_id, version)` |
| `document_version` | non-empty string | Phase 4.0/4.2 document version |

Every field is optional; `None` means "no restriction on this
dimension". Supplied values are validated fail-closed
(`DomainValidationError`) and trimmed.

**Intentionally excluded (unsupported/speculative):**

- **tenant** — mandatory execution-level concern, never part of scope (§
  tenant isolation below).
- `jurisdiction`, `title`, `effective_date`, `retrieved_at`, `status`,
  `metadata`, commodity — present on `EvidenceDocument`/the database
  schema but **not in the Phase 4.4 vector payload**, so no reliable
  canonical indexed value exists to filter on. Adding them requires a
  separate indexing change, not a speculative scope field.
- `source_location`, `chunk_index`, `content`, `content_fingerprint`,
  `embedding_model`, `embedding_dimensions` — identity/content/embedding
  metadata, not scope dimensions.
- matching *absent* `document_version` (NULL) — exact non-null equality
  only; no safe first-class expression was defined, so it is not offered.

Unknown dimensions cannot be expressed: the frozen dataclass rejects
extra keyword arguments (`tenant_id`, `jurisdiction`, `commodity`,
`filters`, …) with `TypeError`, so a loosely typed `filters: dict` style
scope is impossible by construction.

## Filter semantics

- **AND (conjunctive)**: a result is in scope only if it satisfies
  *every* supplied filter. `source_id = X` means only evidence belonging
  to source X is returned; supplying `source_id` *and* `source_type`
  requires both.
- **Exact equality** on the canonical field value (after trimming).
- One semantic source for membership: `EvidenceRetrievalScope.accepts(result)`
  is used by both the adapter and the service for re-validation, and
  `items()` yields the active filters as canonical `(payload field,
  value)` pairs in fixed order for provider translation.

## Mandatory tenant isolation (separate from scope)

```text
effective retrieval = mandatory tenant constraint
                    + optional caller-approved metadata constraints
```

- `EvidenceRetrievalScope` has **no tenant field**; tenant identity
  remains a required keyword of every retrieval call and is validated
  (`require_tenant_context`) *before* scope is even examined.
- A caller cannot construct an unrestricted or cross-tenant scope: the
  scope can neither express another tenant nor remove the tenant
  condition.
- The adapter's provider filter always begins with the tenant condition,
  which scope conditions are then appended to (never replacing it).
- Tenant isolation remains enforced when scope is empty, when filters are
  supplied, when a caller attempts to specify another tenant, and when
  provider filtering behaves incorrectly (Phase 5.1 defense-in-depth
  re-checks are preserved unchanged).

## Empty-scope behavior

An omitted or empty scope means **tenant constraint only** — never "all
tenants". The service normalizes `None` to an empty
`EvidenceRetrievalScope`; the adapter then sends a filter containing
exactly one condition (the mandatory tenant condition). This is
explicitly tested at both layers.

## Provider translation

```text
Domain retrieval scope
        ↓ EvidenceRetriever.retrieve(query, *, tenant_id, scope)
        ↓ EvidenceVectorIndex.find(vector, *, tenant_id, top_k, scope)
        ↓ QdrantEvidenceVectorIndex
        ↓ Qdrant filter expression (must = [tenant, …scope conditions])
```

- The adapter builds `must` conditions from the canonical
  `scope.items()` pairs: `source_id` / `source_type` /
  `document_version` as strings, `document_id` encoded as its UUID
  string (the Phase 4.4 payload encoding). Qdrant's `must` list provides
  the AND semantics.
- Provider-specific objects appear **nowhere** in domain models,
  application services, or the domain-semantics tests (verified by tests
  that read the domain module sources). No Qdrant filter object crosses
  the adapter boundary, and `EvidenceVectorIndex.find` still accepts an
  already-embedded vector — never raw text.

## Defense-in-depth validation

Metadata filtering never replaces tenant validation:

1. `require_tenant_context` runs first (service and adapter).
2. The provider call always carries the tenant condition; scope
   conditions are appended.
3. Every translated result is re-checked: tenant identity must match,
   then `scope.accepts(result)` must hold.
4. A provider returning `source_id = B` when `source_id = A` was
   requested is treated as a **retrieval integrity failure** —
   `VectorStoreError` with the operation and cause (never silently
   ignored, never converted to "no results").
5. Malformed metadata fails closed: an out-of-scope/malformed value with
   an active scope raises; malformed persisted payloads are rejected by
   `EvidenceRetrievalResult.from_record` in the adapter and translated to
   `VectorStoreError`.

## Scope and provenance

Filtering is applied to results only as selection; returned evidence
keeps the complete Phase 5.1 provenance — tenant, document, chunk, source
identity, version, content fingerprint, content, and embedding metadata —
as a full `EvidenceRetrievalResult` (13 fields, verified by tests).

## Compatibility

- `scope` is an optional keyword with default `None` on
  `EvidenceRetriever.retrieve` and `EvidenceVectorIndex.find`; existing
  Phase 5.1/5.2 call sites, semantics, ordering, deduplication, and
  failure behavior are unchanged.
- The only edits to earlier-phase tests were mechanical signature
  extensions of test doubles (`find(..., scope=None)`) — **no assertion
  was changed or weakened**.
- `EvidenceRetrievalQuery`, `EvidenceRetrievalConfig`,
  `EvidenceRetrievalResult`, `EvidenceRetriever`, and
  `EvidenceVectorIndex` remain valid and usable exactly as before.

## Testing

`tests/unit/test_evidence_retrieval_scope.py` — **41 focused tests**
(fakes only; no live Qdrant): scope contract/validation (6), empty scope
(3), single filters incl. adapter (4), AND semantics (4),
source-type/version/document filtering (4), tenant isolation with scope
(4), provider translation (4), scope integrity (4), provenance after
filtering (2), no-results vs failure (3), compatibility (3).

Integration: no Qdrant server is configured; consistent with Phases
4.4/4.5/5.1/5.2, no live integration test was added.

## Intentionally deferred / non-goals

LLM query rewriting, reranking, hybrid BM25/vector search, agentic
retrieval, answer generation, compliance reasoning, legal
interpretation, citation generation, conversational retrieval, and
heuristic classification of user queries. New scope dimensions
(jurisdiction, dates, status, commodity) are deferred until a phase
indexes those fields into the payload — they are not speculatively added
here. **Phase 5.4 has not started; Phase 5 is not complete.**

## Verification

- Focused: `pytest tests/unit/test_evidence_retrieval_scope.py -q`
  → **41/41 passed**.
- Phase 5.1 focused re-run → **56/56 passed**.
- Phase 5.2 focused re-run → **40/40 passed**.
- Full unit suite → **605 passed** (564 baseline + 41), 0 failures,
  0 errors; only the 2 pre-existing `starlette`/`anyio` warnings.
- Domain import surface verified (`EvidenceRetrievalScope` exported); no
  secrets written to docs or logs.
- Live Qdrant integration: **not run** — no server configured.