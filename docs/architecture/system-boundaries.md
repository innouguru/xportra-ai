# System Boundaries — Xportra AI (Phase 0.2)

> Conceptual boundary map, NOT an implementation specification. Detailed
> architecture will be designed and approved before implementation of the
> relevant phase (each phase scoped via `REQUIREMENTS.md` and ADRs).

## Conceptual Flow

```text
Regulatory Knowledge
        ↓
Applicability / Domain Logic
        ↓
Evidence & Document Intelligence
        ↓
Retrieval
        ↓
Compliance Reasoning
        ↓
Decision Support
        ↓
Application/API
```

## Boundary Descriptions

1. **Regulatory Knowledge** — curated regulatory/source content with
   provenance. Grounds everything downstream (principles SP-2, invariants
   on source traceability and ingestion integrity).
2. **Applicability / Domain Logic** — explicit, deterministic rules
   determining which requirements apply. Authoritative over LLM reasoning
   for the regulatory universe (principle SP-1; ADR-0001).
3. **Evidence & Document Intelligence** — organization and interpretation
   of compliance evidence, traceable to its source (principle SP-3).
4. **Retrieval** — scoped, metadata-filtered access to knowledge and
   evidence (invariants on metadata filtering and tenant isolation).
5. **Compliance Reasoning** — source-grounded analysis over applicable
   requirements and evidence; explains, never certifies (principle SP-4).
6. **Decision Support** — gap identification and guidance presentation for
   the exporter; advisory only, not legal certification or official
   approval.
7. **Application/API** — user workflow and integration surface. Carries no
   domain/compliance logic of its own beyond its layer responsibilities
   (invariant: business logic must not move into API handlers for
   convenience).

## Status

- Approved as a conceptual map only. No interfaces, schemas, storage
  choices, or providers are decided here.
- Detailed design for each boundary will be approved in its phase before
  any implementation.
