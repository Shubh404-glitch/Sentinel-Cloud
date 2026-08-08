"""
FastAPI application entrypoint.

Section 9 (Backend Architecture): "API layer: thin -- validates input
shape, enforces tenant scoping and auth, delegates to the application
layer, shapes the response. No business logic lives in a route
handler." Stage 1 wires up only the health-check route; every other
route in Section 4's api/routes/ listing is added alongside the stage
that implements its underlying feature (ingestion in Stage 3, dashboard
reads in Stage 5, etc.) rather than stubbed out empty now.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sentinelscan_cloud.api.middleware.auth_context import AuthContextMiddleware
from sentinelscan_cloud.api.routes import (
    analytics,
    api_keys,
    assets,
    audit_log,
    auth,
    dashboard,
    health,
    ingestion,
    projects,
    recommendations,
    reports,
    risk_center,
    search,
    timeline,
    users,
)
from sentinelscan_cloud.config.settings import get_settings
from sentinelscan_cloud.ingestion.job_queue import get_job_queue
from sentinelscan_cloud.intelligence.queue_registration import (
    register_intelligence_processing_handler,
)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "SentinelScan Cloud -- Understand, Prioritize, Decide. "
        "Intelligence and decision support over reports already produced "
        "by SentinelScan Discover or SentinelScan Operate. Never scans."
    ),
    version="0.1.0",
)

# -------------------------
# CORS
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication Context
app.add_middleware(AuthContextMiddleware)


@app.on_event("startup")
async def _register_job_handlers() -> None:
    """
    Stage 4 queue integration: wires the Intelligence Processing
    pipeline into the JobQueue.
    """
    register_intelligence_processing_handler(get_job_queue())


# -------------------------
# Routers
# -------------------------
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(ingestion.router)
app.include_router(dashboard.router)
app.include_router(projects.router)
app.include_router(assets.router)
app.include_router(reports.router)
app.include_router(risk_center.router)
app.include_router(recommendations.router)
app.include_router(timeline.router)
app.include_router(analytics.router)
app.include_router(search.router)
app.include_router(users.router)
app.include_router(api_keys.router)
app.include_router(audit_log.router)