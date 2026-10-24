# Phase 4D — Product-Owner Architecture Approval Gate

- **Status:** Completed 2026-10-20; ADR-0017 accepted as the basis for
  implementation planning only.
- **Type:** Documentation and approval gate; no implementation is authorized.
- **Architecture decision:** [ADR-0017](../../docs/decisions/ADR-0017-regulatory-knowledge-administration.md), accepted as the basis for planning only.
- **Architecture plan:** [Phase 4D administration plan](../../docs/phases/phase-4d-regulatory-knowledge-administration.md).
- **Pilot direction and evidence:** [Phase 4D.2 decisions](../../docs/phases/phase-4d-2-sesame-eu-pilot-product-owner-decisions.md) and [Phase 4D.4 readiness assessment](../../docs/phases/phase-4d-4-pilot-scope-and-implementation-readiness.md).
- **Proposed requirements:** R-4D in [REQUIREMENTS.md](../../REQUIREMENTS.md).

## Decision record

The product owner accepts ADR-0017 as the architecture basis for proceeding
to implementation planning, with unresolved decisions and qualified-review
gates carried forward.

This acceptance permits planning only. It does not authorize runtime code,
database migrations, production or infrastructure changes, or exporter-facing
publication. Each implementation task requires separate authorization and a
bounded active task; publication requires implemented and tested controls
plus separate explicit authorization.

## Status summary

| Gate | Status |
|---|---|
| Research | Bounded official-source research recorded; completeness and current legal applicability are not established. |
| Pilot direction | Agreed for planning only: raw/unprocessed food-use sesame from Nigeria, Kano/Jigawa operational sourcing, intended Dutch import/customs clearance. |
| Product and shipment applicability | Pending exact specification/classification, route/BCP, plant-health and shipment-specific review. |
| Architecture acceptance | Accepted as the planning basis only. |
| Implementation planning | Authorized; tracked in the successor Phase 4D.10 task. |
| Implementation | Not authorized; requires separate approval and a bounded task. |
| Exporter-facing publication | Not authorized; requires qualified review, implemented and tested controls, and separate explicit approval. |

## Product-owner directions already provided

These directions are recorded and are not reopened by this package. They
govern the accepted planning basis; they do not establish implemented behavior,
legal applicability, or publication approval.

1. **Global access:** Use restricted, operator-managed grants and
   revocations with fail-closed authorization and auditable attribution.
   Tenant owner/member roles do not grant global access, and administrative
   access does not itself grant Stage A or Stage B authority.
2. **Applicability architecture:** Propose additive evolution of
   `regulatory_requirement_applicability` for runtime results. Retain
   `requirement_applicability` for its distinct tenant/exporter/product/
   destination workflow; add no third applicability model. Verify consumers,
   constraints, candidate-to-canonical linkage, and scope versioning before
   implementation. Keep Stage B governance decisions separate from
   evaluator results.
3. **Two-stage review:** Stage A verifies source and requirement wording;
   Stage B separately approves applicability to a versioned pilot scope.
   Different authorized reviewers are the default. A same-person exception
   requires explicit authorization, justification, and audit history.
4. **Durable background ingestion:** Persist the original artifact and
   ingestion job before processing; provide idempotency, safe retries,
   visible failures, attempt history, and restart recovery. Durable background
   processing is settled direction, not a choice against synchronous
   processing. The dispatch/execution mechanism remains undecided and must
   fit Render, budget, no-Docker, and operational constraints. No worker,
   queue, scheduler, or integrated regulatory worker is assumed to exist or
   approved.
5. **Freshness and supersession:** Identify affected requirements and
   restrict them from current applicable use pending required review.
   Preserve historical artifacts, provenance, decisions, and re-review
   history. A source-status change does not automatically make every linked
   requirement legally invalid.
6. **Unknown and incomplete coverage:** Return a qualified partial
   assessment only when verified requirements support it within scope.
   Represent unknown applicability, missing facts, stale sources, and
   incomplete coverage explicitly; reject requests that cannot support a
   defensible limited assessment. A missing catalog entry is not proof that
   no requirement exists.
7. **Artifact retention:** Preserve original artifacts and version history
   under an explicit policy. Retention duration, deletion policy, storage
   limits, and operational rules remain undecided. New versions do not
   overwrite history or inherit approval.
8. **Extraction failure:** Permit controlled manual candidate entry and
   review after failed or partial extraction. Preserve artifact/source
   references, attribution, and extraction outcome. Manual candidates pass
   the same two review stages and do not convert failed/partial processing
   into success.

## Proposed architecture decisions still needing definition

These are implementation-planning gates, not reasons to reopen the settled
product-owner directions. ADR-0017 contains the detailed proposal and
repository evidence; no answer below should be inferred.

| Decision needed | Why it matters |
|---|---|
| Define the trusted operator boundary, grant bootstrap, grant/revocation process, distinct permission assignment, and audit/incident record. | Global access is a new security boundary; no such grant mechanism was found in the current implementation. |
| Confirm additive schema changes, constraints, existing consumers, candidate-to-canonical provenance linkage, and versioned pilot-scope identity. | Existing applicability tables have distinct semantics; the selected runtime-result table currently targets extracted candidates, and neither table is a shared publication approval record. |
| Select a durable background dispatch/execution and recovery mechanism under actual Render, budget, no-Docker, and operations constraints. | Durable background processing is the direction, but the repository has no integrated regulatory job/worker/queue/scheduler, and the mechanism must provide persisted work, idempotency, retry, visible failures, and restart recovery. |
| Set private artifact storage constraints, retention duration, deletion/legal-hold rules, limits, and cost ownership. | Current metadata does not establish durable retention of immutable uploaded bytes; provenance and reproducibility depend on an explicit policy. |
| Define accepted formats, upload and processing limits, PDF parsing/safety and page provenance, and OCR scope. | The regulatory parser currently supports plain text, Markdown, and JSON, not PDF; the separate evidence-upload PDF path is not regulatory ingestion. |
| Define exporter API compatibility/migration from caller-supplied requirement lists to a server-loaded, current published catalog. | The current assessment endpoint accepts caller-supplied requirements and does not load a published canonical catalog. |
| Define observable exporter states and decision rules for unknown facts, stale/superseded material, incomplete coverage, qualified partial outcomes, and rejected/out-of-scope requests. | Unclear states could wrongly imply that missing coverage means no obligations, or that an unsupported request was assessed. |
| Define source-change impact mapping and re-review triggers for candidates, canonical requirements, and prior applicability decisions. | Source/version metadata exists, but no complete workflow was found to identify and restrict affected published material while preserving history. |

## Product, legal, and source-review gates

Architecture approval cannot resolve these matters. Qualified review and
shipment facts remain necessary before a requirement can be approved as
applicable or published.

| Open question | Required review or evidence |
|---|---|
| Exact sesame product form, intended use, processing/treatment, and CN/TARIC classification. | Written product specification and qualified customs-classification and regulatory review. |
| Whether the scope is Dutch import/customs clearance, first EU entry, or market obligations, and how those interact for a shipment. | Confirm customs procedure and actual destination/route; do not infer Dutch first entry from Dutch clearance. |
| Applicable designated BCP, entry procedure, and transit route. | Shipment route and current official BCP authorization/procedure evidence, reviewed by qualified customs/regulatory personnel. |
| Plant-health and phytosanitary applicability. | Qualified plant-health review against current official EU and Dutch sources for the exact product and route. |
| Nigerian export requirements and source completeness. | Retrieve and review current NEPC procedures and complete NAQS materials; resolve the recorded access/readability gaps and verify any sesame-specific procedure. |
| Buyer-specific or contractual requirements. | Deferred from the pilot; any future inclusion needs separate scope, tenant-isolation, and presentation decisions. |

Kano and Jigawa remain operational sourcing regions only unless
authoritative evidence and qualified review establish legal significance.
Research does not establish a complete sesame compliance checklist, shipment
clearance, or exporter-publication approval. No source claim becomes a
verified exporter-facing requirement merely by being recorded here.

## Future acceptance criteria

These are proposed criteria for later implementation and verification; they
are not evidence that the capability or tests exist.

- Unauthorized global access is denied; tenant roles do not confer global
  permissions; grant and revocation actions are attributable and auditable.
- Stage A and Stage B use distinct decisions and permissions; reviewer
  separation is enforced by default and any exception is explicitly
  authorized, justified, and audited.
- Candidate-to-canonical links preserve source/artifact/version/location,
  review decisions, and prior history.
- Durable jobs are persisted with the original artifact before processing;
  idempotency, retries, visible failure/partial outcomes, attempt history,
  and restart recovery are tested.
- Failed/partial extraction remains explicit; controlled manual recovery
  preserves provenance and passes both review stages.
- Stale or superseded sources restrict affected requirements from current
  applicable use pending review, without erasing history or implying
  automatic legal invalidity.
- Exporter assessment loads only current, approved canonical records from a
  server-owned catalog, not caller-supplied requirement lists.
- Partial assessments are limited and qualified; unknown facts and
  incomplete coverage are explicit, and missing entries never mean no
  requirements.
- Tenant isolation is verified for catalog, artifacts, assessment results,
  and evidence.
- User/API states make no unsupported claim of exhaustive coverage,
  government approval, regulatory clearance, or export clearance.

## Non-goals

- Accepting ADR-0017 on the product owner's behalf.
- Implementing code, schema/migrations, tests, or infrastructure.
- Changing production services, configuration, or data.
- Publishing regulatory requirements to exporters or treating the proposed
  pilot as legally verified or exhaustive.
