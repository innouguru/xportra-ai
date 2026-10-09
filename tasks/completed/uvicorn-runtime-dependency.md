# uvicorn-runtime-dependency — Complete

Micro-task fixing Render startup `uvicorn: command not found`.
Complete 2026-10-08.

## Root cause (verified, not assumed)

git HEAD `pyproject.toml` declares no Uvicorn dependency; the
`uvicorn[standard]>=0.30,<1.0` line existed only in the uncommitted
working tree. Render builds from the pushed commit, so
`pip install -e .` installed FastAPI et al. but no `uvicorn` console
script — while the (unchanged, correct) start command invokes
exactly that script. Local venv confirms the healthy end state:
uvicorn dist 0.54.0 (satisfies `>=0.30,<1.0`), executable on PATH.

## Change

No dependency line needed writing — the existing
`uvicorn[standard]>=0.30,<1.0` runtime declaration is the correct
fix (range-pinned per CD-10–CD-13 policy; `[standard]` = production
server extras; single occurrence, no duplication, no new
mechanism). Added regression coverage so it cannot silently regress:

- New `tests/unit/test_production_runtime_dependencies.py`
  (stdlib only): uvicorn declared; constraint range-pinned
  (`>=` + `,<`); no duplicate runtime deps; installed dist
  exposes the `uvicorn` console script (the exact failure mode).
- `XPORTA-V1-DEPLOYMENT.md` §7: note that the start command
  requires the declared dependency + deploy-from-a-commit containing
  it + clear-build-cache guidance.

No Python-requirement, start-command, Supabase, Qdrant, auth, CORS,
frontend, architecture, or dependency change beyond keeping the
existing declaration.

## Tests

- New file: 4/4 pass. Full `pytest tests`: **2077 passed,
  51 skipped (gated), 63 subtests, 0 failures**. No deploy, no
  installs, no live services.

## Files changed (this task only)

- `tests/unit/test_production_runtime_dependencies.py` (new)
- `docs/deployment/XPORTA-V1-DEPLOYMENT.md` (§7 note)
- `ACTIVE_TASK.md`, `CURRENT_STATE.md`, this record (state)

The `pyproject.toml` uvicorn line itself predates this task
(uncommitted working-tree change); this task pins and documents it.

## Remaining deployment action (operator)

Commit + push so Render builds a tree containing the uvicorn
declaration (repo convention has held everything uncommitted —
this failure is the cost of that), then on Render: Clear build
cache & deploy (a cached env predating the declaration will keep
failing), and re-run the start command. No app-side action remains.
