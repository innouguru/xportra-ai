# INVARIANTS.md — Architectural Invariants

> Invariants currently established for Xportra AI. These hold across all
> phases unless explicitly amended via an ADR. Violations block task
> completion.

1. **Deterministic applicability logic must not be replaced by an LLM.**
   Where deterministic rules govern applicability, the LLM may explain or
   assist but must never become the decision procedure.
2. **Regulatory/source traceability must be preserved.** Every compliance
   conclusion must be traceable to its regulatory or authoritative source.
3. **Evidence must remain traceable to its source.** Every piece of evidence
   must retain a link to the document and location it came from.
4. **Tenant isolation must be enforced when multi-tenant functionality is
   introduced.** No cross-tenant data access or leakage is permitted.
5. **Metadata filtering must not be bypassed where required.** Where
   retrieval or reasoning depends on metadata scoping (e.g., tenant,
   jurisdiction, document type), filters must be applied, not skipped.
6. **Ingestion integrity must be preserved.** Ingested content must not be
   silently altered, truncated, or misattributed; provenance and versioning
   must be retained.
7. **Business logic must not be moved into API handlers merely for
   convenience.** Domain/compliance logic belongs in its proper layer.
8. **Architectural changes require an ADR.** Structural, boundary, data-flow,
   storage, or cross-cutting changes must be recorded in `docs/decisions/`
   before implementation.
9. **Tests must not be bypassed to make a task appear complete.** No
   skipping, faking, weakening, or deleting tests to force a pass.
