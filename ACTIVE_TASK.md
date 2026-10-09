# ACTIVE_TASK.md — Current Active Task

## Task: production-wiring-release

**Status:** In progress (2026-10-08).

Release commit carrying the complete coherent production-wiring
changes Render needs (diagnosed: pushed `86f1aca` lacks
`health.py`/registration → `/health` 404): health endpoint +
registration, lifespan composition, SUPABASE_URL gate, Qdrant
API-key support (both paths), Qdrant spec docs (§14), completed
secure-CORS-boundary work the API requires, and all associated
regression tests + task records. No implementation changes (code
already correct), no deploy, no Render config change. Staging only
the release set; scratch artifacts and cumulative state stay out.
Task record: `tasks/active/production-wiring-release.md`.
