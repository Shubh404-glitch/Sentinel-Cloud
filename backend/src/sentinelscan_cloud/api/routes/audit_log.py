"""Audit Log API (Stage 7: Organization Administration). Read-only --
AuditLogEntryRepository exposes no update/delete (domain/audit_log_entry.py:
append-only). ADMIN-only: an audit trail of every Project/User/ApiKey/
Recommendation-status mutation in the Organization is compliance-
relevant, not something every MEMBER needs to browse.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.api.deps.auth import require_role
from sentinelscan_cloud.api.schemas.read_models import AuditLogEntryResponse, PaginatedResponse
from sentinelscan_cloud.db.session import get_db_session
from sentinelscan_cloud.domain.audit_log_entry import AuditLogEntry
from sentinelscan_cloud.domain.enums import RoleEnum
from sentinelscan_cloud.domain.user import User
from sentinelscan_cloud.repositories.audit_log_entry_repository import AuditLogEntryRepository

router = APIRouter(prefix="/audit-log", tags=["audit-log"])


def _to_response(e: AuditLogEntry) -> AuditLogEntryResponse:
    return AuditLogEntryResponse(
        id=e.id, action=e.action, affected_entity_type=e.affected_entity_type,
        affected_entity_id=e.affected_entity_id, user_id=e.user_id, api_key_id=e.api_key_id,
        metadata_json=e.metadata_json, created_at=e.created_at,
    )


@router.get("", response_model=PaginatedResponse[AuditLogEntryResponse])
async def list_audit_log(
    action: str | None = Query(default=None, description="Exact match, e.g. 'project.created'."),
    affected_entity_type: str | None = Query(default=None, description="Exact match, e.g. 'Project'."),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role(RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[AuditLogEntryResponse]:
    repo = AuditLogEntryRepository(session, organization_id=current_user.organization_id)
    entries = await repo.list_filtered(
        action=action, affected_entity_type=affected_entity_type, limit=limit, offset=offset
    )
    total = await repo.count_filtered(action=action, affected_entity_type=affected_entity_type)
    return PaginatedResponse(items=[_to_response(e) for e in entries], total=total, limit=limit, offset=offset)
