# UI / Product Architecture — Xportra AI Exporter Workflow

> Specification only. No frontend code, no backend changes.
> Every endpoint, state, role, and DTO field below is verified
> against the implemented API (`xportra/api/`), application
> DTOs (`xportra/application/dtos.py`), and the Phase 6/7
> domain contracts. Anything the backend cannot do is listed
> under §11 instead of invented.

## 1. Product workflow

The single central journey — **Shipment → Requirements →
Evidence → Analysis → Review → Additional Evidence /
Re-analysis → Final Assessment**:

```text
1.  Create workflow/shipment          §2 Screen 1
2.  Provide shipment information      §2 Screen 2
3.  See context/applicability status  §2 Screen 3
4.  Provide/upload supporting evidence§2 Screen 4  (reference-based, §4)
5.  See missing/insufficient evidence §2 Screen 5
6.  Run analysis                      §2 Screen 6
7.  Review findings + provenance      §2 Screen 7
8.  Supply additional evidence        §2 Screen 8
9.  Re-run analysis                   §2 Screen 6 (repeat)
10. Review the final assessment       §2 Screen 7 (latest round)
11. Explicitly finalize the package   §2 Screen 9
12. View package/report/history       §2 Screen 10
```

Steps 8→6→7→11 may repeat; step 11 executes exactly
once per workflow (terminal, §7). The RAG machinery
(`POST /rag/query`) supports analysis internally and
must NOT become a user-facing chatbot screen.

## 2. Screen inventory

Conventions used below: **Goal** (user intent), **APIs**
(verified endpoints), **Data** (response fields shown),
**Actions**, **States** (loading/empty/error), **Perms**
(owner-only actions marked ★; everything else is
member-visible), **Nav** (where the screen links).

### Screen 1 — New shipment / workflow

- Goal: start a compliance case for a shipment.
- APIs: `POST /compliance/workflows/start` (201) with
  `{case_id, shipment_id?}`; optional exporter/product/
  destination lookups via `GET /exporters/{id}`,
  `GET /products/{id}`, `GET /destination-markets/{id}`
  to pick identifiers the tenant already owns.
- Data: returned workflow record (held client-side —
  the server keeps no session, §11.2) + summary
  (`workflow_id`, `state`, `is_closed`).
- Actions: ★ create workflow (owner-only).
- States: loading on submit; error on 400/422
  (malformed IDs), 401 (no auth), 403 (member
  attempting creation).
- Nav: → Screen 2 on success.

### Screen 2 — Shipment information

- Goal: record what the shipment is/facts of the case.
- APIs: `POST /compliance/workflows/provide-information`
  then optionally `note-evidence-pending` (records travel
  in-body; each response returns the updated record the
  UI must retain).
- Data: summary `state` progression
  `created → information_provided → evidence_pending`.
- Actions: ★ advance information steps.
- States: validation errors inline; 409
  `invalid_transition` if the workflow already moved
  past the step (re-fetch via Screen 6 status read).
- Nav: ↔ Screen 1 (back), → Screen 3.

### Screen 3 — Applicability status

- Goal: see which requirements apply — deterministic
  truth, not AI judgment.
- APIs: `POST /compliance/workflows/record-applicability`;
  `POST /compliance/assessments/applicability` with
  `{requirements[], exporter?, product?, destination?,
  actor_role?}` for the per-requirement breakdown.
- Data: per-requirement `outcome` ∈ {`applicable`,
  `not_applicable`, `unknown`} + `reason`; counts.
- Presentation rule: `unknown` renders as
  **"Not yet determined — [reason]"**, never as failed;
  `not_applicable` rows collapse into a muted section.
- Actions: ★ record the outcome, → evidence.
- Nav: → Screen 4.

### Screen 4 — Evidence intake

- Goal: register supporting evidence for the case.
- APIs: `POST /compliance-evidence` (or
  `/with-requirements`) then
  `POST /compliance/workflows/supply-evidence`
  with `{workflow, evidence_id, requirement_id?}`.
- Data: evidence record (`id`, `document_title`,
  `document_type`, `file_reference_or_uri`, `status`);
  workflow `supplied_evidence_ids`.
- **Constraint (§11.1): no file-upload endpoint exists.**
  The form collects title + type + URI/reference
  (e.g. storage URL, registry number), never raw bytes.
  Member role may record and associate evidence.
- Actions: record evidence (member-allowed), ★ supply
  to workflow, associate evidence↔requirement.
- Nav: → Screen 5.

### Screen 5 — Evidence gaps

- Goal: see what is missing or insufficient.
- APIs: `POST /compliance/assessments/case-readiness`
  (`readiness_state` ∈ {`ready`, `partially_ready`,
  `not_ready`}, `gaps[]` with `kind` ∈
  {`applicability_undetermined`,
  `assessment_incomplete`, `evidence_absent`,
  `evidence_insufficient`, `knowledge_uncited`,
  `explanation_absent`,
  `satisfying_evidence_unestablished`});
  `POST /compliance/workflows/status`
  (`open_requirements`, `supplied_evidence_ids`).
- Presentation rule: missing/insufficient evidence
  renders as **"Still needed"**, never as
  non-compliant. `not_ready` means "cannot enumerate
  the requirement set yet", not failure.
- Actions: → supply more (Screen 4/8), → run
  analysis when ready enough.
- Nav: → Screen 6.

### Screen 6 — Run / re-run analysis

- Goal: execute one analysis pass (owner-only, ★).
- APIs: `POST /compliance/workflows/analyze` with
  `{workflow, cases[], mode?, max_context_chars?,
  top_k?, decision_summary?}` → updated record +
  report DTO. Re-run is the same endpoint; the state
  machine routes passes (round counter, report IDs).
- Data: `report_id`, per-round `round_index`,
  `analysis_ids`, `trace_ids`.
- States: long loading state (retrieval + LLM);
  503 `infrastructure_failure` (retryable) and 503
  `rag_not_configured` (deployment gap, §11.3);
  409 on wrong state.
- Nav: → Screen 7 after each run.

### Screen 7 — Findings review

- Goal: understand each requirement's finding and its
  provenance. Read-only for members.
- APIs: report DTO already returned by analyze; or
  `GET /compliance/reports/{report_id}`;
  `POST /compliance/workflows/submit-for-review` (★)
  to mark review done.
- Data per finding: requirement text, `applicability`,
  `assessment` ∈ {`satisfied`, `not_satisfied`,
  `unknown`}, `explanation`, supporting vs
  conflicting evidence, `sources`,
  `missing_information[]`, `uncertainty` ∈
  {`determined`, `uncertain`, `unknown`} +
  explanation, `evidence_sufficiency` ∈ {`supported`,
  `insufficient`, `missing`, `unknown`},
  `contradiction_state` ∈ {`none`, `present`}.
- Presentation rules (§5): `unknown` → **"Needs
  attention"**; `not_satisfied` → requirement-level
  status only; contradiction `present` → show both
  sides, never resolve; NO overall score, verdict,
  percentage, or ranking anywhere (the backend
  exposes none).
- Actions: → request additional evidence
  (`request-additional-evidence` with
  `requirement_ids`, ★) → Screen 8; → finalize
  when satisfied with the latest round (Screen 9).
- Nav: ↔ Screen 8 (loop), → Screen 9.

### Screen 8 — Additional evidence

- Goal: close gaps flagged in review.
- APIs: same as Screen 4 (record + supply) against
  the `additional_evidence_requested` /
  `reanalysis_required` states; then Screen 6 re-run.
- Data: updated `supplied_evidence_ids`; new round
  appended (prior rounds preserved, distinguishable
  by `round_index`/`report_id`).
- Nav: → Screen 6 → Screen 7.

### Screen 9 — Finalize (explicit action)

- Goal: produce the terminal assessment package —
  a deliberate, single, irreversible user action.
- APIs: `POST /compliance/workflows/finalize`
  (201) with the reviewed workflow record. The
  server resolves the latest stored result itself;
  readiness/staleness/terminal rules enforced
  server-side (`not_ready` reasons render inline
  from `error.details.reasons[]`).
- UX requirements: confirm dialog stating finality;
  only enabled from `review_required` on the latest
  round; 409 `stale_analysis` → force re-review of
  the current round (never auto-fix).
- Actions: ★ finalize (owner-only). No reopen, no
  versioning, no "finalize v2" affordance may exist.
- Nav: → Screen 10.

### Screen 10 — Package, report & history

- Goal: view and share the finished artifact. Read-only.
- APIs: `POST /compliance/workflows/package`
  (`FinalPackageDTO`: identities, `state`,
  `round_count`, `open_requirements`, full `report`,
  carried `decision_summary`);
  `GET /compliance/reports/{report_id}`;
  `POST /compliance/workflows/history`
  (`entries[]` kinds: `workflow_created`,
  `shipment_bound`, `evidence_supplied`,
  `analysis_completed`, `final_package_ready`);
  `POST /compliance/workflows/is-closed`.
- Data: package banner ("Final — terminal, cannot be
  reopened"), unresolved `open_requirements` shown as
  outstanding items (not failures), full findings,
  timeline from history entries.
- Nav: terminal screen (links back to Screen 1 for a
  new shipment only).

## 3. Workflow-state presentation map

Backend states are process-only; the UI labels them
without reinterpreting regulatory truth:

| Backend `state` | UI label | Meaning shown |
|---|---|---|
| `created` | Draft | Case opened, nothing recorded |
| `information_provided` | Shipment details added | Facts recorded |
| `evidence_pending` | Awaiting evidence | Nothing judged yet |
| `applicability_determined` | Requirements mapped | See Screen 3 |
| `analysis_available` | Analysis ready to review | See Screen 7 |
| `review_required` | In review | Awaiting user decision |
| `additional_evidence_requested` | More evidence requested | Listed requirement IDs |
| `reanalysis_required` | Re-analysis needed | Run again (Screen 6) |
| `assessment_package_ready` | Final — closed | Terminal (§7) |

Orthogonal dimensions (never merged into one badge):
workflow progress (above) · evidence presence (Screen
5) · applicability per requirement (Screen 3) ·
assessment per requirement (Screen 7) · readiness
`ready bool + reasons[]` (Screen 9 inline).

Forbidden collapses: `missing evidence` ≠
non-compliant; `unknown` ≠ failed; `not_ready`
(readiness/process) ≠ unfavorable outcome;
`contradiction: present` ≠ error (show both sides).

## 4. Evidence UX contract

- Required/supplied/missing/insufficient all derive
  from `case-readiness` gaps + `open_requirements` +
  `supplied_evidence_ids` — three corroborating
  sources, same truth.
- Evidence↔requirement links shown from association
  records and `requirement_id` on supply.
- Post-re-analysis evidence appends; history shows
  each supply as its own entry; rounds never rewrite.
- Uploads are URI/reference forms (§11.1); show the
  stored URI back, never a file preview from bytes
  the API cannot serve.

## 5. Analysis UX contract

Per finding show exactly the DTO fields (§2/Screen 7):
text, applicability, assessment, explanation,
supporting/conflicting evidence, sources,
missing_information, uncertainty (+ explanation),
sufficiency (+ explanation), contradiction state.
Trace IDs may link to history entries; chain-of-
thought and model internals are not exposed by the
API and must not be reconstructed client-side.
Report counts may back small summary chips
(`satisfied N · attention N`), never a verdict.

## 6. Finalization UX contract

Review (Screen 7, repeatable, non-terminal) vs
Finalize (Screen 9, once, terminal) are visually
distinct actions. The finalize control states the
consequence ("Creates the final package. This cannot
be undone or reopened."). After 201, the UI shows
the terminal banner and disables every mutating
control for that workflow (any attempt returns 409
`terminal_workflow`). No reopen/version UI exists
by design.

## 7. API contract matrix

Legend: ★ owner-only (member → 403
`permission_denied`). Tenant always from auth context;
bodies never carry tenant authority.

| UI action | Method + endpoint | Request | Response | Errors → workflow effect |
|---|---|---|---|---|
| Create workflow | POST `/compliance/workflows/start` ★ | `{case_id, shipment_id?}` | 201 record + summary | 400/422 bad IDs; 401; 403 member |
| Shipment info | POST `.../provide-information` ★ | `{workflow}` | 200 record + summary | 409 `invalid_transition` (already past) |
| Mark evidence pending | POST `.../note-evidence-pending` ★ | `{workflow}` | 200 record + summary | 409 invalid_transition |
| Record applicability | POST `.../record-applicability` ★ | `{workflow}` | 200 record + summary | 409 invalid_transition |
| Check applicability | POST `/compliance/assessments/applicability` | `{requirements[], exporter?, product?, destination?, actor_role?}` | 200 outcomes+reasons | 400 bad input |
| Record evidence | POST `/compliance-evidence` (+`/with-requirements`) | `{document_title, document_type, file_reference_or_uri, …}` | 201 evidence record | 400/422; member allowed |
| Link evidence↔req | POST `/compliance-evidence/{id}/requirements` | `{requirement_id}` | 201 association | 404 unknown evidence; member allowed |
| Supply evidence | POST `.../supply-evidence` ★ | `{workflow, evidence_id, requirement_id?}` | 200 record + summary | 404 unknown evidence; 409 wrong state |
| Readiness/gaps | POST `/compliance/assessments/case-readiness` | `{cases[]}` | 200 `readiness_state`, `gaps[]` | 400 bad cases |
| Status | POST `.../status` | `{workflow}` | 200 summary | 403 cross-tenant (`tenant_mismatch`) |
| Run/re-run analysis | POST `.../analyze` ★ | `{workflow, cases[], mode?, budget?, top_k?, decision_summary?}` | 200 record + report | 409 wrong state; 503 infra/unwired |
| Submit for review | POST `.../submit-for-review` ★ | `{workflow}` | 200 record + summary | 409 invalid_transition |
| Request more evidence | POST `.../request-additional-evidence` ★ | `{workflow, requirement_ids[]}` | 200 record + summary | 422 empty list; 409 |
| History | POST `.../history` | `{workflow}` | 200 entries[] | 403 cross-tenant |
| Closure check | POST `.../is-closed` | `{workflow}` | 200 `{workflow_id, is_closed}` | — |
| Finalize | POST `.../finalize` ★ | `{workflow}` | 201 record + package | 409 `not_ready` (reasons in details), `stale_analysis`, `terminal_workflow`; 404 unstored |
| Read package | POST `.../package` | `{workflow}` | 200 package | 404 not finalized |
| Read report | GET `/compliance/reports/{report_id}` | path ID | 200 report | 404 unknown; 422 malformed |
| Lookup master data | GET `/exporters/{id}`, `/products/{id}`, `/destination-markets/{id}`, `/compliance-evidence/{id}`, `/certifications-permits-licenses/{id}` | path ID | 200 record | 404 unknown (non-leaking) |
| Master-data creates | POST `/exporters`, `/products`, `/destination-markets`, `/certifications-permits-licenses` | resource fields | 201 record | owner-only; 403 member |

Error body everywhere: `{"error": {"code", "message",
"details"?}}`; readiness reasons arrive as
`details.reasons[]` (`{code, detail}`) for inline
rendering. The client retains the latest workflow
record per screen transition (server holds no
session).

## 8. Authentication/session assumptions

- Production: `Authorization: Bearer <Supabase JWT>`;
  server verifies, resolves membership, optional
  `X-Xportra-Tenant-ID` selects among the user's
  tenants (rejected if not a member). No auth →
  401 `authentication_required` (+ `WWW-Authenticate:
  Bearer`); unknown tenant selection → 403/404
  without leaking other tenants' existence.
- Non-production only: `X-Development-Tenant-ID: <uuid>`
  yields a synthetic owner context (disabled in
  production → 503). The UI dev harness may use it;
  production builds must not send it.
- Actor identity: Bearer subject UUID, else `None`;
  informational only — tenant/role decisions never
  depend on it.
- Sessions: none server-side. The SPA holds the JWT
  (memory preferred over localStorage), the active
  tenant selection, role (from a lightweight
  who-am-I? — see §11.4), and the current workflow
  record(s). 401 → re-authenticate; 403 → show
  permission messaging, never retry as another tenant.
- Roles are fixed: `owner` (everything) vs `member`
  (reads + evidence record/associate only). No
  role management UI exists.

## 9. Responsive/product considerations

- Desktop (primary): three-column review layout —
  journey stepper left, findings center, provenance/
  gaps rail right; tables for applicability/gaps.
- Tablet: stepper collapses to a top progress bar;
  provenance rail becomes expandable rows.
- Mobile: single-column stepped flow (one screen =
  one journey step), sticky primary action
  (Analyze / Finalize), timeline as vertical list.
- Every mutating action is a full-screen-blocking
  request state with retry; analysis runs show
  progress + cancellability is NOT assumed (no
  cancel endpoint — navigation away is safe, the
  record persists client-side for resume).
- Product anchor: a persistent journey stepper
  (the 12-step spine in §1) on every screen — the
  workflow, not decoration, is the navigation.

## 10. UI information architecture

```text
Shipments (list — client-held records, §11.2)
└── Shipment → Workflow
    ├── Overview (status, stepper, gaps summary)
    ├── Requirements (Screen 3)
    ├── Evidence (Screens 4+5+8)
    ├── Analysis (Screens 6+7, per-round tabs)
    └── Package (Screens 9+10, terminal)
Tenant settings (tenant display, role display, sign-out)
```

No admin dashboard, no RAG playground, no generic
CRUD browser beyond the master-data pickers in
Screen 1. The primary action on every screen
advances the journey spine.

## 11. Backend capabilities the UI must NOT assume

1. **File upload.** No multipart/bytestring endpoint
   exists; evidence intake is title/type/URI
   reference forms. (Needs a storage-backed upload
   feature + endpoint before any "Upload PDF" button.)
2. **Server-side workflow listing/resume.** No list
   or get-by-ID workflow endpoint exists; the UI must
   retain full workflow records client-side (e.g.
   local list of in-flight records). Bookmarking needs
   the record, not just an ID.
3. **Readiness pre-check endpoint.** No standalone
   readiness read exists; readiness is learned from
   finalize 409 details (or the history projection).
4. **Role introspection.** No who-am-I/role endpoint
   is defined; the UI learns role implicitly (403 on
   owner-only actions) until one is added.
5. **Notifications, dashboards, analytics, multi-case
   comparison.** None exist; counts come from report
   DTOs only.
6. **Reopen/versioning.** Terminal is permanent by
   domain invariant; the UI must not offer it.

## 12. Frontend implementation prerequisites

1. API base URL + Supabase JWT issuance flow wired
   (production) or dev-tenant header harness (local).
2. Tenant selector bound to `X-Xportra-Tenant-ID`
   semantics (membership-validated server-side).
3. Client workflow-record store (retain/replace per
   response; survive reload for resume).
4. Component kit for the five state vocabularies
   (§3) with the forbidden-collapse rules as unit
   tests.
5. Contract tests against OpenAPI for the §7 matrix
   (endpoint, shape, error codes).
6. Accessibility + responsive shells per §9 before
   journey wiring.

## 13. Result / Decision / Outcome

- **Result:** a complete, backend-verified UI
  contract: 10 screens over the 12-step journey,
  role model, state vocabularies, evidence/analysis/
  finalization UX rules, full API matrix, auth
  assumptions, responsive IA, and six documented
  backend gaps.
- **Decision:** frontend implementation may proceed
  strictly within this contract; any screen or
  control not traceable to §7 requires a backend
  task first. No backend change is required to start.
- **Outcome:** the next genuine task is UI
  implementation scaffolding (framework choice,
  auth/session shell, record store, journey
  stepper) — a build task, not a spec task.
