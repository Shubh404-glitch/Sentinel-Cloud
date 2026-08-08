"""Response shapes for Stage 5's read-side API (Section 8: Dashboard,
Projects, Assets, Report Center, Risk Center, Recommendations,
Infrastructure Timeline, Analytics, Search)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Consistent pagination envelope used by every Stage 5 list
    endpoint: items for this page, the total count across all pages
    (so a client can render "X of Y" / compute page count), and the
    limit/offset that produced this page."""

    items: list[T]
    total: int
    limit: int
    offset: int


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    criticality: str
    created_at: datetime


class ProjectStatisticsResponse(ProjectResponse):
    asset_count: int
    open_finding_count: int
    average_asset_score: float | None


class ProjectCreateRequest(BaseModel):
    name: str
    criticality: str = "medium"


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    criticality: str | None = None


class AssetResponse(BaseModel):
    id: uuid.UUID
    identifier: str
    display_name: str | None
    tags: list[str] | None
    current_score: float | None
    knowledge_depth_label: str


class AssetDetailResponse(AssetResponse):
    extensions: dict | None
    knowledge_depth_report_count: int


class AssetScoreHistoryEntry(BaseModel):
    score: float
    contributing_factors: dict
    created_at: datetime


class FindingResponse(BaseModel):
    id: uuid.UUID
    title: str
    description: str
    severity: str
    is_new: bool | None
    is_recurring: bool | None
    is_resolved: bool | None
    cve_ids: list[str] | None
    threat_reference_entry_id: uuid.UUID | None


class RecommendationResponse(BaseModel):
    id: uuid.UUID
    title: str
    rationale: str
    priority_rank: int
    finding_ids: list[uuid.UUID]


class SecurityScoreResponse(BaseModel):
    scope: str
    score: float
    contributing_factors: dict
    created_at: datetime


class TimelineEventResponse(BaseModel):
    id: uuid.UUID
    event_type: str
    summary: str
    asset_id: uuid.UUID | None
    project_id: uuid.UUID | None
    created_at: datetime


class ReportSummaryResponse(BaseModel):
    id: uuid.UUID
    source_edition: str
    schema_version: str
    processing_status: str
    processing_failure_reason: str | None
    created_at: datetime
    has_raw_blob: bool
    # The storage key itself is deliberately NOT exposed here (Section
    # 15: minimize what's returned to a caller) -- a future download
    # endpoint would resolve id -> a short-lived signed URL server-side
    # rather than handing back the raw object-storage key/path.


class DashboardResponse(BaseModel):
    organization_score: SecurityScoreResponse | None
    project_count: int
    asset_count: int
    open_finding_count: int
    risk_distribution: dict[str, int]  # severity -> count, across the whole Organization
    recent_timeline_events: list[TimelineEventResponse]


class AnalyticsResponse(BaseModel):
    total_open_findings: int
    findings_by_severity: dict[str, int]
    total_assets: int
    average_asset_score: float | None


class ScoreTrendPoint(BaseModel):
    score: float
    created_at: datetime


class AnalyticsTrendsResponse(BaseModel):
    """Section 8 Analytics: "exposure over time... remediation
    velocity" -- the historical half of Analytics, distinct from the
    point-in-time AnalyticsResponse above. Populated directly from
    SecurityScoreSnapshot history (Section 12's Knowledge Evolution:
    this naturally gets more meaningful as more Reports accumulate)."""

    score_trend: list[ScoreTrendPoint]


class SearchResultResponse(BaseModel):
    entity_type: str  # "asset" | "finding" | "report" | "recommendation"
    entity_id: uuid.UUID
    label: str


# -- Stage 7: Organization Administration ---------------------------------
# RoleEnum's own contract (domain/enums.py): "ADMIN: manage Users,
# ApiKeys, Projects within the Organization." Projects got CRUD in
# Stage 5; Users and ApiKeys never did -- see the Stage 7 Completion
# Report for why that was a genuine, concrete gap (no way to actually
# provision an ingestion API key, or add a teammate, through the API).


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime


class UserCreateRequest(BaseModel):
    """No email/SMTP infrastructure exists anywhere in this system
    (verified before designing this), so there is no "invite" flow --
    an ADMIN directly sets the new user's initial password, the same
    trust model already used for ApiKeyCreateRequest below."""

    email: str
    display_name: str
    password: str
    role: str = "member"


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    name: str
    key_prefix: str
    is_active: bool
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreateRequest(BaseModel):
    name: str


class ApiKeyCreateResponse(ApiKeyResponse):
    """The raw key is included ONLY in the response to the create call
    that generated it -- ApiKeyResponse (used by list/get) never has
    this field, matching domain/api_key.py's own "shown exactly once"
    contract."""

    raw_key: str


class AuditLogEntryResponse(BaseModel):
    id: uuid.UUID
    action: str
    affected_entity_type: str
    affected_entity_id: uuid.UUID | None
    user_id: uuid.UUID | None
    api_key_id: uuid.UUID | None
    metadata_json: dict
    created_at: datetime
