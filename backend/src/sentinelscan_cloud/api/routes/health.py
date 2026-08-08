"""
Health-check endpoint.

Deliberately checks real database connectivity (db.session.check_database_connectivity)
rather than just returning 200 unconditionally -- a health check that
can't fail is not a health check. Returns 200 with status="ok" only if
the database round-trip actually succeeds; 503 with status="degraded"
and the failure reason otherwise, so an orchestrator/load balancer can
tell the difference between "process is up" and "process can actually
do its job."
"""
from __future__ import annotations

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from sentinelscan_cloud.db.session import check_database_connectivity

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    database: str
    detail: str | None = None


@router.get("/health", response_model=HealthResponse)
async def health_check(response: Response) -> HealthResponse:
    try:
        ok = await check_database_connectivity()
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: any DB failure must degrade, not crash
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="degraded", database="unreachable", detail=str(exc))

    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="degraded", database="unreachable")

    return HealthResponse(status="ok", database="reachable")
