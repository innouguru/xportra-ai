# Phase 4D.4 — Pilot Scope Confirmation and Implementation Readiness Gate

- **Assessment date:** 2026-10-20.
- **Status:** Pilot direction agreed for planning; ADR-0017 accepted as the
  planning basis only; classification and shipment-specific applicability
  remain open; implementation is not authorized.
- **Research inputs:** [Phase 4D.1 source research](./phase-4d-1-sesame-eu-pilot-source-research.md),
  [Phase 4D.2 product-owner decision record](./phase-4d-2-sesame-eu-pilot-product-owner-decisions.md),
  and [Phase 4D.3 country research](./phase-4d-3-eu-pilot-country-research.md).
- **Architecture:** [ADR-0017](../decisions/ADR-0017-regulatory-knowledge-administration.md)
  is accepted as the basis for implementation planning only.
- **Architecture review:** Phase 4D.6 repository-grounded recommendations
  and the Phase 4D.7 consolidated product-owner directions are recorded in
  ADR-0017; implementation contracts remain open for their planned gates.

This record distinguishes the product owner's agreed planning choices from
the unresolved exact product specification/classification, shipment entry
and customs route, architecture, implementation, and regulatory publication.
It is a documentation-only readiness assessment.
It does not assess a shipment, establish import clearance, provide a complete
export checklist, or authorize runtime or schema work.

## 1. Agreed planning direction

The product owner has agreed with proceeding toward the Netherlands-based
pilot recommendation. For planning, the direction is:

- **Product:** raw or unprocessed sesame seeds (*Sesamum indicum*) intended
  for human consumption; seed for sowing is outside the initial direction.
- **Presentation:** raw or unprocessed. Exact preparation/treatment details
  and legal classification still require a written product specification
  and qualified review.
- **Origin:** Nigeria.
- **Initial sourcing focus:** Kano and Jigawa States, Nigeria. These are
  operational sourcing regions only, not regulatory applicability
  conditions.
- **Country:** the Netherlands, selected because relevant NVWA national
  import guidance was accessible and readable in the Phase 4D.3 research.
  The agreed planning boundary is consignments intended for import and
  customs clearance in the Netherlands.
- **Source governance:** prioritize official sources. Stage A human
  verification of source, wording, and interpretation is separate from Stage
  B approval of applicability to the defined pilot scope. Both decisions
  must be explicitly recorded before exporter presentation as applicable.
- **Document intake:** designated Xportra staff upload source PDFs and
  supported text documents; official URLs are metadata only. URL retrieval is
  deferred. Regulatory PDF capability remains subject to parser and safety
  verification.
- **Organization-specific requirements:** internal and buyer-specific
  requirement management is deferred from the pilot and, if later approved,
  must remain a separate tenant-isolated category.
- **Exporter-facing publication:** prohibited until publication and
  applicability controls are implemented, tested, and separately
  authorized. No requirement is approved for publication by this record.

No shipment has been assessed. The listed direction is not a finding that
the proposed product fits a particular CN/TARIC code, satisfies Dutch or
EU entry conditions, or is cleared for import.

## 2. Destination boundary

“The Netherlands” can describe several related but distinct facts:

1. **First EU entry through a Dutch designated border control post (BCP).**
   This identifies the point where a consignment first enters the Union and
   where applicable border controls occur. It requires the actual route and
   a designated BCP authorized for the relevant goods to be identified.
2. **Import and customs clearance in the Netherlands.** This identifies the
   Member State where the goods are released into the relevant customs
   procedure. It does not, by itself, prove that the first EU entry or
   official border check occurred at a Dutch BCP; transit and customs
   procedures must be considered.
3. **Placement on the Dutch market, regardless of EU entry route.** This
   identifies the intended market. Goods may enter and undergo border
   procedures in another Member State before being marketed in the
   Netherlands, so this does not establish Dutch first-entry procedures.

The concepts can coincide, but they are not interchangeable. Choosing the
Netherlands as a market destination does not establish the applicable entry
point.

### Agreed planning boundary

**The product owner has agreed to limit the pilot direction to consignments
intended to be imported and customs-cleared in the Netherlands, while
requiring the actual first EU entry point, designated BCP, and transit route
to be explicit shipment facts before entry-control applicability is
assessed.** Do not include goods solely because they will eventually be
placed on the Dutch market after entering and being cleared in another
Member State.

This is the narrowest useful scope aligned with the readable NVWA guidance
about imports into the Netherlands, without asserting that the goods must
enter through a Dutch BCP or that the source research established a
commodity-authorized BCP. Phase 4D.3 did not verify the applicable Dutch
BCP list or a route. The planning boundary is agreed, but route-specific
entry and BCP applicability still require shipment facts and qualified
customs/regulatory review. The agreed boundary does not require all first
entry to occur in the Netherlands.

## 3. Decisions and blockers

“Agreed direction” below records the supplied product-owner direction; it
does not mean the operational choice is implemented or legally verified.

| Decision / question | Recommended default | Rationale | Owner | Status | Evidence or action needed |
|---|---|---|---|---|---|
| Food-use sesame versus seed for sowing | Limit the pilot direction to sesame intended for human consumption; exclude seed for sowing. | Intended use changes the source universe and legal treatment. | Product owner; qualified regulatory reviewer for applicability | **Agreed for planning; legal applicability unverified** | Verify intended-use evidence and current legal scope for the actual consignment. |
| Raw/unprocessed presentation | Raw or unprocessed sesame seeds; record exact cleaning, hulling, treatment, and preparation details. | “Raw” alone may not settle tariff classification or applicable provisions. | Product owner; customs-classification reviewer | **Agreed at planning level; detailed specification pending** | Written product specification and qualified classification review. |
| CN/TARIC classification | Do not hard-code or infer classification from the research row. | EU provisions may depend on tariff line and product form; an annex description is not a customs ruling. | Qualified customs-classification reviewer | **Open blocker** | Classification opinion for the exact product, intended use, and presentation, with date and source. |
| Netherlands destination meaning | Scope planning to consignments intended for Dutch import/customs clearance; require explicit entry route and BCP facts; exclude goods only marketed in the Netherlands after entry/clearance elsewhere. | First entry, customs clearance, and market placement are related but distinct. | Product owner; customs reviewer | **Agreed for planning; shipment/route facts remain open** | Verify the customs procedure and entry route for each shipment; country direction does not establish first EU entry. |
| Actual designated border control post and entry procedure | No BCP selected. Determine it from the intended route and product scope before evaluating BCP-specific applicability. | Research confirmed general NVWA controls at BCPs but did not verify the current Dutch BCP list or authorization for this product. | Importer/logistics owner; qualified regulatory reviewer | **Open blocker** | Current Commission BCP listing, commodity/activity authorization, and confirmation by the relevant national authority or importer. |
| Plant-health and phytosanitary requirements | Treat as a separate applicability track; neither assume a certificate is required nor assume exemption. | NVWA general plant-product guidance describes procedures, but the specific sesame form and applicable plant-health provisions were not determined. | Qualified plant-health reviewer; importer | **Open blocker** | Exact-product check against current EU plant-health law and official Dutch import guidance, including any certificate, notification, inspection, or exception. |
| Kano and Jigawa scope | Use as initial operational sourcing regions only; do not make them applicability conditions without evidence. | No source in the reviewed research establishes a state-specific EU rule. | Product owner; sourcing operations | **Agreed; origin evidence remains operational** | Maintain sourcing traceability as an operational need; regulatory relevance requires authoritative evidence. |
| Input method and formats | Designate Xportra staff upload PDFs and supported text documents; record official URLs as metadata only; defer URL retrieval. | Regulatory parsing currently supports TXT, Markdown, and JSON, not PDF; evidence PDF extraction is separate. | Product owner; architecture/security reviewers | **Upload-only/no URL retrieval agreed; format and PDF capability gates pending** | Confirm exact text formats, parser interface, dependency, upload/extraction limits, malware/content handling, and page-level provenance. |
| Stage A requirement verification | Human verifies source provenance, relevant wording/location, and interpretation. | Extraction alone does not establish authoritative wording. | Authorized verification reviewer | **Agreed; architecture and implementation pending** | Approve roles, audit events, decision vocabulary, and transition controls. |
| Stage B pilot-applicability approval | Separate decision determines applicability to the defined pilot; unknown remains unresolved and cannot be treated as applicable. | Verified wording does not prove applicability to a product or shipment. | Authorized applicability approver; qualified reviewer as needed | **Agreed; architecture and implementation pending** | Approve scope-version linkage and decision/audit model; obtain qualified legal/classification review. |
| Reviewer separation | Prefer different people for the two stages; a small-team same-person exception must be explicit, permission-controlled where feasible, and auditable. | Independent review is preferable without silently making small-team operation impossible. | Product owner; governance owner | **Direction agreed; exception control design pending** | Approve role separation and exception procedure in ADR-0017. |
| Buyer/organization-specific requirements | Defer organization and buyer-specific requirement management from the pilot; any later capability must be separately categorized and tenant-isolated. | Private terms are not public law and must never be merged indistinguishably into the shared catalog. | Product owner; architecture owner | **Pilot deferral agreed in direction; architecture confirmation pending** | Confirm scope exclusion; no pilot schema/API/UI for tenant-specific rules. |
| Unknown, incomplete, stale, or unverified coverage | Distinguish approved applicable requirement, unknown applicability, incomplete coverage, stale/re-review, unverified candidate, and (later) tenant/buyer-specific records. | Missing facts or records cannot support a negative compliance conclusion. | Product owner; qualified regulatory reviewer; UX owner | **Principle agreed; exact copy and architecture pending** | Define tested state semantics; absence of a catalog match must not imply no requirement or clearance. |
| NEPC and NAQS source verification | Keep Nigerian export and phytosanitary candidates unpublished until readable current official sources and applicability are verified. | NEPC pages were not text-verified; the NAQS Plant Export Guidelines PDF remains unreadable; general NAQS guidance is not sesame-specific. | Qualified Nigerian export/plant-health reviewer; source administrator | **Open evidence blocker** | Obtain and review current NEPC procedure/profile evidence and complete NAQS guidelines or direct official confirmation; record versions and exact provisions. |

### Decision authority

The product owner has agreed the planning direction for intended use,
raw/unprocessed presentation, destination boundary, sourcing-region
treatment, upload-only intake, two-stage review, buyer/organization-scope
deferral, and explicit exporter-facing uncertainty. Exact implementation
contracts remain subject to ADR approval.

Qualified review is required for customs classification, the applicable
EU legal scope and amendment status at a relevant shipment date, entry
conditions, border-control-post designation, plant-health and phytosanitary
applicability, and Nigerian export procedures. Product-owner agreement
cannot substitute for those technical determinations.

## 4. Implementation readiness assessment

The following is a read-only review of the current repository, including
`xportra/domain/ingestion.py`, API authorization and routing, persistence
repositories, migrations `001` and `003`–`008`, `pyproject.toml`, and the
existing unit-test modules. A Phase 4C-specific findings document was not
located in the inspected `docs/` or `tasks/` paths; Phase 4D.1–4D.3 and
current source files were used as the evidence baseline. Existing evidence
upload capabilities are not treated as regulatory source administration.

| Capability | What exists in the repository | Missing for the proposed regulatory pilot |
|---|---|---|
| Administrator authorization distinct from tenant owner/member | `xportra/api/authorization.py` authorizes tenant `owner`/`member` roles; `xportra/api/auth.py` resolves user identity and tenant membership. | No separate global staff grant, grant/revocation lifecycle, Stage A/Stage B permission, or shared-regulatory-operation check. Tenant ownership is not a safe substitute. |
| Source registry and document intake | Migration `001` contains shared authorities and regulatory-source records with jurisdiction, source URL, retrieval time, status, and supersession pointers. `RegulatorySourceRepository` reads sources; `SourceAcquisitionService` validates and records artifact metadata. | No complete source-management or regulatory upload API/UI. Artifact records store URI/hash/length/type metadata; the acquisition service does not persist original bytes. No URL-retrieval workflow is proposed. |
| Text parsing and PDF extraction/failure handling | `ArtifactParsingService` handles `text/plain`, `text/markdown`, and `application/json`; explicit parser exceptions represent malformed or empty input. Normalization and extraction services exist. | No PDF MIME support, PyMuPDF integration, or regulatory PDF extraction/failure workflow. `pyproject.toml` does not declare PyMuPDF. The separate exporter evidence PDF path does not implement regulatory ingestion. |
| Durable ingestion jobs, stage status, and retry | Artifact, normalization, metadata, and candidate tables persist individual records and some statuses. | No unified durable ingestion-attempt/job record with stage history, retry lifecycle, and safe terminal outcomes. Existing evidence-upload `processing_status` is tenant evidence state, not regulatory ingestion. |
| Regulatory candidate provenance and review | `regulatory_requirements` candidates retain their normalized-document association, source location, position, and extracted/rejected/archived status. | No Stage A verification or Stage B applicability decision, reviewer identity/time/rationale, requested-changes state, complete review history, or candidate-to-canonical linkage was identified. |
| Publication approval and audit history | Canonical `requirements` have draft/active/superseded/archived status; `requirement_sources` link canonical requirements to sources. | No two-stage decision record, append-only publication audit, or linkage from verified candidate locations to canonical requirements. `active` alone does not establish verification or pilot applicability. |
| Applicability model | `ComplianceApplicabilityService` composes the deterministic `RegulatoryRequirementApplicabilityService`; outcomes preserve applicable, not-applicable, and unknown. The latter supports optional persistence to `regulatory_requirement_applicability`, but the current assessment API does not wire that repository and accepts caller-supplied requirements. Current matching covers limited destination, commodity, actor, and quantity facts. | Phase 4D.6 proposes `regulatory_requirement_applicability` as the persisted runtime result model after additive canonical-link and pilot-scope-version support; `requirement_applicability` remains a separate tenant/product/destination workflow. Stage B approval stays separate append-only governance history. Current logic does not establish sesame classification, detailed presentation, route/BCP, or the full current legal universe. This proposal is pending approval; do not add a third applicability table or evaluator. |
| Exporter retrieval restricted to approved publications | Existing assessment/application paths evaluate supplied requirement records; current APIs serve tenant workflows. | No server-owned catalog retrieval or filter requiring both stages and current source state. Existing editable requirements UI is not a published-catalog interface. |
| Freshness, supersession, unknown/incomplete states | Source records can represent status, version/effective dates, and supersession pointers. Applicability outcomes include `unknown`. | No complete source-change-to-re-review workflow; no complete freshness policy or publication history; no catalog coverage state that distinguishes incomplete/stale coverage from no applicable requirements. Unknown applicability alone does not represent catalog completeness. |
| Admin API and user interface | Existing API routers cover tenant, shipment/compliance, evidence upload, organization, and related workflows. Existing frontend has no regulatory knowledge administration interface identified. | No regulatory source/candidate/review/publication API or administration UI. |
| Organization-specific requirements | Tenant models exist, but no separate organization-managed requirements workflow was identified as an approved shared-catalog capability. | Defer organization-specific and buyer-specific schema/API/UI from this pilot; any later capability must be a distinct tenant-isolated extension, never merged into official regulation. |
| Automated verification | Unit tests cover parser/normalization, metadata extraction, requirement extraction, deterministic regulatory applicability, and tenant authorization/compliance behavior. | No integrated tests for global staff grants, both approval gates, provenance through publication, retry lifecycle, source-change re-review, published-catalog filtering, organization separation, or combined tenant-isolation/publication boundaries. Existing generic tenant tests do not prove these new paths. |

These findings describe partial foundations, not a complete feature. A
service, repository, migration, parser, or existing test is not by itself an
implemented regulatory-administration workflow or publication control.
No schema change, API, UI, or runtime behavior was created by this
assessment.

## 5. Independent gate status

| Gate | Status | Evidence / remaining condition |
|---|---|---|
| 1. Research completed | **Completed as bounded research; limitations remain** | Phase 4D.1–4D.3 records source retrieval and legal-chain work; NEPC/NAQS, classification, BCP, and broader legal-scope gaps remain explicit. |
| 2. Pilot direction agreed | **Reached for planning** | Raw/unprocessed food-use Nigerian sesame; Kano/Jigawa are operational sourcing regions; intended Dutch import/customs clearance; staff-upload-only direction; two-stage review; organization-specific workflow deferred. |
| 3. Destination and product scope fully defined | **Planning boundary agreed; complete legal/operational applicability pending** | Exact product specification/CN-TARIC classification, route/BCP, current plant-health measures, and shipment facts require qualified review. |
| 4. Architecture basis accepted for planning | **Yes, planning only** | ADR-0017 is accepted as the planning basis. Grant bootstrap, schema/linkage/scope versioning, background execution under Render/budget/no-Docker constraints, retention/deletion, file limits/parsing, API compatibility, state semantics, and source-change propagation still require design and approval at their gates. |
| 5. Implementation authorized | **Not authorized** | Requires approved product scope, approved requirements, accepted architecture/ADR where applicable, and a bounded active implementation task. |
| 6. Implementation verified | **Not started** | No Phase 4D implementation exists for this proposed workflow; no implementation acceptance tests have been run. |
| 7. Exporter-facing publication authorized | **Not authorized** | Requires implemented and tested review/publication/applicability controls plus explicit publication authorization. No requirement is approved for exporter publication. |

Passing a gate does not automatically pass a later gate.

## 6. Approval checklist and next decision

Implementation planning is authorized by acceptance of ADR-0017 as the
planning basis only. The system-level staff permission model and
grant/revocation owner, Stage A/Stage B permissions and small-team exception,
durable background execution, artifact retention and security limits, PDF
support gate, freshness and incomplete-coverage policy, and deferral of
organization-specific schema/API/UI remain open for their planned decision
gates. Qualified reviewers must resolve classification, legal scope,
route/BCP, plant-health, and Nigerian-source questions before publication.

The decisions in Phase 4D.2 and this record do not authorize implementation.
Track the active planning task separately from any future bounded
implementation task.
