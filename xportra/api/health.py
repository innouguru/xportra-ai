"""Process-liveness probe for hosted execution (render-production-wiring).

Exactly one unauthenticated route::

    GET /health → 200 {"status": "ok"}

This is liveness only, never readiness: the handler takes no
dependencies, opens no database connection, contacts no Supabase,
Qdrant, or OpenRouter service, and reads no configuration. It answers
200 whenever the application process is alive and routing works — including
while downstream services are down — so a hosting provider health check
stays routable during downstream outages. Authenticated endpoint behavior
is unchanged; use an authenticated read (e.g. ``GET /compliance/shipments``)
where database/tenancy verification is required.
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Report process liveness with a minimal stable body."""
    return {"status": "ok"}
