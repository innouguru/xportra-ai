# Phase 4D.2 — Sesame-to-EU Pilot Product-Owner Decisions

- **Status:** Product direction agreed for planning; ADR-0017 accepted as the
  basis for implementation planning only.
- **Date:** 2026-10-20.
- **Related research:** [Phase 4D.1 source research](./phase-4d-1-sesame-eu-pilot-source-research.md).
- **Related scope:** [Phase 4D administration proposal](./phase-4d-regulatory-knowledge-administration.md).
- **Related requirements:** Proposed R-4D in `REQUIREMENTS.md`.
- **Related architecture:** Accepted as the basis for implementation planning
  only, [ADR-0017](../decisions/ADR-0017-regulatory-knowledge-administration.md).
- **Later architecture directions:** The eight Phase 4D.7 product-owner
  directions are consolidated in ADR-0017; they do not replace this pilot
  scope record or authorize implementation.
- **Implementation authorized:** No.
- **Exporter publication authorized:** No.

The product owner has confirmed the planning decisions in this record and
accepted ADR-0017 as the basis for implementation planning only. Neither
decision establishes shipment-level legal applicability, implementation
authorization, or exporter-facing publication approval. The remaining
architecture and technical decisions are listed separately below and in
[ADR-0017](../decisions/ADR-0017-regulatory-knowledge-administration.md).

## A. Agreed planning direction

The agreed narrow pilot direction is:

- Raw or unprocessed sesame seeds (*Sesamum indicum*) intended for human
  consumption, originating in Nigeria.
- Kano and Jigawa States as initial operational sourcing regions only.
  They are not legal applicability conditions absent authoritative evidence.
- Consignments intended for import and customs clearance in the Netherlands.
  This does not require or establish first EU entry through a Dutch border
  control post; entry point, designated BCP, and transit route remain explicit
  shipment facts for review.
- Official regulatory sources prioritized. Extracted statements remain
  candidates until human verification and a separate pilot-applicability
  approval are recorded.
- No exporter-facing publication until the relevant controls are implemented,
  tested, and separately authorized.

The direction is not a confirmed CN/TARIC classification, legal conclusion,
complete import checklist, shipment assessment, government approval, or
export clearance. The narrow commodity and destination boundary keeps
classification, source verification, and acceptance testing tractable;
claiming coverage for all Nigerian agricultural exports or every EU
destination would exceed the retrieved evidence and available source
coverage.

## B. Decision register and remaining answers

| Decision | Agreed direction / recommended default | Alternatives | Why it matters | Owner | Status |
|---|---|---|---|---|---|
| Intended use | Human-consumption food-use sesame; exclude seed for sowing from the initial pilot | Add seed for sowing only as a separately scoped later product | Intended use changes the relevant source universe and legal treatment | Product owner; qualified regulatory reviewer for applicability | **Agreed for planning; legal applicability unverified** |
| Product presentation | Raw or unprocessed sesame seeds; record detailed preparation and treatment attributes | Add named processed forms only as separately classified scope | The actual form affects tariff classification and applicable provisions | Product owner; qualified customs-classification reviewer | **Agreed at planning level; exact specification/classification pending** |
| Destination | Netherlands, for consignments intended for import and customs clearance there | Dutch first EU entry; Dutch-market placement regardless of entry route | Import clearance, first entry, and market placement are related but distinct | Product owner; customs reviewer | **Agreed for planning; route/BCP remain unverified shipment facts** |
| Kano and Jigawa | Operational sourcing focus only; not an applicability rule | Add evidence-backed origin conditions only if later supported | No reviewed source establishes a state-specific EU rule | Product owner; sourcing operations | **Agreed** |
| Shared catalog administrators | Designated Xportra staff; global authority must be separate from organization membership or ownership | A separately approved contracted-reviewer role | Tenant roles cannot safely grant global authority | Product owner; security/identity owner | **Staff-only planning direction accepted; grant/revocation design pending** |
| Publication governance | Stage A verifies source provenance, source text, wording, and interpretation. Stage B separately approves applicability to the defined pilot scope. Both decisions are auditable and required before exporter presentation as applicable. | Revise only through an explicit governance decision; machine-only publication is excluded | Requirement verification does not prove shipment or pilot applicability | Product owner; authorized reviewers | **Two-stage approval agreed; permissions and transition design proposed** |
| Separation of reviewers | Prefer different people for verification and applicability approval where practical; any small-team same-person exception must be explicit, permission-controlled where feasible, and auditable | Enforce two-person review for every item | Provides independent challenge without silently blocking a small pilot team | Product owner; governance owner | **Direction agreed; exception controls need architecture approval** |
| Initial document intake | Staff-uploaded regulatory PDFs and supported text documents; preserve originals and known official source URLs as metadata. No URL retrieval or automated acquisition. | Add allowlisted URL retrieval only in a separately approved later scope | Remote retrieval adds security and reliability controls; evidence-upload PDF parsing is not regulatory parsing | Product owner; architecture/security reviewers | **Upload-only agreed; precise formats and PDF implementation gate pending** |
| Organization-specific and buyer-specific requirements | Defer organization-managed requirements workflow, schema/API, and UI from this pilot; treat them as a later, clearly separated tenant-isolated extension | Bring forward only under a separately approved scope and data boundary | Private terms must never be indistinguishable from shared official law | Product owner; architecture owner | **Separate-category direction agreed; pilot deferral recommended** |
| Exporter uncertainty | Distinguish verified requirement, approved pilot applicability, unknown applicability, incomplete coverage, stale/re-review, unverified candidate, and future organization/buyer-specific records. Missing entries are not proof of no requirement. | Revise user wording without collapsing states | Missing facts or source coverage cannot support a negative compliance conclusion | Product owner; UX and regulatory reviewers | **Principle agreed; exact copy and acceptance tests pending** |
| Ingestion execution | Persist the original artifact and durable job before processing; use durable background processing with idempotency, retries, visible failures, restart recovery, and attempt history | Worker, queue, dispatch, and retry mechanisms to be evaluated against hosting and operations constraints | Current stages are synchronous; no durable job, worker, queue, or scheduler exists | Product owner; architecture/operations owner | **Background-processing direction accepted; mechanism, budget/hosting fit, limits, and operational ownership pending** |

## C. Evidence and legal limitations

The underlying citations, dates, URLs, and claim-level limitations are
recorded in the [Phase 4D.1 research record](./phase-4d-1-sesame-eu-pilot-source-research.md).
The evidence categories remain distinct:

1. Retrieved source text.
2. Text verified against an identified source.
3. Verified against an authentic legal instrument.
4. Applicability confirmed for the defined product scope.
5. Approved for publication by an authorized reviewer.

The confirmed planning direction does not promote any source claim to
categories 4 or 5. Shipment-level applicability and publication approval
remain unestablished.

### Supported by reviewed authentic Official Journal texts

- The authentic text of Regulation (EU) 2019/1793 contains Article 4's
  CHED release text, Article 8(2)'s overall-frequency meaning, Article
  10(1) and 10(2)(d)'s sampling-results and Salmonella-in-25-g text, and
  Article 11's Annex II official-certificate rule.
- The reviewed authentic 2025/1441, 2026/194, and 2026/1206 texts list
  Nigerian food-use *Sesamum* seeds in Annex II, point 1, row 12, with CN
  `1207 40 90`, specified processed-product `ex` lines and TARIC `49`,
  Salmonella, and a 50% identity/physical-check frequency. The row's
  footnote refers to Annex III, point 1(a).
- Article 8(2) says the 50% frequency is overall for all products within
  that Annex II entry. It is not an individual shipment guarantee or a
  Salmonella prevalence rate.
- Regulation 2025/1441 amended Article 10(2)(a), deleted Article 10(2)(c)
  and Article 10(3), changed Article 3, and replaced Annex IV. The reviewed
  provisions preserve Article 10(2)(d)'s Salmonella criterion and the
  general Article 11 certificate clause. Both identified 2025 corrigenda
  were checked; neither changes the Nigerian sesame row.
- The bounded Official Publications Office metadata search found no later
  direct amendment to Regulation 2019/1793 after 2026/1206 by the research
  date. It was not an exhaustive search of separate EU food, customs,
  plant-health, or emergency instruments.

### Consolidated text and other source limits

The 30 June 2026 consolidation is a documentation text without legal effect.
Its sesame entry and relevant clauses were cross-checked against authentic
OJ instruments described above; it is not the legal authority for those
category 3 findings. No material sesame-row or cited Article 4, 8, 10, or
11 claim in this decision record relies solely on the consolidation. It does
not establish future legal status, shipment classification, or applicability.

NEPC's export-procedures and sesame-profile pages could not be retrieved as
readable text. The NAQS Plant Export Guidelines PDF has not been text-read,
and its current status and page-level contents remain unknown. The NAQS
general plant-quarantine page was readable in an earlier research pass, but
it is general guidance and does not establish a sesame-specific obligation.

### Review still required

- Obtain qualified review of the exact raw/unprocessed product specification,
  CN/TARIC classification, origin evidence, shipment date, and applicable
  EU/Dutch scope. The agreed food-use and Netherlands import/customs-clearance
  direction does not establish shipment-level applicability.
- Establish which EU and Nigerian requirements apply to that defined scope;
  the annex description alone does not settle shipment applicability. Keep
  first EU entry, designated BCP, and transit route as explicit shipment
  facts; do not infer them from Dutch customs clearance.
- Obtain readable, current NEPC procedures and the complete NAQS guidelines,
  and verify any applicable sesame-specific Nigerian procedure.
- Maintain Kano/Jigawa as operational sourcing regions only unless later
  authoritative evidence supports a separate legal applicability rule.
- Keep all candidates unpublished until both Stage A verification and the
  separate Stage B pilot-applicability approval, with provenance and review
  history, are recorded.

## D. Proposed pilot acceptance criteria

These are proposed testable criteria for later approval; recording the
planning direction does not authorize their implementation:

1. Stage A verification records the reviewer, timestamp, exact source
   artifact/version/location, wording, and rationale; Stage B independently
   records the pilot-scope version, applicability decision, reviewer,
   timestamp, and rationale. Neither stage may be inferred from the other.
2. The exporter interface presents a requirement as applicable only after
   both required decisions and an explicit publication state are approved
   and current. Drafts, rejected candidates, unverified candidates, unknown
   applicability, and withdrawn or superseded records are not represented
   as approved applicable requirements.
3. Every published requirement has traceable provenance to its source,
   artifact/version, exact source location, candidate, reviewer, review
   decision at both stages, and publication event.
4. Applicability is explicitly evaluated for the agreed product use and
   presentation plus verified classification, origin, destination, route,
   and relevant dates when applicable. Missing facts produce `unknown`, not
   a negative result.
5. Unknown, incomplete, stale, and under-review coverage is visible and
   cannot be interpreted as proof that no requirements exist.
6. Source freshness, withdrawal, changed content, and supersession can be
   represented; affected requirements can be flagged for re-review while
   preserving prior artifacts and publication history.
7. Exporter-facing behavior and copy do not imply government approval,
   certification, legal clearance, or export clearance.
8. Tests exercise both approval gates, publication gating, provenance,
   defined-scope applicability, uncertainty/incomplete-coverage states, source changes
   and re-review, exclusion of non-published material, and isolation of
   future organization-specific records.

## E. Architecture planning decision and remaining gates

ADR-0017 is accepted as the basis for implementation planning only. The
open design decisions below remain assigned to the Phase 4D.10 task sequence;
they do not reopen the eight accepted planning directions.

These gates remain independent:

| Gate | State now | What is needed |
|---|---|---|
| Research complete | Bounded research pass recorded; source and legal-status gaps remain | No broader or exhaustive legal verification is claimed |
| Pilot direction agreed | **For planning** | Food-use raw/unprocessed Nigerian sesame, Kano/Jigawa operational sourcing, and intended Dutch import/customs clearance |
| Complete product and legal applicability defined | **Pending** | Exact classification and specification, shipment-level facts, and qualified applicability/source review |
| Architecture basis accepted for planning | **Yes, planning only** | ADR-0017 accepted; unresolved technical contracts remain open |
| Implementation authorized | **No** | Approved scope and architecture, updated requirements/roadmap, and bounded active implementation tasks |
| Requirements approved for exporter publication | **No** | Qualified applicability review plus authorized human review and explicit publication approval |

Passing one gate does not satisfy any later gate automatically. Architecture
acceptance does not establish legal applicability, authorize implementation,
or authorize exporter-facing publication.
