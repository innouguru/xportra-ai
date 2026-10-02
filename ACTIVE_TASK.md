# ACTIVE_TASK.md — Current Active Task

## Task: Landing Page Motion & Sticky Header

**Status:** Complete (2026-09-28).

Focused public-landing enhancement on the
approved redesign: sticky header with quiet
scrolled treatment, restrained hero entrance,
scroll reveals, and one editorial workflow
diagram (Shipment → Requirements → Evidence
→ Ready). Reduced-motion support, no new
dependencies, no other screens touched.

Verification: full frontend suite 62 files /
410 tests, 0 failures (none weakened);
`npx tsc --noEmit` clean; `npm run build`
succeeds; production preview serves `/` at
200. No browser engine exists: final human
visual review remains the gate. No commit or
push performed.
