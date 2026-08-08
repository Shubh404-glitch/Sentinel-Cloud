"""API Keys API (Stage 7: Organization Administration). RoleEnum's own
contract: "ADMIN: manage ... ApiKeys ... within the Organization" --
every operation here (including list) is ADMIN-only, unlike Users,
since an ApiKey's mere existence/name/prefix is itself sensitive
administrative metadata about how the Organization's ingestion is
configured, not something every MEMBER needs visibility into.

The raw key is shown exactly once, at creation (domain/api_key.py's own
documented contract) -- ApiKeyCreateResponse is the only schema with a
raw_key field, and it is never persisted anywhere (security/
api_key_hashing.py's generate_api_key() only ever returns it in memory).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from sentinelscan_cloud.api.deps.auth import require_role
from sentinelscan_cloud.api.schemas.read_models import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    PaginatedResponse,
)
from sentinelscan_cloud.db.session import get_db_session
from sentinelscan_cloud.domain.api_key import ApiKey
from sentinelscan_cloud.domain.enums import RoleEnum
from sentinelscan_cloud.domain.user import User
from sentinelscan_cloud.repositories.api_key_repository import ApiKeyRepository
from sentinelscan_cloud.repositories.audit_log_entry_repository import AuditLogEntryRepository
from sentinelscan_cloud.security.api_key_hashing import generate_api_key

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


def _to_response(k: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=k.id, name=k.name, key_prefix=k.key_prefix, is_active=k.is_active, revoked_at=k.revoked_at,
        created_at=k.created_at,
    )


@router.get("", response_model=PaginatedResponse[ApiKeyResponse])
async def list_api_keys(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role(RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedResponse[ApiKeyResponse]:
    repo = ApiKeyRepository(session, organization_id=current_user.organization_id)
    keys = await repo.list_all(limit=limit, offset=offset)
    total = await repo.count_all()
    return PaginatedResponse(items=[_to_response(k) for k in keys], total=total, limit=limit, offset=offset)


@router.post("", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreateRequest,
    current_user: User = Depends(require_role(RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db_session),
) -> ApiKeyCreateResponse:
    raw_key, key_prefix, hashed_key = generate_api_key()
    api_key = ApiKey(
        organization_id=current_user.organization_id, name=body.name, hashed_key=hashed_key, key_prefix=key_prefix,
    )
    session.add(api_key)
    await session.flush()

    audit_repo = AuditLogEntryRepository(session, organization_id=current_user.organization_id)
    audit_repo.record(
        action="api_key.created", affected_entity_type="ApiKey", affected_entity_id=api_key.id,
        user_id=current_user.id, metadata={"name": api_key.name, "key_prefix": api_key.key_prefix},
    )
    await session.commit()
    await session.refresh(api_key)

    return ApiKeyCreateResponse(
        id=api_key.id, name=api_key.name, key_prefix=api_key.key_prefix, is_active=api_key.is_active,
        revoked_at=api_key.revoked_at, created_at=api_key.created_at, raw_key=raw_key,
    )


@router.delete("/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    api_key_id: uuid.UUID,
    current_user: User = Depends(require_role(RoleEnum.ADMIN)),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Revoke, not delete (Section 15's write-only-credential model
    doesn't need a hard-delete path, and revoking preserves the row for
    AuditLogEntry/observability -- a deleted ApiKey row would cascade-
    delete via ON DELETE CASCADE and silently lose that history)."""
    repo = ApiKeyRepository(session, organization_id=current_user.organization_id)
    api_key = await repo.get_by_id(api_key_id)
    if api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")

    api_key.is_active = False
    api_key.revoked_at = datetime.now(timezone.utc)

    audit_repo = AuditLogEntryRepository(session, organization_id=current_user.organization_id)
    audit_repo.record(
        action="api_key.revoked", affected_entity_type="ApiKey", affected_entity_id=api_key.id,
        user_id=current_user.id, metadata={"name": api_key.name},
    )
    await session.commit()
