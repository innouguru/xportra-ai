# ADR-0003: Source authority framework for regulatory provenance

- Status: Accepted
- Date: 2026-09-19

## Context

Xportra AI is designed to support export-compliance intelligence for agricultural exporters. The system must guide users using regulatory sources that are authoritative, relevant, and current, but it must not silently confuse weaker sources with primary legal authority.

Export compliance depends on both origin jurisdiction and destination jurisdiction. A document may be an authoritative source in one context and informative only in another. In addition, a source may be official but stale, superseded, or non-binding. Source status, authority, and effective dates are therefore distinct concerns.

The project also requires that source traceability be preserved, and that the system never represent lower-tier guidance as if it were equivalent to primary law or regulation.

## Decision

Xportra AI adopts the following source-authority framework:

1. Primary legal and regulatory authorities are preferred as the primary source tier.
2. Official government guidance is distinguished from law or regulation and is not treated as equivalent to a primary regulatory source unless the legal status is explicitly established.
3. Recognized international authorities such as WTO, IPPC, and Codex may be used according to their jurisdictional and technical role, but they do not automatically override applicable destination-country law.
4. Source status and effective dates are tracked separately from source authority so superseded or withdrawn material does not silently remain current.
5. Lower-tier sources must never be silently treated as equivalent to a primary regulatory source.
6. The system must represent both origin and destination jurisdictions conceptually because export compliance depends on both.
7. Source metadata must include: authority, jurisdiction, publication date, effective date, version, status, source URL, retrieval timestamp, supersedes, and superseded_by.

Initial Nigerian authorities include, where applicable:

- NAFDAC
- Nigeria Customs Service
- Nigerian Export Promotion Council
- Standards Organisation of Nigeria
- Federal Ministry of Agriculture and Food Security
- Nigeria Agricultural Quarantine Service

Destination-country primary authorities must also be supported because export compliance depends on both origin and destination jurisdictions.

## Alternatives considered

### 1. Treat all sources as equivalent if they appear relevant

This would simplify retrieval logic but would conflate authority and status. It would create false confidence and could mask the difference between a binding regulation and a secondary summary or advisory note.

### 2. Ignore jurisdictional role and choose by recency alone

This would prioritize timeliness over legal authority. It would risk using superseded or lower-tier materials as if they were controlling guidance.

### 3. Allow the model to infer authority without explicit metadata

This leaves too much ambiguity and reduces auditability. The project requires source transparency and explicit authority tracking.

### 4. Source-authority framework with explicit provenance metadata (chosen)

This preserves legal hierarchy, jurisdictional nuance, and source traceability while keeping source status and source authority separate concepts. It also matches the requirement that source freshness and effective-date handling remain explicit and auditable.

## Consequences

- The system will treat source hierarchy as a first-class architecture concern, not an afterthought.
- Retrieval, reasoning, and summarization will need metadata fields for authority, status, jurisdiction, and supersession.
- Lower-tier or historic sources remain usable for context but must be identified as such.
- The architecture will support both origin and destination jurisdiction logic without assuming a single legal authority is always controlling.
- Future implementation work must maintain this distinction between source authority and source freshness.

## Related requirements

- `REQUIREMENTS.md` — Source Authority & Provenance section (SA-1 through SA-7)
- `docs/architecture/technology-baseline.md` — source-authority and provenance guidance
- `docs/decisions/ADR-0001-deterministic-applicability-authoritative.md` — authoritative decision logic remains distinct from LLM reasoning
- `docs/decisions/ADR-0002-free-first-technology-baseline.md` — technology baseline remains separate from regulatory source decisions
