# Technology Baseline & Ingestion Boundary — Xportra AI

> Approved initial technology baseline for Xportra AI.
> This is an implementation baseline, not an irreversible architectural lock-in.
> No application functionality is implemented by this document.

## Approved technology baseline

### Core

- Python 3.13.x
- FastAPI

### Database and storage

- PostgreSQL via Supabase Free
- Supabase Storage Free
- Supabase Auth Free where authentication is required

### Vector retrieval

- Qdrant, initially running locally without Docker

### LLM

- OpenRouter as the model gateway
- Free models initially

### Embeddings

- sentence-transformers
- `all-MiniLM-L6-v2` initially
- The embedding model must remain configurable and replaceable

### Ingestion pipeline

- Python + `httpx` for source acquisition
- PyMuPDF for PDF extraction
- `python-docx` for DOCX extraction
- BeautifulSoup for HTML extraction
- Custom Python cleaning and normalization
- Custom Python chunking initially
- sentence-transformers for local embeddings
- Qdrant for vector storage
- PostgreSQL for source, document, version, and ingestion metadata
- Supabase Storage for original files

### Observability

- Python structured logging
- OpenTelemetry libraries
- No paid observability platform initially

### Development and deployment

- Windows + existing Python virtual environment
- GitHub for source control
- GitHub Actions for CI
- No Docker currently
- No virtualization-dependent infrastructure currently

## Cost principle

> Xportra AI must remain capable of development and testing using free-tier or locally available infrastructure until a specific requirement justifies spending money.

This does not prohibit future paid infrastructure. Any paid component must be justified by an identified requirement, capacity constraint, reliability requirement, or production need.

## Architectural flexibility

The selected technologies represent the initial implementation baseline rather than permanent architectural commitments. The application should use appropriate abstractions so that:

- Qdrant can later be replaced if required
- the LLM provider/model can change
- the embedding model can change
- Supabase PostgreSQL remains PostgreSQL-compatible at the application boundary
- local development infrastructure can later be replaced by production infrastructure

This does not require broad abstraction now; it requires a deliberately simple boundary that does not lock the system to a single vendor or deployment pattern.

## Ingestion boundary

The ingestion flow remains a staged, traceable pipeline:

```text
Authoritative Source
      ↓
Source Acquisition
      ↓
Document Parsing
      ↓
Cleaning / Normalization
      ↓
Metadata Extraction
      ↓
Chunking
      ↓
Embedding
      ↓
Qdrant
```

Original source documents and ingestion/source metadata must remain traceable through the system. Provenance and version information must remain associated with the source item, extracted content, and any derived chunks or embeddings so that the system can explain where a document came from and how it was processed.

## Source authority and provenance

Xportra AI uses a source-authority hierarchy to ensure that regulatory guidance is grounded in the correct level of authority and remains auditable over time.

### Source-authority hierarchy

1. Primary legal and regulatory authorities are preferred.
2. Official government guidance is distinguished from law or regulation and is not treated as equivalent to a primary regulatory instrument unless the jurisdiction and legal status are clearly established.
3. Recognized international authorities such as WTO, IPPC, and Codex may be used according to their jurisdictional and technical role, but they do not automatically outrank applicable destination-country law.
4. A lower-tier source must never silently be treated as equivalent to a primary regulatory source.
5. Both origin jurisdiction and destination jurisdiction must be represented conceptually because export compliance depends on both.

### Initial Nigerian authorities

Where applicable, the architecture must support the following primary origin-jurisdiction authorities:

- NAFDAC
- Nigeria Customs Service
- Nigerian Export Promotion Council
- Standards Organisation of Nigeria
- Federal Ministry of Agriculture and Food Security
- Nigeria Agricultural Quarantine Service

Destination-country primary authorities must also be supported because export compliance depends on both origin and destination law.

### Source status and effective-date handling

Source status and source freshness are separate concepts. The architecture must track whether a source is current, obsolete, superseded, draft, archived, or withdrawn independently from its authority tier. Effective dates must be tracked explicitly so superseded material does not silently become current guidance.

### Required source metadata

The architecture must support the following source metadata fields:

- authority
- jurisdiction
- publication date
- effective date
- version
- status
- source URL
- retrieval timestamp
- supersedes
- superseded_by

This metadata supports traceability, supersession handling, and freshness checks without conflating a source's legal authority with whether it is still current.

## Boundary notes

- The ingestion boundary is intentionally defined as a pipeline boundary, not as an application implementation.
- Source material, metadata, and derived artifacts remain distinct but linked.
- The architecture supports a future move from local development infrastructure to production infrastructure without forcing a premature redesign.
- Source authority, source freshness, and effective-date handling remain architecture-level concerns even before domain implementation begins.
