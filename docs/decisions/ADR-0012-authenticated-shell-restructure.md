# ADR-0012: Authenticated shell restructure (shipment-first expandable sidebar)

- Status: Accepted (requirements/architecture only — no implementation)
- Date: 2026-09-28
- Scope: Future authenticated application shell; constrains
  implementation subtasks 10.8A–10.8J
  (`docs/phases/phase-10-8-ui-ux-redesign-requirements.md`)
- Requirements: `REQUIREMENTS.md` R-10.8 (R-10.8.1–R-10.8.6,
  R-10.8.13–R-10.8.15 for shell concerns)

## Context

The Phase 10.7A information architecture exposes backend
and domain concepts as primary navigation: Overview,
Shipments, Documents, Requirements, Assessment, plus Ask
Xportra and Settings (`REQUIREMENTS.md` R-10.7A.2). The
Phase 10.7B visual system renders that model in a
topbar-oriented shell (sidebar layout only at 1100px and
above; wrapping topbar below). That implementation is
technically valid, but the product owner has explicitly
approved a new product experience direction: Xportra as
a calm compliance workspace for exporters and operations
staff, organized around the user's mental model — which
shipments are in progress, what is happening, what needs
attention, what to do next — rather than around internal
workflow stages. The prior R2 shell attempt was
correctly blocked for lack of approved requirements;
this ADR plus R-10.8 closes that governance gap.

## Decision

Move from the Phase 10.7 topbar-oriented shell and
navigation model to a shipment-first expandable-sidebar
workspace:

1. **Primary navigation is shipment concepts only.**
   Xportra brand, Dashboard, View Shipments, Account.
   Documents, Requirements, Evidence, and Assessment
   leave the primary navigation and are encountered
   within a shipment (R-10.8.1, R-10.8.8).
2. **Public and authenticated experiences separate.**
   Public `/` is the marketing/product landing page;
   the authenticated app is a distinct workspace.
   The authenticated Xportra logo opens the public
   landing page in a new browser tab without signing
   the user out; exact routing is deferred to
   Phase 10.8B (R-10.8.2).
3. **Sidebar shell.** Expandable sidebar (~240px
   expanded), user-controlled collapse, automatic
   collapse at smaller desktop widths, mobile
   hamburger-triggered drawer, brand mark retained
   when collapsed, avatar/account control and a
   subtle notification entry point in the shell,
   stable workspace frame for contextual page
   layouts, no bottom navigation (R-10.8.3,
   R-10.8.13).
4. **Account and notifications are shell placement
   only for now.** Avatar menu (Profile,
   Organization, Settings, Sign out) and the
   subtle notification entry point ship as
   navigation/menu shell; their pages and any
   notification center arrive later (R-10.8.4,
   R-10.8.5; full pages in 10.8I).
5. **Theme behavior.** Dark default plus light
   theme, existing palette retained (dark green /
   near-black, off-white, electric lime accent,
   restrained semantics). This explicitly
   supersedes the R-10.7B.5 theme-switcher
   exclusion (R-10.8.6).
6. **Accessibility is structural, not decorative.**
   Keyboard navigation, semantic landmarks, visible
   focus, screen-reader and status communication,
   drawer/modal focus management, reduced motion,
   never color-alone status (R-10.8.14).

## Alternatives considered

1. **Keep the Phase 10.7 topbar + concept navigation
   and restyle only.** Rejected: the objection is
   the navigation model itself (domain concepts as
   destinations), which a restyle cannot fix; the
   product owner explicitly approved the
   shipment-first direction.
2. **Bottom navigation on mobile.** Rejected: the
   approved responsive model is a hamburger drawer
   (R-10.8.13); a bottom bar would add a second
   navigation paradigm to maintain.
3. **Full notification center in the first shell
   task.** Rejected: notifications stay quiet and
   informational with a subtle entry point first
   (R-10.8.5); the center remains out of scope.

## Consequences

- Implementation subtasks 10.8A–10.8J follow in
  sequence; 10.8B (shell) migrates navigation,
  brand behavior, account/notification placement,
  theme switching, and responsive/accessible
  drawer semantics. Existing routes stay mounted
  until their replacements land; no route is
  removed silently.
- The Phase 10.7A/10.7B implementation remains the
  running UI until 10.8B replaces it; no existing
  navigation is removed by this ADR.
- Historical Phase 10.7A/10.7B records are
  unchanged. Supersessions are recorded
  explicitly: R-10.7A.2 (primary nav direction),
  R-10.7B.3 (topbar-oriented shell model), and
  R-10.7B.5 (theme-switcher exclusion) are
  superseded as direction for future
  implementation; the notifications exclusions in
  R-10.1.9, R-10.4.8, R-10.5.4, and R-10.6.6 are
  narrowed to the entry-point scope only.
- No code, schema, endpoint, contract, or behavior
  changed by this ADR.
