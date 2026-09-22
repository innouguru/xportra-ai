# ADR-0002: Free-first technology baseline for early project execution

- Status: Accepted
- Date: 2026-09-19

## Context

Xportra AI is in early Phase 0 and has not yet implemented application functionality. The project must remain capable of development and testing using free-tier or locally available infrastructure until a specific requirement justifies spending money.

The system is intended to evolve toward a production-ready compliance intelligence platform, but the repository and architecture remain intentionally minimal. The team must avoid premature infrastructure or provider lock-in while still establishing a practical initial baseline for local development and eventual production evolution.

## Decision

Xportra AI adopts the following initial technology baseline:

- Python 3.13.x
- FastAPI
- PostgreSQL via Supabase Free
- Supabase Storage Free
- Supabase Auth Free where authentication is required
- Qdrant running locally without Docker
- OpenRouter as the model gateway with free models initially
- sentence-transformers with `all-MiniLM-L6-v2` initially
- Python + `httpx`, PyMuPDF, `python-docx`, BeautifulSoup, custom cleaning and chunking, structured logging, and OpenTelemetry libraries for the ingestion and observability pipeline
- Windows + the existing Python virtual environment
- GitHub + GitHub Actions
- No Docker currently
- No paid observability platform currently

Further, the project will maintain a free-first principle:

> Xportra AI must remain capable of development and testing using free-tier or locally available infrastructure until a specific requirement justifies spending money.

This applies to development and early validation work. Paid infrastructure is allowed only when there is an explicit requirement, capacity limitation, reliability need, or production need that justifies the spending.

## Alternatives considered

### 1. Full cloud-first / paid-first stack

This would reduce setup friction but would create unnecessary cost and early lock-in before requirements are known. It would also move the project away from the lightweight local-first model required for early development and experimentation.

### 2. Docker-first local stack

Docker is a useful deployment abstraction later, but it is not required for the current project stage. The project explicitly does not require Docker at this point, and requiring it too early would impose local infrastructure complexity before the product requirements are established.

### 3. Vendor-locked provider choices without abstraction

This would risk unnecessary lock-in and would conflict with the requirement to preserve architectural flexibility as the project matures.

## Consequences

- The project retains a practical, low-friction path for development and testing with free or local infrastructure.
- The architecture remains flexible enough for future replacement of Qdrant, LLM provider/model selection, embedding models, and infrastructure boundaries.
- The system avoids premature infrastructure cost and Docker complexity.
- The baseline remains clearly scoped as an initial implementation decision rather than a permanent commitment.
- Future paid infrastructure decisions will require explicit justification based on requirements or production constraints.

## Related requirements

- `REQUIREMENTS.md` — product, principles, and cost-boundary decisions.
- `docs/architecture/technology-baseline.md` — baseline specification and ingestion boundary.
- `docs/architecture/configuration-contract.md` — environment contract remains separate from provider selection.
