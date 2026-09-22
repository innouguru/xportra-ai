# ADR-0001: Deterministic Applicability Logic Is Authoritative Over LLM Reasoning

- **Status:** Accepted
- **Date:** 2026-09-19
- **Linked requirements:** SP-1, NG-6 (`REQUIREMENTS.md`); Invariant 1
  (`INVARIANTS.md`)
- **Linked task:** `tasks/active/phase-0-2-project-contract.md`
  (completed record: `tasks/completed/phase-0-2-project-contract.md`)

## Context

Xportra AI helps Nigerian agricultural exporters understand which export
requirements apply to them. Deciding the applicable regulatory universe is
the highest-stakes determination in the system: an omitted requirement
creates false confidence, and an invented one creates false burden.
LLM outputs are probabilistic and can hallucinate; they cannot by
themselves guarantee completeness, correctness, or auditability of the
applicable-requirements set.

## Decision

Which requirements apply is determined by explicit, deterministic
business/domain logic. That logic is the authority for the regulatory
universe. The LLM may explain applicability outcomes, summarize
requirements, and assist with evidence interpretation, but it must never
be the decision procedure for what applies.

## Alternatives Considered

1. **LLM decides applicability (rejected):** flexible but non-deterministic,
   un-auditable, and prone to inventing or omitting requirements —
   directly violates NG-5/NG-6 and Invariant 1.
2. **Hybrid with LLM override (rejected):** allowing the LLM to extend or
   override the deterministic set reintroduces the same failure mode with
   weaker guarantees; any LLM-suggested addition must instead become a
   proposal for explicit rule curation, not a silent decision.
3. **Deterministic rules authoritative, LLM explanatory (chosen):**
   auditability and stability from rules; readability and assistance from
   the model. Each layer does what it is reliable for.

## Consequences

- Applicability rules must be versioned, tested (including regression
  coverage), and traceable to their sources — future Phase 3 work.
- Gaps or conflicts in authoritative information must surface as explicit
  unknowns, never as invented requirements (NG-5).
- Retrieval, reasoning, and decision-support layers consume the
  deterministic applicable set; they do not redefine it.
- Changes to this decision require a superseding ADR.
