# Phase 10.7A — Public Landing Page & Application Information Architecture

> Implemented 2026-09-27 under `REQUIREMENTS.md` R-10.7A.
> Frontend-only product/UX restructuring. No backend,
> domain, compliance, API-contract, tenant-isolation,
> or deterministic-semantics change. Task record:
> `tasks/completed/phase-10-7a-product-information-architecture.md`.

## 1. What changed and why

The frontend exposed internal workflow stages as if
they were user concepts, and started at a technical
case-ID form. It now has a commercial entry point and
four shipment concepts. Every workflow capability
remains reachable: established screens stay mounted
as deep links, and the restructuring composes —
never rewrites — their components.

## 2. Public entry point

- `/` is a new public `LandingPage`: product summary,
  how-it-works journey, exporter audience, resources —
  all copy derived from already-implemented behavior.
  No customer numbers, certifications, partnerships,
  guarantees, or statistics are claimed anywhere.
- Primary CTA `Start a shipment` → `/start`;
  secondary `See how it works` → `#how-it-works`.
- Without an active shipment, the shell shows the
  public site map (Product, How It Works, For
  Exporters, Resources) plus Sign in and Start a
  shipment — no workflow concepts leak.

## 3. Authenticated navigation

With an active shipment the shell offers Overview,
Shipments, Documents, Requirements, Assessment, plus
secondary Ask Xportra (workspace-provided slot) and
Settings. Internal stages (information, gaps,
additional evidence, analysis runs, findings review,
final review, reports, history) are no longer
top-level destinations.

## 4. Shipment workspace

- Identity hero leads with the remembered human
  profile (Origin → Destination, product); system
  identifiers stay in the existing disclosure.
- Contextual tabs: Overview, Documents, Requirements,
  Assessment. Established screens persist under a
  Details group (shipment details, all shipments,
  latest report, history).
- Overview is the command center: identity, state,
  a derived Next action, requirements/documents/
  rounds summaries, attention items, then areas.

## 5. New shipment

The form collects Product, Origin, Destination
(required) plus Quantity, Unit, Shipment date
(optional). `case_id`/`shipment_id` UUIDs are
generated behind the form; the profile is remembered
on-device with the returned workflow (`lib/shipments.ts`,
sessionStorage, validated shape, corrupt content
ignored). The profile is display metadata only —
never sent to the backend, never a compliance fact.

## 6. Documents

One `DocumentsPage` with tabs composing the
unchanged Evidence, Gaps, and AdditionalEvidence
screens: Documents (supplied, processing, upload,
download), Needed (readiness gaps), Requested
(request/supply loop). Upload, processing, gap, and
download behavior is intact.

## 7. Requirements and Assessment

- Requirements unchanged: status, provenance,
  applicability semantics, evidence relationships,
  uncertainty, and actions preserved.
- New `AssessmentPage` stages the unchanged Analysis,
  Findings, FinalReview, Package, and History screens
  as tabs (run → review → final → package, history
  secondary), opening on the stage the client state
  implies. Relative in-component navigation
  (`../review`, `../package`) still resolves because
  the established routes remain mounted.

## 8. Shipments and Settings

- `ShipmentsPage` lists device-remembered shipments
  by human identity with workflow state, open and
  forget actions; forgetting is device-local only.
- `SettingsPage` shows session method (never secret
  values), the API endpoint, sign out, and a
  workspace-data note. No backend settings exist, so
  none are presented.

## 9. Visual direction and accessibility

Information architecture first: existing classes,
tokens, and components reused throughout (a small
addition for tab selected-state, landing hero, and
the route line). Keyboard tab lists with arrow-key
support, labelled controls, `role="alert"` errors,
`aria-live` statuses, text+dot badges, inherited
focus outlines and control-height targets, existing
reduced-motion and 860px/390px responsive behavior.
Verified statically and in jsdom; no browser engine
was available, so no pixel-perfect claim is made.

## 10. Verification

- Focused: new suites for shipments lib, landing,
  new shipment, shipments, documents tabs,
  assessment stages, settings (28 tests), plus
  updated AppShell, WorkspacePage, and Overview
  suites — all passing.
- Full frontend suite: **36 files / 208 tests
  passing** (baseline 27/157 at Phase 10.5; +9 files,
  +51 tests), 0 failures. Existing suites updated
  only where navigation assertions described the old
  IA; strictness preserved (same counts, same
  semantics coverage).
- `npx tsc --noEmit` clean; `npm run build`
  succeeds (67 modules).
- Backend untouched: no backend suite re-run
  required. Live services not executed (no
  environment), as before. No packages installed.

## 11. Explicitly NOT implemented

Dark foundation/off-white/lime visual redesign
(structured for, not applied); conversational
upload; chat changes; evidence deletion; retention
policy; workflow reopening; background queue;
notifications; RAG, reasoning, or compliance-rule
changes; provider migration; deployment
infrastructure. No commit/push performed.
