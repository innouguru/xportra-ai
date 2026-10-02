# ROADMAP.md — Approved Development Phases

> Status reconciled 2026-09-27 (post-Phase-10 audit):
> checkboxes below reflect the actual repository state
> through Phase 10.5, cross-checked against phase
> documents, completed task records, and
> `CURRENT_STATE.md` verification. A phase is marked
> complete only where those sources agree. No future
> phase is scoped: the next phase may start only when
> its scope is defined in `REQUIREMENTS.md` and
> scheduled via `tasks/`.

- [x] **Phase 0 — Agent Harness & Project Foundation** (complete)
- [x] **Phase 1 — Core Domain & Database** (complete per
  `CURRENT_STATE.md` and phase docs 1.1–1.10; only
  partial task-record retention — see note below)
- [x] **Phase 2 — Knowledge Ingestion** (complete per
  `CURRENT_STATE.md` and phase docs 2.1–2.9)
- [x] **Phase 3 — Deterministic Applicability Engine** (complete
  per `CURRENT_STATE.md` and phase docs 3.0–3.9)
- [x] **Phase 4 — Document Intelligence & Evidence Matching**
  (complete per `CURRENT_STATE.md` and phase docs 4.0–4.5)
- [x] **Phase 5 — Retrieval & RAG** (complete 2026-09-23:
  RAG retrieval, generation & validation, Phases
  5.1–5.16 verified; live gates recorded NOT EXECUTED —
  see `CURRENT_STATE.md`)
- [x] **Phase 6 — Compliance Reasoning & Decision Support**
  (complete per `CURRENT_STATE.md` and phase docs 6.1–6.6)
- [x] **Phase 7 — User Workflow** (COMPLETE and closed,
  including 7.5 permanent closure)
- [x] **Phase 8 — API & Application Integration** (complete
  through 8.5, per phase docs and task records)
- [x] **Phase 9 — Frontend Workspace** (complete through
  redesign Pass C, per phase docs and 157 frontend
  tests. Historical label note: this slot was originally
  titled "Evaluation & Reliability"; what was actually
  approved and built here is the exporter frontend
  workspace. No evaluation-harness phase was ever
  scoped or built.)
- [x] **Phase 10 — Production Hardening & Evidence Upload**
  (complete 2026-09-27: 10.1 security/configuration
  hardening; 10.2 conversational backend foundation;
  10.3 upload boundary scope; 10.4 upload backend;
  10.5 upload UX. Historical label note: this slot was
  originally titled "Production Hardening" only; see
  `REQUIREMENTS.md` R-10.1/R-10.2/R-10.4/R-10.5 for
  the approved scope actually built.)

Note on task-record retention: completed task files for
Phase 1 sub-phases were never filed under
`tasks/completed/`; Phase 1 completion is recorded in
`CURRENT_STATE.md` and phase docs 1.1–1.10. Stale
active-dir mirrors were reconciled on 2026-09-27
(see commit history). This note records the gap rather
than inventing records.

- [ ] **Phase 10.8 — UI/UX Redesign** (requirements
  approved 2026-09-28: `REQUIREMENTS.md` R-10.8
  with binding `ADR-0012`. Docs-only — no
  implementation started. Subtasks defined but not
  scheduled: 10.8A Redesign foundation, 10.8B
  Application shell, 10.8C Dashboard, 10.8D New
  Shipment, 10.8E Shipment Workspace, 10.8F
  Document Verification, 10.8G View Shipments +
  Historical Report, 10.8H Public Landing Page,
  10.8I Settings / Notifications / Responsive,
  10.8J Accessibility / Visual QA. 10.8A
  Redesign foundation complete 2026-09-28
  (frontend tokens/theme/primitives only).
  10.8B Application shell complete 2026-09-28
  (frontend shell + two routes only; no
  product pages).   10.8C Dashboard complete
  2026-09-28 (frontend resumption workspace;
  real registry data; no analytics). 10.8D New
  Shipment complete 2026-09-28 (frontend
  intake; existing creation boundary; no draft
  autosave by guardrail). 10.8E Shipment
  Workspace complete 2026-09-28 (frontend
  briefing workbench; real record/report
  data; 10.8F drawer seam). 10.8F Document
  Verification complete 2026-09-28 (frontend
  upload/link/finding/preview; nothing
  invented). 10.8G View Shipments + History
  complete 2026-09-28 (frontend archive +
  read-only report; no PDF boundary). 10.8H
  Public Landing Page complete 2026-09-28
  (frontend public route; dedicated chrome;
  R-10.8.12 copy). 10.8A.1 Typography
  correction complete 2026-09-28 (canonical
  scale only; architecture unchanged). 10.8I
  Settings / Notifications / Responsive
  complete 2026-09-28 (utility surface +
  minimal integration; no redesigns). 10.8J
  Accessibility / Visual QA complete
  2026-09-28 (audit + 3 corrections; no
  redesign). Phase 10.8 redesign complete —
  ready for final human visual review.)

No implementation subtask beyond the above is
started. Detailed scope for any future work will
be recorded in `REQUIREMENTS.md` and decomposed
into task files under `tasks/` when approved.
