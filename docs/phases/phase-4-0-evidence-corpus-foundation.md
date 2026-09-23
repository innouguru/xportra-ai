# Phase 4.0 — Evidence Corpus Foundation

**Status:** Complete and verified (2026-09-22)
**Phase:** Phase 4 — Retrieval
**Type:** Persistent corpus foundation — no search/retrieval

> This record describes what was actually implemented and verified.

## Objective

Establish the persistent evidence corpus future retrieval searches:
Sources → Corpus → future retrieval → Executor → Result. No semantic,
vector, keyword, reranking, RAG, or LLM work.

## Model

`EvidenceDocument` in `xportra/domain/evidence_corpus.py`: `tenant_id,
document_id, title, content, source_type, source_id, source_location,
jurisdiction, document_version, effective_date, retrieved_at, status,
metadata`. No chunk entity yet (deferred; representation supports
adding chunks later without changing documents).

## Provenance, types, status

Provenance required (`source_id`, `source_type`, `source_location`,
`document_id`); no anonymous records. Types: `regulation, guidance,
certificate, policy, other` (unknown rejected). Status: `active,
inactive` only — active means retrievable, never compliant/satisfied.

## Identity and dedup

Stable `uuid5(NAMESPACE_URL, "xportra:evidence-document:<tenant_hex>:
<source_id>:<version>")`; `content_fingerprint` = sha256 of stripped
content. Same tenant+source+version → same document; duplicates
rejected (`DomainValidationError` pre-check + unique DB constraint);
different versions are distinct documents.

## Persistence and repository

Migration `009_evidence_documents(.down).sql`: table
`xportra.evidence_documents` with tenant FK, checks, unique
(tenant, source, version), indexes, updated_at trigger.
`EvidenceDocumentRepository` (`create`, `get_by_id`,
`get_by_source_identity`, `list_for_tenant`), all tenant-scoped.
`EvidenceCorpusService` validates, enforces dedup, maps integrity
errors to `DomainPersistenceError`. Executor untouched (future
implementation will depend on the repository).

## Security / non-goals / tests / verification

Fail-closed on bad tenant, cross-tenant, missing identity, bad type,
empty content, malformed rows, duplicates. No vectors, embeddings,
Qdrant, BM25, ranking, query rewriting, web, crawling, LLM, RAG,
agents, APIs. Tests `tests/unit/test_evidence_corpus.py` — 26 tests.
Focused 26/26; full suite 313/313 (287 baseline + 26). DB integration
not run (`DATABASE_URL` unconfigured); repository SQL follows the
existing psycopg conventions and migration 009 applies the schema.
