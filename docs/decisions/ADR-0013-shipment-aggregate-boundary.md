# ADR-0013: Tenant-scoped first-class Shipment aggregate

- Status: Accepted (design/documentation only — no implementation)
- Date: 2026-10-07
- Scope: Commercial shipment/profile ownership boundary; constrains the
  future shipment-persistence implementation phase (expected migration 013)
- Requirements: `REQUIREMENTS.md` R-10.8.8 (shipment-first structure),
  R-10.8.10 (completed-shipment immutability), SP-1, SP-5;
  `INVARIANTS.md` 4 (tenant isolation), 7 (layering), 8 (ADR before
  implementation)

## Context

The completed Shipment Persistence Boundary Audit established the
following verified facts about the repository:

1. Commercial shipment/profile facts (product, origin, destination,
   quantity, unit, shipment date) exist only in frontend state and
   `sessionStorage` (`frontend/src/lib/shipments.ts` — explicitly
   "presentation metadata … never sent to the backend, never presented
   as a compliance fact").
2. `case_id` and `shipment_id` are intentionally distinct identities:
   `case_id` is the reasoning/case grouping identity carried through
   the Phase 6 reasoning result, while `shipment_id` is the shipment
   association fixed once-and-early on the workflow
   (`xportra/domain/shipment_intake.py`, `xportra/domain/compliance_workflow.py`).
3. `compliance_workflows` (migration 012,
   `migrations/012_compliance_workflows.sql`) persists workflow/process
   state only — identity (`tenant_id`, `workflow_id`, `case_id`,
   `shipment_id`), workflow `state`, evidence references, and open
   requirements. It intentionally contains no commercial profile fields,
   no verdicts, and no compliance content.
4. `exporters`, `products`, and `destination_markets` (migration 001)
   are reusable tenant-scoped master/reference data, not shipment
   instances.
5. `requirement_applicability` rows are requirement-level
   applicability/result data keyed by
   (tenant, requirement, exporter, product, destination), not shipment
   ownership.
6. Analysis/report/round/package records (migrations 008–010) are
   process outcome records, not commercial shipment facts.
7. The shipment profile directly influences compliance applicability
   (origin/destination jurisdiction in SA-6, product characteristics in
   the applicability context), yet the current client-only profile
   cannot support reliable cross-request, cross-tab, cross-device, or
   historical shipment retrieval, nor any server-side ownership
   validation.

Before this ADR, `ShipmentReference`
(`xportra/domain/shipment_intake.py`) is an identity-only triple
(tenant, shipment, case): the module docstring states "no Shipment
domain object and no shipment table exist" and that "shipment
commercial fields … belong to a future shipment-management subsystem."
`bind_shipment` therefore accepts any client-generated UUID with no
server-owned registry to validate against. `start_workflow`
(`xportra/application/workflows.py`) accepts `case_id` plus an
optional `shipment_id` UUID and nothing else; the frontend
(`frontend/src/api/workflows.ts` `StartWorkflowInput`) sends exactly
that. Workflow identity itself is server-derived and deterministic
(`uuid5` over `tenant + case + shipment` in
`ComplianceWorkflowService.begin`); that design is unchanged by this
ADR.

## Decision

Xportra AI will introduce a tenant-scoped first-class Shipment
aggregate to own commercial shipment/profile facts independently from
the compliance workflow/process state.

The aggregate owns the **facts about the shipment**; the workflow owns
the **process of assessing that shipment**. Shipment and Workflow must
not be collapsed into one entity.

```text
Tenant
  │
  └── Shipment
        │
        ├── commercial/profile facts
        │
        └── Compliance Workflow
              │
              ├── workflow state
              ├── evidence
              ├── applicability
              ├── analysis rounds
              └── assessment package
```

Why the existing entities are insufficient (each is necessary but none
owns the shipment):

- `compliance_workflows` owns workflow identity, workflow state,
  evidence references, open requirements, and process continuity. It
  must not become the owner of commercial shipment facts: adding
  product/origin/destination/quantity columns would conflate a durable
  commercial object with a process record, prevent shipment reuse
  across workflows, and force every workflow-row reader to carry
  commercial semantics.
- `exporters` is a reusable/master entity (legal identity registered
  per tenant). A shipment involves an exporter; it is not one.
- `products` is a reusable/master entity (catalog item per
  tenant/exporter). A shipment moves a quantity of a product at a
  date; it is not a catalog row.
- `destination_markets` is a reusable/master entity (per-tenant
  country/market reference). A shipment goes to a destination; it is
  not the market definition.
- `requirement_applicability` is requirement-level applicability/result
  data (one row per requirement × context join). It records outcomes
  about requirements, not ownership of the shipment that produced the
  context.
- Analysis/report/round/package records are process/result records
  (what was assessed, in which round, with which inputs). They
  reference shipment context; they do not own it.

## Detailed Design Boundary

### 1. Aggregate responsibility

A Shipment represents:

> A tenant-owned commercial shipment instance whose product, origin,
> destination, quantity, unit, and shipment date provide durable context
> for compliance processing.

The aggregate owns commercial/profile facts. The compliance workflow
owns assessment process state. Workflow state must never be duplicated
into Shipment, and shipment profile fields must never be duplicated
into `compliance_workflows`.

### 2. Proposed minimum persistence boundary

Expected columns for the future `shipments` table (exact PostgreSQL
types/constraints reconciled with existing migration conventions at
implementation time):

| Field | Purpose | Required / nullable | Commercial fact or process identifier | Used by compliance logic | Mutable after workflow binding |
|---|---|---|---|---|---|
| `tenant_id` | Ownership scope; FK to `tenants(id)` | Required | Ownership (neither) | Only as tenant scope/filter, never as a compliance input | Never — identity is immutable |
| `shipment_id` | Commercial shipment instance identity | Required | Commercial identity | Referenced (binding), not interpreted | Never — identity is immutable |
| `case_id` | Reasoning/case grouping this shipment's assessment belongs to | Required | Process identifier (grouping) | Yes — carried through reasoning, readiness, history | Never after binding — rebinding is a new workflow concern, not a shipment edit |
| `product` | Human-entered product description for the shipment | Required (v1 free text) | Commercial fact | Yes — product characteristics feed the applicability context | Editable while shipment is editable; bound/terminal handling per §5 |
| `origin_country` | Country of origin for the shipment | Required | Commercial fact | Yes — origin jurisdiction drives source selection (SA-6) | Same as `product` |
| `destination_country` | Destination country for the shipment | Required | Commercial fact | Yes — destination jurisdiction drives applicability (SA-6) | Same as `product` |
| `quantity` | Shipment quantity (numeric-as-text in the current intake) | Nullable/optional | Commercial fact | Contextual only — not a primary applicability driver today | Same as `product` |
| `unit` | Quantity unit (e.g. kg, bags) | Nullable/optional | Commercial fact | Contextual only | Same as `product` |
| `shipment_date` | Intended/actual shipment date | Nullable/optional | Commercial fact | Contextual only (no date-driven rule exists today) | Same as `product` |

No field is added merely because it appears convenient in the
frontend. Assessed and explicitly excluded from the v1 boundary:

- **Shipment reference / display string** — derived presentation
  (`product · origin → destination`, cf. `shipmentDisplayName`), not a
  persisted fact. Storing it would duplicate derivable data.
- **Weight** — no weight input exists in the current intake and no
  compliance rule consumes it. Quantity + unit covers the v1 need; a
  dedicated weight/measure field is a future product decision.
- **Exporter identity** — the current intake collects no exporter
  selection, and forcing an `exporters` FK now would invent a product
  requirement. Recorded as an open question (future FK).
- **Product master ID** — v1 product is free text; coercing it to a
  `products` FK now would break the existing intake and invent catalog
  discipline. Recorded as an open question (future FK).
- **Destination market ID** — same reasoning as product master ID;
  v1 stores the country value, not a `destination_markets` FK.
  Recorded as an open question.

Standard `created_at` / `updated_at` (via `xportra.set_updated_at()`)
follow the convention of every existing table.

### 3. Identity model

Four identities, never collapsed:

```text
Shipment:  (tenant_id, shipment_id)   — composite primary key
Shipment:  case_id                    — reasoning/case grouping, non-key reference
Workflow:  (tenant_id, workflow_id)   — existing composite primary key (migration 012)
Workflow:  references shipment_id     — existing nullable association column
           references case_id         — existing grouping column
```

- `shipment_id` identifies the commercial shipment instance.
- `case_id` remains the reasoning/case grouping identity (carried by
  reasoning results, readiness checks, and history).
- `workflow_id` identifies the compliance workflow/process and remains
  server-derived under the existing deterministic identity design
  (`uuid5` over `tenant + case + shipment`) unless a later ADR changes
  that decision. This ADR changes nothing about workflow identity.
- The workflow→shipment link stays a reference (the existing
  `compliance_workflows.shipment_id` column), resolved against the
  server-owned shipment row — not against a client assertion.

### 4. Ownership and tenant boundary

```text
tenant → shipment
```

is the fundamental ownership boundary. All Shipment reads/writes are
tenant-scoped. A `shipment_id` from a request is never sufficient by
itself; the server resolves `(tenant_id, shipment_id)` from the
authenticated tenant context before treating the shipment as
authoritative (`INVARIANTS.md` 4 holds).

Expected behavior (specified here, implemented later):

- **Unknown shipment** — `(tenant_id, shipment_id)` resolves to no row:
  fail closed (not-found; no workflow binding, no compliance use).
- **Shipment belonging to another tenant** — same-row lookup under the
  caller's tenant finds nothing: fail closed exactly as unknown, with
  no existence disclosure beyond what the error contract already
  permits.
- **Mismatched `case_id`** — shipment's `case_id` differs from the
  workflow's `case_id`: reject the binding/use (the Phase 7.2
  tenant/case re-check pattern extends to the persisted aggregate).
- **Mismatched workflow/shipment binding** — a workflow whose stored
  `shipment_id` differs from the presented shipment: reject (the
  existing no-switch rule in `bind_shipment` extends to persisted
  rows).

### 5. Shipment lifecycle

Minimum lifecycle (evaluated against the audit's `draft → bound →
terminal-read-only` suggestion — adopted with clarified semantics):

```text
draft → bound → locked
```

- `draft` — created from intake facts, not yet bound to any workflow.
  Fully editable.
- `bound` — associated with a live (non-terminal) compliance workflow.
  Profile edits are permitted only through explicit domain handling
  that invalidates or flags dependent compliance outputs (see §7);
  silent edits that leave stale analysis appearing valid are
  forbidden.
- `locked` — the bound workflow reached its terminal state
  (`assessment_package_ready`, Phase 7.5 permanent closure) or the
  shipment was explicitly closed. Read-only; corrections require a new
  shipment (or a future versioning mechanism), never mutation.

No further states are created. This lifecycle is the **shipment**
lifecycle and is distinct from the **compliance workflow** lifecycle
(`created → information_provided → evidence_pending → … →
assessment_package_ready`), which continues to live solely in the
domain workflow service and `compliance_workflows.state`. Workflow
state is not duplicated into Shipment; shipment status is not read as
workflow state.

### 6. Relationship to the existing workflow

```text
Shipment
    ↓ referenced by
ComplianceWorkflow
```

The workflow references a server-owned Shipment rather than accepting
an arbitrary client-created shipment identity as authoritative. At
`start_workflow`, the server persists (or resolves) the Shipment row
first, then binds the workflow to it. Explicitly out of scope for this
boundary change (unchanged):

- workflow transitions and their owning service;
- workflow ID derivation;
- workflow state storage;
- any duplication of shipment profile fields into
  `compliance_workflows`.

### 7. API boundary (design proposal only — not implemented)

The existing `POST /compliance/workflows/start` interaction accepts
identifiers only (`{ case_id, shipment_id? }`). The implementation
phase should evolve it so the server can receive the already-collected
shipment profile and persist it. The frontend must **not** require a
new shipment-creation UI as part of the first implementation — the
existing New Shipment form already collects the profile; only the
transport changes.

Conceptual direction (exact schema subject to implementation
validation against existing DTO conventions in
`xportra/application/dtos.py` and `xportra/api/schemas.py`):

```text
POST /compliance/workflows/start

{
    case_id,
    shipment_id,
    shipment: {
        product,
        origin_country,
        destination_country,
        quantity,
        unit,
        shipment_date
    }
}
```

The ADR states explicitly: field naming, required/optional
partitioning, and error mapping must be reconciled with existing DTO
conventions at implementation time; this sketch is not the schema.

### 8. Compliance input resolution (intended precedence)

For future compliance operations (`determine_applicability`,
`run_analysis`, and their successors):

```text
Explicit validated request input
        ↓ (absent)
server-owned Shipment profile
        ↓ (absent and required)
error if required information is unavailable
```

Once a shipment is bound, arbitrary client-supplied profile data must
not silently override the server-owned Shipment. Explicit per-request
overrides, if ever allowed, require their own decision and audit
treatment. Not implemented by this ADR.

### 9. Mutation rules

Shipment profile fields (`product`, `origin_country`,
`destination_country`, `quantity`, `unit`, `shipment_date`) may be
edited while the shipment is in an editable lifecycle state (`draft`,
or `bound` via explicit domain handling). Once bound to a workflow,
mutation requires explicit domain handling such that stale compliance
analysis cannot silently remain valid — i.e. an edit to a bound
shipment must either trigger re-analysis/invalidation through the
existing workflow transitions or be rejected. Once terminal
(`locked`), shipments are read-only (R-10.8.10, Phase 7.5).

This ADR does not redesign workflow transitions to implement
re-analysis; it records the requirement that the implementation phase
must address the edit→staleness relationship.

### 10. Historical integrity

Shipment persistence is necessary for historical integrity because a
completed assessment must remain associated with the shipment context
that produced it. Today that context lives only in `sessionStorage`
and in-memory React state: a cleared tab, a second device, or any
later audit cannot reconstruct what was assessed, for whom, from
where, to where, and when. Server-owned shipment rows bound to
workflows and referenced by rounds/packages close that gap.

Whether preserving historical values requires immutable shipment after
finalization (the `locked` state above), row versioning, or a later
snapshot mechanism is **not decided here** — recorded as a future
architectural question (see Open Questions). No snapshot architecture
is prescribed.

## Consequences

- A future implementation phase introduces migration 013 with a
  tenant-scoped `shipments` table (§Migration Implications), a domain
  Shipment object, repository/persistence support, application-service
  binding, and the evolved `start` API — each reconciled with existing
  conventions. Nothing in this ADR authorizes starting that work; it
  only fixes the boundary the work must honor.
- `bind_shipment`'s structural weakness (accepting an arbitrary UUID
  with no registry) becomes fixable: binding resolves against the
  shipment registry.
- Frontend intake needs no new UI in the first implementation; the
  device-local registry (`lib/shipments.ts`) remains display metadata
  until the server owns shipments, at which point its role shrinks to
  cache/fallback (a later decision).
- `compliance_workflows` stays profile-free; master tables stay
  instance-free; workflow identity and transitions are untouched.
- `INVARIANTS.md` 4 is strengthened (ownership becomes checkable);
  invariants 7 and 8 are satisfied by construction (no handler logic,
  ADR-first).

## Alternatives Considered

- **A. Put shipment fields in `compliance_workflows`.** Rejected: it
  conflates commercial facts with workflow process state, provides no
  reusable shipment aggregate (one shipment → potentially several
  workflows is unrepresentable), and loads every workflow read with
  commercial semantics.
- **B. Reuse `products`, `exporters`, or `destination_markets` as the
  shipment.** Rejected: these are reusable master/reference entities
  (catalog, legal identity, market definition), not per-instance
  shipment records carrying quantity/unit/date. Pressing instance data
  into them corrupts their master semantics.
- **C. Keep the shipment profile only in `sessionStorage`.**
  Rejected: client-only storage cannot provide durable server-owned
  history, cross-device access, reliable compliance context, or
  ownership validation — the exact gaps the audit verified.
- **D. Introduce a dedicated tenant-scoped Shipment aggregate (this
  ADR).** Selected: it matches the identified requirements
  (shipment-first structure R-10.8.8, completed-shipment immutability
  R-10.8.10, tenant isolation, deterministic applicability inputs) and
  the existing architecture (identity-only `ShipmentReference` already
  names the seam; migration 012 already keeps profile fields out of
  the workflow row) with the smallest new surface.

## Security / Tenant Considerations

- Before this aggregate: `shipment_id` is a client-generated UUID
  accepted by `bind_shipment` with no server-side existence or
  ownership check — any well-formed UUID binds. UUID unguessability is
  not authorization and is not claimed as such.
- After this aggregate: `(tenant_id, shipment_id)` identifies a
  server-owned record resolved under the authenticated tenant context;
  cross-tenant presentation fails closed as not-found.
- Tenant isolation (`INVARIANTS.md` 4) and the R-10.1 tenant-isolation
  matrix extend to shipment reads/writes/binds; the implementation
  phase must add the corresponding regression tests.
- No secrets, raw evidence bytes, or provider internals touch the
  shipment aggregate; profile fields are business facts with no
  special sensitivity beyond normal tenant confidentiality.

## Migration Implications

- Implementation is expected to introduce **migration 013** creating
  `xportra.shipments` with at minimum: `tenant_id` (FK to
  `tenants(id)`), `shipment_id`, `case_id`, `product`,
  `origin_country`, `destination_country`, `quantity` (nullable),
  `unit` (nullable), `shipment_date` (nullable), `status`
  (`draft | bound | locked`), `created_at` / `updated_at` (standard
  trigger), composite `PRIMARY KEY (tenant_id, shipment_id)`, plus a
  deterministic `.down.sql` rollback. Exact PostgreSQL types, check
  constraints, and secondary indexes are reconciled with existing
  migration conventions (001/010/011/012) at implementation time.
- No migration is written by this ADR. No repository, service, schema,
  frontend, transition, or test file is changed by this ADR.

## Open Questions

Unresolved questions that do **not** block the first implementation
unless the implementation phase finds otherwise:

- OQ-S1: Should `case_id` eventually become a first-class persisted
  aggregate rather than a grouping identifier carried by reference?
- OQ-S2: Is shipment profile versioning eventually needed, or is
  `locked`-immutability sufficient for the product's audit needs?
- OQ-S3: Should `product` eventually become a foreign key to the
  existing product master (and what catalog discipline would that
  impose on intake)?
- OQ-S4: Should exporter identity eventually become a foreign key to
  `exporters`, and which actor captures it at intake?
- OQ-S5: Do historical assessments require immutable shipment
  snapshots distinct from the live row (vs. relying on `locked`)?
- OQ-S6: Do shipment deletion/archive semantics need dedicated rules
  beyond the `locked` state (cf. R-10.4.3 evidence archival precedent)?

## Linked Requirements / Tasks

- Requirements: `REQUIREMENTS.md` R-10.8.8, R-10.8.10, SP-1, SP-5, SA-6
- Prior evidence: Shipment Persistence Boundary Audit (starting
  evidence for this ADR; no separate audit document found in the
  repository — findings restated in Context above and verified against
  cited source files)
- Follow-on: shipment persistence implementation (migration 013 and
  associated domain/application/API work — not started, to be
  scheduled via `tasks/` with its own `REQUIREMENTS.md` scope)
